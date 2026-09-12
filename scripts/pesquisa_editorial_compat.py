#!/usr/bin/env python3
"""Camada conservadora de compatibilidade da pesquisa editorial.

- Mantém o núcleo original e as EXATAS duas leituras Airtable do script-base.
- Reaproveita os registros já lidos para reconhecer nomes/formatos de campos equivalentes.
- Resolve URLs intermediárias do Google News apenas quando chegam a fonte editorial confiável.
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


def scalar_text(value):
    """Extrai texto sem fazer nenhuma consulta externa.

    Airtable pode entregar valores como string, lista ou objeto (ex.: campos derivados,
    lookup e rich values). Mantemos a extração conservadora e determinística.
    """
    if value in (None, ''):
        return ''
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        for item in value:
            text = scalar_text(item)
            if text:
                return text
        return ''
    if isinstance(value, dict):
        for key in ('url', 'href', 'title', 'titulo', 'name', 'nome', 'text', 'label', 'value'):
            if key in value:
                text = scalar_text(value.get(key))
                if text:
                    return text
        return ''
    return str(value).strip()


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
        ('Título', 'Titulo', 'Título da sugestão', 'Titulo da sugestao', 'Assunto',
         'Título da notícia', 'Titulo da noticia', 'Título da notícia sugerida',
         'Notícia sugerida', 'Noticia sugerida', 'Título do evento', 'Titulo do evento',
         'Evento sugerido', 'Nome do evento', 'Nome', 'Evento')
        if kind == 'eventos' else
        ('Título', 'Titulo', 'Título da sugestão', 'Titulo da sugestao', 'Assunto',
         'Título da notícia', 'Titulo da noticia', 'Título da notícia sugerida',
         'Titulo da noticia sugerida', 'Notícia sugerida', 'Noticia sugerida',
         'Notícia', 'Noticia', 'Nome')
    )
    value = scalar_text(value_by_alias(fields, aliases))
    if value:
        return value

    # Fallback somente em campos cujo NOME indica claramente conteúdo/título.
    markers = ('titulo', 'assunto', 'manchete', 'headline')
    if kind == 'eventos':
        markers += ('nome evento', 'evento sugerido')
    else:
        markers += ('noticia sugerida',)
    for k, v in fields.items():
        nk = keynorm(k)
        if any(marker in nk for marker in markers):
            text = scalar_text(v)
            if text and not re.match(r'^https?://', text, flags=re.I):
                return text
    return ''


def _urls_from_value(value):
    urls = []
    if value in (None, ''):
        return urls
    if isinstance(value, dict):
        for key in ('url', 'href', 'link', 'value'):
            if key in value:
                urls.extend(_urls_from_value(value.get(key)))
        return urls
    if isinstance(value, (list, tuple)):
        for item in value:
            urls.extend(_urls_from_value(item))
        return urls
    text = scalar_text(value)
    if not text:
        return urls
    if re.match(r'^https?://', text, flags=re.I):
        urls.append(text)
    else:
        urls.extend(re.findall(r'https?://[^\s<>"\']+', text, flags=re.I))
    return urls


def find_url(fields):
    aliases = ('Link', 'URL', 'Site', 'Fonte/Link', 'Fonte Link', 'Link da sugestão',
               'URL da sugestão', 'Link da notícia', 'Link da noticia', 'URL da notícia',
               'URL da noticia', 'Link do evento', 'URL do evento', 'Link da fonte',
               'URL da fonte', 'Endereço', 'Endereco')
    candidates = []
    direct = value_by_alias(fields, aliases)
    candidates.extend(_urls_from_value(direct))
    for k, v in fields.items():
        nk = keynorm(k)
        if ('link' in nk or 'site' in nk or 'endereco' in nk or re.search(r'(^| )url( |$)', nk)):
            candidates.extend(_urls_from_value(v))
    for value in candidates:
        s = html.unescape(str(value).strip()).rstrip('.,);]')
        if re.match(r'^https?://', s, flags=re.I):
            return s
    return ''


def parse_date(value, default_today=False):
    s = scalar_text(value)
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
        # Diagnóstico sem conteúdo/PII e sem nova leitura: registra somente nomes de campos.
        safe_keys = ','.join(sorted(keynorm(k) for k in f.keys()))
        print(f"airtable_unmapped_record={record.get('id','')}|kind={kind}|title={bool(title)}|url={bool(link)}|field_keys={safe_keys}")
        return None
    if kind == 'noticias':
        date = parse_date(value_by_alias(f, ('Data', 'Data da notícia', 'Data da noticia', 'Data de publicação', 'Data de publicacao')), default_today=True)
        return {
            'Data': date,
            'DataBR': pe.datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y'),
            'Titulo': title,
            'Tema': scalar_text(pe.first(f, 'Tema', 'Categoria')) or 'Copa Feminina 2027',
            'CidadeUF': scalar_text(pe.first(f, 'Cidade/UF', 'CidadeUF', 'Cidade', 'Local')) or 'Brasil',
            'Veiculo': scalar_text(pe.first(f, 'Veículo', 'Veiculo', 'Fonte')) or urllib.parse.urlparse(link).netloc,
            'Link': link,
            'Sentimento': 'Neutro',
            'Impacto': scalar_text(pe.first(f, 'Impacto')) or 'Médio',
            'Resumo': scalar_text(pe.first(f, 'Resumo', 'Descrição', 'Descricao', 'Observações', 'Observacoes'))[:1200],
        }
    date = parse_date(value_by_alias(f, ('Data', 'Data do evento', 'Data do Evento')))
    if not date:
        print(f"airtable_event_without_valid_date={record.get('id','')}")
        return None
    city = scalar_text(pe.first(f, 'Cidade'))
    uf = scalar_text(pe.first(f, 'UF', 'Estado'))
    return {
        'ID': scalar_text(pe.first(f, 'ID')) or f"SUG-{record.get('id', '')}",
        'Titulo': title, 'Status': 'Planejado', 'Data': date,
        'DataBR': pe.datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y'),
        'UF': uf, 'Cidade': city,
        'Categoria': scalar_text(pe.first(f, 'Categoria')) or 'Evento',
        'Organizador': scalar_text(pe.first(f, 'Organizador')), 'Publico': 0,
        'Patrocinador': scalar_text(pe.first(f, 'Patrocinador')),
        'Local': scalar_text(pe.first(f, 'Local')), 'Latitude': None, 'Longitude': None,
        'Link': link,
        'Observacoes': scalar_text(pe.first(f, 'Observações', 'Observacoes', 'Resumo', 'Descrição', 'Descricao'))[:1200],
        'Mes': '', 'Ano': int(date[:4]), 'Regiao': ''
    }


pe.candidate_from_record = candidate_from_record_compat
_original_rss_candidates = pe.rss_candidates
_original_gdelt_candidates = pe.gdelt_candidates
_original_existing_keys = pe.existing_keys


def _decode_embedded_url(value):
    value = html.unescape(str(value or '')).replace('\\u0026', '&').replace('\\u003d', '=').replace('\\/', '/').strip()
    # Duas passagens cobrem percent-encoding simples e duplo sem transformar dados arbitrários.
    for _ in range(2):
        decoded = urllib.parse.unquote(value)
        if decoded == value:
            break
        value = decoded
    return value


def _external_http_url(candidate):
    candidate = _decode_embedded_url(candidate)
    if candidate.startswith('//'):
        candidate = 'https:' + candidate
    if not candidate.startswith(('http://', 'https://')):
        return ''
    parsed = urllib.parse.urlparse(candidate)
    host = parsed.netloc.casefold().removeprefix('www.')
    if host in ('news.google.com', 'google.com') or host.endswith('.google.com'):
        # Links Google podem carregar a URL editorial em parâmetros conhecidos.
        qs = urllib.parse.parse_qs(parsed.query)
        for key in ('url', 'q', 'u', 'target', 'dest', 'destination'):
            for value in qs.get(key, []):
                direct = _external_http_url(value)
                if direct:
                    return direct
        return ''
    return candidate


def resolve_google_news(url):
    """Resolve agregador sem aceitar o Google como fonte editorial.

    Só devolve URL final quando ela pertence à lista já existente de fontes confiáveis.
    Falha fechada: se não resolver, o item segue para rejeição normal do script-base.
    """
    try:
        data, final_url, _ = pe.request_bytes(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RadarBrasil2027/1.4)'},
            timeout=15,
        )
        direct = _external_http_url(final_url)
        if direct and pe.trusted_url(direct):
            return direct

        raw = data[:900000].decode('utf-8', 'ignore')
        variants = [raw, html.unescape(raw), _decode_embedded_url(raw)]
        patterns = (
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',
            r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
            r'[?&](?:url|q|u|target|dest|destination)=([^&"\'<> ]+)',
            r'href=["\'](https?://[^"\']+)',
            r'"(https?://[^"<> ]+)"',
        )
        for text in variants:
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
    overlap = len(a & b)
    containment = overlap / min(len(a), len(b))
    union = overlap / len(a | b)
    return overlap >= 3 and (containment >= 0.72 or union >= 0.60)


def filter_known_stories(candidates):
    priors = known_titles()
    out = []
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
