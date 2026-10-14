#!/usr/bin/env python3
"""Concilia sugestões Airtable uma vez por dia, sem tocar na pesquisa pública horária.

Orçamento hard-stop: duas leituras (uma por tabela) e até quatro atualizações
por execução. Nunca pesquisa fontes públicas em lote nem envia e-mails.
"""
import importlib.util
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "editorial" / "sugestoes-diarias-status.json"
MAX_PATCHES = 4
BRT = ZoneInfo("America/Sao_Paulo")
today = datetime.now(BRT).date()

if os.environ.get("RADAR_PUBLIC_ONLY") == "1" or os.environ.get("RADAR_AIRTABLE_ALLOW") != "1":
    raise SystemExit("bloqueado: autorização exclusiva do leitor diário ausente")
if not os.environ.get("AIRTABLE_TOKEN", "").strip():
    raise SystemExit("bloqueado: AIRTABLE_TOKEN ausente")

# Commit do status impede nova leitura no mesmo dia, inclusive em reruns.
if STATUS_PATH.exists():
    previous = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    if previous.get("stage") == "completed" and str(previous.get("started_at", ""))[:10] == today.isoformat():
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
patches = 0
selected = 0

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
    title = str(pe.first(fields, "Evento sugerido", "Título ou assunto", "Título", "Titulo")).strip()
    link = str(pe.first(fields, "Fonte ou link", "Link", "URL")).strip()
    if title and link:
        return ("PENDENTE_VERIFICACAO: a sugestão possui título e fonte, mas não "
                "passou nas verificações automáticas; revisão editorial necessária.")
    return ""

pe.pending_enrichment_reason = pending_instead_of_silent_reject

def daily_read(table_id):
    global selected
    records = original_read(table_id)  # 1 GET; falha fechada se houver paginação.
    records.sort(key=lambda x: x.get("createdTime", ""), reverse=True)
    ready = []
    is_events = table_id == pe.TABLE_EVENTS
    for record in records:
        if selected >= MAX_PATCHES:
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
        published = (identity in event_ids) if is_events else (bool(link) and link in news_links)
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
            continue
        if duplicated:
            limited_patch(table_id, rid, {
                "Status": "Duplicado",
                "Resultado da verificação": "DUPLICATA_COMPROVADA: link já consta no Radar.",
                "Última verificação": pe.iso()
            })
            selected += 1
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
                continue
        # O núcleo ainda aplica o validador editorial v5.5 antes de enfileirar.
        ready.append(record)
        selected += 1
    print(f"sugestoes_diarias_tabela={table_id}|lidas={len(records)}|selecionadas={len(ready)}")
    return ready

pe.airtable_read = daily_read
result = pe.main()
print(f"sugestoes_diarias_patches={patches}|maximo={MAX_PATCHES}|selecionados={selected}")
raise SystemExit(result)
