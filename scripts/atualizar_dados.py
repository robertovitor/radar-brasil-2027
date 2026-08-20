#!/usr/bin/env python3
import base64
import datetime as dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from openpyxl import load_workbook

SOURCE_URL = os.environ["ONEDRIVE_URL"]
OUTPUT = Path(os.environ.get("OUTPUT_FILE", "dados.json"))
SHEET = "02_Eventos"
FIELDS = [
    "ID", "Status", "Data", "DataBR", "UF", "Cidade", "Categoria",
    "Organizador", "Publico", "Patrocinador", "Local", "Latitude",
    "Longitude", "Link", "Observacoes", "Mes", "Ano", "Regiao",
]
MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
          "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def normalized(value):
    text = "" if value is None else str(value).strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def download_candidates(url):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["download"] = "1"
    direct = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    token = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    return [
        direct,
        f"https://api.onedrive.com/v1.0/shares/u!{token}/root/content",
    ]


def download_xlsx():
    errors = []
    for url in download_candidates(SOURCE_URL):
        try:
            response = requests.get(
                url,
                timeout=90,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            if not response.content.startswith(b"PK"):
                raise ValueError("a resposta não é um arquivo XLSX")
            return response.content
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("Não foi possível baixar a planilha:\n" + "\n".join(errors))


def as_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Data inválida: {value!r}")


def as_number(value, default=None):
    if value is None or str(value).strip() == "":
        return default
    if isinstance(value, (int, float)):
        number = value
    else:
        text = str(value).strip().replace(".", "").replace(",", ".")
        number = float(text)
    return int(number) if float(number).is_integer() else float(number)


def main():
    temp = Path("/tmp/radar_brasil_2027.xlsx")
    temp.write_bytes(download_xlsx())
    workbook = load_workbook(temp, read_only=True, data_only=True)
    if SHEET not in workbook.sheetnames:
        raise RuntimeError(f"A aba {SHEET!r} não foi encontrada.")
    sheet = workbook[SHEET]

    wanted = {normalized(field): field for field in FIELDS}
    header_row = None
    columns = {}
    for row_number, row in enumerate(sheet.iter_rows(min_row=1, max_row=50, values_only=True), 1):
        found = {wanted[normalized(value)]: index for index, value in enumerate(row)
                 if normalized(value) in wanted}
        if all(name in found for name in ("ID", "Status", "Data")) and len(found) >= 15:
            header_row, columns = row_number, found
            break
    if header_row is None:
        raise RuntimeError("Cabeçalho da aba 02_Eventos não reconhecido.")
    missing = [field for field in FIELDS if field not in columns]
    if missing:
        raise RuntimeError("Campos obrigatórios ausentes: " + ", ".join(missing))

    events = []
    for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
        event_id = row[columns["ID"]]
        if event_id is None or not str(event_id).strip():
            continue
        event = {field: row[columns[field]] for field in FIELDS}
        date = as_date(event["Data"])
        for field in ("ID", "Status", "UF", "Cidade", "Categoria", "Organizador",
                      "Patrocinador", "Local", "Link", "Observacoes", "Regiao"):
            event[field] = "" if event[field] is None else str(event[field]).strip()
        event["Data"] = date.isoformat()
        event["DataBR"] = date.strftime("%d/%m/%Y")
        event["Publico"] = as_number(event["Publico"], 0)
        event["Latitude"] = as_number(event["Latitude"])
        event["Longitude"] = as_number(event["Longitude"])
        event["Mes"] = MONTHS[date.month - 1]
        event["Ano"] = date.year
        events.append({field: event[field] for field in FIELDS})

    if not events:
        raise RuntimeError("Nenhum evento válido foi encontrado; dados.json não será alterado.")
    ids = [event["ID"] for event in events]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Há IDs de eventos duplicados; dados.json não será alterado.")

    OUTPUT.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(events)} eventos gravados em {OUTPUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise
