#!/usr/bin/env python3
"""Seleciona o item mais relevante e ainda não publicado do Radar Brasil 2027."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re


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
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=pathlib.Path, default="dados.json")
    parser.add_argument("--news", type=pathlib.Path, default="noticias.json")
    parser.add_argument("--ledger", type=pathlib.Path, default="instagram/publicados.json")
    parser.add_argument("--output-dir", type=pathlib.Path, default="instagram/fila/automatica")
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
        post = {
            "id": slug,
            "idempotency_key": selected["key"],
            "approved": True,
            "source_type": selected["source_type"],
            "image_url": "https://robertovitor.github.io/radar-brasil-2027/mapa-brasil.png",
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
