#!/usr/bin/env python3
"""Executa o preparador do Instagram bloqueando imagens já usadas em posts publicados."""
from __future__ import annotations

import json
import pathlib
import urllib.parse

import preparar_post_instagram_curado as base


def clean_url(value):
    value = str(value or '').strip()
    if not value:
        return ''
    p = urllib.parse.urlsplit(value)
    # Ignora diferenças cosméticas de query/fragmento e normaliza host/path.
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, '', ''))


def used_image_urls():
    ledger = base.load('instagram/publicados.json', {'published': []})
    used = set()
    for row in ledger.get('published', []):
        post_file = str(row.get('post_file') or '').strip()
        if not post_file:
            continue
        p = pathlib.Path(post_file)
        if not p.exists():
            continue
        try:
            post = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        for field in ('image_source_url', 'image_page_url', 'image_url'):
            url = clean_url(post.get(field))
            if url:
                used.add(url)
    return used


def main():
    used = used_image_urls()

    # Desativa, somente nesta execução, imagens curadas que já apareceram antes.
    catalog_path = pathlib.Path('instagram/imagens-curadas.json')
    original_catalog = catalog_path.read_text(encoding='utf-8') if catalog_path.exists() else None
    if original_catalog is not None:
        try:
            catalog = json.loads(original_catalog)
            for item in catalog.get('items', []):
                if clean_url(item.get('image_source_url')) in used:
                    item['reutilizacao_permitida'] = False
                    item['bloqueada_por_repeticao'] = True
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except Exception:
            pass

    original_find = base.find_commons_image

    def find_unique_commons_image(item):
        search_context = item.get('search_context') or item['title']
        for query in base.commons_queries(search_context):
            params = {
                'action': 'query', 'generator': 'search',
                'gsrsearch': query + ' filetype:bitmap', 'gsrnamespace': '6', 'gsrlimit': '20',
                'prop': 'imageinfo', 'iiprop': 'url|mime|size|extmetadata', 'iiurlwidth': '1600',
                'format': 'json', 'formatversion': '2'
            }
            try:
                data = base.http_json(base.COMMONS_API + '?' + urllib.parse.urlencode(params))
            except Exception as exc:
                print('commons_search_failed=' + type(exc).__name__)
                continue
            pages = (data.get('query') or {}).get('pages') or []
            for page in pages:
                info = (page.get('imageinfo') or [{}])[0]
                mime = base.clean(info.get('mime')).casefold()
                width = int(info.get('width') or 0)
                height = int(info.get('height') or 0)
                meta = info.get('extmetadata') or {}
                if mime not in ('image/jpeg', 'image/png', 'image/webp') or width < 700 or height < 450 or not base.license_allowed(meta):
                    continue
                ok, reason = base.semantic_image_ok(item, page, meta, query)
                if not ok:
                    continue
                url = base.clean(info.get('thumburl') or info.get('url'))
                if not url:
                    continue
                if clean_url(url) in used:
                    print('image_rejected=already_used:' + base.clean(page.get('title')))
                    continue
                source_page = 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(base.clean(page.get('title')).replace(' ', '_'), safe=':/()_-')
                return {
                    'image_source_url': url,
                    'source_page_url': source_page,
                    'credito': base.commons_credit(meta),
                    'licenca': base.commons_license(meta),
                    'reutilizacao_permitida': True,
                    'auto_found': True,
                    'query': query,
                    'semantic_reason': reason,
                }
        return None

    base.find_commons_image = find_unique_commons_image
    try:
        return base.main()
    finally:
        base.find_commons_image = original_find
        if original_catalog is not None:
            catalog_path.write_text(original_catalog, encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
