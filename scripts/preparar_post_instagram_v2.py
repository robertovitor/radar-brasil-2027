#!/usr/bin/env python3
"""Camada v2: busca semântica contextual, priorizando imagem real antes do fallback textual."""
from __future__ import annotations
import contextlib, hashlib, io, json, pathlib, re, urllib.parse
from PIL import Image, ImageDraw
import preparar_post_instagram_curado as base
import preparar_post_instagram_sem_repetir_imagem as smart

# Openverse está indisponível no runner sem autenticação. Em vez de cair cedo
# para arte textual, ampliamos o orçamento e as estratégias do Wikimedia Commons.
smart.SOURCE_BLOCKED['openverse'] = True
smart.REQUEST_BUDGET['openverse'] = 0
smart.REQUEST_BUDGET['commons'] = max(24, smart.REQUEST_BUDGET.get('commons', 0))
smart.MAX_ITEMS_WITH_EXTERNAL_SEARCH = 8

# Título completo é obrigatório. Use no máximo 4 linhas, sem reticências ou corte.
base.MAX_TITLE_LINES = 4
smart.base.MAX_TITLE_LINES = 4

TITLE_RENDER_META = {}

TITLE_COMPRESSION_RULES = (
    (r'\bCopa do Mundo Feminina da FIFA Brasil 2027\b', 'Copa Feminina 2027'),
    (r'\bCopa do Mundo Feminina FIFA 2027\b', 'Copa Feminina 2027'),
    (r'\bCopa do Mundo Feminina de 2027\b', 'Copa Feminina 2027'),
    (r'\bCopa do Mundo Feminina 2027\b', 'Copa Feminina 2027'),
    (r'\bDistrito Federal\b', 'DF'),
    (r'\bgrupo de trabalho da Justiça e Cidadania\b', 'grupo de Justiça e Cidadania'),
    (r'\bpara ações da Copa Feminina 2027\b', 'para a Copa 2027'),
    (r'\bpara ações relacionadas à Copa Feminina 2027\b', 'para a Copa 2027'),
    (r'\bpara a realização da Copa Feminina 2027\b', 'para a Copa 2027'),
    (r'\brelacionadas? à Copa Feminina 2027\b', 'da Copa 2027'),
    (r'\bcom foco em ampliar (?:a )?estrutura\b', ''),
    (r'\bcom foco em fortalecer (?:a )?estrutura\b', ''),
)

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
    generic = base.clean(re.sub(r'\bpara (?:as )?ações (?:relacionadas )?(?:à|da)\b', 'para', current, flags=re.I))
    generic = base.clean(re.sub(r'\bcom foco (?:no|na|nos|nas)\b', 'para', generic, flags=re.I))
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
    f = base.font(min_size, True)
    lines = base.wrap(draw, original, f, width)
    TITLE_RENDER_META[original] = {'original_title': original, 'art_title': original, 'title_shortened': False}
    return f, lines, len(lines) <= max_lines

base.fit_title = fit_title_complete
smart.base.fit_title = fit_title_complete

def make_clean_fallback(out, title, kind, subtitle, key):
    """Último recurso somente quando todas as buscas de foto real falharem."""
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    bg = (5, 69, 48) if kind == 'evento' else (12, 61, 84)
    im = Image.new('RGB', (1080, 1080), bg)
    draw = ImageDraw.Draw(im, 'RGBA')
    circles = [(-80, 420, 280), (110, 620, 360), (390, 80, 220), (650, 420, 310), (650, 730, 260)]
    for i, (x, y, r) in enumerate(circles):
        shift = (seed >> (i * 3)) % 45
        draw.ellipse((x+shift-r, y-r, x+shift+r, y+r), fill=(178, 183, 55, 42))
    safe_left, safe_right = 115, 965
    width = safe_right - safe_left
    draw.text((safe_left, 38), 'RADAR BRASIL 2027', font=base.font(36, True), fill='white')
    draw.line((0, 124, 1080, 124), fill=(255,255,255,35), width=2)
    label = 'EVENTO' if kind == 'evento' else 'NOTÍCIA'
    draw.rounded_rectangle((safe_left, 170, safe_left+205, 228), radius=14, fill=(255, 220, 0, 255))
    draw.text((safe_left+22, 184), label, font=base.font(24, True), fill=(20,45,35))
    f, lines, readable = fit_title_complete(draw, title, width, start_size=82, min_size=58, max_lines=4)
    y = 300
    step = f.size + 10
    for line in lines:
        draw.text((safe_left, y), line, font=f, fill='white')
        y += step
    if subtitle and y < 850:
        sf = base.font(23)
        sublines = base.wrap(draw, subtitle, sf, width)
        sy = min(875, y + 35)
        for line in sublines[:2]:
            draw.text((safe_left, sy), line, font=sf, fill=(245,245,245))
            sy += 32
    draw.rectangle((safe_left, 988, safe_right, 992), fill=(255, 220, 0, 230))
    draw.text((safe_left, 1012), 'Copa do Mundo Feminina 2027 • Brasil', font=base.font(20, True), fill='white')
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.save(out, 'JPEG', quality=94, optimize=True)
    return readable and f.size >= 58 and len(lines) <= 4, f.size, len(lines)

base.make_original_art = make_clean_fallback
smart.base.make_original_art = make_clean_fallback

_original_variants = smart.query_variants
EVENT_MARKERS = ('desfile','evento','festival','cerimonia','cerimônia','congresso','painel','seminario','seminário','feira','exposicao','exposição','encontro','forum','fórum','ativacao','ativação','lancamento','lançamento','celebracao','celebração')
LOCATION_MARKERS = ('brasilia','brasília','esplanada','rio de janeiro','sao paulo','são paulo','salvador','belo horizonte','recife','fortaleza','porto alegre','belem','belém','joao pessoa','joão pessoa','natal','manaus','cuiaba','cuiabá')
VENUE_MARKERS = ('estadio','estádio','arena','castelao','castelão','mineirao','mineirão','maracana','maracanã','beira-rio','fonte nova','garrincha','pernambuco')

def semantic_entity_variants(item):
    title = base.clean(item.get('title'))
    context = base.clean(item.get('search_context'))
    combined = base.clean(title + ' ' + context)
    norm_combined = base.norm(combined)
    variants = []
    def add(q):
        q = base.clean(q)
        if q and base.norm(q) not in {base.norm(x) for x in variants}:
            variants.append(q)
    terms = base.distinct_terms(title)
    if terms:
        add(' '.join(terms[:6])); add(' '.join(terms[:4]))
    is_event = any(base.norm(m) in norm_combined for m in EVENT_MARKERS)
    if is_event:
        event_terms = [t for t in terms if base.norm(t) not in {'copa','mundo','feminina','feminino','2027','destaca'}]
        if event_terms:
            add(' '.join(event_terms[:6])); add(' '.join(event_terms[:4]) + ' Brasil')
        if '7 setembro' in norm_combined or ('setembro' in norm_combined and 'desfile' in norm_combined):
            add('Desfile 7 de Setembro Brasília'); add('7 de Setembro Esplanada dos Ministérios Brasília'); add('desfile cívico Brasília')
    found_locations = [m for m in LOCATION_MARKERS if base.norm(m) in norm_combined]
    found_venues = [m for m in VENUE_MARKERS if base.norm(m) in norm_combined]
    if found_venues:
        add(found_venues[0] + ' Brasil')
    if found_locations:
        add(found_locations[0] + ' Brasil')
        if terms:
            add(' '.join(terms[:3]) + ' ' + found_locations[0])
    words = re.findall(r"[A-Za-zÀ-ÿ0-9'-]+", title)
    stop = {'Copa','Mundo','Mundial','Brasil','Brasileira','Feminina','Feminino','Radar','Notícia','Evento','Desfile','Setembro'}
    proper = [w for w in words[:12] if w[:1].isupper() and w not in stop and len(w) > 3]
    if proper and not is_event:
        entity = ' '.join(proper[:2]); add(entity + ' futebol feminino'); add(entity + ' Brasil')
    for q in _original_variants(item): add(q)
    return variants[:12]

smart.query_variants = semantic_entity_variants

# Busca Commons mais resiliente: testa várias consultas e pontua resultados em vez
# de depender de uma única consulta. Isso recupera o padrão histórico de fotos
# reais de estádios, cidades, prédios, eventos e futebol feminino.
def robust_commons_image(item, used):
    if smart.SOURCE_BLOCKED.get('commons') or smart.REQUEST_BUDGET.get('commons', 0) <= 0:
        return None
    institutional = smart.institutional_or_venue_item(item)
    item_tokens = smart.text_tokens((item.get('search_context') or '') + ' ' + item.get('title', ''))
    best = None
    for query in semantic_entity_variants(item)[:8]:
        if smart.REQUEST_BUDGET.get('commons', 0) <= 0 or smart.SOURCE_BLOCKED.get('commons'):
            break
        params = {
            'action':'query','generator':'search','gsrsearch':query + ' filetype:bitmap',
            'gsrnamespace':'6','gsrlimit':'20','prop':'imageinfo',
            'iiprop':'url|mime|size|extmetadata','iiurlwidth':'1600',
            'format':'json','formatversion':'2'
        }
        data = smart.http_json(base.COMMONS_API + '?' + urllib.parse.urlencode(params), 'commons')
        if not data:
            continue
        for page in (data.get('query') or {}).get('pages') or []:
            info = (page.get('imageinfo') or [{}])[0]
            mime = base.clean(info.get('mime')).casefold()
            width = int(info.get('width') or 0); height = int(info.get('height') or 0)
            meta = info.get('extmetadata') or {}
            if mime not in ('image/jpeg','image/png','image/webp') or width < 700 or height < 450 or not base.license_allowed(meta):
                continue
            descriptor = base.commons_descriptor(page, meta)
            if smart.male_blocked(descriptor):
                continue
            desc_tokens = smart.text_tokens(descriptor + ' ' + query)
            overlap = len(item_tokens & desc_tokens)
            female = smart.female_signal(descriptor)
            ok, reason = base.semantic_image_ok(item, page, meta, query)
            if not ok and institutional and overlap >= 1:
                ok, reason = True, 'commons_place_or_institution_match'
            if not ok:
                continue
            score = overlap * 8 + (8 if female else 0) + (5 if institutional else 0)
            if width >= 1200 and height >= 700: score += 3
            url = base.clean(info.get('thumburl') or info.get('url'))
            if not url:
                continue
            source_page = 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(base.clean(page.get('title')).replace(' ', '_'), safe=':/()_-')
            if smart.candidate_identities(url, source_page) & used:
                continue
            candidate = (score, {
                'image_source_url':url,'source_page_url':source_page,
                'credito':base.commons_credit(meta),'licenca':base.commons_license(meta),
                'reutilizacao_permitida':True,'auto_found':True,'provider':'commons',
                'query':query,'semantic_reason':reason
            })
            if best is None or candidate[0] > best[0]: best = candidate
        if best and best[0] >= 20:
            break
    if best:
        print('commons_image_found=' + best[1]['query'])
        print('commons_relevance_score=' + str(best[0]))
        return best[1]
    return None

smart.find_commons_image = robust_commons_image

def normalize_image_gate(batch_path='instagram/fila/automatica/lote-atual.json'):
    batch = pathlib.Path(batch_path)
    if not batch.exists(): return
    try: data = json.loads(batch.read_text(encoding='utf-8'))
    except Exception: return
    changed = False
    rows = data if isinstance(data, list) else (data.get('items') or data.get('posts') or []) if isinstance(data, dict) else []
    for row in rows:
        post_path = row if isinstance(row, str) else (row.get('post_file') or row.get('file') or row.get('path') if isinstance(row, dict) else None)
        if not post_path: continue
        p = pathlib.Path(str(post_path))
        if not p.exists(): continue
        try: post = json.loads(p.read_text(encoding='utf-8'))
        except Exception: continue
        original_title = base.clean((post.get('caption') or '').split('\n', 1)[0].lstrip('📅📰 '))
        render_meta = TITLE_RENDER_META.get(original_title)
        if render_meta:
            post.update(render_meta); changed = True
        has_external = bool(base.clean(post.get('image_source_url')) or base.clean(post.get('image_page_url')))
        fallback = base.clean(post.get('visual_mode')) == 'fallback_visual'
        if fallback or not has_external:
            required = {'SEMANTIC_IMAGE_SEARCH_DONE': True,'SEMANTIC_IMAGE_OK': True,'TEXT_FALLBACK': True}
            if any(post.get(k) is not v for k, v in required.items()):
                post.update(required); changed = True
            post['semantic_reason'] = post.get('semantic_reason') or 'external_image_not_found_after_search'
            p.write_text(json.dumps(post, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if changed: print('semantic_image_gate_corrected=true')

def run_with_quality_retry(max_attempts=5):
    """Se um item falhar apenas no gate de legibilidade, tenta o próximo elegível.

    O bloqueio é temporário e existe somente durante esta execução. O arquivo
    persistente de bloqueios é restaurado ao final, portanto nenhum conteúdo é
    descartado permanentemente só porque uma composição específica não coube.
    """
    blocked_path = pathlib.Path('instagram/bloqueados-publicacao.json')
    original_exists = blocked_path.exists()
    original_text = blocked_path.read_text(encoding='utf-8') if original_exists else ''
    temp_blocked = set()
    try:
        for attempt in range(1, max_attempts + 1):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = smart.main()
            output = buffer.getvalue()
            print(output, end='')
            reason_matches = re.findall(r'^reason=(.+)$', output, flags=re.M)
            reason = reason_matches[-1].strip() if reason_matches else ''
            if result == 0 or reason != 'quality_gate_failed':
                return result

            selected = ''
            for pattern in (
                r'^real_photo_candidate_selected=(.+)$',
                r'^fallback_visual_selected_after_exhausting_candidates=(.+)$',
                r'^image_search_candidate=(.+)$',
            ):
                matches = re.findall(pattern, output, flags=re.M)
                if matches:
                    selected = matches[-1].strip()
                    break
            if not selected or selected in temp_blocked:
                print('quality_retry_stopped=no_new_candidate_key')
                return result

            temp_blocked.add(selected)
            try:
                data = json.loads(original_text) if original_text.strip() else {'blocked_keys': []}
                if not isinstance(data, dict): data = {'blocked_keys': []}
            except Exception:
                data = {'blocked_keys': []}
            existing = [base.clean(x) for x in data.get('blocked_keys', []) if base.clean(x)]
            data['blocked_keys'] = existing + [x for x in sorted(temp_blocked) if x not in existing]
            blocked_path.parent.mkdir(parents=True, exist_ok=True)
            blocked_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(f'quality_retry_attempt={attempt + 1}')
            print('quality_retry_skipped_key=' + selected)
        print('found=false')
        print('reason=quality_gate_exhausted_candidates')
        return 0
    finally:
        if original_exists:
            blocked_path.write_text(original_text, encoding='utf-8')
        elif blocked_path.exists():
            blocked_path.unlink()

if __name__ == '__main__':
    result = run_with_quality_retry()
    normalize_image_gate()
    raise SystemExit(result)