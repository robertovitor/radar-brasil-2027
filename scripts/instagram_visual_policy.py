#!/usr/bin/env python3
"""Política visual isolada do Instagram do Radar Brasil 2027.

Não seleciona conteúdo, não publica e não altera schedules.
Somente renderiza artes por tipo, com fallback controlado pelo chamador.
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import re
from PIL import Image, ImageDraw, ImageFont

POLICY_PATH = pathlib.Path('instagram/visual-policy.json')
DEFAULT_POLICY = {
    'version': 2,
    'enabled': True,
    'fallback_to_legacy': True,
    'opportunity_instagram_enabled': False,
    'types': {
        'evento': 'legacy',
        'noticia': 'legacy',
        'oportunidade': 'legacy',
    },
}


def clean(value):
    return ' '.join(str(value or '').split())


def load_policy(path=POLICY_PATH):
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    try:
        raw = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
        if isinstance(raw, dict):
            for key in ('version', 'enabled', 'fallback_to_legacy', 'opportunity_instagram_enabled'):
                if key in raw:
                    policy[key] = raw[key]
            if isinstance(raw.get('types'), dict):
                policy['types'].update(raw['types'])
    except Exception as exc:
        print('visual_policy_warning=' + type(exc).__name__)
    return policy


def visual_mode(kind, policy=None):
    policy = policy or load_policy()
    if not policy.get('enabled'):
        return 'legacy'
    return clean((policy.get('types') or {}).get(kind)) or 'legacy'


def _pill(draw, xy, text, font, fill, text_fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x0 + (x1 - x0 - tw) / 2, y0 + (y1 - y0 - th) / 2 - 2), text, font=font, fill=text_fill)


def _fit(draw, title, width, fit_title, start=82, max_lines=4):
    return fit_title(draw, clean(title), width, start_size=start, min_size=58, max_lines=max_lines)


def _variant_for(item, modulo):
    key = clean(item.get('key') or item.get('title'))
    digest = hashlib.sha256(key.encode('utf-8')).digest()
    return digest[0] % max(1, modulo)


# ---------- EVENTOS: arte textual ----------

def render_event_text_art(out, item, *, font, wrap, fit_title):
    im = Image.new('RGB', (1080, 1080), (5, 69, 48))
    draw = ImageDraw.Draw(im, 'RGBA')
    left, right = 115, 965
    width = right - left

    draw.rectangle((0, 0, 1080, 128), fill=(3, 45, 34, 255))
    draw.text((left, 36), 'RADAR BRASIL 2027', font=font(36, True), fill='white')
    _pill(draw, (left, 166, left + 210, 228), 'EVENTO', font(25, True), (255, 220, 0, 255), (14, 48, 36, 255))

    draw.line((760, 180, 1010, 430), fill=(255, 255, 255, 30), width=8)
    draw.line((840, 180, 1010, 350), fill=(255, 220, 0, 80), width=8)
    draw.ellipse((825, 250, 1045, 470), outline=(255, 255, 255, 40), width=6)

    f, lines, readable = _fit(draw, item.get('title'), width, fit_title, start=82, max_lines=4)
    y = 286
    for line in lines[:4]:
        draw.text((left, y), line, font=f, fill='white')
        y += f.size + 10

    info_y = max(650, y + 32)
    date_text = clean(item.get('display_date') or item.get('subtitle'))
    place_text = clean(item.get('display_place'))
    for label, value, yy in (
        ('QUANDO', date_text or 'Data a confirmar', info_y),
        ('ONDE', place_text or 'Local a definir', info_y + 150),
    ):
        draw.rounded_rectangle((left, yy, right, yy + 128), radius=24, fill=(255, 255, 255, 22), outline=(255, 255, 255, 45), width=2)
        draw.text((left + 28, yy + 20), label, font=font(20, True), fill=(255, 220, 0))
        vf = font(27 if label == 'ONDE' else 28, True)
        vals = wrap(draw, value, vf, width - 56)
        draw.text((left + 28, yy + 54), vals[0] if vals else value, font=vf, fill='white')

    draw.rectangle((left, 986, right, 991), fill=(255, 220, 0, 255))
    draw.text((left, 1010), 'Saiba mais pelo link da bio', font=font(20, True), fill='white')
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.save(out, 'JPEG', quality=94, optimize=True)
    return readable and f.size >= 58 and len(lines) <= 4, f.size, len(lines), {
        'visual_mode': 'radar_event_text_art',
        'semantic_reason': 'owned_text_art_policy',
        'image_credit': 'Arte própria do Radar Brasil 2027',
        'license_note': 'arte_propria',
    }


# ---------- NOTÍCIAS: arte gráfica ilustrada ----------

def _news_headline(title):
    t = clean(title)
    t = re.sub(
        r'\s+-\s+(?:www\.)?[a-z0-9.-]+\.(?:com|com\.br|org|org\.br|net|net\.br|br)$',
        '', t, flags=re.I,
    )
    t = re.sub(r'^Fifa\b', 'FIFA', t)
    replacements = (
        (r'\bCopa do Mundo Feminina da FIFA Brasil 2027\b', 'Copa Feminina 2027'),
        (r'\bCopa do Mundo Feminina FIFA 2027\b', 'Copa Feminina 2027'),
        (r'\bCopa do Mundo Feminina de 2027\b', 'Copa Feminina 2027'),
        (r'\bCopa do Mundo Feminina 2027\b', 'Copa Feminina 2027'),
        (r'\bCopa do Mundo Feminina no Brasil(?: em 2027)?\b', 'Copa Feminina 2027'),
        (r'\bpor exigência da FIFA para a Copa Feminina 2027\b', 'para a Copa Feminina 2027'),
        (r'\bpor exigência da Fifa para a Copa Feminina 2027\b', 'para a Copa Feminina 2027'),
    )
    for pattern, repl in replacements:
        t = clean(re.sub(pattern, repl, t, flags=re.I))
    return t


def _fit_news_headline(draw, title, width, font_fn, wrap_fn):
    original = clean(title)
    headline = _news_headline(original)
    candidates = [headline]

    # Remove somente caudas explicativas completas; nunca usa reticências.
    for pattern in (
        r'\s+com foco\s+.*$',
        r'\s+durante\s+.*$',
        r'\s+ap[oó]s\s+.*$',
        r'\s+enquanto\s+.*$',
        r'\s+para ações\s+.*$',
    ):
        reduced = clean(re.sub(pattern, '', headline, flags=re.I))
        if len(reduced) >= 28 and reduced not in candidates:
            candidates.append(reduced)

    if ':' in headline:
        left = clean(headline.split(':', 1)[0])
        if 28 <= len(left) <= 90 and left not in candidates:
            candidates.append(left)

    for candidate in candidates:
        for size in range(78, 57, -2):
            f = font_fn(size, True)
            lines = wrap_fn(draw, candidate, f, width)
            if len(lines) <= 4:
                return f, lines, True, candidate

    f = font_fn(58, True)
    lines = wrap_fn(draw, headline, f, width)
    return f, lines, len(lines) <= 4, headline


def _draw_stadium_lights(draw, x, y, scale=1.0, color=(255, 255, 255, 110)):
    pole = int(150 * scale)
    draw.line((x, y, x, y + pole), fill=color, width=max(3, int(6 * scale)))
    for dx in (-32, -10, 12, 34):
        draw.ellipse((x + dx * scale - 6 * scale, y - 8 * scale, x + dx * scale + 6 * scale, y + 4 * scale), fill=color)


def _draw_footballer(draw, x, y, scale=1.0):
    skin = (116, 74, 48, 255)
    hair = (20, 25, 28, 255)
    jersey = (244, 196, 40, 255)
    shorts = (18, 74, 128, 255)
    outline = (8, 34, 48, 255)
    hr = int(44 * scale)
    draw.ellipse((x - hr, y - hr, x + hr, y + hr), fill=skin, outline=outline, width=max(3, int(5 * scale)))
    draw.ellipse((x - hr - 8 * scale, y - hr - 10 * scale, x + hr + 5 * scale, y + hr * .3), fill=hair)
    draw.polygon([(x + hr * .4, y - hr * .3), (x + 100 * scale, y - 28 * scale), (x + 150 * scale, y + 25 * scale), (x + 92 * scale, y + 22 * scale)], fill=hair)
    draw.polygon([(x - 70 * scale, y + 52 * scale), (x + 70 * scale, y + 52 * scale), (x + 88 * scale, y + 240 * scale), (x - 88 * scale, y + 240 * scale)], fill=jersey, outline=outline)
    draw.polygon([(x - 88 * scale, y + 110 * scale), (x - 138 * scale, y + 248 * scale), (x - 108 * scale, y + 267 * scale), (x - 42 * scale, y + 135 * scale)], fill=skin)
    draw.polygon([(x + 88 * scale, y + 110 * scale), (x + 150 * scale, y + 240 * scale), (x + 123 * scale, y + 260 * scale), (x + 42 * scale, y + 136 * scale)], fill=skin)
    draw.rectangle((x - 82 * scale, y + 240 * scale, x + 82 * scale, y + 322 * scale), fill=shorts)
    draw.polygon([(x - 62 * scale, y + 322 * scale), (x - 18 * scale, y + 322 * scale), (x - 34 * scale, y + 500 * scale), (x - 74 * scale, y + 500 * scale)], fill=skin)
    draw.polygon([(x + 18 * scale, y + 322 * scale), (x + 62 * scale, y + 322 * scale), (x + 76 * scale, y + 500 * scale), (x + 36 * scale, y + 500 * scale)], fill=skin)
    try:
        ff = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DeJaVuSans-Bold.ttf', int(66 * scale))
        draw.text((x - 22 * scale, y + 122 * scale), '7', font=ff, fill=(12, 70, 75, 220))
    except Exception:
        pass


def _draw_trophy(draw, cx, cy, scale=1.0):
    gold, dark = (242, 185, 46, 255), (83, 59, 20, 255)
    w, h = 150 * scale, 190 * scale
    draw.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 3), radius=int(25 * scale), fill=gold, outline=dark, width=max(4, int(6 * scale)))
    draw.arc((cx - w, cy - h / 2, cx - w / 4, cy + h / 4), 70, 285, fill=gold, width=max(12, int(24 * scale)))
    draw.arc((cx + w / 4, cy - h / 2, cx + w, cy + h / 4), 255, 110, fill=gold, width=max(12, int(24 * scale)))
    draw.rectangle((cx - 24 * scale, cy + h / 3, cx + 24 * scale, cy + h * .67), fill=gold)
    draw.rounded_rectangle((cx - 90 * scale, cy + h * .62, cx + 90 * scale, cy + h * .82), radius=int(12 * scale), fill=dark)


def _draw_city_skyline(draw, base_x, base_y, scale=1.0):
    buildings = [