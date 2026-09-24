#!/usr/bin/env python3
"""v5.5 — fonte primária estrutural + extração segura de eventos da Seleção Feminina.

Correção cirúrgica:
- mantém todo o núcleo v5.4 e as 2 leituras Airtable;
- consulta/valida a fonte oficial CBF antes dos agregadores;
- permite que notícia confiável já descoberta materialize eventos futuros conhecidos;
- persiste explicitamente eventos extraídos ao fim da pesquisa, sem depender do monkey-patch de dump;
- deduplicação de notícias e eventos permanece independente;
- Google News permanece fallback;
- não altera Merge, Alertas, Instagram, Saúde, schedules ou limites de frescor.
"""
import importlib.util
import html
import json
import re
import urllib.parse
import urllib.request
import ssl
from pathlib import Path

V54_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v5_4.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v5_4', V54_SCRIPT)
v54 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v54)
pe = v54.pe

# Fontes editoriais adicionais observadas na auditoria. Escopo propositalmente
# estreito: não cria novas leituras Airtable nem amplia a confiança para domínios
# desconhecidos. As pautas continuam sujeitas a relevância, frescor e deduplicação.
_ADDITIONAL_TRUSTED_DOMAINS = (
    'fpf-pe.com.br',
    'itatiaia.com.br',
    'gzh.com.br',
    'correiodopovo.com.br',
    'machinadoesporte.com.br',
    'womanifs.com',
    'diariodonordeste.verdesmares.com.br',
    'jc.ne10.uol.com.br',
    'mktesportivo.com',
)
pe.TRUSTED_DOMAINS = tuple(dict.fromkeys(tuple(pe.TRUSTED_DOMAINS) + _ADDITIONAL_TRUSTED_DOMAINS))
v54.v2.SOURCE_DOMAIN_HINTS.update({
    'federacao pernambucana de futebol': 'fpf-pe.com.br',
    'federação pernambucana de futebol': 'fpf-pe.com.br',
    'radio itatiaia': 'itatiaia.com.br',
    'rádio itatiaia': 'itatiaia.com.br',
    'gzh': 'gzh.com.br',
    'correio do povo': 'correiodopovo.com.br',
    'maquina do esporte': 'machinadoesporte.com.br',
    'máquina do esporte': 'machinadoesporte.com.br',
    'diario do nordeste': 'diariodonordeste.verdesmares.com.br',
    'diário do nordeste': 'diariodonordeste.verdesmares.com.br',
    'jc': 'jc.ne10.uol.com.br',
    'jornal do commercio': 'jc.ne10.uol.com.br',
    'mkt esportivo': 'mktesportivo.com',
})

_original_rss_candidates = pe.rss_candidates
_original_dump = pe.dump

def _official_request_bytes(url, *, timeout=15):
    """HTTPS oficial com verificação TLS obrigatória e fallback de CA bundle.

    Nunca usa contexto SSL não verificado. Primeiro preserva o cliente existente;
    somente para erro de cadeia de certificado tenta o bundle Mozilla/certifi,
    quando disponível no runner.
    """
    headers={'User-Agent':'Mozilla/5.0 (compatible; RadarBrasil2027/2.5)'}
    try:
        return pe.request_bytes(url,headers=headers,timeout=timeout)
    except Exception as first:
        if 'CERTIFICATE_VERIFY_FAILED' not in str(first):
            raise
        try:
            import certifi
            ctx=ssl.create_default_context(cafile=certifi.where())
            req=urllib.request.Request(url,headers=headers)
            with urllib.request.urlopen(req,timeout=timeout,context=ctx) as resp:
                data=resp.read()
                final_url=resp.geturl()
                hdrs=dict(resp.headers.items())
            if urllib.parse.urlparse(final_url).scheme != 'https':
                raise RuntimeError('official_https_downgrade_blocked')
            print('primary_cbf_tls_fallback=certifi_verified')
            return data,final_url,hdrs
        except Exception as second:
            print(f'primary_cbf_tls_fallback_failed={type(second).__name__}:{second}')
            raise first

# A validação editorial v5 usa pe.request_bytes diretamente. Em alguns runners,
# a cadeia TLS da CBF falha no cliente padrão embora a página oficial esteja válida.
# Aplica fallback SOMENTE para HTTPS da CBF, sempre com verificação certifi; não
# altera outras fontes, não desativa TLS e não cria qualquer leitura Airtable.
_base_request_bytes = pe.request_bytes

def _request_bytes_cbf_verified(url, headers=None, timeout=25):
    try:
        return _base_request_bytes(url, headers=headers, timeout=timeout)
    except Exception as first:
        parsed=urllib.parse.urlparse(str(url or ''))
        host=parsed.netloc.casefold().removeprefix('www.')
        if parsed.scheme != 'https' or not (host == 'cbf.com.br' or host.endswith('.cbf.com.br')):
            raise
        try:
            import certifi
            ctx=ssl.create_default_context(cafile=certifi.where())
            h={'User-Agent':getattr(pe,'UA','RadarBrasil2027/2.8')}
            if headers: h.update(headers)
            req=urllib.request.Request(url,headers=h)
            with urllib.request.urlopen(req,timeout=timeout,context=ctx) as resp:
                data=resp.read(); final_url=resp.geturl(); hdrs=dict(resp.headers.items())
            final=urllib.parse.urlparse(final_url)
            final_host=final.netloc.casefold().removeprefix('www.')
            if final.scheme != 'https' or not (final_host == 'cbf.com.br' or final_host.endswith('.cbf.com.br')):
                raise RuntimeError('cbf_verified_redirect_blocked')
            print('suggestion_cbf_tls_fallback=certifi_verified')
            return data,final_url,hdrs
        except Exception:
            raise first

pe.request_bytes=_request_bytes_cbf_verified

# Resgate conservador de sugestões de EVENTO sem data.
# O link original (inclusive rede social) serve apenas como pista de descoberta.
# Para materializar o evento, exigimos uma fonte editorial já confiável no Radar,
# correspondência semântica com o título sugerido e data explícita no conteúdo.
# Nenhuma leitura adicional do Airtable é feita.
_original_candidate_from_record_v55 = pe.candidate_from_record
_event_date_rescues = 0
MAX_EVENT_DATE_RESCUES = 2
_EVENT_RESCUE_STOP = {
    'evento','eventos','cidade','cidades','brasil','copa','2027','para','com',
    'uma','das','dos','de','do','da','em','no','na','ao','aos'
}
_EVENT_MONTHS = {
    'janeiro':1,'fevereiro':2,'marco':3,'março':3,'abril':4,'maio':5,'junho':6,
    'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12,
}
_HOST_CITIES = {
    'porto alegre':('Porto Alegre','RS'),'recife':('Recife','PE'),
    'fortaleza':('Fortaleza','CE'),'salvador':('Salvador','BA'),
    'belo horizonte':('Belo Horizonte','MG'),'sao paulo':('São Paulo','SP'),
    'são paulo':('São Paulo','SP'),'rio de janeiro':('Rio de Janeiro','RJ'),
    'brasilia':('Brasília','DF'),'brasília':('Brasília','DF'),
}

def _recent_record_for_rescue(record, max_age_days=7):
    raw=str(record.get('createdTime') or '').strip()
    if not raw:
        return False
    try:
        dt=pe.datetime.fromisoformat(raw.replace('Z','+00:00'))
        return (pe.now().date()-dt.astimezone(pe.BRT).date()).days <= max_age_days
    except Exception:
        return False

def _event_rescue_tokens(title):
    return [x for x in pe.norm(title).split() if len(x)>=4 and x not in _EVENT_RESCUE_STOP]

def _trusted_search_results(query):
    out=[]; seen=set()

    def add(href):
        href=str(href or '').strip()
        if not href or not pe.trusted_url(href):
            return False
        key=pe.urlnorm(href)
        if not key or key in seen:
            return False
        seen.add(key); out.append(href)
        return True

    # Caminho 1: busca HTML genérica.
    url='https://html.duckduckgo.com/html/?'+urllib.parse.urlencode({'q':query})
    try:
        data,_,_=pe.request_bytes(
            url,
            headers={'User-Agent':'Mozilla/5.0 (compatible; RadarBrasil2027/3.1)'},
            timeout=10,
        )
        raw=data[:650000].decode('utf-8','ignore')
        for m in re.finditer(r"<a\\b[^>]*href=[\\\"']([^\\\"']+)[\\\"'][^>]*>",raw,flags=re.I|re.S):
            href=v54.v2._candidate_from_search_href(html.unescape(m.group(1)))
            add(href)
            if len(out)>=4:
                break
    except Exception as exc:
        print(f'event_date_rescue_search_warning=duckduckgo|{type(exc).__name__}:{exc}')

    # Caminho 2: Google News RSS somente como descoberta. O agregador nunca
    # é aceito como fonte final; a URL precisa resolver para domínio confiável.
    rss_url='https://news.google.com/rss/search?'+urllib.parse.urlencode({
        'q':query,'hl':'pt-BR','gl':'BR','ceid':'BR:pt-419'
    })
    try:
        data,_,_=pe.request_bytes(rss_url,timeout=10)
        root=pe.ET.fromstring(data)
        for item in root.findall('.//item')[:10]:
            title=(item.findtext('title') or '').strip()
            link=(item.findtext('link') or '').strip()
            source_el=item.find('source')
            source=(source_el.text or '').strip() if source_el is not None else ''
            domain=v54.v2._source_domain(source)
            if not title or not link or not domain or not pe.trusted_url('https://'+domain+'/'):
                continue
            direct=v54.compat.resolve_google_news(link)
            if direct and add(direct):
                print(f'event_date_rescue_google_resolved={domain}|{direct}')
            if len(out)>=6:
                break
    except Exception as exc:
        print(f'event_date_rescue_search_warning=google-news|{type(exc).__name__}:{exc}')

    print(f'event_date_rescue_sources={len(out)}')
    return out

def _date_from_event_text(text, published=None):
    raw=html.unescape(str(text or '')).casefold()
    # Prioriza intervalos ("24 e 25 de setembro"), evitando confundir com data de publicação.
    range_re=re.compile(r'(?<!\d)(\d{1,2})\s*(?:e|a|–|-)\s*(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(20\d{2}))?',re.I)
    single_re=re.compile(r'(?<!\d)(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(20\d{2}))?',re.I)
    event_words=('evento','encontro','acontece','acontecerá','acontecera','será realizado','sera realizado','realizado','realizada','dias','programação','programacao')
    def build(day,month_name,year,ctx):
        month=_EVENT_MONTHS.get(pe.norm(month_name))
        if not month:
            return None
        if year:
            y=int(year)
        elif published is not None:
            y=published.year
        else:
            return None
        try:
            d=pe.datetime(y,month,int(day)).date()
        except ValueError:
            return None
        if published is not None and not year and d < published-pe.timedelta(days=2):
            try:
                d=pe.datetime(y+1,month,int(day)).date()
            except ValueError:
                return None
        if d < pe.now().date()-pe.timedelta(days=1) or d > pe.datetime(2028,12,31).date():
            return None
        return d
    for m in range_re.finditer(raw):
        ctx=raw[max(0,m.start()-180):min(len(raw),m.end()+180)]
        if not any(w in ctx for w in event_words):
            continue
        d=build(m.group(1),m.group(3),m.group(4),ctx)
        if d:
            return d
    for m in single_re.finditer(raw):
        ctx=raw[max(0,m.start()-180):min(len(raw),m.end()+180)]
        if any(w in ctx for w in ('publicado','publicada','atualizado','atualizada')):
            continue
        if not any(w in ctx for w in event_words):
            continue
        d=build(m.group(1),m.group(2),m.group(3),ctx)
        if d:
            return d
    return None

def _recover_missing_event_date(record):
    global _event_date_rescues
    if _event_date_rescues >= MAX_EVENT_DATE_RESCUES or not _recent_record_for_rescue(record):
        return None
    fields=dict(record.get('fields',{}) or {})
    title=str(v54.compat.find_title(fields,'eventos') or v54._infer_title(fields,'')).strip()
    link=str(v54.compat.find_url(fields) or v54._infer_url(fields)).strip()
    if not title or not link:
        return None
    # Não tenta corrigir registros que já possuem data parseável.
    if v54.compat.parse_date(v54.compat.value_by_alias(fields,('Data','Data do evento','Data do Evento','Data informada'))):
        return None
    tokens=_event_rescue_tokens(title)
    if len(tokens)<2:
        print(f'event_date_rescue_skipped={record.get("id","")}|reason=title_too_generic')
        return None

    _event_date_rescues += 1
    query=f'{title} futebol feminino evento 2026 "Copa 2027"'
    for href in _trusted_search_results(query):
        try:
            data,final_url,headers=pe.request_bytes(
                href,
                headers={'User-Agent':'Mozilla/5.0 (compatible; RadarBrasil2027/3.0)'},
                timeout=12,
            )
            if not pe.trusted_url(final_url):
                continue
            ctype=str(headers.get('Content-Type','')).casefold()
            if 'html' not in ctype:
                continue
            raw=data[:900000].decode('utf-8','ignore')
            page_title=v54.v5._page_title(raw)
            visible=pe.clean_html_text(v54.v3._strip_non_editorial_blocks(raw))[:12000]
            blob=pe.norm(f'{page_title} {visible}')
            if not all(t in blob for t in tokens):
                continue
            if not pe.article_is_relevant(page_title or title,visible):
                continue
            if not any(x in blob for x in ('evento','encontro','seminario','seminário','workshop','congresso','forum','fórum','painel')):
                continue
            published=v54.v5._page_date(raw)
            event_date=_date_from_event_text(visible,published)
            if event_date is None:
                continue

            enriched=dict(record); ef=dict(fields)
            ef['Data']=event_date.isoformat()
            ef['Título']=page_title or title
            ef['Link']=final_url
            if not str(v54.compat.value_by_alias(ef,('Cidade','Cidade informada')) or '').strip():
                for needle,(city,uf) in _HOST_CITIES.items():
                    if needle in blob:
                        ef['Cidade informada']=city
                        ef['UF']=uf
                        break
            enriched['fields']=ef
            print(f'event_date_rescue_found={record.get("id","")}|date={event_date.isoformat()}|source={final_url}')
            return enriched
        except Exception as exc:
            print(f'event_date_rescue_candidate_warning={type(exc).__name__}:{exc}')
    print(f'event_date_rescue_unresolved={record.get("id","")}|title={title[:120]}')
    return None

def candidate_from_record_v59(record,kind):
    candidate=_original_candidate_from_record_v55(record,kind)
    if candidate is not None or kind!='eventos':
        return candidate
    enriched=_recover_missing_event_date(record)
    if enriched is None:
        return None
    return _original_candidate_from_record_v55(enriched,kind)

pe.candidate_from_record=candidate_from_record_v59

# Ampliação temática mínima: segue a mesma pesquisa pública e os mesmos gates,
# apenas cobre atualizações de ingressos da Seleção Feminina que podem não citar
# "Copa 2027" no título. Não altera Airtable nem aprova nada por si só.
_extra_public_queries = (
    '"Seleção Brasileira feminina" ingressos OR bilhetes OR "venda de ingressos"',
)
pe.PUBLIC_QUERIES = list(dict.fromkeys(list(pe.PUBLIC_QUERIES) + list(_extra_public_queries)))

CBF_LISTINGS = (
    'https://www.cbf.com.br/selecao-brasileira/noticias/selecao-feminina',
    'https://www.cbf.com.br/selecao-brasileira/noticias/selecao-feminina-principal',
)
WIFS_EVENT_PAGE = 'https://womanifs.com/'
WIFS_MONTHS = {6:('jun','junho','june'),7:('jul','julho','july')}
WIFS_EVENTS = (
    ('2027-06-23','Rio de Janeiro','RJ'),
    ('2027-06-27','Porto Alegre','RS'),
    ('2027-07-03','Brasília','DF'),
    ('2027-07-06','Recife','PE'),
    ('2027-07-09','Fortaleza','CE'),
    ('2027-07-11','Salvador','BA'),
    ('2027-07-15','Belo Horizonte','MG'),
    ('2027-07-23','São Paulo','SP'),
)

CBF_OFFICIAL_EVENT_PAGES = (
    'https://www.cbf.com.br/selecao-brasileira/noticias/selecao-feminina-principal/a/selecao-feminina-enfrenta-a-argentina-dias-10-e-13-de-outubro-em-porto-alegre-e-recife',
    'https://www.cbf.com.br/selecao-brasileira/noticias/selecao-feminina-principal/a/selecao-feminina-enfrenta-japao-em-dois-amistosos-em-novembro-e-dezembro',
)
EVENT_RULES = ({
    'opponent':'Argentina',
    'title_needles':('selecao','feminina','argentina'),
    'news_needles':('amistoso','amistosos','argentina'),
    'events':(
        ('2026-10-10','Porto Alegre','RS','Beira-Rio'),
        ('2026-10-13','Recife','PE','Arena Pernambuco'),
    ),
},{
    'opponent':'Japão',
    'title_needles':('selecao','feminina','japao'),
    'news_needles':('amistoso','amistosos','japao'),
    'events':(
        ('2026-11-29','Hiroshima','JP','Edion Peace Wing Hiroshima'),
        ('2026-12-05','Okayama','JP','JFE Harenokuni Stadium'),
    ),
},)

def _known_event_keys():
    keys=set()
    for path in (pe.ROOT/'dados.json', pe.INBOX):
        obj=pe.load(path, [] if path.name!='inbox.json' else {'eventos':[],'noticias':[]})
        items=obj if isinstance(obj,list) else obj.get('eventos',[])
        for item in items:
            if not isinstance(item,dict): continue
            date=str(item.get('Data') or '').strip(); title=pe.norm(item.get('Titulo')); city=pe.norm(item.get('Cidade'))
            if date and title: keys.add((date,title,city))
    return keys

def _official_link_matches(title, href):
    nt=pe.norm(title); path=pe.norm(urllib.parse.urlparse(href).path.replace('-', ' ')); text=f'{nt} {path}'
    if any(x in text for x in ('sub 17','sub17','sub 20','sub20','base feminina','selecao base')): return False
    return any(all(pe.norm(x) in text for x in rule['title_needles']) for rule in EVENT_RULES)

def _extract_links(raw, base_url):
    out=[]; seen=set()
    for href,label in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',raw,flags=re.I|re.S):
        href=html.unescape(href).strip()
        if href.startswith('/'): href=urllib.parse.urljoin(base_url,href)
        if 'cbf.com.br' not in urllib.parse.urlparse(href).netloc.casefold() or '/noticias/' not in href: continue
        clean=v54.v2._clean_page_title(label); key=pe.urlnorm(href)
        if not key or key in seen or not _official_link_matches(clean,href): continue
        seen.add(key); out.append((href,clean))
    return out

def _validate_official_page(href,hint=''):
    """Valida página oficial e conserva o texto para extrair TODOS os eventos nela contidos.

    Fail-closed: a página só vira candidata quando ao menos uma regra de evento é
    comprovada no próprio conteúdo. O texto não cria evento sozinho; cada evento
    ainda precisa passar pelas regras estruturadas e pela deduplicação.
    """
    try:
        data,final_url,headers=_official_request_bytes(href,timeout=15)
        if 'cbf.com.br' not in urllib.parse.urlparse(final_url).netloc.casefold(): return None
        raw=data[:900000].decode('utf-8','ignore'); title=v54.v2._clean_page_title(raw) or hint
        if not title or '<' in title: title=hint
        visible=html.unescape(re.sub(r'(?is)<(script|style)\\b.*?</\\1>',' ',raw[:500000]))
        visible=html.unescape(re.sub(r'(?s)<[^>]+>',' ',visible))
        visible=re.sub(r'\\s+',' ',visible).strip()
        combined=pe.norm(f'{title} {visible}')
        if any(x in combined for x in ('sub 17','sub17','sub 20','sub20')) and 'selecao feminina principal' not in combined: return None
        for rule in EVENT_RULES:
            if all(pe.norm(x) in combined for x in rule['title_needles']) and any(x in combined for x in ('amistoso','amistosos','enfrenta','contra')):
                matched=[r['opponent'] for r in EVENT_RULES if all(pe.norm(x) in combined for x in r['title_needles']) and any(x in combined for x in ('amistoso','amistosos','enfrenta','contra'))]
                return {'origin':'cbf-primary-v5.5','title':title or hint,'source':'cbf.com.br','trusted_source_domain':'cbf.com.br','url':final_url,'pub':'','event_text':combined,'event_time_text':visible,'matched_event_rules':matched}
    except Exception as exc: print(f'primary_cbf_page_warning={type(exc).__name__}:{exc}')
    return None

def _primary_cbf_candidates():
    out=[]; seen=set()
    for listing_url in CBF_LISTINGS:
        try:
            data,final_url,headers=_official_request_bytes(listing_url,timeout=15)
            links=_extract_links(data[:900000].decode('utf-8','ignore'),final_url); print(f'primary_cbf_listing={listing_url}|matches={len(links)}')
            for href,label in links[:8]:
                key=pe.urlnorm(href)
                if key in seen: continue
                candidate=_validate_official_page(href,label)
                if candidate: seen.add(key); out.append(candidate); print(f'primary_cbf_validated={candidate["title"][:160]}|{candidate["url"]}')
        except Exception as exc: print(f'primary_cbf_listing_warning={type(exc).__name__}:{exc}')
    for href in CBF_OFFICIAL_EVENT_PAGES:
        key=pe.urlnorm(href)
        if key in seen: continue
        slug=pe.norm(urllib.parse.urlparse(href).path.replace('-', ' '))
        hint=('Seleção Feminina enfrenta Japão em dois amistosos em novembro e dezembro' if 'japao' in slug else 'Seleção Feminina enfrenta a Argentina dias 10 e 13 de outubro em Porto Alegre e Recife')
        candidate=_validate_official_page(href,hint)
        if candidate: seen.add(key); out.append(candidate); print(f'primary_cbf_direct_validated={candidate["url"]}')
    print(f'primary_cbf_event_candidates={len(out)}'); return out

def _wifs_event_candidates():
    """Extrai agenda de uma página-fonte por camadas, sem depender do layout.

    Ordem: dados estruturados/embutidos -> texto visível. Cada evento só é
    materializado quando data e cidade aparecem na mesma unidade de conteúdo.
    Nenhuma leitura Airtable adicional é feita.
    """
    try:
        data,final_url,headers=pe.request_bytes(WIFS_EVENT_PAGE,headers={'User-Agent':'Mozilla/5.0 (compatible; RadarBrasil2027/2.7)'},timeout=15)
        if 'womanifs.com' not in urllib.parse.urlparse(final_url).netloc.casefold(): return []
        raw=data[:1600000].decode('utf-8','ignore')
        raw_norm=pe.norm(html.unescape(raw))
        if not ('mulheres que mudam o jogo' in raw_norm and '2027' in raw_norm and ('world cup' in raw_norm or 'copa do mundo' in raw_norm)):
            print('wifs_validation=failed_context'); return []

        # Unidades independentes de evidência. Preservamos scripts JSON/configuração
        # porque agendas modernas frequentemente são hidratadas no cliente.
        units=[]
        for m in re.finditer(r'(?is)<script\\b[^>]*>(.*?)</script>',raw):
            body=html.unescape(m.group(1))
            if len(body)<=500000: units.append(pe.norm(body))
        for m in re.finditer(r'(?is)<(?:article|section|li|div)\\b[^>]*>(.*?)</(?:article|section|li|div)>',raw):
            body=html.unescape(re.sub(r'(?s)<[^>]+>',' ',m.group(1)))
            if body.strip(): units.append(pe.norm(re.sub(r'\\s+',' ',body)))
        visible=re.sub(r'(?is)<(script|style)\\b.*?</\\1>',' ',raw)
        visible=html.unescape(re.sub(r'(?s)<[^>]+>',' ',visible))
        visible_text=re.sub(r'\\s+',' ',visible).strip()
        units.append(pe.norm(visible_text))
        # O HTML bruto normalizado é fallback final para atributos/data-* e blobs
        # de configuração. Não é suficiente sozinho: ainda exigimos data+cidade.
        units.append(raw_norm)

        confirmed=[]; confirmed_times={}
        for date,city,uf in WIFS_EVENTS:
            d=pe.datetime.strptime(date,'%Y-%m-%d'); cityn=pe.norm(city)
            months=WIFS_MONTHS.get(d.month,())
            numeric=(d.strftime('%Y-%m-%d'),d.strftime('%d/%m/%Y'),d.strftime('%d/%m'),f'{d.day}/{d.month}')
            def has_date(u):
                if any(pe.norm(x) in u for x in numeric): return True
                return bool(re.search(rf'(?<!\\d)0?{d.day}(?!\\d)',u)) and any(m in u for m in months) and ('2027' in u or len(u)<800)
            evidence=False
            for u in units:
                if cityn not in u: continue
                # Em unidades grandes, exige proximidade; em blocos pequenos, coocorrência.
                if len(u)<1200:
                    if has_date(u): evidence=True; break
                else:
                    for pos in [m.start() for m in re.finditer(re.escape(cityn),u)]:
                        window=u[max(0,pos-500):pos+500]
                        if has_date(window): evidence=True; break
                    if evidence: break
            if evidence:
                confirmed.append((date,city,uf))
                event_time=_extract_event_time_for_known_event(
                    visible_text,date,city,'',('mulheres que mudam o jogo','wifs','jornada')
                )
                if event_time:
                    confirmed_times[f'{date}|{city}']=event_time
                    print(f'wifs_event_time={date}|{city}|{event_time}')
                print(f'wifs_structured_event_confirmed={date}|{city}')
            else: print(f'wifs_event_not_confirmed={date}|{city}')
        print(f'wifs_events_validated={len(confirmed)}')
        return [{'origin':'wifs-primary-v5.7','title':'Jornada Mulheres que Mudam o Jogo – 2027 Women’s World Cup','source':'womanifs.com','trusted_source_domain':'womanifs.com','url':final_url,'pub':'','confirmed_events':confirmed,'confirmed_event_times':confirmed_times,'event_timezone':'America/Sao_Paulo'}]
    except Exception as exc:
        print(f'wifs_warning={type(exc).__name__}:{exc}'); return []

def _cbf_known_event_fallback_candidates(rss):
    """Fallback sem nova chamada externa: reutiliza os candidatos RSS já baixados.

    Só ativa uma regra quando o próprio título/fonte já observado nesta execução
    contém Brasil/Seleção Feminina + adversário + contexto de amistoso. Não
    desabilita TLS e não faz leitura adicional de Airtable.
    """
    out=[]; seen=set()
    for c in rss:
        if not isinstance(c,dict): continue
        nt=pe.norm(f"{c.get('title','')} {c.get('source','')}")
        if any(x in nt for x in ('sub 17','sub17','sub 20','sub20','selecao base')): continue
        if not (('selecao feminina' in nt) or ('selecao brasileira feminina' in nt) or ('brasil' in nt and 'feminina' in nt)): continue
        for rule in EVENT_RULES:
            opp=pe.norm(rule['opponent'])
            if opp not in nt or not any(x in nt for x in ('amistoso','amistosos','enfrenta','contra')): continue
            key=(opp,pe.urlnorm(str(c.get('url') or '')))
            if key in seen: continue
            seen.add(key); out.append({'origin':'cbf-rss-evidence-v5.6','title':str(c.get('title') or ''),'source':str(c.get('source') or ''),'trusted_source_domain':'event-rule-confirmed','url':str(c.get('url') or ''),'pub':str(c.get('pub') or ''),'matched_opponent':rule['opponent']})
            print(f'cbf_rss_event_evidence={rule["opponent"]}|{c.get("title","")[:140]}')
    print(f'cbf_rss_event_fallback_candidates={len(out)}'); return out

def _cbf_semantic_schedule_candidates(rss):
    """Interpreta chamadas genéricas sem inventar evento.

    Aprende o padrão 'Seleção Brasileira Feminina define mais dois amistosos':
    quando adversário não está no título, a chamada pode ativar uma regra SOMENTE
    se houver uma única regra futura compatível com o período ainda não resolvido.
    Isso usa o calendário estruturado EVENT_RULES como evidência e não faz fetch.
    """
    out=[]
    for c in rss:
        if not isinstance(c,dict): continue
        nt=pe.norm(f"{c.get('title','')} {c.get('source','')}")
        if any(x in nt for x in ('sub 17','sub17','sub 20','sub20','selecao base')): continue
        # "Seleção Brasileira Feminina" já identifica Brasil; não exige a
        # palavra Brasil separadamente. Mantém exclusão de base logo acima.
        brazil_women=('selecao brasileira feminina' in nt) or (('selecao feminina' in nt) and ('brasil' in nt or 'brasileira' in nt))
        vague_friendlies=any(x in nt for x in ('mais dois amistosos','dois amistosos','novos amistosos','define mais'))
        if not (brazil_women and vague_friendlies): continue
        # Fail-closed: só inferimos se exatamente uma regra futura não tiver adversário
        # explícito no título e seus eventos forem posteriores aos já conhecidos de outubro.
        compatible=[r for r in EVENT_RULES if all(str(e[0]) >= '2026-11-01' for e in r['events'])]
        if len(compatible)!=1:
            print(f'cbf_semantic_ambiguous={len(compatible)}|{c.get("title","")[:140]}'); continue
        rule=compatible[0]
        out.append({'origin':'cbf-semantic-schedule-v5.7','title':str(c.get('title') or ''),'source':str(c.get('source') or ''),'trusted_source_domain':'event-rule-confirmed','url':str(c.get('url') or ''),'pub':str(c.get('pub') or ''),'matched_opponent':rule['opponent']})
        print(f'cbf_semantic_schedule_evidence={rule["opponent"]}|{c.get("title","")[:140]}')
    print(f'cbf_semantic_schedule_candidates={len(out)}'); return out

def _trusted_news_event_candidates(rss):
    out=[]
    for c in rss:
        if not isinstance(c,dict): continue
        text=pe.norm(f"{c.get('title','')} {c.get('source','')}")
        if any(x in text for x in ('sub 17','sub17','sub 20','sub20','selecao base')): continue
        for rule in EVENT_RULES:
            if not all(pe.norm(x) in text for x in rule['news_needles']): continue
            if not (('selecao brasileira feminina' in text) or ('selecao feminina' in text) or ('brasil' in text and 'feminina' in text)): continue
            out.append({'origin':'trusted-news-event-signal-v5.5','title':str(c.get('title') or ''),'source':str(c.get('source') or ''),'trusted_source_domain':'event-rule-confirmed','url':str(c.get('url') or ''),'pub':str(c.get('pub') or '')}); break
    print(f'trusted_news_event_candidates={len(out)}'); return out

def _extract_explicit_event_time(text, keywords=()):
    """Extrai horário apenas quando há marcador temporal explícito perto do evento."""
    raw=html.unescape(str(text or '')).casefold()
    if not raw:
        return ''
    pattern=re.compile(r'\b(?:às|as|a partir das|com início às|com inicio as|início às|inicio as|começa às|comeca as|será às|sera as|marcada para às|marcada para as)\s*([01]?\d|2[0-3])(?:\s*(?::|h)\s*([0-5]\d))?\s*(?:h|horas?)?\b',re.I)
    wanted=[pe.norm(x) for x in keywords if pe.norm(x)]
    for m in pattern.finditer(raw):
        window=raw[max(0,m.start()-220):min(len(raw),m.end()+220)]
        nw=pe.norm(window)
        if wanted and not any(x in nw for x in wanted):
            continue
        before=pe.norm(raw[max(0,m.start()-70):m.start()])
        if any(x in before for x in ('publicado','publicada','atualizado','atualizada')):
            continue
        hour=int(m.group(1)); minute=int(m.group(2) or 0)
        return f'{hour:02d}:{minute:02d}'
    return ''

def _extract_event_time_for_known_event(text,date,city='',venue='',keywords=()):
    """Extrai horário somente perto da data/local do evento conhecido.

    Isso evita aplicar ao segundo jogo o horário do primeiro quando uma mesma
    matéria oficial contém dois ou mais eventos.
    """
    raw=html.unescape(str(text or ''))
    if not raw or not date:
        return ''
    try:
        d=pe.datetime.strptime(str(date)[:10],'%Y-%m-%d')
    except Exception:
        return ''
    months=('janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro')
    anchors=[
        str(city or '').strip(), str(venue or '').strip(),
        d.strftime('%d/%m/%Y'), d.strftime('%d/%m'),
        f'{d.day} de {months[d.month-1]} de {d.year}',
        f'{d.day} de {months[d.month-1]}',
    ]
    folded=raw.casefold()
    windows=[]
    for value in anchors:
        if not value:
            continue
        needle=value.casefold()
        for m in re.finditer(re.escape(needle),folded):
            windows.append(raw[max(0,m.start()-650):min(len(raw),m.end()+650)])
    # Só aceita o horário se ele estiver em uma janela ancorada no evento.
    for window in windows:
        event_time=_extract_explicit_event_time(window,keywords)
        if event_time:
            return event_time
    return ''

def _known_event_time_keys():
    keys=set()
    for path in (pe.ROOT/'dados.json', pe.INBOX):
        obj=pe.load(path, [] if path.name!='inbox.json' else {'eventos':[],'noticias':[]})
        items=obj if isinstance(obj,list) else obj.get('eventos',[])
        for item in items:
            if not isinstance(item,dict):
                continue
            date=str(item.get('Data') or '').strip(); title=pe.norm(item.get('Titulo')); city=pe.norm(item.get('Cidade'))
            hora=str(item.get('Hora') or '').strip()
            if date and title and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',hora):
                keys.add((date,title,city))
    return keys

def _apply_time_fields(event,candidate,default_timezone='America/Sao_Paulo'):
    hora=str(candidate.get('event_time') or '').strip()
    hora_fim=str(candidate.get('event_end_time') or '').strip()
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',hora):
        return event
    event=dict(event); event['Hora']=hora
    if re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',hora_fim):
        event['HoraFim']=hora_fim
    event['FusoHorario']=str(candidate.get('event_timezone') or '').strip() or default_timezone
    return event

def _convocation_events_from_rss(rss):
    """Extrai convocação apenas com evidência explícita da data do EVENTO.

    Nunca usa pubDate/data da notícia como data da convocação. Matérias de repercussão
    ("convocadas", lista, atletas de um estado/clube etc.) permanecem somente notícias.
    """
    out=[]; seen=set()
    for c in rss:
        if not isinstance(c,dict): continue
        title=str(c.get('title') or '').strip()
        nt=pe.norm(f"{title} {c.get('source','')}")
        if 'convoc' not in nt: continue
        if any(x in nt for x in ('sub 17','sub17','sub 20','sub20','selecao base','categoria de base')): continue
        women=('selecao brasileira feminina' in nt) or ('selecao feminina' in nt) or (('brasil' in nt or 'brasileira' in nt) and 'feminina' in nt)
        if not women: continue

        source_url=str(c.get('url') or ''); body=''; final_url=source_url
        try:
            body,final_url=pe.fetch_article_excerpt(source_url)
        except Exception:
            body=''
        evidence=f"{title} {body}"
        ne=pe.norm(evidence)

        # Exige linguagem inequívoca de anúncio/agendamento da convocação.
        explicit_call=any(x in ne for x in (
            'convocacao sera','convocacao acontece','convocacao ocorrera',
            'vai convocar','ira convocar','anunciara a convocacao',
            'lista sera anunciada','lista sera divulgada'
        ))
        if not explicit_call:
            print(f'convocation_news_only_no_explicit_event={title[:140]}')
            continue

        # A data deve estar no conteúdo da fonte; pubDate nunca é data do evento.
        explicit_dates=_extract_explicit_dates(evidence)
        if not explicit_dates:
            print(f'convocation_news_only_no_explicit_date={title[:140]}')
            continue
        future_or_today=[d for d in explicit_dates if d >= pe.now().date()]
        if not future_or_today:
            continue
        d=min(future_or_today); date=d.isoformat()
        key=(date,'convocacao-selecao-feminina')
        if key in seen: continue
        seen.add(key)
        event_time=_extract_explicit_event_time(evidence,('convocacao','convocação','convoca'))
        candidate={'origin':'convocation-rss-v5.9','title':title,'source':str(c.get('source') or ''),'trusted_source_domain':'event-rule-confirmed','url':str(final_url or source_url),'pub':str(c.get('pub') or ''),'event_date':date}
        if event_time:
            candidate['event_time']=event_time
            candidate['event_timezone']='America/Sao_Paulo'
        out.append(candidate)
        print(f'convocation_event_evidence={date}|{title[:140]}')
    print(f'convocation_event_candidates={len(out)}'); return out

def _recent_known_news_event_candidates(max_age_days=30, limit=12):
    """Retrovarredura local e limitada para notícias anteriores ao aprendizado.

    Não consulta Airtable nem faz HTTP aqui. Lê apenas noticias.json, restringe a
    notícias recentes com sinal forte de evento/premiação e limita o lote. O fetch
    da fonte continua centralizado em _future_events_from_news, com as mesmas
    proteções de data explícita, relevância e deduplicação de eventos.
    """
    items=pe.load(pe.ROOT/'noticias.json',[])
    if not isinstance(items,list): return []
    cutoff=pe.now().date()-pe.timedelta(days=max_age_days)
    out=[]; seen=set()
    signal_words=('bola de ouro','indicada','indicado','indicacao','nomeada','nomeado','finalista','concorre','premio','premiacao','premiação','cerimonia','cerimônia','sorteio','congresso','seminario','seminário','forum','fórum','workshop','lancamento','lançamento')
    for item in reversed(items):
        if not isinstance(item,dict): continue
        title=str(item.get('Titulo') or '').strip(); link=str(item.get('Link') or '').strip()
        if not title or not link: continue
        nt=pe.norm(title)
        if not any(pe.norm(x) in nt for x in signal_words): continue
        raw_date=str(item.get('Data') or '')[:10]
        try: d=pe.datetime.strptime(raw_date,'%Y-%m-%d').date()
        except Exception: continue
        if d < cutoff: continue
        key=pe.urlnorm(link) or nt
        if key in seen: continue
        seen.add(key)
        out.append({'origin':'known-news-backfill-v5.10','title':title,'source':str(item.get('Veiculo') or ''),'url':link,'pub':'','known_news_date':raw_date})
        if len(out)>=limit: break
    print(f'known_news_backfill_candidates={len(out)}|max_age_days={max_age_days}|limit={limit}')
    return out

def _future_events_from_news(rss):
    """Extrai eventos futuros explícitos de notícias já coletadas, sem novo fetch.

    Regra deliberadamente conservadora: exige (1) assunto ligado à Seleção Brasileira
    Feminina/futebol feminino, (2) linguagem inequívoca de evento futuro, (3) data
    completa explícita no título disponível ao coletor e (4) tipo de evento conhecido.
    Não usa pubDate como data do evento e exclui categorias de base.
    """
    out=[]; seen=set(); months={'janeiro':1,'fevereiro':2,'marco':3,'março':3,'abril':4,'maio':5,'junho':6,'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}
    event_words=('cerimonia','cerimônia','premiacao','premiação','sorteio','congresso','seminario','seminário','forum','fórum','workshop','lancamento','lançamento','evento')
    future_words=('sera','será','acontece','acontecera','acontecerá','marcado','marcada','realizado','realizada','conhecido','conhecida','entregue','premiacao','premiação','cerimonia','cerimônia')
    for c in rss:
        if not isinstance(c,dict): continue
        title=str(c.get('title') or '').strip(); nt=pe.norm(f"{title} {c.get('source','')}")
        if any(x in nt for x in ('sub 17','sub17','sub 20','sub20','sub 23','sub23','selecao base','categoria de base')): continue
        relevant=('selecao brasileira feminina' in nt) or ('futebol feminino' in nt) or any(x in nt for x in ('lorena','marta','bola de ouro'))
        # Pré-filtro barato: só abre a matéria quando o título sinaliza premiação/evento
        # potencialmente estruturável. Reutiliza fetch HTTP; não toca no Airtable.
        award_signal=any(x in nt for x in ('indicada','indicado','indicacao','nomeada','nomeado','finalista','concorre','premio','premiação','premiacao'))
        signal=('bola de ouro' in nt) or award_signal or any(pe.norm(x) in nt for x in event_words)
        if not relevant or not signal: continue
        body=''; final_url=str(c.get('url') or '')
        try:
            body,final_url=pe.fetch_article_excerpt(final_url)
        except Exception as e:
            print(f'future_event_fetch_failed={type(e).__name__}|{title[:120]}')
        nb=pe.norm(f"{title} {body}")
        if not body or not any(pe.norm(x) in nb for x in future_words): continue
        # A data precisa estar explicitamente no título OU corpo da fonte; pubDate nunca vira data do evento.
        evidence=f"{title} {body}"
        m=re.search(r'(?<!\\d)([0-3]?\\d)[/.-]([01]?\\d)[/.-](20\\d{2})(?!\\d)',evidence)
        date=''
        if m:
            try: date=pe.datetime(int(m.group(3)),int(m.group(2)),int(m.group(1))).date().isoformat()
            except ValueError: continue
        if not date:
            tn=pe.norm(evidence)
            for mon,num in months.items():
                mm=re.search(rf'(?<!\\d)([0-3]?\\d) de {pe.norm(mon)}(?: de)? (20\\d{{2}})',tn)
                if mm:
                    try: date=pe.datetime(int(mm.group(2)),num,int(mm.group(1))).date().isoformat()
                    except ValueError: date=''
                    break
        if not date or date < pe.now().date().isoformat(): continue
        if 'bola de ouro' in nb:
            event_title='Cerimônia da Bola de Ouro 2026'; category='Premiação / Futebol Feminino'; city='Londres'; uf=''; organizer='France Football'; local=''; semantic='bola-de-ouro-2026'
            event_time=_extract_explicit_event_time(evidence,('bola de ouro','cerimonia','cerimônia','premiacao','premiação'))
            event_timezone='Europe/London'
        else:
            # Outros tipos ficam apenas sinalizados até termos extração segura de nome/local.
            print(f'future_event_ambiguous_type={date}|{title[:140]}'); continue
        key=(date,semantic,pe.norm(city))
        if key in seen: continue
        seen.add(key); candidate={'origin':'future-news-event-v5.9','title':title,'source':str(c.get('source') or ''),'trusted_source_domain':'event-rule-confirmed','url':str(final_url or c.get('url') or ''),'event_date':date,'event_title':event_title,'category':category,'city':city,'uf':uf,'organizer':organizer,'local':local,'semantic_key':semantic}
        if event_time:
            candidate['event_time']=event_time; candidate['event_timezone']=event_timezone
            print(f'future_event_time={date}|{semantic}|{event_time}|{event_timezone}')
        out.append(candidate)
        print(f'future_event_evidence={date}|{semantic}|{title[:140]}')
    print(f'future_news_event_candidates={len(out)}'); return out

def _events_from_candidates(candidates):
    known=_known_event_keys(); known_time=_known_event_time_keys(); out=[]
    for c in candidates:
        origin=str(c.get('origin') or ''); trusted=str(c.get('trusted_source_domain') or '').casefold()
        if trusted not in ('cbf.com.br','event-rule-confirmed','womanifs.com'): continue
        if origin=='future-news-event-v5.9':
            date=str(c.get('event_date') or ''); event_title=str(c.get('event_title') or '').strip(); city=str(c.get('city') or '').strip(); key=(date,pe.norm(event_title),pe.norm(city))
            if not date or not event_title:
                continue
            has_new_time=bool(str(c.get('event_time') or '').strip()) and key not in known_time
            if key in known and not has_new_time:
                print(f'future_event_duplicate={date}|{event_title}|{city}')
                continue
            if key not in known:
                known.add(key)
            elif has_new_time:
                print(f'future_event_time_enrichment={date}|{event_title}|{city}|{c.get("event_time")}')
            uf=str(c.get('uf') or '')
            event={'ID':f"NEWS-EVENT-{date}-{str(c.get('semantic_key') or 'event').upper()}",'Titulo':event_title,'Status':'Planejado','Data':date,'DataBR':pe.datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y'),'UF':uf,'Cidade':city,'Categoria':str(c.get('category') or 'Evento'),'Organizador':str(c.get('organizer') or ''),'Publico':0,'Patrocinador':'','Local':str(c.get('local') or ''),'Latitude':None,'Longitude':None,'Link':str(c.get('url') or ''),'Observacoes':f"Evento futuro extraído de notícia relevante: {str(c.get('title') or '')[:500]}",'Mes':('Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez')[int(date[5:7])-1],'Ano':int(date[:4]),'Regiao':''}
            event=_apply_time_fields(event,c,'America/Sao_Paulo')
            if event.get('Hora'): known_time.add(key)
            out.append(event)
            print(f'future_event_extracted={date}|{event_title}|{city}')
            continue
        if origin in ('convocation-rss-v5.8','convocation-rss-v5.9'):
            date=str(c.get('event_date') or '')
            event_title='Convocação da Seleção Brasileira Feminina'; key=(date,pe.norm(event_title),pe.norm('Rio de Janeiro'))
            if not date:
                continue
            has_new_time=bool(str(c.get('event_time') or '').strip()) and key not in known_time
            if key in known and not has_new_time:
                print(f'convocation_event_duplicate={date}')
                continue
            if key not in known:
                known.add(key)
            elif has_new_time:
                print(f'convocation_event_time_enrichment={date}|{c.get("event_time")}')
            event={'ID':f'CBF-CONVOCACAO-{date}','Titulo':event_title,'Status':'Planejado','Data':date,'DataBR':pe.datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y'),'UF':'RJ','Cidade':'Rio de Janeiro','Categoria':'Convocação da Seleção Feminina','Organizador':'CBF','Publico':0,'Patrocinador':'','Local':'','Latitude':None,'Longitude':None,'Link':str(c.get('url') or ''),'Observacoes':'Convocação da Seleção Brasileira Feminina identificada em cobertura pública do próprio dia; seleções de base são excluídas.','Mes':('Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez')[int(date[5:7])-1],'Ano':int(date[:4]),'Regiao':'Sudeste'}
            event=_apply_time_fields(event,c,'America/Sao_Paulo')
            if event.get('Hora'): known_time.add(key)
            out.append(event)
            print(f'convocation_event_extracted={date}|Rio de Janeiro')
            continue
        if origin in ('wifs-primary-v5.6','wifs-primary-v5.7'):
            time_map=c.get('confirmed_event_times',{}) if isinstance(c.get('confirmed_event_times',{}),dict) else {}
            for date,city,uf in c.get('confirmed_events',[]):
                event_title='Jornada Mulheres que Mudam o Jogo – WIFS'; key=(date,pe.norm(event_title),pe.norm(city))
                event_time=str(time_map.get(f'{date}|{city}') or '').strip()
                has_new_time=bool(event_time) and key not in known_time
                if key in known and not has_new_time:
                    print(f'wifs_event_duplicate={date}|{city}'); continue
                if key not in known:
                    known.add(key)
                else:
                    print(f'wifs_event_time_enrichment={date}|{city}|{event_time}')
                event={'ID':f'WIFS-{date}-{uf}','Titulo':event_title,'Status':'Planejado','Data':date,'DataBR':pe.datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y'),'UF':uf,'Cidade':city,'Categoria':'Ativação / evento Copa Feminina 2027','Organizador':'WIFS','Publico':0,'Patrocinador':'','Local':'','Latitude':None,'Longitude':None,'Link':str(c.get('url') or WIFS_EVENT_PAGE),'Observacoes':'Evento derivado de página-fonte; data e cidade validadas no conteúdo antes da materialização.','Mes':('Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez')[int(date[5:7])-1],'Ano':int(date[:4]),'Regiao':{'RS':'Sul','RJ':'Sudeste','SP':'Sudeste','MG':'Sudeste','DF':'Centro-Oeste','PE':'Nordeste','CE':'Nordeste','BA':'Nordeste'}.get(uf,'')}
                if event_time:
                    event=_apply_time_fields(event,{'event_time':event_time,'event_timezone':str(c.get('event_timezone') or 'America/Sao_Paulo')})
                    known_time.add(key)
                out.append(event)
                print(f'wifs_event_extracted={date}|{city}')
            continue
        title=str(c.get('title') or '').strip(); nt=pe.norm(title); event_text=str(c.get('event_text') or nt)
        for rule in EVENT_RULES:
            if origin in ('cbf-rss-evidence-v5.6','cbf-semantic-schedule-v5.7'):
                if pe.norm(rule['opponent']) != pe.norm(c.get('matched_opponent')): continue
            elif origin=='trusted-news-event-signal-v5.5':
                if not all(pe.norm(x) in nt for x in rule['news_needles']): continue
            elif origin=='cbf-primary-v5.5':
                # Uma matéria pode conter N eventos. Cada regra precisa aparecer no
                # conteúdo da própria página; não basta a página ter validado outra regra.
                if not all(pe.norm(x) in event_text for x in rule['title_needles']): continue
                if not any(x in event_text for x in ('amistoso','amistosos','enfrenta','contra')): continue
            elif not all(pe.norm(x) in nt for x in rule['title_needles']): continue
            for date,city,uf,venue in rule['events']:
                event_title=f"Brasil x {rule['opponent']} — amistoso da Seleção Feminina"; key=(date,pe.norm(event_title),pe.norm(city))
                time_evidence=str(c.get('event_time_text') or '')
                event_time=_extract_event_time_for_known_event(
                    time_evidence,date,city,venue,(rule['opponent'],'amistoso','seleção feminina','selecao feminina')
                ) if time_evidence else ''
                has_new_time=bool(event_time) and key not in known_time
                if key in known and not has_new_time:
                    print(f'official_event_duplicate={date}|{city}|{rule["opponent"]}'); continue
                if key not in known:
                    known.add(key)
                else:
                    print(f'official_event_time_enrichment={date}|{city}|{rule["opponent"]}|{event_time}')
                source_url=str(c.get('url') or CBF_OFFICIAL_EVENT_PAGES[0])
                event={'ID':f'CBF-{date}-{rule["opponent"].upper()}','Titulo':event_title,'Status':'Planejado','Data':date,'DataBR':pe.datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y'),'UF':uf,'Cidade':city,'Categoria':'Amistoso da Seleção Feminina','Organizador':'CBF','Publico':0,'Patrocinador':'','Local':venue,'Latitude':None,'Longitude':None,'Link':source_url,'Observacoes':f"Amistoso Brasil x {rule['opponent']} confirmado; evento materializado independentemente da notícia.",'Mes':('Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez')[int(date[5:7])-1],'Ano':int(date[:4]),'Regiao':{'RS':'Sul','PE':'Nordeste'}.get(uf,'')}
                if event_time:
                    timezone='Asia/Tokyo' if uf=='JP' else 'America/Sao_Paulo'
                    event=_apply_time_fields(event,{'event_time':event_time,'event_timezone':timezone},timezone)
                    known_time.add(key)
                out.append(event)
                print(f'official_event_extracted={date}|{city}|{venue}|origin={origin}|time={event_time or "unknown"}')
    return out

def rss_candidates_v55():
    primary=_primary_cbf_candidates(); wifs=_wifs_event_candidates(); rss=_original_rss_candidates(); signals=_trusted_news_event_candidates(rss); cbf_fallback=_cbf_known_event_fallback_candidates(rss); cbf_semantic=_cbf_semantic_schedule_candidates(rss); convocations=_convocation_events_from_rss(rss); known_news=_recent_known_news_event_candidates(); future_events=_future_events_from_news(rss+known_news)
    # A extração é 1 fonte -> 0..N eventos. Notícia e eventos continuam com
    # deduplicação independente; reconhecer uma notícia nunca consome os eventos.
    pe._v55_official_events=_events_from_candidates(primary+wifs+signals+cbf_fallback+cbf_semantic+convocations+future_events)
    return primary+rss
pe.rss_candidates=rss_candidates_v55

# Resolver conservador adicional: quando Google News e GDELT trazem o MESMO
# título e a mesma fonte confiável, prefere a URL editorial direta do GDELT.
# Não amplia o universo editorial: exige título equivalente, domínio conhecido,
# mesma origem editorial e todos os gates existentes continuam sendo aplicados.
_v55_public_research = pe.public_research
_v55_gdelt_candidates = pe.gdelt_candidates

def _direct_title_key(value):
    return pe.norm(v54.v2._strip_source_suffix(str(value or '')))

def _same_publisher(url, domain):
    if not url or not domain:
        return False
    try:
        return v54.v2._same_domain(str(url), str(domain)) and pe.trusted_url(str(url))
    except Exception:
        return False

def public_research_v56(keys):
    rss = pe.rss_candidates()
    gdelt = _v55_gdelt_candidates()

    direct_by_title = {}
    for g in gdelt:
        if not isinstance(g,dict):
            continue
        link = str(g.get('url') or '').strip()
        title_key = _direct_title_key(g.get('title'))
        if not title_key or not pe.trusted_url(link):
            continue
        direct_by_title.setdefault(title_key, g)

    prepared = []
    upgraded = 0
    for c0 in rss:
        c = dict(c0)
        if c.get('origin') in ('google-news','google-news-trusted-source'):
            title_key = _direct_title_key(c.get('title'))
            source_domain = str(c.get('trusted_source_domain') or v54.v2._source_domain(c.get('source','')) or '').strip()
            g = direct_by_title.get(title_key)
            if g and _same_publisher(g.get('url'), source_domain):
                c['google_news_url'] = c.get('url','')
                c['url'] = str(g.get('url') or '')
                c['origin'] = 'google-news-gdelt-resolved-v5.6'
                c['trusted_source_domain'] = source_domain
                upgraded += 1
                print(f"google_news_gdelt_resolved=v5.6|{source_domain}|{c['url']}")
        prepared.append(c)

    saved_rss, saved_gdelt = pe.rss_candidates, pe.gdelt_candidates
    try:
        pe.rss_candidates = lambda: prepared
        pe.gdelt_candidates = lambda: gdelt
        result = _v55_public_research(keys)
    finally:
        pe.rss_candidates, pe.gdelt_candidates = saved_rss, saved_gdelt

    print(f'google_news_gdelt_resolved_count={upgraded}')
    return result

pe.public_research = public_research_v56

# Mantido por compatibilidade; a persistência final abaixo não depende deste hook.
def dump_v55(path,obj):
    if path==pe.INBOX and isinstance(obj,dict):
        extra=getattr(pe,'_v55_official_events',[])
        if extra:
            existing=list(obj.get('eventos',[])); keys={(str(x.get('Data') or ''),pe.norm(x.get('Titulo')),pe.norm(x.get('Cidade'))) for x in existing if isinstance(x,dict)}; added=0
            for event in extra:
                key=(event['Data'],pe.norm(event['Titulo']),pe.norm(event['Cidade']))
                if key not in keys: existing.append(event); keys.add(key); added+=1
            obj=dict(obj); obj['eventos']=existing; print(f'official_events_added_to_inbox={added}')
    return _original_dump(path,obj)
pe.dump=dump_v55

def _materialize_official_events():
    """Persistência explícita, idempotente e fail-closed dos eventos já validados."""
    extra=list(getattr(pe,'_v55_official_events',[]) or [])
    if not extra:
        print('official_events_materialized=0|reason=no_extracted_events'); return 0
    inbox=pe.load(pe.INBOX,{'eventos':[],'noticias':[]})
    if not isinstance(inbox,dict): raise RuntimeError('editorial/inbox.json não é um objeto JSON')
    existing=list(inbox.get('eventos',[]) or []); keys={(str(x.get('Data') or ''),pe.norm(x.get('Titulo')),pe.norm(x.get('Cidade'))) for x in existing if isinstance(x,dict)}; added=0; enriched=0
    index_by_key={(str(x.get('Data') or ''),pe.norm(x.get('Titulo')),pe.norm(x.get('Cidade'))):i for i,x in enumerate(existing) if isinstance(x,dict)}
    for event in extra:
        key=(str(event.get('Data') or ''),pe.norm(event.get('Titulo')),pe.norm(event.get('Cidade')))
        if key in keys:
            idx=index_by_key.get(key)
            if idx is not None:
                updates={}
                for field in ('Hora','HoraFim','FusoHorario'):
                    value=str(event.get(field) or '').strip()
                    if value and not str(existing[idx].get(field) or '').strip():
                        updates[field]=value
                if updates:
                    existing[idx]={**existing[idx],**updates}; enriched+=1
            continue
        existing.append(event); keys.add(key); index_by_key[key]=len(existing)-1; added+=1
    if added or enriched:
        updated=dict(inbox); updated['eventos']=existing
        _original_dump(pe.INBOX,updated)
        verify=pe.load(pe.INBOX,{'eventos':[],'noticias':[]})
        verify_keys={(str(x.get('Data') or ''),pe.norm(x.get('Titulo')),pe.norm(x.get('Cidade'))) for x in verify.get('eventos',[]) if isinstance(x,dict)}
        missing=[e for e in extra if (str(e.get('Data') or ''),pe.norm(e.get('Titulo')),pe.norm(e.get('Cidade'))) not in verify_keys]
        if missing: raise RuntimeError(f'Falha ao persistir {len(missing)} evento(s) oficial(is) no inbox')
    print(f'official_events_materialized={added}|time_enriched={enriched}|extracted={len(extra)}'); return added

if __name__=='__main__':
    rc=pe.main()
    if rc not in (None,0): raise SystemExit(rc)
    _materialize_official_events()
    raise SystemExit(0)
