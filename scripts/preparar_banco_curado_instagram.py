#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib

import preparar_post_instagram_curado as base
import selecionar_imagem_banco_instagram as bank

CURATED = pathlib.Path('instagram/imagens-curadas.json')


def load_curated():
    if CURATED.exists():
        try:
            data = json.loads(CURATED.read_text(encoding='utf-8'))
            if isinstance(data, dict) and isinstance(data.get('items'), list):
                return data
        except Exception:
            pass
    return {'version': 3, 'description': 'Imagens curadas e imagens do banco aprovado para o Instagram.', 'items': []}


def main():
    events = base.load('dados.json', [])
    news = base.load('noticias.json', [])
    ledger = base.load('instagram/publicados.json', {'published': []})
    state = base.load('instagram/conteudo-conhecido.json', {'pending_new': []})
    blocked = base.load('instagram/bloqueados-publicacao.json', {'blocked_keys': []})

    published = {base.clean(x.get('key')) for x in ledger.get('published', []) if isinstance(x, dict)}
    published |= {base.clean(x) for x in blocked.get('blocked_keys', [])}
    pending = [base.clean(x) for x in state.get('pending_new', [])]
    ranked = base.candidates(events, news, published, pending, base.published_titles(ledger))

    catalog = load_curated()
    items = catalog.get('items', [])
    by_key = {base.clean(x.get('idempotency_key')): x for x in items if isinstance(x, dict) and base.clean(x.get('idempotency_key'))}
    session_used = set()
    added = 0
    updated = 0

    # Prepara um estoque pequeno de próximas pautas, evitando inflar o arquivo.
    for item in ranked[:30]:
        key = base.clean(item.get('key'))
        current = by_key.get(key)
        # Curadoria manual válida sempre tem precedência sobre o banco automático.
        if current and current.get('reutilizacao_permitida') is True and current.get('origem') != 'banco_aprovado':
            continue

        picked = bank.select(item, session_used)
        if not picked:
            continue
        session_used |= {bank.identity(picked.get('image_source_url')), bank.identity(picked.get('source_page_url'))} - {''}
        row = {
            'idempotency_key': key,
            'image_source_url': picked.get('image_source_url') or '',
            'source_page_url': picked.get('source_page_url') or '',
            'credito': picked.get('credito') or '',
            'licenca': picked.get('licenca') or '',
            'reutilizacao_permitida': True,
            'justificativa': 'Selecionada automaticamente do banco editorial aprovado por relevância temática e antirrepetição.',
            'origem': 'banco_aprovado',
            'bank_image_id': picked.get('bank_image_id') or '',
            'bank_category': picked.get('bank_category') or '',
            'semantic_reason': picked.get('semantic_reason') or '',
        }
        if current:
            current.clear(); current.update(row); updated += 1
        else:
            items.append(row); by_key[key] = row; added += 1

    catalog['version'] = max(int(catalog.get('version') or 0), 3)
    catalog['description'] = 'Imagens selecionadas para posts do Radar Brasil 2027. Itens do banco_aprovado usam somente licenças abertas e passam por filtros editoriais e antirrepetição.'
    catalog['items'] = items
    CURATED.parent.mkdir(parents=True, exist_ok=True)
    CURATED.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'bank_curated_added={added}')
    print(f'bank_curated_updated={updated}')
    print(f'bank_curated_total={sum(1 for x in items if isinstance(x,dict) and x.get("origem")=="banco_aprovado" and x.get("reutilizacao_permitida") is True)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
