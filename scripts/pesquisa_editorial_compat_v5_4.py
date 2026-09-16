#!/usr/bin/env python3
"""v5.4 — tolerância controlada para sugestões e Google News.

Escopo deliberadamente estreito:
- mantém exatamente as duas leituras Airtable do núcleo;
- não altera Merge, alertas, Instagram, saúde, schedules ou escrita no Airtable;
- sugestões: infere título/URL/data do payload já lido quando os nomes dos campos
  do formulário não coincidem com aliases conhecidos;
- Google News: quando a URL direta não é resolvida, permite fallback SOMENTE para
  fonte cujo domínio seja reconhecido e confiável, mantendo relevância, frescor e
  deduplicação. O link do agregador fica marcado como tal e não transforma
  news.google.com em domínio confiável global.
"""
import importlib.util
import re
from datetime import datetime
from pathlib import Path

V53_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v5_3.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v5_3', V53_SCRIPT)
v53 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v53)

v52=v53.v52; v51=v53.v51; v5=v53.v5; v3=v53.v3; v2=v53.v2
pe=v53.pe; compat=v53.compat

# ---------- Airtable: inferência local, sem nova chamada ----------
_IGNORE_KEYS=('status','email','e mail','nome contato','telefone','whatsapp','observacao','observacoes','comentario','comentarios','cidade','estado','uf','categoria','tema','impacto','organizador','patrocinador','publico','id')

def _all_scalar_values(value, depth=0):
    if depth>4 or value in (None,''): return []
    if isinstance(value,dict):
        out=[]
        for x in value.values(): out.extend(_all_scalar_values(x,depth+1))
        return out
    if isinstance(value,(list,tuple)):
        out=[]
        for x in value: out.extend(_all_scalar_values(x,depth+1))
        return out
    return [str(value).strip()]

def _infer_url(fields):
    # URL explícita em qualquer valor do registro. Não depende do nome da coluna.
    for value in fields.values():
        for text in _all_scalar_values(value):
            m=re.search(r'https?://[^\s<>"\']+', text, flags=re.I)
            if m: return m.group(0).rstrip('.,);]')
    return ''

def _infer_title(fields, link=''):
    # Prefere texto descritivo de tamanho editorial; ignora metadados administrativos.
    candidates=[]
    for key,value in fields.items():
        nk=compat.keynorm(key)
        if any(x==nk or x in nk for x in _IGNORE_KEYS): continue
        for text in _all_scalar_values(value):
            text=re.sub(r'\s+',' ',text).strip()
            if not text or text==link or re.match(r'^https?://',text,re.I): continue
            if compat.parse_date(text): continue
            if 12 <= len(text) <= 260 and len(text.split()) >= 3:
                score=(2 if any(x in nk for x in ('titulo','noticia','evento','assunto','nome')) else 0)+min(len(text)//40,3)
                candidates.append((score,len(text),text))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][2]
    return ''

def _infer_event_date(fields):
    # Primeiro qualquer campo cujo NOME sugira data/quando/dia; depois qualquer valor
    # que normalize inequivocamente para uma data. Não inventa data ausente.
    ordered=[]
    for key,value in fields.items():
        nk=compat.keynorm(key)
        if any(x in nk for x in ('data','quando','dia')): ordered.append(value)
    ordered += list(fields.values())
    seen=set()
    for value in ordered:
        for text in _all_scalar_values(value):
            if text in seen: continue
            seen.add(text)
            normalized=v3._normalize_event_date(text)
            parsed=compat.parse_date(normalized)
            if parsed:
                try:
                    d=datetime.strptime(parsed,'%Y-%m-%d').date()
                    # Eventos do Radar: janela ampla, mas evita datas absurdas/históricas.
                    if pe.now().date().year-1 <= d.year <= 2028: return parsed
                except ValueError: pass
    return ''

def _normalize_record_v54(record,kind):
    enriched=v53._normalize_record_v53(record,kind)
    fields=dict(enriched.get('fields',{}) or {})
    link=compat.find_url(fields) or _infer_url(fields)
    title=compat.find_title(fields,kind) or _infer_title(fields,link)
    # Se só houver link, a página continua sendo a fonte do título; orçamento v5.3 vale.
    if not title and link and pe.trusted_url(link): title=v2._title_from_url(link)
    if link: fields['Link']=link
    if title: fields['Título']=title
    if kind=='eventos' and not compat.parse_date(compat.value_by_alias(fields,('Data','Data do evento','Data do Evento'))):
        d=_infer_event_date(fields)
        if d: fields['Data']=d
    out=dict(enriched); out['fields']=fields
    return out

def candidate_from_record_v54(record,kind):
    if kind not in ('noticias','eventos'): return v53.candidate_from_record_v53(record,kind)
    enriched=_normalize_record_v54(record,kind)
    candidate=compat.candidate_from_record_compat(enriched,kind)
    if candidate is None: return None
    return v5._validate_suggestion(enriched,kind,candidate)

pe.candidate_from_record=candidate_from_record_v54

# ---------- Google News: fallback controlado para fonte confiável ----------
_original_rss_candidates=pe.rss_candidates

def _trusted_source_domain(source):
    domain=v2._source_domain(source)
    if not domain: return ''
    return domain if pe.trusted_url('https://'+domain+'/') else ''

def rss_candidates_v54():
    out=[]
    for c0 in _original_rss_candidates():
        c=dict(c0)
        if c.get('origin')=='google-news':
            domain=_trusted_source_domain(c.get('source',''))
            if domain and pe.article_is_relevant(c.get('title','')):
                # O resolver direto já falhou nas camadas anteriores. Em vez de perder a
                # pauta, preserva o URL Google News como trilha de auditoria e confia
                # somente na combinação fonte confiável + título relevante + pubDate.
                c['origin']='google-news-trusted-source'
                c['trusted_source_domain']=domain
                print(f"google_news_trusted_fallback=v5.4|{domain}|{c.get('title','')[:140]}")
        out.append(c)
    return out

pe.rss_candidates=rss_candidates_v54

_original_public_research=pe.public_research

def public_research_v54(keys):
    # O núcleo não aceita news.google.com. Para o fallback controlado, fazemos a menor
    # adaptação possível: coletamos candidatos v5.4, aprovamos apenas os de fonte
    # confiável e data RSS recente; os demais continuam pelo núcleo normal.
    raw=pe.rss_candidates()+pe.gdelt_candidates()
    fallback=[]; normal=[]
    for c in raw:
        if c.get('origin')=='google-news-trusted-source': fallback.append(c)
        else: normal.append(c)

    # Executa núcleo normal sem recolher RSS outra vez.
    saved_rss=pe.rss_candidates; saved_gdelt=pe.gdelt_candidates
    try:
        pe.rss_candidates=lambda: normal
        pe.gdelt_candidates=lambda: []
        count,approved,rejected,duplicates,audit=_original_public_research(keys)
    finally:
        pe.rss_candidates=saved_rss; pe.gdelt_candidates=saved_gdelt

    seen={pe.norm(x.get('Titulo','')) for x in approved}
    for c in fallback:
        title=c.get('title','').strip(); domain=c.get('trusted_source_domain','')
        base={'origem':'google-news-trusted-source','titulo':title,'fonte':c.get('source',''),'url':c.get('url','')}
        tk=pe.norm(title)
        if not title or not domain or not pe.article_is_relevant(title):
            rejected+=1; audit.append({**base,'decisao':'rejeitado','motivo':'Fallback sem fonte confiável ou relevância.'}); continue
        if tk in seen or ('t:'+tk) in keys:
            duplicates+=1; audit.append({**base,'decisao':'duplicado','motivo':'Título já existente.'}); continue
        pub=str(c.get('pub',''))
        # Google RSS usa RFC 2822; aceita somente publicação verificavelmente recente.
        try:
            from email.utils import parsedate_to_datetime
            d=parsedate_to_datetime(pub).astimezone(pe.BRT).date()
        except Exception:
            rejected+=1; audit.append({**base,'decisao':'rejeitado','motivo':'Data RSS não verificável.'}); continue
        age=(pe.now().date()-d).days
        if age < -1 or age > v5.NEWS_MAX_AGE_DAYS:
            rejected+=1; audit.append({**base,'decisao':'rejeitado','motivo':f'Notícia fora da janela de frescor ({age}d).'}); continue
        item={'Data':d.isoformat(),'DataBR':d.strftime('%d/%m/%Y'),'Titulo':title,'Tema':'Copa Feminina 2027','CidadeUF':'Brasil','Veiculo':domain,'Link':c.get('url',''),'Sentimento':'Neutro','Impacto':'Médio','Resumo':f'Fonte: {domain}. Descoberta via Google News; URL editorial direta não resolvida automaticamente.'}
        approved.append(item); seen.add(tk); keys.add('t:'+tk)
        audit.append({**base,'decisao':'aprovado','motivo':'Fallback v5.4: fonte confiável, título relevante, data RSS recente e não duplicado.'})
    return count+len(fallback),approved,rejected,duplicates,audit

pe.public_research=public_research_v54

if __name__=='__main__':
    raise SystemExit(pe.main())
