#!/usr/bin/env python3
import json, os, re, subprocess, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE="appB3SvKrUP82i5V7"
T_SUB="tblFNuYxkhT9bNkq8"; T_UNSUB="tblzoncdirWtB0ntL"; T_LED="tblnNdNX5KDhtzPoP"; T_QUEUE="tbl3GXV4vzTj2etFw"
TOKEN=os.environ.get("AIRTABLE_TOKEN","")
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUTOFF="2026-09-28"
if not TOKEN: raise SystemExit("AIRTABLE_TOKEN ausente")

def api(method, table, payload=None):
    url=f"https://api.airtable.com/v0/{BASE}/{table}"
    data=None
    if payload is not None:
        data=json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,method=method,headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)

def all_records(table):
    out=[]; off=None
    while True:
        q=("?pageSize=100"+("&offset="+urllib.parse.quote(off) if off else ""))
        req=urllib.request.Request(f"https://api.airtable.com/v0/{BASE}/{table}{q}",headers={"Authorization":f"Bearer {TOKEN}"})
        with urllib.request.urlopen(req,timeout=30) as r: d=json.load(r)
        out += d.get("records",[])
        off=d.get("offset")
        if not off: return out

def name(v):
    if isinstance(v,dict): return v.get("name","")
    return str(v or "")

def norm(s): return re.sub(r"[^a-z0-9]+","-",str(s or "").lower()).strip("-")

events=json.load(open(os.path.join(ROOT,"dados.json"),encoding="utf-8"))
subs=all_records(T_SUB); unsubs=all_records(T_UNSUB); led=all_records(T_LED); queue=all_records(T_QUEUE)

blocked=set()
for r in unsubs:
    f=r.get("fields",{})
    if name(f.get("Confirmação"))=="Confirmado" or name(f.get("Status")) in ("Confirmado","Processado"):
        e=str(f.get("Email") or "").strip().lower()
        if e: blocked.add(e)

eligible={}
for r in subs:
    f=r.get("fields",{})
    email=str(f.get("Email") or "").strip().lower()
    if not email or email in blocked: continue
    if f.get("Consentimento") is True and name(f.get("Status"))=="Ativo" and name(f.get("Confirmação"))=="Confirmado":
        eligible[email]={"record":r,"confirmed":str(f.get("Confirmado em") or "")}

sent=set()
sent_any=set()
for r in led:
    f=r.get("fields",{})
    if name(f.get("Status"))!="Enviado": continue
    ident=str(f.get("ID evento") or "").strip()
    email=str(f.get("Email") or "").strip().lower()
    if ident:
        sent.add((ident,email))

queued=set()
for r in queue:
    f=r.get("fields",{})
    if name(f.get("Status")) not in ("Pendente","Enviando","Enviado"): continue
    queued.add((str(f.get("Identidade") or ""),str(f.get("Email") or "").lower()))

def first_seen(ident, title):
    # Usa o histórico real do dados.json: primeiro commit em que o item apareceu.
    needles=[x for x in (ident,title) if x]
    for needle in needles:
        try:
            out=subprocess.check_output(
                ["git","log","--reverse","--format=%cI","-S",needle,"--","dados.json"],
                cwd=ROOT,text=True,stderr=subprocess.DEVNULL,timeout=20
            ).strip().splitlines()
            if out: return out[0].strip()
        except Exception:
            pass
    return ""

candidates=[]
for ev in events:
    date=str(ev.get("Data") or "")
    if date and date < CUTOFF: continue
    title=str(ev.get("Titulo") or "").strip()
    if not title: continue
    ident=str(ev.get("ID") or "").strip()
    if not ident:
        ident=norm(title)+"-"+norm(date)+"-"+norm(ev.get("Link") or ev.get("Fonte") or "")
    published=first_seen(ident,title)
    if not published:
        print("skip_without_first_seen="+ident)
        continue

    recipients=[]
    for email,meta in eligible.items():
        if (ident,email) in sent or (ident,email) in queued: continue
        confirmed=meta["confirmed"]
        # Anti-backlog: quem confirmou depois da publicação não recebe item antigo.
        if confirmed and confirmed > published:
            continue
        recipients.append(email)
    if recipients:
        candidates.append((published,date,title,ident,ev,recipients))

if not candidates:
    print("no_pending=true"); raise SystemExit(0)

# Novidade real primeiro: data da primeira publicação no Radar, nunca data futura do evento.
candidates.sort(key=lambda x:(x[0],x[2]),reverse=True)
published,date,title,ident,ev,recipients=candidates[0]
print("selected_item="+ident)
print("selected_first_seen="+published)

records=[]
for email,meta in eligible.items():
    if (ident,email) in sent or (ident,email) in queued: continue
    confirmed=meta["confirmed"]
    # Sem timestamp confiável de publicação no JSON não inventa bloqueio por confirmação.
    key=f"evento:{ident}:{email}"
    loc=" — ".join([x for x in [str(ev.get("Local") or "").strip(), (str(ev.get("Cidade") or "")+"/"+str(ev.get("UF") or "")).strip("/")] if x])
    body=f"{title}\n\nData: {ev.get('DataBR') or date}\n"
    if ev.get("Hora"): body+=f"Horário: {ev.get('Hora')}\n"
    if loc: body+=f"Local: {loc}\n"
    obs=str(ev.get("Observacoes") or "").strip()
    if obs: body+=f"\n{obs}\n"
    link=str(ev.get("Link") or ev.get("Fonte") or "").strip()
    if link: body+=f"\nFonte: {link}\n"
    body+="Radar: https://radarfutebolfeminino2027.com.br/"
    records.append({"fields":{"Chave":key,"Email":email,"Tipo":"Evento","Identidade":ident,"Título":title,"Assunto":"Radar Brasil 2027 — "+title,"Corpo":body,"Status":"Pendente","Criado em":datetime.now(timezone.utc).isoformat()}})
if not records:
    print("candidate_without_recipients="+ident); raise SystemExit(0)
for i in range(0,len(records),10): api("POST",T_QUEUE,{"records":records[i:i+10],"typecast":True})
print("queued_item="+ident); print("queued_recipients="+str(len(records)))
