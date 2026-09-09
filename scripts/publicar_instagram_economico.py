#!/usr/bin/env python3
"""Camada econômica para publicar no Instagram sem consultas auxiliares redundantes."""
from __future__ import annotations

import json
import os
import pathlib
import time

import publicar_instagram as base

CACHE = pathlib.Path("instagram/meta-account-cache.json")
_original_discover = base.discover_instagram_user


def discover_instagram_user_economico(token: str) -> tuple[str, str, str]:
    configured = os.getenv("INSTAGRAM_USER_ID", "").strip()
    if configured:
        return _original_discover(token)

    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            user_id = str(data.get("user_id") or "").strip()
            graph_root = str(data.get("graph_root") or base.INSTAGRAM_GRAPH_ROOT).strip()
            username = str(data.get("username") or "").strip()
            if user_id:
                print("instagram_profile_lookup_skipped=repo_cache")
                return graph_root, user_id, username
        except (json.JSONDecodeError, OSError):
            print("instagram_account_cache_warning=invalid")

    graph_root, user_id, username = _original_discover(token)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps(
            {
                "user_id": user_id,
                "username": username,
                "graph_root": graph_root,
                "source": "successful_profile_discovery",
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print("instagram_account_cache_updated=true")
    return graph_root, user_id, username


def wait_until_ready_economico(container_id: str, token: str, graph_root: str) -> None:
    # Imagem estática: evitar polling de status, que consumia até quatro chamadas
    # por publicação. Aguardar localmente e deixar media_publish ser a próxima
    # chamada à Meta. Se a mídia ainda não estiver pronta, o retry seguro do
    # publicador aguarda novamente sem consultar status.
    seconds = max(8, int(os.getenv("INSTAGRAM_CONTAINER_LOCAL_WAIT_SECONDS", "12")))
    print(f"container_status_poll_skipped=true;local_wait_seconds={seconds}")
    time.sleep(seconds)


base.discover_instagram_user = discover_instagram_user_economico
base.wait_until_ready = wait_until_ready_economico


if __name__ == "__main__":
    try:
        raise SystemExit(base.main())
    except (base.InstagramError, json.JSONDecodeError) as exc:
        import sys
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
