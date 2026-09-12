#!/usr/bin/env python3
"""Camada conservadora de compatibilidade da pesquisa editorial.

- Mantém o núcleo original e as EXATAS duas leituras Airtable do script-base.
- Reaproveita os registros já lidos para reconhecer nomes de campos equivalentes.
- Tenta resolver URLs intermediárias do Google News antes da validação editorial.
- Não altera schedule, concorrência, merge, alertas, Instagram ou saúde.
"""
import html
import importlib.util
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


# first() continua sem qualquer chamada externa: trabalha apenas no dict de fields já obtido.
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
        ('Título', 'Titulo', 'Título da notícia', 'Titulo da noticia', 'Título da notícia sugerida',
         'Título do evento', 'Titulo do evento', 'Nome do evento', 'Nome', 'Evento')
        if kind == 'eventos' else
        ('Título', 'Titulo', 'Título da notícia', 'Titulo da noticia', 'Título da notícia sugerida',
         'Titulo da noticia sugerida', 'Notícia', 'Noticia', 'Nome')
    )
    value = value_by_alias(fields, aliases)
    if value not in (None, ''):
        return str(value).strip()
    for k, v in fields.items():
        nk = keynorm(k)
        if isinstance(v, str) and v.strip() and ('titulo' in nk or (kind == 'eventos' and 'nome' in nk and 'evento' in nk)):
            return v.strip()
    return ''


def find_url(fields):
    aliases = ('Link', 'URL', 'Link da notícia', 'Link da noticia', 'URL da notícia', 'URL da noticia',
               'Link do evento', 'URL do evento', 'Link da fonte', 'URL da fonte')
    candidates = []
    direct = value_by_alias(fields, aliases)
    if direct not in (None, ''):
        candidates.append(direct)
    for k, v in fields.items():
        nk = keynorm(k)
        if ('link' in nk or re.search(r'(^| )url( |$)', nk)) and v not in (None, ''):
            candidates.append(v)
    for value in candidates:
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
        return {
            'Data': date,
            'DataBR': pe.datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y'),
            'Titulo': title,
            'Tema': str(pe.first(f, 'Tema', 'Categoria')).strip() or 'Copa Feminina 2027',
            'CidadeUF': str(pe.first(f, 'Cidade/UF', 'CidadeUF', 'Cidade', 'Local')).strip() or 'Brasil',
            'Veiculo': str(pe.first(f, 'Veículo', 'Veiculo', 'Fonte')).strip() or urllib.parse.urlparse(link).netloc,
            'Link': link,
            'Sentimento': 'Neutro',
            'Impacto': str(pe.first(f, 'Impacto')).strip() or 'Médio',
            'Resumo': str(pe.first(f, 'Resumo', 'Descrição', 'Descricao', 'Observações', 'Observacoes')).strip()[:1200],
        }
    date = parse_date(value_by_alias(f, ('Data', 'Data do evento', 'Data do Evento')))
    if not date:
        return None
    city = str(pe.first(f, 'Cidade')).strip()
    uf = str(pe.first(f, 'UF', 'Estado')).strip()
    return {
        'ID': str(pe.first(f, 'ID')).strip() or f"SUG-{record.get('id', '')}",
        'Titulo': title, 'Status': 'Planejado', 'Data': date,
        'DataBR': pe.datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y'),
        'UF': uf, 'Cidade': city,
        'Categoria': str(pe.first(f, 'Categoria')).strip() or 'Evento',
        'Organizador': str(pe.first(f, 'Organizador')).strip(), 'Publico': 0,
        'Patrocinador': str(pe.first(f, 'Patrocinador')).strip(),
        'Local': str(pe.first(f, 'Local')).strip(), 'Latitude': None, 'Longitude': None,
        'Link': link,
        'Observacoes': str(pe.first(f, 'Observações', 'Observacoes', 'Resumo', 'Descrição', 'Descricao')).strip()[:1200],
        'Mes': '', 'Ano': int(date[:4]), 'Regiao': ''
    }


pe.candidate_from_record = candidate_from_record_compat
_original_rss_candidates = pe.rss_candidates


def resolve_google_news(url):
    try:
        data, final_url, _ = pe.request_bytes(url, timeout=12)
        final_host = urllib.parse.urlparse(final_url).netloc.casefold().removeprefix('www.')
        if final_url.startswith(('http://', 'https://')) and final_host not in ('news.google.com', 'google.com'):
            return final_url
        raw = data[:400000].decode('utf-8', 'ignore')
        patterns = (
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
            r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
        )
        for pattern in patterns:
            m = re.search(pattern, raw, flags=re.I)
            if not m:
                continue
            candidate = html.unescape(m.group(1)).strip()
            host = urllib.parse.urlparse(candidate).netloc.casefold().removeprefix('www.')
            if candidate.startswith(('http://', 'https://')) and host not in ('news.google.com', 'google.com'):
                return candidate
    except Exception as exc:
        print(f'google_news_resolve_warning={type(exc).__name__}:{exc}')
    return ''


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
        out.append(c)
    return out


pe.rss_candidates = rss_candidates_compat

if __name__ == '__main__':
    raise SystemExit(pe.main())
