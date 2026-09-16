#!/usr/bin/env python3
"""Correção cirúrgica para fontes Google News com nome de veículo sem domínio.

Mantém integralmente a pesquisa editorial v3 e acrescenta somente aliases de domínio
para fontes que já apareceram no RSS. Não altera Airtable, schedules, merge, alertas,
Instagram, saúde, critérios de relevância ou limites de busca/validação.
"""
import importlib.util
from pathlib import Path

V3_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v3.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v3', V3_SCRIPT)
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)

# O Google News informou a fonte como "O TEMPO". Sem este alias, o fallback v2
# encerra antes da busca editorial porque _source_domain() não consegue obter domínio.
# A matéria ainda precisa passar por trusted_url, mesmo domínio, validação do título,
# relevância, frescor e deduplicação já existentes; portanto o alias não aprova nada só.
v3.v2.SOURCE_DOMAIN_HINTS.update({
    'o tempo': 'otempo.com.br',
})

if __name__ == '__main__':
    raise SystemExit(v3.pe.main())
