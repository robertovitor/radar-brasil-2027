#!/usr/bin/env python3
"""Prepara um post do Radar Brasil 2027 com gates obrigatórios de semântica visual e legibilidade."""
from __future__ import annotations
import datetime as dt, difflib, hashlib, html, io, json, pathlib, re, urllib.parse, urllib.request, unicodedata
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from publicar_instagram import same_topic as publisher_same_topic

try:
    from instagram_visual_policy import (
        load_policy as load_visual_policy,
        render_owned_art,
        visual_mode as policy_visual_mode,
    )
except Exception:
    render_owned_art = None
    def load_visual_policy():
        return {
            "enabled": False,
            "fallback_to_legacy": True,
            "opportunity_instagram_enabled": False,
            "types": {},
        }
    def policy_visual_mode(kind, policy=None):
        return "legacy"

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
DEDUP_STOPWORDS=STOPWORDS|{
    'sobre','ate','até','apos','após','seu','sua','seus','suas','que','como','mais','menos',
    'novo','nova','novos','novas','confirma','confirmam','prepara','preparam','destaca',
    'adequacao','adequacoes','adequação','adequações','evento','notícia','noticia'
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
POLITICAL_IMAGE_BLOCKERS=(
    'politico','político','politica partidaria','política partidária','partido politico','partido político',
    'presidente da republica','presidente da república','vice-presidente','senador','senadora',
    'deputado','deputada','ministro','ministra','governador','governadora','prefeito','prefeita',
    'parlamentar','congresso nacional','senado federal','camara dos deputados','câmara dos deputados',
    'assembleia legislativa','plenário','plenario','palacio do planalto','palácio do planalto',
    'palacio','palácio','prefeitura','city hall','governo federal','governo estadual','governo municipal',
    'ministerio','ministério','secretaria de governo','centro administrativo municipal',
    'paco municipal','paço municipal','inauguracao','inauguração','cerimonia de assinatura',
    'cerimônia de assinatura','reuniao ministerial','reunião ministerial','sessao solene',
    'sessão solene','comicio','comício','campanha eleitoral'
)
WOMEN_CUP_MARKERS=(
    'copa do mundo feminina','mundial feminino','women world cup',"women's world cup",
    'fifa women','fifa female','copa feminina','feminina 2027','women 2027'
)
STADIUM_MARKERS=(
    'estadio','estádio','stadium','arena','maracana','maracanã','mineirao','mineirão',
    'mane garrincha','mané garrincha','fonte nova','castelao','castelão','beira-rio'
)
FIFA_CBF_MARKERS=(
    'fifa','confederacao brasileira de futebol','confederação brasileira de futebol',
    'selecao brasileira feminina','seleção brasileira feminina','cbf'
)
BRAZIL_PLACE_MARKERS=(
    'cidade','cityscape','skyline','ponto turistico','ponto turístico','tourist attraction',
    'monumento','monument','praca','praça','square','praia','beach','parque','park',
    'ponte','bridge','museu','museum','teatro','theatre','theater','centro cultural',
    'avenida','avenue','orla','waterfront','centro historico','centro histórico','historic center'
)
BRAZIL_MARKERS=(
    'brasil','brazil','brasilia','brasília','rio de janeiro','sao paulo','são paulo','salvador',
    'fortaleza','recife','belo horizonte','porto alegre','curitiba','belem','belém','manaus',
    'natal','goiania','goiânia','cuiaba','cuiabá'
)
VISUAL_QUERY_BLOCKERS=POLITICAL_IMAGE_BLOCKERS+(
    'governo','ministerio','ministério','senado','camara','câmara','lei','legislacao','legislação',
    'tributario','tributário','tributaria','tributária','imposto','decreto','bancada','prefeitura',
    'secretaria','politica publica','política pública'
)
# Compatibilidade com as camadas antigas: somente domínios visuais permitidos.
# Política e órgãos governamentais ficam explicitamente fora desta lista.
INSTITUTIONAL_MARKERS=STADIUM_MARKERS+FIFA_CBF_MARKERS+BRAZIL_PLACE_MARKERS

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

def title_from_post(post):
    caption=str(post.get('caption') or '').strip()
    if not caption: return ''
    return re.sub(r'^[^\wÀ-ÿ]+','',caption.splitlines()[0]).strip()

def dedup_tokens(value):
    ignored={norm(x) for x in DEDUP_STOPWORDS}
    tokens=[]
    for raw in re.findall(r'[a-z0-9áàâãéêíóôõúç]+',clean(value).casefold()):
        token=norm(raw)
        if len(token)<3 or token in ignored: continue
        tokens.append(token[:7])
    return set(tokens)

def duplicate_title(a,b):
    # Usa exatamente a mesma regra da trava final de publicação.
    # Assim, uma pauta que seria recusada por duplicidade semântica na etapa
    # de publicar já é retirada do ranking, e a mesma rodada segue para o
    # próximo candidato sem criar bloqueio permanente.
    return publisher_same_topic(a,b)

def published_titles(ledger):
    titles=[]
    for row in ledger.get('published',[]):
        p=pathlib.Path(clean(row.get('post_file')))
        if not p.exists(): continue
        try: title=title_from_post(json.loads(p.read_text(encoding='utf-8')))
        except Exception: continue
        if title: titles.append(title)
    return titles

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

OTHER_SPORT_CONTENT_BLOCKERS=('volei','volley','liga das nacoes de volei','basquete','basketball','automobilismo','formula 1','formula1','futsal','handebol','handball')
RADAR_FOOTBALL_CONTENT_MARKERS=('futebol feminino','selecao feminina','selecao brasileira feminina','copa do mundo feminina','copa feminina','mundial feminino','fifa women','women world cup','women s world cup')
def radar_content_ok(item):
    text=norm(' '.join(clean(v) for v in item.values()))
    if any(norm(x) in text for x in OTHER_SPORT_CONTENT_BLOCKERS):
        return any(norm(x) in text for x in RADAR_FOOTBALL_CONTENT_MARKERS)
    return True

ENGLISH_TITLE_MARKERS=(
    ' the ',' and ',' for ',' with ',' from ',' manager',' coordinator',' specialist',
    ' customer ',' care ',' ticketing',' general public',' operations',' programme',' program',
    ' world cup',' women ',' women\'s ',' stadium',' host city',' jobs',' job ',' careers',
)
PORTUGUESE_TEXT_MARKERS=(
    ' para ',' com ',' da ',' do ',' das ',' dos ',' no ',' na ',' em ',' uma ',' um ',
    ' oportunidade ',' trabalho ',' atendimento ',' público ',' ingressos ',' copa ',' futebol ',
)

def looks_english_title(value):
    t=' '+clean(value).casefold()+' '
    hits=sum(1 for marker in ENGLISH_TITLE_MARKERS if marker in t)
    pt=sum(1 for marker in PORTUGUESE_TEXT_MARKERS if marker in t)
    return hits>=2 and hits>pt

def looks_portuguese_text(value):
    t=' '+clean(value).casefold()+' '
    return sum(1 for marker in PORTUGUESE_TEXT_MARKERS if marker in t)>=2

def concise_portuguese_headline(value,max_chars=112):
    s=clean(value)
    if not s:
        return ''
    # Primeira frase; depois remove caudas explicativas completas para caber na arte.
    s=re.split(r'(?<=[.!?])\s+',s,maxsplit=1)[0].rstrip(' .')
    if len(s)<=max_chars:
        return s
    for sep in (';',' — ',' – ', ', com ', ', que ', ' com ', ' durante ', ' para '):
        pos=s.casefold().find(sep.casefold())
        if 38<=pos<=max_chars:
            return clean(s[:pos].rstrip(' ,;:-'))
    words=s.split()
    out=[]
    for word in words:
        candidate=' '.join(out+[word])
        if len(candidate)>max_chars:
            break
        out.append(word)
    return clean(' '.join(out).rstrip(' ,;:-'))

def art_title_pt(kind,title,summary='',organization='',category=''):
    original=clean(title)
    if not original or not looks_english_title(original):
        return original

    direct={
        'ticketing general public customer care manager':
            'Gerente de atendimento ao público na operação de ingressos',
    }
    mapped=direct.get(original.casefold())
    if mapped:
        return mapped

    summary=clean(summary)
    organization=clean(organization)
    category=clean(category)

    # Para vagas/oportunidades, o resumo editorial já está em português e é
    # fonte mais segura do que uma tradução literal incompleta do cargo.
    if kind=='oportunidade' and summary and looks_portuguese_text(summary):
        match=re.search(r'com atuação em\s+([^.;]+)',summary,flags=re.I)
        if match and organization:
            role=concise_portuguese_headline(match.group(1),82)
            if role:
                return clean(f'{organization} abre vaga para {role}')
        if category.casefold()=='trabalho' and organization:
            if 'copa' in norm(summary):
                return clean(f'{organization} abre oportunidade de trabalho para a Copa Feminina 2027')
            return clean(f'Oportunidade de trabalho na {organization}')
        candidate=concise_portuguese_headline(summary)
        if candidate:
            return candidate

    # Notícias com título estrangeiro usam o resumo editorial em português.
    if kind=='noticia' and summary and looks_portuguese_text(summary):
        candidate=concise_portuguese_headline(summary)
        if candidate:
            return candidate

    # Fail closed editorial: nunca coloca inglês na arte.
    if kind=='oportunidade':
        return clean(f'Oportunidade {("na "+organization) if organization else "para a Copa Feminina 2027"}')
    if kind=='noticia':
        return 'Notícia sobre a Copa Feminina 2027'
    return 'Radar Brasil 2027'

def candidates(events,news,opportunities,published,pending,prior_titles=()):
    out=[]
    today_brt=dt.datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    for x in events:
        title=clean(x.get('Titulo')); d=date(x.get('Data')); key='instagram:evento:'+clean(x.get('ID') or title).casefold()
        if title and d and key not in published and not base(x) and not any(duplicate_title(title,old) for old in prior_titles):
            place=', '.join(filter(None,[clean(x.get('Local')),clean(x.get('Cidade')),clean(x.get('UF'))]))
            subtitle=(clean(x.get('DataBR')) or d.strftime('%d/%m/%Y'))+' • '+(place or 'Local a definir')
            search_context=' '.join(filter(None,[title,clean(x.get('Cidade')),clean(x.get('UF')),clean(x.get('Local')),clean(x.get('Organizador'))]))
            event_date=clean(x.get('DataBR')) or d.strftime('%d/%m/%Y')
            out.append(dict(key=key,title=title,art_title=title,date=d,type='evento',subtitle=subtitle,search_context=search_context,visual_places=place,display_date=event_date,display_place=place or 'Local a definir',caption=f"📅 {title}\n\nQuando: {event_date}\nOnde: {place or 'Local a definir'}\n\n{clean(x.get('Observacoes'))}\n\nFonte: {clean(x.get('Organizador')) or 'Radar Brasil 2027'}\n\n#RadarBrasil2027 #MundialFeminino2027 #FutebolFeminino\n\nSaiba mais pelo link da Bio"))
    for x in news:
        title=clean(x.get('Titulo')); d=date(x.get('Data')); key='instagram:noticia:'+clean(x.get('Link') or title).casefold()
        if title and d and d<=dt.datetime.now(dt.timezone.utc).date() and key not in published and not base(x) and radar_content_ok(x) and not any(duplicate_title(title,old) for old in prior_titles):
            subtitle=(clean(x.get('Veiculo')) or 'Radar Brasil 2027')+' • '+d.strftime('%d/%m/%Y')
            summary=clean(x.get('Resumo'))
            art_title=art_title_pt('noticia',title,summary=summary)
            search_context=' '.join(filter(None,[title,clean(x.get('Tema')),clean(x.get('CidadeUF')),clean(x.get('Veiculo'))]))
            out.append(dict(key=key,title=title,art_title=art_title,date=d,type='noticia',subtitle=subtitle,search_context=search_context,visual_places=clean(x.get('CidadeUF')),display_date=d.strftime('%d/%m/%Y'),display_place=clean(x.get('CidadeUF')),caption=f"📰 {title}\n\n{summary}\n\nFonte: {clean(x.get('Veiculo'))}\n\n#RadarBrasil2027 #MundialFeminino2027 #FutebolFeminino\n\nSaiba mais pelo link da Bio"))
    for x in opportunities:
        title=clean(x.get('Titulo'))
        status=norm(x.get('Status'))
        link=clean(x.get('Link'))
        if not title or not link or 'abert' not in status:
            continue
        deadline=date(x.get('PrazoInscricao'))
        if deadline and deadline < today_brt:
            continue
        discovered=date(x.get('DataDescoberta')) or date(x.get('UltimaVerificacao')) or today_brt
        key='instagram:oportunidade:'+clean(x.get('ID') or link or title).casefold()
        if key in published or any(duplicate_title(title,old) for old in prior_titles):
            continue
        category=clean(x.get('Categoria')) or 'Oportunidade'
        organization=clean(x.get('Organizacao')) or clean(x.get('Fonte')) or 'Radar Brasil 2027'
        modality=clean(x.get('Modalidade'))
        reach=clean(x.get('CidadeUF')) or clean(x.get('Abrangencia')) or 'Brasil'
        where=' • '.join(v for v in (modality,reach) if v)
        deadline_text='Prazo: '+deadline.strftime('%d/%m/%Y') if deadline else 'Inscrições abertas'
        subtitle=' • '.join(v for v in (category,organization) if v)
        summary=clean(x.get('Resumo'))
        art_title=art_title_pt('oportunidade',title,summary=summary,organization=organization,category=category)
        search_context=' '.join(filter(None,[title,category,organization,modality,reach]))
        out.append(dict(
            key=key,title=title,art_title=art_title,date=discovered,type='oportunidade',subtitle=subtitle,
            search_context=search_context,visual_places=reach,display_date=deadline_text,
            display_place=where,category=category,organization=organization,
            caption=f"🎯 {title}\n\nTipo: {category}\nOrganização: {organization}\n{('Modalidade: '+modality) if modality else ''}\n{deadline_text}\n\n{summary}\n\nFonte: {clean(x.get('Fonte')) or organization}\n\n#RadarBrasil2027 #Oportunidades #CopaFeminina2027 #FutebolFeminino\n\nSaiba mais pelo link da Bio"
        ))
    pending_order={clean(key):idx for idx,key in enumerate(pending)}
    def rank(i):
        # Evento que acontece hoje tem prioridade editorial sobre a fila normal.
        # Depois dele, preserva exatamente a ordenação histórica da fila.
        # A reconciliação estrita de tentativa incerta na Meta continua sendo
        # aplicada depois e permanece acima de pauta nova por segurança.
        today_event_tie=0 if i['type']=='evento' and i['date']==today_brt else 1
        pending_idx=pending_order.get(i['key'])
        pending_tie=0 if pending_idx is not None else 1
        recent_pending=-(pending_idx if pending_idx is not None else -1)
        type_tie={'evento':0,'noticia':1,'oportunidade':2}.get(i['type'],3)
        return (today_event_tie,-i['date'].toordinal(),pending_tie,recent_pending,type_tie,i['key'])
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

def commons_queries(text,places=''):
    """Consulta apenas domínios visuais permitidos, nunca política ou governo."""
    blocked={norm(x) for x in VISUAL_QUERY_BLOCKERS}
    uniq=[w for w in distinct_terms(text) if norm(w) not in blocked]
    place=clean(places)
    queries=[]
    def add(q):
        q=clean(q)
        if q and norm(q) not in {norm(x) for x in queries}: queries.append(q)
    if uniq:
        add(' '.join(uniq[:5])+' futebol feminino Brasil')
        add(' '.join(uniq[:3])+' Copa do Mundo Feminina')
    if place:
        add(place+' estádio futebol feminino')
        add(place+' cidade ponto turístico Brasil')
    add('Copa do Mundo Feminina FIFA 2027 Brasil')
    add('CBF futebol feminino Brasil')
    add('Seleção Brasileira feminina futebol')
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
    # A consulta não entra no descritor: somente os metadados reais da imagem
    # podem aprovar o gate semântico.
    fields=[clean(page.get('title')),strip_html(meta.get('ObjectName',{}).get('value')),strip_html(meta.get('ImageDescription',{}).get('value')),strip_html(meta.get('Categories',{}).get('value'))]
    return ' '.join(x for x in fields if x)

def restricted_visual_domain(text,item_text=''):
    desc=norm(text); context=norm(item_text)
    def has_marker(markers):
        # Limites de palavra evitam que "men football" bloqueie "women football".
        return any(re.search(r'(?<![a-z0-9])'+re.escape(norm(x))+r'(?![a-z0-9])',desc) for x in markers)
    if has_marker(POLITICAL_IMAGE_BLOCKERS):
        return False,'politics_or_government_visual_blocked'
    if has_marker(MALE_BLOCKERS):
        return False,'male_or_mens_football_blocker'
    female=has_marker(FEMALE_MARKERS)
    women_cup=has_marker(WOMEN_CUP_MARKERS)
    fifa_cbf=has_marker(FIFA_CBF_MARKERS)
    stadium=has_marker(STADIUM_MARKERS)
    brazil_place=has_marker(BRAZIL_PLACE_MARKERS)
    brazil=has_marker(BRAZIL_MARKERS)
    context_terms={norm(x) for x in distinct_terms(context)}
    desc_terms={norm(x) for x in distinct_terms(desc)}
    related=bool(context_terms & desc_terms)
    stadium_ok=stadium and (brazil or related)
    place_ok=brazil_place and (brazil or related)
    if female or women_cup:
        return True,'women_football_or_womens_cup'
    if fifa_cbf:
        return True,'fifa_or_cbf'
    if stadium_ok:
        return True,'relevant_stadium'
    if place_ok:
        return True,'relevant_brazilian_city_or_landmark'
    return False,'outside_restricted_visual_domain'

def curated_image_policy_ok(item,image):
    descriptor=' '.join(filter(None,[
        clean(image.get('source_page_url')),clean(image.get('image_source_url')),
        clean(image.get('justificativa')),clean(image.get('visual_description'))
    ]))
    return restricted_visual_domain(descriptor,(item.get('search_context') or '')+' '+item.get('visual_places',''))

def semantic_image_ok(item,page,meta,query):
    # query é mantida apenas para auditoria; não pode influenciar a aprovação.
    descriptor=commons_descriptor(page,meta)
    return restricted_visual_domain(descriptor,(item.get('search_context') or '')+' '+item.get('visual_places',''))

def find_commons_image(item):
    search_context=item.get('search_context') or item['title']
    for query in commons_queries(search_context,item.get('visual_places','')):
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


HOST_CITY_ALIASES={
    'belo horizonte':('belo horizonte','bh'),
    'brasilia':('brasilia','brasília'),
    'fortaleza':('fortaleza',),
    'porto alegre':('porto alegre',),
    'recife':('recife','sao lourenco da mata','são lourenço da mata'),
    'rio de janeiro':('rio de janeiro','rio'),
    'salvador':('salvador',),
    'sao paulo':('sao paulo','são paulo'),
}
HOST_STADIUM_ALIASES={
    'mineirao':('mineirao','mineirão'),
    'mane garrincha':('mane garrincha','mané garrincha','estadio nacional de brasilia','estádio nacional de brasília'),
    'castelao':('castelao','castelão','arena castelao','arena castelão'),
    'beira-rio':('beira-rio','beira rio'),
    'arena pernambuco':('arena pernambuco',),
    'maracana':('maracana','maracanã'),
    'fonte nova':('fonte nova','arena fonte nova'),
    'neo quimica arena':('neo quimica arena','neo química arena','arena corinthians'),
}
BRAZIL_WOMEN_BANK_MARKERS=(
    "brazil women's national football team","brazil women soccer team",
    "brazil women football","team brazil","teambrazil",
    "selecao brasileira feminina","seleção brasileira feminina",
    "atletas da selecao brasileira de futebol feminino",
    "atletas da seleção brasileira de futebol feminino",
)
BRAZIL_WOMEN_PLAYER_MARKERS=(
    'marta','formiga','debinha','cristiane','kerolin','adriana','gabi nunes','tamires',
    'bia zaneratto','andressa alves','ary borges','rafaelle','ludmila','geyse','angelina',
    'yasmim','tarciane','amanda gutierres','lorena','luciana','barbara','bárbara'
)
BANK_FOREIGN_ONLY_BLOCKERS=(
    'german football team','germany women','zimbabwe','sweden women','usa women','canada women',
    'france women','england women','spain women','japan women'
)

def _contains_phrase(text,values):
    n=norm(text)
    return any(norm(v) in n for v in values)

def _specific_host_city(text):
    n=norm(text)
    for canonical,aliases in HOST_CITY_ALIASES.items():
        if any(norm(alias) in n for alias in aliases):
            return canonical
    return ''

def _specific_host_stadium(text):
    n=norm(text)
    for canonical,aliases in HOST_STADIUM_ALIASES.items():
        if any(norm(alias) in n for alias in aliases):
            return canonical
    return ''

def classify_real_news_topic(item):
    text=' '.join([
        clean(item.get('title')),clean(item.get('search_context')),
        clean(item.get('visual_places')),clean(item.get('caption'))
    ])
    n=norm(text)
    stadium=_specific_host_stadium(text)
    if stadium:
        return 'estadio_sede',stadium
    city=_specific_host_city(text)
    # Seleção só ganha da cidade quando há sinal explícito da equipe feminina.
    selection_explicit=(
        'selecao brasileira feminina' in n or
        'selecao feminina' in n or
        ('convocacao' in n and 'brasil' in n) or
        ('amistoso' in n and 'brasil' in n)
    )
    if selection_explicit:
        return 'selecao_brasileira_feminina',''
    if city:
        return 'cidade_sede',city
    return 'outro',''

def recent_real_news_photo(ledger):
    for row in reversed(ledger.get('published',[])):
        if not isinstance(row,dict): continue
        p=pathlib.Path(clean(row.get('post_file')))
        if not p.exists(): continue
        try: post=load(p,{})
        except Exception: continue
        if clean(post.get('source_type'))!='noticia':
            continue
        return clean(post.get('visual_mode'))=='news_real_bank_v1'
    return False

def used_real_image_refs(ledger):
    used=set()
    for row in ledger.get('published',[]):
        if not isinstance(row,dict): continue
        p=pathlib.Path(clean(row.get('post_file')))
        if not p.exists(): continue
        try: post=load(p,{})
        except Exception: continue
        for field in ('bank_image_id','image_source_url','image_page_url'):
            value=clean(post.get(field))
            if value: used.add(value)
    return used

def _bank_descriptor(row):
    return ' '.join([
        clean(row.get('titulo')),clean(row.get('pessoa_local')),clean(row.get('observacoes')),
        clean(row.get('fonte')),clean(row.get('atribuicao'))
    ])

def _bank_row_base_ok(row,used):
    if clean(row.get('instagram_ok')).upper()!='SIM':
        return False
    if clean(row.get('status_licenca')).upper() not in ('APROVADA','APROVADA_AUTO'):
        return False
    url=clean(row.get('url_thumbnail') or row.get('url_direta'))
    page=clean(row.get('pagina_origem'))
    image_id=clean(row.get('id'))
    if not url or not page or not image_id:
        return False
    if image_id in used or url in used or page in used:
        return False
    desc=_bank_descriptor(row)
    if _contains_phrase(desc,POLITICAL_IMAGE_BLOCKERS):
        return False
    if _contains_phrase(desc,MALE_BLOCKERS):
        return False
    return True

def _bank_selection_ok(row):
    desc=_bank_descriptor(row)
    n=norm(desc)
    strong=_contains_phrase(desc,BRAZIL_WOMEN_BANK_MARKERS) or any(norm(x) in n for x in BRAZIL_WOMEN_PLAYER_MARKERS)
    if not strong:
        return False
    # Títulos claramente de outra seleção são rejeitados, mesmo quando a descrição cita Brasil.
    title=clean(row.get('titulo'))
    if _contains_phrase(title,BANK_FOREIGN_ONLY_BLOCKERS) and not _contains_phrase(title,BRAZIL_WOMEN_BANK_MARKERS):
        return False
    return True

def _bank_place_ok(row,topic,specific):
    if not specific:
        return False
    desc=_bank_descriptor(row)
    category=clean(row.get('categoria'))
    if topic=='cidade_sede':
        if category!='cidades_sedes_2027':
            return False
        aliases=HOST_CITY_ALIASES.get(specific,(specific,))
        return _contains_phrase(desc,aliases)
    if topic=='estadio_sede':
        if category!='estadios_sedes_2027':
            return False
        aliases=HOST_STADIUM_ALIASES.get(specific,(specific,))
        return _contains_phrase(desc,aliases)
    return False

def _news_bank_context(item):
    return ' '.join([
        clean(item.get('title')),
        clean(item.get('search_context')),
        clean(item.get('visual_places')),
    ])

def _news_bank_score(item,row,topic,specific):
    """Pontua aderência do catálogo. Retorna negativo quando a imagem é insegura."""
    desc=_bank_descriptor(row)
    context=_news_bank_context(item)
    category=clean(row.get('categoria'))

    allowed,reason=restricted_visual_domain(desc,context)
    if not allowed:
        return -1,reason

    context_tokens={norm(x) for x in distinct_terms(context)}
    desc_tokens={norm(x) for x in distinct_terms(desc)}
    overlap=len(context_tokens & desc_tokens)

    female_desc=_contains_phrase(desc,FEMALE_MARKERS)
    women_cup_desc=_contains_phrase(desc,WOMEN_CUP_MARKERS)
    context_female=_contains_phrase(context,FEMALE_MARKERS)
    context_cup=_contains_phrase(context,WOMEN_CUP_MARKERS) or 'copa feminina' in norm(context) or 'mundial feminino' in norm(context)
    context_fans=any(x in norm(context) for x in ('torcida','torcedor','torcedora','torcedores','fas','fãs','publico','público','engajamento'))
    desc_fans=any(x in norm(desc) for x in ('torcida','torcedor','torcedora','torcedores','fans','supporters','spectators'))

    if topic=='cidade_sede':
        if not _bank_place_ok(row,topic,specific):
            return -1,'city_exact_match_required'
        return 100,'host_city_exact_match'

    if topic=='estadio_sede':
        if not _bank_place_ok(row,topic,specific):
            return -1,'stadium_exact_match_required'
        return 100,'host_stadium_exact_match'

    if category=='selecao_brasileira':
        if not _bank_selection_ok(row):
            return -1,'brazil_women_selection_gate'
        score=8*overlap
        if topic=='selecao_brasileira_feminina':
            score+=28
        if overlap>=1:
            score+=10
        return score,'brazil_women_selection_catalog'

    if category=='futebol_feminino':
        if not female_desc and not women_cup_desc:
            return -1,'female_metadata_required'
        score=8*overlap
        if context_female:
            score+=8
        if context_cup and women_cup_desc:
            score+=5
        return score,'women_football_catalog'

    if category.startswith('copa_feminina_'):
        if not women_cup_desc and not female_desc:
            return -1,'womens_world_cup_metadata_required'
        score=8*overlap
        if context_cup:
            score+=8
        if _contains_phrase(desc,BANK_FOREIGN_ONLY_BLOCKERS) and overlap<2:
            return -1,'foreign_team_without_context_match'
        return score,'womens_world_cup_catalog'

    if category=='torcida':
        if not context_fans or not desc_fans:
            return -1,'fan_context_required'
        if not female_desc and not women_cup_desc:
            return -1,'women_fan_metadata_required'
        return 20+8*overlap,'women_fans_catalog'

    return -1,'unsupported_catalog_category'

def choose_news_bank_image(item,bank_catalog,ledger):
    if clean(item.get('type'))!='noticia':
        return None

    topic,specific=classify_real_news_topic(item)
    used=used_real_image_refs(ledger)
    candidates=[]

    for row in bank_catalog if isinstance(bank_catalog,list) else []:
        if not isinstance(row,dict) or not _bank_row_base_ok(row,used):
            continue
        score,reason=_news_bank_score(item,row,topic,specific)
        if score < 16:
            continue
        seed=hashlib.sha256((clean(item.get('key'))+'|'+clean(row.get('id'))).encode('utf-8')).hexdigest()
        candidates.append((-score,seed,row,reason))

    if not candidates:
        print('news_catalog_no_safe_match='+topic+(':'+specific if specific else ''))
        return None

    candidates.sort(key=lambda x:(x[0],x[1]))
    neg_score,_,row,reason=candidates[0]
    score=-neg_score
    print('news_catalog_priority_match='+clean(row.get('id'))+':score='+str(score)+':'+reason)
    return {
        'image_source_url':clean(row.get('url_thumbnail') or row.get('url_direta')),
        'source_page_url':clean(row.get('pagina_origem')),
        'credito':clean(row.get('atribuicao') or row.get('autor') or row.get('fonte')),
        'licenca':clean(row.get('licenca')),
        'bank_image_id':clean(row.get('id')),
        'bank_topic':topic if topic!='outro' else clean(row.get('categoria')),
        'bank_specific':specific,
        'bank_score':score,
        'bank_reason':reason,
    }

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
    events=load('dados.json',[]); news=load('noticias.json',[]); opportunities=load('oportunidades.json',[]); visual_policy=load_visual_policy(); ledger=load('instagram/publicados.json',{'published':[]}); state=load('instagram/conteudo-conhecido.json',{'pending_new':[]}); catalog=load('instagram/imagens-curadas.json',{'items':[]}); bank_catalog=load('banco_imagens/catalogo.json',[]); blocked=load('instagram/bloqueados-publicacao.json',{'blocked_keys':[]}); reservations=load('instagram/reservas-publicacao.json',{'reservations':[]})
    now=dt.datetime.now(dt.timezone.utc)
    ledger_keys={clean(x.get('key')) for x in ledger.get('published',[]) if isinstance(x,dict)}
    active_reservations=set()
    strict_pending=set()
    reservation_ttl=dt.timedelta(hours=2)
    for row in reservations.get('reservations',[]):
        if not isinstance(row,dict):
            continue
        key=clean(row.get('key'))
        if not key or key in ledger_keys:
            continue
        strict=bool(row.get('requires_strict_reconciliation'))
        uncertain=bool(row.get('uncertain_after_meta'))
        if strict:
            strict_pending.add(key)
        reconciliation_ready=False
        if strict and uncertain:
            raw_until=clean(row.get('blocked_until'))
            try:
                until=dt.datetime.fromisoformat(raw_until.replace('Z','+00:00'))
                if until.tzinfo is None: until=until.replace(tzinfo=dt.timezone.utc)
                reconciliation_ready=now>=until.astimezone(dt.timezone.utc)
            except (ValueError,TypeError):
                reconciliation_ready=not raw_until
        raw=clean(row.get('last_attempt_at') or row.get('reserved_at'))
        try:
            stamp=dt.datetime.fromisoformat(raw.replace('Z','+00:00'))
            if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=dt.timezone.utc)
            if now-stamp.astimezone(dt.timezone.utc) < reservation_ttl and not reconciliation_ready:
                active_reservations.add(key)
        except (ValueError,TypeError):
            # Reserva sem timestamp válido permanece bloqueada: falhar fechado evita duplicação.
            if not reconciliation_ready:
                active_reservations.add(key)
    published=ledger_keys|{clean(x) for x in blocked.get('blocked_keys',[])}|active_reservations
    pending=[clean(key) for key in state.get('pending_new',[])]; stamps=[]
    for x in ledger.get('published',[]):
        if not isinstance(x,dict): continue
        raw=clean(x.get('published_at') or x.get('reconciled_at'))
        try:
            stamp=dt.datetime.fromisoformat(raw.replace('Z','+00:00'))
            if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=dt.timezone.utc)
            stamps.append(stamp.astimezone(dt.timezone.utc))
        except (ValueError,TypeError): pass
    if stamps and (now-max(stamps)).total_seconds()<3600: print('found=false'); print('reason=minimum_interval'); return 0
    # Fila manual opcional para publicacoes excepcionais. Quando vazia ou ausente,
    # o comportamento historico da selecao automatica permanece inalterado.
    manual_queue=load('instagram/fila/manual-pendente.json',{'posts':[]})
    manual_candidates=[]
    for manual_path in manual_queue.get('posts',[]) if isinstance(manual_queue,dict) else []:
        p=pathlib.Path(clean(manual_path))
        if not p.exists():
            continue
        try:
            manual_post=load(p,{})
        except Exception:
            continue
        manual_key=clean(manual_post.get('idempotency_key') or manual_post.get('id'))
        if not manual_key or manual_key in published:
            continue
        if manual_post.get('approved') is not True:
            continue
        if not clean(manual_post.get('image_url')) or not clean(manual_post.get('caption')):
            continue
        manual_candidates.append((manual_key,p))
    curated={clean(x.get('idempotency_key')):x for x in catalog.get('items',[]) if x.get('reutilizacao_permitida') is True and all(clean(x.get(field)) for field in ('image_source_url','source_page_url','credito','licenca'))}
    ranked=candidates(events,news,opportunities if visual_policy.get('opportunity_instagram_enabled') else [],published,pending,published_titles(ledger))
    # Tentativas ambíguas liberadas pelo cooldown vêm sempre antes de pauta nova.
    ranked.sort(key=lambda item: 0 if item['key'] in strict_pending else 1)
    # Reconciliações realmente elegíveis continuam acima de post manual novo.
    # Reservas históricas que já não estão no ranking não bloqueiam a fila manual.
    strict_manual=[row for row in manual_candidates if row[0] in strict_pending]
    strict_ranked=[item for item in ranked if item['key'] in strict_pending]
    chosen_manual=(strict_manual[0] if strict_manual else (manual_candidates[0] if manual_candidates and not strict_ranked else None))
    if chosen_manual:
        manual_key,p=chosen_manual
        batch=pathlib.Path('instagram/fila/automatica/lote-atual.json')
        batch.parent.mkdir(parents=True,exist_ok=True)
        batch.write_text(json.dumps({'posts':[str(p)]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('priority_manual_post='+manual_key)
        print('found=true')
        print('batch_file='+str(batch))
        return 0
    if ranked and ranked[0]['key'] in strict_pending:
        print('priority_strict_reconciliation='+ranked[0]['key'])
    if not ranked: print('found=false'); print('reason=no_eligible_item'); return 0
    fallback_item=ranked[0]
    # Notícias priorizam o catálogo editorial inteiro. O catálogo só vence a
    # arte própria quando há aderência material no metadata e imagem não repetida.
    # Sem match seguro, o fallback permanece a arte ilustrada do Radar.
    if clean(fallback_item.get('type'))=='noticia':
        bank_image=choose_news_bank_image(fallback_item,bank_catalog,ledger)
        if bank_image:
            item=fallback_item
            s=slug(item['key']); art=f'instagram/artes/{s}.jpg'; post=f'instagram/fila/automatica/{s}.json'; batch='instagram/fila/automatica/lote-atual.json'
            try:
                readable,font_size,line_count=make_photo_art(
                    clean(bank_image.get('image_source_url')),art,clean(item.get('art_title') or item['title']),item['type'],clean(bank_image.get('credito'))
                )
                title_ok=bool(readable and font_size>=MIN_TITLE_FONT and line_count<=MAX_TITLE_LINES)
                if title_ok:
                    common={
                        'id':s,'idempotency_key':item['key'],'approved':True,'source_type':'noticia',
                        'image_url':ROOT+art,'caption':item['caption'],'visual_mode':'news_real_bank_v1',
                        'SEMANTIC_IMAGE_OK':True,'TITLE_READABILITY_OK':True,
                        'semantic_reason':'catalog_priority:'+clean(bank_image.get('bank_reason') or bank_image.get('bank_topic')),
                        'title_font_px':font_size,'title_lines':line_count,
                        'image_source_url':clean(bank_image.get('image_source_url')),
                        'image_page_url':clean(bank_image.get('source_page_url')),
                        'image_credit':clean(bank_image.get('credito')),
                        'license_note':clean(bank_image.get('licenca')),
                        'bank_image_id':clean(bank_image.get('bank_image_id')),
                        'bank_topic':clean(bank_image.get('bank_topic')),
                        'bank_specific':clean(bank_image.get('bank_specific')),
                        'bank_score':bank_image.get('bank_score'),
                        'original_title':item['title'],
                        'art_title':clean(item.get('art_title') or item['title']),
                        'title_translated_to_pt':clean(item.get('art_title') or item['title']) != clean(item['title']),
                    }
                    pathlib.Path(post).parent.mkdir(parents=True,exist_ok=True)
                    pathlib.Path(post).write_text(json.dumps(common,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    pathlib.Path(batch).write_text(json.dumps({'posts':[post]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    print('visual_mode=news_real_bank_v1')
                    print('news_real_bank_image_id='+clean(bank_image.get('bank_image_id')))
                    print('news_real_bank_topic='+clean(bank_image.get('bank_topic')))
                    print('SEMANTIC_IMAGE_OK=true')
                    print('TITLE_READABILITY_OK=true')
                    print('found=true')
                    print('batch_file='+batch)
                    return 0
                print('news_real_bank_rejected=title_readability')
            except Exception as exc:
                print('news_real_bank_failed='+type(exc).__name__)
            print('news_real_bank_fallback=illustrated_art')
    owned_mode=policy_visual_mode(fallback_item.get('type'),visual_policy)
    if render_owned_art is not None and owned_mode != 'legacy':
        item=fallback_item
        s=slug(item['key']); art=f'instagram/artes/{s}.jpg'; post=f'instagram/fila/automatica/{s}.json'; batch='instagram/fila/automatica/lote-atual.json'
        try:
            readable,font_size,line_count,owned_meta=render_owned_art(
                art,item,font=font,wrap=wrap,fit_title=fit_title,policy=visual_policy
            )
            title_ok=bool(readable and font_size>=MIN_TITLE_FONT and line_count<=MAX_TITLE_LINES)
            if not title_ok:
                raise RuntimeError('owned_art_title_readability_failed')
            common={
                'id':s,'idempotency_key':item['key'],'approved':True,'source_type':item['type'],
                'image_url':ROOT+art,'caption':item['caption'],'SEMANTIC_IMAGE_OK':True,
                'TITLE_READABILITY_OK':True,'title_font_px':font_size,'title_lines':line_count,
                'image_source_url':'','image_page_url':'',
                'original_title':item['title'],
                'art_title':clean(item.get('art_title') or item['title']),
                'title_translated_to_pt':clean(item.get('art_title') or item['title']) != clean(item['title'])
            }
            common.update(owned_meta)
            pathlib.Path(post).parent.mkdir(parents=True,exist_ok=True)
            pathlib.Path(post).write_text(json.dumps(common,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            pathlib.Path(batch).write_text(json.dumps({'posts':[post]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print('visual_policy_mode='+owned_mode)
            print('visual_mode='+clean(common.get('visual_mode')))
            print('SEMANTIC_IMAGE_OK=true')
            print('TITLE_READABILITY_OK=true')
            print('title_font_px='+str(font_size))
            print('title_lines='+str(line_count))
            print('found=true')
            print('batch_file='+batch)
            return 0
        except Exception as exc:
            print('owned_art_failed='+item['key']+':'+type(exc).__name__)
            if not visual_policy.get('fallback_to_legacy',True):
                print('found=false'); print('reason=owned_art_failed'); return 1
            print('owned_art_fallback_to_legacy=true')
    # Prioriza conteúdo que possua fotografia real válida. Só usa a arte textual
    # quando nenhum dos itens elegíveis tiver imagem segura e não repetida.
    fallback_item=ranked[0]; item=None; c=None
    # Evento que acontece hoje tem prioridade editorial absoluta. A disponibilidade
    # de foto pode definir a forma do post, nunca fazer uma pauta menos urgente furar
    # a fila. Mantém intactas deduplicação, reserva, cooldown e reconciliação Meta.
    today_brt=dt.datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    today_event=(fallback_item.get('type')=='evento' and fallback_item.get('date')==today_brt)
    image_candidates=[fallback_item] if today_event else ranked
    if today_event:
        print('priority_event_today='+fallback_item['key'])
    for candidate in image_candidates:
        candidate_image=curated.get(candidate['key'])
        if candidate_image:
            policy_ok,policy_reason=curated_image_policy_ok(candidate,candidate_image)
            if not policy_ok:
                print('curated_image_rejected='+policy_reason+':'+candidate['key']); candidate_image=None
            else:
                candidate_image=dict(candidate_image)
                candidate_image['semantic_reason']=policy_reason
        if not candidate_image:
            candidate_image=find_commons_image(candidate)
            if candidate_image: print('auto_image_found='+clean(candidate_image.get('query')))
        if candidate_image:
            item=candidate; c=candidate_image
            print('real_photo_candidate_selected='+item['key'])
            break
        print('real_photo_unavailable='+candidate['key'])
    if item is None:
        item=fallback_item
        print('fallback_visual_selected_after_exhausting_candidates='+item['key'])
    s=slug(item['key']); art=f'instagram/artes/{s}.jpg'; post=f'instagram/fila/automatica/{s}.json'; batch='instagram/fila/automatica/lote-atual.json'; source_mode='fallback_visual'; semantic_ok=True; semantic_reason='text_art_no_external_photo'
    if c:
        try:
            readable,font_size,line_count=make_photo_art(clean(c['image_source_url']),art,clean(item.get('art_title') or item['title']),item['type'],clean(c.get('credito'))); source_mode='auto_commons_photo' if c.get('auto_found') else 'curated_photo'; semantic_reason=clean(c.get('semantic_reason')) or 'curated_semantic_gate'
        except Exception as exc:
            print('photo_failed='+item['key']+':'+type(exc).__name__); readable,font_size,line_count=make_original_art(art,clean(item.get('art_title') or item['title']),item['type'],item['subtitle'],item['key']); source_mode='fallback_visual'; semantic_reason='photo_failed_fallback_text_art'
    else: readable,font_size,line_count=make_original_art(art,item['title'],item['type'],item['subtitle'],item['key'])
    title_ok=bool(readable and font_size>=MIN_TITLE_FONT and line_count<=MAX_TITLE_LINES)
    if not semantic_ok or not title_ok:
        print('found=false'); print('reason=quality_gate_failed'); print('SEMANTIC_IMAGE_OK='+str(bool(semantic_ok)).lower()); print('TITLE_READABILITY_OK='+str(bool(title_ok)).lower()); return 1
    common={'id':s,'idempotency_key':item['key'],'approved':True,'source_type':item['type'],'image_url':ROOT+art,'caption':item['caption'],'visual_mode':source_mode,'SEMANTIC_IMAGE_OK':True,'TITLE_READABILITY_OK':True,'semantic_reason':semantic_reason,'title_font_px':font_size,'title_lines':line_count,'original_title':item['title'],'art_title':clean(item.get('art_title') or item['title']),'title_translated_to_pt':clean(item.get('art_title') or item['title']) != clean(item['title'])}
    if source_mode in ('curated_photo','auto_commons_photo'):
        common.update({'image_source_url':clean(c['image_source_url']),'image_page_url':clean(c['source_page_url']),'image_credit':clean(c['credito']),'license_note':clean(c['licenca'])})
    else:
        common.update({'image_source_url':'','image_page_url':'','image_credit':'Arte própria do Radar Brasil 2027','license_note':'fallback_visual_original'})
    pathlib.Path(post).parent.mkdir(parents=True,exist_ok=True); pathlib.Path(post).write_text(json.dumps(common,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); pathlib.Path(batch).write_text(json.dumps({'posts':[post]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('visual_mode='+source_mode); print('SEMANTIC_IMAGE_OK=true'); print('TITLE_READABILITY_OK=true'); print('title_font_px='+str(font_size)); print('title_lines='+str(line_count)); print('found=true'); print('batch_file='+batch); return 0

if __name__=='__main__': raise SystemExit(main())
