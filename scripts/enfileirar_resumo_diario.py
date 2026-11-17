#!/usr/bin/env python3
"""Enfileira um único resumo diário por assinante na fila Gmail já ativa.
Faz quatro leituras Airtable (duas listas de assinantes, descadastros e fila do dia).
Não grava endereços no GitHub nem imprime dados pessoais.
"""
import hashlib, json, os, re, subprocess, urllib.parse, urllib.request
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

BASE = "appB3SvKrUP82i5V7"
T_EVENTS = "tblFNuYxkhT9bNkq8"
T_NEWS = "tblZFVMQAdxXkenaS"
T_UNSUB = "tblzoncdirWtB0ntL"
T_QUEUE = "tbl3GXV4vzTj2etFw"
SITE = os.environ.get("RADAR_PUBLIC_SITE", "https://radarfutebolfeminino2027.com.br").rstrip("/")
TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
TZ = ZoneInfo("America/Sao_Paulo")
API_READS = 0
API_WRITES = 0


def api(method, table, params=None, payload=None):
    global API_READS, API_WRITES
    if not TOKEN:
        raise RuntimeError("AIRTABLE_TOKEN ausente")
    url = f"https://api.airtable.com/v0/{BASE}/{table}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"
    })
    if method == "GET":
        API_READS += 1
    else:
        API_WRITES += 1
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def records(table, formula, fields):
    result, offset = [], None
    while True:
        params = [("pageSize", "100"), ("filterByFormula", formula)]
        params.extend(("fields[]", field) for field in fields)
        if offset:
            params.append(("offset", offset))
        page = api("GET", table, params=params)
        result.extend(page.get("records", []))
        offset = page.get("offset")
        if not offset:
            return result


def public_json(path):
    req = urllib.request.Request(f"{SITE}/{path}", headers={
        "User-Agent": "RadarBrasil2027-digest/1.0", "Cache-Control": "no-cache"
    })
    with urllib.request.urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"site_http_{response.status}_{path}")
        data = json.load(response)
    if not isinstance(data, list):
        raise RuntimeError(f"site_json_invalido_{path}")
    return data


def label(value):
    return value.get("name", "") if isinstance(value, dict) else str(value or "")


def valid_email(value):
    value = str(value or "").strip().lower()
    return value if re.fullmatch(r"[^\\s<>@,;]+@[^\\s<>@,;]+\\.[^\\s<>@,;]+", value) else ""


def utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def first_seen(path, needles):
    for needle in (str(x or "").strip() for x in needles):
        if not needle:
            continue
        try:
            found = subprocess.check_output(
                ["git", "log", "--reverse", "--format=%cI", "-S", needle, "--", path],
                text=True, stderr=subprocess.DEVNULL, timeout=20
            ).strip().splitlines()
            if found:
                return utc(found[0])
        except Exception:
            pass
    return None


def event_id(item):
    value = str(item.get("ID") or "").strip()
    if value:
        return value
    raw = "|".join(str(item.get(k) or "").strip().lower() for k in ("Titulo", "Data", "Link", "Fonte"))
    return hashlib.sha256(raw.encode()).hexdigest()


def event_end_of_day(item):
    raw = str(item.get("Data") or item.get("DataBR") or "").strip()
    try:
        day = date.fromisoformat(raw[:10])
    except ValueError:
        try:
            day = datetime.strptime(raw[:10], "%d/%m/%Y").date()
        except ValueError:
            return None
    hour = str(item.get("Hora") or "").strip()
    match = re.search(r"(\\d{1,2})[:hH](\\d{2})", hour)
    if match:
        try:
            return datetime.combine(day, time(int(match.group(1)), int(match.group(2))), TZ)
        except ValueError:
            pass
    # Sem horário publicado, mantém o evento elegível até o fim da data informada.
    return datetime.combine(day, time(23, 59, 59), TZ)


def subscribers(table, topic):
    formula = "AND({Consentimento}=1,{Status}='Ativo',{Confirmação}='Confirmado')"
    rows = records(table, formula, ["E-mail", "Consentimento", "Status", "Confirmação", "Confirmado em"])
    result = {}
    for row in rows:
        fields = row.get("fields", {})
        addr = valid_email(fields.get("E-mail"))
        if not addr or fields.get("Consentimento") is not True:
            continue
        if label(fields.get("Status")) != "Ativo" or label(fields.get("Confirmação")) != "Confirmado":
            continue
        result.setdefault(addr, {})[topic] = fields.get("Confirmado em") or "1970-01-01T00:00:00Z"
    return result


def unsubscribes():
    rows = records(T_UNSUB, "{Confirmar descadastro}=1",
                   ["E-mail", "Tipo de mensagem", "Confirmar descadastro", "Status"])
    blocked = {}
    for row in rows:
        fields = row.get("fields", {})
        addr = valid_email(fields.get("E-mail"))
        if not addr or fields.get("Confirmar descadastro") is not True:
            continue
        if label(fields.get("Status")) not in ("Pendente", "Processado"):
            continue
        kind = label(fields.get("Tipo de mensagem")).strip().lower()
        topics = {"events"} if kind == "eventos" else {"news"} if kind == "notícias" else {"events", "news"}
        blocked.setdefault(addr, set()).update(topics)
    return blocked


def queued_today(day_key):
    formula = f"FIND('resumo-{day_key}-',{{Chave}})>0"
    rows = records(T_QUEUE, formula, ["Chave", "Email", "Status"])
    return {(valid_email(r.get("fields", {}).get("Email")),
             str(r.get("fields", {}).get("Chave") or "")) for r in rows}


def digest_body(events, news):
    lines = ["Olá! Este é o resumo diário do Radar Brasil 2027.", ""]
    if news:
        lines += ["NOTÍCIAS", ""]
        for item in news:
            lines.append("• " + str(item.get("Titulo") or "Notícia").strip())
            summary = str(item.get("Resumo") or "").strip()
            if summary:
                lines.append(summary)
            source = str(item.get("Veiculo") or "").strip()
            if source:
                lines.append("Fonte: " + source)
            link = str(item.get("Link") or "").strip()
            if link:
                lines.append("Leia mais: " + link)
            lines.append("")
    if events:
        lines += ["EVENTOS", ""]
        for item in events:
            lines.append("• " + str(item.get("Titulo") or "Evento").strip())
            when = str(item.get("DataBR") or item.get("Data") or "").strip()
            hour = str(item.get("Hora") or "").strip()
            if when:
                lines.append("Data: " + when + ((" às " + hour) if hour else ""))
            place = " — ".join(x for x in (
                str(item.get("Local") or "").strip(),
                "/".join(x for x in (str(item.get("Cidade") or "").strip(),
                                      str(item.get("UF") or "").strip()) if x)
            ) if x)
            if place:
                lines.append("Local: " + place)
            summary = str(item.get("Observacoes") or item.get("Resumo") or "").strip()
            if summary:
                lines.append(summary)
            link = str(item.get("Link") or item.get("Fonte") or "").strip()
            if link:
                lines.append("Fonte: " + link)
            lines.append("")
    lines += ["Acesse o Radar: https://radarfutebolfeminino2027.com.br/",
              "", "Para cancelar uma categoria de avisos, use o formulário de descadastro do Radar."]
    return "\\n".join(lines)


def main():
    since = utc(os.environ.get("RADAR_SINCE", "2026-11-06T19:08:15Z"))
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(TZ)
    day_key = local_now.date().isoformat()

    event_subs = subscribers(T_EVENTS, "events")
    news_subs = subscribers(T_NEWS, "news")
    blocked = unsubscribes()
    audience = {}
    for source in (event_subs, news_subs):
        for addr, topics in source.items():
            audience.setdefault(addr, {}).update(topics)
    for addr, topics in blocked.items():
        if addr in audience:
            for topic in topics:
                audience[addr].pop(topic, None)

    local_events = json.load(open("dados.json", encoding="utf-8"))
    local_news = json.load(open("noticias.json", encoding="utf-8"))
    live_events = {event_id(x) for x in public_json("dados.json") if isinstance(x, dict)}
    live_news = {str(x.get("Link") or "").strip() for x in public_json("noticias.json")
                 if isinstance(x, dict)}

    new_events, new_news = [], []
    for item in local_events:
        if not isinstance(item, dict) or event_id(item) not in live_events:
            continue
        title = str(item.get("Titulo") or "").strip()
        event_end = event_end_of_day(item)
        if not title or not event_end or event_end < local_now:
            continue
        published = first_seen("dados.json", [str(item.get("ID") or ""), title])
        if published and since < published <= now:
            item = dict(item)
            item["_published_at"] = published.isoformat()
            new_events.append(item)

    for item in local_news:
        if not isinstance(item, dict):
            continue
        link = str(item.get("Link") or "").strip()
        title = str(item.get("Titulo") or "").strip()
        if not link or link not in live_news or not title:
            continue
        published = first_seen("noticias.json", [link])
        if published and since < published <= now and now - published <= timedelta(hours=72):
            item = dict(item)
            item["_published_at"] = published.isoformat()
            new_news.append(item)

    existing = queued_today(day_key)
    pending = []
    for addr, topics in audience.items():
        events = [x for x in new_events if "events" in topics
                  and utc(topics["events"]) <= utc(x["_published_at"])]
        news = [x for x in new_news if "news" in topics
                and utc(topics["news"]) <= utc(x["_published_at"])]
        if not events and not news:
            continue
        recipient_hash = hashlib.sha256(addr.encode()).hexdigest()[:20]
        key = f"resumo-{day_key}-{recipient_hash}"
        if (addr, key) in existing:
            continue
        subject = "Radar Brasil 2027 — Resumo diário " + local_now.strftime("%d/%m/%Y")
        # A fila aceita apenas Evento/Notícia; o tipo não altera o conteúdo do resumo.
        kind = "Evento" if events and not news else "Notícia"
        pending.append({"fields": {
            "Chave": key, "Email": addr, "Tipo": kind, "Identidade": key,
            "Título": "Resumo diário Radar Brasil 2027", "Assunto": subject,
            "Corpo": digest_body(events, news), "Status": "Pendente",
            "Criado em": now.isoformat()
        }})

    # Um registro por assinante/dia. A automação Gmail ativa faz a entrega.
    for start in range(0, len(pending), 10):
        api("POST", T_QUEUE, payload={"records": pending[start:start + 10], "typecast": True})

    print(json.dumps({
        "since": since.isoformat(), "local_day": day_key,
        "event_subscribers": len(event_subs), "news_subscribers": len(news_subs),
        "eligible_subscribers": len(audience), "new_events": len(new_events),
        "new_news": len(new_news), "daily_digests_queued": len(pending),
        "airtable_reads": API_READS, "airtable_writes": API_WRITES
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
