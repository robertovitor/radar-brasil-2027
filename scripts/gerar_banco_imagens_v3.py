#!/usr/bin/env python3
from __future__ import annotations
import csv, html, json, re, time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
CSV_PATH=ROOT/'banco_imagens'/'catalogo.csv'
JSON_PATH=ROOT/'banco_imagens'/'catalogo.json'
API='https://commons.wikimedia.org/w/api.php'
UA='RadarBrasil2027/1.2 (catalogo editorial de imagens abertas; contato via GitHub)'

QUOTAS={
 'selecao_brasileira':100,
 'futebol_feminino_brasil':70,
 'copas_femininas':80,
 'futebol_feminino_internacional':40,
 'estadios_sedes_2027':100,
 'cidades_sedes_2027':80,
 'torcida_futebol_feminino':30,
}

SEARCHES={
 'selecao_brasileira':[
  'Brazil women national football team','Brazil women football Marta','Brazil women football Debinha','Brazil women football Formiga','Brazil women football Cristiane','Brazil women football Kerolin','Brazil women football Adriana','Brazil women football Gabi Nunes'],
 'futebol_feminino_brasil':[
  'women association football Brazil','Brazil female footballer','Brazil women football players','Campeonato Brasileiro de Futebol Feminino','Corinthians women football Brazil','Palmeiras women football Brazil','Ferroviaria women football Brazil','Santos women football Brazil'],
 'copas_femininas':[
  '2023 FIFA Women World Cup football','2019 FIFA Women World Cup football','2015 FIFA Women World Cup football','2011 FIFA Women World Cup football','2007 FIFA Women World Cup football','2003 FIFA Women World Cup football','1999 FIFA Women World Cup football'],
 'futebol_feminino_internacional':[
  'women national association football team','women international football players','women soccer national team','female association football players'],
 'estadios_sedes_2027':[
  'Mineirao stadium Belo Horizonte','Estadio Nacional Brasilia Mane Garrincha','Arena Castelao Fortaleza Brazil','Beira-Rio stadium Porto Alegre','Arena Pernambuco stadium','Maracana stadium Rio de Janeiro','Arena Fonte Nova Salvador','Arena Corinthians Sao Paulo stadium','Neo Quimica Arena stadium'],
 'cidades_sedes_2027':[
  'Belo Horizonte Brazil city landmark','Brasilia Brazil city landmark','Fortaleza Ceara Brazil landmark','Porto Alegre Brazil landmark','Recife Pernambuco Brazil landmark','Rio de Janeiro Brazil landmark','Salvador Bahia Brazil landmark','Sao Paulo Brazil landmark'],
 'torcida_futebol_feminino':[
  'FIFA Women World Cup fans','women soccer supporters stadium','women association football supporters','women football crowd stadium','women soccer fans crowd','female football supporters stadium'],
}

FIELDS=['id','categoria','titulo','pessoa_local','fonte','pagina_origem','url_direta','url_thumbnail','autor','licenca','url_licenca','atribuicao','status_licenca','instagram_ok','largura','altura','arquivo_local','ultima_utilizacao','qtd_utilizacoes','observacoes']
OPEN=re.compile(r'(?:CC0|public domain|PD-|CC[- ]?BY(?:[- ]?SA)?(?:[- ]?\d(?:\.\d)?)?)',re.I)
BLOCKLIC=re.compile(r'(?:NC|ND|non.?commercial|no.?derivatives|fair use)',re.I)
BLOCK_COMMON=re.compile(r"(?:president|governor|prefeit|minister|politic|election|partid|logo|flag of|coat of arms)",re.I)
BLOCK_AMERICAN=re.compile(r'(?:NFL|NCAA|Badgers|Georgia Tech|Ole Miss|American football|gridiron|touchdown|quarterback|Super Bowl)',re.I)
WOMEN=re.compile(r"(?:women|woman|women's|female|femin|femenin|mulher|garota|girl)",re.I)
SOCCER=re.compile(r'(?:association football|soccer|futebol|football|FIFA|World Cup)',re.I)
FANS=re.compile(r'(?:fan|supporter|crowd|spectator|torcida|torcedor|arquibancada|stands)',re.I)
BRAZIL=re.compile(r'(?:Brazil|Brasil|brasileir|Corinthians|Palmeiras|Ferrovi[aá]ria|Santos)',re.I)


def clean(v):
 if not v:return ''
 v=html.unescape(v);v=re.sub(r'<br\s*/?>',' ',v,flags=re.I);v=re.sub(r'<[^>]+>','',v)
 return re.sub(r'\s+',' ',v).strip()

def mv(meta,key):
 x=meta.get(key) or {};return clean(x.get('value') if isinstance(x,dict) else '')

def api(params):
 params={**params,'format':'json','formatversion':'2','maxlag':'5'};url=f"{API}?{urlencode(params)}"
 for attempt in range(7):
  try:
   req=Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
   with urlopen(req,timeout=45) as r:data=json.loads(r.read().decode('utf-8'))
   time.sleep(1.15);return data
  except HTTPError as e:
   if e.code not in (429,503):raise
   wait=min(60,8*(attempt+1));print(f'Rate limit {e.code}; aguardando {wait}s');time.sleep(wait)
 raise RuntimeError('Commons continuou limitando apos retries')

def candidates(query,pages=4):
 off=0
 for _ in range(pages):
  d=api({'action':'query','generator':'search','gsrsearch':query,'gsrnamespace':6,'gsrlimit':50,'gsroffset':off,'prop':'imageinfo','iiprop':'url|size|mime|extmetadata','iiurlwidth':1600})
  for p in d.get('query',{}).get('pages',[]):yield p
  nxt=d.get('continue',{}).get('gsroffset')
  if nxt is None:return
  off=int(nxt)

def editorial_ok(cat,title,desc):
 text=f'{title} {desc}'
 if BLOCK_COMMON.search(text):return False
 if cat=='torcida_futebol_feminino':
  return bool(WOMEN.search(text) and SOCCER.search(text) and FANS.search(text) and not BLOCK_AMERICAN.search(text))
 if cat=='selecao_brasileira':return bool(BRAZIL.search(text) and WOMEN.search(text) and SOCCER.search(text))
 if cat=='futebol_feminino_brasil':return bool(BRAZIL.search(text) and WOMEN.search(text) and SOCCER.search(text))
 if cat=='copas_femininas':return bool(WOMEN.search(text) and re.search(r'world cup|copa do mundo',text,re.I))
 if cat=='futebol_feminino_internacional':return bool(WOMEN.search(text) and SOCCER.search(text) and not BLOCK_AMERICAN.search(text))
 return True

def to_row(p,cat):
 title=p.get('title','')
 if not title.startswith('File:'):return None
 infos=p.get('imageinfo') or []
 if not infos:return None
 ii=infos[0]
 if ii.get('mime') not in {'image/jpeg','image/png'}:return None
 w,h=int(ii.get('width') or 0),int(ii.get('height') or 0)
 if w<700 or h<500:return None
 m=ii.get('extmetadata') or {};desc=mv(m,'ImageDescription')
 if not editorial_ok(cat,title,desc):return None
 lic=mv(m,'LicenseShortName');lurl=mv(m,'LicenseUrl');terms=mv(m,'UsageTerms');lt=' '.join(x for x in (lic,terms,lurl) if x)
 if not lt or BLOCKLIC.search(lt) or not OPEN.search(lt):return None
 author=mv(m,'Artist') or mv(m,'Credit') or 'Autor indicado na pagina do arquivo';credit=mv(m,'Credit')
 page=ii.get('descriptionurl') or 'https://commons.wikimedia.org/wiki/'+title.replace(' ','_');direct=ii.get('url','');thumb=ii.get('thumburl') or direct
 if not direct:return None
 attr=[author]
 if credit and credit.lower() not in author.lower():attr.append(credit)
 attr.append(lic or terms)
 return {'categoria':cat,'titulo':title[5:].rsplit('.',1)[0].replace('_',' '),'pessoa_local':desc[:300],'fonte':'Wikimedia Commons','pagina_origem':page,'url_direta':direct,'url_thumbnail':thumb,'autor':author[:500],'licenca':lic or terms,'url_licenca':lurl,'atribuicao':' | '.join(x for x in attr if x)[:900],'status_licenca':'APROVADA_AUTO','instagram_ok':'SIM','largura':w,'altura':h,'arquivo_local':'','ultima_utilizacao':'','qtd_utilizacoes':'0','observacoes':'Licenca aberta conferida automaticamente via extmetadata do Wikimedia Commons e filtro editorial Radar 2027; revalidar se a pagina de origem mudar.'}

def manual_seed():
 if not CSV_PATH.exists():return []
 with CSV_PATH.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 out=[]
 for r in rows:
  if r.get('status_licenca')=='APROVADA' and r.get('instagram_ok')=='SIM':
   n={k:r.get(k,'') for k in FIELDS};n['categoria']='selecao_brasileira';out.append(n)
 return out[:QUOTAS['selecao_brasileira']]

def main():
 rows=manual_seed();seenp={r.get('pagina_origem','') for r in rows};seenu={r.get('url_direta','') for r in rows if r.get('url_direta')};counts=Counter(r['categoria'] for r in rows)
 print('Sementes manuais',len(rows))
 for cat,quota in QUOTAS.items():
  for q in SEARCHES[cat]:
   if counts[cat]>=quota:break
   print('Busca',cat,counts[cat],'/',quota,q)
   try:
    for p in candidates(q):
     if counts[cat]>=quota:break
     r=to_row(p,cat)
     if not r or r['pagina_origem'] in seenp or r['url_direta'] in seenu:continue
     rows.append(r);seenp.add(r['pagina_origem']);seenu.add(r['url_direta']);counts[cat]+=1
   except Exception as e:print('AVISO',q,repr(e))
  if counts[cat]<quota:raise SystemExit(f'Categoria incompleta {cat}: {counts[cat]}/{quota}')
 if len(rows)!=500:raise SystemExit(f'Total invalido {len(rows)}/500')
 for i,r in enumerate(rows,1):r['id']=f'IMG{i:04d}'
 with CSV_PATH.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows({k:r.get(k,'') for k in FIELDS} for r in rows)
 JSON_PATH.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('TOTAL',len(rows),'DISTRIBUICAO',dict(counts))

if __name__=='__main__':main()
