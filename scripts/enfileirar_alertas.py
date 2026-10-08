#!/usr/bin/env python3
import json, os, re, subprocess, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE="appB3SvKrUP82i5V7"
T_EVENT_SUB="tblFNuYxkhT9bNkq8"; T_NEWS_SUB="tblZFVMQAdxXkenaS"
T_UNSUB="tblzoncdirWtB0ntL"; T_EVENT_LED="tblnNdNX5KDhtzPoP"; T_NEWS_LED="tbloZ3eNgHf8Yg6qE"
T_QUEUE="tbl3GXV4vzTj2etFw"
TOKEN=os.environ.get("AIRTABLE_TOKEN","")
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUTOFF="2026-09-28"
if not TOKEN: raise SystemExit("AIRTABLE_TOKEN ausente")

def api(method, table, payload=None):
    url=f"https://api.airtable.com/v0/{BASE}/{table}"
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request(url,data=data,method=method,headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)

def all_records(table):
    out=[]; off=None
    while True:
        q="?pageSize=100"+("&offset="+urllib.parse.quote(off) if off else "")
        req=urllib.request.Request(f"https://api.airtable.com/v0/{BASE}/{table}{q}",headers={"Authorization":f"Bearer {TOKEN}"})
        with urllib.request.urlopen(req,timeout=30) as r: d=json.load(r)
        out += d.get("records",[]); off=d.get("offset")
        if not off: return out

def name(v):
    return v.get("name","") if isinstance(v,dict) else str(v or "")

def norm(s):
    return re.sub(r"[^a-z0-9]+","-",str(s or "").lower()).strip("-")

def load_json(path):
    with open(os.path.join(ROOT,path),encoding="utf-8") as fh: return json.load(fh)

def first_seen(path, needles):
    for needle in [str(x or "").strip() for x in needles if str(x or "").strip()]:
        try:
            out=subprocess.check_output(
                ["git","log","--reverse","--format=%cI","-S",needle,"--",path],
                cwd=ROOT,text=True,stderr=subprocess.DEVNULL,timeout=20
            ).strip().splitlines()
            if out: return out[0].strip()
        except Exception:
            pass
    return ""

def subscriber_map(rows, blocked):
    out={}
    for r in rows:
        f=r.get("fields",{})
        email=str(f.get("E-mail") or "").strip().lower()
        if not email or email in blocked: continue
        if f.get("Consentimento") is True and name(f.get("Status"))=="Ativo" and name(f.get("Confirmação"))=="Confirmado":
            out[email]={"confirmed":str(f.get("Confirmado em") or "")}
    return out

unsubs=all_records(T_UNSUB)
blocked=set()
for r in unsubs:
    f=r.get("fields",{})
    if name(f.get("Confirmação"))=="Confirmado" or name(f.get("Status")) in ("Confirmado","Processado"):
        email=str(f.get("E-mail") or "").strip().lower()
        if email: blocked.add(email)

event_subs=subscriber_map(all_records(T_EVENT_SUB),blocked)
news_subs=subscriber_map(all_records(T_NEWS_SUB),blocked)
event_led=all_records(T_EVENT_LED); news_led=all_records(T_NEWS_LED); queue=all_records(T_QUEUE)

sent_event=set()
for r in event_led:
    f=r.get("fields",{})
    if name(f.get("Status"))=="Enviado":
        ident=str(f.get("ID do evento") or "").strip()
        email=str(f.get("E-mail") or "").strip().lower()
        if ident and email: sent_event.add((ident,email))

sent_news=set()
for r in news_led:
    f=r.get("fields",{})
    if name(f.get("Status"))=="Enviado":
        link=str(f.get("Link da notícia") or "").strip()
        email=str(f.get("E-mail") or "").strip().lower()
        if link and email: sent_news.add((link,email))

queued=set()
for r in queue:
    f=r.get("fields",{})
    if name(f.get("Status")) not in ("Pendente","Enviando","Enviado"): continue
    queued.add((name(f.get("Tipo")),str(f.get("Identidade") or "").strip(),str(f.get("Email") or "").strip().lower()))

candidates=[]

for ev in load_json("dados.json"):
    date=str(ev.get("Data") or "")
    if date and date < CUTOFF: continue
    title=str(ev.get("Titulo") or "").strip()
    if not title: continue
    ident=str(ev.get("ID") or "").strip() or norm(title)+"-"+norm(date)+"-"+norm(ev.get("Link") or ev.get("Fonte") or "")
    published=first_seen("dados.json",[ident,title])
    if not published: continue
    recipients=[]
    for email,meta in event_subs.items():
        if (ident,email) in sent_event or ("Evento",ident,email) in queued: continue
        confirmed=meta["confirmed"]
        if confirmed and confirmed > published: continue
        recipients.append(email)
    if recipients:
        candidates.append((published,"Evento",date,title,ident,ev,recipients))

for news in load_json("noticias.json"):
    date=str(news.get("Data") or "")
    if date and date < CUTOFF: continue
    title=str(news.get("Titulo") or "").strip()
    link=str(news.get("Link") or "").strip()
    if not title or not link: continue
    ident=link
    published=first_seen("noticias.json",[link,title])
    if not published: continue
    recipients=[]
    for email,meta in news_subs.items():
        if (link,email) in sent_news or ("Notícia",ident,email) in queued: continue
        confirmed=meta["confirmed"]
        if confirmed and confirmed > published: continue
        recipients.append(email)
    if recipients:
        candidates.append((published,"Notícia",date,title,ident,news,recipients))

if not candidates:
    print("no_pending=true"); raise SystemExit(0)

# Um único item por rodada, entre eventos e notícias, sempre pela novidade real.
candidates.sort(key=lambda x:(x[0],x[3]),reverse=True)
published,kind,date,title,ident,item,recipients=candidates[0]
print("selected_type="+kind)
print("selected_item="+ident)
print("selected_first_seen="+published)

records=[]
for email in recipients:
    key=("evento:" if kind=="Evento" else "noticia:")+ident+":"+email
    if kind=="Evento":
        loc=" — ".join([x for x in [str(item.get("Local") or "").strip(),(str(item.get("Cidade") or "")+"/"+str(item.get("UF") or "")).strip("/")] if x])
        body=f"{title}\n\nData: {item.get('DataBR') or date}\n"
        if item.get("Hora"): body+=f"Horário: {item.get('Hora')}\n"
        if loc: body+=f"Local: {loc}\n"
        obs=str(item.get("Observacoes") or "").strip()
        if obs: body+=f"\n{obs}\n"
        link=str(item.get("Link") or item.get("Fonte") or "").strip()
        if link: body+=f"\nFonte: {link}\n"
    else:
        summary=str(item.get("Resumo") or "").strip()
        body=f"{title}\n\n"
        if summary: body+=summary+"\n\n"
        vehicle=str(item.get("Veiculo") or "").strip()
        if vehicle: body+=f"Fonte: {vehicle}\n"
        body+=f"Leia mais: {ident}\n"
    body+="\nRadar: https://radarfutebolfeminino2027.com.br/"
    records.append({"fields":{
        "Chave":key,"Email":email,"Tipo":kind,"Identidade":ident,"Título":title,
        "Assunto":"Radar Brasil 2027 — "+title,"Corpo":body,"Status":"Pendente",
        "Criado em":datetime.now(timezone.utc).isoformat()
    }})

for i in range(0,len(records),10):
    api("POST",T_QUEUE,{"records":records[i:i+10],"typecast":True})
print("queued_type="+kind)
print("queued_item="+ident)
print("queued_recipients="+str(len(records)))
