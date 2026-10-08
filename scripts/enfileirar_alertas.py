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

# Bloqueio conservador: outras modalidades não devem gerar alertas de futebol.
# Expressões explícitas apenas; não bloquear textos genéricos sobre esporte feminino.
OTHER_SPORTS=re.compile(
    r"\\b(?:v[oô]lei|voleibol|volleyball|basquete|basketball|handebol|handball|"
    r"futsal|beach volleyball|v[oô]lei de praia|gin[aá]stica|nata[cç][aã]o)\\b",
    re.IGNORECASE,
)
FOOTBALL_CONTEXT=re.compile(r"\\b(?:futebol|football|soccer|fifa|cbf)\\b",re.IGNORECASE)

def unrelated_sport_news(item):
    title=str(item.get("Titulo") or "")
    # Título de outra modalidade prevalece sobre rótulos genéricos da curadoria.
    if OTHER_SPORTS.search(title) and not FOOTBALL_CONTEXT.search(title):
        return True
    return False

def load_json(path):
    with open(os.path.join(ROOT,path),encoding="utf-8") as fh: return json.load(fh)

# Verifica os mesmos arquivos públicos carregados pelo frontend antes de enfileirar.
# Falha fechada: erro HTTP, JSON inválido ou item ausente => nenhum novo e-mail.
PUBLIC_SITE=os.environ.get("RADAR_PUBLIC_SITE","https://radarfutebolfeminino2027.com.br").rstrip("/")

def public_items(path):
    url=PUBLIC_SITE+"/"+path
    req=urllib.request.Request(url,headers={"User-Agent":"RadarBrasil2027-alertas/1.0","Cache-Control":"no-cache"})
    with urllib.request.urlopen(req,timeout=20) as response:
        if response.status!=200: raise RuntimeError("public_site_http="+str(response.status))
        data=json.load(response)
    if not isinstance(data,list): raise RuntimeError("public_site_invalid_json="+path)
    return data

def event_identity(ev):
    title=str(ev.get("Titulo") or "").strip()
    date=str(ev.get("Data") or "")
    return str(ev.get("ID") or "").strip() or norm(title)+"-"+norm(date)+"-"+norm(ev.get("Link") or ev.get("Fonte") or "")

def news_identity(item):
    return str(item.get("Link") or "").strip()

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

# O resumo de backlog de 06/10 já comunicou notícias anteriores a esse envio.
# Não reabrir alertas individuais antigos para os destinatários do resumo.
backlog_news_cutoff={}
for r in queue:
    f=r.get("fields",{})
    if name(f.get("Tipo"))!="Notícia" or name(f.get("Status"))!="Enviado":
        continue
    ident=str(f.get("Identidade") or "").strip()
    key=str(f.get("Chave") or "").strip()
    if not (ident.startswith("backlog-") or key.startswith("backlog-")):
        continue
    email=str(f.get("Email") or "").strip().lower()
    sent_at=str(f.get("Criado em") or r.get("createdTime") or "").strip()
    if email and sent_at:
        backlog_news_cutoff[email]=max(backlog_news_cutoff.get(email,""),sent_at)

# Links já incluídos em resumos enviados ou em processamento não voltam
# a ser tratados como notícias individuais.
digest_covered={}
for r in queue:
    fields=r.get("fields",{})
    if str(fields.get("Identidade") or "").startswith("resumo-") and name(fields.get("Status")) in ("Pendente","Enviando","Enviado"):
        email=str(fields.get("Email") or "").strip().lower()
        body=str(fields.get("Corpo") or "")
        digest_covered.setdefault(email,set()).update(re.findall(r"https?://[^\\s]+",body))

queued=set()
for r in queue:
    f=r.get("fields",{})
    if name(f.get("Status")) not in ("Pendente","Enviando","Enviado"): continue
    queued.add((name(f.get("Tipo")),str(f.get("Identidade") or "").strip(),str(f.get("Email") or "").strip().lower()))

# Gate de publicação: arquivos do site, não apenas conteúdo local do GitHub.
# Consultas HTTP públicas não consomem API do Airtable.
try:
    live_events=public_items("dados.json")
    live_news=public_items("noticias.json")
except Exception as exc:
    raise SystemExit("public_site_unavailable_no_enqueue="+str(exc))
published_events={event_identity(e) for e in live_events if isinstance(e,dict)}
published_news={news_identity(n) for n in live_news if isinstance(n,dict)}
print("public_site_events="+str(len(published_events)))
print("public_site_news="+str(len(published_news)))

candidates=[]

for ev in load_json("dados.json"):
    date=str(ev.get("Data") or "")
    if date and date < CUTOFF: continue
    title=str(ev.get("Titulo") or "").strip()
    if not title: continue
    ident=event_identity(ev)
    if ident not in published_events:
        print("skipped_not_on_site_event="+ident)
        continue
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
    if unrelated_sport_news(news):
        print("skipped_unrelated_sport="+title)
        continue
    ident=link
    if ident not in published_news:
        print("skipped_not_on_site_news="+ident)
        continue
    published=first_seen("noticias.json",[link,title])
    if not published: continue
    recipients=[]
    for email,meta in news_subs.items():
        # Conteúdo anterior ao resumo já foi comunicado em lote.
        if email in backlog_news_cutoff:
            cutoff=backlog_news_cutoff[email]
            if datetime.fromisoformat(published.replace("Z","+00:00")) <= datetime.fromisoformat(cutoff.replace("Z","+00:00")):
                continue
        if link in digest_covered.get(email,set()): continue
        if (link,email) in sent_news or ("Notícia",ident,email) in queued: continue
        confirmed=meta["confirmed"]
        if confirmed and confirmed > published: continue
        recipients.append(email)
    if recipients:
        candidates.append((published,"Notícia",date,title,ident,news,recipients))

# Recuperação em lote: um único resumo por assinante, não um e-mail por notícia.
# A identidade determinística impede reenvio do mesmo conjunto após a primeira fila.
news_candidates=[c for c in candidates if c[1]=="Notícia"]
if len(news_candidates)>1:
    by_email={}
    for c in news_candidates:
        for email in c[6]:
            by_email.setdefault(email,[]).append(c)
    digest_records=[]
    for email,items in by_email.items():
        items.sort(key=lambda c:(c[0],c[3]),reverse=True)
        # Uma identidade estável por conjunto; não repetir conjuntos já enfileirados.
        import hashlib
        digest_id="resumo-"+hashlib.sha256(("\\n".join(sorted(c[4] for c in items))).encode()).hexdigest()[:24]
        if ("Notícia",digest_id,email) in queued:
            continue
        lines=["Resumo de notícias do Radar Brasil 2027","",f"{len(items)} notícias ainda não enviadas individualmente:",""]
        for c in items:
            lines.extend(["• "+c[3],c[4],""])
        lines.append("Radar: https://radarfutebolfeminino2027.com.br/")
        digest_records.append({"fields":{
            "Chave":"noticia:"+digest_id+":"+email,"Email":email,"Tipo":"Notícia",
            "Identidade":digest_id,"Título":"Resumo de notícias pendentes",
            "Assunto":"Radar Brasil 2027 — resumo de notícias pendentes",
            "Corpo":"\\n".join(lines),"Status":"Pendente",
            "Criado em":datetime.now(timezone.utc).isoformat()
        }})
    if digest_records:
        for i in range(0,len(digest_records),10):
            api("POST",T_QUEUE,{"records":digest_records[i:i+10],"typecast":True})
        print("digest_queued_recipients="+str(len(digest_records)))
        print("digest_unique_news="+str(len({c[4] for c in news_candidates})))
        raise SystemExit(0)
    # Não voltar a enfileirar os mesmos itens individualmente.
    candidates=[c for c in candidates if c[1]!="Notícia"]

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
