#!/usr/bin/env python3
"""Acrescenta fotos de estádios, cidades-sede e torcida ao catálogo existente.

Preserva integralmente os registros atuais. Só incorpora imagens do Wikimedia
Commons com metadados de licença aberta, atribuição, resolução e filtros
editoriais aprovados pelo gerador-base.
"""
from __future__ import annotations

import csv
import json
from collections import Counter

import gerar_banco_imagens_v3 as base

TARGETS = {
    "estadios_sedes_2027": 50,
    "cidades_sedes_2027": 40,
    "torcida_futebol_feminino": 10,
}


def main() -> None:
    if not base.CSV_PATH.exists():
        raise SystemExit("Catálogo CSV não encontrado; expansão cancelada.")

    with base.CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) < 500:
        raise SystemExit(f"Catálogo-base inesperado: {len(rows)} registros; mínimo 500.")

    seen_pages = {r.get("pagina_origem", "").strip() for r in rows if r.get("pagina_origem")}
    seen_urls = {r.get("url_direta", "").strip() for r in rows if r.get("url_direta")}
    counts = Counter(r.get("categoria", "") for r in rows)
    additions = []

    for category, target in TARGETS.items():
        if category not in base.SEARCHES:
            raise SystemExit(f"Categoria sem consultas configuradas: {category}")
        for query in base.SEARCHES[category]:
            if counts[category] >= target:
                break
            print(f"Busca {category}: {counts[category]}/{target} — {query}")
            try:
                for page in base.candidates(query, pages=6):
                    if counts[category] >= target:
                        break
                    row = base.to_row(page, category)
                    if not row:
                        continue
                    page_url = row.get("pagina_origem", "").strip()
                    direct_url = row.get("url_direta", "").strip()
                    if not page_url or not direct_url:
                        continue
                    if page_url in seen_pages or direct_url in seen_urls:
                        continue
                    additions.append(row)
                    seen_pages.add(page_url)
                    seen_urls.add(direct_url)
                    counts[category] += 1
            except Exception as exc:
                print(f"AVISO busca {category} ({query}): {type(exc).__name__}: {exc}")

        if counts[category] < target:
            raise SystemExit(
                f"Expansão incompleta em {category}: {counts[category]}/{target}. "
                "Nenhum arquivo foi sobrescrito; revise consultas e tente novamente."
            )

    if len(rows) + len(additions) != 600:
        raise SystemExit(
            f"Total inesperado: base={len(rows)}, novas={len(additions)}, "
            f"total={len(rows) + len(additions)}; esperado 600."
        )

    for index, row in enumerate(additions, start=len(rows) + 1):
        row["id"] = f"IMG{index:04d}"

    combined = rows + additions
    with base.CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=base.FIELDS)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in base.FIELDS} for row in combined)

    base.JSON_PATH.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("EXPANSAO_OK", len(additions))
    print("TOTAL", len(combined))
    print("NOVAS_CATEGORIAS", {key: counts[key] for key in TARGETS})


if __name__ == "__main__":
    main()
