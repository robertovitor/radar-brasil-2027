#!/usr/bin/env python3
"""Publica sequencialmente todos os posts de um lote do Radar Brasil 2027."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time


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

    print(f"Lote concluído: {successes} sucesso(s), {len(failures)} falha(s).")
    if failures:
        print("Falharam: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
