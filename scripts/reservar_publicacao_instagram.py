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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("reserve", "clear"))
    parser.add_argument("--batch", required=True, type=pathlib.Path)
    parser.add_argument("--reservations", default="instagram/reservas-publicacao.json", type=pathlib.Path)
    parser.add_argument("--ledger", default="instagram/publicados.json", type=pathlib.Path)
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
        kept = [x for x in rows if str(x.get("key") or "") != key]
        changed = len(kept) != len(rows)
        if changed:
            args.reservations.parent.mkdir(parents=True, exist_ok=True)
            args.reservations.write_text(json.dumps({"reservations": kept}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"reservation_changed={'true' if changed else 'false'}")
        print(f"reservation_key={key}")
        return 0

    if key in published_keys:
        print("reservation_changed=false")
        print(f"reservation_key={key}")
        print("reservation_reason=already_published")
        return 0

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    existing = next((x for x in rows if str(x.get("key") or "") == key), None)
    if existing:
        existing["last_attempt_at"] = now
        existing["attempts"] = int(existing.get("attempts") or 1) + 1
        existing["post_file"] = str(post_path)
    else:
        rows.append({
            "key": key,
            "post_file": str(post_path),
            "reserved_at": now,
            "last_attempt_at": now,
            "attempts": 1,
        })

    args.reservations.parent.mkdir(parents=True, exist_ok=True)
    args.reservations.write_text(json.dumps({"reservations": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("reservation_changed=true")
    print(f"reservation_key={key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
