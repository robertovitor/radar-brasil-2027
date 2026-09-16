#!/usr/bin/env python3
"""Camada v5.1: correções cirúrgicas sem alterar arquitetura ou leituras Airtable.

- normaliza sugestões já lidas ANTES do parser/validador v5;
- reconhece URLs aninhadas em valores Airtable sem nova leitura;
- só recupera título a partir de URL em domínio confiável;
- mantém a porta editorial v5 (fonte, título, relevância, frescor e dedupe);
- melhora o fallback Google News usando o orçamento de validação já existente;
- inclui O TEMPO na lista explícita de fontes editoriais confiáveis.

Não altera schedules, Airtable, merge, alertas, Instagram ou saúde.
"""
import html
import importlib.util
import re
import urllib.parse
from pathlib import Path

V5_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v5.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v5', V5_SCRIPT)
v5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v5)

v4 = v5.v4
v3 = v5.v3
v2 = v5.v2
pe = v5.pe
compat = v2.compat
_v5_candidate_from_record = v5.candidate_from_record_v5

if 'otempo.com.br' not in pe.TRUSTED_DOMAINS:
    pe.TRUSTED_DOMAINS = tuple(pe.TRUSTED_DOMAINS) + ('otempo.com.br',)


def _urls_nested(value, depth=0):
    """Extrai URLs de strings/listas/objetos Airtable já carregados, sem I/O externo."""
    if depth > 4 or value in (None, ''):
        return []
    if isinstance(value, dict):
        out = []
        # Primeiro chaves semanticamente fortes; depois demais valores para anexos/lookups.
        ordered = []
        for key in ('url', 'href', 'link', 'value'):
            if key in value:
                ordered.append(value.get(key))
        ordered.extend(v for k, v in value.items() if k not in ('url', 'href', 'link', 'value'))
        for item in ordered:
            out.extend(_urls_nested(item, depth + 1))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_urls_nested(item, depth + 1))
        return out
    text = html.unescape(str(value).strip())
    if not text:
        return []
    return [u.rstrip('.,);]') for u in re.findall(r'https?://[^\s<>"\']+', text, flags=re.I)]


def _first_embedded_url(fields):
    """Fallback conservador: aceita somente URL HTTP(S) explícita nos valores já lidos."""
    for value in (fields or {}).values():
        for url in _urls_nested(value):
            if re.match(r'^https?://', url, flags=re.I):
                return url
    return ''


def _named_value(fields, markers):
    """Localiza valor apenas quando o NOME do campo contém marcador conhecido."""
    for key, value in (fields or {}).items():
        nk = compat.keynorm(key)
        if any(marker in nk for marker in markers) and value not in (None, ''):
            return value
    return ''


def _pre_normalize_record(record, kind):
    fields = dict(record.get('fields', {}) or {})
    title = compat.find_title(fields, kind)
    link = compat.find_url(fields) or _first_embedded_url(fields)

    # Fail-closed: título automático somente se a própria URL já for de fonte confiável.
    if link and not title and pe.trusted_url(link):
        title = v2._title_from_url(link)

    if title:
        fields['Título'] = title
    if link:
        fields['Link'] = link

    if kind == 'eventos':
        raw_date = compat.value_by_alias(fields, (
            'Data', 'Data do evento', 'Data do Evento', 'Data informada',
            'Data do evento informada', 'Data sugerida'
        )) or _named_value(fields, ('data evento', 'data informada', 'data sugerida'))
        normalized = v3._normalize_event_date(raw_date)
        parsed = compat.parse_date(normalized)
        if parsed:
            fields['Data'] = parsed
    elif kind == 'noticias':
        raw_date = compat.value_by_alias(fields, (
            'Data', 'Data da notícia', 'Data da noticia',
            'Data de publicação', 'Data de publicacao'
        )) or _named_value(fields, ('data noticia', 'data publicacao'))
        parsed = compat.parse_date(raw_date)
        if parsed:
            fields['Data'] = parsed

    enriched = dict(record)
    enriched['fields'] = fields
    return enriched


def candidate_from_record_v5_1(record, kind):
    if kind not in ('noticias', 'eventos'):
        return _v5_candidate_from_record(record, kind)
    return _v5_candidate_from_record(_pre_normalize_record(record, kind), kind)


pe.candidate_from_record = candidate_from_record_v5_1


def _search_editorial_url_v5_1(title, source):
    """Usa melhor as duas validações por pauta sem aumentar buscas externas."""
    if v2._fallback_searches >= v2.MAX_FALLBACK_SEARCHES:
        return ''
    domain = v2._source_domain(source)
    if not domain or not pe.trusted_url('https://' + domain + '/'):
        return ''

    v2._fallback_searches += 1
    editorial_title = v2._strip_source_suffix(title)
    query = f'site:{domain} {v2._search_terms(editorial_title)}'
    validations = 0

    duck_url = 'https://html.duckduckgo.com/html/?' + urllib.parse.urlencode({'q': query})
    try:
        data, _, _ = pe.request_bytes(
            duck_url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/1.8)'},
            timeout=12,
        )
        raw = data[:500000].decode('utf-8', 'ignore')
        for href, _label in v2._result_candidates(raw, domain):
            if validations >= v2.MAX_VALIDATIONS_PER_SEARCH:
                break
            validations += 1
            if v2._validate_editorial_candidate(href, editorial_title, domain):
                print(f'google_news_search_resolved=duckduckgo-v5.1|{domain}|{href}')
                return href
    except Exception as exc:
        print(f'google_news_search_warning=duckduckgo-v5.1|{type(exc).__name__}:{exc}')

    if validations < v2.MAX_VALIDATIONS_PER_SEARCH:
        rss_url = 'https://www.bing.com/news/search?' + urllib.parse.urlencode({
            'q': query, 'format': 'rss', 'setlang': 'pt-BR'
        })
        try:
            data, _, _ = pe.request_bytes(
                rss_url,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/1.8)'},
                timeout=12,
            )
            raw = data[:500000].decode('utf-8', 'ignore')
            for href in v2._rss_result_candidates(raw, domain):
                if validations >= v2.MAX_VALIDATIONS_PER_SEARCH:
                    break
                validations += 1
                if v2._validate_editorial_candidate(href, editorial_title, domain):
                    print(f'google_news_search_resolved=bing-rss-v5.1|{domain}|{href}')
                    return href
        except Exception as exc:
            print(f'google_news_search_warning=bing-rss-v5.1|{type(exc).__name__}:{exc}')

    print(f'google_news_search_unresolved_v5.1={domain}|validations={validations}')
    return ''


v2._search_editorial_url = _search_editorial_url_v5_1

if __name__ == '__main__':
    raise SystemExit(pe.main())
