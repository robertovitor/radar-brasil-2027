#!/usr/bin/env python3
"""Gera no máximo uma publicação inédita elegível do Radar Brasil 2027."""

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
    for item in items:
        title = clean(item.get("Titulo"))
        summary = clean(item.get("Resumo"))
        key = "instagram:noticia:" + clean(item.get("Link") or title).casefold()
        date = parse_date(item.get("Data"))
        if not title or key in published or not date or date > today or is_base_selection(item):
            continue
        yield {
            "date": date,
            "key": key,
            "caption": (
                f"📰 {title}\n\n{summary}\n\n"
                f"Fonte: {clean(item.get('Veiculo'))}\n\n"
                "#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino\n\n"
                "Saiba mais pelo link da Bio"
            ),
            "source_type": "noticia",
            "priority": {"alto": 3, "medio": 2, "baixo": 1}.get(normalized(item.get("Impacto")), 1),
            "title": title,
            "art_detail": f"{clean(item.get('CidadeUF'))} • Fonte: {clean(item.get('Veiculo'))}",
        }


def event_candidates(items: list[dict], today: dt.date, published: set[str]):
    for item in items:
        title = clean(item.get("Titulo"))
        event_id = clean(item.get("ID") or title)
        key = "instagram:evento:" + event_id.casefold()
        date = parse_date(item.get("Data"))
        if not title or key in published or not date or is_base_selection(item):
            continue
        place = ", ".join(filter(None, (clean(item.get("Local")), clean(item.get("Cidade")), clean(item.get("UF")))))
        yield {
            "date": date,
            "key": key,
            "caption": (
                f"📅 {title}\n\n"
                f"Quando: {clean(item.get('DataBR')) or date.strftime('%d/%m/%Y')}\n"
                f"Onde: {place or 'Local a definir'}\n\n"
                f"{clean(item.get('Observacoes'))}\n\n"
                f"Fonte: {clean(item.get('Organizador')) or 'Radar Brasil 2027'}\n\n"
                "#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino\n\n"
                "Saiba mais pelo link da Bio"
            ),
            "source_type": "evento",
            "priority": 2,
            "title": title,
            "art_detail": (
                f"{clean(item.get('DataBR')) or date.strftime('%d/%m/%Y')} • "
                f"{clean(item.get('Cidade'))}/{clean(item.get('UF'))}"
            ),
        }


def all_content_keys(events: list[dict], news: list[dict]) -> set[str]:
    keys: set[str] = set()
    for item in events:
        title = clean(item.get("Titulo"))
        if title and not is_base_selection(item):
            keys.add("instagram:evento:" + clean(item.get("ID") or title).casefold())
    for item in news:
        title = clean(item.get("Titulo"))
        if title and not is_base_selection(item):
            keys.add("instagram:noticia:" + clean(item.get("Link") or title).casefold())
    return keys


def update_discovery_state(path: pathlib.Path, current_keys: set[str], published: set[str]) -> set[str]:
    """Mantém fila de itens recém-divulgados no site até eles serem publicados."""
    if not path.exists():
        state = {"known": sorted(current_keys), "pending_new": []}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return set()

    state = load(path, {"known": [], "pending_new": []})
    known = set(state.get("known", []))
    pending = set(state.get("pending_new", []))
    pending |= current_keys - known
    pending -= published
    known |= current_keys
    state = {"known": sorted(known), "pending_new": sorted(pending)}
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pending


def slug_for(key: str) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", normalized(key)).strip("-")[-88:]
    digest = hashlib.sha256(key.encode()).hexdigest()[:10]
    return f"{readable}-{digest}" if readable else digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=pathlib.Path, default="dados.json")
    parser.add_argument("--news", type=pathlib.Path, default="noticias.json")
    parser.add_argument("--ledger", type=pathlib.Path, default="instagram/publicados.json")
    parser.add_argument("--discovery-state", type=pathlib.Path, default="instagram/conteudo-conhecido.json")
    parser.add_argument("--output-dir", type=pathlib.Path, default="instagram/fila/automatica")
    parser.add_argument("--art-dir", type=pathlib.Path, default="instagram/artes")
    parser.add_argument("--github-output", type=pathlib.Path)
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    events = load(args.events, [])
    news = load(args.news, [])
    ledger = load(args.ledger, {"published": []})
    published_items = ledger.get("published", [])
    published = {clean(item.get("key")) for item in published_items}

    current_keys = all_content_keys(events, news)
    pending_new = update_discovery_state(args.discovery_state, current_keys, published)

    timestamps = []
    for item in published_items:
        raw = clean(item.get("published_at"))
        if raw:
            try:
                timestamps.append(dt.datetime.fromisoformat(raw.replace("Z", "+00:00")))
            except ValueError:
                pass
    if timestamps and (now - max(timestamps)).total_seconds() < 3600:
        print("Intervalo mínimo de 60 minutos ainda não concluído.")
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                output.write("found=false\n")
                output.write("batch_file=\n")
                output.write("count=0\n")
        return 0

    candidates = list(event_candidates(events, today, published)) + list(news_candidates(news, today, published))

    # Prioridade editorial solicitada:
    # 1. novos eventos divulgados no site;
    # 2. novas notícias divulgadas no site;
    # 3. eventos ainda não publicados, dos mais recentes para os mais antigos;
    # 4. notícias ainda não publicadas, das mais recentes para as mais antigas.
    def rank(item: dict):
        is_new = item["key"] in pending_new
        if is_new and item["source_type"] == "evento":
            tier = 1
        elif is_new and item["source_type"] == "noticia":
            tier = 2
        elif item["source_type"] == "evento":
            tier = 3
        else:
            tier = 4
        return (tier, -item["date"].toordinal(), -item["priority"], item["key"])

    candidates.sort(key=rank)

    # Um item só está pronto para publicação quando o JSON e sua arte referenciada
    # já existiam no repositório antes deste ciclo. A preparação e a publicação
    # ficam, portanto, separadas em execuções distintas.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ready_by_key: dict[str, pathlib.Path] = {}
    for queued_path in sorted(args.output_dir.glob("*.json")):
        if queued_path.name == "lote-atual.json":
            continue
        queued = load(queued_path, {})
        queued_key = clean(queued.get("idempotency_key"))
        image_url = clean(queued.get("image_url"))
        marker = "/main/"
        art_path = pathlib.Path(image_url.split(marker, 1)[1]) if marker in image_url else None
        if queued_key and art_path and art_path.exists():
            ready_by_key[queued_key] = queued_path

    post_paths: list[str] = []
    prepared_only = False
    selected = next((item for item in candidates if item["key"] in ready_by_key), None)

    if selected:
        queued_path = ready_by_key[selected["key"]]
        post_paths.append(queued_path.as_posix())
        print(
            f"Prioridade selecionada: {rank(selected)[0]} | "
            f"{selected['source_type']} | {selected['title']}"
        )
        print("Arte e JSON já estavam salvos; item liberado para publicação.")
    elif candidates:
        selected = candidates[0]
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
        prepared_only = True
        print(
            f"Prioridade preparada: {rank(selected)[0]} | "
            f"{selected['source_type']} | {selected['title']}"
        )
        print("JSON e arte salvos; publicação ficará para um ciclo posterior.")

    batch_path = args.output_dir / "lote-atual.json"
    if post_paths:
        batch = {"generated_at": now.isoformat(), "count": len(post_paths), "posts": post_paths}
        batch_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Publicação preparada: {len(post_paths)} item.")
    elif prepared_only:
        print("Item preparado, mas ainda não liberado para publicação neste ciclo.")
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
