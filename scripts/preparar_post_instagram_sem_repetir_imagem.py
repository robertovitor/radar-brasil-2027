#!/usr/bin/env python3
"""Executa o preparador do Instagram bloqueando qualquer imagem já usada em posts publicados."""
from __future__ import annotations

import json
import pathlib
import re
import urllib.parse

import preparar_post_instagram_curado as base


def clean_url(value):
    value = str(value or '').strip()
    if not value:
        return ''
    p = urllib.parse.urlsplit(value)
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, '', ''))


def image_identity(value):
    """Normaliza URLs do Commons para a identidade do arquivo, ignorando tamanho do thumbnail."""
    url = clean_url(value)
    if not url:
        return ''
    p = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(p.path)
    # source_page_url: /wiki/File:Nome.jpg
    if '/wiki/' in path:
        title = path.split('/wiki/', 1)[1].replace('_', ' ')
        return 'commons:' + title.casefold()
    # thumb URL: /wikipedia/commons/thumb/a/ab/Nome.jpg/1600px-Nome.jpg
    if '/thumb/' in path:
        before_size = path.rsplit('/', 1)[0]
        filename = before_size.rsplit('/', 1)[-1]
        return 'commons-file:' + filename.casefold()
    # original Commons URL: /wikipedia/commons/a/ab/Nome.jpg
    filename = path.rsplit('/', 1)[-1]
    return (p.netloc.lower() + ':' + filename.casefold()) if filename else url


def used_image_identities():
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
        for field in ('image_page_url', 'source_page_url', 'image_source_url', 'image_url'):
            ident = image_identity(post.get(field))
            if ident:
                used.add(ident)
    return used


def candidate_identities(source_url='', source_page_url=''):
    return {x for x in (image_identity(source_url), image_identity(source_page_url)) if x}


def main():
    used = used_image_identities()

    # Desativa imagens curadas cuja fotografia/arquivo já apareceu em qualquer post publicado.
    catalog_path = pathlib.Path('instagram/imagens-curadas.json')
    original_catalog = catalog_path.read_text(encoding='utf-8') if catalog_path.exists() else None
    if original_catalog is not None:
        try:
            catalog = json.loads(original_catalog)
            for item in catalog.get('items', []):
                identities = candidate_identities(item.get('image_source_url'), item.get('source_page_url'))
                if identities & used:
                    item['reutilizacao_permitida'] = False
                    item['bloqueada_por_repeticao'] = True
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except Exception as exc:
            print('catalog_uniqueness_check_failed=' + type(exc).__name__)

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
                source_page = 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(base.clean(page.get('title')).replace(' ', '_'), safe=':/()_-')
                identities = candidate_identities(url, source_page)
                if identities & used:
                    print('image_rejected=already_used_file:' + base.clean(page.get('title')))
                    continue
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
        result = base.main()
        # Gate adicional: nunca deixe um post preparado com foto já publicada.
        batch = pathlib.Path('instagram/fila/automatica/lote-atual.json')
        if batch.exists():
            try:
                data = json.loads(batch.read_text(encoding='utf-8'))
                for post_file in data.get('posts', []):
                    p = pathlib.Path(post_file)
                    if not p.exists():
                        continue
                    post = json.loads(p.read_text(encoding='utf-8'))
                    identities = candidate_identities(post.get('image_source_url'), post.get('image_page_url'))
                    if identities & used:
                        print('IMAGE_UNIQUE_OK=false')
                        print('found=false')
                        print('reason=duplicate_image_blocked_after_render')
                        return 1
                    post['IMAGE_UNIQUE_OK'] = True
                    p.write_text(json.dumps(post, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                print('IMAGE_UNIQUE_OK=true')
            except Exception as exc:
                print('IMAGE_UNIQUE_OK=false')
                print('uniqueness_final_gate_failed=' + type(exc).__name__)
                return 1
        return result
    finally:
        base.find_commons_image = original_find
        if original_catalog is not None:
            catalog_path.write_text(original_catalog, encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
