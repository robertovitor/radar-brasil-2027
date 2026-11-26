#!/usr/bin/env python3
"""Acrescenta 100 fotos variadas de estádios, cidades-sede e torcida.

Preserva os 500 registros originais. Se a expansão já existir, substitui
somente as 100 linhas destas três categorias, evitando acumular duplicatas.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter

import gerar_banco_imagens_v3 as base

NEW_CATEGORIES = {
    "estadios_sedes_2027",
    "cidades_sedes_2027",
    "torcida_futebol_feminino",
}

def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

def matches_alias(row: dict, aliases: tuple[str, ...]) -> bool:
    descriptor = norm(" ".join((row.get("titulo", ""), row.get("pessoa_local", ""))))
    return any(norm(alias) in descriptor for alias in aliases)

def main() -> None:
    if not base.CSV_PATH.exists():
        raise SystemExit("Catálogo CSV não encontrado; expansão cancelada.")

    with base.CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        current = list(csv.DictReader(f))

    # Reaproveita a base original e regenera somente as categorias da expansão.
    rows = [r for r in current if r.get("categoria") not in NEW_CATEGORIES]
    if len(rows) < 500:
        raise SystemExit(f"Catálogo-base inesperado: {len(rows)} registros; mínimo 500.")

    seen_pages = {r.get("pagina_origem", "").strip() for r in rows if r.get("pagina_origem")}
    seen_urls = {r.get("url_direta", "").strip() for r in rows if r.get("url_direta")}
    additions = []
    counts = Counter()

    def collect(category: str, query: str, target: int, aliases: tuple[str, ...] = ()) -> None:
        if target <= 0:
            return
        found = 0
        print(f"Busca {category}: meta {target} — {query}")
        try:
            for page in base.candidates(query, pages=6):
                if found >= target:
                    break
                row = base.to_row(page, category)
                if not row:
                    continue
                # Exige licença, URL da licença, autoria e atribuição explícitas.
                if not all(row.get(field) for field in ("autor", "licenca", "url_licenca", "atribuicao")):
                    continue
                if aliases and not matches_alias(row, aliases):
                    continue
                page_url = row.get("pagina_origem", "").strip()
                direct_url = row.get("url_direta", "").strip()
                if not page_url or not direct_url or page_url in seen_pages or direct_url in seen_urls:
                    continue
                additions.append(row)
                seen_pages.add(page_url)
                seen_urls.add(direct_url)
                found += 1
                counts[category] += 1
        except Exception as exc:
            print(f"AVISO busca {category} ({query}): {type(exc).__name__}: {exc}")
        if found < target:
            raise SystemExit(
                f"Variedade insuficiente em {category} / {query}: {found}/{target}. "
                "Catálogo original preservado; não gravado."
            )

    # 50 imagens distribuídas pelas oito arenas. São Paulo usa duas consultas.
    stadium_plan = [
        ("Mineirão", 7, ["Mineirao stadium Belo Horizonte"], ("mineirao", "mineirão")),
        ("Mané Garrincha", 6, ["Estadio Nacional Brasilia Mane Garrincha"], ("mane garrincha", "estadio nacional de brasilia", "estádio nacional de brasília")),
        ("Castelão", 6, ["Arena Castelao Fortaleza Brazil"], ("castelao", "castelão", "arena castelao", "arena castelão")),
        ("Beira-Rio", 6, ["Beira-Rio stadium Porto Alegre"], ("beira-rio", "beira rio")),
        ("Arena Pernambuco", 6, ["Arena Pernambuco stadium"], ("arena pernambuco",)),
        ("Maracanã", 6, ["Maracana stadium Rio de Janeiro"], ("maracana", "maracanã")),
        ("Fonte Nova", 6, ["Arena Fonte Nova Salvador"], ("fonte nova", "arena fonte nova")),
        ("Neo Química Arena", 7, ["Arena Corinthians Sao Paulo stadium", "Neo Quimica Arena stadium"], ("neo quimica arena", "neo química arena", "arena corinthians")),
    ]
    for label, total, queries, aliases in stadium_plan:
        if len(queries) == 1:
            collect("estadios_sedes_2027", queries[0], total, aliases)
        else:
            collect("estadios_sedes_2027", queries[0], 4, aliases)
            collect("estadios_sedes_2027", queries[1], total - 4, aliases)

    # Cinco imagens para cada uma das oito cidades-sede.
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
    for label, query, aliases in city_plan:
        collect("cidades_sedes_2027", query, 5, aliases)

    # Torcida: distribui as dez imagens por diferentes consultas, não por uma só.
    fan_queries = base.SEARCHES["torcida_futebol_feminino"]
    fan_targets = [2, 2, 2, 2, 1, 1]
    for query, target in zip(fan_queries, fan_targets):
        collect("torcida_futebol_feminino", query, target)

    if len(additions) != 100:
        raise SystemExit(f"Expansão incompleta: {len(additions)}/100. Catálogo original preservado.")
    expected = {"estadios_sedes_2027": 50, "cidades_sedes_2027": 40, "torcida_futebol_feminino": 10}
    if dict(counts) != expected:
        raise SystemExit(f"Distribuição inesperada: {dict(counts)}")

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
    print("DISTRIBUICAO", dict(counts))

if __name__ == "__main__":
    main()
