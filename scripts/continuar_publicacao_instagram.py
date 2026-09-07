#!/usr/bin/env python3
"""Continua a rodada do Instagram após reconciliações até obter um post realmente novo.

A continuação acontece dentro do mesmo job. Se a Meta entrar em rate limit, a
reserva da tentativa é liberada, o cooldown persistido é respeitado e a rodada
termina em modo adiado, sem gerar falso erro.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "instagram/publicados.json"
RATE_STATE = ROOT / "instagram/meta-rate-limit.json"
MAX_TENTATIVAS = int(os.environ.get("INSTAGRAM_CONTINUATION_MAX_ATTEMPTS", "8"))


def run(cmd: list[str], *, env: dict[str, str] | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=capture, check=False)


def git_sync() -> bool:
    return run(["git", "pull", "--rebase", "--autostash", "origin", "main"]).returncode == 0


def git_commit_push(paths: list[str], message: str) -> bool:
    run(["git", "config", "user.name", "radar-instagram-bot"])
    run(["git", "config", "user.email", "actions@users.noreply.github.com"])
    run(["git", "add", *paths])
    if run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        print(f"commit_skipped={message}:no_changes")
        return True
    if run(["git", "commit", "-m", message]).returncode != 0:
        return False
    if not git_sync():
        return False
    return run(["git", "push", "origin", "HEAD:main"]).returncode == 0


def ledger_rows() -> list[dict]:
    try:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("published", []) if isinstance(data, dict) else []
    return [r for r in rows if isinstance(r, dict)]


def rate_limit_active() -> tuple[bool, str]:
    try:
        state = json.loads(RATE_STATE.read_text(encoding="utf-8"))
        raw = str(state.get("blocked_until") or "").strip()
        if not state.get("active") or not raw:
            return False, ""
        until = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if until.tzinfo is None:
            until = until.replace(tzinfo=dt.timezone.utc)
        active = dt.datetime.now(dt.timezone.utc) < until.astimezone(dt.timezone.utc)
        return active, until.astimezone(dt.timezone.utc).isoformat()
    except Exception:
        return False, ""


def parse_selector(output: str) -> tuple[bool, str, str]:
    found = False
    batch = ""
    reason = ""
    for line in output.splitlines():
        if line.startswith("found="):
            found = line.split("=", 1)[1].strip().lower() == "true"
        elif line.startswith("batch_file="):
            batch = line.split("=", 1)[1].strip()
        elif line.startswith("reason="):
            reason = line.split("=", 1)[1].strip()
    return found, batch, reason


def batch_key(batch_path: pathlib.Path) -> str:
    try:
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        posts = batch.get("posts", []) if isinstance(batch, dict) else []
        if not posts:
            return ""
        post_path = pathlib.Path(str(posts[0]))
        if not post_path.is_absolute():
            post_path = ROOT / post_path
        post = json.loads(post_path.read_text(encoding="utf-8"))
        return str(post.get("key") or post.get("idempotency_key") or "").strip()
    except Exception:
        return ""


def row_for_key(key: str) -> dict | None:
    for row in reversed(ledger_rows()):
        if str(row.get("key") or "").strip() == key:
            return row
    return None


def clear_reservation(batch: pathlib.Path, env: dict[str, str]) -> bool:
    if not git_sync():
        return False
    clear = run([sys.executable, "scripts/reservar_publicacao_instagram.py", "clear", "--batch", str(batch.relative_to(ROOT))], env=env)
    if clear.returncode != 0:
        return False
    return git_commit_push(["instagram/reservas-publicacao.json"], "Libera reserva após publicação confirmada ou adiada")


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = "scripts"
    env["INSTAGRAM_CONTINUATION_ACTIVE"] = "1"

    for attempt in range(1, MAX_TENTATIVAS + 1):
        print(f"continuation_attempt={attempt}", flush=True)
        if not git_sync():
            print("continuation_error=git_sync_failed", file=sys.stderr)
            return 1

        selected = run([sys.executable, "scripts/preparar_post_instagram_v2.py"], env=env, capture=True)
        output = (selected.stdout or "") + (selected.stderr or "")
        print(output, end="" if output.endswith("\n") else "\n")
        found, batch_raw, reason = parse_selector(output)

        if selected.returncode != 0:
            if reason in {"quality_gate_failed", "all_quality_candidates_exhausted"}:
                print(f"continuation_stopped={reason}")
                return 0
            print(f"continuation_error=selector_failed:{reason or selected.returncode}", file=sys.stderr)
            return selected.returncode or 1
        if not found or not batch_raw:
            print(f"continuation_stopped={reason or 'no_candidate'}")
            return 0

        batch = pathlib.Path(batch_raw)
        if not batch.is_absolute():
            batch = ROOT / batch
        key = batch_key(batch)
        if not key:
            print("continuation_error=batch_key_missing", file=sys.stderr)
            return 1
        print(f"continuation_candidate_key={key}")

        if not git_commit_push(["instagram/artes", "instagram/fila/automatica"], "Prepara post com imagem única"):
            return 1
        if not git_sync():
            return 1

        reserve = run([sys.executable, "scripts/reservar_publicacao_instagram.py", "reserve", "--batch", str(batch.relative_to(ROOT))], env=env)
        if reserve.returncode != 0:
            return 1
        if not git_commit_push(["instagram/reservas-publicacao.json"], "Reserva post antes da publicação no Instagram"):
            return 1

        publish = run([
            sys.executable, "scripts/publicar_lote_instagram.py",
            "--batch", str(batch.relative_to(ROOT)),
            "--ledger", "instagram/publicados.json",
        ], env=env)

        if not git_commit_push(["instagram/publicados.json"], "Registra publicação confirmada no Instagram"):
            return 1
        status = run(["git", "status", "--porcelain", "--", "instagram/meta-rate-limit.json"], capture=True)
        if RATE_STATE.exists() and status.stdout.strip():
            if not git_commit_push(["instagram/meta-rate-limit.json"], "Atualiza cooldown de rate limit da Meta"):
                return 1

        row = row_for_key(key)
        confirmed = bool(row and row.get("instagram_media_id"))
        reconciled = bool(row and row.get("reconciled_from_remote"))
        genuinely_new = bool(row and row.get("published_at") and not reconciled)

        if confirmed:
            if not clear_reservation(batch, env):
                return 1
        elif publish.returncode != 0:
            limited, blocked_until = rate_limit_active()
            if limited:
                if not clear_reservation(batch, env):
                    return 1
                print("continuation_deferred_rate_limit=true")
                print(f"continuation_resume_after={blocked_until}")
                print("continuation_action=wait_for_next_automatic_trigger_after_cooldown")
                return 0
            print("continuation_error=meta_publish_unconfirmed", file=sys.stderr)
            return publish.returncode or 1

        if genuinely_new:
            print("continuation_new_post_published=true")
            print(f"continuation_new_post_key={key}")
            return 0
        if reconciled:
            print("continuation_reconciled_existing=true")
            print("continuation_action=try_next_candidate_same_run")
            time.sleep(1)
            continue

        print("continuation_error=confirmed_without_new_or_reconciled_state", file=sys.stderr)
        return 1

    print(f"continuation_stopped=max_attempts_{MAX_TENTATIVAS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
