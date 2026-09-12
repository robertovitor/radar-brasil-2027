#!/usr/bin/env python3
"""Camada conservadora de compatibilidade da pesquisa editorial.

- Mantém o núcleo original e as EXATAS duas leituras Airtable do script-base.
- Reaproveita os registros já lidos para reconhecer nomes de campos equivalentes.
- Resolve URLs intermediárias do Google News antes da validação editorial.
- Bloqueia pautas já existentes/publicadas, inclusive por similaridade conservadora.
- Não altera schedule, concorrência, merge, alertas, Instagram ou saúde.
"""
import html
import importlib.util
import json
import re
import unicodedata
import urllib.parse
from pathlib import Path

BASE_SCRIPT = Path(__file__).with_name('pesquisa_editorial.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_base', BASE_SCRIPT)
pe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pe)


def keynorm(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def compatible_first(fields, *names):
    for name in names:
        if fields.get(name) not in (None, ''):
            return fields.get(name)
    normalized = {keynorm(k): v for k, v in fields.items() if v not in (None, '')}
    for name in names:
        k = keynorm(name)
        if k in normalized:
            return normalized[k]
    return ''


pe.first = compatible_first


def value_by_alias(fields, aliases):
    normalized = {keynorm(k): v for k, v in fields.items() if v not in (None, '')}
    for alias in aliases:
        if keynorm(alias) in normalized:
            return normalized[keynorm(alias)]
    return ''


def find_title(fields, kind):
    aliases = (
        ('Título', 'Titulo', 'Título da sugestão', 'Titulo da sugestao', 'Assunto', 'Título da notícia', 'Titulo da noticia', 'Título da notícia sugerida', 'Título do evento', 'Titulo do evento', 'Nome do evento', 'Nome', 'Evento')
        if kind == 'eventos' else
        ('Título', 'Titulo', 'Título da sugestão', 'Titulo da sugestao', 'Assunto', 'Título da notícia', 'Titulo da noticia', 'Título da notícia sugerida', 'Titulo da noticia sugerida', 'Notícia', 'Noticia', 'Nome')
    )
    value = value_by_alias(fields, aliases)
    if value not in (None, ''):
        return str(value).strip()
    for k, v in fields.items():
        nk = keynorm(k)
        if isinstance(v, str) and v.strip() and ('titulo' in nk or 'assunto' in nk or (kind == 'eventos' and ('nome evento' in nk or nk == 'evento'))):
            return v.strip()
    return ''


def find_url(fields):
    aliases = ('Link', 'URL', 'Site', 'Fonte/Link', 'Fonte Link', 'Link da sugestão', 'URL da sugestão', 'Link da notícia', 'Link da noticia', 'URL da notícia', 'URL da noticia', 'Link do evento', 'URL do evento', 'Link da fonte', 'URL da fonte')
    candidates = []
    direct = value_by_alias(fields, aliases)
    if direct not in (None, ''):
        candidates.append(direct)
    for k, v in fields.items():
        nk = keynorm(k)
        if ('link' in nk or 'site' in nk or re.search(r'(^| )url( |$)', nk)) and v not in (None, ''):
            candidates.append(v)
    for value in candidates:
        if isinstance(value, dict):
            value = value.get('url') or value.get('href') or ''
        s = str(value).strip()
        if re.match(r'^https?://', s, flags=re.I):
            return s
    return ''


def parse_date(value, default_today=False):
    s = str(value or '').strip()
    if not s:
        return pe.now().date().isoformat() if default_today else ''
    s10 = s[:10]
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s10):
        return s10
    for pattern in (r'^(\d{2})/(\d{2})/(20\d{2})$', r'^(\d{2})-(\d{2})-(20\d{2})$'):
        m = re.match(pattern, s10)
        if m:
            return f'{m.group(3)}-{m.group(2)}-{m.group(1)}'
    return ''


def candidate_from_record_compat(record, kind):
    f = record.get('fields', {})
    title = find_title(f, kind)
    link = find_url(f)
    if not title or not link:
        return None
    if kind == 'noticias':
        date = parse_date(value_by_alias(f, ('Data', 'Data da notícia', 'Data da noticia', 'Data de publicação', 'Data de publicacao')), default_today=True)
        return {'Data': date, 'DataBR': pe.datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y'), 'Titulo': title, 'Tema': str(pe.first(f, 'Tema', 'Categoria')).strip() or 'Copa Feminina 2027', 'CidadeUF': str(pe.first(f, 'Cidade/UF', 'CidadeUF', 'Cidade', 'Local')).strip() or 'Brasil', 'Veiculo': str(pe.first(f, 'Veículo', 'Veiculo', 'Fonte')).strip() or urllib.parse.urlparse(link).netloc, 'Link': link, 'Sentimento': 'Neutro', 'Impacto': str(pe.first(f, 'Impacto')).strip() or 'Médio', 'Resumo': str(pe.first(f, 'Resumo', 'Descrição', 'Descricao', 'Observações', 'Observacoes')).strip()[:1200]}
    date = parse_date(value_by_alias(f, ('Data', 'Data do evento', 'Data do Evento')))
    if not date:
        return None
    city = str(pe.first(f, 'Cidade')).strip(); uf = str(pe.first(f, 'UF', 'Estado')).strip()
    return {'ID': str(pe.first(f, 'ID')).strip() or f"SUG-{record.get('id', '')}", 'Titulo': title, 'Status': 'Planejado', 'Data': date, 'DataBR': pe.datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y'), 'UF': uf, 'Cidade': city, 'Categoria': str(pe.first(f, 'Categoria')).strip() or 'Evento', 'Organizador': str(pe.first(f, 'Organizador')).strip(), 'Publico': 0, 'Patrocinador': str(pe.first(f, 'Patrocinador')).strip(), 'Local': str(pe.first(f, 'Local')).strip(), 'Latitude': None, 'Longitude': None, 'Link': link, 'Observacoes': str(pe.first(f, 'Observações', 'Observacoes', 'Resumo', 'Descrição', 'Descricao')).strip()[:1200], 'Mes': '', 'Ano': int(date[:4]), 'Regiao': ''}


pe.candidate_from_record = candidate_from_record_compat
_original_rss_candidates = pe.rss_candidates
_original_gdelt_candidates = pe.gdelt_candidates
_original_existing_keys = pe.existing_keys


def _external_http_url(candidate):
    candidate = html.unescape(str(candidate or '')).replace('\\u0026', '&').replace('\\/', '/').strip()
    if candidate.startswith('//'):
        candidate = 'https:' + candidate
    if not candidate.startswith(('http://', 'https://')):
        return ''
    parsed = urllib.parse.urlparse(candidate)
    host = parsed.netloc.casefold().removeprefix('www.')
    if host in ('news.google.com', 'google.com') or host.endswith('.google.com'):
        # Alguns links do Google carregam a URL editorial em um parâmetro.
        qs = urllib.parse.parse_qs(parsed.query)
        for key in ('url', 'q', 'u'):
            for value in qs.get(key, []):
                decoded = urllib.parse.unquote(value)
                direct = _external_http_url(decoded)
                if direct:
                    return direct
        return ''
    return candidate


def resolve_google_news(url):
    """Resolve o agregador sem aceitar o próprio Google como fonte editorial.

    Estratégia em camadas: redirect HTTP, canonical/og:url e links externos
    presentes no HTML. Não faz nenhuma leitura Airtable adicional.
    """
    try:
        data, final_url, _ = pe.request_bytes(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/1.3)'}, timeout=15)
        direct = _external_http_url(final_url)
        if direct:
            return direct
        raw = data[:700000].decode('utf-8', 'ignore')
        raw_unescaped = html.unescape(raw).replace('\\u0026', '&').replace('\\/', '/')
        patterns = (
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',
            r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
            r'href=["\'](https?://[^"\']+)',
            r'"(https?://[^"<> ]+)"',
        )
        for text in (raw, raw_unescaped):
            for pattern in patterns:
                for match in re.finditer(pattern, text, flags=re.I):
                    direct = _external_http_url(match.group(1))
                    if direct and pe.trusted_url(direct):
                        return direct
        print('google_news_resolve_unresolved=1')
    except Exception as exc:
        print(f'google_news_resolve_warning={type(exc).__name__}:{exc}')
    return ''


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def existing_keys_compat():
    keys = _original_existing_keys()
    ledger = load_json(pe.ROOT / 'instagram' / 'publicados.json', {})
    for row in ledger.get('published', []):
        key = str(row.get('key') or '')
        if key.startswith('instagram:noticia:http'):
            keys.add('u:' + pe.urlnorm(key[len('instagram:noticia:'):]))
    return keys


pe.existing_keys = existing_keys_compat

STOPWORDS = {'a','o','as','os','de','da','do','das','dos','e','em','no','na','nos','nas','para','por','com','um','uma','que','ao','à','brasil','2027','copa','mundo','feminina','feminino','fifa'}


def title_tokens(title):
    return {x for x in keynorm(title).split() if len(x) >= 4 and x not in STOPWORDS}


def known_titles():
    titles = []
    for path in (pe.ROOT / 'noticias.json', pe.INBOX):
        obj = load_json(path, [] if path.name != 'inbox.json' else {'noticias': []})
        rows = obj if isinstance(obj, list) else obj.get('noticias', [])
        for row in rows:
            if isinstance(row, dict) and row.get('Titulo'):
                titles.append(str(row['Titulo']))
    return titles


def same_story(title, prior):
    a, b = title_tokens(title), title_tokens(prior)
    if not a or not b:
        return False
    overlap = len(a & b); containment = overlap / min(len(a), len(b)); union = overlap / len(a | b)
    return overlap >= 3 and (containment >= 0.72 or union >= 0.60)


def filter_known_stories(candidates):
    priors = known_titles(); out = []
    for c in candidates:
        title = str(c.get('title') or '')
        matched = next((p for p in priors if same_story(title, p)), None)
        if matched:
            print(f"semantic_duplicate_skipped={title} | existing={matched}")
            continue
        out.append(c)
    return out


def rss_candidates_compat():
    out = []
    for candidate in _original_rss_candidates():
        c = dict(candidate)
        if c.get('origin') == 'google-news':
            direct = resolve_google_news(c.get('url', ''))
            if direct:
                c['google_news_url'] = c.get('url', '')
                c['url'] = direct
                c['origin'] = 'google-news-resolved'
                print(f"google_news_resolved={c.get('source','')}|{direct}")
        out.append(c)
    return filter_known_stories(out)


def gdelt_candidates_compat():
    return filter_known_stories(_original_gdelt_candidates())


pe.rss_candidates = rss_candidates_compat
pe.gdelt_candidates = gdelt_candidates_compat

if __name__ == '__main__':
    raise SystemExit(pe.main())
