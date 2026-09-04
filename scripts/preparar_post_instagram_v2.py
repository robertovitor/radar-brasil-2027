#!/usr/bin/env python3
"""Camada v2: busca semântica por entidade e fallback textual limpo, sem cortar título."""
from __future__ import annotations
import hashlib, pathlib, re
from PIL import Image, ImageDraw
import preparar_post_instagram_curado as base
import preparar_post_instagram_sem_repetir_imagem as smart

# Título completo é obrigatório. Pode usar até 5 linhas, mas nunca reticências/corte.
base.MAX_TITLE_LINES = 5
smart.base.MAX_TITLE_LINES = 5


def fit_title_complete(draw, title, width, start_size=88, min_size=58, max_lines=5):
    title = base.clean(title)
    for size in range(start_size, min_size - 1, -2):
        f = base.font(size, True)
        lines = base.wrap(draw, title, f, width)
        if len(lines) <= max_lines:
            return f, lines, True
    f = base.font(min_size, True)
    lines = base.wrap(draw, title, f, width)
    return f, lines, len(lines) <= max_lines


base.fit_title = fit_title_complete
smart.base.fit_title = fit_title_complete


def make_clean_fallback(out, title, kind, subtitle, key):
    """Fallback inspirado no layout antigo: limpo, alto contraste e título integral."""
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    bg = (5, 69, 48) if kind == 'evento' else (12, 61, 84)
    im = Image.new('RGB', (1080, 1080), bg)
    draw = ImageDraw.Draw(im, 'RGBA')

    # Fundo discreto: círculos grandes com baixa opacidade, sem competir com o texto.
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

    f, lines, readable = fit_title_complete(draw, title, width, start_size=82, min_size=58, max_lines=5)
    y = 300
    step = f.size + 10
    for line in lines:
        draw.text((safe_left, y), line, font=f, fill='white')
        y += step

    # Metadado só aparece se houver espaço; título sempre tem prioridade.
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
    return readable and f.size >= 58 and len(lines) <= 5, f.size, len(lines)


base.make_original_art = make_clean_fallback
smart.base.make_original_art = make_clean_fallback

# Busca semântica explícita por entidade central antes das consultas contextuais longas.
_original_variants = smart.query_variants

def semantic_entity_variants(item):
    title = base.clean(item.get('title'))
    context = base.clean(item.get('search_context'))
    variants = []
    def add(q):
        q = base.clean(q)
        if q and base.norm(q) not in {base.norm(x) for x in variants}:
            variants.append(q)

    # Pessoas/entidades no começo do título ganham consultas diretas.
    words = re.findall(r"[A-Za-zÀ-ÿ0-9'-]+", title)
    stop = {'Copa','Mundo','Mundial','Brasil','Brasileira','Feminina','Feminino','Radar','Notícia','Evento'}
    proper = [w for w in words[:12] if w[:1].isupper() and w not in stop and len(w) > 3]
    if proper:
        entity = ' '.join(proper[:2])
        add(entity + ' futebol feminino')
        add(entity + ' jogadora Brasil')
        add(entity + ' seleção brasileira feminina')
    # Para nomes muito conhecidos escritos sem padrão de maiúsculas, preserve os primeiros termos relevantes.
    terms = base.distinct_terms(title)
    if terms:
        add(' '.join(terms[:2]) + ' futebol feminino')
        add(' '.join(terms[:3]) + ' Brasil')
    for q in _original_variants(item):
        add(q)
    return variants[:7]

smart.query_variants = semantic_entity_variants

if __name__ == '__main__':
    raise SystemExit(smart.main())
