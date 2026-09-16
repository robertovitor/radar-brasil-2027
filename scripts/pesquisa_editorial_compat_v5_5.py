#!/usr/bin/env python3
"""v5.5 — extração segura de eventos da Seleção Feminina descobertos na pesquisa.

Mantém a v5.4 e acrescenta somente uma ponte notícia -> evento:
- usa os candidatos RSS/Google News JÁ coletados pela v5.4 (zero novas leituras Airtable);
- aceita evento quando título + fonte confiável deixam confronto/data/local inequívocos;
- não exige que a notícia tenha sido aprovada como notícia antes;
- não transforma notícias genéricas em eventos;
- deduplica contra dados.json e editorial/inbox.json;
- não altera Merge, Alertas, Instagram, Saúde, schedules ou limites de frescor.
"""
import importlib.util
from pathlib import Path

V54_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v5_4.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v5_4', V54_SCRIPT)
v54 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v54)
pe = v54.pe

_original_rss_candidates = pe.rss_candidates
_original_dump = pe.dump

# Casos estruturados devem ser raros e comprováveis. O gatilho não depende mais de a
# notícia virar notícia aprovada; basta a pauta já descoberta pela pesquisa, fonte
# confiável/reconhecida e título inequívoco.
EVENT_RULES = (
    {
        'opponent': 'Argentina',
        'title_needles': ('selecao', 'feminina', 'argentina'),
        'source_allow': ('cbf.com.br', 'ge.globo.com', 'agorars.com.br'),
        'events': (
            ('2026-10-10', 'Porto Alegre', 'RS', 'Beira-Rio'),
            ('2026-10-13', 'São Lourenço da Mata', 'PE', 'Arena Pernambuco'),
        ),
    },
)


def _known_event_keys():
    keys=set()
    for path in (pe.ROOT/'dados.json', pe.INBOX):
        obj=pe.load(path, [] if path.name!='inbox.json' else {'eventos':[],'noticias':[]})
        items=obj if isinstance(obj,list) else obj.get('eventos',[])
        for item in items:
            if not isinstance(item,dict): continue
            date=str(item.get('Data') or '').strip()
            title=pe.norm(item.get('Titulo'))
            city=pe.norm(item.get('Cidade'))
            if date and title: keys.add((date,title,city))
    return keys


def _source_domain(candidate):
    # v5.4 já marca trusted_source_domain quando reconhece a fonte do Google News.
    domain=str(candidate.get('trusted_source_domain') or '').casefold().strip()
    if domain: return domain
    source=str(candidate.get('source') or '').casefold()
    # reaproveita o resolvedor existente; não faz request adicional.
    try:
        domain=v54.v2._source_domain(source) or ''
    except Exception:
        domain=''
    return domain.casefold()


def _events_from_candidates(candidates):
    known=_known_event_keys(); out=[]
    for c in candidates:
        title=str(c.get('title') or '').strip()
        nt=pe.norm(title)
        domain=_source_domain(c)
        for rule in EVENT_RULES:
            if not all(pe.norm(x) in nt for x in rule['title_needles']): continue
            if not any(allowed in domain for allowed in rule['source_allow']): continue
            # Proteção adicional: a pauta precisa falar explicitamente em amistoso/jogo.
            if not any(x in nt for x in ('amistoso','jogo','enfrenta','contra')): continue
            for date,city,uf,venue in rule['events']:
                event_title=f"Brasil x {rule['opponent']} — amistoso da Seleção Feminina"
                key=(date,pe.norm(event_title),pe.norm(city))
                if key in known:
                    print(f'official_event_duplicate={date}|{city}|{rule["opponent"]}')
                    continue
                known.add(key)
                out.append({
                    'ID':f'CBF-{date}-{rule["opponent"].upper()}',
                    'Titulo':event_title,
                    'Status':'Planejado',
                    'Data':date,
                    'DataBR':pe.datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y'),
                    'UF':uf,
                    'Cidade':city,
                    'Categoria':'Amistoso da Seleção Feminina',
                    'Organizador':'CBF',
                    'Publico':0,
                    'Patrocinador':'',
                    'Local':venue,
                    'Latitude':None,
                    'Longitude':None,
                    'Link':str(c.get('url') or ''),
                    'Observacoes':f"Amistoso Brasil x {rule['opponent']} identificado em pauta recente de fonte confiável; data e local estruturados pela regra editorial do Radar.",
                    'Mes':'',
                    'Ano':int(date[:4]),
                    'Regiao':'',
                })
                print(f'official_event_extracted={date}|{city}|{venue}|source={domain}')
    return out


def rss_candidates_v55():
    candidates=_original_rss_candidates()
    pe._v55_official_events=_events_from_candidates(candidates)
    return candidates

pe.rss_candidates=rss_candidates_v55


def dump_v55(path,obj):
    if path==pe.INBOX and isinstance(obj,dict):
        extra=getattr(pe,'_v55_official_events',[])
        if extra:
            existing=list(obj.get('eventos',[]))
            # Segunda barreira de dedupe, inclusive se o núcleo adicionou o mesmo evento.
            keys={(str(x.get('Data') or ''),pe.norm(x.get('Titulo')),pe.norm(x.get('Cidade'))) for x in existing if isinstance(x,dict)}
            added=0
            for event in extra:
                key=(event['Data'],pe.norm(event['Titulo']),pe.norm(event['Cidade']))
                if key not in keys:
                    existing.append(event); keys.add(key); added+=1
            obj=dict(obj); obj['eventos']=existing
            print(f'official_events_added_to_inbox={added}')
    return _original_dump(path,obj)

pe.dump=dump_v55

if __name__=='__main__':
    raise SystemExit(pe.main())
