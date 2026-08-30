#!/usr/bin/env python3
"""Prepara um post usando somente imagem web previamente curada e autorizada."""
from __future__ import annotations
import datetime as dt, hashlib, io, json, pathlib, re, urllib.request, unicodedata
from PIL import Image, ImageDraw, ImageFont

ROOT='https://raw.githubusercontent.com/robertovitor/radar-brasil-2027/main/'

def load(p, default):
    p=pathlib.Path(p)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()
def norm(v):
    s=unicodedata.normalize('NFKD',clean(v).casefold())
    return ''.join(c for c in s if not unicodedata.combining(c))
def date(v):
    try:return dt.date.fromisoformat(clean(v)[:10])
    except:return None
def base(item):
    t=norm(' '.join(clean(v) for v in item.values()))
    return bool(re.search(r'\bsub[ -]?(15|16|17|18|19|20|23)\b',t)) and ('selecao' in t or 'mundial feminino' in t)
def slug(key): return re.sub(r'[^a-z0-9]+','-',norm(key)).strip('-')[-70:]+'-'+hashlib.sha256(key.encode()).hexdigest()[:10]
def font(n,b=False): return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf'%('-Bold' if b else ''),n)
def wrap(draw,text,f,w):
    out=[]; cur=''
    for word in text.split():
        test=(cur+' '+word).strip()
        if draw.textbbox((0,0),test,font=f)[2]<=w: cur=test
        else:
            if cur: out.append(cur)
            cur=word
    if cur: out.append(cur)
    return out

def candidates(events,news,published,pending):
    out=[]
    for x in events:
        title=clean(x.get('Titulo')); d=date(x.get('Data')); key='instagram:evento:'+clean(x.get('ID') or title).casefold()
        if title and d and key not in published and not base(x):
            place=', '.join(filter(None,[clean(x.get('Local')),clean(x.get('Cidade')),clean(x.get('UF'))]))
            out.append(dict(key=key,title=title,date=d,type='evento',caption=f"📅 {title}\n\nQuando: {clean(x.get('DataBR')) or d.strftime('%d/%m/%Y')}\nOnde: {place or 'Local a definir'}\n\n{clean(x.get('Observacoes'))}\n\nFonte: {clean(x.get('Organizador')) or 'Radar Brasil 2027'}\n\n#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino\n\nSaiba mais pelo link da Bio"))
    for x in news:
        title=clean(x.get('Titulo')); d=date(x.get('Data')); key='instagram:noticia:'+clean(x.get('Link') or title).casefold()
        if title and d and d<=dt.datetime.now(dt.timezone.utc).date() and key not in published and not base(x):
            out.append(dict(key=key,title=title,date=d,type='noticia',caption=f"📰 {title}\n\n{clean(x.get('Resumo'))}\n\nFonte: {clean(x.get('Veiculo'))}\n\n#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino\n\nSaiba mais pelo link da Bio"))
    def rank(i):
        new=i['key'] in pending
        tier=1 if new and i['type']=='evento' else 2 if new else 3 if i['type']=='evento' else 4
        return (tier,-i['date'].toordinal(),i['key'])
    return sorted(out,key=rank)

def make_art(url,out,title,kind,credit):
    req=urllib.request.Request(url,headers={'User-Agent':'RadarBrasil2027/1.0'})
    with urllib.request.urlopen(req,timeout=25) as r: raw=r.read(15_000_000)
    im=Image.open(io.BytesIO(raw)).convert('RGB')
    w,h=im.size; side=min(w,h); left=(w-side)//2; top=(h-side)//2
    im=im.crop((left,top,left+side,top+side)).resize((1080,1080),Image.Resampling.LANCZOS)
    draw=ImageDraw.Draw(im,'RGBA')
    draw.rectangle((0,0,1080,115),fill=(0,0,0,120)); draw.text((42,30),'RADAR BRASIL 2027',font=font(40,True),fill='white')
    draw.rectangle((0,720,1080,1080),fill=(0,0,0,155)); f=font(48,True); lines=wrap(draw,title,f,980)
    y=755
    for line in lines[:4]: draw.text((48,y),line,font=f,fill='white'); y+=58
    label='EVENTO' if kind=='evento' else 'NOTÍCIA'; draw.text((48,1015),label,font=font(25,True),fill=(255,223,0))
    if credit: draw.text((250,1017),'Imagem: '+credit,font=font(20),fill=(240,240,240))
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True); im.save(out,'JPEG',quality=92,optimize=True)

def main():
    events=load('dados.json',[]); news=load('noticias.json',[]); ledger=load('instagram/publicados.json',{'published':[]}); state=load('instagram/conteudo-conhecido.json',{'pending_new':[]}); catalog=load('instagram/imagens-curadas.json',{'items':[]})
    published={clean(x.get('key')) for x in ledger.get('published',[])}; pending=set(state.get('pending_new',[]))
    now=dt.datetime.now(dt.timezone.utc)
    stamps=[]
    for x in ledger.get('published',[]):
        try: stamps.append(dt.datetime.fromisoformat(clean(x.get('published_at')).replace('Z','+00:00')))
        except: pass
    if stamps and (now-max(stamps)).total_seconds()<3600: print('found=false'); return 0
    curated={clean(x.get('idempotency_key')):x for x in catalog.get('items',[]) if x.get('reutilizacao_permitida') is True and clean(x.get('image_source_url'))}
    for item in candidates(events,news,published,pending):
        c=curated.get(item['key'])
        if not c: continue
        s=slug(item['key']); art=f'instagram/artes/{s}.jpg'; post=f'instagram/fila/automatica/{s}.json'; batch='instagram/fila/automatica/lote-atual.json'
        make_art(clean(c['image_source_url']),art,item['title'],item['type'],clean(c.get('credito')))
        payload={'id':s,'idempotency_key':item['key'],'approved':True,'source_type':item['type'],'image_url':ROOT+art,'caption':item['caption'],'image_source_url':clean(c['image_source_url']),'image_page_url':clean(c.get('source_page_url')),'image_credit':clean(c.get('credito')),'license_note':clean(c.get('licenca'))}
        pathlib.Path(post).parent.mkdir(parents=True,exist_ok=True); pathlib.Path(post).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); pathlib.Path(batch).write_text(json.dumps({'posts':[post]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('found=true'); print('batch_file='+batch); return 0
    print('found=false'); return 0
if __name__=='__main__': raise SystemExit(main())
