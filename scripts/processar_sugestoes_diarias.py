#!/usr/bin/env python3
"""Daily, strictly budgeted suggestion intake. No Airtable writes or social autoapproval."""
import json, os, pathlib, urllib.request, urllib.parse
from datetime import datetime, timezone
from scripts import pesquisa_editorial as pe

ROOT=pathlib.Path(__file__).resolve().parents[1]
AUDIT=ROOT/'editorial'/'sugestoes-status.json'
MAX_RECORDS=100
TABLES=(('eventos',pe.TABLE_EVENTS),('noticias',pe.TABLE_NEWS))

def run():
    report={'at':datetime.now(timezone.utc).isoformat(),'reads':0,'writes':0,'processed':0,'queued':0,'pending':0,'duplicates':0,'errors':[],'items':[]}
    try:
        if os.getenv('RADAR_SUGGESTIONS_DAILY')!='1' or os.getenv('RADAR_AIRTABLE_ALLOW')!='1':
            raise RuntimeError('Daily-only authorization absent')
        token=os.getenv('AIRTABLE_TOKEN','').strip()
        if not token: raise RuntimeError('Missing AIRTABLE_TOKEN')
        inbox=pe.load(pe.INBOX,{'eventos':[],'noticias':[]})
        keys=pe.existing_keys()
        for kind,table in TABLES:
            url=f'https://api.airtable.com/v0/{pe.BASE}/{table}?pageSize={MAX_RECORDS}'
            req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json'},method='GET')
            # Two requests total, no Airtable pagination or writes; fail closed at >100.
            report['reads']+=1
            with urllib.request.urlopen(req,timeout=20) as response:
                payload=json.load(response)
            if payload.get('offset'):
                raise RuntimeError('Table exceeds 100 rows: pagination disabled to protect budget')
            for rec in payload.get('records',[]):
                f=rec.get('fields',{})
                if not pe.processable(f): continue
                report['processed']+=1
                rid=rec['id']; link=str(pe.first(f,'Fonte ou link','Link','URL') or '').strip()
                title=str(pe.first(f,'Evento sugerido','Título ou assunto','Título','Titulo') or '').strip()
                status=str(pe.first(f,'Status') or '')
                if status.casefold()=='aprovado':
                    # Approved items should go through existing reconciliation, never republish blindly.
                    continue
                item={'id':rid,'kind':kind,'title':title,'outcome':'pending'}
                report['items'].append(item)
                host=(urllib.parse.urlparse(link).hostname or '').casefold().removeprefix('www.')
                if not title or not link or host in ('instagram.com','facebook.com','tiktok.com'):
                    item['reason']='Needs verified caption/source and complete metadata'
                    report['pending']+=1
                    continue
                if not pe.trusted_url(link):
                    item['reason']='Source needs independent editorial verification'
                    report['pending']+=1
                    continue
                candidate=pe.candidate_from_record(rec,kind)
                if not candidate:
                    item['reason']='Missing mandatory event date or structure'
                    report['pending']+=1
                    continue
                if kind=='eventos' and candidate['Data'] < datetime.now(timezone.utc).date().isoformat():
                    item['reason']='Past event cannot be newly published'
                    report['pending']+=1
                    continue
                if ('u:'+pe.urlnorm(candidate['Link'])) in keys or ('t:'+pe.norm(candidate['Titulo'])) in keys:
                    item['outcome']='duplicate'; report['duplicates']+=1
                    continue
                excerpt,_=pe.fetch_article_excerpt(link)
                if not excerpt or not pe.article_is_relevant(title,excerpt):
                    item['reason']='Source text/relevance not independently verified'
                    report['pending']+=1
                    continue
                if kind=='noticias':
                    candidate['Resumo']=candidate.get('Resumo') or excerpt[:900]
                inbox.setdefault(kind,[]).append(candidate)
                keys.add('u:'+pe.urlnorm(candidate['Link']))
                keys.add('t:'+pe.norm(candidate['Titulo']))
                item['outcome']='queued'; report['queued']+=1
        if report['queued']:
            pe.dump(pe.INBOX,inbox)
        report['status']='complete'
    except Exception as e:
        report['status']='failed'
        report['errors'].append(str(e))
    AUDIT.parent.mkdir(parents=True,exist_ok=True)
    AUDIT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='items'},ensure_ascii=False))
    return 0 if report['status']=='complete' else 1

if __name__=='__main__':
    raise SystemExit(run())
