#!/usr/bin/env python3
"""Seleciona imagem aberta/licenciada relevante para o Instagram com busca contextual e orçamento controlado."""
from __future__ import annotations

import html as html_lib
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request

import preparar_post_instagram_curado as base

OPENVERSE_API = 'https://api.openverse.org/v1/images/'
ALLOWED_OPENVERSE_LICENSES = {'cc0', 'by', 'by-sa', 'pdm'}
REQUEST_BUDGET = {'page': 3, 'openverse': 8, 'commons': 2}
SOURCE_BLOCKED = {'openverse': False, 'commons': False}
CACHE = {}
ITEM_SEARCH_COUNT = 0
MAX_ITEMS_WITH_EXTERNAL_SEARCH = 5


def clean_url(value):
    value = str(value or '').strip()
    if not value:
        return ''
    p = urllib.parse.urlsplit(value)
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, '', ''))


def image_identity(value):
    url = clean_url(value)
    if not url:
        return ''
    p = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(p.path)
    if '/wiki/' in path:
        title = path.split('/wiki/', 1)[1].replace('_', ' ')
        return 'commons:' + title.casefold()
    if '/thumb/' in path:
        before_size = path.rsplit('/', 1)[0]
        filename = before_size.rsplit('/', 1)[-1]
        return 'commons-file:' + filename.casefold()
    filename = path.rsplit('/', 1)[-1]
    return (p.netloc.lower() + ':' + filename.casefold()) if filename else url


def used_image_identities():
    ledger = base.load('instagram/publicados.json', {'published': []})
    used = set()
    for row in ledger.get('published', []):
        post_file = str(row.get('post_file') or '').strip()
        if not post_file:
            continue
        p = pathlib.Path(post_file)
        if not p.exists():
            continue
        try:
            post = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        for field in ('image_page_url', 'source_page_url', 'image_source_url', 'image_url'):
            ident = image_identity(post.get(field))
            if ident:
                used.add(ident)
    return used


def candidate_identities(source_url='', source_page_url=''):
    return {x for x in (image_identity(source_url), image_identity(source_page_url)) if x}


def news_source_url(item):
    key = base.clean(item.get('key'))
    prefix = 'instagram:noticia:'
    if key.startswith(prefix):
        url = key[len(prefix):]
        if url.startswith('http://') or url.startswith('https://'):
            return url
    return ''


def fetch_page_hints(item):
    """Usa a página como pista sem reutilizar automaticamente sua imagem protegida."""
    url = news_source_url(item)
    if not url or REQUEST_BUDGET['page'] <= 0:
        return ''
    cache_key = 'page:' + url
    if cache_key in CACHE:
        return CACHE[cache_key]
    REQUEST_BUDGET['page'] -= 1
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 RadarBrasil2027/2.1',
        'Accept': 'text/html,application/xhtml+xml',
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read(600_000).decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
    except Exception as exc:
        print('source_page_hint_failed=' + type(exc).__name__)
        CACHE[cache_key] = ''
        return ''

    hints = []
    patterns = [
        r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+(?:property|name)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\']([^"\']+)',
        r'<title[^>]*>(.*?)</title>',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I | re.S)
        if match:
            text = re.sub(r'<[^>]+>', ' ', match.group(1))
            text = html_lib.unescape(text)
            text = base.clean(text)
            if text:
                hints.append(text)
    result = ' '.join(hints)[:2500]
    CACHE[cache_key] = result
    if result:
        print('source_page_hint_ok=true')
    return result


def distinct_query_terms(text, limit):
    return base.distinct_terms(text)[:limit]


def query_variants(item):
    """Busca progressiva: entidade/local primeiro; contexto feminino depois."""
    title = base.clean(item.get('title'))
    context = base.clean(item.get('search_context'))
    page_hints = fetch_page_hints(item)
    combined = base.clean(' '.join([title, context, page_hints]))
    terms7 = distinct_query_terms(combined, 7)
    terms5 = distinct_query_terms(combined, 5)
    terms3 = distinct_query_terms(combined, 3)
    variants = []

    def add(q):
        q = base.clean(q)
        if q and base.norm(q) not in {base.norm(x) for x in variants}:
            variants.append(q)

    if terms7:
        add(' '.join(terms7))
    if terms5:
        add(' '.join(terms5))
    if terms3:
        add(' '.join(terms3) + ' women football')
    # Última expansão controlada para fotos temáticas, sem virar busca genérica demais.
    if item.get('type') == 'evento' and terms3:
        add(' '.join(terms3) + ' Brazil')
    return variants[:4]


def http_json(url, source):
    if SOURCE_BLOCKED.get(source) or REQUEST_BUDGET.get(source, 0) <= 0:
        return None
    REQUEST_BUDGET[source] -= 1
    req = urllib.request.Request(url, headers={
        'User-Agent': 'RadarBrasil2027/2.1 (GitHub robertovitor/radar-brasil-2027)',
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        print(f'{source}_search_failed=HTTPError:{exc.code}')
        if exc.code in (429, 403):
            SOURCE_BLOCKED[source] = True
        return None
    except Exception as exc:
        print(f'{source}_search_failed={type(exc).__name__}')
        return None


def text_tokens(value):
    return {base.norm(x) for x in base.distinct_terms(value)}


def female_signal(text):
    n = base.norm(text)
    extra = ('women', 'woman', 'female', 'feminina', 'feminino', 'jogadora', 'jogadoras', 'girls')
    return any(base.norm(marker) in n for marker in base.FEMALE_MARKERS + extra)


def male_blocked(text):
    n = base.norm(text)
    return any(base.norm(marker) in n for marker in base.MALE_BLOCKERS)


def institutional_or_venue_item(item):
    n = base.norm((item.get('search_context') or '') + ' ' + item.get('title', ''))
    markers = tuple(base.INSTITUTIONAL_MARKERS) + ('estadio', 'estádio', 'arena', 'museu', 'cidade', 'prefeitura', 'senado', 'camara', 'câmara')
    return any(base.norm(x) in n for x in markers)


def openverse_score(item, result, query):
    title = base.clean(result.get('title'))
    tags = ' '.join(base.clean(t.get('name')) for t in (result.get('tags') or []) if isinstance(t, dict))
    creator = base.clean(result.get('creator'))
    haystack = ' '.join([title, tags, creator])
    if male_blocked(haystack):
        return -100

    item_text = (item.get('search_context') or '') + ' ' + item.get('title', '')
    item_tokens = text_tokens(item_text)
    image_tokens = text_tokens(haystack)
    query_tokens = text_tokens(query)
    overlap = len(item_tokens & image_tokens)
    query_overlap = len(query_tokens & image_tokens)

    score = overlap * 6 + query_overlap * 3
    if female_signal(haystack):
        score += 10
    if institutional_or_venue_item(item) and overlap >= 1:
        score += 4
    try:
        if int(result.get('width') or 0) >= 900 and int(result.get('height') or 0) >= 600:
            score += 2
    except Exception:
        pass
    return score


def acceptable_threshold(item):
    return 6 if institutional_or_venue_item(item) else 9


def find_openverse_image(item, used):
    if SOURCE_BLOCKED['openverse'] or REQUEST_BUDGET['openverse'] <= 0:
        return None
    best = None
    threshold = acceptable_threshold(item)
    # No máximo duas consultas Openverse por candidato para preservar orçamento.
    for query in query_variants(item)[:2]:
        if REQUEST_BUDGET['openverse'] <= 0 or SOURCE_BLOCKED['openverse']:
            break
        cache_key = 'openverse:' + base.norm(query)
        if cache_key in CACHE:
            data = CACHE[cache_key]
        else:
            params = {'q': query, 'page_size': '25', 'mature': 'false'}
            data = http_json(OPENVERSE_API + '?' + urllib.parse.urlencode(params), 'openverse')
            CACHE[cache_key] = data
        if not data:
            continue

        for result in data.get('results') or []:
            license_id = base.clean(result.get('license')).casefold()
            if license_id not in ALLOWED_OPENVERSE_LICENSES:
                continue
            url = base.clean(result.get('url') or result.get('thumbnail'))
            page = base.clean(result.get('foreign_landing_url'))
            if not url or not page or candidate_identities(url, page) & used:
                continue
            score = openverse_score(item, result, query)
            if score < threshold:
                continue
            if best is None or score > best[0]:
                best = (score, result, url, page, query)
        # Resultado forte encerra cedo e evita chamada extra.
        if best and best[0] >= threshold + 8:
            break

    if not best:
        return None
    score, result, url, page, query = best
    creator = base.clean(result.get('creator')) or 'Autor não informado'
    license_id = base.clean(result.get('license')).upper()
    license_version = base.clean(result.get('license_version'))
    lic = (license_id + (' ' + license_version if license_version else '')).strip()
    print('openverse_image_found=' + query)
    print('openverse_relevance_score=' + str(score))
    return {
        'image_source_url': url,
        'source_page_url': page,
        'credito': creator,
        'licenca': lic or 'Licença aberta via Openverse',
        'reutilizacao_permitida': True,
        'auto_found': True,
        'provider': 'openverse',
        'query': query,
        'semantic_reason': 'openverse_progressive_context_match',
    }


def find_commons_image(item, used):
    if SOURCE_BLOCKED['commons'] or REQUEST_BUDGET['commons'] <= 0:
        return None
    variants = query_variants(item)
    if not variants:
        return None
    query = variants[min(1, len(variants) - 1)]
    params = {
        'action': 'query', 'generator': 'search',
        'gsrsearch': query + ' filetype:bitmap', 'gsrnamespace': '6', 'gsrlimit': '8',
        'prop': 'imageinfo', 'iiprop': 'url|mime|size|extmetadata',
        'format': 'json', 'formatversion': '2',
    }
    data = http_json(base.COMMONS_API + '?' + urllib.parse.urlencode(params), 'commons')
    if not data:
        return None
    pages = (data.get('query') or {}).get('pages') or []
    for page in pages:
        info = (page.get('imageinfo') or [{}])[0]
        mime = base.clean(info.get('mime')).casefold()
        width = int(info.get('width') or 0)
        height = int(info.get('height') or 0)
        meta = info.get('extmetadata') or {}
        if mime not in ('image/jpeg', 'image/png', 'image/webp') or width < 700 or height < 450:
            continue
        if not base.license_allowed(meta):
            continue
        ok, reason = base.semantic_image_ok(item, page, meta, query)
        if not ok:
            # Para local/instituição aceitamos sobreposição textual forte mesmo sem marcador feminino.
            descriptor = base.commons_descriptor(page, meta)
            overlap = len(text_tokens((item.get('search_context') or '') + ' ' + item.get('title', '')) & text_tokens(descriptor))
            if not (institutional_or_venue_item(item) and overlap >= 2):
                continue
            reason = 'commons_venue_or_institution_match'
        url = base.clean(info.get('url'))
        if not url:
            continue
        source_page = 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(base.clean(page.get('title')).replace(' ', '_'), safe=':/()_-')
        if candidate_identities(url, source_page) & used:
            continue
        print('commons_image_found=' + query)
        return {
            'image_source_url': url,
            'source_page_url': source_page,
            'credito': base.commons_credit(meta),
            'licenca': base.commons_license(meta),
            'reutilizacao_permitida': True,
            'auto_found': True,
            'provider': 'commons',
            'query': query,
            'semantic_reason': reason,
        }
    return None


def main():
    global ITEM_SEARCH_COUNT
    used = used_image_identities()

    catalog_path = pathlib.Path('instagram/imagens-curadas.json')
    original_catalog = catalog_path.read_text(encoding='utf-8') if catalog_path.exists() else None
    if original_catalog is not None:
        try:
            catalog = json.loads(original_catalog)
            for item in catalog.get('items', []):
                identities = candidate_identities(item.get('image_source_url'), item.get('source_page_url'))
                if identities & used:
                    item['reutilizacao_permitida'] = False
                    item['bloqueada_por_repeticao'] = True
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except Exception as exc:
            print('catalog_uniqueness_check_failed=' + type(exc).__name__)

    original_find = base.find_commons_image

    def find_smart_public_image(item):
        global ITEM_SEARCH_COUNT
        if ITEM_SEARCH_COUNT >= MAX_ITEMS_WITH_EXTERNAL_SEARCH:
            return None
        ITEM_SEARCH_COUNT += 1
        print('image_search_candidate=' + base.clean(item.get('key')))
        image = find_openverse_image(item, used)
        if image:
            return image
        return find_commons_image(item, used)

    base.find_commons_image = find_smart_public_image
    try:
        result = base.main()
        print('image_search_candidates_used=' + str(ITEM_SEARCH_COUNT))
        print('image_search_budget_remaining=' + json.dumps(REQUEST_BUDGET, sort_keys=True))
        batch = pathlib.Path('instagram/fila/automatica/lote-atual.json')
        if batch.exists():
            try:
                data = json.loads(batch.read_text(encoding='utf-8'))
                for post_file in data.get('posts', []):
                    p = pathlib.Path(post_file)
                    if not p.exists():
                        continue
                    post = json.loads(p.read_text(encoding='utf-8'))
                    identities = candidate_identities(post.get('image_source_url'), post.get('image_page_url'))
                    if identities & used:
                        print('IMAGE_UNIQUE_OK=false')
                        print('found=false')
                        print('reason=duplicate_image_blocked_after_render')
                        return 1
                    post['IMAGE_UNIQUE_OK'] = True
                    p.write_text(json.dumps(post, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                print('IMAGE_UNIQUE_OK=true')
            except Exception as exc:
                print('IMAGE_UNIQUE_OK=false')
                print('uniqueness_final_gate_failed=' + type(exc).__name__)
                return 1
        return result
    finally:
        base.find_commons_image = original_find
        if original_catalog is not None:
            catalog_path.write_text(original_catalog, encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
