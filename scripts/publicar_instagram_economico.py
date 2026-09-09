#!/usr/bin/env python3
"""Camada econômica para publicar no Instagram sem consultas auxiliares redundantes."""
from __future__ import annotations

import json
import os
import pathlib
import time

import publicar_instagram as base

CACHE = pathlib.Path("instagram/meta-account-cache.json")
STATE = base.RATE_LIMIT_STATE
_original_discover = base.discover_instagram_user


def _read_json(path: pathlib.Path) -> dict:
    try:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _cached_account() -> tuple[str, str, str] | None:
    for path in (CACHE, STATE):
        data = _read_json(path)
        user_id = str(data.get("instagram_user_id") or data.get("user_id") or "").strip()
        if not user_id:
            continue
        graph_root = str(data.get("instagram_graph_root") or data.get("graph_root") or base.INSTAGRAM_GRAPH_ROOT).strip()
        username = str(data.get("instagram_username") or data.get("username") or "").strip()
        return graph_root, user_id, username
    return None


def _persist_account(graph_root: str, user_id: str, username: str) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "user_id": user_id,
        "username": username,
        "graph_root": graph_root,
        "source": "successful_profile_discovery",
    }
    CACHE.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    state = _read_json(STATE)
    state["instagram_user_id"] = user_id
    state["instagram_username"] = username
    state["instagram_graph_root"] = graph_root
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def discover_instagram_user_economico(token: str) -> tuple[str, str, str]:
    configured = os.getenv("INSTAGRAM_USER_ID", "").strip()
    if configured:
        return _original_discover(token)

    cached = _cached_account()
    if cached:
        print("instagram_profile_lookup_skipped=repo_state_cache")
        return cached

    graph_root, user_id, username = _original_discover(token)
    _persist_account(graph_root, user_id, username)
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
