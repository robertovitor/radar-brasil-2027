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
                editorialmente_aprovada=status.strip().casefold()=='aprovado'
                item={'id':rid,'kind':kind,'title':title,'outcome':'pending'}
                report['items'].append(item)
                if not title or not link:
                    item['reason']='Título ou link ausente; completar a sugestão'
                    report['pending']+=1
                    continue
                candidate=pe.candidate_from_record(rec,kind)
                if not candidate:
                    item['reason']='Data ou estrutura obrigatória ausente'
                    report['pending']+=1
                    continue
                if kind=='eventos' and candidate['Data'] < datetime.now(timezone.utc).date().isoformat():
                    item['reason']='Evento com data passada; não publicar como novidade'
                    report['pending']+=1
                    continue
                if (('u:'+pe.urlnorm(candidate['Link'])) in keys
                    or ('t:'+pe.norm(candidate['Titulo'])) in keys
                    or (kind=='eventos' and ('i:'+str(candidate.get('ID','')).strip().casefold()) in keys)):
                    item['outcome']='duplicate'; report['duplicates']+=1
                    continue
                # Uma sugestão marcada como Aprovado já passou pela revisão editorial
                # no Airtable. Não exigir que links de Instagram exponham HTML público
                # novamente: isso bloqueava a publicação de sugestões já validadas.
                if not editorialmente_aprovada:
                    host=(urllib.parse.urlparse(link).hostname or '').casefold().removeprefix('www.')
                    if host in ('instagram.com','facebook.com','tiktok.com') or not pe.trusted_url(link):
                        item['reason']='Fonte social ou domínio ainda sem confirmação independente'
                        report['pending']+=1
                        continue
                    excerpt,final_url=pe.fetch_article_excerpt(link)
                    if not excerpt or not pe.trusted_url(final_url) or not pe.article_is_relevant(title,excerpt):
                        item['reason']='Fonte/conteúdo ainda não verificado; permanece pendente'
                        report['pending']+=1
                        continue
                    if kind=='noticias':
                        candidate['Resumo']=candidate.get('Resumo') or excerpt[:900]
                inbox.setdefault(kind,[]).append(candidate)
                keys.add('u:'+pe.urlnorm(candidate['Link']))
                keys.add('t:'+pe.norm(candidate['Titulo']))
                if kind=='eventos': keys.add('i:'+str(candidate.get('ID','')).strip().casefold())
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
