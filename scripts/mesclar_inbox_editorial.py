#!/usr/bin/env python3
"""Mescla inclusões editoriais, deduplica fatos/eventos e registra novidades para o Instagram."""
import json, pathlib, re, unicodedata
from datetime import datetime
from difflib import SequenceMatcher

ROOT = pathlib.Path(__file__).resolve().parents[1]
INBOX = ROOT / 'editorial' / 'inbox.json'
IG_STATE = ROOT / 'instagram' / 'conteudo-conhecido.json'

# Duplicações já auditadas no acervo. Mantemos o registro canônico e removemos a cópia.
DROP_EVENT_IDS = {
    'evt-wifs-20260914',               # dup de EVT-0022
    'evt-20260824-workshop-sede',      # dup de EVT-0023
    'evt-7set2026-bsb',                # dup de EVT-20260907-DESFILE-COPA2027
}
DROP_NEWS_LINK_PARTS = {
    'vod.fifa.com/es/news/copa-mundial-femenina-brasil-2027-apertura-plazo-presentacion-solicitudes-programa-voluntariado',
    'futebolbaiano.com.br/2026/09/r-400-milhoes-e-novos-voos-bahia-se-prepara-para-receber-turistas-na-copa.html',
    'gov.br/esporte/pt-br/noticias/sancionada-lei-que-cria-condicoes-para-realizacao-da-copa-do-mundo-feminina-de-2027',
}

STOP = {
    'a','as','ao','aos','da','das','de','do','dos','e','em','na','nas','no','nos','o','os','para','por','com','um','uma',
    'copa','mundo','mundial','feminina','feminino','fifa','brasil','2027','2026','rumo','sobre','durante','nova','novo'
}


def load(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def norm(v):
    s = str(v or '').strip().casefold()
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def tokens(v):
    return {t for t in norm(v).split() if len(t) > 2 and t not in STOP}


def jac(a, b):
    a, b = tokens(a), tokens(b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def seq(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def parse_date(v):
    try:
        return datetime.strptime(str(v or '')[:10], '%Y-%m-%d').date()
    except Exception:
        return None


def date_gap(a, b):
    da, db = parse_date(a), parse_date(b)
    return abs((da-db).days) if da and db else 9999


def same_place(a, b, kind):
    if kind == 'eventos':
        pa = norm(f"{a.get('Cidade','')} {a.get('UF','')}")
        pb = norm(f"{b.get('Cidade','')} {b.get('UF','')}")
    else:
        pa = norm(a.get('CidadeUF'))
        pb = norm(b.get('CidadeUF'))
    return bool(pa and pb and pa == pb)


def legislative_progression(a, b):
    texta = norm(f"{a.get('Titulo','')} {a.get('Resumo','')}")
    textb = norm(f"{b.get('Titulo','')} {b.get('Resumo','')}")
    # Câmara -> Senado, projeto -> sanção etc. são desdobramentos, não duplicação.
    stages = ('camara','senado','sancao','sancionado','presidencia','promulgacao','homologacao')
    sa = {x for x in stages if x in texta}
    sb = {x for x in stages if x in textb}
    return bool(sa and sb and sa != sb)


def is_duplicate(a, b, kind):
    if kind == 'eventos':
        if norm(a.get('ID')) and norm(a.get('ID')) == norm(b.get('ID')):
            return True
        if norm(a.get('Link')) and norm(a.get('Link')) == norm(b.get('Link')):
            return True
        if date_gap(a.get('Data'), b.get('Data')) == 0 and same_place(a, b, kind):
            tj = jac(a.get('Titulo'), b.get('Titulo'))
            ts = seq(a.get('Titulo'), b.get('Titulo'))
            # Mesma data/cidade + títulos semanticamente próximos = mesmo acontecimento.
            if tj >= 0.48 or ts >= 0.78:
                return True
        return False

    # notícias
    la, lb = norm(a.get('Link')), norm(b.get('Link'))
    if la and la == lb:
        return True
    if norm(a.get('Titulo')) == norm(b.get('Titulo')):
        return True
    if legislative_progression(a, b):
        return False
    if date_gap(a.get('Data'), b.get('Data')) <= 3 and same_place(a, b, kind):
        tj = jac(a.get('Titulo'), b.get('Titulo'))
        ts = seq(a.get('Titulo'), b.get('Titulo'))
        sj = jac(a.get('Resumo'), b.get('Resumo'))
        nums_a = set(re.findall(r'\b\d+[\d.,]*\b', norm(a.get('Resumo'))))
        nums_b = set(re.findall(r'\b\d+[\d.,]*\b', norm(b.get('Resumo'))))
        distinctive_number = bool(nums_a & nums_b)
        if tj >= 0.62 or ts >= 0.82:
            return True
        if tj >= 0.28 and sj >= 0.36:
            return True
        if distinctive_number and tj >= 0.20 and sj >= 0.27:
            return True
    return False


def cleanup_current(items, kind):
    kept, removed = [], []
    for item in items:
        if kind == 'eventos' and norm(item.get('ID')) in DROP_EVENT_IDS:
            removed.append(item); continue
        if kind == 'noticias':
            link = norm(item.get('Link')).replace(' ', '')
            if any(norm(p).replace(' ', '') in link for p in DROP_NEWS_LINK_PARTS):
                removed.append(item); continue
        dup = next((x for x in kept if is_duplicate(item, x, kind)), None)
        if dup:
            removed.append(item)
        else:
            kept.append(item)
    return kept, removed


def instagram_key(kind, item):
    if kind == 'eventos':
        ident = norm(item.get('ID') or item.get('Titulo'))
        return f'instagram:evento:{ident}' if ident else ''
    ident = norm(item.get('Link') or item.get('Titulo'))
    return f'instagram:noticia:{ident}' if ident else ''


def clean_instagram_state(removed_events, removed_news):
    state = load(IG_STATE, {'known': [], 'pending_new': []})
    drop = {instagram_key('eventos', x) for x in removed_events} | {instagram_key('noticias', x) for x in removed_news}
    drop.discard('')
    known = [k for k in dict.fromkeys(state.get('known', [])) if k not in drop]
    pending = [k for k in dict.fromkeys(state.get('pending_new', [])) if k not in drop]
    changed = known != state.get('known', []) or pending != state.get('pending_new', [])
    if changed:
        IG_STATE.write_text(json.dumps({'known': known, 'pending_new': pending}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return changed


def merge(target_path, incoming, kind):
    current = load(target_path, [])
    current, removed = cleanup_current(current, kind)
    fresh = []
    for item in incoming:
        if any(is_duplicate(item, x, kind) for x in current + fresh):
            continue
        fresh.append(item)
    merged = (fresh + current) if kind == 'noticias' else (current + fresh)
    original = load(target_path, [])
    if merged != original:
        target_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return fresh, removed


def update_instagram_state(new_events, new_news):
    state = load(IG_STATE, {'known': [], 'pending_new': []})
    known = list(dict.fromkeys(state.get('known', [])))
    pending = list(dict.fromkeys(state.get('pending_new', [])))
    for kind, items in (('eventos', new_events), ('noticias', new_news)):
        for item in items:
            key = instagram_key(kind, item)
            if key and key not in known: known.append(key)
            if key and key not in pending: pending.append(key)
    if new_events or new_news:
        IG_STATE.parent.mkdir(parents=True, exist_ok=True)
        IG_STATE.write_text(json.dumps({'known': known, 'pending_new': pending}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    inbox = load(INBOX, {'eventos': [], 'noticias': []})
    fresh_events, removed_events = merge(ROOT/'dados.json', inbox.get('eventos', []), 'eventos')
    fresh_news, removed_news = merge(ROOT/'noticias.json', inbox.get('noticias', []), 'noticias')
    clean_instagram_state(removed_events, removed_news)
    update_instagram_state(fresh_events, fresh_news)

    incoming_events = inbox.get('eventos', [])
    incoming_news = inbox.get('noticias', [])
    processed = len(incoming_events) + len(incoming_news)
    if processed:
        INBOX.write_text(json.dumps({'eventos': [], 'noticias': []}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    discarded = processed - len(fresh_events) - len(fresh_news)
    print(f'eventos_incluidos={len(fresh_events)}')
    print(f'noticias_incluidas={len(fresh_news)}')
    print(f'eventos_duplicados_removidos={len(removed_events)}')
    print(f'noticias_duplicadas_removidas={len(removed_news)}')
    print(f'itens_descartados_como_duplicados={discarded}')
    print(f'instagram_pendentes_adicionados={len(fresh_events)+len(fresh_news)}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
