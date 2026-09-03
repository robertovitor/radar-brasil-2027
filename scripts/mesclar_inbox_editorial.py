#!/usr/bin/env python3
"""Mescla inclusões editoriais incrementais e registra novidades para o Instagram."""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
INBOX = ROOT / 'editorial' / 'inbox.json'
IG_STATE = ROOT / 'instagram' / 'conteudo-conhecido.json'

def load(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def norm(v):
    return ' '.join(str(v or '').strip().casefold().split())

def merge(target_path, incoming, kind):
    current = load(target_path, [])
    if kind == 'noticias':
        seen_links = {norm(x.get('Link')) for x in current if x.get('Link')}
        seen_titles = {norm(x.get('Titulo')) for x in current if x.get('Titulo')}
        fresh = [x for x in incoming if norm(x.get('Link')) not in seen_links and norm(x.get('Titulo')) not in seen_titles]
        current = fresh + current
    else:
        seen_ids = {norm(x.get('ID')) for x in current if x.get('ID')}
        seen_links = {norm(x.get('Link')) for x in current if x.get('Link')}
        fresh = [x for x in incoming if norm(x.get('ID')) not in seen_ids and (not x.get('Link') or norm(x.get('Link')) not in seen_links)]
        current.extend(fresh)
    if fresh:
        target_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return fresh

def instagram_key(kind, item):
    if kind == 'eventos':
        ident = norm(item.get('ID') or item.get('Titulo'))
        return f'instagram:evento:{ident}' if ident else ''
    ident = norm(item.get('Link') or item.get('Titulo'))
    return f'instagram:noticia:{ident}' if ident else ''

def update_instagram_state(new_events, new_news):
    state = load(IG_STATE, {'known': [], 'pending_new': []})
    known = list(dict.fromkeys(state.get('known', [])))
    pending = list(dict.fromkeys(state.get('pending_new', [])))
    for kind, items in (('eventos', new_events), ('noticias', new_news)):
        for item in items:
            key = instagram_key(kind, item)
            if key and key not in known:
                known.append(key)
            if key and key not in pending:
                pending.append(key)
    if new_events or new_news:
        IG_STATE.parent.mkdir(parents=True, exist_ok=True)
        IG_STATE.write_text(json.dumps({'known': known, 'pending_new': pending}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    inbox = load(INBOX, {'eventos': [], 'noticias': []})
    fresh_events = merge(ROOT/'dados.json', inbox.get('eventos', []), 'eventos')
    fresh_news = merge(ROOT/'noticias.json', inbox.get('noticias', []), 'noticias')
    update_instagram_state(fresh_events, fresh_news)
    if fresh_events or fresh_news:
        INBOX.write_text(json.dumps({'eventos': [], 'noticias': []}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'eventos_incluidos={len(fresh_events)}')
    print(f'noticias_incluidas={len(fresh_news)}')
    print(f'instagram_pendentes_adicionados={len(fresh_events)+len(fresh_news)}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
