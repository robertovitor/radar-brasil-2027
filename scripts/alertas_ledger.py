#!/usr/bin/env python3
"""Ledger local de envios de alertas, sem armazenar endereços de e-mail.

Uso:
  python scripts/alertas_ledger.py check --kind evento --recipient-record-id rec... --content-key EVT-0001
  python scripts/alertas_ledger.py register --kind noticia --recipient-record-id rec... --content-key https://...

O recipient_ref é derivado do record ID do Airtable via SHA-256. O e-mail nunca é
persistido no repositório público.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "evento": ROOT / "alertas" / "envios-eventos.json",
    "noticia": ROOT / "alertas" / "envios-noticias.json",
}


def recipient_ref(record_id: str) -> str:
    value = (record_id or "").strip()
    if not value.startswith("rec"):
        raise ValueError("recipient-record-id inválido")
    return hashlib.sha256(("airtable:" + value).encode("utf-8")).hexdigest()[:24]


def load(kind: str) -> dict:
    path = FILES[kind]
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("entries"), list):
        data["entries"] = []
    return data


def save(kind: str, data: dict) -> None:
    path = FILES[kind]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def key(kind: str, recipient_record_id: str, content_key: str, alert_type: str = "novo") -> str:
    ref = recipient_ref(recipient_record_id)
    raw = f"{kind}|{alert_type.strip().lower()}|{content_key.strip()}|{ref}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def find_entry(data: dict, delivery_key: str) -> dict | None:
    for row in data.get("entries", []):
        if isinstance(row, dict) and row.get("delivery_key") == delivery_key:
            return row
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("check", "register"):
        p = sub.add_parser(name)
        p.add_argument("--kind", required=True, choices=sorted(FILES))
        p.add_argument("--recipient-record-id", required=True)
        p.add_argument("--content-key", required=True)
        p.add_argument("--alert-type", default="novo")
        if name == "register":
            p.add_argument("--gmail-message-id", default="")
            p.add_argument("--status", default="enviado")

    args = parser.parse_args()
    data = load(args.kind)
    delivery_key = key(args.kind, args.recipient_record_id, args.content_key, args.alert_type)
    existing = find_entry(data, delivery_key)

    if args.command == "check":
        print("already_sent=" + ("true" if existing else "false"))
        print("delivery_key=" + delivery_key)
        return 0 if existing else 1

    if existing:
        print("already_sent=true")
        print("delivery_key=" + delivery_key)
        return 0

    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    data["entries"].append({
        "delivery_key": delivery_key,
        "recipient_ref": recipient_ref(args.recipient_record_id),
        "content_key": args.content_key.strip(),
        "alert_type": args.alert_type.strip().lower(),
        "sent_at": now,
        "status": args.status.strip().lower(),
        "gmail_message_id": args.gmail_message_id.strip(),
    })
    save(args.kind, data)
    print("registered=true")
    print("delivery_key=" + delivery_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
