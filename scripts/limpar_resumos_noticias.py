#!/usr/bin/env python3
"""Saneia e encurta resumos de notícias já publicadas.

Conservador:
- não consulta Airtable;
- não altera título, data, link, tema, impacto ou sentimento;
- resumos longos são encerrados em frase completa;
- só acessa a URL quando o resumo está contaminado por boilerplate.
"""
import json
from pathlib import Path
import pesquisa_editorial_compat_v3 as compat

ROOT=Path(__file__).resolve().parents[1]
NEWS=ROOT/'noticias.json'
MARKERS=('script =','googlesyndication','doubleclick','ir para o conteúdo','ir para a página inicial','menu de navegação','abrir menu principal','seu navegador não pode executar javascript','termos mais buscados','acesse sua conta ou cadastre-se','carregando...','página principal\\">','publicidade')

def suspicious(text):
    value=str(text or '').strip().casefold()
    return bool(value) and any(marker in value for marker in MARKERS)

def main():
    try:items=json.loads(NEWS.read_text(encoding='utf-8'))
    except Exception as exc:print(f'news_cleanup_read_error={type(exc).__name__}:{exc}'); return 1
    if not isinstance(items,list):print('news_cleanup_skipped=not_a_list'); return 0
    changed=0
    for item in items:
        if not isinstance(item,dict):continue
        original=' '.join(str(item.get('Resumo') or '').split()).strip()
        clean=original
        if suspicious(original):
            link=str(item.get('Link') or '').strip()
            if link.startswith(('http://','https://')):
                fetched,_=compat.fetch_article_excerpt_clean(link)
                fetched=' '.join(str(fetched or '').split()).strip()
                if len(fetched)>=100 and not suspicious(fetched):clean=fetched
        if clean and not suspicious(clean):clean=compat.shorten_summary(clean)
        if clean and clean!=original:
            item['Resumo']=clean; changed+=1
            print(f"news_summary_shortened={item.get('Titulo','')}")
    if changed:NEWS.write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'news_cleanup_changed={changed}'); return 0

if __name__=='__main__':raise SystemExit(main())
