#!/usr/bin/env python3
"""Camada v5.2: corrige dois gargalos observados na auditoria de 2026-09-16.

1) Sugestões Airtable: usa o registro já normalizado pela v5.1 para construir o
   candidato diretamente com o parser compatível, antes da porta editorial v5.
   Isso evita voltar ao encadeamento legado que ainda podia descartar título/URL
   recuperados. Não faz nenhuma leitura Airtable adicional.
2) Google News: entende redirects Bing modernos (parâmetro u=a1<base64>) e usa
   duas consultas conservadoras (título exato e termos) mantendo os mesmos tetos
   globais de busca/validação. A URL só é aceita após validação da página editorial.

Não altera schedules, merge, alertas, Instagram, saúde ou limites Airtable.
"""
import base64
import html
import importlib.util
import re
import urllib.parse
from pathlib import Path

V51_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v5_1.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v5_1', V51_SCRIPT)
v51 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v51)

v5 = v51.v5
v3 = v51.v3
v2 = v51.v2
pe = v51.pe
compat = v51.compat


def candidate_from_record_v5_2(record, kind):
    if kind not in ('noticias', 'eventos'):
        return v51._v5_candidate_from_record(record, kind)

    enriched = v51._pre_normalize_record(record, kind)
    # Ponto central da correção: não volta ao wrapper v5/legado. O parser compatível
    # recebe os campos canônicos que a v5.1 acabou de recuperar do MESMO payload.
    candidate = compat.candidate_from_record_compat(enriched, kind)
    if candidate is None:
        return None
    return v5._validate_suggestion(enriched, kind, candidate)


pe.candidate_from_record = candidate_from_record_v5_2


def _decode_bing_u(value):
    """Decodifica somente o formato público u=a1<base64url> usado em redirects Bing."""
    value = html.unescape(urllib.parse.unquote(str(value or ''))).strip()
    if not value.startswith('a1'):
        return ''
    payload = value[2:]
    try:
        payload += '=' * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode('ascii')).decode('utf-8', 'strict')
    except Exception:
        return ''
    return decoded if decoded.startswith(('http://', 'https://')) else ''


_original_candidate_from_search_href = v2._candidate_from_search_href


def _candidate_from_search_href_v5_2(href):
    href = html.unescape(str(href or '')).strip()
    if href.startswith('//'):
        href = 'https:' + href
    parsed = urllib.parse.urlparse(href)
    host = parsed.netloc.casefold().removeprefix('www.')
    if host.endswith('bing.com'):
        qs = urllib.parse.parse_qs(parsed.query)
        for raw in qs.get('u', []):
            direct = _decode_bing_u(raw)
            if direct:
                return direct
    return _original_candidate_from_search_href(href)


v2._candidate_from_search_href = _candidate_from_search_href_v5_2


def _search_editorial_url_v5_2(title, source):
    """Busca limitada e fail-closed da URL editorial de uma pauta Google News."""
    if v2._fallback_searches >= v2.MAX_FALLBACK_SEARCHES:
        return ''
    domain = v2._source_domain(source)
    if not domain or not pe.trusted_url('https://' + domain + '/'):
        return ''

    v2._fallback_searches += 1
    editorial_title = v2._strip_source_suffix(title)
    terms = v2._search_terms(editorial_title)
    # Duas consultas no máximo, como na v5.1. A primeira preserva mais sinal do título;
    # a segunda tolera pequenas diferenças editoriais. Validação total continua <=2.
    queries = [f'site:{domain} "{editorial_title}"', f'site:{domain} {terms}']
    validations = 0
    seen = set()

    def inspect(raw, engine):
        nonlocal validations
        for href, _label in v2._result_candidates(raw, domain):
            if validations >= v2.MAX_VALIDATIONS_PER_SEARCH:
                break
            key = compat.pe.urlnorm(href)
            if not key or key in seen:
                continue
            seen.add(key)
            validations += 1
            if v2._validate_editorial_candidate(href, editorial_title, domain):
                print(f'google_news_search_resolved={engine}-v5.2|{domain}|{href}')
                return href
        return ''

    # Uma consulta por mecanismo; não aumenta o número de requests de busca da v5.1.
    endpoints = (
        ('duckduckgo', 'https://html.duckduckgo.com/html/?', {'q': queries[0]}),
        ('bing-html', 'https://www.bing.com/search?', {'q': queries[1], 'setlang': 'pt-BR', 'cc': 'br'}),
    )
    for engine, base, params in endpoints:
        if validations >= v2.MAX_VALIDATIONS_PER_SEARCH:
            break
        try:
            data, _, _ = pe.request_bytes(
                base + urllib.parse.urlencode(params),
                headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/2.1)'},
                timeout=12,
            )
            resolved = inspect(data[:600000].decode('utf-8', 'ignore'), engine)
            if resolved:
                return resolved
        except Exception as exc:
            print(f'google_news_search_warning={engine}-v5.2|{type(exc).__name__}:{exc}')

    print(f'google_news_search_unresolved_v5.2={domain}|validations={validations}')
    return ''


v2._search_editorial_url = _search_editorial_url_v5_2

if __name__ == '__main__':
    raise SystemExit(pe.main())
