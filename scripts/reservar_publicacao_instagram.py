#!/usr/bin/env python3
"""Mantém reservas persistentes para impedir republicação após falha entre Meta e ledger."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib


def load(path: pathlib.Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def stable_key(post: dict) -> str:
    explicit = str(post.get("idempotency_key") or post.get("id") or "").strip()
    if explicit:
        return explicit
    canonical = json.dumps(
        {"image_url": post.get("image_url"), "caption": post.get("caption")},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def parse_timestamp(value: object) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def meta_rate_limit_active(path: pathlib.Path) -> tuple[bool, str]:
    """Retorna se a Meta está em cooldown ativo e até quando.

    Um rate limit depois de a Meta devolver creation_id é um resultado ambíguo:
    o post pode ter sido efetivamente criado/publicado mesmo sem confirmação local.
    Nessa situação a reserva NÃO pode ser liberada, pois isso permitiria republicar
    a mesma pauta antes de uma reconciliação remota.
    """
    if not path.exists():
        return False, ""
    try:
        state = load(path, {})
        raw = str(state.get("blocked_until") or "").strip()
        if not state.get("active") or not raw:
            return False, raw
        until = parse_timestamp(raw)
        if until is None:
            return False, raw
        return dt.datetime.now(dt.timezone.utc) < until, until.isoformat()
    except (json.JSONDecodeError, OSError, TypeError):
        return False, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("reserve", "clear"))
    parser.add_argument("--batch", required=True, type=pathlib.Path)
    parser.add_argument("--reservations", default="instagram/reservas-publicacao.json", type=pathlib.Path)
    parser.add_argument("--ledger", default="instagram/publicados.json", type=pathlib.Path)
    parser.add_argument("--rate-limit-state", default="instagram/meta-rate-limit.json", type=pathlib.Path)
    parser.add_argument("--ttl-hours", default=2.0, type=float)
    args = parser.parse_args()

    batch = load(args.batch, {})
    posts = [pathlib.Path(x) for x in batch.get("posts", [])]
    if not posts:
        print("reservation_changed=false")
        return 0

    post_path = posts[0]
    post = load(post_path, {})
    key = stable_key(post)
    ledger = load(args.ledger, {"published": []})
    published_keys = {str(x.get("key") or "") for x in ledger.get("published", []) if isinstance(x, dict)}
    state = load(args.reservations, {"reservations": []})
    rows = [x for x in state.get("reservations", []) if isinstance(x, dict)]

    if args.action == "clear":
        # Se a publicação já foi confirmada no ledger, liberar é seguro.
        if key in published_keys:
            kept = [x for x in rows if str(x.get("key") or "") != key]
            changed = len(kept) != len(rows)
            if changed:
                args.reservations.parent.mkdir(parents=True, exist_ok=True)
                args.reservations.write_text(
                    json.dumps({"reservations": kept}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            print(f"reservation_changed={'true' if changed else 'false'}")
            print(f"reservation_key={key}")
            print("reservation_clear_reason=published_confirmed")
            return 0

        # CRÍTICO: rate limit sem confirmação é estado ambíguo, não falha limpa.
        # Preserva a reserva e força reconciliação remota na próxima tentativa.
        rate_active, blocked_until = meta_rate_limit_active(args.rate_limit_state)
        if rate_active:
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            changed = False
            found = False
            for row in rows:
                if str(row.get("key") or "") != key:
                    continue
                found = True
                before = dict(row)
                row["requires_strict_reconciliation"] = True
                row["uncertain_after_meta"] = True
                row["last_attempt_at"] = now
                if blocked_until:
                    row["blocked_until"] = blocked_until
                if row != before:
                    changed = True
            if not found:
                rows.append({
                    "key": key,
                    "post_file": str(post_path),
                    "reserved_at": now,
                    "last_attempt_at": now,
                    "attempts": 1,
                    "requires_strict_reconciliation": True,
                    "uncertain_after_meta": True,
                    "blocked_until": blocked_until,
                })
                changed = True
            if changed:
                args.reservations.parent.mkdir(parents=True, exist_ok=True)
                args.reservations.write_text(
                    json.dumps({"reservations": rows}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            print(f"reservation_changed={'true' if changed else 'false'}")
            print(f"reservation_key={key}")
            print("reservation_preserved_due_uncertain_meta=true")
            print("reservation_requires_strict_reconciliation=true")
            if blocked_until:
                print(f"reservation_blocked_until={blocked_until}")
            return 0

        kept = [x for x in rows if str(x.get("key") or "") != key]
        changed = len(kept) != len(rows)
        if changed:
            args.reservations.parent.mkdir(parents=True, exist_ok=True)
            args.reservations.write_text(
                json.dumps({"reservations": kept}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(f"reservation_changed={'true' if changed else 'false'}")
        print(f"reservation_key={key}")
        print("reservation_clear_reason=no_active_rate_limit")
        return 0

    if key in published_keys:
        print("reservation_changed=false")
        print(f"reservation_key={key}")
        print("reservation_reason=already_published")
        return 0

    now = dt.datetime.now(dt.timezone.utc)
    existing = next((x for x in rows if str(x.get("key") or "") == key), None)
    previous_attempts = 0
    if existing:
        previous_attempts = int(existing.get("attempts") or 1)
        last_attempt = parse_timestamp(existing.get("last_attempt_at") or existing.get("reserved_at"))
        age = now - last_attempt if last_attempt else dt.timedelta(0)
        ttl = dt.timedelta(hours=max(0.1, args.ttl_hours))
        if age < ttl:
            remaining = max(1, int((ttl - age).total_seconds()))
            print("reservation_changed=false")
            print(f"reservation_key={key}")
            print("reservation_conflict=true")
            print(f"reservation_retry_after_seconds={remaining}")
            return 3
        rows = [x for x in rows if str(x.get("key") or "") != key]

    stamp = now.isoformat()
    rows.append({
        "key": key,
        "post_file": str(post_path),
        "reserved_at": stamp,
        "last_attempt_at": stamp,
        "attempts": previous_attempts + 1,
        "requires_strict_reconciliation": previous_attempts > 0,
    })

    args.reservations.parent.mkdir(parents=True, exist_ok=True)
    args.reservations.write_text(
        json.dumps({"reservations": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("reservation_changed=true")
    print(f"reservation_key={key}")
    print(f"reservation_attempt={previous_attempts + 1}")
    print(f"reservation_takeover={'true' if previous_attempts else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
