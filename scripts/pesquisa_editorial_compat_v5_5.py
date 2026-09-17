#!/usr/bin/env python3
"""v5.5 — fonte primária estrutural + extração segura de eventos da Seleção Feminina.

Correção cirúrgica:
- mantém todo o núcleo v5.4 e as 2 leituras Airtable;
- consulta/valida a fonte oficial CBF antes dos agregadores;
- permite que notícia confiável já descoberta materialize eventos futuros conhecidos;
- deduplicação de notícias e eventos permanece independente;
- Google News permanece fallback;
- não altera Merge, Alertas, Instagram, Saúde, schedules ou limites de frescor.
"""
import importlib.util
import html
import re
import urllib.parse
from pathlib import Path

V54_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v5_4.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v5_4', V54_SCRIPT)
v54 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v54)
pe = v54.pe

_original_rss_candidates = pe.rss_candidates
_original_dump = pe.dump

CBF_LISTINGS = (
    'https://www.cbf.com.br/selecao-brasileira/noticias/selecao-feminina',
    'https://www.cbf.com.br/selecao-brasileira/noticias/selecao-feminina-principal',
)

CBF_OFFICIAL_EVENT_PAGES = (
    'https://www.cbf.com.br/selecao-brasileira/noticias/selecao-feminina-principal/a/selecao-feminina-enfrenta-a-argentina-dias-10-e-13-de-outubro-em-porto-alegre-e-recife',
)

EVENT_RULES = (
    {
        'opponent': 'Argentina',
        'title_needles': ('selecao', 'feminina', 'argentina'),
        'news_needles': ('amistoso', 'amistosos', 'argentina'),
        'events': (
            ('2026-10-10', 'Porto Alegre', 'RS', 'Beira-Rio'),
            ('2026-10-13', 'São Lourenço da Mata', 'PE', 'Arena Pernambuco'),
        ),
    },
)


def _known_event_keys():
    keys=set()
    for path in (pe.ROOT/'dados.json', pe.INBOX):
        obj=pe.load(path, [] if path.name!='inbox.json' else {'eventos':[],'noticias':[]})
        items=obj if isinstance(obj,list) else obj.get('eventos',[])
        for item in items:
            if not isinstance(item,dict): continue
            date=str(item.get('Data') or '').strip()
            title=pe.norm(item.get('Titulo'))
            city=pe.norm(item.get('Cidade'))
            if date and title: keys.add((date,title,city))
    return keys


def _official_link_matches(title, href):
    nt=pe.norm(title)
    path=pe.norm(urllib.parse.urlparse(href).path.replace('-', ' '))
    text=f'{nt} {path}'
    if any(x in text for x in ('sub 17','sub17','sub 20','sub20','base feminina','selecao base')):
        return False
    return any(all(pe.norm(x) in text for x in rule['title_needles']) for rule in EVENT_RULES)


def _extract_links(raw, base_url):
    out=[]; seen=set()
    for href,label in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw, flags=re.I|re.S):
        href=html.unescape(href).strip()
        if href.startswith('/'):
            href=urllib.parse.urljoin(base_url, href)
        if 'cbf.com.br' not in urllib.parse.urlparse(href).netloc.casefold(): continue
        if '/noticias/' not in href: continue
        clean=v54.v2._clean_page_title(label)
        key=pe.urlnorm(href)
        if not key or key in seen or not _official_link_matches(clean, href): continue
        seen.add(key); out.append((href,clean))
    return out


def _validate_official_page(href, hint=''):
    try:
        data, final_url, headers=pe.request_bytes(
            href, headers={'User-Agent':'Mozilla/5.0 (compatible; RadarBrasil2027/2.5)'}, timeout=15)
        if 'cbf.com.br' not in urllib.parse.urlparse(final_url).netloc.casefold(): return None
        raw=data[:900000].decode('utf-8','ignore')
        title=v54.v2._clean_page_title(raw) or hint
        if not title or '<' in title: title=hint
        combined=pe.norm(f'{title} {raw[:250000]}')
        if any(x in combined for x in ('sub 17','sub17','sub 20','sub20')) and 'selecao feminina principal' not in combined:
            return None
        for rule in EVENT_RULES:
            if all(pe.norm(x) in combined for x in rule['title_needles']) and any(x in combined for x in ('amistoso','amistosos','enfrenta','contra')):
                return {'origin':'cbf-primary-v5.5','title':title or hint,'source':'cbf.com.br','trusted_source_domain':'cbf.com.br','url':final_url,'pub':''}
    except Exception as exc:
        print(f'primary_cbf_page_warning={type(exc).__name__}:{exc}')
    return None


def _primary_cbf_candidates():
    out=[]; seen=set()
    for listing_url in CBF_LISTINGS:
        try:
            data, final_url, headers=pe.request_bytes(
                listing_url, headers={'User-Agent':'Mozilla/5.0 (compatible; RadarBrasil2027/2.5)'}, timeout=15)
            raw=data[:900000].decode('utf-8','ignore')
            links=_extract_links(raw, final_url)
            print(f'primary_cbf_listing={listing_url}|matches={len(links)}')
            for href,label in links[:8]:
                key=pe.urlnorm(href)
                if key in seen: continue
                candidate=_validate_official_page(href,label)
                if candidate:
                    seen.add(key); out.append(candidate)
                    print(f'primary_cbf_validated={candidate["title"][:160]}|{candidate["url"]}')
        except Exception as exc:
            print(f'primary_cbf_listing_warning={type(exc).__name__}:{exc}')
    for href in CBF_OFFICIAL_EVENT_PAGES:
        key=pe.urlnorm(href)
        if key in seen: continue
        candidate=_validate_official_page(href,'Seleção Feminina enfrenta a Argentina dias 10 e 13 de outubro em Porto Alegre e Recife')
        if candidate:
            seen.add(key); out.append(candidate)
            print(f'primary_cbf_direct_validated={candidate["url"]}')
    print(f'primary_cbf_event_candidates={len(out)}')
    return out


def _trusted_news_event_candidates(rss):
    """Extrai sinal estrutural do mesmo conjunto RSS já lido; zero leituras Airtable extras.

    Fail-closed: exige Argentina + amistoso(s) e referência inequívoca à Seleção
    Feminina/Brasileira Feminina. O candidato só libera EVENT_RULES já conhecidas;
    não infere datas, cidades ou locais novos do texto.
    """
    out=[]
    for c in rss:
        if not isinstance(c,dict): continue
        text=pe.norm(f"{c.get('title','')} {c.get('source','')}")
        if any(x in text for x in ('sub 17','sub17','sub 20','sub20','selecao base')):
            continue
        for rule in EVENT_RULES:
            if not all(pe.norm(x) in text for x in rule['news_needles']):
                continue
            if not (('selecao brasileira feminina' in text) or ('selecao feminina' in text) or ('brasil' in text and 'feminina' in text)):
                continue
            out.append({
                'origin':'trusted-news-event-signal-v5.5',
                'title':str(c.get('title') or ''),
                'source':str(c.get('source') or ''),
                'trusted_source_domain':'event-rule-confirmed',
                'url':str(c.get('url') or ''),
                'pub':str(c.get('pub') or ''),
            })
            break
    print(f'trusted_news_event_candidates={len(out)}')
    return out


def _events_from_candidates(candidates):
    known=_known_event_keys(); out=[]
    for c in candidates:
        origin=str(c.get('origin') or '')
        trusted=str(c.get('trusted_source_domain') or '').casefold()
        if trusted not in ('cbf.com.br','event-rule-confirmed'): continue
        title=str(c.get('title') or '').strip(); nt=pe.norm(title)
        for rule in EVENT_RULES:
            if origin=='trusted-news-event-signal-v5.5':
                if not all(pe.norm(x) in nt for x in rule['news_needles']): continue
            elif not all(pe.norm(x) in nt for x in rule['title_needles']):
                if origin!='cbf-primary-v5.5': continue
            for date,city,uf,venue in rule['events']:
                event_title=f"Brasil x {rule['opponent']} — amistoso da Seleção Feminina"
                key=(date,pe.norm(event_title),pe.norm(city))
                if key in known:
                    print(f'official_event_duplicate={date}|{city}|{rule["opponent"]}')
                    continue
                known.add(key)
                source_url=str(c.get('url') or CBF_OFFICIAL_EVENT_PAGES[0])
                out.append({
                    'ID':f'CBF-{date}-{rule["opponent"].upper()}', 'Titulo':event_title,
                    'Status':'Planejado','Data':date,
                    'DataBR':pe.datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y'),
                    'UF':uf,'Cidade':city,'Categoria':'Amistoso da Seleção Feminina',
                    'Organizador':'CBF','Publico':0,'Patrocinador':'','Local':venue,
                    'Latitude':None,'Longitude':None,'Link':source_url,
                    'Observacoes':f"Amistoso Brasil x {rule['opponent']} confirmado; evento materializado independentemente da notícia.",
                    'Mes':'','Ano':int(date[:4]),'Regiao':'',
                })
                print(f'official_event_extracted={date}|{city}|{venue}|origin={origin}')
    return out


def rss_candidates_v55():
    primary=_primary_cbf_candidates()
    rss=_original_rss_candidates()
    signals=_trusted_news_event_candidates(rss)
    pe._v55_official_events=_events_from_candidates(primary+signals)
    return primary+rss

pe.rss_candidates=rss_candidates_v55


def dump_v55(path,obj):
    if path==pe.INBOX and isinstance(obj,dict):
        extra=getattr(pe,'_v55_official_events',[])
        if extra:
            existing=list(obj.get('eventos',[]))
            keys={(str(x.get('Data') or ''),pe.norm(x.get('Titulo')),pe.norm(x.get('Cidade'))) for x in existing if isinstance(x,dict)}
            added=0
            for event in extra:
                key=(event['Data'],pe.norm(event['Titulo']),pe.norm(event['Cidade']))
                if key not in keys:
                    existing.append(event); keys.add(key); added+=1
            obj=dict(obj); obj['eventos']=existing
            print(f'official_events_added_to_inbox={added}')
    return _original_dump(path,obj)

pe.dump=dump_v55

if __name__=='__main__':
    raise SystemExit(pe.main())
