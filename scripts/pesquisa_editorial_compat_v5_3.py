#!/usr/bin/env python3
"""Camada v5.3: corrige causas observadas sem ampliar leituras Airtable.

- Sugestões: reaproveita o MESMO payload Airtable, reconhece campos por semântica do
  nome, aceita URLs aninhadas e amplia somente o orçamento de recuperação de título
  da própria página sugerida. Continua passando pela porta editorial v5.
- Google News/CBF: para pautas cuja fonte é CBF, tenta primeiro a listagem oficial da
  Seleção Feminina e valida a página oficial encontrada. Google News permanece apenas
  como descoberta; buscadores continuam fallback.

Não altera schedule, Merge, Alertas, Instagram, Saúde ou as 2 leituras Airtable.
"""
import html
import importlib.util
import re
import urllib.parse
from pathlib import Path

V52_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v5_2.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v5_2', V52_SCRIPT)
v52 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v52)

v51 = v52.v51
v5 = v52.v5
v3 = v52.v3
v2 = v52.v2
pe = v52.pe
compat = v52.compat

# A causa dos falsos negativos de sugestões link-only era o teto global de 6 títulos
# para até 46 registros. Isto NÃO lê Airtable: apenas permite validar mais URLs já lidas.
v2.MAX_MISSING_TITLE_FETCHES = 24


def _semantic_value(fields, markers):
    for key, value in (fields or {}).items():
        nk = compat.keynorm(key)
        if any(marker in nk for marker in markers) and value not in (None, ''):
            return value
    return ''


def _normalize_record_v53(record, kind):
    enriched = v51._pre_normalize_record(record, kind)
    fields = dict(enriched.get('fields', {}) or {})

    # URL: último fallback somente sobre valores do payload já recebido.
    link = compat.find_url(fields) or v51._first_embedded_url(fields)
    if link:
        fields['Link'] = link

    # Título: campos de formulário podem ser frases/perguntas em vez de aliases fixos.
    title = compat.find_title(fields, kind)
    if not title:
        raw = _semantic_value(fields, ('titulo', 'manchete', 'assunto', 'nome evento', 'noticia sugerida', 'evento sugerido'))
        text = compat.scalar_text(raw)
        if text and not re.match(r'^https?://', text, flags=re.I):
            title = text
    if not title and link and pe.trusted_url(link):
        title = v2._title_from_url(link)
    if title:
        fields['Título'] = title

    # Data de evento: procura apenas campos cujo nome indique inequivocamente data/quando.
    if kind == 'eventos' and not compat.parse_date(compat.value_by_alias(fields, ('Data', 'Data do evento', 'Data do Evento'))):
        raw_date = _semantic_value(fields, ('data', 'quando', 'dia evento', 'dia do evento'))
        normalized = v3._normalize_event_date(raw_date)
        parsed = compat.parse_date(normalized)
        if parsed:
            fields['Data'] = parsed

    enriched = dict(enriched)
    enriched['fields'] = fields
    return enriched


def candidate_from_record_v53(record, kind):
    if kind not in ('noticias', 'eventos'):
        return v51._v5_candidate_from_record(record, kind)
    enriched = _normalize_record_v53(record, kind)
    candidate = compat.candidate_from_record_compat(enriched, kind)
    if candidate is None:
        return None
    return v5._validate_suggestion(enriched, kind, candidate)


pe.candidate_from_record = candidate_from_record_v53

# Fonte primária: cache por execução, uma única leitura pública da listagem oficial.
_cbf_listing_candidates = None
_CBF_LISTING = 'https://www.cbf.com.br/selecao-brasileira/noticias/selecao-feminina'


def _load_cbf_listing():
    global _cbf_listing_candidates
    if _cbf_listing_candidates is not None:
        return _cbf_listing_candidates
    _cbf_listing_candidates = []
    try:
        data, final_url, headers = pe.request_bytes(
            _CBF_LISTING,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/2.3)'},
            timeout=15,
        )
        if not pe.trusted_url(final_url):
            return _cbf_listing_candidates
        raw = data[:900000].decode('utf-8', 'ignore')
        seen = set()
        for href, label in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw, flags=re.I | re.S):
            href = html.unescape(href).strip()
            if href.startswith('/'):
                href = urllib.parse.urljoin(final_url, href)
            if not v2._same_domain(href, 'cbf.com.br') or '/noticias/' not in href:
                continue
            key = pe.urlnorm(href)
            if not key or key in seen:
                continue
            seen.add(key)
            clean_label = v2._clean_page_title(label)
            _cbf_listing_candidates.append((href, clean_label))
        print(f'primary_cbf_listing_candidates={len(_cbf_listing_candidates)}')
    except Exception as exc:
        print(f'primary_cbf_listing_warning={type(exc).__name__}:{exc}')
    return _cbf_listing_candidates


def _resolve_cbf_primary(title):
    expected = v2._strip_source_suffix(title)
    # Primeiro usa o texto do link para não gastar validação em links sem relação.
    ranked = []
    for href, label in _load_cbf_listing():
        score = 1 if label and v2._similar_title(expected, label) else 0
        if not score:
            slug = urllib.parse.urlparse(href).path.rsplit('/', 1)[-1].replace('-', ' ')
            score = 1 if v2._similar_title(expected, slug) else 0
        if score:
            ranked.append(href)
    for href in ranked[:2]:
        if v2._validate_editorial_candidate(href, expected, 'cbf.com.br'):
            print(f'google_news_primary_resolved=cbf-v5.3|{href}')
            return href
    return ''


_original_search_editorial_url = v52._search_editorial_url_v5_2


def _search_editorial_url_v53(title, source):
    domain = v2._source_domain(source)
    if domain == 'cbf.com.br':
        direct = _resolve_cbf_primary(title)
        if direct:
            return direct
    return _original_search_editorial_url(title, source)


v2._search_editorial_url = _search_editorial_url_v53

if __name__ == '__main__':
    raise SystemExit(pe.main())
