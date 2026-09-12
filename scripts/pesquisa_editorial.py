#!/usr/bin/env python3
import html, json, os, pathlib, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
INBOX = ROOT / 'editorial' / 'inbox.json'
STATUS = ROOT / 'editorial' / 'pesquisa-status.json'
BASE = 'appB3SvKrUP82i5V7'
TABLE_EVENTS = 'tblf6qaCTZmKo48m2'
TABLE_NEWS = 'tbl0iuH4F5Hog8gDD'
BRT = timezone(timedelta(hours=-3))
TOKEN = os.environ.get('AIRTABLE_TOKEN','').strip()
UA = 'RadarBrasil2027/1.2 (+https://www.radarcopafeminina2027.com.br/)'

TRUSTED_DOMAINS = (
    'fifa.com','inside.fifa.com','cbf.com.br','gov.br','planalto.gov.br','camara.leg.br','senado.leg.br',
    'agenciabrasil.ebc.com.br','ge.globo.com','globoesporte.globo.com','espn.com.br','cnnbrasil.com.br','uol.com.br',
    'folha.uol.com.br','estadao.com.br','oglobo.globo.com','valor.globo.com','exame.com','lance.com.br','terra.com.br',
    'prefeitura.poa.br','saopaulo.sp.gov.br','prefeitura.sp.gov.br','rio.rj.gov.br','salvador.ba.gov.br','fortaleza.ce.gov.br',
    'recife.pe.gov.br','belohorizonte.mg.gov.br','brasilia.df.gov.br','goias.gov.br','bahia.ba.gov.br','ceara.gov.br',
    'pernambuco.gov.br','mg.gov.br','rs.gov.br','rj.gov.br','es.gov.br','sc.gov.br','pr.gov.br','sp.gov.br'
)

PUBLIC_QUERIES = [
  '"Copa do Mundo Feminina 2027" Brasil',
  '"Copa Feminina 2027" Brasil',
  '"Mundial Feminino 2027" Brasil',
  '"Seleção Brasileira feminina" convocação OR lesão OR transferência OR prêmio OR entrevista',
  '"Seleção Brasileira feminina" Mundial 2027',
  '"Copa Feminina 2027" estádio OR arena OR infraestrutura',
  '"Copa Feminina 2027" mobilidade OR transporte OR aeroporto',
  '"Copa Feminina 2027" turismo OR hotelaria OR hospitalidade',
  '"Copa Feminina 2027" voluntariado OR voluntários',
  '"Copa Feminina 2027" ingressos OR bilhetes',
  '"Copa Feminina 2027" patrocinador OR marca OR ativação',
  '"Copa Feminina 2027" fan zone OR fan festival OR torcida',
  '"Copa Feminina 2027" cidade-sede OR cidades-sede',
  '"futebol feminino" 2027 Brasil FIFA'
]

EXCLUDE_BASE = ('sub-15','sub 15','sub-17','sub 17','sub-20','sub 20','sub-23','sub 23','seleção de base','selecao de base','categoria de base')
RELEVANT_TERMS = (
    'copa feminina','copa do mundo feminina','mundial feminino','futebol feminino','selecao brasileira feminina',
    'seleção brasileira feminina','fifa 2027','2027'
)


def now(): return datetime.now(BRT)
def iso(dt=None): return (dt or now()).isoformat(timespec='seconds')
def load(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def norm(v):
    return re.sub(r'\s+',' ', re.sub(r'[^a-z0-9à-ÿ]+',' ', str(v or '').casefold())).strip()

def urlnorm(v):
    s=str(v or '').strip().casefold().replace('https://','').replace('http://','')
    return s.removeprefix('www.').rstrip('/')

def request_bytes(url, headers=None, timeout=25):
    h={'User-Agent':UA}
    if headers: h.update(headers)
    req=urllib.request.Request(url,headers=h)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read(), r.geturl(), dict(r.headers)

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
    # Exatamente uma leitura por tabela. Nenhuma auditoria faz leitura adicional.
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

def trusted_url(url):
    host=urllib.parse.urlparse(url).netloc.casefold().removeprefix('www.')
    return any(host==d or host.endswith('.'+d) for d in TRUSTED_DOMAINS)

def article_is_relevant(title, text=''):
    blob=norm(f'{title} {text}')
    if any(norm(x) in blob for x in EXCLUDE_BASE): return False
    return any(norm(x) in blob for x in RELEVANT_TERMS)

def clean_html_text(raw):
    raw=re.sub(r'<script\b[^>]*>.*?</script>',' ',raw,flags=re.I|re.S)
    raw=re.sub(r'<style\b[^>]*>.*?</style>',' ',raw,flags=re.I|re.S)
    raw=re.sub(r'<[^>]+>',' ',raw)
    return re.sub(r'\s+',' ',html.unescape(raw)).strip()

def fetch_article_excerpt(url):
    try:
        data,final_url,headers=request_bytes(url,timeout=20)
        ctype=str(headers.get('Content-Type','')).casefold()
        if 'text/html' not in ctype and 'application/xhtml' not in ctype: return '',final_url
        raw=data[:700000].decode('utf-8','ignore')
        return clean_html_text(raw)[:7000], final_url
    except Exception:
        return '',url

def rss_candidates():
    out=[]; seen=set()
    for q in PUBLIC_QUERIES:
        url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q,'hl':'pt-BR','gl':'BR','ceid':'BR:pt-419'})
        try:
            data,_,_=request_bytes(url,timeout=20)
            root=ET.fromstring(data)
            for item in root.findall('.//item')[:15]:
                title=(item.findtext('title') or '').strip(); link=(item.findtext('link') or '').strip(); pub=(item.findtext('pubDate') or '').strip()
                source_el=item.find('source'); source=(source_el.text or '').strip() if source_el is not None else ''
                if not title or not link or not article_is_relevant(title): continue
                k=norm(title)
                if k in seen: continue
                seen.add(k); out.append({'title':title,'url':link,'pub':pub,'source':source,'origin':'google-news'})
        except Exception as e:
            print(f'rss_warning={type(e).__name__}:{e}')
    return out

def gdelt_candidates():
    out=[]; seen=set()
    queries=['"Copa Feminina 2027" OR "Copa do Mundo Feminina 2027"','"Seleção Brasileira feminina"','"futebol feminino" Brasil 2027']
    for q in queries:
        params={'query':q,'mode':'ArtList','maxrecords':'50','format':'json','sort':'HybridRel'}
        url='https://api.gdeltproject.org/api/v2/doc/doc?'+urllib.parse.urlencode(params)
        try:
            data,_,_=request_bytes(url,timeout=25)
            obj=json.loads(data.decode('utf-8','ignore'))
            for a in obj.get('articles',[])[:50]:
                title=str(a.get('title') or '').strip(); link=str(a.get('url') or '').strip()
                if not title or not link or not article_is_relevant(title): continue
                k=urlnorm(link) or norm(title)
                if k in seen: continue
                seen.add(k); out.append({'title':title,'url':link,'pub':str(a.get('seendate') or ''),'source':str(a.get('domain') or ''),'origin':'gdelt'})
        except Exception as e:
            print(f'gdelt_warning={type(e).__name__}:{e}')
    return out

def public_research(keys):
    raw=rss_candidates()+gdelt_candidates()
    dedup=[]; seen_titles=set(); seen_urls=set(); audit=[]
    for c in raw:
        tk=norm(c['title']); uk=urlnorm(c['url'])
        if tk in seen_titles or uk in seen_urls:
            audit.append({'origem':c.get('origin','pesquisa-publica'),'titulo':c.get('title',''),'fonte':c.get('source',''),'url':c.get('url',''),'decisao':'duplicado','motivo':'Duplicado dentro da própria coleta pública.'})
            continue
        seen_titles.add(tk); seen_urls.add(uk); dedup.append(c)

    approved=[]; rejected=0; duplicates=0
    for c in dedup:
        title=c['title']; link=c['url']
        base={'origem':c.get('origin','pesquisa-publica'),'titulo':title,'fonte':c.get('source',''),'url':link}
        if ('u:'+urlnorm(link)) in keys or ('t:'+norm(title)) in keys:
            duplicates+=1
            audit.append({**base,'decisao':'duplicado','motivo':'Já existe em dados.json, noticias.json ou editorial/inbox.json.'})
            continue
        if c['origin']=='google-news':
            rejected+=1
            audit.append({**base,'decisao':'rejeitado','motivo':'Resultado do Google News sem URL editorial direta validável nesta etapa.'})
            continue
        if not trusted_url(link):
            rejected+=1
            audit.append({**base,'decisao':'rejeitado','motivo':'Domínio fora da lista de fontes confiáveis para inclusão automática.'})
            continue
        excerpt,final_url=fetch_article_excerpt(link)
        if final_url and final_url!=link and trusted_url(final_url): link=final_url
        if not excerpt:
            rejected+=1
            audit.append({**base,'url_final':link,'decisao':'rejeitado','motivo':'Não foi possível obter conteúdo textual suficiente da fonte.'})
            continue
        if not article_is_relevant(title,excerpt):
            rejected+=1
            audit.append({**base,'url_final':link,'decisao':'rejeitado','motivo':'Conteúdo sem relevância editorial suficiente ou relacionado a seleção de base.'})
            continue
        date=now().date().isoformat()
        m=re.search(r'(20\d{2})(\d{2})(\d{2})', c.get('pub',''))
        if m: date=f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
        item={'Data':date,'DataBR':datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y'),'Titulo':title,'Tema':'Copa Feminina 2027','CidadeUF':'Brasil','Veiculo':urllib.parse.urlparse(link).netloc.removeprefix('www.'),'Link':link,'Sentimento':'Neutro','Impacto':'Médio','Resumo':excerpt[:900]}
        approved.append(item)
        audit.append({**base,'url_final':link,'decisao':'aprovado','motivo':'Fonte confiável, conteúdo acessível, relevante e não duplicado.'})
        keys.add('u:'+urlnorm(link)); keys.add('t:'+norm(title))
    return len(dedup), approved, rejected, duplicates, audit

def main():
    started=now(); cycle=started.strftime('%Y%m%d-%H')
    status={'cycle_id':cycle,'started_at':iso(started),'completed_at':None,'stage':'started','executor':'github-actions-native','airtable_reads_total':0,'airtable_reads':[],'sugestoes_lidas':0,'sugestoes_noticias_lidas':0,'candidatos_publicos':0,'aprovados_novos':0,'rejeitados':0,'duplicados':0,'inbox_itens_adicionados':0,'inbox_commit_needed':False,'auditoria':[],'observacoes_operacionais':''}
    inbox=load(INBOX,{'eventos':[],'noticias':[]}); before=json.loads(json.dumps(inbox)); keys=existing_keys()
    try:
        if not TOKEN: raise RuntimeError('AIRTABLE_TOKEN ausente nos GitHub Actions Secrets')
        ev=airtable_read(TABLE_EVENTS); status['airtable_reads_total']+=1; status['airtable_reads'].append({'table':'Sugestões','reads':1})
        nw=airtable_read(TABLE_NEWS); status['airtable_reads_total']+=1; status['airtable_reads'].append({'table':'Sugestões de Notícias','reads':1})
        status['sugestoes_lidas']=len(ev); status['sugestoes_noticias_lidas']=len(nw)

        for table,records,kind,table_name in ((TABLE_EVENTS,ev,'eventos','Sugestões'),(TABLE_NEWS,nw,'noticias','Sugestões de Notícias')):
            for rec in records:
                f=rec.get('fields',{})
                if not processable(f): continue
                raw_title=str(first(f,'Título','Titulo','Título da notícia','Titulo da noticia','Nome','Evento')).strip()
                raw_link=str(first(f,'Link','URL','Fonte','Link da notícia','Link da noticia')).strip()
                audit_base={'origem':'airtable','tabela':table_name,'record_id':rec.get('id',''),'titulo':raw_title,'url':raw_link}
                cand=candidate_from_record(rec,kind)
                if not cand:
                    status['rejeitados']+=1
                    status['auditoria'].append({**audit_base,'decisao':'rejeitado','motivo':'Registro processável sem título/link válidos ou, para evento, sem data ISO válida.'})
                    continue
                dup=('u:'+urlnorm(cand.get('Link'))) in keys or ('t:'+norm(cand.get('Titulo'))) in keys
                if dup:
                    status['duplicados']+=1
                    status['auditoria'].append({**audit_base,'decisao':'duplicado','motivo':'Já existe em dados.json, noticias.json ou editorial/inbox.json.'})
                    continue
                inbox.setdefault(kind,[]).append(cand); keys.add('u:'+urlnorm(cand.get('Link'))); keys.add('t:'+norm(cand.get('Titulo')))
                status['aprovados_novos']+=1
                status['auditoria'].append({**audit_base,'decisao':'aprovado','motivo':'Sugestão estruturada, válida e não duplicada; enfileirada para o Radar.'})
                upd={}
                if 'Status' in f: upd['Status']='Aprovado'
                if 'Resultado da verificação' in f: upd['Resultado da verificação']='Aprovado pela pesquisa editorial nativa; enfileirado para o Radar.'
                if 'Última verificação' in f: upd['Última verificação']=iso()
                if upd: airtable_patch(table,rec['id'],upd)

        public_count, public_approved, public_rejected, public_dup, public_audit = public_research(keys)
        status['candidatos_publicos']=public_count
        status['rejeitados']+=public_rejected
        status['duplicados']+=public_dup
        status['auditoria'].extend(public_audit)
        for cand in public_approved: inbox.setdefault('noticias',[]).append(cand)
        status['aprovados_novos']+=len(public_approved)

        status['inbox_itens_adicionados']=sum(len(inbox.get(k,[]))-len(before.get(k,[])) for k in ('eventos','noticias'))
        status['inbox_commit_needed']=inbox!=before
        if inbox!=before: dump(INBOX,inbox)
        status['stage']='completed'
        status['observacoes_operacionais']='Execução nativa GitHub. Exatamente duas leituras Airtable; pesquisa pública ampliada em múltiplos eixos via Google News RSS + GDELT, com deduplicação, filtro anti-base, confiança de domínio, validação de conteúdo e trilha de auditoria gravada no pesquisa-status.json. A auditoria reutiliza os dados já lidos e não faz chamadas adicionais ao Airtable.'
        code=0
    except Exception as e:
        status['stage']='failed'; status['observacoes_operacionais']=f'{type(e).__name__}: {e}'
        code=1
    status['completed_at']=iso(); dump(STATUS,status)
    print(json.dumps(status,ensure_ascii=False))
    return code

if __name__=='__main__':
    raise SystemExit(main())
