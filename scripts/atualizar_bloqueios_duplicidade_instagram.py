#!/usr/bin/env python3
from __future__ import annotations

import difflib
import json
import pathlib
import re
import unicodedata

LEDGER = pathlib.Path('instagram/publicados.json')
NEWS = pathlib.Path('noticias.json')
EVENTS = pathlib.Path('dados.json')
BLOCKED = pathlib.Path('instagram/bloqueados-publicacao.json')

STOP = {
    'a','o','as','os','de','da','do','das','dos','e','em','na','no','nas','nos','para','por','com','sem','um','uma',
    'copa','mundo','mundial','feminina','feminino','fifa','2027','brasil','brasileira','brasileiro','radar','noticia','evento',
    'sobre','ate','apos','seu','sua','seus','suas','que','como','mais','menos','novo','nova','novos','novas','confirma',
    'confirmam','prepara','preparam','destaca','adequacao','adequacoes'
}

def clean(v):
    return re.sub(r'\s+', ' ', str(v or '')).strip()

def norm(v):
    s = unicodedata.normalize('NFKD', clean(v).casefold())
    return ''.join(c for c in s if not unicodedata.combining(c))

def tokens(v):
    out=[]
    for raw in re.findall(r'[a-z0-9áàâãéêíóôõúç]+', clean(v).casefold()):
        t=norm(raw)
        if len(t) >= 3 and t not in STOP:
            out.append(t)
    return set(out)

def title_from_post(post):
    caption=clean(post.get('caption'))
    if not caption:
        return ''
    return re.sub(r'^[^\wÀ-ÿ]+', '', caption.splitlines()[0]).strip()

def story_text_from_post(post):
    caption=clean(post.get('caption'))
    return clean(title_from_post(post) + ' ' + caption)

def near_duplicate(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = tokens(a), tokens(b)
    if len(ta) < 3 or len(tb) < 3:
        return False
    shared=len(ta & tb)
    coverage=shared/min(len(ta),len(tb))
    jaccard=shared/len(ta | tb)
    seq=difflib.SequenceMatcher(None, na, nb).ratio()
    return (
        (shared >= 4 and coverage >= 0.72) or
        (shared >= 5 and jaccard >= 0.48) or
        (shared >= 3 and coverage >= 0.86) or
        seq >= 0.88
    )

def same_story(candidate_title, candidate_body, prior_title, prior_body):
    if near_duplicate(candidate_title, prior_title):
        return True
    ct, pt = tokens(candidate_title), tokens(prior_title)
    cb, pb = tokens(candidate_body), tokens(prior_body)
    title_shared=len(ct & pt)
    body_shared=len(cb & pb)
    title_cov=(title_shared/min(len(ct),len(pt))) if ct and pt else 0
    body_cov=(body_shared/min(len(cb),len(pb))) if cb and pb else 0
    # Exige coincidência forte tanto no assunto quanto no texto, reduzindo falso positivo
    # entre notícias diferentes sobre o mesmo tema geral da Copa.
    return title_shared >= 3 and title_cov >= 0.55 and body_shared >= 5 and body_cov >= 0.55

def load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default

def main():
    ledger=load(LEDGER, {'published':[]})
    prior=[]
    for row in ledger.get('published',[]):
        if not isinstance(row,dict):
            continue
        p=pathlib.Path(clean(row.get('post_file')))
        if not p.exists():
            continue
        post=load(p,{})
        title=title_from_post(post)
        body=story_text_from_post(post)
        if title:
            prior.append((clean(row.get('key')), title, body))

    state=load(BLOCKED, {'blocked_keys':[]})
    blocked=set(clean(x) for x in state.get('blocked_keys',[]) if clean(x))
    reasons=state.get('duplicate_reasons',{}) if isinstance(state.get('duplicate_reasons',{}),dict) else {}
    added=[]

    for x in load(NEWS,[]):
        title=clean(x.get('Titulo'))
        key='instagram:noticia:'+clean(x.get('Link') or title).casefold()
        body=clean(title+' '+clean(x.get('Resumo'))+' '+clean(x.get('Tema'))+' '+clean(x.get('Veiculo')))
        if not title or key in blocked or any(key == pk for pk,_,_ in prior):
            continue
        for prior_key, prior_title, prior_body in prior:
            if same_story(title,body,prior_title,prior_body):
                blocked.add(key)
                reasons[key]={'reason':'duplicate_story_already_published','matches':prior_key,'candidate_title':title,'published_title':prior_title}
                added.append(key)
                break

    for x in load(EVENTS,[]):
        title=clean(x.get('Titulo'))
        key='instagram:evento:'+clean(x.get('ID') or title).casefold()
        body=clean(title+' '+clean(x.get('Observacoes'))+' '+clean(x.get('Cidade'))+' '+clean(x.get('UF'))+' '+clean(x.get('Organizador')))
        if not title or key in blocked or any(key == pk for pk,_,_ in prior):
            continue
        for prior_key, prior_title, prior_body in prior:
            if same_story(title,body,prior_title,prior_body):
                blocked.add(key)
                reasons[key]={'reason':'duplicate_story_already_published','matches':prior_key,'candidate_title':title,'published_title':prior_title}
                added.append(key)
                break

    new_state=dict(state) if isinstance(state,dict) else {}
    new_state['blocked_keys']=sorted(blocked)
    new_state['duplicate_reasons']=reasons
    BLOCKED.parent.mkdir(parents=True,exist_ok=True)
    serialized=json.dumps(new_state,ensure_ascii=False,indent=2)+'\n'
    before=BLOCKED.read_text(encoding='utf-8') if BLOCKED.exists() else ''
    if serialized != before:
        BLOCKED.write_text(serialized,encoding='utf-8')
        print('dedup_state_changed=true')
    else:
        print('dedup_state_changed=false')
    print('duplicates_blocked_now='+str(len(added)))
    for key in added:
        print('duplicate_blocked='+key)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
