#!/usr/bin/env python3
"""Mescla inclusões editoriais, bloqueia duplicações do mesmo fato e enfileira novidades."""
import json, pathlib, re, unicodedata
from datetime import datetime
from difflib import SequenceMatcher

ROOT = pathlib.Path(__file__).resolve().parents[1]
INBOX = ROOT / 'editorial' / 'inbox.json'
IG_STATE = ROOT / 'instagram' / 'conteudo-conhecido.json'

# Duplicações confirmadas na auditoria. A cópia é removida caso reapareça.
DROP_EVENT_IDS = {
    'evt-wifs-20260914',
    'evt-20260824-workshop-sede',
    'evt-7set2026-bsb',
}
DROP_NEWS_LINK_PARTS = {
    'vod.fifa.com/es/news/copa-mundial-femenina-brasil-2027-apertura-plazo-presentacion-solicitudes-programa-voluntariado',
    'futebolbaiano.com.br/2026/09/r-400-milhoes-e-novos-voos-bahia-se-prepara-para-receber-turistas-na-copa.html',
    'gov.br/esporte/pt-br/noticias/sancionada-lei-que-cria-condicoes-para-realizacao-da-copa-do-mundo-feminina-de-2027',
}
STOP = {
    'a','as','ao','aos','da','das','de','do','dos','e','em','na','nas','no','nos','o','os','para','por','com','um','uma',
    'copa','mundo','mundial','feminina','feminino','fifa','brasil','2027','2026','rumo','sobre','durante'
}


def load(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def norm(v):
    s = str(v or '').strip().casefold()
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def raw_id(v):
    return str(v or '').strip().casefold()


def url_norm(v):
    s = str(v or '').strip().casefold().replace('https://','').replace('http://','')
    if s.startswith('www.'):
        s = s[4:]
    return s.rstrip('/')


def tokens(v):
    return {t for t in norm(v).split() if len(t) > 2 and t not in STOP}


def jac(a,b):
    a,b=tokens(a),tokens(b)
    return len(a&b)/len(a|b) if a and b else 0.0


def seq(a,b):
    return SequenceMatcher(None,norm(a),norm(b)).ratio()


def parse_date(v):
    try:
        return datetime.strptime(str(v or '')[:10],'%Y-%m-%d').date()
    except Exception:
        return None


def date_gap(a,b):
    da,db=parse_date(a),parse_date(b)
    return abs((da-db).days) if da and db else 9999


def same_place(a,b,kind):
    if kind == 'eventos':
        pa = norm(f"{a.get('Cidade','')} {a.get('UF','')}")
        pb = norm(f"{b.get('Cidade','')} {b.get('UF','')}")
    else:
        pa = norm(a.get('CidadeUF'))
        pb = norm(b.get('CidadeUF'))
    return bool(pa and pb and pa == pb)


def legislative_progression(a,b):
    ta=norm(f"{a.get('Titulo','')} {a.get('Resumo','')}")
    tb=norm(f"{b.get('Titulo','')} {b.get('Resumo','')}")
    stages=('camara','senado','sancao','sancionado','presidencia','promulgacao','homologacao')
    sa={x for x in stages if x in ta}
    sb={x for x in stages if x in tb}
    return bool(sa and sb and sa != sb)


def duplicate_incoming(a,b,kind):
    """Deduplicação conservadora para novas inclusões; fonte diferente não cria fato novo."""
    if kind == 'eventos':
        if norm(a.get('ID')) and norm(a.get('ID')) == norm(b.get('ID')):
            return True
        if url_norm(a.get('Link')) and url_norm(a.get('Link')) == url_norm(b.get('Link')):
            return True
        if date_gap(a.get('Data'),b.get('Data')) == 0 and same_place(a,b,kind):
            return jac(a.get('Titulo'),b.get('Titulo')) >= 0.55 or seq(a.get('Titulo'),b.get('Titulo')) >= 0.82
        return False

    if url_norm(a.get('Link')) and url_norm(a.get('Link')) == url_norm(b.get('Link')):
        return True
    if norm(a.get('Titulo')) == norm(b.get('Titulo')):
        return True
    if legislative_progression(a,b):
        return False
    if date_gap(a.get('Data'),b.get('Data')) <= 2 and same_place(a,b,kind):
        return jac(a.get('Titulo'),b.get('Titulo')) >= 0.70 or seq(a.get('Titulo'),b.get('Titulo')) >= 0.86
    return False


def explicit_cleanup(events, news):
    ev_removed=[]; ev=[]
    for x in events:
        if raw_id(x.get('ID')) in DROP_EVENT_IDS:
            ev_removed.append(x)
        else:
            ev.append(x)

    nw_removed=[]; nw=[]; seen_urls=set()
    for x in news:
        u=url_norm(x.get('Link'))
        if any(url_norm(p) in u for p in DROP_NEWS_LINK_PARTS):
            nw_removed.append(x)
            continue
        # URLs iguais com ou sem www são a mesma matéria/fonte.
        if u and u in seen_urls:
            nw_removed.append(x)
            continue
        if u:
            seen_urls.add(u)
        nw.append(x)
    return ev,nw,ev_removed,nw_removed


def instagram_key(kind,item):
    if kind == 'eventos':
        ident=norm(item.get('ID') or item.get('Titulo'))
        return f'instagram:evento:{ident}' if ident else ''
    ident=norm(item.get('Link') or item.get('Titulo'))
    return f'instagram:noticia:{ident}' if ident else ''


def main():
    events=load(ROOT/'dados.json',[])
    news=load(ROOT/'noticias.json',[])
    state=load(IG_STATE,{'known':[],'pending_new':[]})
    original_events=list(events)
    original_news=list(news)
    original_state=json.loads(json.dumps(state))

    events,news,removed_events,removed_news=explicit_cleanup(events,news)
    inbox=load(INBOX,{'eventos':[],'noticias':[]})

    fresh_events=[]
    for x in inbox.get('eventos',[]):
        if not any(duplicate_incoming(x,y,'eventos') for y in events+fresh_events):
            fresh_events.append(x)

    fresh_news=[]
    for x in inbox.get('noticias',[]):
        if not any(duplicate_incoming(x,y,'noticias') for y in news+fresh_news):
            fresh_news.append(x)

    events.extend(fresh_events)
    news=fresh_news+news

    drop={instagram_key('eventos',x) for x in removed_events}|{instagram_key('noticias',x) for x in removed_news}
    drop.discard('')
    known=[k for k in dict.fromkeys(state.get('known',[])) if k not in drop]
    pending=[k for k in dict.fromkeys(state.get('pending_new',[])) if k not in drop]
    for kind,items in (('eventos',fresh_events),('noticias',fresh_news)):
        for x in items:
            k=instagram_key(kind,x)
            if k and k not in known:
                known.append(k)
            if k and k not in pending:
                pending.append(k)
    state={'known':known,'pending_new':pending}

    if events != original_events:
        (ROOT/'dados.json').write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if news != original_news:
        (ROOT/'noticias.json').write_text(json.dumps(news,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if state != original_state:
        IG_STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if inbox.get('eventos') or inbox.get('noticias'):
        INBOX.write_text(json.dumps({'eventos':[],'noticias':[]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    discarded=len(inbox.get('eventos',[]))+len(inbox.get('noticias',[]))-len(fresh_events)-len(fresh_news)
    print(f'eventos_duplicados_removidos={len(removed_events)}')
    print(f'noticias_duplicadas_removidas={len(removed_news)}')
    print(f'eventos_incluidos={len(fresh_events)}')
    print(f'noticias_incluidas={len(fresh_news)}')
    print(f'itens_descartados_como_duplicados={discarded}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
