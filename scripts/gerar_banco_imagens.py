#!/usr/bin/env python3
"""Gera catálogo de 500 imagens abertas para o Radar Brasil 2027.

Fonte primária: Wikimedia Commons via MediaWiki API.
Aceita apenas licenças abertas compatíveis com republicação (CC0, PD, CC BY, CC BY-SA).
Não baixa os binários: armazena URL direta + thumbnail + metadados de licença/autoria.
"""

from __future__ import annotations

import csv
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "banco_imagens" / "catalogo.csv"
OUT_JSON = ROOT / "banco_imagens" / "catalogo.json"
TARGET = 500
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "RadarBrasil2027/1.0 (catalogo editorial de imagens abertas)"

# Consultas editoriais. As primeiras têm maior prioridade.
SEARCHES = [
    ("selecao_brasileira", 'Brazil women national football team'),
    ("selecao_brasileira", 'Brazil women football Marta'),
    ("selecao_brasileira", 'Brazil women football Debinha'),
    ("selecao_brasileira", 'Brazil women football Formiga'),
    ("selecao_brasileira", 'Brazil women football Cristiane'),
    ("selecao_brasileira", 'Brazil women football Kerolin'),
    ("futebol_feminino", 'women association football Brazil'),
    ("futebol_feminino", 'women football Brazil players'),
    ("copa_feminina_2023", '2023 FIFA Women World Cup football'),
    ("copa_feminina_2019", '2019 FIFA Women World Cup football'),
    ("copa_feminina_2015", '2015 FIFA Women World Cup football'),
    ("copa_feminina_2011", '2011 FIFA Women World Cup football'),
    ("copa_feminina_2007", '2007 FIFA Women World Cup football'),
    ("torcida", 'women football supporters stadium'),
    ("torcida", 'women soccer fans stadium'),
    ("estadio", 'Maracana stadium Rio de Janeiro'),
    ("estadio", 'Mineirao stadium Belo Horizonte'),
    ("estadio", 'Arena Fonte Nova Salvador'),
    ("estadio", 'Estadio Nacional Brasilia Mane Garrincha'),
    ("estadio", 'Arena Corinthians Sao Paulo stadium'),
    ("estadio", 'Neo Quimica Arena stadium'),
    ("estadio", 'Castelao stadium Fortaleza Brazil'),
    ("estadio", 'Beira-Rio stadium Porto Alegre'),
    ("estadio", 'Arena Pernambuco stadium'),
    ("estadio", 'Arena Amazonia stadium Manaus'),
    ("estadio", 'Arena das Dunas stadium Natal'),
    ("estadio", 'Arena da Baixada Curitiba stadium'),
    ("cidade_sede", 'Rio de Janeiro Brazil city landmark'),
    ("cidade_sede", 'Sao Paulo Brazil city landmark'),
    ("cidade_sede", 'Brasilia Brazil landmark'),
    ("cidade_sede", 'Belo Horizonte Brazil landmark'),
    ("cidade_sede", 'Salvador Bahia Brazil landmark'),
    ("cidade_sede", 'Porto Alegre Brazil landmark'),
    ("cidade_sede", 'Recife Pernambuco Brazil landmark'),
    ("cidade_sede", 'Fortaleza Ceara Brazil landmark'),
    ("cidade_sede", 'Manaus Amazonas Brazil landmark'),
    ("cidade_sede", 'Natal Rio Grande do Norte Brazil landmark'),
    ("cidade_sede", 'Curitiba Parana Brazil landmark'),
]

# Aceitos para Instagram inclusive quando houver uso institucional/comercial futuro.
OPEN_LICENSE_RE = re.compile(
    r"(?:CC0|public domain|PD-|CC[- ]?BY(?:[- ]?SA)?(?:[- ]?\d(?:\.\d)?)?)",
    re.I,
)
BLOCK_LICENSE_RE = re.compile(r"(?:NC|ND|non.?commercial|no.?derivatives|fair use)", re.I)

# Rejeita temas que frequentemente causaram ruído editorial no Radar.
BLOCK_TITLE_RE = re.compile(
    r"(?:men['’]?s|masculin|president|governor|prefeit|minister|politic|election|partid|logo|flag of|coat of arms)",
    re.I,
)

ALLOWED_MIME = {"image/jpeg", "image/png"}

FIELDS = [
    "id", "categoria", "titulo", "pessoa_local", "fonte", "pagina_origem",
    "url_direta", "url_thumbnail", "autor", "licenca", "url_licenca",
    "atribuicao", "status_licenca", "instagram_ok", "largura", "altura",
    "arquivo_local", "ultima_utilizacao", "qtd_utilizacoes", "observacoes",
]


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def meta_value(meta: dict, key: str) -> str:
    item = meta.get(key) or {}
    return clean_html(item.get("value") if isinstance(item, dict) else "")


def api(params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    req = Request(f"{API}?{urlencode(params)}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_files(query: str, limit_pages: int = 3):
    """Até 150 candidatos por consulta, paginando 50 por vez."""
    offset = 0
    for _ in range(limit_pages):
        data = api({
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 50,
            "gsroffset": offset,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1600,
        })
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return
        for page in pages:
            yield page
        cont = data.get("continue", {}).get("gsroffset")
        if cont is None:
            return
        offset = int(cont)
        time.sleep(0.12)


def row_from_page(page: dict, category: str) -> dict | None:
    title = page.get("title", "")
    if not title.startswith("File:") or BLOCK_TITLE_RE.search(title):
        return None
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    ii = infos[0]
    if ii.get("mime") not in ALLOWED_MIME:
        return None
    width, height = int(ii.get("width") or 0), int(ii.get("height") or 0)
    if width < 700 or height < 500:
        return None

    meta = ii.get("extmetadata") or {}
    license_short = meta_value(meta, "LicenseShortName")
    license_url = meta_value(meta, "LicenseUrl")
    usage_terms = meta_value(meta, "UsageTerms")
    license_text = " ".join(x for x in (license_short, usage_terms, license_url) if x)
    if not license_text or BLOCK_LICENSE_RE.search(license_text) or not OPEN_LICENSE_RE.search(license_text):
        return None

    artist = meta_value(meta, "Artist") or meta_value(meta, "Credit") or "Autor indicado na página do arquivo"
    credit = meta_value(meta, "Credit")
    desc = meta_value(meta, "ImageDescription")
    commons_page = ii.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}"
    direct = ii.get("url", "")
    thumb = ii.get("thumburl") or direct
    if not direct:
        return None

    display_title = title[5:].rsplit(".", 1)[0].replace("_", " ")
    attribution_parts = [artist]
    if credit and credit.lower() not in artist.lower():
        attribution_parts.append(credit)
    attribution_parts.append(license_short or usage_terms)

    return {
        "categoria": category,
        "titulo": display_title,
        "pessoa_local": desc[:300],
        "fonte": "Wikimedia Commons",
        "pagina_origem": commons_page,
        "url_direta": direct,
        "url_thumbnail": thumb,
        "autor": artist[:500],
        "licenca": license_short or usage_terms,
        "url_licenca": license_url,
        "atribuicao": " | ".join(x for x in attribution_parts if x)[:900],
        "status_licenca": "APROVADA_AUTO",
        "instagram_ok": "SIM",
        "largura": width,
        "altura": height,
        "arquivo_local": "",
        "ultima_utilizacao": "",
        "qtd_utilizacoes": "0",
        "observacoes": "Licença aberta conferida automaticamente via extmetadata do Wikimedia Commons; revalidar se a página de origem mudar.",
    }


def load_existing() -> list[dict]:
    if not OUT_CSV.exists():
        return []
    with OUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    normalized = []
    for r in rows:
        item = {k: r.get(k, "") for k in FIELDS}
        normalized.append(item)
    return normalized


def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = load_existing()
    seen_pages = {r.get("pagina_origem", "").strip() for r in rows if r.get("pagina_origem")}
    seen_urls = {r.get("url_direta", "").strip() for r in rows if r.get("url_direta")}

    print(f"Catálogo existente: {len(rows)}")
    for category, query in SEARCHES:
        if len(rows) >= TARGET:
            break
        print(f"Buscando: {category} :: {query}")
        try:
            for page in search_files(query):
                if len(rows) >= TARGET:
                    break
                row = row_from_page(page, category)
                if not row:
                    continue
                if row["pagina_origem"] in seen_pages or row["url_direta"] in seen_urls:
                    continue
                rows.append(row)
                seen_pages.add(row["pagina_origem"])
                seen_urls.add(row["url_direta"])
        except Exception as exc:
            print(f"AVISO: falha em {query}: {exc}")
        time.sleep(0.2)

    # IDs estáveis por posição; preserva IDs manuais já existentes quando presentes.
    for idx, row in enumerate(rows[:TARGET], start=1):
        if not row.get("id"):
            row["id"] = f"IMG{idx:04d}"

    rows = rows[:TARGET]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({k: r.get(k, "") for k in FIELDS} for r in rows)

    with OUT_JSON.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"TOTAL={len(rows)}")
    if len(rows) < TARGET:
        raise SystemExit(f"Banco incompleto: {len(rows)}/{TARGET}. Amplie SEARCHES e execute novamente.")


if __name__ == "__main__":
    main()
