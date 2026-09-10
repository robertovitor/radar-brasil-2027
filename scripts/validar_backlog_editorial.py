#!/usr/bin/env python3
"""Falha o merge se uma sugestao aprovada do snapshot nao estiver no Radar.

O snapshot e alimentado pela rotina editorial conectada ao Airtable. Este gate
nao chama o Airtable: ele valida, no proprio repositorio, que toda sugestao
aprovada e ainda nao marcada como publicada esteja presente no inbox ou nos
JSONs canonicos apos o merge.
"""
import json
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "editorial" / "backlog-sugestoes.json"
INBOX = ROOT / "editorial" / "inbox.json"
EVENTS = ROOT / "dados.json"
NEWS = ROOT / "noticias.json"


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value):
    text = str(value or "").strip().casefold()
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def url_norm(value):
    text = str(value or "").strip().casefold()
    text = text.replace("https://", "").replace("http://", "")
    if text.startswith("www."):
        text = text[4:]
    return text.rstrip("/")


def pick(item, *names):
    for name in names:
        if name in item and item.get(name) not in (None, ""):
            return item.get(name)
    return ""


def is_approved(item, kind):
    status = norm(pick(item, "status", "Status"))
    if status not in {"aprovado", "aprovada", "approved"}:
        return False
    if kind == "eventos":
        published = pick(
            item,
            "incluido_no_radar",
            "Incluido no Radar",
            "Incluído no Radar",
            "incluido",
        )
    else:
        published = pick(
            item,
            "publicada_no_radar",
            "Publicada no Radar",
            "publicado_no_radar",
            "publicada",
        )
    return published not in (True, 1, "true", "True", "sim", "Sim", "yes", "Yes")


def matches_event(candidate, item):
    cid = norm(pick(candidate, "id", "ID"))
    iid = norm(pick(item, "ID", "id"))
    if cid and iid and cid == iid:
        return True

    curl = url_norm(pick(candidate, "link", "Link", "url", "URL"))
    iurl = url_norm(pick(item, "Link", "link", "URL", "url"))
    if curl and iurl and curl == iurl:
        return True

    ctitle = norm(pick(candidate, "titulo", "Titulo", "Título", "title"))
    ititle = norm(pick(item, "Titulo", "Título", "titulo", "title"))
    cdate = str(pick(candidate, "data", "Data", "date"))[:10]
    idate = str(pick(item, "Data", "data", "date"))[:10]
    ccity = norm(pick(candidate, "cidade", "Cidade", "cidade_uf", "CidadeUF"))
    icity = norm(pick(item, "Cidade", "cidade", "CidadeUF", "cidade_uf"))
    return bool(ctitle and ititle and ctitle == ititle and (not cdate or not idate or cdate == idate) and (not ccity or not icity or ccity == icity))


def matches_news(candidate, item):
    curl = url_norm(pick(candidate, "link", "Link", "url", "URL"))
    iurl = url_norm(pick(item, "Link", "link", "URL", "url"))
    if curl and iurl and curl == iurl:
        return True

    ctitle = norm(pick(candidate, "titulo", "Titulo", "Título", "title"))
    ititle = norm(pick(item, "Titulo", "Título", "titulo", "title"))
    return bool(ctitle and ititle and ctitle == ititle)


def describe(item):
    return {
        "record_id": pick(item, "record_id", "recordId", "airtable_record_id", "id_record"),
        "titulo": pick(item, "titulo", "Titulo", "Título", "title"),
        "link": pick(item, "link", "Link", "url", "URL"),
    }


def main():
    snapshot = load(SNAPSHOT, {"eventos": [], "noticias": []})
    inbox = load(INBOX, {"eventos": [], "noticias": []})
    events = load(EVENTS, [])
    news = load(NEWS, [])

    unresolved = []

    approved_events = [x for x in snapshot.get("eventos", []) if is_approved(x, "eventos")]
    approved_news = [x for x in snapshot.get("noticias", []) if is_approved(x, "noticias")]

    for item in approved_events:
        if not any(matches_event(item, x) for x in events + inbox.get("eventos", [])):
            unresolved.append(("evento", describe(item)))

    for item in approved_news:
        if not any(matches_news(item, x) for x in news + inbox.get("noticias", [])):
            unresolved.append(("noticia", describe(item)))

    print(f"snapshot_generated_at_utc={snapshot.get('generated_at_utc')}")
    print(f"aprovados_eventos_pendentes={len(approved_events)}")
    print(f"aprovados_noticias_pendentes={len(approved_news)}")
    print(f"aprovados_nao_materializados={len(unresolved)}")

    if unresolved:
        print("ERRO: ha sugestoes aprovadas do backlog que nao foram materializadas no inbox nem nos JSONs finais:")
        for kind, item in unresolved:
            print(f"- {kind}: record_id={item['record_id']} titulo={item['titulo']} link={item['link']}")
        return 2

    print("BACKLOG_EDITORIAL_OK=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
