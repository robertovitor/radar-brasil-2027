#!/usr/bin/env python3
import re
import gerar_banco_imagens_v3 as base

MEN=re.compile(r"(?:\bmen\b|men['’]?s|\bmale\b|masculin)",re.I)

def editorial_ok(cat,title,desc):
    text=f'{title} {desc}'
    if base.BLOCK_COMMON.search(text):
        return False
    if cat=='torcida_futebol_feminino':
        return bool(base.WOMEN.search(text) and base.SOCCER.search(text) and base.FANS.search(text) and not base.BLOCK_AMERICAN.search(text) and not MEN.search(text))
    if cat=='selecao_brasileira':
        return bool(base.BRAZIL.search(text) and base.SOCCER.search(text) and not MEN.search(text))
    if cat=='futebol_feminino_brasil':
        return bool(base.BRAZIL.search(text) and base.SOCCER.search(text) and not MEN.search(text))
    if cat=='copas_femininas':
        return bool(re.search(r'world cup|copa do mundo',text,re.I) and not MEN.search(text))
    if cat=='futebol_feminino_internacional':
        return bool(base.SOCCER.search(text) and not base.BLOCK_AMERICAN.search(text) and not MEN.search(text))
    return True

base.editorial_ok=editorial_ok
base.main()
