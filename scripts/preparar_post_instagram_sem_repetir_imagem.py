#!/usr/bin/env python3
"""Seleciona imagem pública/licenciada relevante, evitando repetição e excesso de requisições."""
from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request

import preparar_post_instagram_curado as base

OPENVERSE_API = 'https://api.openverse.org/v1/images/'
ALLOWED_OPENVERSE_LICENSES = {'cc0', 'by', 'by-sa', 'pdm'}
REQUEST_BUDGET = {'openverse': 6, 'commons': 3}
SOURCE_BLOCKED = {'openverse': False, 'commons': False}
CACHE = {}


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


def compact_query(item):
    context = item.get('search_context') or item.get('title') or ''
    terms = base.distinct_terms(context)
    # Mantém nomes próprios, cidade, estádio, entidade e tema. Evita consultas gigantes.
    q = ' '.join(terms[:7]).strip()
    if not q:
        q = base.clean(item.get('title'))
    return q


def http_json(url, source):
    if SOURCE_BLOCKED[source] or REQUEST_BUDGET[source] <= 0:
        return None
    REQUEST_BUDGET[source] -= 1
    req = urllib.request.Request(url, headers={
        'User-Agent': 'RadarBrasil2027/2.0 (contact: GitHub robertovitor/radar-brasil-2027)',
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
    return any(base.norm(marker) in n for marker in base.FEMALE_MARKERS)


def male_blocked(text):
    n = base.norm(text)
    return any(base.norm(marker) in n for marker in base.MALE_BLOCKERS)


def openverse_score(item, result):
    title = base.clean(result.get('title'))
    tags = ' '.join(base.clean(t.get('name')) for t in (result.get('tags') or []) if isinstance(t, dict))
    creator = base.clean(result.get('creator'))
    haystack = ' '.join([title, tags, creator])
    if male_blocked(haystack):
        return -100
    item_tokens = text_tokens((item.get('search_context') or '') + ' ' + item.get('title', ''))
    image_tokens = text_tokens(haystack)
    overlap = len(item_tokens & image_tokens)
    score = overlap * 5
    if female_signal(haystack):
        score += 8
    if item.get('type') == 'evento' and overlap >= 2:
        score += 3
    if result.get('width') and result.get('height'):
        try:
            if int(result['width']) >= 900 and int(result['height']) >= 600:
                score += 2
        except Exception:
            pass
    return score


def find_openverse_image(item, used):
    if SOURCE_BLOCKED['openverse'] or REQUEST_BUDGET['openverse'] <= 0:
        return None
    query = compact_query(item)
    cache_key = 'openverse:' + base.norm(query)
    if cache_key in CACHE:
        data = CACHE[cache_key]
    else:
        params = {
            'q': query,
            'page_size': '20',
            'mature': 'false',
        }
        data = http_json(OPENVERSE_API + '?' + urllib.parse.urlencode(params), 'openverse')
        CACHE[cache_key] = data
    if not data:
        return None

    ranked = []
    for result in data.get('results') or []:
        license_id = base.clean(result.get('license')).casefold()
        if license_id not in ALLOWED_OPENVERSE_LICENSES:
            continue
        url = base.clean(result.get('url') or result.get('thumbnail'))
        page = base.clean(result.get('foreign_landing_url'))
        if not url or not page:
            continue
        identities = candidate_identities(url, page)
        if identities & used:
            continue
        score = openverse_score(item, result)
        if score < 8:
            continue
        ranked.append((score, result, url, page))

    if not ranked:
        return None
    ranked.sort(key=lambda x: x[0], reverse=True)
    score, result, url, page = ranked[0]
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
        'query': query,
        'semantic_reason': 'openverse_context_match',
    }


def find_commons_image(item, used):
    if SOURCE_BLOCKED['commons'] or REQUEST_BUDGET['commons'] <= 0:
        return None
    query = compact_query(item)
    params = {
        'action': 'query',
        'generator': 'search',
        'gsrsearch': query + ' filetype:bitmap',
        'gsrnamespace': '6',
        'gsrlimit': '8',
        'prop': 'imageinfo',
        'iiprop': 'url|mime|size|extmetadata',
        'format': 'json',
        'formatversion': '2',
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
            continue
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
            'query': query,
            'semantic_reason': reason,
        }
    return None


def main():
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
        # 1) Openverse agrega imagens abertas de múltiplas fontes da internet.
        image = find_openverse_image(item, used)
        if image:
            return image
        # 2) Commons é fallback secundário, com orçamento pequeno para evitar 429.
        return find_commons_image(item, used)

    base.find_commons_image = find_smart_public_image
    try:
        result = base.main()
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
