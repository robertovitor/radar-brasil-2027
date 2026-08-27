#!/usr/bin/env python3
"""Seleciona o item mais relevante e ainda não publicado do Radar Brasil 2027."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re

from PIL import Image, ImageDraw, ImageFont


DIRECT_TERMS = (
    "copa do mundo feminina 2027",
    "copa feminina 2027",
    "mundial feminino 2027",
    "fifa 2027",
)
RELEVANT_TERMS = (
    "cidade-sede", "cidades-sede", "seleção brasileira", "selecao brasileira",
    "futebol feminino", "fifa", "tour da taça", "tour da taca", "voluntár",
    "legado", "ativação", "ativacao", "sorteio", "estádio", "estadio",
)


def load(path: pathlib.Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_date(value: object) -> dt.date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError:
        return None


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def wrapped(draw: ImageDraw.ImageDraw, text: str, chosen_font, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=chosen_font)[2] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def create_art(path: pathlib.Path, item: dict) -> None:
    """Cria card quadrado exclusivo e legível para o feed."""
    digest = hashlib.sha256(item["key"].encode()).digest()
    palettes = [
        ((4, 74, 48), (17, 142, 91), (255, 210, 0)),
        ((8, 45, 92), (22, 105, 180), (255, 201, 40)),
        ((74, 27, 109), (151, 53, 176), (71, 220, 170)),
        ((121, 38, 24), (218, 91, 45), (255, 211, 77)),
    ]
    start, end, accent = palettes[digest[0] % len(palettes)]
    image = Image.new("RGB", (1080, 1080))
    pixels = image.load()
    for y in range(1080):
        ratio = y / 1079
        color = tuple(int(a + (b - a) * ratio) for a, b in zip(start, end))
        for x in range(1080):
            pixels[x, y] = color
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(7):
        radius = 90 + digest[i + 1]
        x = (digest[i + 8] * 7 + i * 137) % 1180 - 100
        y = (digest[i + 15] * 5 + i * 181) % 1180 - 100
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*accent, 24))

    draw.rounded_rectangle((58, 56, 1022, 1024), radius=38, fill=(0, 0, 0, 72), outline=(255, 255, 255, 45), width=2)
    draw.text((94, 92), "RADAR BRASIL 2027", font=font(48, True), fill=(255, 255, 255, 255))
    label = "NOTÍCIA" if item["source_type"] == "noticia" else "AGENDA"
    label_width = draw.textbbox((0, 0), label, font=font(29, True))[2]
    draw.rounded_rectangle((94, 180, 134 + label_width, 232), radius=22, fill=(*accent, 255))
    draw.text((114, 188), label, font=font(29, True), fill=(18, 35, 30, 255))

    title_font = font(62, True)
    lines = wrapped(draw, item["title"], title_font, 850)
    while len(lines) > 6 and title_font.size > 44:
        title_font = font(title_font.size - 4, True)
        lines = wrapped(draw, item["title"], title_font, 850)
    y = 292
    for line in lines[:6]:
        draw.text((94, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += title_font.size + 15

    draw.line((94, 863, 986, 863), fill=(*accent, 255), width=5)
    detail_lines = wrapped(draw, item["art_detail"], font(31), 850)
    y = 895
    for line in detail_lines[:2]:
        draw.text((94, y), line, font=font(31), fill=(255, 255, 255, 235))
        y += 43
    draw.text((94, 980), "@RadarBrasil2027", font=font(25, True), fill=(*accent, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)


def relevance(text: str) -> int:
    lowered = text.casefold()
    score = sum(12 for term in DIRECT_TERMS if term in lowered)
    score += sum(2 for term in RELEVANT_TERMS if term in lowered)
    return score


def news_candidates(items: list[dict], today: dt.date, published: set[str]):
    for item in items:
        title = clean(item.get("Titulo"))
        summary = clean(item.get("Resumo"))
        key = "instagram:noticia:" + clean(item.get("Link") or title).casefold()
        date = parse_date(item.get("Data"))
        if not title or key in published or not date or (today - date).days > 14:
            continue
        impact = clean(item.get("Impacto")).casefold()
        impact_score = {"alto": 10, "médio": 5, "medio": 5}.get(impact, 0)
        score = relevance(" ".join((title, summary, clean(item.get("Tema"))))) + impact_score
        if score < 8:
            continue
        yield {
            "score": score + max(0, 7 - (today - date).days),
            "date": date,
            "key": key,
            "caption": (
                f"📰 {title}\n\n{summary}\n\n"
                f"Fonte: {clean(item.get('Veiculo'))}\n"
                f"Saiba mais: {clean(item.get('Link'))}\n\n"
                "#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino"
            ),
            "source_type": "noticia",
            "title": title,
            "art_detail": f"{clean(item.get('CidadeUF'))} • Fonte: {clean(item.get('Veiculo'))}",
        }


def event_candidates(items: list[dict], today: dt.date, published: set[str]):
    for item in items:
        title = clean(item.get("Titulo"))
        event_id = clean(item.get("ID") or title)
        key = "instagram:evento:" + event_id.casefold()
        date = parse_date(item.get("Data"))
        status = clean(item.get("Status")).casefold()
        if not title or key in published or not date or date < today or "realizado" in status:
            continue
        days = (date - today).days
        if days > 120:
            continue
        text = " ".join((title, clean(item.get("Observacoes")), clean(item.get("Categoria"))))
        score = relevance(text)
        if score < 4:
            continue
        place = ", ".join(filter(None, (clean(item.get("Local")), clean(item.get("Cidade")), clean(item.get("UF")))))
        yield {
            "score": score + max(0, 12 - days // 7),
            "date": date,
            "key": key,
            "caption": (
                f"📅 {title}\n\n"
                f"Quando: {clean(item.get('DataBR')) or date.strftime('%d/%m/%Y')}\n"
                f"Onde: {place or 'Local a definir'}\n\n"
                f"{clean(item.get('Observacoes'))}\n\n"
                f"Mais informações: {clean(item.get('Link'))}\n\n"
                "#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino"
            ),
            "source_type": "evento",
            "title": title,
            "art_detail": f"{clean(item.get('DataBR')) or date.strftime('%d/%m/%Y')} • {clean(item.get('Cidade'))}/{clean(item.get('UF'))}",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=pathlib.Path, default="dados.json")
    parser.add_argument("--news", type=pathlib.Path, default="noticias.json")
    parser.add_argument("--ledger", type=pathlib.Path, default="instagram/publicados.json")
    parser.add_argument("--output-dir", type=pathlib.Path, default="instagram/fila/automatica")
    parser.add_argument("--art-dir", type=pathlib.Path, default="instagram/artes")
    parser.add_argument("--github-output", type=pathlib.Path)
    args = parser.parse_args()

    today = dt.datetime.now(dt.timezone.utc).date()
    ledger = load(args.ledger, {"published": []})
    published = {clean(item.get("key")) for item in ledger.get("published", [])}
    candidates = list(news_candidates(load(args.news, []), today, published))
    candidates += list(event_candidates(load(args.events, []), today, published))
    candidates.sort(key=lambda item: (item["score"], item["date"]), reverse=True)

    found = bool(candidates)
    post_path = ""
    if found:
        selected = candidates[0]
        slug = re.sub(r"[^a-z0-9]+", "-", selected["key"].casefold()).strip("-")[-100:]
        args.output_dir.mkdir(parents=True, exist_ok=True)
        path = args.output_dir / f"{today.isoformat()}-{slug}.json"
        art_path = args.art_dir / f"{today.isoformat()}-{slug}.png"
        create_art(art_path, selected)
        post = {
            "id": slug,
            "idempotency_key": selected["key"],
            "approved": True,
            "source_type": selected["source_type"],
            "image_url": f"https://raw.githubusercontent.com/robertovitor/radar-brasil-2027/main/{art_path.as_posix()}",
            "caption": selected["caption"][:2200],
        }
        path.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        post_path = str(path)
        print(f"Selecionado: {selected['key']} (pontuação {selected['score']})")
    else:
        print("Nenhuma notícia ou evento relevante e inédito disponível.")

    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"found={'true' if found else 'false'}\n")
            output.write(f"post_file={post_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
