#!/usr/bin/env python3
"""Publica sequencialmente todos os posts de um lote do Radar Brasil 2027."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time


def load_published(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    rows = data.get("published", []) if isinstance(data, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def normalize_new_reconciliations(path: pathlib.Path, previous_keys: set[str]) -> int:
    """Reconciliação remota não conta como nova publicação para o intervalo de 1 hora."""
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    rows = data.get("published", []) if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return 0

    changed = 0
    for row in rows:
        if not isinstance(row, dict) or not row.get("reconciled_from_remote"):
            continue
        key = str(row.get("key") or "").strip()
        if key and key in previous_keys:
            continue
        published_at = str(row.get("published_at") or "").strip()
        if not published_at:
            continue
        row["reconciled_at"] = published_at
        row.pop("published_at", None)
        changed += 1

    if changed:
        path.write_text(json.dumps({"published": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True, type=pathlib.Path)
    parser.add_argument("--ledger", default="instagram/publicados.json", type=pathlib.Path)
    parser.add_argument("--delay-seconds", default=3, type=float)
    args = parser.parse_args()

    batch = json.loads(args.batch.read_text(encoding="utf-8"))
    posts = [pathlib.Path(value) for value in batch.get("posts", [])]
    failures: list[str] = []
    successes = 0
    previous_keys = {
        str(row.get("key") or "").strip()
        for row in load_published(args.ledger)
        if str(row.get("key") or "").strip()
    }

    for index, post in enumerate(posts, start=1):
        print(f"[{index}/{len(posts)}] Publicando {post}", flush=True)
        result = subprocess.run(
            [
                sys.executable,
                "scripts/publicar_instagram.py",
                "--post",
                str(post),
                "--ledger",
                str(args.ledger),
                "--mode",
                "publish",
            ],
            check=False,
        )
        if result.returncode == 0:
            successes += 1
        else:
            failures.append(str(post))
        if index < len(posts) and args.delay_seconds > 0:
            time.sleep(args.delay_seconds)

    reconciled = normalize_new_reconciliations(args.ledger, previous_keys)
    if reconciled:
        print(f"reconciled_existing_count={reconciled}")
        print("reconciled_existing_continue=true")
        print("A reconciliação foi registrada sem consumir o intervalo de 1 hora; o próximo gatilho automático continuará procurando outro candidato.")

    print(f"Lote concluído: {successes} sucesso(s), {len(failures)} falha(s).")
    if failures:
        print("Falharam: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
