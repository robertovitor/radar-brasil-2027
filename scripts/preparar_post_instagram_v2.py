#!/usr/bin/env python3
"""Camada v2: busca semântica contextual, priorizando imagem real antes do fallback textual."""
from __future__ import annotations
import contextlib, hashlib, io, json, pathlib, re, urllib.parse
from PIL import Image, ImageDraw
import preparar_post_instagram_curado as base
import preparar_post_instagram_sem_repetir_imagem as smart

# Openverse continua desabilitado porque já retornou 401 no runner.
# Compensamos com uma busca muito mais ampla no Wikimedia Commons.
smart.SOURCE_BLOCKED['openverse'] = True
smart.REQUEST_BUDGET['openverse'] = 0
smart.REQUEST_BUDGET['commons'] = max(48, smart.REQUEST_BUDGET.get('commons', 0))
smart.MAX_ITEMS_WITH_EXTERNAL_SEARCH = 12
base.MAX_TITLE_LINES = 4
smart.base.MAX_TITLE_LINES = 4
TITLE_RENDER_META = {}

TITLE_COMPRESSION_RULES = (
    (r'\bCopa do Mundo Feminina da FIFA Brasil 2027\b', 'Copa Feminina 2027'),
    (r'\bCopa do Mundo Feminina FIFA 2027\b', 'Copa Feminina 2027'),
    (r'\bCopa do Mundo Feminina de 2027\b', 'Copa Feminina 2027'),
    (r'\bCopa do Mundo Feminina 2027\b', 'Copa Feminina 2027'),
    (r'\bDistrito Federal\b', 'DF'),
    (r'\bpara ações relacionadas à Copa Feminina 2027\b', 'para a Copa 2027'),
    (r'\bpara ações da Copa Feminina 2027\b', 'para a Copa 2027'),
    (r'\brelacionadas? à Copa Feminina 2027\b', 'da Copa 2027'),
    (r'\bcom foco em ampliar (?:a )?estrutura\b', ''),
    (r'\bcom foco em fortalecer (?:a )?estrutura\b', ''),
)

def editorial_short_title(title):
    """Cria headline curta para a ARTE; legenda mantém o título original."""
    t = base.clean(title)
    money = re.search(r'(R\$\s*[\d.,]+\s*(?:milhões|milhão|bilhões|bilhão|mil|bi|mi)?)', t, re.I)
    place = re.search(r'\b(Bahia|Ceará|Fortaleza|Salvador|Brasília|DF|Rio de Janeiro|São Paulo|Recife|Pernambuco|Belo Horizonte|Minas Gerais|Porto Alegre|Rio Grande do Sul|Belém|Pará|João Pessoa|Paraíba|Natal|Manaus|Cuiabá)\b', t, re.I)
    if money and place and ('copa' in base.norm(t)):
        return base.clean(f'{place.group(1)} investe {money.group(1)} de olho na Copa 2027')
    if ':' in t:
        left, right = [base.clean(x) for x in t.split(':', 1)]
        if len(left) >= 24 and len(left) <= 72:
            return left
    s = t
    replacements = (
        (r'\bse prepara para receber turistas (?:durante|na|para a)?\s*(?:Copa(?: do Mundo)?(?: Feminina)?(?: de)? 2027)?\b', 'se prepara para a Copa 2027'),
        (r'\bcom foco (?:em|no|na|nos|nas)\b.*$', ''),
        (r'\bvisando (?:a|ao)\b', 'para'),
        (r'\brumo à Copa do Mundo Feminina de 2027\b', 'rumo à Copa 2027'),
        (r'\brumo à Copa do Mundo Feminina 2027\b', 'rumo à Copa 2027'),
    )
    for pattern, repl in replacements:
        s = base.clean(re.sub(pattern, repl, s, flags=re.I))
    if len(s) > 92:
        parts = re.split(r'\s+(?:e|enquanto|após|durante|para que|que)\s+|[;–—]', s, maxsplit=1, flags=re.I)
        if parts and 30 <= len(base.clean(parts[0])) <= 92:
            s = base.clean(parts[0])
    return s

def compact_title_candidates(title):
    original = base.clean(title)
    candidates = [original]
    current = original
    for pattern, replacement in TITLE_COMPRESSION_RULES:
        reduced = base.clean(re.sub(pattern, replacement, current, flags=re.I))
        if reduced != current:
            current = reduced
            if current not in candidates:
                candidates.append(current)
    editorial = editorial_short_title(current)
    if editorial and editorial not in candidates:
        candidates.append(editorial)
    generic = base.clean(re.sub(r'\bpara (?:as )?ações (?:relacionadas )?(?:à|da)\b', 'para', editorial or current, flags=re.I))
    if generic and generic not in candidates:
        candidates.append(generic)
    return candidates

def fit_title_complete(draw, title, width, start_size=88, min_size=58, max_lines=4):
    original = base.clean(title)
    best = None
    for candidate in compact_title_candidates(original):
        for size in range(start_size, min_size - 1, -2):
            f = base.font(size, True)
            lines = base.wrap(draw, candidate, f, width)
            if len(lines) <= max_lines:
                option = (f, lines, candidate)
                if best is None or f.size > best[0].size:
                    best = option
                if f.size >= 70:
                    best = option
                    break
        if best and best[0].size >= 70:
            break
    if best:
        f, lines, candidate = best
        TITLE_RENDER_META[original] = {'original_title': original, 'art_title': candidate, 'title_shortened': candidate != original}
        if candidate != original:
            print('title_shortened_automatically=true')
            print('art_title=' + candidate)
        return f, lines, True
    candidate = editorial_short_title(original)
    for size in range(76, min_size - 1, -2):
        f = base.font(size, True)
        lines = base.wrap(draw, candidate, f, width)
        if len(lines) <= max_lines:
            TITLE_RENDER_META[original] = {'original_title': original, 'art_title': candidate, 'title_shortened': candidate != original}
            print('title_shortened_automatically=true')
            print('art_title=' + candidate)
            return f, lines, True
    f = base.font(min_size, True)
    lines = base.wrap(draw, original, f, width)
    TITLE_RENDER_META[original] = {'original_title': original, 'art_title': original, 'title_shortened': False}
    return f, lines, len(lines) <= max_lines

base.fit_title = fit_title_complete
smart.base.fit_title = fit_title_complete

def make_clean_fallback(out, title, kind, subtitle, key):
    bg = (5,69,48) if kind == 'evento' else (12,61,84)
    im = Image.new('RGB', (1080,1080), bg)
    draw = ImageDraw.Draw(im, 'RGBA')
    safe_left, safe_right = 115, 965
    width = safe_right - safe_left
    draw.text((safe_left,38), 'RADAR BRASIL 2027', font=base.font(36,True), fill='white')
    label = 'EVENTO' if kind == 'evento' else 'NOTÍCIA'
    draw.rounded_rectangle((safe_left,170,safe_left+205,228), radius=14, fill=(255,220,0,255))
    draw.text((safe_left+22,184), label, font=base.font(24,True), fill=(20,45,35))
    f, lines, readable = fit_title_complete(draw, title, width, start_size=82, min_size=58, max_lines=4)
    y = 300
    for line in lines:
        draw.text((safe_left,y), line, font=f, fill='white')
        y += f.size + 10
    draw.rectangle((safe_left,988,safe_right,992), fill=(255,220,0,230))
    draw.text((safe_left,1012), 'Copa do Mundo Feminina 2027 • Brasil', font=base.font(20,True), fill='white')
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.save(out, 'JPEG', quality=94, optimize=True)
    return readable and f.size >= 58 and len(lines) <= 4, f.size, len(lines)

base.make_original_art = make_clean_fallback
smart.base.make_original_art = make_clean_fallback

_original_variants = smart.query_variants

def semantic_entity_variants(item):
    """Gera consultas mais curtas e variadas para aumentar chance de foto contextual."""
    title = base.clean(item.get('title'))
    context = base.clean(item.get('search_context'))
    variants = []
    def add(q):
        q = base.clean(q)
        if q and base.norm(q) not in {base.norm(x) for x in variants}:
            variants.append(q)
    terms = base.distinct_terms(title + ' ' + context)
    if terms:
        add(' '.join(terms[:7]))
        add(' '.join(terms[:5]))
        add(' '.join(terms[:3]))
    # Entidades e locais conhecidos costumam ter fotos abundantes no Commons.
    entity_patterns = (
        r'\bArena Castelão\b', r'\bCastelão\b', r'\bArena Fonte Nova\b', r'\bFonte Nova\b',
        r'\bMaracanã\b', r'\bMané Garrincha\b', r'\bMineirão\b', r'\bBeira-Rio\b', r'\bNeo Química Arena\b',
        r'\bFortaleza\b', r'\bSalvador\b', r'\bRecife\b', r'\bBrasília\b', r'\bRio de Janeiro\b',
        r'\bSão Paulo\b', r'\bBelo Horizonte\b', r'\bPorto Alegre\b', r'\bBahia\b', r'\bCeará\b',
        r'\bFIFA\b', r'\bCBF\b', r'\bSeleção Brasileira\b', r'\bfutebol feminino\b'
    )
    combined = title + ' ' + context
    for pattern in entity_patterns:
        m = re.search(pattern, combined, re.I)
        if m:
            add(m.group(0))
            if 'futebol' not in base.norm(m.group(0)):
                add(m.group(0) + ' football')
    for q in _original_variants(item):
        add(q)
    return variants[:16]

smart.query_variants = semantic_entity_variants


def relaxed_commons_image(item, used):
    """Busca Commons progressiva e menos rígida, mantendo licença, tamanho e antirrepetição."""
    if smart.SOURCE_BLOCKED.get('commons') or smart.REQUEST_BUDGET.get('commons', 0) <= 0:
        return None
    variants = smart.query_variants(item)
    if not variants:
        return None
    item_text = base.clean((item.get('search_context') or '') + ' ' + item.get('title', ''))
    item_tokens = smart.text_tokens(item_text)
    institutional = smart.institutional_or_venue_item(item)

    for query in variants[:8]:
        if smart.REQUEST_BUDGET.get('commons', 0) <= 0 or smart.SOURCE_BLOCKED.get('commons'):
            break
        params = {
            'action': 'query', 'generator': 'search',
            'gsrsearch': query + ' filetype:bitmap', 'gsrnamespace': '6', 'gsrlimit': '20',
            'prop': 'imageinfo', 'iiprop': 'url|mime|size|extmetadata',
            'format': 'json', 'formatversion': '2',
        }
        data = smart.http_json(base.COMMONS_API + '?' + urllib.parse.urlencode(params), 'commons')
        if not data:
            continue
        pages = (data.get('query') or {}).get('pages') or []
        scored = []
        for page in pages:
            info = (page.get('imageinfo') or [{}])[0]
            mime = base.clean(info.get('mime')).casefold()
            width = int(info.get('width') or 0)
            height = int(info.get('height') or 0)
            meta = info.get('extmetadata') or {}
            if mime not in ('image/jpeg','image/png','image/webp') or width < 650 or height < 400:
                continue
            if not base.license_allowed(meta):
                continue
            descriptor = base.commons_descriptor(page, meta)
            if smart.male_blocked(descriptor):
                continue
            image_tokens = smart.text_tokens(descriptor)
            overlap = len(item_tokens & image_tokens)
            female = smart.female_signal(descriptor)
            semantic_ok, semantic_reason = base.semantic_image_ok(item, page, meta, query)
            # Regra relaxada: para local/estádio/instituição, 1 termo forte basta;
            # para outros temas, aceitamos 2 termos ou sinal feminino + 1 termo.
            acceptable = semantic_ok or (institutional and overlap >= 1) or overlap >= 2 or (female and overlap >= 1)
            if not acceptable:
                continue
            url = base.clean(info.get('url'))
            if not url:
                continue
            source_page = 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(base.clean(page.get('title')).replace(' ','_'), safe=':/()_-')
            if smart.candidate_identities(url, source_page) & used:
                continue
            score = overlap * 10 + (8 if female else 0) + (6 if semantic_ok else 0) + (4 if institutional else 0)
            if width >= 1000 and height >= 650:
                score += 3
            reason = semantic_reason if semantic_ok else ('commons_relaxed_venue_match' if institutional else 'commons_relaxed_context_match')
            scored.append((score, url, source_page, meta, reason))
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            score, url, source_page, meta, reason = scored[0]
            print('commons_image_found=' + query)
            print('commons_relevance_score=' + str(score))
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

# Substitui a busca Commons rígida da camada anterior por uma busca progressiva.
smart.find_commons_image = relaxed_commons_image


def normalize_image_gate(batch_path='instagram/fila/automatica/lote-atual.json'):
    batch = pathlib.Path(batch_path)
    if not batch.exists():
        return
    try:
        data = json.loads(batch.read_text(encoding='utf-8'))
    except Exception:
        return
    rows = data if isinstance(data,list) else (data.get('items') or data.get('posts') or []) if isinstance(data,dict) else []
    changed = False
    for row in rows:
        post_path = row if isinstance(row,str) else (row.get('post_file') or row.get('file') or row.get('path') if isinstance(row,dict) else None)
        if not post_path:
            continue
        p = pathlib.Path(str(post_path))
        if not p.exists():
            continue
        try:
            post = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        original_title = base.clean((post.get('caption') or '').split('\n',1)[0].lstrip('📅📰 '))
        render_meta = TITLE_RENDER_META.get(original_title)
        if render_meta:
            post.update(render_meta)
            changed = True
        has_external = bool(base.clean(post.get('image_source_url')) or base.clean(post.get('image_page_url')))
        fallback = base.clean(post.get('visual_mode')) == 'fallback_visual'
        if fallback or not has_external:
            # Fallback textual continua permitido apenas como último recurso,
            # mas não é mais rotulado como uma foto semântica encontrada.
            post.update({'SEMANTIC_IMAGE_SEARCH_DONE':True,'SEMANTIC_IMAGE_OK':False,'TEXT_FALLBACK':True})
            changed = True
        if changed:
            p.write_text(json.dumps(post, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if changed:
        print('semantic_image_gate_corrected=true')


def run_with_quality_retry(max_attempts=5):
    blocked_path = pathlib.Path('instagram/bloqueados.json')
    original = blocked_path.read_bytes() if blocked_path.exists() else None
    try:
        for attempt in range(1, max_attempts + 1):
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                result = smart.main()
            output = capture.getvalue()
            print(output, end='')
            normalize_image_gate()
            if result == 0:
                return 0
            if 'reason=quality_gate_failed' not in output:
                return result
            m = re.search(r'(?:quality_gate_failed|real_photo_unavailable)=([^\n]+)', output)
            key = base.clean(m.group(1)) if m else ''
            if not key:
                return result
            try:
                blocked = json.loads(blocked_path.read_text(encoding='utf-8')) if blocked_path.exists() else {}
            except Exception:
                blocked = {}
            if isinstance(blocked, list):
                blocked = {str(x):True for x in blocked}
            blocked[key] = {'reason':'temporary_quality_retry','attempt':attempt}
            blocked_path.write_text(json.dumps(blocked, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(f'quality_retry_attempt={attempt}')
            print('quality_retry_skipped_key=' + key)
        return result
    finally:
        if original is None:
            if blocked_path.exists():
                blocked_path.unlink()
        else:
            blocked_path.write_bytes(original)

if __name__ == '__main__':
    result = run_with_quality_retry()
    normalize_image_gate()
    raise SystemExit(result)
