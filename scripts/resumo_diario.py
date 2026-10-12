#!/usr/bin/env python3
"""Planejamento local do resumo. Não chama Airtable/Gmail nem grava contatos no GitHub.

O estado e os planos contêm dados pessoais: use caminhos privados fora do repo.
O executor salva o estado privado antes/depois de cada envio pelo conector Gmail.
"""
import argparse
import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
SENDER = "radarcopafeminina2027@gmail.com"
SITE = "https://radarfutebolfeminino2027.com.br/"
FIELDS = {
    "events": {"email": "fldlL10YHvR57jEdQ", "consent": "fldVvcAKLTlfjwe5s",
               "status": "fldeR5nEsDdlyqTbc", "confirmation": "flde97V1R1te0SMpQ",
               "confirmed_at": "fldPQQRnTuZf7V0HN"},
    "news": {"email": "fldS2i5w3XKlBHrdz", "consent": "fldRUPYXSx74EA6Iz",
             "status": "fldOmYlV9xSQZ4o1f", "confirmation": "fld0uOaCAyDoxtA5H",
             "confirmed_at": "fldbEnCwkLpTQVu6R"},
}


def instant(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp precisa de fuso horário")
    return dt


def name(value):
    return value.get("name", "") if isinstance(value, dict) else str(value or "")


def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def address(value):
    email = str(value or "").strip().lower()
    return email if re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+", email) else ""


def complete_records(result):
    if "records" not in result or result.get("nextCursor") or result.get("offset"):
        raise ValueError("Leitura Airtable incompleta; nenhum envio permitido")
    rows = result["records"]
    total = result.get("metadata", {}).get("totalRecordCount")
    if total is not None and total != len(rows):
        raise ValueError("Contagem Airtable não corresponde à lista completa")
    return rows


def refresh_subscribers(state, events, news, now):
    contacts = {}
    for kind, result in (("events", events), ("news", news)):
        f = FIELDS[kind]
        for row in complete_records(result):
            cells = row["cellValuesByFieldId"]
            email = address(cells.get(f["email"]))
            if not email or cells.get(f["consent"]) is not True:
                continue
            if name(cells.get(f["status"])) != "Ativo" or name(cells.get(f["confirmation"])) != "Confirmado":
                continue
            confirmed = cells.get(f["confirmed_at"])
            if confirmed:
                instant(confirmed)
            contacts.setdefault(email, {"subscriptions": {}})["subscriptions"][kind] = {
                "record_id": row["id"], "confirmed_at": confirmed,
                "consent": True, "status": "Ativo", "confirmation": "Confirmado",
            }
    state["subscribers"] = contacts
    state["subscribers_refreshed_at"] = now


def refresh_due(state, now):
    last = state.get("subscribers_refreshed_at")
    return not last or instant(now) - instant(last) >= timedelta(days=7)


def refresh_unsubscribes(state, result, now):
    # Caixa de seleção "Confirmar descadastro" é boolean, não singleSelect.
    blocked = {}
    for row in complete_records(result):
        f = row["cellValuesByFieldId"]
        if f.get("fldmBNL8o8KRNiJp8") is not True and name(f.get("flddfJQosqnaN7qNk")) not in ("Confirmado", "Processado"):
            continue
        email = address(f.get("fldnfgNsfFRy630Vx"))
        if not email:
            continue
        kind = normalized(name(f.get("fld4HYNbrTRgdxQ18")))
        kinds = ["events"] if kind in ("evento", "eventos") else ["news"] if kind in ("noticia", "noticias") else ["events", "news"]
        blocked.setdefault(email, set()).update(kinds)
    state["airtable_unsubscribes"] = {e: sorted(kinds) for e, kinds in blocked.items()}
    state["unsubscribes_checked_at"] = now


def identity(kind, row):
    if kind == "news":
        value = str(row.get("Link") or "").strip()
        if not value:
            raise ValueError("Notícia sem identidade Link")
    else:
        value = str(row.get("ID") or "").strip()
        if not value:
            value = "|".join(normalized(row.get(k)) for k in ("Titulo", "Data", "Link"))
    return kind + ":" + value


def safe_url(value):
    value = str(value or "").strip()
    parsed = urlsplit(value)
    return value if parsed.scheme in ("http", "https") and parsed.netloc else ""


def observe(state, events, news, now, publication_times=None):
    if not isinstance(events, list) or not isinstance(news, list):
        raise ValueError("Fontes públicas devem ser listas completas")
    since = state["last_observed_at"]
    seen = set(state["seen"])
    public_ids = set()
    for kind, rows in (("events", events), ("news", news)):
        for row in rows:
            key = identity(kind, row)
            public_ids.add(key)
            if key in seen:
                continue
            seen.add(key)
            published = (publication_times or {}).get(key)
            if published and instant(published) < instant(state["started_at"]):
                continue
            state["pending"][key] = {
                "key": key, "kind": kind, "title": str(row.get("Titulo") or "").strip(),
                "summary": str(row.get("Resumo") or row.get("Observacoes") or ""),
                "url": safe_url(row.get("Link")), "date": str(row.get("DataBR") or row.get("Data") or ""),
                "location": str(row.get("Local") or row.get("CidadeUF") or row.get("Cidade") or ""),
                "published_at": published, "new_since": since, "observed_at": now,
            }
    state["seen"] = sorted(seen)
    state["last_observed_at"] = now
    # Não divulgar itens removidos pela curadoria.
    state["pending"] = {k: v for k, v in state["pending"].items() if k in public_ids}


def allowed(state, email, kind):
    return kind not in set(state.get("airtable_unsubscribes", {}).get(email, [])) | set(state.get("gmail_unsubscribes", {}).get(email, []))


def digest_html(items, day, token):
    out = ['<div style="font-family:Arial,sans-serif;line-height:1.6;max-width:640px;color:#17351f">',
           '<h1 style="font-size:24px">Radar Brasil 2027</h1>',
           '<p>Resumo diário — ' + html.escape(datetime.fromisoformat(day).strftime("%d/%m/%Y")) + '</p>']
    for kind, heading in (("news", "Notícias"), ("events", "Novos eventos")):
        selected = [item for item in items if item["kind"] == kind]
        if not selected:
            continue
        out.append("<h2>" + heading + "</h2>")
        for item in selected:
            out.append("<h3>" + html.escape(item["title"]) + "</h3>")
            if kind == "events":
                detail = " · ".join(x for x in (item["date"], item["location"]) if x)
                out.append("<p>" + html.escape(detail) + "</p>")
            if item["summary"]:
                out.append("<p>" + html.escape(item["summary"]) + "</p>")
            if item["url"]:
                out.append('<p><a href="' + html.escape(item["url"], quote=True) + '">Leia na fonte</a></p>')
    unsubscribe = "mailto:" + SENDER + "?subject=" + quote("DESCADASTRAR RADAR") + "&body=" + quote("Quero cancelar todos os resumos do Radar Brasil 2027.")
    out.extend(['<p><a href="' + SITE + '">Veja o Radar</a></p>',
                '<hr><p style="font-size:12px">Você recebe este resumo conforme suas inscrições confirmadas. '
                'Para deixar de receber, <a href="' + html.escape(unsubscribe, quote=True) + '">clique aqui</a> '
                'e envie a solicitação, ou responda com DESCADASTRAR RADAR.</p>',
                '<p style="font-size:10px;color:#777">Referência: ' + token + '</p></div>'])
    return "".join(out)


def plan(state, now):
    if not state["pending"]:
        return []
    if refresh_due(state, now):
        raise ValueError("Cache de assinantes vencido; atualizar antes do envio")
    checked = state.get("unsubscribes_checked_at")
    if not checked or instant(now) - instant(checked) > timedelta(hours=1):
        raise ValueError("Verificar descadastros antes do envio")
    gmail_checked = state.get("gmail_unsubscribes_checked_at")
    if not gmail_checked or instant(now) - instant(gmail_checked) > timedelta(hours=1):
        raise ValueError("Verificar pedidos de cancelamento no Gmail antes do envio")
    day = instant(now).astimezone(TZ).date().isoformat()
    drafts = []
    for email, contact in sorted(state["subscribers"].items()):
        key = day + ":" + hashlib.sha256(email.encode()).hexdigest()
        if key in state["deliveries"]:  # inclui sending/unknown: reconciliar, nunca reenviar cegamente
            continue
        items = []
        for item in state["pending"].values():
            subscription = contact["subscriptions"].get(item["kind"])
            if not subscription or not allowed(state, email, item["kind"]):
                continue
            confirmed = subscription.get("confirmed_at")
            if confirmed:
                lower = item.get("published_at") or item["new_since"]
                if instant(confirmed) > instant(lower):
                    continue
            items.append(item)
        if not items:
            continue
        items.sort(key=lambda x: (x["kind"], x["key"]))
        token = "radar-digest-" + day + "-" + key.split(":", 1)[1][:16]
        drafts.append({"key": key, "to": email, "subject": "Radar Brasil 2027 — Resumo diário " + day,
                       "token": token, "item_keys": [i["key"] for i in items], "html": digest_html(items, day, token)})
    return drafts


def reserve(state, draft, now):
    if draft["key"] in state["deliveries"]:
        raise ValueError("Destinatário já reservado nesta data")
    state["deliveries"][draft["key"]] = {"status": "sending", "reserved_at": now,
                                          "token": draft["token"], "item_keys": draft["item_keys"]}


def mark_sent(state, key, gmail_id, now):
    if not gmail_id or state["deliveries"][key]["status"] not in ("sending", "unknown"):
        raise ValueError("Envio exige reserva e Gmail ID confirmado")
    state["deliveries"][key].update(status="sent", gmail_id=gmail_id, sent_at=now)


def finish(state, now):
    if any(d["status"] != "sent" for d in state["deliveries"].values()):
        raise ValueError("Há envio incerto; reconciliar antes de encerrar rodada")
    state["pending"] = {}
    state["last_completed_at"] = now


def charge_api(state, now, count):
    month = instant(now).astimezone(TZ).strftime("%Y-%m")
    budget = state["api_budget"]
    used = budget["used"].get(month, 0)
    limit = budget["limits"].get(month, budget["default_limit"])
    if used + count > limit:
        raise ValueError("Orçamento de chamadas esgotado; pausar sem enviar")
    budget["used"][month] = used + count


def private_path(value):
    path = Path(value).resolve()
    root = Path(__file__).resolve().parents[1]
    if path == root or root in path.parents:
        raise ValueError("Estado/plano privado deve ficar fora do repositório público")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--news", required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--publication-times")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    state_path, output_path = private_path(args.state), private_path(args.output)
    state = read(state_path)
    observe(state, read(args.events), read(args.news), args.now, read(args.publication_times) if args.publication_times else None)
    drafts = plan(state, args.now)
    output_path.write_text(json.dumps({"state": state, "drafts": drafts}, ensure_ascii=False, indent=2), encoding="utf-8")
    output_path.chmod(0o600)
    print(json.dumps({"pending_items": len(state["pending"]), "planned_recipients": len(drafts)}))


if __name__ == "__main__":
    main()
