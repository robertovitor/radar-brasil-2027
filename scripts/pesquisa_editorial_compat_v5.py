#!/usr/bin/env python3
"""Camada conservadora v5: sugestões Airtable passam pela mesma porta editorial.

Objetivos:
- manter exatamente as 2 leituras Airtable existentes;
- reaproveitar normalização/aliases/fallbacks da v4;
- impedir que sugestão humana tenha via de aprovação mais frouxa que pesquisa pública;
- exigir fonte confiável, página editorial acessível, correspondência de título,
  relevância, frescor verificável para notícias e deduplicação já existente;
- para eventos, aceitar formatos de data normalizáveis, mas nunca data inválida.

Não altera schedules, merge, alertas, Instagram, saúde ou escrita no Airtable.
"""
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

V4_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v4.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v4', V4_SCRIPT)
v4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v4)

v3 = v4.v3
v2 = v3.v2
pe = v3.pe
_original_candidate_from_record = pe.candidate_from_record

NEWS_MAX_AGE_DAYS = 30


def _meta(raw, names):
    for tag in re.findall(r'<meta\b[^>]*>', raw, flags=re.I | re.S):
        attrs = dict((k.casefold(), pe.html.unescape(v)) for k, _, v in re.findall(
            r'([:\w-]+)\s*=\s*(["\'])(.*?)\2', tag, flags=re.I | re.S))
        key = (attrs.get('property') or attrs.get('name') or attrs.get('itemprop') or '').casefold()
        if key in names and attrs.get('content'):
            return attrs['content'].strip()
    return ''


def _page_title(raw):
    title = _meta(raw, {'og:title', 'twitter:title', 'headline'})
    if title:
        return v2._clean_page_title(title)
    m = re.search(r'<title[^>]*>(.*?)</title>', raw, flags=re.I | re.S)
    return v2._clean_page_title(m.group(1)) if m else ''


def _page_date(raw):
    value = _meta(raw, {
        'article:published_time', 'datepublished', 'date', 'pubdate',
        'publishdate', 'publish_date', 'parsely-pub-date'
    })
    candidates = [value] if value else []
    # JSON-LD é somente fallback de data; não confiamos nele para título/domínio.
    candidates += re.findall(r'["\']datePublished["\']\s*:\s*["\']([^"\']+)', raw, flags=re.I)
    for candidate in candidates:
        m = re.search(r'(20\d{2})-(\d{2})-(\d{2})', str(candidate))
        if not m:
            continue
        try:
            return datetime.strptime('-'.join(m.groups()), '%Y-%m-%d').date()
        except ValueError:
            pass
    return None


def _explicit_record_date(record, kind):
    fields = record.get('fields', {}) or {}
    aliases = (
        ('Data', 'Data da notícia', 'Data da noticia', 'Data de publicação', 'Data de publicacao')
        if kind == 'noticias' else
        ('Data', 'Data do evento', 'Data do Evento', 'Data informada', 'Data do evento informada', 'Data sugerida')
    )
    value = v2.compat.value_by_alias(fields, aliases)
    if kind == 'eventos':
        value = v3._normalize_event_date(value)
    parsed = v2.compat.parse_date(value)
    if not parsed:
        return None
    try:
        return datetime.strptime(parsed, '%Y-%m-%d').date()
    except ValueError:
        return None


def _known_duplicate(candidate):
    link = str(candidate.get('Link') or '')
    title = str(candidate.get('Titulo') or '')
    keys = pe.existing_keys()
    if ('u:' + pe.urlnorm(link)) in keys or ('t:' + pe.norm(title)) in keys:
        return True
    return bool(v3._semantic_prior_title(title))


def _validate_suggestion(record, kind, candidate):
    title = str(candidate.get('Titulo') or '').strip()
    link = str(candidate.get('Link') or '').strip()
    rid = record.get('id', '')

    if not title or not link:
        print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=missing_title_or_url')
        return None
    if not pe.trusted_url(link):
        print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=untrusted_domain')
        return None
    if _known_duplicate(candidate):
        print(f'suggestion_v5_duplicate={rid}|kind={kind}')
        return None

    try:
        data, final_url, headers = pe.request_bytes(
            link,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/2.0)'},
            timeout=15,
        )
    except Exception as exc:
        print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=source_unreachable|error={type(exc).__name__}')
        return None

    if not pe.trusted_url(final_url):
        print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=redirect_untrusted')
        return None
    ctype = str(headers.get('Content-Type', '')).casefold()
    if 'html' not in ctype:
        print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=non_html_source')
        return None

    raw = data[:900000].decode('utf-8', 'ignore')
    editorial_title = _page_title(raw)
    if not editorial_title or v3._is_generic_protection_title(editorial_title):
        print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=editorial_title_unverifiable')
        return None
    if not v2._similar_title(title, editorial_title):
        print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=title_mismatch')
        return None

    excerpt = pe.clean_html_text(v3._strip_non_editorial_blocks(raw))[:7000]
    if not excerpt or not pe.article_is_relevant(editorial_title, excerpt):
        print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=irrelevant')
        return None

    if kind == 'noticias':
        published = _page_date(raw) or _explicit_record_date(record, kind)
        if published is None:
            print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=freshness_unverifiable')
            return None
        age = (pe.now().date() - published).days
        if age < -1 or age > NEWS_MAX_AGE_DAYS:
            print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=stale|age_days={age}')
            return None
        candidate = dict(candidate)
        candidate['Data'] = published.isoformat()
        candidate['DataBR'] = published.strftime('%d/%m/%Y')
        candidate['Titulo'] = editorial_title
        candidate['Link'] = final_url
    else:
        event_date = _explicit_record_date(record, kind)
        if event_date is None:
            print(f'suggestion_v5_rejected={rid}|kind={kind}|reason=invalid_event_date')
            return None
        candidate = dict(candidate)
        candidate['Data'] = event_date.isoformat()
        candidate['DataBR'] = event_date.strftime('%d/%m/%Y')
        candidate['Ano'] = event_date.year
        candidate['Titulo'] = editorial_title
        candidate['Link'] = final_url

    # Dedup novamente com os valores canônicos obtidos da própria fonte.
    if _known_duplicate(candidate):
        print(f'suggestion_v5_duplicate={rid}|kind={kind}|phase=canonical')
        return None

    print(f'suggestion_v5_approved={rid}|kind={kind}|domain_title_relevance_freshness_dedup=ok')
    return candidate


def candidate_from_record_v5(record, kind):
    candidate = _original_candidate_from_record(record, kind)
    if candidate is None:
        return None
    if kind not in ('noticias', 'eventos'):
        return candidate
    return _validate_suggestion(record, kind, candidate)


pe.candidate_from_record = candidate_from_record_v5

if __name__ == '__main__':
    raise SystemExit(pe.main())
