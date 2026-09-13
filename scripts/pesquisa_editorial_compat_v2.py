#!/usr/bin/env python3
"""Fallback conservador para resolver URLs do Google News.

Esta camada NÃO altera schedule, concorrência, Airtable, merge, Instagram ou alertas.
Ela reaproveita pesquisa_editorial_compat.py e acrescenta apenas:
- uma busca editorial limitada quando o resolvedor nativo do Google News não encontra a URL direta;
- extração conservadora do título quando uma sugestão de notícia ou evento já lida do Airtable tem URL válida, mas título vazio.
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
_original_candidate_from_record = compat.candidate_from_record_compat

# Limites rígidos: evitam explosão de chamadas e qualquer efeito cascata.
MAX_FALLBACK_SEARCHES = 8
MAX_MISSING_TITLE_FETCHES = 6
# Distribui as validações entre resultados do Google News: antes, o primeiro
# resultado podia consumir sozinho todo o orçamento global e bloquear os demais.
MAX_FALLBACK_VALIDATIONS = 12
MAX_VALIDATIONS_PER_SEARCH = 2
_fallback_searches = 0
_missing_title_fetches = 0
_fallback_validations = 0

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
    'o globo': 'oglobo.globo.com',
    'estadao': 'estadao.com.br',
    'estadão': 'estadao.com.br',
    'folha de s paulo': 'folha.uol.com.br',
    'folha': 'folha.uol.com.br',
    'lance': 'lance.com.br',
    'a tarde': 'atarde.com.br',
    'prefeitura de fortaleza': 'fortaleza.ce.gov.br',
    'prefeitura de porto alegre': 'prefeitura.poa.br',
    'prefeitura poa br': 'prefeitura.poa.br',
}


def _clean_page_title(value):
    value = re.sub(r'<[^>]+>', ' ', html.unescape(str(value or '')))
    value = re.sub(r'\s+', ' ', value).strip()
    return value[:300]


def _title_from_url(url):
    """Extrai somente o título editorial da própria URL sugerida.

    Não consulta Airtable, não altera o registro e não aprova a pauta; apenas permite
    que a validação editorial existente prossiga quando o formulário recebeu só o link.
    """
    global _missing_title_fetches
    if _missing_title_fetches >= MAX_MISSING_TITLE_FETCHES:
        return ''
    if not re.match(r'^https?://', str(url or ''), flags=re.I):
        return ''
    _missing_title_fetches += 1
    try:
        data, _, _ = pe.request_bytes(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/1.5)'},
            timeout=12,
        )
        raw = data[:500000].decode('utf-8', 'ignore')
        patterns = (
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:title["\']',
            r'<title[^>]*>(.*?)</title>',
        )
        for pattern in patterns:
            match = re.search(pattern, raw, flags=re.I | re.S)
            if match:
                title = _clean_page_title(match.group(1))
                if len(title) >= 8:
                    print(f'suggestion_title_resolved={urllib.parse.urlparse(url).netloc}|{title}')
                    return title
    except Exception as exc:
        print(f'suggestion_title_warning={type(exc).__name__}:{exc}')
    return ''


def candidate_from_record_v2(record, kind):
    """Preserva o parser atual e só trata sugestão com link válido + título vazio."""
    candidate = _original_candidate_from_record(record, kind)
    if candidate is not None:
        return candidate
    if kind not in ('noticias', 'eventos'):
        return None

    fields = record.get('fields', {})
    link = compat.find_url(fields)
    title = compat.find_title(fields, kind)
    if not link or title:
        return None

    resolved_title = _title_from_url(link)
    if not resolved_title:
        return None

    # Não modifica o registro original vindo do Airtable.
    enriched_record = dict(record)
    enriched_fields = dict(fields)
    enriched_fields['Título'] = resolved_title
    enriched_record['fields'] = enriched_fields
    # Todas as demais regras permanecem no parser original; para eventos, por exemplo,
    # a data continua obrigatória e precisa ser válida.
    return _original_candidate_from_record(enriched_record, kind)


# O núcleo passa a usar o fallback apenas no registro já lido; nenhuma leitura Airtable extra.
pe.candidate_from_record = candidate_from_record_v2


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


def _same_domain(url, domain):
    host = urllib.parse.urlparse(str(url or '')).netloc.casefold().removeprefix('www.')
    return bool(host and domain and (host == domain or host.endswith('.' + domain) or domain.endswith('.' + host)))


def _search_terms(title):
    words = [w for w in re.findall(r'[\wÀ-ÿ-]+', _strip_source_suffix(title)) if len(w) >= 4]
    stop = {'copa','mundo','feminina','feminino','2027','brasil','fifa','para','com','uma','das','dos','de','do','da','em','no','na'}
    useful = [w for w in words if compat.keynorm(w) not in stop]
    return ' '.join(useful[:8]) or _strip_source_suffix(title)


def _result_candidates(raw, domain):
    """Extrai candidatos sem confiar no layout exato do buscador."""
    seen = set()
    patterns = (
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r'(https?://[^\s"\'<>]+)',
    )
    for pattern in patterns:
        for m in re.finditer(pattern, raw, flags=re.I | re.S):
            href = _candidate_from_duck_href(m.group(1))
            if not _same_domain(href, domain) or not pe.trusted_url(href):
                continue
            key = compat.pe.urlnorm(href)
            if not key or key in seen:
                continue
            seen.add(key)
            label = ''
            if m.lastindex and m.lastindex >= 2:
                label = _clean_page_title(m.group(2))
            yield href, label


def _validate_editorial_candidate(url, expected_title, domain):
    """Valida domínio + título da própria página antes de aceitar a URL."""
    global _fallback_validations
    if _fallback_validations >= MAX_FALLBACK_VALIDATIONS:
        return False
    if not _same_domain(url, domain) or not pe.trusted_url(url):
        return False
    _fallback_validations += 1
    try:
        data, final_url, headers = pe.request_bytes(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/1.6)'},
            timeout=12,
        )
        if not _same_domain(final_url, domain) or not pe.trusted_url(final_url):
            return False
        ctype = str(headers.get('Content-Type', '')).casefold()
        if 'html' not in ctype:
            return False
        raw = data[:500000].decode('utf-8', 'ignore')
        page_title = ''
        for pattern in (
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            r'<title[^>]*>(.*?)</title>',
        ):
            m = re.search(pattern, raw, flags=re.I | re.S)
            if m:
                page_title = _clean_page_title(m.group(1))
                if page_title:
                    break
        return bool(page_title and _similar_title(expected_title, page_title))
    except Exception as exc:
        print(f'google_news_validation_warning={type(exc).__name__}:{exc}')
        return False


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
    # Evita a consulta excessivamente rígida com o título inteiro entre aspas.
    query = f'site:{domain} {_search_terms(editorial_title)}'
    url = 'https://html.duckduckgo.com/html/?' + urllib.parse.urlencode({'q': query})
    try:
        data, _, _ = pe.request_bytes(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/1.6)'},
            timeout=12,
        )
        raw = data[:500000].decode('utf-8', 'ignore')
        validations_this_search = 0
        for href, label in _result_candidates(raw, domain):
            # O label do buscador é apenas um filtro rápido; a confirmação final vem da própria página.
            if label and not _similar_title(editorial_title, label):
                continue
            if validations_this_search >= MAX_VALIDATIONS_PER_SEARCH:
                break
            validations_this_search += 1
            if _validate_editorial_candidate(href, editorial_title, domain):
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
