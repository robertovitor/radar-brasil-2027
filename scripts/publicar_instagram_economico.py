#!/usr/bin/env python3
"""Camada econômica para publicar no Instagram sem consultas auxiliares redundantes."""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time

import publicar_instagram as base

CACHE = pathlib.Path("instagram/meta-account-cache.json")
STATE = base.RATE_LIMIT_STATE
BLOCKED = pathlib.Path("instagram/bloqueados-publicacao.json")
RESERVATIONS = pathlib.Path("instagram/reservas-publicacao.json")
_original_discover = base.discover_instagram_user
_original_request_json = base.request_json


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


def _current_post_key() -> str:
    try:
        index = sys.argv.index("--post")
        post_path = pathlib.Path(sys.argv[index + 1])
        post = _read_json(post_path)
        return base.stable_key(post)
    except (ValueError, IndexError, OSError, json.JSONDecodeError):
        return ""


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _hydrate_legacy_uncertain_blocks() -> None:
    """Bloqueia localmente reservas antigas que já chegaram à Meta.

    Essas reservas foram criadas antes da trava permanente. Se estão marcadas
    como uncertain_after_meta, não podem ser republicadas só porque o post
    deixou de aparecer na conta (por exemplo, após exclusão manual).
    """
    reservations = _read_json(RESERVATIONS)
    rows = reservations.get("reservations", [])
    if not isinstance(rows, list):
        return

    legacy_keys = {
        str(row.get("key") or "").strip()
        for row in rows
        if isinstance(row, dict)
        and row.get("uncertain_after_meta") is True
        and str(row.get("key") or "").strip()
    }
    if not legacy_keys:
        return

    data = _read_json(BLOCKED)
    blocked_keys = data.get("blocked_keys", [])
    if not isinstance(blocked_keys, list):
        blocked_keys = []
    current = {str(value).strip() for value in blocked_keys if str(value).strip()}
    missing = sorted(legacy_keys - current)
    if not missing:
        return

    data["blocked_keys"] = [*blocked_keys, *missing]
    legacy = data.get("legacy_uncertain_meta", {})
    if not isinstance(legacy, dict):
        legacy = {}
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for key in missing:
        legacy[key] = {
            "blocked_at": now,
            "reason": "legacy_uncertain_after_meta_never_republish",
        }
    data["legacy_uncertain_meta"] = legacy
    BLOCKED.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"legacy_uncertain_meta_blocks_loaded={len(missing)}")


def _persist_meta_attempt_block(key: str, creation_id: str) -> None:
    """Torna irreversível a idempotência assim que a Meta cria o contêiner.

    A exclusão manual do post no Instagram não pode transformar a pauta em
    inédita novamente. Por isso, antes de chamar media_publish, a chave é
    persistida no repositório em bloqueados-publicacao.json. Se essa gravação
    falhar, a publicação é abortada para nunca existir uma publicação remota
    sem memória local permanente.
    """
    if not key:
        raise base.InstagramError("Não foi possível determinar a chave idempotente antes de publicar na Meta.")

    data = _read_json(BLOCKED)
    blocked_keys = data.get("blocked_keys", [])
    if not isinstance(blocked_keys, list):
        blocked_keys = []
    blocked_keys = [str(value).strip() for value in blocked_keys if str(value).strip()]

    attempts = data.get("meta_attempts", {})
    if not isinstance(attempts, dict):
        attempts = {}

    if key in blocked_keys and key in attempts:
        print(f"meta_attempt_block_already_persisted={key}")
        return

    if key not in blocked_keys:
        blocked_keys.append(key)
    attempts[key] = {
        "creation_id": str(creation_id),
        "attempted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "reason": "meta_container_created_never_republish",
    }
    data["blocked_keys"] = blocked_keys
    data["meta_attempts"] = attempts
    BLOCKED.parent.mkdir(parents=True, exist_ok=True)
    BLOCKED.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _git("config", "user.name", "radar-instagram-bot")
    _git("config", "user.email", "actions@users.noreply.github.com")
    add = _git("add", str(BLOCKED))
    if add.returncode != 0:
        raise base.InstagramError(f"Falha ao preparar trava idempotente no Git: {add.stdout[-500:]}")

    commit = _git("commit", "-m", f"Trava republicação após criação na Meta: {key[:80]}")
    if commit.returncode != 0 and "nothing to commit" not in commit.stdout.lower():
        raise base.InstagramError(f"Falha ao registrar trava idempotente: {commit.stdout[-500:]}")

    for attempt in range(1, 4):
        pull = _git("pull", "--rebase", "--autostash", "origin", "main")
        if pull.returncode == 0:
            push = _git("push", "origin", "HEAD:main")
            if push.returncode == 0:
                print(f"meta_attempt_block_persisted=true;key={key};creation_id={creation_id}")
                return
        time.sleep(attempt * 2)

    raise base.InstagramError(
        "A Meta criou o contêiner, mas a trava idempotente não pôde ser persistida no GitHub. "
        "Publicação abortada antes de media_publish para evitar duplicação futura."
    )


def request_json_idempotente(method: str, path: str, token: str, params: dict | None = None, graph_root: str = base.FACEBOOK_GRAPH_ROOT) -> dict:
    response = _original_request_json(method, path, token, params, graph_root=graph_root)
    normalized_path = path.strip("/")
    is_container_creation = method.upper() == "POST" and normalized_path.endswith("/media") and not normalized_path.endswith("/media_publish")
    if is_container_creation:
        creation_id = str(response.get("id") or "").strip()
        if creation_id:
            _persist_meta_attempt_block(_current_post_key(), creation_id)
    return response


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
base.request_json = request_json_idempotente


if __name__ == "__main__":
    try:
        _hydrate_legacy_uncertain_blocks()
        raise SystemExit(base.main())
    except (base.InstagramError, json.JSONDecodeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
