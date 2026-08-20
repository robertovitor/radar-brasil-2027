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

SOURCE_URL = os.environ["SOURCE_URL"]
OUTPUT = Path(os.environ.get("OUTPUT_FILE", "dados.json"))
NEWS_OUTPUT = Path(os.environ.get("NEWS_OUTPUT_FILE", "noticias.json"))
SHEET = "02_Eventos"
NEWS_SHEET = "06_Noticias"
FIELDS = [
    "ID", "Status", "Data", "DataBR", "UF", "Cidade", "Categoria",
    "Organizador", "Publico", "Patrocinador", "Local", "Latitude",
    "Longitude", "Link", "Observacoes", "Mes", "Ano", "Regiao",
]
MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
          "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
REGIONS = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte",
    "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste",
    "MA": "Nordeste", "PB": "Nordeste", "PE": "Nordeste",
    "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste",
    "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul", "BR": "Nacional",
}
SOURCE_REQUIRED = [
    "ID", "Status", "Data", "UF", "Cidade", "Categoria", "Organizador",
    "Publico", "Patrocinador", "Local", "Latitude", "Longitude",
    "Link", "Observacoes",
]


def normalized(value):
    text = "" if value is None else str(value).strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def download_candidates(url):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "dropbox.com" in parts.netloc:
        query["dl"] = "1"
        query.pop("download", None)
    else:
        query["download"] = "1"
    direct = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    token = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    candidates = [direct]
    if "1drv.ms" in parts.netloc or "onedrive.live.com" in parts.netloc:
        candidates.append(
            f"https://api.onedrive.com/v1.0/shares/u!{token}/root/content"
        )
    return candidates


def download_xlsx():
    errors = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    })

    # Abre primeiro o compartilhamento e preserva eventuais cookies
    # antes de solicitar o download direto.
    try:
        landing = session.get(SOURCE_URL, timeout=90, allow_redirects=True)
        landing.raise_for_status()
        if landing.content.startswith(b"PK"):
            return landing.content
    except Exception as exc:
        landing = None
        errors.append(f"abertura do link incorporado: {exc}")

    candidates = download_candidates(SOURCE_URL)
    if landing is not None:
        query = dict(parse_qsl(urlsplit(landing.url).query, keep_blank_values=True))
        resid = query.get("resid")
        cid = query.get("cid")
        if resid:
            params = {"resid": resid}
            if cid:
                params["cid"] = cid
            if query.get("authkey"):
                params["authkey"] = query["authkey"]
            candidates.insert(0, "https://onedrive.live.com/download?" + urlencode(params))

    for url in candidates:
        try:
            headers = {"Referer": landing.url if landing is not None else SOURCE_URL}
            response = session.get(
                url, timeout=90, allow_redirects=True, headers=headers
            )
            response.raise_for_status()
            if not response.content.startswith(b"PK"):
                raise ValueError(
                    f"a resposta não é XLSX ({response.headers.get('content-type', 'tipo desconhecido')})"
                )
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
    wanted.update({
        "publicoestimado": "Publico",
        "linkfonte": "Link",
    })
    header_row = None
    columns = {}
    for row_number, row in enumerate(sheet.iter_rows(min_row=1, max_row=50, values_only=True), 1):
        found = {wanted[normalized(value)]: index for index, value in enumerate(row)
                 if normalized(value) in wanted}
        if all(name in found for name in SOURCE_REQUIRED):
            header_row, columns = row_number, found
            break
    if header_row is None:
        raise RuntimeError("Cabeçalho da aba 02_Eventos não reconhecido.")
    missing = [field for field in SOURCE_REQUIRED if field not in columns]
    if missing:
        raise RuntimeError("Campos obrigatórios ausentes: " + ", ".join(missing))

    events = []
    for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
        event_id = row[columns["ID"]]
        if event_id is None or not str(event_id).strip():
            continue
        event = {
            field: row[columns[field]] if field in columns else None
            for field in FIELDS
        }
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
        event["Regiao"] = REGIONS.get(event["UF"].upper(), "")
        events.append({field: event[field] for field in FIELDS})

    if not events:
        raise RuntimeError("Nenhum evento válido foi encontrado; dados.json não será alterado.")
    ids = [event["ID"] for event in events]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Há IDs de eventos duplicados; dados.json não será alterado.")

    OUTPUT.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if NEWS_SHEET not in workbook.sheetnames:
        raise RuntimeError(f"A aba {NEWS_SHEET!r} não foi encontrada.")
    news_sheet = workbook[NEWS_SHEET]
    news_wanted = {
        "data": "Data", "titulo": "Titulo", "tema": "Tema",
        "cidadeuf": "CidadeUF", "veiculo": "Veiculo", "link": "Link",
        "sentimento": "Sentimento", "impacto": "Impacto", "resumo": "Resumo",
    }
    news_header = None
    news_columns = {}
    for row_number, row in enumerate(
        news_sheet.iter_rows(min_row=1, max_row=30, values_only=True), 1
    ):
        found = {
            news_wanted[normalized(value)]: index
            for index, value in enumerate(row)
            if normalized(value) in news_wanted
        }
        if all(field in found for field in news_wanted.values()):
            news_header, news_columns = row_number, found
            break
    if news_header is None:
        raise RuntimeError("Cabeçalho da aba 06_Noticias não reconhecido.")

    news = []
    for row in news_sheet.iter_rows(min_row=news_header + 1, values_only=True):
        title = row[news_columns["Titulo"]]
        if title is None or not str(title).strip():
            continue
        date = as_date(row[news_columns["Data"]])
        item = {
            "Data": date.isoformat(),
            "DataBR": date.strftime("%d/%m/%Y"),
            "Titulo": str(title).strip(),
            "Tema": str(row[news_columns["Tema"]] or "").strip(),
            "CidadeUF": str(row[news_columns["CidadeUF"]] or "").strip(),
            "Veiculo": str(row[news_columns["Veiculo"]] or "").strip(),
            "Link": str(row[news_columns["Link"]] or "").strip(),
            "Sentimento": str(row[news_columns["Sentimento"]] or "").strip(),
            "Impacto": str(row[news_columns["Impacto"]] or "").strip(),
            "Resumo": str(row[news_columns["Resumo"]] or "").strip(),
        }
        news.append(item)
    news.sort(key=lambda item: item["Data"], reverse=True)
    NEWS_OUTPUT.write_text(
        json.dumps(news, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"{len(events)} eventos gravados em {OUTPUT}; "
        f"{len(news)} notícias gravadas em {NEWS_OUTPUT}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise
