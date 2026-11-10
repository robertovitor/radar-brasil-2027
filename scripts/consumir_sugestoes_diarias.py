#!/usr/bin/env python3
"""Concilia sugestões Airtable uma vez por dia, sem tocar na pesquisa pública horária.

Orçamento hard-stop: duas leituras (uma por tabela) e até quatro atualizações
por execução. Nunca pesquisa fontes públicas em lote nem envia e-mails.
"""
import importlib.util
import json
import os
import html
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "editorial" / "sugestoes-diarias-status.json"
MAX_PATCHES = 4
MAX_RECORDS_PER_TABLE = {"eventos": 1, "noticias": 3}  # reserva 1 evento e até 3 notícias
APPROVALS_PATH = ROOT / "editorial" / "aprovacoes-manuais.json"
APPROVALS = json.loads(APPROVALS_PATH.read_text(encoding="utf-8")) if APPROVALS_PATH.exists() else {"items": []}
MANUAL_APPROVALS = {(" ".join(str(title).casefold().split()), str(x.get("kind", ""))) for x in APPROVALS.get("items", []) if x.get("decision") == "approved_by_editor" for title in [x.get("title", ""), *x.get("aliases", [])]}
BRT = ZoneInfo("America/Sao_Paulo")
today = datetime.now(BRT).date()

if os.environ.get("RADAR_PUBLIC_ONLY") == "1" or os.environ.get("RADAR_AIRTABLE_ALLOW") != "1":
    raise SystemExit("bloqueado: autorização exclusiva do leitor diário ausente")
if not os.environ.get("AIRTABLE_TOKEN", "").strip():
    raise SystemExit("bloqueado: AIRTABLE_TOKEN ausente")

# Commit do status impede nova leitura no mesmo dia, inclusive em reruns.
if STATUS_PATH.exists():
    previous = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    same_day_done = previous.get("stage") == "completed" and str(previous.get("started_at", ""))[:10] == today.isoformat()
    retry_requested = os.environ.get("RADAR_SUGGESTIONS_RETRY") == "1"
    previous_had_no_publications = int(previous.get("aprovados_novos", 0) or 0) == 0
    if same_day_done and not (retry_requested and previous_had_no_publications):
        print("suggestions_daily_already_completed=true")
        raise SystemExit(0)

spec = importlib.util.spec_from_file_location(
    "radar_editorial_v55", ROOT / "scripts" / "pesquisa_editorial_compat_v5_5.py"
)
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)
pe = compat.pe
pe.STATUS = STATUS_PATH

# Nunca duplicar a pesquisa pública de :45 nem alterar sua telemetria.
pe.public_research = lambda keys: (0, [], 0, 0, [])

original_read = pe.airtable_read
original_patch = pe.airtable_patch
original_pending = pe.pending_enrichment_reason
original_candidate = pe.candidate_from_record
patches = 0
selected = 0

# O título editorial é extraído da página vinculada à sugestão. Os formulários
# podem trazer somente o link; não se deve exigir que o visitante repita o título.
_SOURCE_TITLE_CACHE = {}

def source_title(fields, kind):
    link = str(pe.first(fields, "Fonte ou link", "Link", "URL")).strip()
    if not link:
        return ""
    key = pe.urlnorm(link) or link
    if key in _SOURCE_TITLE_CACHE:
        return _SOURCE_TITLE_CACHE[key]
    title = ""
    try:
        parsed = urllib.parse.urlparse(link)
        host = (parsed.hostname or "").casefold().removeprefix("www.")
        social = host in ("instagram.com", "facebook.com", "tiktok.com")
        if parsed.scheme != "https" or not parsed.hostname or (not social and not pe.trusted_url(link)):
            return ""
        data, final_url, headers = pe.request_bytes(
            link,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RadarBrasil2027/3.2)",
                     "Accept": "text/html,application/xhtml+xml"},
            timeout=12,
        )
        final = urllib.parse.urlparse(final_url)
        final_host = (final.hostname or "").casefold().removeprefix("www.")
        if final.scheme != "https" or not final.hostname or (not social and not pe.trusted_url(final_url)):
            return ""
        if social and final_host not in ("instagram.com", "facebook.com", "tiktok.com"):
            return ""
        raw = data[:1000000].decode("utf-8", "ignore")
        metas = {}
        for tag in re.findall(r"<meta\b[^>]*>", raw, flags=re.I):
            attrs = {k.casefold(): html.unescape(v) for k, q, v in re.findall(
                r"([\w:-]+)\s*=\s*([\"\'])(.*?)\2", tag, flags=re.S)}
            name = attrs.get("property", attrs.get("name", "")).casefold()
            if name in ("og:title", "twitter:title", "title", "og:site_name"):
                metas[name] = attrs.get("content", "")
        match = re.search(r"<title\b[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
        title = metas.get("og:title") or metas.get("twitter:title") or (match.group(1) if match else "")
        title = html.unescape(re.sub(r"<[^>]+>", " ", title))
        title = re.sub(r"\s+", " ", title).strip(" -|•")
        if not title or title.casefold() in ("instagram", "facebook", "tiktok"):
            # Redes sociais podem expor a manchete/legenda somente nos metadados
            # de descrição ou no JSON incorporado.
            if (final.hostname or "").casefold().removeprefix("www.") in (
                "instagram.com", "facebook.com", "tiktok.com"
            ):
                caption = compat._social_page_details(link)
                if caption:
                    chunks = re.split(r"(?<=[.!?])\s+|\n", caption)
                    title = next((x.strip() for x in chunks if len(x.strip()) >= 18), caption[:180].strip())
        if title and title.casefold() not in ("instagram", "facebook", "tiktok"):
            title = title[:260]
    except Exception as exc:
        print(f"suggestion_source_title_unavailable={type(exc).__name__}")
        title = ""
    _SOURCE_TITLE_CACHE[key] = title
    print(f"suggestion_source_title={'ok' if title else 'missing'}|kind={kind}")
    return title

def resolve_suggestion_title(fields, kind):
    title = str(pe.first(fields, "Evento sugerido", "Título ou assunto", "Título", "Titulo")).strip()
    if not title:
        title = source_title(fields, kind)
    if not title:
        return ""
    normalized = pe.norm(title)
    # Associa uma manchete extraída à aprovação humana somente por correspondência
    # textual clara; não atribui aprovação a uma sugestão sem relação.
    for approval in APPROVALS.get("items", []):
        if approval.get("decision") != "approved_by_editor" or approval.get("kind") != kind:
            continue
        canonical = str(approval.get("title", "")).strip()
        variants = [canonical, *approval.get("aliases", [])]
        for variant in variants:
            v = pe.norm(variant)
            tokens = [t for t in v.split() if len(t) >= 4]
            if v and (v in normalized or (len(tokens) >= 2 and sum(t in normalized for t in tokens) >= max(2, len(tokens)-1))):
                return canonical
            if v == "convocacao" and re.search(r"convocad[ao]|convoca[cç][aã]o", normalized):
                return canonical
    return title

def candidate_with_source_title(record, kind):
    copied = dict(record)
    fields = dict(copied.get("fields", {}) or {})
    resolved = resolve_suggestion_title(fields, kind)
    raw_title = source_title(fields, kind) if not str(pe.first(fields, "Evento sugerido", "Título ou assunto", "Título", "Titulo")).strip() else str(pe.first(fields, "Evento sugerido", "Título ou assunto", "Título", "Titulo")).strip()
    if resolved:
        # O validador compara o título com a própria página. Preserva a manchete
        # extraída da fonte quando ela corresponde a uma aprovação manual.
        approved = any(
            x.get("decision") == "approved_by_editor" and x.get("kind") == kind
            and " ".join(str(x.get("title", "")).casefold().split()) == " ".join(resolved.casefold().split())
            for x in APPROVALS.get("items", [])
        )
        title = raw_title if approved and raw_title else resolved
        fields["Título"] = title
        fields["Evento sugerido"] = title
        fields["Título ou assunto"] = title
        link = str(pe.first(fields, "Fonte ou link", "Link", "URL")).strip()
        host = (urllib.parse.urlparse(link).hostname or "").casefold().removeprefix("www.")
        if approved and host in ("instagram.com", "facebook.com", "tiktok.com"):
            pe.TRUSTED_DOMAINS = tuple(dict.fromkeys(tuple(pe.TRUSTED_DOMAINS) + (host,)))
    copied["fields"] = fields
    return original_candidate(copied, kind)

pe.candidate_from_record = candidate_with_source_title

published_events = pe.load(ROOT / "dados.json", [])
published_news = pe.load(ROOT / "noticias.json", [])
event_ids = {str(x.get("ID", "")) for x in published_events if isinstance(x, dict)}
event_links = {pe.urlnorm(x.get("Link")) for x in published_events if isinstance(x, dict) and x.get("Link")}
news_links = {pe.urlnorm(x.get("Link")) for x in published_news if isinstance(x, dict) and x.get("Link")}

def limited_patch(table_id, record_id, fields):
    global patches
    if not fields:
        return
    if patches >= MAX_PATCHES:
        raise RuntimeError("orçamento de até quatro escritas no Airtable excedido")
    original_patch(table_id, record_id, fields)
    patches += 1

pe.airtable_patch = limited_patch

def pending_instead_of_silent_reject(fields, kind):
    reason = original_pending(fields, kind)
    if reason:
        return reason
    title = resolve_suggestion_title(fields, kind)
    link = str(pe.first(fields, "Fonte ou link", "Link", "URL")).strip()
    if title and link:
        return ("PENDENTE_VERIFICACAO: a sugestão possui título e fonte, mas não "
                "passou nas verificações automáticas; revisão editorial necessária.")
    return ""

pe.pending_enrichment_reason = pending_instead_of_silent_reject

def daily_read(table_id):
    global selected
    records = original_read(table_id)  # 1 GET; falha fechada se houver paginação.
    is_events = table_id == pe.TABLE_EVENTS
    kind = "eventos" if is_events else "noticias"
    def priority(record):
        fields = record.get("fields", {})
        title = " ".join(resolve_suggestion_title(fields, kind).casefold().split())
        return (0 if (title, kind) in MANUAL_APPROVALS else 1, record.get("createdTime", ""))
    # Registros com aprovação humana explícita entram primeiro, sem dispensar
    # validação de data, duplicidade, integridade dos campos ou publicação.
    records.sort(key=priority)
    ready = []
    table_selected = 0
    for record in records:
        if table_selected >= MAX_RECORDS_PER_TABLE[kind] or selected >= MAX_PATCHES:
            break
        fields = record.setdefault("fields", {})
        # O Airtable omite campos vazios no JSON; sem isto o núcleo não salva Status.
        fields.setdefault("Status", "")
        fields.setdefault("Resultado da verificação", "")
        fields.setdefault("Última verificação", "")
        if not pe.processable(fields):
            continue
        rid = record.get("id", "")
        link = pe.urlnorm(pe.first(fields, "Fonte ou link", "Link", "URL"))
        identity = "SUG-" + rid
        resolved_title = resolve_suggestion_title(fields, kind)
        if is_events:
            published = identity in event_ids
        else:
            title_key = pe.norm(resolved_title)
            published = bool(link and link in news_links) or bool(title_key and any(
                pe.norm(item.get("Titulo", "")) == title_key
                or (len([t for t in title_key.split() if len(t) >= 4]) >= 1
                    and sum(t in pe.norm(item.get("Titulo", "")) for t in title_key.split() if len(t) >= 4)
                    >= max(1, len([t for t in title_key.split() if len(t) >= 4]) - 1))
                for item in published_news
                if str(item.get("Data", "")) >= "2026-10-01"
            ))
        duplicated = bool(link) and (link in event_links if is_events else link in news_links)
        if published:
            included_field = "Incluído no Radar" if is_events else "Publicada no Radar"
            if not fields.get(included_field) or pe.norm(fields.get("Status")) != "aprovado":
                limited_patch(table_id, rid, {
                    "Status": "Aprovado", included_field: True,
                    "Resultado da verificação": "RECONCILIADO: já publicado no Radar.",
                    "Última verificação": pe.iso()
                })
                selected += 1
            table_selected += 1
            continue
        if duplicated:
            limited_patch(table_id, rid, {
                "Status": "Duplicado",
                "Resultado da verificação": "DUPLICATA_COMPROVADA: link já consta no Radar.",
                "Última verificação": pe.iso()
            })
            selected += 1
            table_selected += 1
            continue
        # Eventos antigos não devem voltar como novidade; nunca republicá-los.
        if is_events:
            raw = str(pe.first(fields, "Data informada", "Data", "Data do evento")).strip()[:10]
            event_date = None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    event_date = datetime.strptime(raw, fmt).date()
                    break
                except ValueError:
                    continue
            if event_date and event_date < today:
                limited_patch(table_id, rid, {
                    "Status": "Recusado",
                    "Resultado da verificação": "Evento com data encerrada; não publicar como novidade.",
                    "Última verificação": pe.iso()
                })
                selected += 1
                table_selected += 1
                continue
        # O núcleo ainda aplica o validador editorial v5.5 antes de enfileirar.
        ready.append(record)
        selected += 1
        table_selected += 1
    print(f"sugestoes_diarias_tabela={table_id}|lidas={len(records)}|selecionadas={len(ready)}")
    return ready

pe.airtable_read = daily_read
result = pe.main()
print(f"sugestoes_diarias_patches={patches}|maximo={MAX_PATCHES}|selecionados={selected}")
raise SystemExit(result)
