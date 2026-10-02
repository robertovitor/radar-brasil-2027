#!/usr/bin/env python3
"""Garante que toda inclusão publicada no Radar gere obrigação de Instagram.

A fila pending_new é durável: só deixa de ser elegível quando a chave aparece
no ledger de publicações/bloqueios do publicador. O estado known serve para
detectar apenas inclusões novas, evitando backfill do acervo histórico.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/"instagram"/"conteudo-conhecido.json"

def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def clean(v):
    return " ".join(str(v or "").strip().split())

def key_event(x):
    ident=clean(x.get("ID") or x.get("Titulo")).casefold()
    return f"instagram:evento:{ident}" if ident else ""

def key_news(x):
    ident=clean(x.get("Link") or x.get("Titulo")).casefold()
    return f"instagram:noticia:{ident}" if ident else ""

def key_opp(x):
    ident=clean(x.get("ID") or x.get("Link") or x.get("Titulo")).casefold()
    return f"instagram:oportunidade:{ident}" if ident else ""

def main():
    state=load(STATE,{"known":[],"pending_new":[]})
    known=list(dict.fromkeys(clean(k) for k in state.get("known",[]) if clean(k)))
    pending=list(dict.fromkeys(clean(k) for k in state.get("pending_new",[]) if clean(k)))
    known_set=set(known)
    added=[]

    groups=(
        ("evento",load(ROOT/"dados.json",[]),key_event),
        ("noticia",load(ROOT/"noticias.json",[]),key_news),
        ("oportunidade",load(ROOT/"oportunidades.json",[]),key_opp),
    )
    for kind,rows,keyfn in groups:
        for row in rows:
            if not isinstance(row,dict):
                continue
            key=keyfn(row)
            if not key or key in known_set:
                continue
            known.append(key); known_set.add(key)
            if key not in pending:
                pending.append(key)
            added.append((kind,key))

    new_state={"known":known,"pending_new":pending}
    if new_state!=state:
        STATE.write_text(json.dumps(new_state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"instagram_obligations_added={len(added)}")
    for kind,key in added:
        print(f"instagram_obligation={kind}|{key}")
    print(f"instagram_pending_total={len(pending)}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
