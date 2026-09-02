#!/usr/bin/env python3
"""Mescla inclusões editoriais incrementais em dados.json/noticias.json com deduplicação."""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
INBOX = ROOT / 'editorial' / 'inbox.json'

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
    return len(fresh)

def main():
    inbox = load(INBOX, {'eventos': [], 'noticias': []})
    ne = merge(ROOT/'dados.json', inbox.get('eventos', []), 'eventos')
    nn = merge(ROOT/'noticias.json', inbox.get('noticias', []), 'noticias')
    if ne or nn:
        INBOX.write_text(json.dumps({'eventos': [], 'noticias': []}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'eventos_incluidos={ne}')
    print(f'noticias_incluidas={nn}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
