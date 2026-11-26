#!/usr/bin/env python3
"""Expansao incremental e balanceada do banco de imagens do Radar Brasil 2027."""
from __future__ import annotations
import csv, json, re, time, unicodedata
from collections import Counter
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import gerar_banco_imagens_v3 as base

NEW_CATEGORIES = {"estadios_sedes_2027", "cidades_sedes_2027", "torcida_futebol_feminino"}
API = base.API
UA = base.UA

def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

def matches_alias(row: dict, aliases: tuple[str, ...]) -> bool:
    descriptor = norm(" ".join((row.get("titulo", ""), row.get("pessoa_local", ""))))
    return any(norm(alias) in descriptor for alias in aliases)

# Ritmo conservador e respeito ao Retry-After / reset informado pelo Commons.
_last_call = 0.0
def resilient_api(params):
    global _last_call
    gap = 3.0 - (time.monotonic() - _last_call)
    if gap > 0:
        time.sleep(gap)
    params = {**params, "format": "json", "formatversion": "2", "maxlag": "5"}
    url = f"{API}?{urlencode(params)}"
    for attempt in range(9):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            _last_call = time.monotonic()
            return data
        except HTTPError as exc:
            if exc.code not in (429, 503):
                raise
            retry_after = exc.headers.get("Retry-After")
            reset = exc.headers.get("X-RateLimit-Reset")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else 0
            if not wait and reset and reset.isdigit():
                wait = max(0, int(reset) - int(time.time()))
            if not wait:
                wait = min(180, 20 * (2 ** min(attempt, 3)))
            wait = max(wait, 15)
            print(f"Commons HTTP {exc.code}; aguardando {wait}s (tentativa {attempt + 1}/9)", flush=True)
            time.sleep(wait)
            _last_call = time.monotonic()
    raise RuntimeError("Wikimedia Commons manteve limite 429/503 após 9 tentativas")

base.api = resilient_api

def main() -> None:
    if not base.CSV_PATH.exists():
        raise SystemExit("Catálogo CSV não encontrado; expansão cancelada.")
    with base.CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        current = list(csv.DictReader(f))
    rows = [r for r in current if r.get("categoria") not in NEW_CATEGORIES]
    if len(rows) != 500:
        raise SystemExit(f"Catálogo-base inesperado: {len(rows)} registros; esperado 500.")
    seen_pages = {r.get("pagina_origem", "").strip() for r in rows if r.get("pagina_origem")}
    seen_urls = {r.get("url_direta", "").strip() for r in rows if r.get("url_direta")}
    additions = []
    counts = Counter()
    distribution = Counter()

    def collect(category: str, query: str, target: int, aliases: tuple[str, ...] = (),
                city: str = "", venue: str = "", pages: int = 2) -> None:
        found = 0
        print(f"Busca {category}: meta {target} — {query}", flush=True)
        for page in base.candidates(query, pages=pages):
            if found >= target:
                break
            row = base.to_row(page, category)
            if not row:
                continue
            if not all(row.get(field) for field in ("autor", "licenca", "url_licenca", "atribuicao")):
                continue
            if aliases and not matches_alias(row, aliases):
                continue
            page_url = row.get("pagina_origem", "").strip()
            direct_url = row.get("url_direta", "").strip()
            if not page_url or not direct_url or page_url in seen_pages or direct_url in seen_urls:
                continue
            tags = []
            if city:
                tags.append(f"CIDADE_SEDE={city}")
            if venue:
                tags.append(f"ARENA={venue}")
            row["observacoes"] = (row.get("observacoes", "").rstrip() + " | " + " | ".join(tags)).strip(" |")
            additions.append(row)
            seen_pages.add(page_url)
            seen_urls.add(direct_url)
            found += 1
            counts[category] += 1
            if city:
                distribution[f"cidade:{city}"] += 1
            if venue:
                distribution[f"arena:{venue}"] += 1
        if found != target:
            raise SystemExit(
                f"Variedade insuficiente em {category} / {query}: {found}/{target}. "
                "Catálogo original preservado; não gravado."
            )

    stadium_plan = [
        ("Mineirão", "Belo Horizonte", 7, ["Mineirao stadium Belo Horizonte"], ("mineirao", "mineirão")),
        ("Mané Garrincha", "Brasília", 6, ["Estadio Nacional Brasilia Mane Garrincha"], ("mane garrincha", "estadio nacional de brasilia", "estádio nacional de brasília")),
        ("Castelão", "Fortaleza", 6, ["Arena Castelao Fortaleza Brazil"], ("castelao", "castelão", "arena castelao", "arena castelão")),
        ("Beira-Rio", "Porto Alegre", 6, ["Beira-Rio stadium Porto Alegre"], ("beira-rio", "beira rio")),
        ("Arena Pernambuco", "Recife", 6, ["Arena Pernambuco stadium"], ("arena pernambuco",)),
        ("Maracanã", "Rio de Janeiro", 6, ["Maracana stadium Rio de Janeiro"], ("maracana", "maracanã")),
        ("Fonte Nova", "Salvador", 6, ["Arena Fonte Nova Salvador"], ("fonte nova", "arena fonte nova")),
        ("Neo Química Arena", "São Paulo", 7, ["Arena Corinthians Sao Paulo stadium", "Neo Quimica Arena stadium"], ("neo quimica arena", "neo química arena", "arena corinthians")),
    ]
    for venue, city, total, queries, aliases in stadium_plan:
        if len(queries) == 1:
            collect("estadios_sedes_2027", queries[0], total, aliases, city, venue)
        else:
            collect("estadios_sedes_2027", queries[0], 4, aliases, city, venue)
            collect("estadios_sedes_2027", queries[1], total - 4, aliases, city, venue)

    city_plan = [
        ("Belo Horizonte", "Belo Horizonte Brazil city landmark", ("belo horizonte",)),
        ("Brasília", "Brasilia Brazil city landmark", ("brasilia", "brasília")),
        ("Fortaleza", "Fortaleza Ceara Brazil landmark", ("fortaleza",)),
        ("Porto Alegre", "Porto Alegre Brazil landmark", ("porto alegre",)),
        ("Recife", "Recife Pernambuco Brazil landmark", ("recife",)),
        ("Rio de Janeiro", "Rio de Janeiro Brazil landmark", ("rio de janeiro",)),
        ("Salvador", "Salvador Bahia Brazil landmark", ("salvador",)),
        ("São Paulo", "Sao Paulo Brazil landmark", ("sao paulo", "são paulo")),
    ]
    for city, query, aliases in city_plan:
        collect("cidades_sedes_2027", query, 5, aliases, city=city, pages=2)

    fan_queries = base.SEARCHES["torcida_futebol_feminino"]
    for query, target in zip(fan_queries, [2, 2, 2, 2, 1, 1]):
        collect("torcida_futebol_feminino", query, target, pages=2)

    expected = {"estadios_sedes_2027": 50, "cidades_sedes_2027": 40, "torcida_futebol_feminino": 10}
    if len(additions) != 100 or dict(counts) != expected:
        raise SystemExit(f"Expansão incompleta: {len(additions)}/100; {dict(counts)}")
    for city, _, _ in city_plan:
        if distribution[f"cidade:{city}"] != 5 + next(n for v,c,n,_,_ in stadium_plan if c == city):
            raise SystemExit(f"Distribuição incorreta para {city}: {distribution[f'cidade:{city}']}")
    for venue, _, target, _, _ in stadium_plan:
        if distribution[f"arena:{venue}"] != target:
            raise SystemExit(f"Distribuição incorreta para arena {venue}")
    for index, row in enumerate(additions, start=len(rows) + 1):
        row["id"] = f"IMG{index:04d}"
    combined = rows + additions
    if len(combined) != 600:
        raise SystemExit(f"Total inesperado: {len(combined)}/600")
    with base.CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=base.FIELDS)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in base.FIELDS} for row in combined)
    base.JSON_PATH.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("EXPANSAO_OK", len(additions))
    print("TOTAL", len(combined))
    print("DISTRIBUICAO_CIDADES_E_ARENAS", dict(distribution))
    print("DISTRIBUICAO_CATEGORIAS", dict(counts))

if __name__ == "__main__":
    main()
