#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import re
import unicodedata
import urllib.parse

CATALOG = pathlib.Path('banco_imagens/catalogo.json')
LEDGER = pathlib.Path('instagram/publicados.json')

BLOCK = re.compile(r'\b(?:presidente|presidência|presidencia|governo|governador|governadora|prefeito|prefeita|ministro|ministra|senador|senadora|deputado|deputada|palácio do planalto|palacio do planalto|lula|bolsonaro|pol[ií]tica|elei[cç][aã]o|partido|congresso|assembleia legislativa)\b', re.I)
AMERICAN = re.compile(r'\b(?:nfl|ncaa|american football|gridiron|touchdown|quarterback|super bowl|badgers|ole miss|georgia tech)\b', re.I)
MEN = re.compile(r"(?:\bmen\b|men['’]?s|\bmale\b|masculin)", re.I)
WOMEN = re.compile(r"(?:women|woman|female|feminina|feminino|jogadora|jogadoras|femenina)", re.I)
SOCCER = re.compile(r"(?:football|soccer|futebol|copa|world cup|sele[cç][aã]o|team|jogadora)", re.I)

CATEGORY_HINTS = {
    'selecao_brasileira': ('brasil','brazil','seleção','selecao','marta','formiga','debinha','cristiane','kerolin','adriana','tamires','zaneratto','ary borges','rafaelle','ludmila','geyse','angelina','yasmim','tarciane','lorena','portilho'),
    'futebol_feminino_brasil': ('brasil','brazil','brasileirão','brasileirao','corinthians','palmeiras','ferroviária','ferroviaria','santos','são paulo','sao paulo','flamengo','fluminense','internacional','grêmio','gremio','cruzeiro','bahia','bragantino','botafogo','vasco'),
    'copas_femininas': ('world cup','copa do mundo','2023','2019','2015','2011','2007','2003','1999','1995','1991'),
    'futebol_feminino_internacional': ('women','female','feminina','femenina','football','soccer'),
    'estadios_sedes_2027': ('mineirão','mineirao','mané garrincha','mane garrincha','castelão','castelao','beira-rio','beira rio','arena de pernambuco','maracanã','maracana','fonte nova','neo química','neo quimica','arena corinthians'),
    'cidades_sedes_2027': ('belo horizonte','brasília','brasilia','fortaleza','porto alegre','recife','rio de janeiro','salvador','são paulo','sao paulo'),
    'torcida_futebol_feminino': ('fans','supporters','torcida','crowd','cheering'),
}

def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii','ignore').decode('ascii').lower()
    return re.sub(r'\s+',' ',s).strip()

def identity(url):
    try:
        p = urllib.parse.urlsplit(str(url or ''))
        path = urllib.parse.unquote(p.path)
        if '/wiki/' in path:
            return 'commons:' + path.split('/wiki/',1)[1].replace('_',' ').casefold()
        if '/thumb/' in path:
            return 'commons-file:' + path.rsplit('/',2)[-2].casefold()
        return (p.netloc + ':' + path.rsplit('/',1)[-1]).casefold()
    except Exception:
        return ''

def used_identities():
    used = set()
    if not LEDGER.exists():
        return used
    try:
        data = json.loads(LEDGER.read_text(encoding='utf-8'))
    except Exception:
        return used
    for row in data.get('published', [])[-60:]:
        if not isinstance(row, dict):
            continue
        post_file = pathlib.Path(str(row.get('post_file') or ''))
        if not post_file.exists():
            continue
        try:
            post = json.loads(post_file.read_text(encoding='utf-8'))
        except Exception:
            continue
        for field in ('image_source_url','image_page_url','source_page_url','image_url'):
            ident = identity(post.get(field))
            if ident:
                used.add(ident)
    return used

def editorial_allowed(row):
    if str(row.get('instagram_ok','')).upper() != 'SIM':
        return False
    if not str(row.get('status_licenca','')).upper().startswith('APROVADA'):
        return False
    lic = str(row.get('licenca') or '').lower()
    if not any(x in lic for x in ('cc0','public domain','domínio público','dominio publico','cc by','cc-by','pdm')):
        return False
    text = ' '.join(str(row.get(k) or '') for k in ('titulo','pessoa_local','atribuicao','observacoes'))
    if BLOCK.search(text) or AMERICAN.search(text) or MEN.search(text):
        return False
    cat = str(row.get('categoria') or '')
    if cat in ('selecao_brasileira','futebol_feminino_brasil','copas_femininas','futebol_feminino_internacional','torcida_futebol_feminino'):
        if not SOCCER.search(text):
            return False
    if cat == 'torcida_futebol_feminino' and not WOMEN.search(text):
        return False
    return bool(row.get('url_direta') or row.get('pagina_origem'))

def infer_categories(item_text):
    n = norm(item_text)
    scores = []
    for cat, hints in CATEGORY_HINTS.items():
        score = sum(1 for h in hints if norm(h) in n)
        if score:
            scores.append((score, cat))
    scores.sort(reverse=True)
    return [cat for _,cat in scores] or ['selecao_brasileira','futebol_feminino_brasil','copas_femininas','estadios_sedes_2027','cidades_sedes_2027']

def select(item, used=None):
    if not CATALOG.exists():
        return None
    try:
        rows = json.loads(CATALOG.read_text(encoding='utf-8'))
    except Exception:
        return None
    used = set(used or ()) | used_identities()
    item_text = ' '.join(str(item.get(k) or '') for k in ('title','search_context','visual_places'))
    item_tokens = set(re.findall(r'[a-z0-9]{3,}', norm(item_text)))
    preferred = infer_categories(item_text)
    ranked = []
    for row in rows:
        if not isinstance(row, dict) or not editorial_allowed(row):
            continue
        src = str(row.get('url_direta') or '')
        page = str(row.get('pagina_origem') or '')
        ids = {identity(src), identity(page)} - {''}
        if ids & used:
            continue
        row_text = ' '.join(str(row.get(k) or '') for k in ('titulo','pessoa_local','categoria'))
        row_tokens = set(re.findall(r'[a-z0-9]{3,}', norm(row_text)))
        overlap = len(item_tokens & row_tokens)
        cat = str(row.get('categoria') or '')
        cat_bonus = max(0, 18 - preferred.index(cat)*4) if cat in preferred else 0
        female_bonus = 5 if WOMEN.search(row_text) else 0
        score = overlap * 7 + cat_bonus + female_bonus
        ranked.append((score, overlap, row))
    if not ranked:
        return None
    ranked.sort(key=lambda x: (x[0], x[1], str(x[2].get('qtd_utilizacoes') or '0')), reverse=True)
    score, overlap, row = ranked[0]
    if score < 8:
        return None
    return {
        'image_source_url': row.get('url_direta') or row.get('url_thumbnail') or '',
        'source_page_url': row.get('pagina_origem') or '',
        'credito': row.get('atribuicao') or row.get('autor') or '',
        'licenca': row.get('licenca') or '',
        'reutilizacao_permitida': True,
        'auto_found': True,
        'provider': 'banco_aprovado',
        'query': 'catalogo_local',
        'semantic_reason': f"bank:{row.get('categoria')}:{row.get('id')} score={score}",
        'bank_image_id': row.get('id') or '',
        'bank_category': row.get('categoria') or '',
    }

if __name__ == '__main__':
    print('Este módulo é usado pelo preparador do Instagram.')
