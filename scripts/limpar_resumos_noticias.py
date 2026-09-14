#!/usr/bin/env python3
"""Corrige apenas resumos de noticias claramente contaminados por boilerplate.

Conservador por desenho:
- não consulta Airtable;
- não altera título, data, link, tema, impacto ou sentimento;
- não toca em resumos já limpos;
- só substitui quando consegue extrair texto editorial melhor da URL existente.
"""
import json
from pathlib import Path
import pesquisa_editorial_compat_v3 as compat

ROOT = Path(__file__).resolve().parents[1]
NEWS = ROOT / 'noticias.json'

MARKERS = (
    'script =', 'googlesyndication', 'doubleclick', 'ir para o conteúdo',
    'ir para a página inicial', 'menu de navegação', 'abrir menu principal',
    'seu navegador não pode executar javascript', 'termos mais buscados',
    'acesse sua conta ou cadastre-se', 'carregando...', 'página principal\\">',
    'publicidade',
)


def suspicious(text):
    value = str(text or '').strip().casefold()
    if not value:
        return False
    return any(marker in value for marker in MARKERS)


def main():
    try:
        items = json.loads(NEWS.read_text(encoding='utf-8'))
    except Exception as exc:
        print(f'news_cleanup_read_error={type(exc).__name__}:{exc}')
        return 1
    if not isinstance(items, list):
        print('news_cleanup_skipped=not_a_list')
        return 0

    changed = 0
    for item in items:
        if not isinstance(item, dict) or not suspicious(item.get('Resumo')):
            continue
        link = str(item.get('Link') or '').strip()
        if not link.startswith(('http://', 'https://')):
            continue
        clean, _ = compat.fetch_article_excerpt_clean(link)
        clean = ' '.join(str(clean or '').split()).strip()[:900]
        if len(clean) < 100 or suspicious(clean):
            print(f"news_cleanup_kept={item.get('Titulo','')}")
            continue
        item['Resumo'] = clean
        changed += 1
        print(f"news_cleanup_fixed={item.get('Titulo','')}")

    if changed:
        NEWS.write_text(json.dumps(items, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'news_cleanup_changed={changed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())