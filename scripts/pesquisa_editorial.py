#!/usr/bin/env python3
import json, os, pathlib, re, sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
INBOX = ROOT / 'editorial' / 'inbox.json'
STATUS = ROOT / 'editorial' / 'pesquisa-status.json'
BASE = 'appB3SvKrUP82i5V7'
TABLE_EVENTS = 'tblf6qaCTZmKo48m2'
TABLE_NEWS = 'tbl0iuH4F5Hog8gDD'
BRT = timezone(timedelta(hours=-3))
TOKEN = os.environ.get('AIRTABLE_TOKEN','').strip()
UA = 'RadarBrasil2027/1.0 (+https://www.radarcopafeminina2027.com.br/)'


def now(): return datetime.now(BRT)
def iso(dt=None): return (dt or now()).isoformat(timespec='seconds')
def load(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def norm(v):
    return re.sub(r'\s+',' ', re.sub(r'[^a-z0-9]+',' ', str(v or '').casefold())).strip()

def urlnorm(v):
    s=str(v or '').strip().casefold().replace('https://','').replace('http://','')
    return s.removeprefix('www.').rstrip('/')

def request_json(url, method='GET', payload=None):
    headers={'User-Agent':UA}
    if TOKEN: headers['Authorization']=f'Bearer {TOKEN}'
    data=None
    if payload is not None:
        headers['Content-Type']='application/json'
        data=json.dumps(payload).encode('utf-8')
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))

def airtable_read(table_id):
    # Uma única leitura por tabela. pageSize máximo da API REST é 100.
    url=f'https://api.airtable.com/v0/{BASE}/{table_id}?pageSize=100'
    obj=request_json(url)
    if obj.get('offset'):
        raise RuntimeError('Tabela Airtable excede 100 registros; abortado para preservar limite de exatamente 2 leituras.')
    return obj.get('records',[])

def airtable_patch(table_id, record_id, fields):
    if not fields: return
    url=f'https://api.airtable.com/v0/{BASE}/{table_id}/{record_id}'
    request_json(url,'PATCH',{'fields':fields})

def first(fields,*names):
    for n in names:
        if fields.get(n) not in (None,''): return fields.get(n)
    return ''

def processable(fields):
    st=norm(first(fields,'Status','status'))
    return st in ('','pendente','em verificacao','em verificação','aprovado')

def existing_keys():
    keys=set()
    for path in (ROOT/'dados.json', ROOT/'noticias.json', INBOX):
        obj=load(path, [] if path.name!='inbox.json' else {'eventos':[],'noticias':[]})
        items=obj if isinstance(obj,list) else obj.get('eventos',[])+obj.get('noticias',[])
        for x in items:
            if isinstance(x,dict):
                if x.get('Link'): keys.add('u:'+urlnorm(x.get('Link')))
                if x.get('Titulo'): keys.add('t:'+norm(x.get('Titulo')))
    return keys

def candidate_from_record(record, kind):
    f=record.get('fields',{})
    title=str(first(f,'Título','Titulo','Título da notícia','Titulo da noticia','Nome','Evento')).strip()
    link=str(first(f,'Link','URL','Fonte','Link da notícia','Link da noticia')).strip()
    if not title or not link: return None
    if kind=='noticias':
        date=str(first(f,'Data','Data da notícia','Data da noticia')).strip()[:10] or now().date().isoformat()
        return {'Data':date,'DataBR':datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y') if re.fullmatch(r'\d{4}-\d{2}-\d{2}',date) else '',
                'Titulo':title,'Tema':str(first(f,'Tema','Categoria')).strip() or 'Copa Feminina 2027',
                'CidadeUF':str(first(f,'Cidade/UF','CidadeUF','Cidade','Local')).strip() or 'Brasil',
                'Veiculo':str(first(f,'Veículo','Veiculo','Fonte')).strip() or urllib.parse.urlparse(link).netloc,
                'Link':link,'Sentimento':'Neutro','Impacto':str(first(f,'Impacto')).strip() or 'Médio',
                'Resumo':str(first(f,'Resumo','Descrição','Descricao','Observações','Observacoes')).strip()[:1200]}
    date=str(first(f,'Data','Data do evento')).strip()[:10]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date): return None
    city=str(first(f,'Cidade')).strip(); uf=str(first(f,'UF')).strip()
    return {'ID':str(first(f,'ID')).strip() or f"SUG-{record.get('id','')}", 'Titulo':title,'Status':'Planejado','Data':date,
            'DataBR':datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y'),'UF':uf,'Cidade':city,
            'Categoria':str(first(f,'Categoria')).strip() or 'Evento','Organizador':str(first(f,'Organizador')).strip(),
            'Publico':0,'Patrocinador':str(first(f,'Patrocinador')).strip(),'Local':str(first(f,'Local')).strip(),
            'Latitude':None,'Longitude':None,'Link':link,'Observacoes':str(first(f,'Observações','Observacoes','Resumo','Descrição','Descricao')).strip()[:1200],
            'Mes':'','Ano':int(date[:4]),'Regiao':''}

def rss_candidates():
    queries=[
      '"Copa do Mundo Feminina 2027" Brasil',
      '"Copa Feminina 2027" estádio OR mobilidade OR turismo OR voluntariado OR ingressos',
      '"Seleção Brasileira feminina" 2027 FIFA'
    ]
    out=[]
    for q in queries:
        url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q,'hl':'pt-BR','gl':'BR','ceid':'BR:pt-419'})
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA})
            with urllib.request.urlopen(req,timeout=25) as r: root=ET.fromstring(r.read())
            for item in root.findall('.//item')[:12]:
                title=(item.findtext('title') or '').strip(); link=(item.findtext('link') or '').strip(); pub=(item.findtext('pubDate') or '').strip()
                if not title or not link: continue
                txt=norm(title)
                if not any(k in txt for k in ('femin','2027','selecao brasileira')): continue
                out.append((title,link,pub))
        except Exception as e:
            print(f'rss_warning={type(e).__name__}:{e}')
    return out

def main():
    started=now(); cycle=started.strftime('%Y%m%d-%H')
    status={'cycle_id':cycle,'started_at':iso(started),'completed_at':None,'stage':'started','executor':'github-actions-native',
            'airtable_reads_total':0,'airtable_reads':[],'sugestoes_lidas':0,'sugestoes_noticias_lidas':0,
            'candidatos_publicos':0,'aprovados_novos':0,'rejeitados':0,'duplicados':0,'inbox_itens_adicionados':0,
            'inbox_commit_needed':False,'observacoes_operacionais':''}
    inbox=load(INBOX,{'eventos':[],'noticias':[]}); before=json.loads(json.dumps(inbox)); keys=existing_keys()
    try:
        if not TOKEN: raise RuntimeError('AIRTABLE_TOKEN ausente nos GitHub Actions Secrets')
        ev=airtable_read(TABLE_EVENTS); status['airtable_reads_total']+=1; status['airtable_reads'].append({'table':'Sugestões','reads':1})
        nw=airtable_read(TABLE_NEWS); status['airtable_reads_total']+=1; status['airtable_reads'].append({'table':'Sugestões de Notícias','reads':1})
        status['sugestoes_lidas']=len(ev); status['sugestoes_noticias_lidas']=len(nw)

        for table,records,kind in ((TABLE_EVENTS,ev,'eventos'),(TABLE_NEWS,nw,'noticias')):
            for rec in records:
                f=rec.get('fields',{})
                if not processable(f): continue
                cand=candidate_from_record(rec,kind)
                if not cand:
                    status['rejeitados']+=1; continue
                dup=('u:'+urlnorm(cand.get('Link'))) in keys or ('t:'+norm(cand.get('Titulo'))) in keys
                if dup:
                    status['duplicados']+=1
                    continue
                inbox.setdefault(kind,[]).append(cand); keys.add('u:'+urlnorm(cand.get('Link'))); keys.add('t:'+norm(cand.get('Titulo')))
                status['aprovados_novos']+=1
                # Só escreve campos que já existem na tabela, evitando criação acidental de schema.
                upd={}
                if 'Status' in f: upd['Status']='Aprovado'
                if 'Resultado da verificação' in f: upd['Resultado da verificação']='Aprovado pela pesquisa editorial nativa; enfileirado para o Radar.'
                if 'Última verificação' in f: upd['Última verificação']=iso()
                if upd: airtable_patch(table,rec['id'],upd)

        public=rss_candidates(); status['candidatos_publicos']=len(public)
        # Pesquisa pública fica conservadora: apenas contabiliza candidatos. Inclusão automática exige sugestão estruturada/Airtable.
        status['inbox_itens_adicionados']=sum(len(inbox.get(k,[]))-len(before.get(k,[])) for k in ('eventos','noticias'))
        status['inbox_commit_needed']=inbox!=before
        if inbox!=before: dump(INBOX,inbox)
        status['stage']='completed'; status['observacoes_operacionais']='Execução nativa GitHub. Exatamente duas leituras Airtable; pesquisa pública RSS executada de forma conservadora.'
        code=0
    except Exception as e:
        status['stage']='failed'; status['observacoes_operacionais']=f'{type(e).__name__}: {e}'
        code=1
    status['completed_at']=iso(); dump(STATUS,status)
    print(json.dumps(status,ensure_ascii=False))
    return code

if __name__=='__main__':
    raise SystemExit(main())
