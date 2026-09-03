#!/usr/bin/env python3
"""Prepara um post do Radar Brasil 2027 com gates obrigatórios de semântica visual e legibilidade."""
from __future__ import annotations
import datetime as dt, hashlib, html, io, json, pathlib, re, urllib.parse, urllib.request, unicodedata
from PIL import Image, ImageDraw, ImageFont

ROOT='https://raw.githubusercontent.com/robertovitor/radar-brasil-2027/main/'
COMMONS_API='https://commons.wikimedia.org/w/api.php'
SAFE_LEFT=150
SAFE_RIGHT=930
SAFE_WIDTH=SAFE_RIGHT-SAFE_LEFT
MIN_TITLE_FONT=58
MAX_TITLE_LINES=4
ALLOWED_LICENSE_MARKERS=(
    'cc by ', 'cc-by-', 'cc by-sa', 'cc-by-sa', 'cc0',
    'public domain', 'pd-', 'domínio público', 'dominio publico'
)
STOPWORDS={
    'a','o','as','os','de','da','do','das','dos','e','em','na','no','nas','nos','para','por','com','sem','um','uma',
    'copa','mundo','mundial','feminina','feminino','fifa','2027','brasil','brasileira','brasileiro','radar','noticia','evento'
}
MALE_BLOCKERS=(
    'cristiano ronaldo','neymar','lionel messi','copa da russia','russia 2018','world cup 2018',
    'selecao masculina','seleção masculina','men national team',"men's national team",
    "men's football",'men football',"men's soccer",'men soccer'
)
FEMALE_MARKERS=(
    'futebol feminino','women football','women soccer',"women's football", "women's soccer",
    'female football','female soccer','selecao feminina','seleção feminina','jogadora','jogadoras',
    'atleta feminina','atletas femininas','women national team',"women's national team"
)
INSTITUTIONAL_MARKERS=(
    'ministerio','ministério','secom','senado','camara','câmara','governo','lei','projeto de lei',
    'patrocinio','patrocínio','voluntariado','programa','bancada','transmissao','transmissão',
    'midia','mídia','comunicacao','comunicação','politica publica','política pública'
)

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
def strip_html(v): return clean(html.unescape(re.sub(r'<[^>]+>',' ',str(v or ''))))
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

def fit_title(draw,title,width,start_size=86,min_size=MIN_TITLE_FONT,max_lines=MAX_TITLE_LINES):
    size=start_size
    while size>=min_size:
        f=font(size,True); lines=wrap(draw,title,f,width)
        if len(lines)<=max_lines:
            return f,lines,True
        size-=2
    f=font(min_size,True)
    words=title.split()
    while words:
        candidate=' '.join(words)
        lines=wrap(draw,candidate,f,width)
        if len(lines)<=max_lines:
            if candidate != title:
                last=lines[-1]
                while draw.textbbox((0,0),last+'…',font=f)[2]>width and len(last)>4:
                    last=last[:-1].rstrip()
                lines[-1]=last+'…'
            return f,lines,True
        words=words[:-1]
    return f,['Radar Brasil 2027'],False

def candidates(events,news,published,pending):
    out=[]
    for x in events:
        title=clean(x.get('Titulo')); d=date(x.get('Data')); key='instagram:evento:'+clean(x.get('ID') or title).casefold()
        if title and d and key not in published and not base(x):
            place=', '.join(filter(None,[clean(x.get('Local')),clean(x.get('Cidade')),clean(x.get('UF'))]))
            subtitle=(clean(x.get('DataBR')) or d.strftime('%d/%m/%Y'))+' • '+(place or 'Local a definir')
            search_context=' '.join(filter(None,[title,clean(x.get('Cidade')),clean(x.get('UF')),clean(x.get('Local')),clean(x.get('Organizador'))]))
            out.append(dict(key=key,title=title,date=d,type='evento',subtitle=subtitle,search_context=search_context,caption=f"📅 {title}\n\nQuando: {clean(x.get('DataBR')) or d.strftime('%d/%m/%Y')}\nOnde: {place or 'Local a definir'}\n\n{clean(x.get('Observacoes'))}\n\nFonte: {clean(x.get('Organizador')) or 'Radar Brasil 2027'}\n\n#RadarBrasil2027 #MundialFeminino2027 #FutebolFeminino\n\nSaiba mais pelo link da Bio"))
    for x in news:
        title=clean(x.get('Titulo')); d=date(x.get('Data')); key='instagram:noticia:'+clean(x.get('Link') or title).casefold()
        if title and d and d<=dt.datetime.now(dt.timezone.utc).date() and key not in published and not base(x):
            subtitle=(clean(x.get('Veiculo')) or 'Radar Brasil 2027')+' • '+d.strftime('%d/%m/%Y')
            search_context=' '.join(filter(None,[title,clean(x.get('Tema')),clean(x.get('CidadeUF')),clean(x.get('Veiculo'))]))
            out.append(dict(key=key,title=title,date=d,type='noticia',subtitle=subtitle,search_context=search_context,caption=f"📰 {title}\n\n{clean(x.get('Resumo'))}\n\nFonte: {clean(x.get('Veiculo'))}\n\n#RadarBrasil2027 #MundialFeminino2027 #FutebolFeminino\n\nSaiba mais pelo link da Bio"))
    def rank(i):
        new=i['key'] in pending
        tier=1 if new and i['type']=='evento' else 2 if new else 3 if i['type']=='evento' else 4
        return (tier,-i['date'].toordinal(),i['key'])
    return sorted(out,key=rank)

def http_json(url,timeout=20):
    req=urllib.request.Request(url,headers={'User-Agent':'RadarBrasil2027/1.0 (Instagram image licensing search)'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def distinct_terms(text):
    words=[w for w in re.findall(r'[a-z0-9áàâãéêíóôõúç-]+',clean(text).casefold()) if len(w)>2 and norm(w) not in STOPWORDS]
    uniq=[]; seen=set()
    for w in words:
        n=norm(w)
        if n not in seen:
            uniq.append(w); seen.add(n)
    return uniq

def commons_queries(text):
    """Busca somente por contexto específico; termos genéricos nunca bastam para aprovação."""
    uniq=distinct_terms(text)
    queries=[]
    def add(q):
        q=clean(q)
        if q and norm(q) not in {norm(x) for x in queries}: queries.append(q)
    if uniq:
        add(' '.join(uniq[:10]))
        add(' '.join(uniq[:7]))
        add(' '.join(uniq[:5]))
        for term in uniq[:4]: add(term+' women football')
    return queries[:8]

def license_allowed(meta):
    lic=' '.join([
        strip_html(meta.get('LicenseShortName',{}).get('value')),
        strip_html(meta.get('License',{}).get('value')),
        strip_html(meta.get('UsageTerms',{}).get('value')),
    ]).casefold()
    return any(m in lic for m in ALLOWED_LICENSE_MARKERS)

def commons_credit(meta):
    artist=strip_html(meta.get('Artist',{}).get('value'))
    credit=strip_html(meta.get('Credit',{}).get('value'))
    return artist or credit or 'Wikimedia Commons'

def commons_license(meta):
    short=strip_html(meta.get('LicenseShortName',{}).get('value'))
    usage=strip_html(meta.get('UsageTerms',{}).get('value'))
    return short or usage or 'Licença livre verificada no Wikimedia Commons'

def commons_descriptor(page,meta):
    fields=[clean(page.get('title')),strip_html(meta.get('ObjectName',{}).get('value')),strip_html(meta.get('ImageDescription',{}).get('value')),strip_html(meta.get('Categories',{}).get('value')),strip_html(meta.get('Credit',{}).get('value'))]
    return ' '.join(x for x in fields if x)

def semantic_image_ok(item,page,meta,query):
    item_text=norm((item.get('search_context') or '')+' '+item.get('title',''))
    desc=norm(commons_descriptor(page,meta)+' '+query)
    if any(norm(x) in desc for x in MALE_BLOCKERS): return False,'male_or_mens_football_blocker'
    female=any(norm(x) in desc for x in FEMALE_MARKERS)
    item_terms={norm(x) for x in distinct_terms(item_text)}
    desc_terms={norm(x) for x in distinct_terms(desc)}
    overlap=item_terms & desc_terms
    institutional=any(norm(x) in item_text for x in INSTITUTIONAL_MARKERS)
    if institutional:
        ok=female and len(overlap)>=2
        return ok,('institutional_direct_match' if ok else 'institutional_requires_text_art')
    football_context=any(x in item_text for x in ('futebol','selecao','jogo','amistoso','torneio','copa','mundial'))
    if football_context and not female: return False,'female_context_missing'
    ok=len(overlap)>=2
    return ok,('direct_semantic_match' if ok else 'weak_keyword_overlap')

def find_commons_image(item):
    search_context=item.get('search_context') or item['title']
    for query in commons_queries(search_context):
        params={'action':'query','generator':'search','gsrsearch':query+' filetype:bitmap','gsrnamespace':'6','gsrlimit':'20','prop':'imageinfo','iiprop':'url|mime|size|extmetadata','iiurlwidth':'1600','format':'json','formatversion':'2'}
        try: data=http_json(COMMONS_API+'?'+urllib.parse.urlencode(params))
        except Exception as exc:
            print('commons_search_failed='+type(exc).__name__); continue
        pages=(data.get('query') or {}).get('pages') or []
        for p in pages:
            info=(p.get('imageinfo') or [{}])[0]
            mime=clean(info.get('mime')).casefold(); width=int(info.get('width') or 0); height=int(info.get('height') or 0); meta=info.get('extmetadata') or {}
            if mime not in ('image/jpeg','image/png','image/webp') or width<700 or height<450 or not license_allowed(meta): continue
            ok,reason=semantic_image_ok(item,p,meta,query)
            if not ok:
                print('image_rejected='+reason+':'+clean(p.get('title'))); continue
            url=clean(info.get('thumburl') or info.get('url'))
            if not url: continue
            page='https://commons.wikimedia.org/wiki/'+urllib.parse.quote(clean(p.get('title')).replace(' ','_'),safe=':/()_-')
            return {'image_source_url':url,'source_page_url':page,'credito':commons_credit(meta),'licenca':commons_license(meta),'reutilizacao_permitida':True,'auto_found':True,'query':query,'semantic_reason':reason}
    return None

def make_photo_art(url,out,title,kind,credit):
    req=urllib.request.Request(url,headers={'User-Agent':'RadarBrasil2027/1.0'})
    with urllib.request.urlopen(req,timeout=25) as r: raw=r.read(15_000_000)
    im=Image.open(io.BytesIO(raw)).convert('RGB'); w,h=im.size; side=min(w,h); left=(w-side)//2; top=(h-side)//2
    im=im.crop((left,top,left+side,top+side)).resize((1080,1080),Image.Resampling.LANCZOS)
    draw=ImageDraw.Draw(im,'RGBA'); draw.rectangle((0,0,1080,125),fill=(0,0,0,135)); draw.text((SAFE_LEFT,32),'RADAR BRASIL 2027',font=font(36,True),fill='white'); draw.rectangle((0,610,1080,1080),fill=(0,0,0,182))
    f,lines,readable=fit_title(draw,title,SAFE_WIDTH,start_size=88); y=650; step=f.size+10
    for line in lines[:MAX_TITLE_LINES]: draw.text((SAFE_LEFT,y),line,font=f,fill='white'); y+=step
    label='EVENTO' if kind=='evento' else 'NOTÍCIA'; draw.text((SAFE_LEFT,1012),label,font=font(22,True),fill=(255,223,0))
    if credit:
        cf=font(16); credit_lines=wrap(draw,'Imagem: '+credit,cf,SAFE_WIDTH-145); draw.text((SAFE_LEFT+145,1017),credit_lines[0] if credit_lines else '',font=cf,fill=(240,240,240))
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True); im.save(out,'JPEG',quality=92,optimize=True)
    return readable and f.size>=MIN_TITLE_FONT and len(lines)<=MAX_TITLE_LINES, f.size, len(lines)

def make_original_art(out,title,kind,subtitle,key):
    import math
    seed=int(hashlib.sha256(key.encode()).hexdigest()[:8],16); im=Image.new('RGB',(1080,1080),(8,74,52) if kind=='evento' else (18,56,92)); draw=ImageDraw.Draw(im,'RGBA')
    draw.rectangle((0,560,1080,1080),fill=(12,105,65,255))
    for x in range(0,1081,180): draw.line((x,560,540,1080),fill=(255,255,255,28),width=4)
    draw.ellipse((310,650,770,1110),outline=(255,255,255,70),width=6); draw.line((540,560,540,1080),fill=(255,255,255,65),width=5)
    bx=790+(seed%70); by=270+((seed>>8)%90); br=125; draw.ellipse((bx-br,by-br,bx+br,by+br),fill=(245,245,235,235),outline=(20,40,35,170),width=8); draw.regular_polygon((bx,by,45),5,rotation=18,fill=(25,55,48,220))
    for ang in (18,90,162,234,306):
        x1=bx+42*math.cos(math.radians(ang)); y1=by+42*math.sin(math.radians(ang)); x2=bx+105*math.cos(math.radians(ang)); y2=by+105*math.sin(math.radians(ang)); draw.line((x1,y1,x2,y2),fill=(25,55,48,180),width=7)
    draw.rectangle((0,0,1080,125),fill=(0,0,0,90)); draw.text((SAFE_LEFT,32),'RADAR BRASIL 2027',font=font(36,True),fill='white'); label='EVENTO' if kind=='evento' else 'NOTÍCIA'; draw.rounded_rectangle((SAFE_LEFT,180,SAFE_LEFT+202,244),radius=16,fill=(255,223,0,235)); draw.text((SAFE_LEFT+25,194),label,font=font(25,True),fill=(15,45,35))
    f,lines,readable=fit_title(draw,title,620,start_size=84); y=285
    for line in lines[:MAX_TITLE_LINES]: draw.text((SAFE_LEFT,y),line,font=f,fill='white'); y+=f.size+10
    if subtitle:
        sf=font(24); sublines=wrap(draw,subtitle,sf,SAFE_WIDTH); sy=900
        for line in sublines[:2]: draw.text((SAFE_LEFT,sy),line,font=sf,fill=(245,245,245)); sy+=34
    draw.rectangle((SAFE_LEFT,982,SAFE_RIGHT,986),fill=(255,223,0,220)); draw.text((SAFE_LEFT,1007),'Mundial Feminino 2027 • Brasil',font=font(21,True),fill='white'); pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True); im.save(out,'JPEG',quality=94,optimize=True)
    return readable and f.size>=MIN_TITLE_FONT and len(lines)<=MAX_TITLE_LINES, f.size, len(lines)

def main():
    events=load('dados.json',[]); news=load('noticias.json',[]); ledger=load('instagram/publicados.json',{'published':[]}); state=load('instagram/conteudo-conhecido.json',{'pending_new':[]}); catalog=load('instagram/imagens-curadas.json',{'items':[]})
    published={clean(x.get('key')) for x in ledger.get('published',[])}; pending=set(state.get('pending_new',[])); now=dt.datetime.now(dt.timezone.utc); stamps=[]
    for x in ledger.get('published',[]):
        try: stamps.append(dt.datetime.fromisoformat(clean(x.get('published_at')).replace('Z','+00:00')))
        except: pass
    if stamps and (now-max(stamps)).total_seconds()<3600: print('found=false'); print('reason=minimum_interval'); return 0
    curated={clean(x.get('idempotency_key')):x for x in catalog.get('items',[]) if x.get('reutilizacao_permitida') is True and all(clean(x.get(field)) for field in ('image_source_url','source_page_url','credito','licenca'))}
    ranked=candidates(events,news,published,pending)
    if not ranked: print('found=false'); print('reason=no_eligible_item'); return 0
    item=ranked[0]; c=curated.get(item['key']); s=slug(item['key']); art=f'instagram/artes/{s}.jpg'; post=f'instagram/fila/automatica/{s}.json'; batch='instagram/fila/automatica/lote-atual.json'; source_mode='fallback_visual'; semantic_ok=True; semantic_reason='text_art_no_external_photo'
    if c and c.get('semantic_image_ok') is not True:
        print('curated_image_rejected=semantic_image_ok_missing_or_false'); c=None
    if not c:
        c=find_commons_image(item)
        if c: print('auto_image_found='+clean(c.get('query')))
    if c:
        try:
            readable,font_size,line_count=make_photo_art(clean(c['image_source_url']),art,item['title'],item['type'],clean(c.get('credito'))); source_mode='auto_commons_photo' if c.get('auto_found') else 'curated_photo'; semantic_reason=clean(c.get('semantic_reason')) or 'curated_semantic_gate'
        except Exception as exc:
            print('photo_failed='+item['key']+':'+type(exc).__name__); readable,font_size,line_count=make_original_art(art,item['title'],item['type'],item['subtitle'],item['key']); source_mode='fallback_visual'; semantic_reason='photo_failed_fallback_text_art'
    else: readable,font_size,line_count=make_original_art(art,item['title'],item['type'],item['subtitle'],item['key'])
    title_ok=bool(readable and font_size>=MIN_TITLE_FONT and line_count<=MAX_TITLE_LINES)
    if not semantic_ok or not title_ok:
        print('found=false'); print('reason=quality_gate_failed'); print('SEMANTIC_IMAGE_OK='+str(bool(semantic_ok)).lower()); print('TITLE_READABILITY_OK='+str(bool(title_ok)).lower()); return 1
    common={'id':s,'idempotency_key':item['key'],'approved':True,'source_type':item['type'],'image_url':ROOT+art,'caption':item['caption'],'visual_mode':source_mode,'SEMANTIC_IMAGE_OK':True,'TITLE_READABILITY_OK':True,'semantic_reason':semantic_reason,'title_font_px':font_size,'title_lines':line_count}
    if source_mode in ('curated_photo','auto_commons_photo'):
        common.update({'image_source_url':clean(c['image_source_url']),'image_page_url':clean(c['source_page_url']),'image_credit':clean(c['credito']),'license_note':clean(c['licenca'])})
    else:
        common.update({'image_source_url':'','image_page_url':'','image_credit':'Arte própria do Radar Brasil 2027','license_note':'fallback_visual_original'})
    pathlib.Path(post).parent.mkdir(parents=True,exist_ok=True); pathlib.Path(post).write_text(json.dumps(common,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); pathlib.Path(batch).write_text(json.dumps({'posts':[post]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('visual_mode='+source_mode); print('SEMANTIC_IMAGE_OK=true'); print('TITLE_READABILITY_OK=true'); print('title_font_px='+str(font_size)); print('title_lines='+str(line_count)); print('found=true'); print('batch_file='+batch); return 0

if __name__=='__main__': raise SystemExit(main())
