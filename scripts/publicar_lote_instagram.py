#!/usr/bin/env python3
"""Publica sequencialmente todos os posts de um lote do Radar Brasil 2027."""

from __future__ import annotations

import argparse
import json
import os
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
    """Preserva o horário remoto e registra quando a reconciliação ocorreu."""
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
        # published_at representa o melhor horário conhecido do post remoto e
        # deve continuar contando para a trava de 60 minutos.
        row["reconciled_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
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
        print("A reconciliação foi registrada e passa a consumir o intervalo de 1 hora.")

        # Antes, a continuação dependia de um novo push/workflow. Commits feitos pelo
        # GITHUB_TOKEN não disparam outro workflow de push, então a rodada podia parar
        # aqui por horas. Agora continuamos dentro do mesmo job até achar um post novo.
        if os.environ.get("INSTAGRAM_CONTINUATION_ACTIVE") != "1":
            print("reconciled_existing_same_run_continuation=true", flush=True)
            env = os.environ.copy()
            env["INSTAGRAM_CONTINUATION_ACTIVE"] = "1"
            continuation = subprocess.run(
                [sys.executable, "scripts/continuar_publicacao_instagram.py"],
                env=env,
                check=False,
            )
            if continuation.returncode != 0:
                print("same_run_continuation_failed=true", file=sys.stderr)
                return continuation.returncode

    print(f"Lote concluído: {successes} sucesso(s), {len(failures)} falha(s).")
    if failures:
        print("Falharam: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
