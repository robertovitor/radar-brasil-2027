#!/usr/bin/env python3
"""Fallback conservador para resolver URLs do Google News.

Esta camada NÃO altera schedule, concorrência, Airtable, merge, Instagram ou alertas.
Ela reaproveita pesquisa_editorial_compat.py e apenas acrescenta uma busca editorial
limitada quando o resolvedor nativo do Google News não encontra a URL direta.
"""
import html
import importlib.util
import re
import urllib.parse
from pathlib import Path

COMPAT_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat', COMPAT_SCRIPT)
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)
pe = compat.pe

_original_resolve_google_news = compat.resolve_google_news

# Limite rígido: evita explosão de chamadas e qualquer efeito cascata.
MAX_FALLBACK_SEARCHES = 8
_fallback_searches = 0

SOURCE_DOMAIN_HINTS = {
    'gov br': 'gov.br',
    'ge': 'ge.globo.com',
    'cbf': 'cbf.com.br',
    'agencia brasil': 'agenciabrasil.ebc.com.br',
    'agência brasil': 'agenciabrasil.ebc.com.br',
    'exame': 'exame.com',
    'terra': 'terra.com.br',
    'cnn brasil': 'cnnbrasil.com.br',
    'espn brasil': 'espn.com.br',
    'uol': 'uol.com.br',
    'prefeitura de fortaleza': 'fortaleza.ce.gov.br',
    'prefeitura poa br': 'prefeitura.poa.br',
}


def _source_domain(source):
    s = str(source or '').strip().casefold().removeprefix('www.')
    # Quando o próprio RSS já informa um domínio, use-o diretamente.
    if re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}', s):
        return s
    key = compat.keynorm(s)
    return SOURCE_DOMAIN_HINTS.get(key, '')


def _strip_source_suffix(title):
    title = str(title or '').strip()
    # O Google News costuma anexar " - Veículo" ao título.
    return re.sub(r'\s+-\s+[^-]{2,80}$', '', title).strip()


def _tokens(value):
    stop = {'copa','mundo','feminina','feminino','2027','brasil','fifa','para','com','uma','das','dos','de','do','da','em','no','na'}
    return {x for x in compat.keynorm(value).split() if len(x) >= 4 and x not in stop}


def _similar_title(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    overlap = len(ta & tb)
    return overlap >= 3 and overlap / min(len(ta), len(tb)) >= 0.60


def _candidate_from_duck_href(href):
    href = html.unescape(str(href or '')).strip()
    if href.startswith('//'):
        href = 'https:' + href
    parsed = urllib.parse.urlparse(href)
    host = parsed.netloc.casefold().removeprefix('www.')
    if host.endswith('duckduckgo.com'):
        qs = urllib.parse.parse_qs(parsed.query)
        vals = qs.get('uddg', [])
        if vals:
            return urllib.parse.unquote(vals[0])
    return href


def _search_editorial_url(title, source):
    global _fallback_searches
    if _fallback_searches >= MAX_FALLBACK_SEARCHES:
        return ''
    domain = _source_domain(source)
    if not domain:
        return ''
    # Mantém a mesma política de confiança já existente no Radar.
    probe = 'https://' + domain + '/'
    if not pe.trusted_url(probe):
        return ''

    _fallback_searches += 1
    editorial_title = _strip_source_suffix(title)
    query = f'site:{domain} "{editorial_title}"'
    url = 'https://html.duckduckgo.com/html/?' + urllib.parse.urlencode({'q': query})
    try:
        data, _, _ = pe.request_bytes(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/1.4)'},
            timeout=12,
        )
        raw = data[:500000].decode('utf-8', 'ignore')
        # Resultado padrão do HTML do DuckDuckGo.
        for m in re.finditer(r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw, flags=re.I|re.S):
            href = _candidate_from_duck_href(m.group(1))
            label = re.sub(r'<[^>]+>', ' ', html.unescape(m.group(2)))
            parsed = urllib.parse.urlparse(href)
            host = parsed.netloc.casefold().removeprefix('www.')
            same_domain = host == domain or host.endswith('.' + domain) or domain.endswith('.' + host)
            if same_domain and _similar_title(editorial_title, label) and pe.trusted_url(href):
                print(f'google_news_search_resolved={domain}|{href}')
                return href
    except Exception as exc:
        print(f'google_news_search_warning={type(exc).__name__}:{exc}')
    return ''


def resolve_google_news_v2(url, title='', source=''):
    direct = _original_resolve_google_news(url)
    if direct:
        return direct
    return _search_editorial_url(title, source)


def rss_candidates_v2():
    out = []
    for candidate in compat._original_rss_candidates():
        c = dict(candidate)
        if c.get('origin') == 'google-news':
            direct = resolve_google_news_v2(c.get('url', ''), c.get('title', ''), c.get('source', ''))
            if direct:
                c['google_news_url'] = c.get('url', '')
                c['url'] = direct
                c['origin'] = 'google-news-resolved'
                print(f"google_news_resolved_v2={c.get('source','')}|{direct}")
        out.append(c)
    return compat.filter_known_stories(out)


pe.rss_candidates = rss_candidates_v2
# GDELT e todas as demais rotinas permanecem exatamente as mesmas da camada compatível.
pe.gdelt_candidates = compat.gdelt_candidates_compat

if __name__ == '__main__':
    raise SystemExit(pe.main())
