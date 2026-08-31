#!/usr/bin/env python3
"""Prepara um post do Radar Brasil 2027 somente com fotografia curada e licenciada."""
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
            subtitle=(clean(x.get('DataBR')) or d.strftime('%d/%m/%Y'))+' • '+(place or 'Local a definir')
            out.append(dict(key=key,title=title,date=d,type='evento',subtitle=subtitle,caption=f"📅 {title}\n\nQuando: {clean(x.get('DataBR')) or d.strftime('%d/%m/%Y')}\nOnde: {place or 'Local a definir'}\n\n{clean(x.get('Observacoes'))}\n\nFonte: {clean(x.get('Organizador')) or 'Radar Brasil 2027'}\n\n#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino\n\nSaiba mais pelo link da Bio"))
    for x in news:
        title=clean(x.get('Titulo')); d=date(x.get('Data')); key='instagram:noticia:'+clean(x.get('Link') or title).casefold()
        if title and d and d<=dt.datetime.now(dt.timezone.utc).date() and key not in published and not base(x):
            subtitle=(clean(x.get('Veiculo')) or 'Radar Brasil 2027')+' • '+d.strftime('%d/%m/%Y')
            out.append(dict(key=key,title=title,date=d,type='noticia',subtitle=subtitle,caption=f"📰 {title}\n\n{clean(x.get('Resumo'))}\n\nFonte: {clean(x.get('Veiculo'))}\n\n#RadarBrasil2027 #CopaFeminina2027 #FutebolFeminino\n\nSaiba mais pelo link da Bio"))
    def rank(i):
        new=i['key'] in pending
        tier=1 if new and i['type']=='evento' else 2 if new else 3 if i['type']=='evento' else 4
        return (tier,-i['date'].toordinal(),i['key'])
    return sorted(out,key=rank)

def make_photo_art(url,out,title,kind,credit):
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

def make_original_art(out,title,kind,subtitle,key):
    """Gera arte 1080x1080 original, sem depender de fotografia de terceiros."""
    seed=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)
    im=Image.new('RGB',(1080,1080),(8,74,52) if kind=='evento' else (18,56,92))
    draw=ImageDraw.Draw(im,'RGBA')
    # Elementos gráficos determinísticos para cada item: cada post recebe uma arte exclusiva.
    for i in range(7):
        x=(seed*(i+3)*37)%1080; y=(seed*(i+5)*53)%1080; r=110+((seed>>(i%8))%210)
        draw.ellipse((x-r,y-r,x+r,y+r),fill=(255,223,0,22+5*i))
    draw.polygon([(0,0),(1080,0),(1080,260),(0,430)],fill=(0,0,0,42))
    draw.rectangle((0,0,1080,118),fill=(0,0,0,68))
    draw.text((48,31),'RADAR BRASIL 2027',font=font(40,True),fill='white')
    label='EVENTO' if kind=='evento' else 'NOTÍCIA'
    draw.rounded_rectangle((48,180,250,244),radius=16,fill=(255,223,0,235))
    draw.text((73,194),label,font=font(25,True),fill=(15,45,35))
    f=font(58,True); lines=wrap(draw,title,f,960)
    y=320
    for line in lines[:6]:
        draw.text((58,y),line,font=f,fill='white'); y+=72
    if subtitle:
        sf=font(30)
        sublines=wrap(draw,subtitle,sf,940)
        sy=min(820,y+30)
        for line in sublines[:3]:
            draw.text((60,sy),line,font=sf,fill=(245,245,245)); sy+=42
    draw.rectangle((48,982,1032,986),fill=(255,223,0,220))
    draw.text((48,1007),'Copa do Mundo Feminina 2027 • Brasil',font=font(24,True),fill='white')
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True); im.save(out,'JPEG',quality=94,optimize=True)

def main():
    events=load('dados.json',[]); news=load('noticias.json',[]); ledger=load('instagram/publicados.json',{'published':[]}); state=load('instagram/conteudo-conhecido.json',{'pending_new':[]}); catalog=load('instagram/imagens-curadas.json',{'items':[]})
    published={clean(x.get('key')) for x in ledger.get('published',[])}; pending=set(state.get('pending_new',[]))
    now=dt.datetime.now(dt.timezone.utc)
    stamps=[]
    for x in ledger.get('published',[]):
        try: stamps.append(dt.datetime.fromisoformat(clean(x.get('published_at')).replace('Z','+00:00')))
        except: pass
    if stamps and (now-max(stamps)).total_seconds()<3600: print('found=false'); return 0
    curated={clean(x.get('idempotency_key')):x for x in catalog.get('items',[]) if x.get('reutilizacao_permitida') is True and all(clean(x.get(field)) for field in ('image_source_url','source_page_url','credito','licenca'))}
    ranked=candidates(events,news,published,pending)
    if not ranked:
        print('found=false'); return 0
    # Tenta até dez candidatos na ordem editorial. Ausência ou falha de
    # imagem bloqueia somente o candidato atual, nunca os seguintes.
    item=None; c=None; art=''; post=''; batch='instagram/fila/automatica/lote-atual.json'
    for candidate in ranked[:10]:
        candidate_curated=curated.get(candidate['key'])
        if not candidate_curated:
            print('blocked_image='+candidate['key'])
            continue
        candidate_slug=slug(candidate['key'])
        candidate_art=f'instagram/artes/{candidate_slug}.jpg'
        try:
            make_photo_art(clean(candidate_curated['image_source_url']),candidate_art,candidate['title'],candidate['type'],clean(candidate_curated.get('credito')))
        except Exception as exc:
            print('blocked_image='+candidate['key']+':'+type(exc).__name__)
            continue
        item=candidate; c=candidate_curated; s=candidate_slug; art=candidate_art
        post=f'instagram/fila/automatica/{s}.json'
        break
    if item is None:
        print('found=false'); return 0
    payload={'id':s,'idempotency_key':item['key'],'approved':True,'source_type':item['type'],'image_url':ROOT+art,'caption':item['caption'],'image_source_url':clean(c['image_source_url']),'image_page_url':clean(c['source_page_url']),'image_credit':clean(c['credito']),'license_note':clean(c['licenca'])}
    pathlib.Path(post).parent.mkdir(parents=True,exist_ok=True); pathlib.Path(post).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); pathlib.Path(batch).write_text(json.dumps({'posts':[post]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('found=true'); print('batch_file='+batch); return 0
    print('found=false'); return 0
if __name__=='__main__': raise SystemExit(main())
