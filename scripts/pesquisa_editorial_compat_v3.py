#!/usr/bin/env python3
"""Camada conservadora v3 da pesquisa editorial.

Fecha brechas sem aumentar leituras do Airtable:
- sugestões de notícias já lidas passam pela comparação semântica conservadora;
- sugestões de eventos podem usar Data informada/Cidade informada como aliases;
- datas brasileiras textuais/ranges simples são normalizadas antes do parser legado;
- títulos genéricos de páginas de proteção não viram eventos;
- candidatos públicos resolvidos também passam por deduplicação semântica final;
- resumos públicos priorizam conteúdo editorial e descartam menus/scripts/publicidade.

Não altera schedules e não muda merge, alertas, Instagram ou saúde operacional.
"""
import importlib.util
import re
from pathlib import Path

V2_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v2.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v2', V2_SCRIPT)
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
pe = v2.pe

_original_candidate_from_record = pe.candidate_from_record
_original_title_from_url = v2._title_from_url
_original_rss_candidates = pe.rss_candidates

GENERIC_PROTECTION_TITLES = (
    'verificacao de seguranca',
    'security check',
    'just a moment',
    'attention required',
    'access denied',
    'checking your browser',
    'checking if the site connection is secure',
    'are you a robot',
    'robot or human',
)

MONTHS_PT = {
    'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'abril': 4,
    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12,
}

BOILERPLATE_MARKERS = (
    'ir para o conteúdo', 'ir para a página inicial', 'menu de navegação',
    'abrir menu principal', 'assine', 'publicidade', 'newsletter',
    'acesse sua conta', 'cadastre-se grátis', 'termos mais buscados',
    'seu navegador não pode executar javascript', 'script =',
    'googlesyndication', 'doubleclick', 'carregando...', 'página principal',
)


def _is_generic_protection_title(title):
    norm = v2.compat.keynorm(title)
    return any(marker in norm for marker in GENERIC_PROTECTION_TITLES)


def _safe_title_from_url(url):
    title = _original_title_from_url(url)
    if title and _is_generic_protection_title(title):
        print(f"suggestion_title_blocked_protection={title}")
        return ''
    return title


# candidate_from_record_v2 consulta esta função pelo namespace do módulo v2.
v2._title_from_url = _safe_title_from_url


def _same_story_v3(title, prior):
    """Mantém a regra anterior e fecha duas famílias de duplicatas já observadas."""
    if v2.compat.same_story_v2_original(title, prior):
        return True
    a = v2.compat.keynorm(title)
    b = v2.compat.keynorm(prior)

    volunteer_a = ('voluntar' in a and ('copa' in a or 'mundial' in a) and '2027' in a)
    volunteer_b = ('voluntar' in b and ('copa' in b or 'mundial' in b) and '2027' in b)
    if volunteer_a and volunteer_b:
        return True

    ticket_a = ('ingresso' in a and ('preco' in a or 'valor' in a or 'estudo' in a) and '2027' in a)
    ticket_b = ('ingresso' in b and ('preco' in b or 'valor' in b or 'estudo' in b) and '2027' in b)
    if ticket_a and ticket_b:
        return True

    return False


if not hasattr(v2.compat, 'same_story_v2_original'):
    v2.compat.same_story_v2_original = v2.compat.same_story
v2.compat.same_story = _same_story_v3


def _semantic_prior_title(title):
    if not title:
        return ''
    for prior in v2.compat.known_titles():
        if v2.compat.same_story(str(title), str(prior)):
            return str(prior)
    return ''


def _normalize_event_date(value):
    """Normaliza formatos comuns do formulário sem inventar data."""
    text = v2.compat.scalar_text(value).strip()
    if not text:
        return value
    if re.match(r'^\d{4}-\d{2}-\d{2}', text):
        return text[:10]
    m = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b', text)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    norm = v2.compat.keynorm(text)
    m = re.search(r'\b(\d{1,2})(?:\s+a\s+\d{1,2})?\s+de\s+([a-z]+)\s+de\s+(20\d{2})\b', norm)
    if m and m.group(2) in MONTHS_PT:
        return f"{int(m.group(1)):02d}/{MONTHS_PT[m.group(2)]:02d}/{m.group(3)}"
    return value


def _event_record_with_form_aliases(record):
    fields = dict(record.get('fields', {}) or {})
    normalized = {v2.compat.keynorm(k): k for k in fields}
    canonical_date_keys = {
        v2.compat.keynorm('Data'),
        v2.compat.keynorm('Data do evento'),
        v2.compat.keynorm('Data do Evento'),
    }
    has_canonical_date = any(k in normalized for k in canonical_date_keys)
    if not has_canonical_date:
        for alias in ('Data informada', 'Data do evento informada', 'Data sugerida'):
            source_key = normalized.get(v2.compat.keynorm(alias))
            if source_key and fields.get(source_key) not in (None, ''):
                fields['Data'] = _normalize_event_date(fields[source_key])
                print(f"airtable_event_date_alias_used={record.get('id','')}|field={v2.compat.keynorm(alias)}")
                break
    else:
        for key in ('Data', 'Data do evento', 'Data do Evento'):
            source_key = normalized.get(v2.compat.keynorm(key))
            if source_key and fields.get(source_key) not in (None, ''):
                fields[source_key] = _normalize_event_date(fields[source_key])
                break

    if not fields.get('Cidade'):
        for alias in ('Cidade informada', 'Cidade do evento'):
            source_key = normalized.get(v2.compat.keynorm(alias))
            if source_key and fields.get(source_key) not in (None, ''):
                fields['Cidade'] = fields[source_key]
                break

    if fields == record.get('fields', {}):
        return record
    enriched = dict(record)
    enriched['fields'] = fields
    return enriched


def candidate_from_record_v3(record, kind):
    if kind == 'eventos':
        record = _event_record_with_form_aliases(record)
    candidate = _original_candidate_from_record(record, kind)
    if candidate is None:
        return None
    if _is_generic_protection_title(candidate.get('Titulo', '')):
        print(f"airtable_candidate_blocked_protection={record.get('id','')}")
        return None
    if kind != 'noticias':
        return candidate
    prior = _semantic_prior_title(candidate.get('Titulo'))
    if not prior:
        return candidate
    blocked = dict(candidate)
    blocked['Titulo'] = prior
    print(f"airtable_semantic_duplicate_skipped={candidate.get('Titulo','')} | existing={prior}")
    return blocked


pe.candidate_from_record = candidate_from_record_v3


def _strip_non_editorial_blocks(raw):
    cleaned = raw
    for tag in ('script', 'style', 'noscript', 'svg', 'nav', 'header', 'footer', 'aside', 'form'):
        cleaned = re.sub(fr'<{tag}\b[^>]*>.*?</{tag}>', ' ', cleaned, flags=re.I | re.S)
    return cleaned


def _meta_description(raw):
    for tag in re.findall(r'<meta\b[^>]*>', raw, flags=re.I | re.S):
        attrs = dict((k.casefold(), pe.html.unescape(v)) for k, _, v in re.findall(
            r'([:\w-]+)\s*=\s*(["\'])(.*?)\2', tag, flags=re.I | re.S
        ))
        key = (attrs.get('property') or attrs.get('name') or '').casefold()
        if key in ('og:description', 'twitter:description', 'description'):
            text = pe.clean_html_text(attrs.get('content', ''))
            if len(text) >= 70:
                return text
    return ''


def _is_editorial_text(text):
    compact = re.sub(r'\s+', ' ', str(text or '')).strip()
    low = compact.casefold()
    if len(compact) < 45:
        return False
    if 'http://' in low or 'https://' in low or 'javascript' in low:
        return False
    if any(marker in low for marker in BOILERPLATE_MARKERS):
        return False
    letters = sum(ch.isalpha() for ch in compact)
    return letters >= max(25, int(len(compact) * 0.45))


def _paragraphs_from_html(fragment):
    out = []
    seen = set()
    for part in re.findall(r'<p\b[^>]*>(.*?)</p>', fragment, flags=re.I | re.S):
        text = pe.clean_html_text(_strip_non_editorial_blocks(part))
        text = re.sub(r'\s+', ' ', text).strip()
        key = v2.compat.keynorm(text)
        if _is_editorial_text(text) and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def fetch_article_excerpt_clean(url):
    """Extrai texto editorial sem mudar número de leituras do Airtable.

    Prioridade: parágrafos dentro de article/main, depois meta description,
    depois parágrafos do documento. Nunca usa o texto bruto inteiro da página.
    """
    try:
        data, final_url, headers = pe.request_bytes(url, timeout=20)
        ctype = str(headers.get('Content-Type', '')).casefold()
        if 'text/html' not in ctype and 'application/xhtml' not in ctype:
            return '', final_url
        raw = data[:900000].decode('utf-8', 'ignore')
        stripped = _strip_non_editorial_blocks(raw)

        paragraphs = []
        for tag in ('article', 'main'):
            for block in re.findall(fr'<{tag}\b[^>]*>(.*?)</{tag}>', stripped, flags=re.I | re.S):
                paragraphs.extend(_paragraphs_from_html(block))
        if not paragraphs:
            desc = _meta_description(raw)
            if desc:
                paragraphs.append(desc)
            paragraphs.extend(_paragraphs_from_html(stripped))

        unique = []
        seen = set()
        for p in paragraphs:
            k = v2.compat.keynorm(p)
            if k and k not in seen:
                seen.add(k)
                unique.append(p)
        excerpt = ' '.join(unique)
        return excerpt[:7000], final_url
    except Exception as exc:
        print(f"clean_excerpt_warning={type(exc).__name__}:{exc}")
        return '', url


# Substitui somente a extração de texto da pesquisa pública. Não toca em schedules,
# Airtable, merge, alertas ou Instagram.
pe.fetch_article_excerpt = fetch_article_excerpt_clean


def rss_candidates_v3():
    """Última barreira semântica após toda resolução/fallback do Google News."""
    priors = v2.compat.known_titles()
    out = []
    for candidate in _original_rss_candidates():
        title = str(candidate.get('title') or candidate.get('Titulo') or '')
        matched = next((p for p in priors if v2.compat.same_story(title, p)), None)
        if matched:
            print(f"semantic_duplicate_final_skipped={title} | existing={matched}")
            continue
        out.append(candidate)
    return out


pe.rss_candidates = rss_candidates_v3

if __name__ == '__main__':
    raise SystemExit(pe.main())