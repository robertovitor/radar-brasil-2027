#!/usr/bin/env python3
"""Gera um lote com todo conteúdo inédito elegível do Radar Brasil 2027."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import unicodedata

from PIL import Image, ImageDraw, ImageFont


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


def normalized(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean(value).casefold())
    return "".join(char for char in text if not unicodedata.combining(char))


def is_base_selection(item: dict) -> bool:
    """Exclui seleções de base sem bloquear conteúdo adulto que cite 'seleção'."""
    text = normalized(" ".join(clean(value) for value in item.values()))
    direct_markers = (
        "selecoes de base",
        "selecao de base",
        "selecao brasileira feminina de base",
    )
    if any(marker in text for marker in direct_markers):
        return True
    youth_category = re.search(r"\bsub[ -]?(15|16|17|18|19|20|23)\b", text)
    selection_context = any(
        marker in text
        for marker in (
            "selecao brasileira",
            "selecao feminina",
            "mundial feminino",
            "copa do mundo feminina sub",
        )
    )
    return bool(youth_category and selection_context)


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
    """Cria um card próprio para cada notícia ou evento."""
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

    draw.rounded_rectangle(
        (58, 56, 1022, 1024), radius=38, fill=(0, 0, 0, 72),
        outline=(255, 255, 255, 45), width=2,
    )
    draw.text((94, 92), "RADAR BRASIL 2027", font=font(48, True), fill=(255, 255, 255, 255))
    label = "NOTÍCIA" if item["source_type"] == "noticia" else "AGENDA"
    label_font = font(29, True)
    label_width = draw.textbbox((0, 0), label, font=label_font)[2]
    draw.rounded_rectangle((94, 180, 134 + label_width, 232), radius=22, fill=(*accent, 255))
    draw.text((114, 188), label, font=label_font, fill=(18, 35, 30, 255))

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
    detail_font = font(31)
    detail_lines = wrapped(draw, item["art_detail"], detail_font, 850)
    y = 895
    for line in detail_lines[:2]:
        draw.text((94, y), line, font=detail_font, fill=(255, 255, 255, 235))
        y += 43
    draw.text((94, 980), "@RadarBrasil2027", font=font(25, True), fill=(*accent, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)


def news_candidates(items: list[dict], today: dt.date, published: set[str]):
    """Publica todas as notícias recentes ainda inéditas, exceto seleções de base."""
    for item in items:
        title = clean(item.get("Titulo"))
        summary = clean(item.get("Resumo"))
        key = "instagram:noticia:" + clean(item.get("Link") or title).casefold()
        date = parse_date(item.get("Data"))
        if (
            not title
            or key in published
            or not date
            or (today - date).days > 14
            or date > today
            or is_base_selection(item)
        ):
            continue
        yield {
            "date": date,
            "key": key,
            "caption": (
                f"📰 {title}\n\n{summary}\n\n"
                f"Fonte: {clean(item.get('Veiculo'))}\n"
                "Saiba mais pelo link da Bio\n\n"
                "#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino"
            ),
            "source_type": "noticia",
            "title": title,
            "art_detail": f"{clean(item.get('CidadeUF'))} • Fonte: {clean(item.get('Veiculo'))}",
        }


def event_candidates(items: list[dict], today: dt.date, published: set[str]):
    """Publica todos os eventos futuros ainda inéditos, exceto seleções de base."""
    for item in items:
        title = clean(item.get("Titulo"))
        event_id = clean(item.get("ID") or title)
        key = "instagram:evento:" + event_id.casefold()
        date = parse_date(item.get("Data"))
        status = clean(item.get("Status")).casefold()
        if (
            not title
            or key in published
            or not date
            or date < today
            or "realizado" in status
            or is_base_selection(item)
        ):
            continue
        place = ", ".join(
            filter(None, (clean(item.get("Local")), clean(item.get("Cidade")), clean(item.get("UF"))))
        )
        yield {
            "date": date,
            "key": key,
            "caption": (
                f"📅 {title}\n\n"
                f"Quando: {clean(item.get('DataBR')) or date.strftime('%d/%m/%Y')}\n"
                f"Onde: {place or 'Local a definir'}\n\n"
                f"{clean(item.get('Observacoes'))}\n\n"
                "Saiba mais pelo link da Bio\n\n"
                "#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino"
            ),
            "source_type": "evento",
            "title": title,
            "art_detail": (
                f"{clean(item.get('DataBR')) or date.strftime('%d/%m/%Y')} • "
                f"{clean(item.get('Cidade'))}/{clean(item.get('UF'))}"
            ),
        }


def slug_for(key: str) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", normalized(key)).strip("-")[-88:]
    digest = hashlib.sha256(key.encode()).hexdigest()[:10]
    return f"{readable}-{digest}" if readable else digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=pathlib.Path, default="dados.json")
    parser.add_argument("--news", type=pathlib.Path, default="noticias.json")
    parser.add_argument("--ledger", type=pathlib.Path, default="instagram/publicados.json")
    parser.add_argument("--output-dir", type=pathlib.Path, default="instagram/fila/automatica")
    parser.add_argument("--art-dir", type=pathlib.Path, default="instagram/artes")
    parser.add_argument("--github-output", type=pathlib.Path)
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    ledger = load(args.ledger, {"published": []})
    published = {clean(item.get("key")) for item in ledger.get("published", [])}
    candidates = list(news_candidates(load(args.news, []), today, published))
    candidates += list(event_candidates(load(args.events, []), today, published))
    candidates.sort(key=lambda item: (item["date"], item["source_type"], item["key"]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    post_paths: list[str] = []
    for selected in candidates:
        slug = slug_for(selected["key"])
        path = args.output_dir / f"{today.isoformat()}-{slug}.json"
        art_path = args.art_dir / f"{today.isoformat()}-{slug}.png"
        create_art(art_path, selected)
        post = {
            "id": slug,
            "idempotency_key": selected["key"],
            "approved": True,
            "source_type": selected["source_type"],
            "image_url": (
                "https://raw.githubusercontent.com/robertovitor/"
                f"radar-brasil-2027/main/{art_path.as_posix()}"
            ),
            "caption": selected["caption"][:2200],
        }
        path.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        post_paths.append(path.as_posix())

    batch_path = args.output_dir / "lote-atual.json"
    if post_paths:
        batch = {"generated_at": now.isoformat(), "count": len(post_paths), "posts": post_paths}
        batch_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Lote preparado com {len(post_paths)} publicação(ões).")
    else:
        print("Nenhuma notícia ou evento inédito elegível disponível.")

    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"found={'true' if post_paths else 'false'}\n")
            output.write(f"batch_file={batch_path.as_posix() if post_paths else ''}\n")
            output.write(f"count={len(post_paths)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
