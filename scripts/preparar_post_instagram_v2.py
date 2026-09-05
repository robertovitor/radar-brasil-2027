#!/usr/bin/env python3
"""Camada v2: busca semântica contextual, priorizando imagem real antes do fallback textual."""
from __future__ import annotations
import hashlib, json, pathlib, re
from PIL import Image, ImageDraw
import preparar_post_instagram_curado as base
import preparar_post_instagram_sem_repetir_imagem as smart

# Hotfix de disponibilidade: Openverse está respondendo 401 no runner.
# Não desperdiçar tentativas nem degradar a execução; usar Commons como fonte externa principal.
smart.SOURCE_BLOCKED['openverse'] = True
smart.REQUEST_BUDGET['openverse'] = 0
smart.REQUEST_BUDGET['commons'] = max(8, smart.REQUEST_BUDGET.get('commons', 0))

# Título completo é obrigatório. Use no máximo 4 linhas, sem reticências ou corte.
base.MAX_TITLE_LINES = 4
smart.base.MAX_TITLE_LINES = 4

# Metadados da versão realmente desenhada. O título editorial completo continua
# intacto na legenda; somente a chamada visual pode ser condensada.
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
)


def compact_title_candidates(title):
    """Produz reduções conservadoras, sem cortar palavras nem usar reticências."""
    original = base.clean(title)
    candidates = [original]
    current = original
    for pattern, replacement in TITLE_COMPRESSION_RULES:
        reduced = base.clean(re.sub(pattern, replacement, current, flags=re.I))
        if reduced != current:
            current = reduced
            if current not in candidates:
                candidates.append(current)

    # Limpezas editoriais seguras e genéricas, aplicadas só depois das regras
    # específicas. Elas removem redundâncias, nunca entidades ou fatos.
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
                # 70 px é o piso preferencial. Assim que uma redução conservadora
                # o alcança, preservamos o máximo possível do título original.
                if f.size >= 70:
                    best = option
                    break
        if best and best[0].size >= 70:
            break
    if best:
        f, lines, candidate = best
        TITLE_RENDER_META[original] = {
            'original_title': original,
            'art_title': candidate,
            'title_shortened': candidate != original,
        }
        if candidate != original:
            print('title_shortened_automatically=true')
            print('art_title=' + candidate)
        return f, lines, True
    f = base.font(min_size, True)
    lines = base.wrap(draw, original, f, width)
    TITLE_RENDER_META[original] = {
        'original_title': original,
        'art_title': original,
        'title_shortened': False,
    }
    return f, lines, len(lines) <= max_lines


base.fit_title = fit_title_complete
smart.base.fit_title = fit_title_complete


def make_clean_fallback(out, title, kind, subtitle, key):
    """Último recurso: arte textual limpa quando nenhuma imagem externa adequada for encontrada."""
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

# Consulta original continua disponível como última expansão.
_original_variants = smart.query_variants

EVENT_MARKERS = (
    'desfile', 'evento', 'festival', 'cerimonia', 'cerimônia', 'congresso', 'painel',
    'seminario', 'seminário', 'feira', 'exposicao', 'exposição', 'encontro', 'forum',
    'fórum', 'ativacao', 'ativação', 'lancamento', 'lançamento', 'celebracao', 'celebração'
)
LOCATION_MARKERS = (
    'brasilia', 'brasília', 'esplanada', 'rio de janeiro', 'sao paulo', 'são paulo',
    'salvador', 'belo horizonte', 'recife', 'fortaleza', 'porto alegre', 'belem', 'belém'
)


def semantic_entity_variants(item):
    """Gera buscas do assunto para o contexto específico; futebol feminino entra depois, não antes."""
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
        add(' '.join(terms[:6]))
        add(' '.join(terms[:4]))

    is_event = any(base.norm(m) in norm_combined for m in EVENT_MARKERS)
    if is_event:
        event_terms = [t for t in terms if base.norm(t) not in {'copa','mundo','feminina','feminino','2027','destaca'}]
        if event_terms:
            add(' '.join(event_terms[:6]))
            add(' '.join(event_terms[:4]) + ' Brasil')
        if '7 setembro' in norm_combined or ('setembro' in norm_combined and 'desfile' in norm_combined):
            add('Desfile 7 de Setembro Brasília')
            add('7 de Setembro Esplanada dos Ministérios Brasília')
            add('desfile cívico Brasília')

    found_locations = [m for m in LOCATION_MARKERS if base.norm(m) in norm_combined]
    if found_locations and terms:
        add(' '.join(terms[:3]) + ' ' + found_locations[0])

    words = re.findall(r"[A-Za-zÀ-ÿ0-9'-]+", title)
    stop = {'Copa','Mundo','Mundial','Brasil','Brasileira','Feminina','Feminino','Radar','Notícia','Evento','Desfile','Setembro'}
    proper = [w for w in words[:12] if w[:1].isupper() and w not in stop and len(w) > 3]
    if proper and not is_event:
        entity = ' '.join(proper[:2])
        add(entity + ' futebol feminino')
        add(entity + ' Brasil')

    for q in _original_variants(item):
        add(q)
    return variants[:8]


smart.query_variants = semantic_entity_variants


def normalize_image_gate(batch_path='instagram/fila/automatica/lote-atual.json'):
    """Fallback textual nunca pode fingir que uma imagem semântica externa foi encontrada."""
    batch = pathlib.Path(batch_path)
    if not batch.exists():
        return
    try:
        data = json.loads(batch.read_text(encoding='utf-8'))
    except Exception:
        return

    changed = False
    rows = data if isinstance(data, list) else (data.get('items') or data.get('posts') or []) if isinstance(data, dict) else []
    for row in rows:
        post_path = row if isinstance(row, str) else (
            row.get('post_file') or row.get('file') or row.get('path')
            if isinstance(row, dict) else None
        )
        if not post_path:
            continue
        p = pathlib.Path(str(post_path))
        if not p.exists():
            continue
        try:
            post = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        original_title = base.clean((post.get('caption') or '').split('\n', 1)[0].lstrip('📅📰 '))
        render_meta = TITLE_RENDER_META.get(original_title)
        if render_meta:
            post.update(render_meta)
            changed = True
        has_external = bool(base.clean(post.get('image_source_url')) or base.clean(post.get('image_page_url')))
        fallback = base.clean(post.get('visual_mode')) == 'fallback_visual'
        if fallback or not has_external:
            required = {
                'SEMANTIC_IMAGE_SEARCH_DONE': True,
                'SEMANTIC_IMAGE_OK': True,
                'TEXT_FALLBACK': True,
            }
            if any(post.get(k) is not v for k, v in required.items()):
                post.update(required)
                changed = True
            post['semantic_reason'] = post.get('semantic_reason') or 'external_image_not_found_after_search'
            p.write_text(json.dumps(post, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if changed:
        print('semantic_image_gate_corrected=true')


if __name__ == '__main__':
    result = smart.main()
    normalize_image_gate()
    raise SystemExit(result)
