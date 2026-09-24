#!/usr/bin/env python3
"""Pesquisa conservadora de oportunidades para o Radar Brasil 2027.

- Não consulta Airtable.
- Não altera Notícias, Eventos, Alertas, Instagram ou Saúde.
- Usa fontes oficiais/plataformas de inscrição confiáveis e busca web apenas como descoberta.
- Mantém itens já conhecidos quando uma fonte falha, evitando sumiços por erro transitório.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import ssl
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CONTEXT = ssl.create_default_context()

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "oportunidades.json"
STATUS_PATH = ROOT / "editorial" / "oportunidades-status.json"

USER_AGENT = "RadarBrasil2027/1.0 (+https://radarfutebolfeminino2027.com.br/)"
TIMEOUT = 12
MAX_SEARCH_RESULTS_PER_QUERY = 6
MAX_PAGES_PER_RUN = 40

TRUSTED_DOMAINS = (
    "fifa.com",
    "inside.fifa.com",
    "jobs.fifa.com",
    "cbf.com.br",
    "cbfacademy.com.br",
    "plataforma.cbfacademy.com.br",
    "sympla.com.br",
    "eventbrite.com.br",
    "womanifs.com",
    "gov.br",
    "prefeitura.sp.gov.br",
    "fortaleza.ce.gov.br",
    "prefeitura.pbh.gov.br",
    "recife.pe.gov.br",
    "salvador.ba.gov.br",
    "portoalegre.rs.gov.br",
    "rio.rj.gov.br",
    "df.gov.br",
    "fferj.com.br",
    "fpf.org.br",
    "cob.org.br",
    "ifce.edu.br",
)

SEED_URLS = (
    "https://inside.fifa.com/tournament-organisation/volunteers/media-releases/volunteer-applications-open-womens-world-cup-brazil-2027",
    "https://jobs.fifa.com/postings/2f370bff-10b8-4622-9bd7-3a02d5222aec",
    "https://jobs.fifa.com/postings/25e65e4b-c419-469a-870c-4e52dce3bc46",
    "https://cbfacademy.com.br/summit-cbf-academy-2026/",
    "https://plataforma.cbfacademy.com.br/pt-br/cursos/182-nutricao-no-futebol",
)

PINPOINT_FEEDS = (
    "https://jobs.fifa.com/postings.json",
)

HUB_URLS = (
    "https://jobs.fifa.com/",
    "https://plataforma.cbfacademy.com.br/pt-br/calendario",
    "https://plataforma.cbfacademy.com.br/pt-br/noticias/244-futebol-feminino-brasileiro",
    "https://www.gov.br/esporte/pt-br/acoes-e-programas-1/acoes-e-programas",
    "https://www.gov.br/esporte/pt-br/noticias",
    "https://fortaleza.ce.gov.br/noticias/categoria/esporte-e-lazer",
    "https://jogasp.prefeitura.sp.gov.br/",
    "https://prefeitura.sp.gov.br/web/esportes",
    "https://prefeitura.pbh.gov.br/esportes",
    "https://womanifs.com/",
)

SEARCH_QUERIES = (
    '"Copa do Mundo Feminina 2027" voluntariado inscrição Brasil',
    '"Copa do Mundo Feminina 2027" vaga trabalho contratação Brasil',
    '"Copa do Mundo Feminina 2027" curso capacitação inscrições Brasil',
    '"futebol feminino" curso inscrições Brasil 2026 2027',
    '"futebol feminino" summit congresso workshop inscrições Brasil 2026 2027',
    'site:sympla.com.br "futebol feminino" curso OR workshop OR congresso OR summit',
    'site:eventbrite.com.br "futebol feminino" curso OR workshop OR congresso',
    'site:womanifs.com inscrição OR registration',
    'site:gov.br/esporte "futebol feminino" inscrição OR curso OR capacitação OR edital',
    'site:prefeitura.sp.gov.br "futebol feminino" inscrição OR curso OR voluntariado',
    'site:fortaleza.ce.gov.br "futebol feminino" inscrição OR curso OR voluntariado',
    'site:prefeitura.pbh.gov.br "futebol feminino" inscrição OR curso OR voluntariado',
    'site:recife.pe.gov.br "futebol feminino" inscrição OR curso OR voluntariado',
    'site:salvador.ba.gov.br "futebol feminino" inscrição OR curso OR voluntariado',
    'site:portoalegre.rs.gov.br "futebol feminino" inscrição OR curso OR voluntariado',
    'site:df.gov.br "futebol feminino" inscrição OR curso OR voluntariado',
    'site:fferj.com.br "futebol feminino" inscrição OR curso OR workshop',
    'site:fpf.org.br "futebol feminino" inscrição OR curso OR workshop',
)

HOST_CITIES = (
    ("Belo Horizonte", "MG"),
    ("Brasília", "DF"),
    ("Fortaleza", "CE"),
    ("Porto Alegre", "RS"),
    ("Recife", "PE"),
    ("Rio de Janeiro", "RJ"),
    ("Salvador", "BA"),
    ("São Paulo", "SP"),
)

MONTHS = {
    "janeiro": 1, "jan": 1, "january": 1,
    "fevereiro": 2, "fev": 2, "february": 2, "feb": 2,
    "março": 3, "marco": 3, "mar": 3, "march": 3,
    "abril": 4, "abr": 4, "april": 4, "apr": 4,
    "maio": 5, "mai": 5, "may": 5,
    "junho": 6, "jun": 6, "june": 6,
    "julho": 7, "jul": 7, "july": 7,
    "agosto": 8, "ago": 8, "august": 8, "aug": 8,
    "setembro": 9, "set": 9, "september": 9, "sep": 9,
    "outubro": 10, "out": 10, "october": 10, "oct": 10,
    "novembro": 11, "nov": 11, "november": 11,
    "dezembro": 12, "dez": 12, "december": 12, "dec": 12,
}

PARTICIPATION_TERMS = (
    "inscri", "inscreva", "candidat", "apply", "application", "volunt",
    "vaga", "career", "job", "curso", "summit", "congres", "workshop",
    "semin", "forum", "fórum", "mentoria", "capacita", "credenciamento",
)
CORE_TERMS = (
    "copa do mundo feminina", "copa feminina 2027", "mundial feminino 2027",
    "women's world cup 2027", "womens world cup 2027", "fwwc2027",
    "brazil 2027", "brasil 2027",
)
WOMEN_FOOTBALL_TERMS = (
    "futebol feminino", "women's football", "womens football",
    "seleção feminina", "selecao feminina", "women athlete", "mulheres no jogo",
)

def now_br() -> dt.datetime:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=-3)))

def norm(value: str) -> str:
    import unicodedata
    value = str(value or "").replace("’", "'").replace("‘", "'")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value).strip().lower()

def atomic_dump(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def request_text(url: str, timeout: int = TIMEOUT) -> tuple[str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
        raw = resp.read(5_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, "ignore")
        return text, resp.geturl()

def canonical_url(url: str) -> str:
    try:
        p = urllib.parse.urlsplit(html.unescape(url.strip()))
        q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        q = [(k, v) for k, v in q if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "ref", "source"}]
        host = p.netloc.lower()
        path = re.sub(r"/+$", "", p.path) or "/"
        # FIFA Careers publica a mesma vaga com e sem prefixo de idioma.
        # Normalizar evita duplicidade entre /en/postings/<id> e /postings/<id>.
        if host == "jobs.fifa.com":
            path = re.sub(r"^/(?:en|pt|es|fr)/postings/", "/postings/", path, flags=re.I)
        return urllib.parse.urlunsplit((p.scheme.lower() or "https", host, path, urllib.parse.urlencode(q), ""))
    except Exception:
        return url.strip()

def trusted_url(url: str) -> bool:
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except Exception:
        return False
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in TRUSTED_DOMAINS)

def visible_text(raw_html: str) -> str:
    s = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>|<noscript\b.*?</noscript>", " ", raw_html)
    s = re.sub(r"(?is)<br\s*/?>|</p>|</li>|</h\d>|</div>|</section>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()

def page_title(raw_html: str, text: str) -> str:
    for pat in (
        r"(?is)<h1\b[^>]*>(.*?)</h1>",
        r"(?is)<title\b[^>]*>(.*?)</title>",
        r'(?is)<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
    ):
        m = re.search(pat, raw_html)
        if m:
            title = visible_text(m.group(1))
            title = re.sub(r"\s*[|\-–]\s*(FIFA|CBF Academy|Sympla).*$", "", title, flags=re.I).strip()
            if 4 <= len(title) <= 180:
                return title
    return (text.splitlines()[0] if text else "")[:180].strip()

def ddg_search(query: str) -> list[str]:
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    raw, _ = request_text(url, timeout=10)
    out, seen = [], set()
    for m in re.finditer(r'(?is)<a\\b[^>]+href=["\\']([^"\\']+)["\\'][^>]*>', raw):
        href = html.unescape(m.group(1))
        if "uddg=" in href:
            try:
                q = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
                href = q.get("uddg", [href])[0]
            except Exception:
                pass
        href = canonical_url(href)
        if href.startswith("http") and trusted_url(href) and href not in seen:
            seen.add(href)
            out.append(href)
            if len(out) >= MAX_SEARCH_RESULTS_PER_QUERY:
                break
    return out

def bing_rss_search(query: str) -> list[str]:
    """Fallback simples: o RSS do Bing expõe links finais sem JavaScript."""
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "format": "rss"})
    raw, _ = request_text(url, timeout=10)
    out, seen = [], set()
    for item in re.findall(r"(?is)<item>(.*?)</item>", raw):
        m = re.search(r"(?is)<link>(.*?)</link>", item)
        if not m:
            continue
        href = html.unescape(m.group(1).strip())
        href = re.sub(r"^<!\\[CDATA\\[(.*?)\\]\\]>$", r"\\1", href, flags=re.S)
        href = canonical_url(href)
        if href.startswith("http") and trusted_url(href) and href not in seen:
            seen.add(href)
            out.append(href)
            if len(out) >= MAX_SEARCH_RESULTS_PER_QUERY:
                break
    return out

def search_web(query: str) -> tuple[list[str], dict]:
    """Combina motores e registra o que cada um conseguiu descobrir."""
    out, seen = [], set()
    engines = {}
    for name, fn in (("duckduckgo", ddg_search), ("bing_rss", bing_rss_search)):
        try:
            results = fn(query)
            engines[name] = len(results)
            for href in results:
                if href not in seen:
                    seen.add(href)
                    out.append(href)
                    if len(out) >= MAX_SEARCH_RESULTS_PER_QUERY:
                        break
        except Exception as exc:
            engines[name] = f"erro:{type(exc).__name__}"
        if len(out) >= MAX_SEARCH_RESULTS_PER_QUERY:
            break
    return out, engines

def discover_hub_links(url: str) -> list[str]:
    """Descobre links com sinal de inscrição/participação em hubs confiáveis."""
    raw, final_url = request_text(url, timeout=12)
    out, seen = [], set()
    for m in re.finditer(r'(?is)<a\\b[^>]+href=["\\']([^"\\']+)["\\'][^>]*>(.*?)</a>', raw):
        href = urllib.parse.urljoin(final_url, html.unescape(m.group(1)))
        href = canonical_url(href)
        if not trusted_url(href) or href in seen:
            continue
        label = norm(visible_text(m.group(2)))
        path = norm(urllib.parse.urlsplit(href).path or "")
        blob = f"{label} {path}"
        eligible_terms = (
            "inscri", "matricul", "volunt", "curso", "capacit", "formacao",
            "summit", "congres", "workshop", "semin", "forum", "vaga",
            "career", "job", "processo seletivo", "chamamento", "edital",
        )
        if any(term in blob for term in eligible_terms):
            seen.add(href)
            out.append(href)
            if len(out) >= 10:
                break
    return out

def contains_any(blob: str, terms) -> bool:
    b = norm(blob)
    return any(norm(t) in b for t in terms)

def relevance_score(title: str, text: str, url: str) -> int:
    blob = f"{title}\n{text[:120000]}"
    b = norm(blob)
    score = 0
    if contains_any(blob, CORE_TERMS):
        score += 6
    if contains_any(blob, WOMEN_FOOTBALL_TERMS):
        score += 4
    if "jobs.fifa.com" in url and ("2027" in b or "women" in b):
        score += 5
    if ("cbfacademy.com.br" in url or "plataforma.cbfacademy.com.br" in url) and ("futebol" in b or "football" in b):
        score += 2
    if "sympla.com.br" in url and ("futebol feminino" in b or "copa 2027" in b):
        score += 2
    if contains_any(blob, PARTICIPATION_TERMS):
        score += 2
    return score

def classify(title: str, text: str, url: str) -> str:
    b = norm(f"{title} {text[:50000]}")
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()

    # O tipo da oportunidade deve vencer palavras genéricas de CTA/rodapé
    # ("Apply", "Career", "vaga"), que aparecem em páginas de cursos e voluntariado.
    if "jobs.fifa.com" in host and "/postings/" in path:
        return "Trabalho"
    if "volunt" in b or "volunteer" in path:
        return "Voluntariado"
    if "summit" in b or "summit" in path:
        return "Summit"
    if "congres" in b:
        return "Congresso"
    if "workshop" in b or "oficina" in b:
        return "Workshop"
    if "/cursos/" in path or "curso" in b or "capacita" in b or "formacao" in b or "matricula" in b:
        return "Curso"
    if any(x in b for x in (
        "employment type", "tipo de emprego", "job description", "career opportunity",
        "vaga de emprego", "processo seletivo", "contratacao", "recursos humanos",
    )):
        return "Trabalho"
    return "Outros"

def organisation(url: str, text: str) -> str:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    path = urllib.parse.urlsplit(url).path
    if "fifa.com" in host:
        return "FIFA"
    if "cbfacademy.com.br" in host:
        return "CBF Academy"
    if "cbf.com.br" in host:
        return "CBF"
    if "sympla.com.br" in host:
        return "Sympla"
    if "eventbrite" in host:
        return "Eventbrite"
    if "womanifs.com" in host:
        return "Women in Football Summit"
    if host.endswith("gov.br") and "/esporte/" in path:
        return "Ministério do Esporte"
    if "prefeitura.sp.gov.br" in host:
        return "Prefeitura de São Paulo"
    if "fortaleza.ce.gov.br" in host:
        return "Prefeitura de Fortaleza"
    if "prefeitura.pbh.gov.br" in host:
        return "Prefeitura de Belo Horizonte"
    if "recife.pe.gov.br" in host:
        return "Prefeitura do Recife"
    if "salvador.ba.gov.br" in host:
        return "Prefeitura de Salvador"
    if "portoalegre.rs.gov.br" in host:
        return "Prefeitura de Porto Alegre"
    if "rio.rj.gov.br" in host:
        return "Prefeitura do Rio de Janeiro"
    if host.endswith(".df.gov.br") or host == "df.gov.br":
        return "Governo do Distrito Federal"
    if "fferj.com.br" in host:
        return "FERJ"
    if "fpf.org.br" in host:
        return "FPF"
    if "cob.org.br" in host:
        return "COB"
    if "ifce.edu.br" in host:
        return "IFCE"
    return host.replace("www.", "")

def extract_mode(text: str, category: str) -> str:
    b = norm(text[:80000])
    # Programas de voluntariado da Copa são presenciais; menções a "online"
    # em cadastro, treinamento ou rodapé não devem alterar o formato principal.
    if category == "Voluntariado":
        if any(x in b for x in ("remote volunteering", "voluntariado remoto", "100% online")):
            return "Online"
        return "Presencial"
    if "hybrid" in b or "hibrid" in b or "semipresencial" in b:
        return "Híbrido"
    if re.search(r"\bonline\b|\bremoto\b|\bremote\b", b):
        return "Online"
    if "onsite" in b or "presencial" in b:
        return "Presencial"
    if category == "Trabalho":
        return "Presencial"
    return ""

def extract_location(title: str, text: str) -> tuple[str, str, str]:
    blob = norm(f"{title}\n{text[:35000]}")
    found = []
    for city, uf in HOST_CITIES:
        if norm(city) in blob:
            found.append((city, uf))
    if len(found) == 1:
        city, uf = found[0]
        return city, uf, f"{city}/{uf}"
    if len(found) > 1:
        return "", "", "8 cidades-sede" if len(found) >= 6 else "Brasil"
    if re.search(r"\bbrazil\b|\bbrasil\b", blob):
        return "", "", "Brasil"
    return "", "", "Online" if "online" in blob else "Brasil"

def parse_named_date(day: str, month_name: str, year: str | None) -> str:
    month = MONTHS.get(norm(month_name))
    if not month:
        return ""
    y = int(year or now_br().year)
    try:
        return dt.date(y, month, int(day)).isoformat()
    except ValueError:
        return ""

def extract_deadline(text: str) -> str:
    compact = re.sub(r"\s+", " ", text[:120000])
    patterns = (
        r"(?i)(?:application deadline|deadline|prazo(?: de)? inscri[cç][aã]o|inscri[cç][oõ]es? at[eé])\s*[:\-]?\s*(\d{1,2})\s+(?:de\s+)?([A-Za-zÀ-ÿ]+)\s+(?:de\s+)?(20\d{2})",
        r"(?i)(?:application deadline|deadline|prazo(?: de)? inscri[cç][aã]o|inscri[cç][oõ]es? at[eé])\s*[:\-]?\s*([A-Za-zÀ-ÿ]+)\s+(\d{1,2}),?\s+(20\d{2})",
        r"(?i)(?:application deadline|deadline|prazo(?: de)? inscri[cç][aã]o|inscri[cç][oõ]es? at[eé])\s*[:\-]?\s*(20\d{2})-(\d{2})-(\d{2})",
    )
    m = re.search(patterns[0], compact)
    if m:
        return parse_named_date(m.group(1), m.group(2), m.group(3))
    m = re.search(patterns[1], compact)
    if m:
        return parse_named_date(m.group(2), m.group(1), m.group(3))
    m = re.search(patterns[2], compact)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    return ""

def infer_status(text: str, deadline: str) -> str:
    today = now_br().date()
    if deadline:
        try:
            d = dt.date.fromisoformat(deadline)
            if d < today:
                return "Encerrada"
            if (d - today).days <= 7:
                return "Encerra em breve"
        except ValueError:
            pass
    b = norm(text[:120000])
    if any(x in b for x in ("applications are now open", "inscricoes ja estao abertas", "inscricoes abertas", "apply now", "inscreva-se", "me inscrever")):
        return "Inscrições abertas"
    if any(x in b for x in ("avise-me", "abertura dos ingressos", "register your interest", "express your interest")):
        return "Inscrições em breve"
    if any(x in b for x in ("applications closed", "inscricoes encerradas", "encerrado")):
        return "Encerrada"
    return "Inscrições abertas"

def relation_level(title: str, text: str, url: str) -> str:
    score = relevance_score(title, text, url)
    return "Alta" if score >= 8 else "Média"

def looks_portuguese(text: str) -> bool:
    """Heurística conservadora para não publicar resumo bruto em outro idioma."""
    b = f" {norm(text)} "
    markers = (
        " oportunidade ", " inscri", " futebol ", " profissionais ", " curso ",
        " capacita", " voluntari", " particip", " trabalho ", " vaga ", " brasil ",
        " organizacao ", " evento ", " publico ", " atuacao ", " equipe ",
    )
    return sum(1 for marker in markers if marker in b) >= 2

def role_focus_pt(title: str) -> str:
    """Traduz o foco funcional de títulos recorrentes do FIFA Careers."""
    t = norm(title)
    rules = (
        ("accounts payable", "contas a pagar e rotinas financeiras"),
        ("access management systems", "sistemas e aplicações de controle de acesso"),
        ("data protection", "proteção de dados e privacidade"),
        ("digital product", "produtos digitais"),
        ("dressing and signage", "ambientação, identidade visual e sinalização"),
        ("hospitality operations", "operações de hospitalidade e infraestrutura nos locais do torneio"),
        ("host broadcast", "operações de transmissão da emissora anfitriã"),
        ("iptv", "serviços de IPTV e distribuição de TV"),
        ("legal", "coordenação jurídica"),
        ("non-competition venue dressing", "ambientação e sinalização de locais não competitivos"),
        ("recruitment & reporting", "recrutamento, indicadores e relatórios de pessoas"),
        ("recruitment and reporting", "recrutamento, indicadores e relatórios de pessoas"),
        ("business intelligence", "inteligência de negócios e dados"),
        ("stadium safety", "segurança e proteção nos estádios"),
        ("venue safety", "segurança e proteção nos locais do torneio"),
        ("ticketing crm communication", "CRM e canais de comunicação da operação de ingressos"),
        ("ticketing crm qa", "qualidade e testes de aceitação de sistemas de ingressos e CRM"),
        ("commercial partners", "relacionamento com parceiros comerciais e clientes do mercado local na operação de ingressos"),
        ("digital communications", "comunicação digital da operação de ingressos"),
        ("customer care analyst", "atendimento ao público na operação de ingressos"),
        ("customer care coordinator", "coordenação de atendimento ao público na operação de ingressos"),
        ("general public customer care manager", "gestão do atendimento ao público na operação de ingressos"),
        ("group sales", "vendas para grupos na operação de ingressos"),
        ("member associations customer care", "atendimento às associações-membro na operação de ingressos"),
        ("sales & strategy", "vendas e estratégia de ingressos"),
        ("sales and strategy", "vendas e estratégia de ingressos"),
        ("ticketing system", "sistemas da operação de ingressos"),
        ("ticketing training", "treinamento da equipe de ingressos"),
        ("venue technology", "tecnologia nos locais do torneio"),
        ("volunteer operations", "operações do programa de voluntariado"),
        ("warehouse & distribution", "armazenagem e distribuição"),
        ("warehouse and distribution", "armazenagem e distribuição"),
        ("workforce planning", "planejamento e operações de força de trabalho"),
        ("travel", "operações de viagens"),
        ("uniforms", "uniformes e operações de força de trabalho"),
    )
    for key, value in rules:
        if key in t:
            return value
    return ""

def extract_summary(title: str, text: str, category: str, org: str = "") -> str:
    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines()]
    candidates = []
    for line in lines:
        if len(line) < 55 or len(line) > 420:
            continue
        b = norm(line)
        if norm(title) in b:
            continue
        if contains_any(line, CORE_TERMS) or contains_any(line, WOMEN_FOOTBALL_TERMS) or contains_any(line, PARTICIPATION_TERMS):
            candidates.append(line)

    # Texto editorial já em português pode ser reaproveitado.
    for candidate in candidates:
        if looks_portuguese(candidate):
            return candidate[:320]

    focus = role_focus_pt(title)
    org_name = org or "A organização"
    if category == "Trabalho":
        if focus:
            return f"Oportunidade profissional da {org_name} ligada à organização da Copa do Mundo Feminina da FIFA 2027 no Brasil, com atuação em {focus}."
        return f"Oportunidade profissional da {org_name} ligada à organização da Copa do Mundo Feminina da FIFA 2027 no Brasil. Consulte a vaga para responsabilidades e requisitos."
    if category == "Voluntariado":
        if focus:
            return f"Oportunidade da {org_name} ligada à Copa do Mundo Feminina da FIFA 2027 no Brasil, com atuação em {focus}."
        return f"Oportunidade de voluntariado da {org_name} relacionada à Copa do Mundo Feminina da FIFA 2027 e ao futebol feminino."
    if category == "Curso":
        return f"Curso ou capacitação da {org_name}, com inscrição para profissionais e interessados no ecossistema do futebol."
    if category == "Summit":
        return f"Encontro da {org_name} com inscrição para participação, networking e debates sobre o ecossistema do futebol."
    if category == "Congresso":
        return f"Congresso da {org_name} com inscrição para participação e troca de conhecimento sobre o ecossistema do futebol."
    if category == "Workshop":
        return f"Workshop da {org_name} com inscrição para formação prática e desenvolvimento de competências ligadas ao futebol."
    return f"Oportunidade da {org_name} com inscrição para participação no ecossistema do futebol feminino."

def stable_id(url: str, title: str) -> str:
    return "OPP-" + hashlib.sha1((canonical_url(url) + "|" + norm(title)).encode("utf-8")).hexdigest()[:12].upper()

def opportunity_from_url(url: str) -> dict | None:
    if not trusted_url(url):
        return None
    raw, final_url = request_text(url)
    final_url = canonical_url(final_url)
    if not trusted_url(final_url):
        return None
    text = visible_text(raw)
    title = page_title(raw, text)
    if not title or relevance_score(title, text, final_url) < 5:
        return None
    if not contains_any(f"{title}\n{text}", PARTICIPATION_TERMS):
        return None

    category = classify(title, text, final_url)
    deadline = extract_deadline(text)
    city, uf, area = extract_location(title, text)
    status = infer_status(text, deadline)
    mode = extract_mode(text, category)
    org = organisation(final_url, text)
    found = now_br().date().isoformat()

    return {
        "ID": stable_id(final_url, title),
        "Titulo": title[:180],
        "Categoria": category,
        "Organizacao": org,
        "Modalidade": mode,
        "Cidade": city,
        "UF": uf,
        "CidadeUF": f"{city}/{uf}" if city and uf else "",
        "Abrangencia": area,
        "DataAbertura": "",
        "PrazoInscricao": deadline,
        "DataInicio": "",
        "DataFim": "",
        "GratuitoPago": "",
        "Resumo": extract_summary(title, text, category, org),
        "Publico": "",
        "Link": final_url,
        "Fonte": org,
        "DataDescoberta": found,
        "UltimaVerificacao": found,
        "Status": status,
        "RelacaoCopa2027": relation_level(title, text, final_url),
        "Origem": "Pesquisa Editorial",
    }

def pinpoint_opportunities(feed_url: str) -> list[dict]:
    """Lê o feed público zero-auth do Pinpoint e extrai vagas da FWWC 2027."""
    raw, _ = request_text(feed_url, timeout=15)
    payload = json.loads(raw)
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return []

    out = []
    found_date = now_br().date().isoformat()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        link = canonical_url(str(row.get("url") or ""))
        html_blob = " ".join(str(row.get(k) or "") for k in (
            "description", "key_responsibilities", "skills_knowledge_expertise", "benefits"
        ))
        text = visible_text(html_blob)
        blob = f"{title}\n{text}"
        if not title or not contains_any(blob, CORE_TERMS):
            continue
        if not trusted_url(link):
            continue

        employment = norm(row.get("employment_type_text") or row.get("employment_type"))
        category = "Voluntariado" if "volunteer" in employment or "volunt" in norm(title) else "Trabalho"

        workplace = norm(row.get("workplace_type_text") or row.get("workplace_type"))
        if "hybrid" in workplace or "hibrid" in workplace:
            mode = "Híbrido"
        elif "remote" in workplace or "online" in workplace:
            mode = "Online"
        elif workplace:
            mode = "Presencial"
        else:
            mode = extract_mode(text, category)

        location_obj = row.get("location") if isinstance(row.get("location"), dict) else {}
        location_name = str(location_obj.get("name") or "").strip()
        city = uf = ""
        area = location_name or "Brasil"
        loc_norm = norm(location_name)
        for host_city, host_uf in HOST_CITIES:
            if norm(host_city) in loc_norm:
                city, uf = host_city, host_uf
                area = f"{city}/{uf}"
                break

        deadline_raw = str(row.get("deadline_at") or "")
        deadline = deadline_raw[:10] if re.match(r"^20\d{2}-\d{2}-\d{2}", deadline_raw) else ""
        status = infer_status(text + "\nApply Now", deadline)

        out.append({
            "ID": stable_id(link, title),
            "Titulo": title[:180],
            "Categoria": category,
            "Organizacao": "FIFA",
            "Modalidade": mode,
            "Cidade": city,
            "UF": uf,
            "CidadeUF": f"{city}/{uf}" if city and uf else "",
            "Abrangencia": area,
            "DataAbertura": "",
            "PrazoInscricao": deadline,
            "DataInicio": "",
            "DataFim": "",
            "GratuitoPago": "",
            "Resumo": extract_summary(title, text, category, "FIFA"),
            "Publico": "Profissionais que atendam aos requisitos da vaga",
            "Link": link,
            "Fonte": "FIFA Careers",
            "DataDescoberta": found_date,
            "UltimaVerificacao": found_date,
            "Status": status,
            "RelacaoCopa2027": "Alta",
            "Origem": "Pesquisa Editorial",
        })
    return out[:40]

def merge(existing: list[dict], found: list[dict]) -> tuple[list[dict], int, int]:
    by_url = {canonical_url(str(x.get("Link", ""))): dict(x) for x in existing if x.get("Link")}
    by_sig = {(norm(x.get("Titulo", "")), norm(x.get("Organizacao", ""))): canonical_url(str(x.get("Link", ""))) for x in existing}
    added = updated = 0

    for item in found:
        url = canonical_url(item["Link"])
        sig = (norm(item.get("Titulo", "")), norm(item.get("Organizacao", "")))
        key = url if url in by_url else by_sig.get(sig, "")
        if key and key in by_url:
            old = by_url[key]
            changed = False
            protected_curated = {
                "Titulo", "Categoria", "Organizacao", "Modalidade", "Resumo",
                "Publico", "GratuitoPago", "DataInicio", "DataFim",
                "RelacaoCopa2027", "Fonte", "Abrangencia", "ID", "Origem",
            }
            curated = norm(old.get("Origem", "")) == "curadoria inicial"
            for field, value in item.items():
                if field == "DataDescoberta":
                    continue
                if curated and field in protected_curated and old.get(field) not in ("", None):
                    continue
                if value not in ("", None) and old.get(field) != value:
                    old[field] = value
                    changed = True
            old["UltimaVerificacao"] = item["UltimaVerificacao"]
            by_url.pop(key, None)
            by_url[url] = old
            by_sig[sig] = url
            if changed:
                updated += 1
        else:
            by_url[url] = item
            by_sig[sig] = url
            added += 1

    rows = list(by_url.values())
    today = now_br().date()
    for row in rows:
        deadline = row.get("PrazoInscricao")
        if deadline:
            try:
                d = dt.date.fromisoformat(deadline)
                if d < today:
                    row["Status"] = "Encerrada"
                elif (d - today).days <= 7 and row.get("Status") != "Encerrada":
                    row["Status"] = "Encerra em breve"
            except ValueError:
                pass

    order = {"Inscrições abertas": 0, "Encerra em breve": 1, "Inscrições em breve": 2, "Encerrada": 3}
    rows.sort(key=lambda x: (
        order.get(x.get("Status", ""), 9),
        x.get("PrazoInscricao") or "9999-12-31",
        x.get("Titulo", ""),
    ))
    return rows, added, updated

def main() -> int:
    started = now_br()
    existing = load_json(DATA_PATH, [])
    urls = []
    seen = set()
    errors = []
    query_stats = []

    def add_url(url: str):
        url = canonical_url(url)
        if url.startswith("http") and trusted_url(url) and url not in seen:
            seen.add(url)
            urls.append(url)

    feed_found = []
    feed_stats = []
    for feed in PINPOINT_FEEDS:
        try:
            items = pinpoint_opportunities(feed)
            feed_stats.append({"feed": feed, "resultados": len(items)})
            feed_found.extend(items)
        except Exception as exc:
            feed_stats.append({"feed": feed, "resultados": 0, "erro": f"{type(exc).__name__}:{exc}"})
            errors.append(f"feed:{feed}:{type(exc).__name__}:{exc}")

    for url in SEED_URLS:
        add_url(url)

    hub_stats = []
    for hub in HUB_URLS:
        try:
            links = discover_hub_links(hub)
            hub_stats.append({"hub": hub, "resultados": len(links)})
            for url in links:
                add_url(url)
        except Exception as exc:
            hub_stats.append({"hub": hub, "resultados": 0, "erro": f"{type(exc).__name__}:{exc}"})
            errors.append(f"hub:{hub}:{type(exc).__name__}:{exc}")

    for query in SEARCH_QUERIES:
        try:
            results, engines = search_web(query)
            query_stats.append({"query": query, "resultados": len(results), "motores": engines})
            for url in results:
                add_url(url)
        except Exception as exc:
            query_stats.append({"query": query, "resultados": 0, "erro": f"{type(exc).__name__}:{exc}"})
            errors.append(f"search:{query}:{type(exc).__name__}:{exc}")

    urls = urls[:MAX_PAGES_PER_RUN]
    found = list(feed_found)
    for url in urls:
        try:
            item = opportunity_from_url(url)
            if item:
                found.append(item)
        except Exception as exc:
            errors.append(f"page:{url}:{type(exc).__name__}:{exc}")

    merged, added, updated = merge(existing, found)
    atomic_dump(DATA_PATH, merged)

    finished = now_br()
    telemetry = {
        "versao": "1.1",
        "inicio": started.isoformat(timespec="seconds"),
        "fim": finished.isoformat(timespec="seconds"),
        "consultas_airtable": 0,
        "queries": query_stats,
        "feeds": feed_stats,
        "hubs": hub_stats,
        "urls_avaliadas": len(urls),
        "oportunidades_validas_na_execucao": len(found),
        "adicionadas": added,
        "atualizadas": updated,
        "total_arquivo": len(merged),
        "erros": errors[:20],
        "isolamento": {
            "noticias": "inalterado",
            "eventos": "inalterado",
            "instagram": "inalterado",
            "alertas": "inalterado",
        },
    }
    atomic_dump(STATUS_PATH, telemetry)

    print(f"oportunidades_feed={len(feed_found)}")
    print(f"oportunidades_urls={len(urls)}")
    print(f"oportunidades_validas={len(found)}")
    print(f"oportunidades_adicionadas={added}")
    print(f"oportunidades_atualizadas={updated}")
    print(f"oportunidades_total={len(merged)}")
    print(f"oportunidades_erros={len(errors)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
