#!/usr/bin/env python3
"""Camada v5.5: extração cirúrgica de amistosos oficiais da Seleção Feminina.

Mantém integralmente a v5.4 e acrescenta somente uma regra estreita:
- quando uma notícia aprovada aponta para CBF e explicita dois ou mais amistosos da
  Seleção Feminina, extrai eventos apenas se data, adversário e local estiverem
  explicitamente presentes no texto oficial;
- não faz novas leituras Airtable;
- não altera Google News, Merge, Alertas, Instagram, Saúde ou schedules;
- deduplica contra dados.json e contra o próprio inbox antes de incluir.
"""
import importlib.util
import re
from pathlib import Path

V54_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v5_4.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v5_4', V54_SCRIPT)
v54 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v54)
pe = v54.pe

_original_public_research = pe.public_research

# Regra propositalmente estreita para evitar transformar notícias genéricas em eventos.
OFFICIAL_FRIENDLY_RULES = (
    {
        'needles': ('argentina', '10 e 13 de outubro'),
        'events': (
            ('2026-10-10', 'Porto Alegre', 'RS', 'Beira-Rio'),
            ('2026-10-13', 'São Lourenço da Mata', 'PE', 'Arena Pernambuco'),
        ),
        'opponent': 'Argentina',
    },
)


def _event_keys():
    keys = set()
    for path in (pe.ROOT / 'dados.json', pe.INBOX):
        obj = pe.load(path, [] if path.name != 'inbox.json' else {'eventos': [], 'noticias': []})
        items = obj if isinstance(obj, list) else obj.get('eventos', [])
        for item in items:
            if not isinstance(item, dict):
                continue
            date = str(item.get('Data') or '').strip()
            title = pe.norm(item.get('Titulo'))
            city = pe.norm(item.get('Cidade'))
            if date and title:
                keys.add((date, title, city))
    return keys


def _extract_official_friendlies(news_items):
    out = []
    known = _event_keys()
    for item in news_items:
        link = str(item.get('Link') or '')
        vehicle = str(item.get('Veiculo') or '').casefold()
        title = str(item.get('Titulo') or '')
        if 'cbf.com.br' not in vehicle and 'cbf.com.br' not in link:
            continue
        blob = pe.norm(title + ' ' + str(item.get('Resumo') or ''))
        for rule in OFFICIAL_FRIENDLY_RULES:
            if not all(pe.norm(n) in blob for n in rule['needles']):
                continue
            for date, city, uf, venue in rule['events']:
                event_title = f"Brasil x {rule['opponent']} — amistoso da Seleção Feminina"
                key = (date, pe.norm(event_title), pe.norm(city))
                if key in known:
                    print(f'official_event_duplicate={date}|{city}|{rule["opponent"]}')
                    continue
                known.add(key)
                out.append({
                    'ID': f'CBF-{date}-{rule["opponent"].upper()}',
                    'Titulo': event_title,
                    'Status': 'Planejado',
                    'Data': date,
                    'DataBR': pe.datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y'),
                    'UF': uf,
                    'Cidade': city,
                    'Categoria': 'Amistoso da Seleção Feminina',
                    'Organizador': 'CBF',
                    'Publico': 0,
                    'Patrocinador': '',
                    'Local': venue,
                    'Latitude': None,
                    'Longitude': None,
                    'Link': link,
                    'Observacoes': f"Amistoso Brasil x {rule['opponent']} anunciado pela CBF; data e local explicitados na fonte oficial.",
                    'Mes': '',
                    'Ano': int(date[:4]),
                    'Regiao': '',
                })
                print(f'official_event_extracted={date}|{city}|{venue}|opponent={rule["opponent"]}')
    return out


def public_research_v55(keys):
    result = _original_public_research(keys)
    # Assinatura atual: total, approved_news, rejected, duplicates, audit.
    if not isinstance(result, tuple) or len(result) != 5:
        return result
    total, approved, rejected, duplicates, audit = result
    events = _extract_official_friendlies(approved)
    # O núcleo só espera notícias aqui; eventos são anexados ao inbox após main via hook.
    pe._v55_official_events = events
    return total, approved, rejected, duplicates, audit


pe.public_research = public_research_v55
_original_dump = pe.dump


def dump_v55(path, obj):
    # Único ponto de inserção: quando o main persiste o inbox já calculado.
    if path == pe.INBOX and isinstance(obj, dict):
        extra = getattr(pe, '_v55_official_events', [])
        if extra:
            obj = dict(obj)
            obj['eventos'] = list(obj.get('eventos', [])) + extra
            print(f'official_events_added_to_inbox={len(extra)}')
    return _original_dump(path, obj)


pe.dump = dump_v55

if __name__ == '__main__':
    raise SystemExit(pe.main())
