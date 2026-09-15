#!/usr/bin/env python3
"""Ledger local de envios de alertas, sem armazenar endereços de e-mail.

Uso:
  python scripts/alertas_ledger.py check --kind evento --recipient-record-id rec... --content-key EVT-0001
  python scripts/alertas_ledger.py register --kind noticia --recipient-record-id rec... --content-key https://...

O recipient_ref é derivado do record ID do Airtable via SHA-256. O e-mail nunca é
persistido no repositório público.

Trava conservadora para notícias:
- `check --kind noticia` só libera o envio se `content-key` já estiver presente em
  `noticias.json`, que é a base pública do Radar após o Merge.
- A validação é totalmente local e não adiciona leituras ao Airtable.
- Eventos mantêm o comportamento anterior para não alterar um fluxo já estável.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "evento": ROOT / "alertas" / "envios-eventos.json",
    "noticia": ROOT / "alertas" / "envios-noticias.json",
}
PUBLIC_NEWS_FILE = ROOT / "noticias.json"


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


def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
        if not parts.scheme or not parts.netloc:
            return value.rstrip("/")
        # Query/fragmentos não definem a identidade editorial para esta trava.
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))
    except Exception:
        return value.rstrip("/")


def news_is_published(content_key: str) -> bool:
    """Confirma localmente que a notícia já passou pelo Merge e está no Radar."""
    if not PUBLIC_NEWS_FILE.exists():
        return False
    try:
        rows = json.loads(PUBLIC_NEWS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(rows, list):
        return False

    wanted = normalize_url(content_key)
    if not wanted:
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        link = normalize_url(str(row.get("Link") or row.get("link") or row.get("URL") or row.get("url") or ""))
        if link and link == wanted:
            return True
    return False


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
        # Fail closed apenas para notícias: o alerta só pode sair depois que o
        # conteúdo estiver em noticias.json. Não consulta Airtable nem muda o
        # comportamento de eventos.
        if args.kind == "noticia" and not news_is_published(args.content_key):
            print("published_in_radar=false")
            print("send_allowed=false")
            print("reason=noticia_ainda_nao_publicada_no_radar")
            print("delivery_key=" + delivery_key)
            return 2
        if args.kind == "noticia":
            print("published_in_radar=true")
            print("send_allowed=true")
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
