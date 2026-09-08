#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "alertas" / "envios-eventos.json",
    ROOT / "alertas" / "envios-noticias.json",
]
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


def main() -> int:
    errors: list[str] = []
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        if EMAIL_RE.search(text):
            errors.append(f"{path.name}: endereço de e-mail detectado")
            continue
        data = json.loads(text)
        if data.get("privacy") != "no_email_addresses":
            errors.append(f"{path.name}: marcador de privacidade ausente")
        if not isinstance(data.get("entries"), list):
            errors.append(f"{path.name}: entries deve ser uma lista")
        for i, row in enumerate(data.get("entries", []), start=1):
            if not isinstance(row, dict):
                errors.append(f"{path.name} entrada {i}: formato inválido")
                continue
            forbidden = {"email", "e-mail", "recipient_email", "recipient"} & set(row)
            if forbidden:
                errors.append(f"{path.name} entrada {i}: campos proibidos {sorted(forbidden)}")
            if not row.get("delivery_key") or not row.get("recipient_ref"):
                errors.append(f"{path.name} entrada {i}: chave ou recipient_ref ausente")
    if errors:
        print("Falha na validação de privacidade:")
        for err in errors:
            print("-", err)
        return 1
    print("OK: ledgers sem endereços de e-mail e com estrutura válida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
