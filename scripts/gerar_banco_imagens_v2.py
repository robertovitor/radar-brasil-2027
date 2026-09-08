#!/usr/bin/env python3
from __future__ import annotations
import csv, html, json, re, time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / 'banco_imagens' / 'catalogo.csv'
JSON_PATH = ROOT / 'banco_imagens' / 'catalogo.json'
API = 'https://commons.wikimedia.org/w/api.php'
UA = 'RadarBrasil2027/1.1 (catalogo editorial de imagens abertas; contato via GitHub)'
TARGET = 500

SEARCHES = [
('selecao_brasileira','Brazil women national football team'),('selecao_brasileira','Brazil women football Marta'),('selecao_brasileira','Brazil women football Debinha'),('selecao_brasileira','Brazil women football Formiga'),('selecao_brasileira','Brazil women football Cristiane'),('selecao_brasileira','Brazil women football Kerolin'),('selecao_brasileira','Brazil women football Gabi Nunes'),('selecao_brasileira','Brazil women football Adriana'),
('futebol_feminino','women association football Brazil'),('futebol_feminino','women football Brazil players'),('futebol_feminino','Brazil female footballer'),
('copa_feminina_2023','2023 FIFA Women World Cup football'),('copa_feminina_2023','2023 women world cup players'),('copa_feminina_2019','2019 FIFA Women World Cup football'),('copa_feminina_2019','2019 women world cup players'),('copa_feminina_2015','2015 FIFA Women World Cup football'),('copa_feminina_2011','2011 FIFA Women World Cup football'),('copa_feminina_2007','2007 FIFA Women World Cup football'),
('torcida','women football supporters stadium'),('torcida','women soccer fans stadium'),('torcida','women football crowd'),
('estadio','Maracana stadium Rio de Janeiro'),('estadio','Mineirao stadium Belo Horizonte'),('estadio','Arena Fonte Nova Salvador'),('estadio','Estadio Nacional Brasilia Mane Garrincha'),('estadio','Arena Corinthians Sao Paulo stadium'),('estadio','Neo Quimica Arena stadium'),('estadio','Castelao stadium Fortaleza Brazil'),('estadio','Beira-Rio stadium Porto Alegre'),('estadio','Arena Pernambuco stadium'),('estadio','Arena Amazonia stadium Manaus'),('estadio','Arena das Dunas stadium Natal'),('estadio','Arena da Baixada Curitiba stadium'),
('cidade_sede','Rio de Janeiro Brazil landmark'),('cidade_sede','Sao Paulo Brazil landmark'),('cidade_sede','Brasilia Brazil landmark'),('cidade_sede','Belo Horizonte Brazil landmark'),('cidade_sede','Salvador Bahia Brazil landmark'),('cidade_sede','Porto Alegre Brazil landmark'),('cidade_sede','Recife Pernambuco Brazil landmark'),('cidade_sede','Fortaleza Ceara Brazil landmark'),('cidade_sede','Manaus Amazonas Brazil landmark'),('cidade_sede','Natal Rio Grande do Norte Brazil landmark'),('cidade_sede','Curitiba Parana Brazil landmark')]

FIELDS=['id','categoria','titulo','pessoa_local','fonte','pagina_origem','url_direta','url_thumbnail','autor','licenca','url_licenca','atribuicao','status_licenca','instagram_ok','largura','altura','arquivo_local','ultima_utilizacao','qtd_utilizacoes','observacoes']
OPEN=re.compile(r'(?:CC0|public domain|PD-|CC[- ]?BY(?:[- ]?SA)?(?:[- ]?\d(?:\.\d)?)?)',re.I)
BLOCKLIC=re.compile(r'(?:NC|ND|non.?commercial|no.?derivatives|fair use)',re.I)
BLOCKTITLE=re.compile(r"(?:men['’]?s|masculin|president|governor|prefeit|minister|politic|election|partid|logo|flag of|coat of arms)",re.I)


def clean(v):
    if not v:return ''
    v=html.unescape(v); v=re.sub(r'<br\s*/?>',' ',v,flags=re.I); v=re.sub(r'<[^>]+>','',v)
    return re.sub(r'\s+',' ',v).strip()

def mv(meta,key):
    x=meta.get(key) or {}; return clean(x.get('value') if isinstance(x,dict) else '')

def api(params):
    params={**params,'format':'json','formatversion':'2','maxlag':'5'}
    url=f"{API}?{urlencode(params)}"
    for attempt in range(6):
        try:
            req=Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
            with urlopen(req,timeout=45) as r:
                data=json.loads(r.read().decode('utf-8'))
            time.sleep(1.15)
            return data
        except HTTPError as e:
            if e.code not in (429,503): raise
            wait=min(60,8*(attempt+1)); print(f'Rate limit {e.code}; aguardando {wait}s'); time.sleep(wait)
    raise RuntimeError('Commons continuou limitando após retries')

def candidates(query):
    off=0
    for _ in range(4):
        d=api({'action':'query','generator':'search','gsrsearch':query,'gsrnamespace':6,'gsrlimit':50,'gsroffset':off,'prop':'imageinfo','iiprop':'url|size|mime|extmetadata','iiurlwidth':1600})
        for p in d.get('query',{}).get('pages',[]): yield p
        nxt=d.get('continue',{}).get('gsroffset')
        if nxt is None:return
        off=int(nxt)

def to_row(p,cat):
    title=p.get('title','')
    if not title.startswith('File:') or BLOCKTITLE.search(title):return None
    infos=p.get('imageinfo') or []
    if not infos:return None
    ii=infos[0]
    if ii.get('mime') not in {'image/jpeg','image/png'}:return None
    w,h=int(ii.get('width') or 0),int(ii.get('height') or 0)
    if w<700 or h<500:return None
    m=ii.get('extmetadata') or {}; lic=mv(m,'LicenseShortName'); lurl=mv(m,'LicenseUrl'); terms=mv(m,'UsageTerms')
    text=' '.join(x for x in (lic,terms,lurl) if x)
    if not text or BLOCKLIC.search(text) or not OPEN.search(text):return None
    author=mv(m,'Artist') or mv(m,'Credit') or 'Autor indicado na página do arquivo'; credit=mv(m,'Credit'); desc=mv(m,'ImageDescription')
    page=ii.get('descriptionurl') or 'https://commons.wikimedia.org/wiki/'+title.replace(' ','_'); direct=ii.get('url',''); thumb=ii.get('thumburl') or direct
    if not direct:return None
    attr=[author];
    if credit and credit.lower() not in author.lower():attr.append(credit)
    attr.append(lic or terms)
    return {'categoria':cat,'titulo':title[5:].rsplit('.',1)[0].replace('_',' '),'pessoa_local':desc[:300],'fonte':'Wikimedia Commons','pagina_origem':page,'url_direta':direct,'url_thumbnail':thumb,'autor':author[:500],'licenca':lic or terms,'url_licenca':lurl,'atribuicao':' | '.join(x for x in attr if x)[:900],'status_licenca':'APROVADA_AUTO','instagram_ok':'SIM','largura':w,'altura':h,'arquivo_local':'','ultima_utilizacao':'','qtd_utilizacoes':'0','observacoes':'Licença aberta conferida automaticamente via extmetadata do Wikimedia Commons; revalidar se a página de origem mudar.'}

def existing():
    if not CSV_PATH.exists():return []
    with CSV_PATH.open(encoding='utf-8-sig',newline='') as f:return [{k:r.get(k,'') for k in FIELDS} for r in csv.DictReader(f)]

def save(rows):
    for i,r in enumerate(rows,1):
        if not r.get('id'):r['id']=f'IMG{i:04d}'
    with CSV_PATH.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows({k:r.get(k,'') for k in FIELDS} for r in rows)
    JSON_PATH.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    rows=existing(); seenp={r.get('pagina_origem','') for r in rows}; seenu={r.get('url_direta','') for r in rows if r.get('url_direta')}
    print('Inicial',len(rows))
    for cat,q in SEARCHES:
        if len(rows)>=TARGET:break
        print('Busca',cat,q,'atual',len(rows))
        try:
            for p in candidates(q):
                if len(rows)>=TARGET:break
                r=to_row(p,cat)
                if not r or r['pagina_origem'] in seenp or r['url_direta'] in seenu:continue
                rows.append(r);seenp.add(r['pagina_origem']);seenu.add(r['url_direta'])
        except Exception as e:print('AVISO',q,repr(e))
    rows=rows[:TARGET];save(rows);print('TOTAL',len(rows))
    if len(rows)<TARGET:raise SystemExit(f'Banco incompleto {len(rows)}/{TARGET}')

if __name__=='__main__':main()
