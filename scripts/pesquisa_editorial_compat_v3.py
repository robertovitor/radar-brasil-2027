#!/usr/bin/env python3
"""Camada conservadora v3 da pesquisa editorial.

Fecha uma única brecha: sugestões já lidas do Airtable também passam pela mesma
comparação semântica conservadora usada na pesquisa pública antes de poderem entrar
em editorial/inbox.json.

Não faz leituras adicionais do Airtable, não altera schedules e não muda merge,
alertas, Instagram ou saúde operacional.
"""
import importlib.util
from pathlib import Path

V2_SCRIPT = Path(__file__).with_name('pesquisa_editorial_compat_v2.py')
spec = importlib.util.spec_from_file_location('pesquisa_editorial_compat_v2', V2_SCRIPT)
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
pe = v2.pe

_original_candidate_from_record = pe.candidate_from_record


def _semantic_prior_title(title):
    """Retorna título já conhecido apenas quando a regra v2 considera a mesma pauta."""
    if not title:
        return ''
    for prior in v2.compat.known_titles():
        if v2.compat.same_story(str(title), str(prior)):
            return str(prior)
    return ''


def candidate_from_record_v3(record, kind):
    candidate = _original_candidate_from_record(record, kind)
    if candidate is None or kind != 'noticias':
        return candidate

    prior = _semantic_prior_title(candidate.get('Titulo'))
    if not prior:
        return candidate

    # O main legado classifica duplicidade por chaves exatas. Substituir SOMENTE o
    # título da cópia em memória pelo título já existente faz essa mesma checagem
    # classificar corretamente como duplicado, sem gravar ou alterar o Airtable.
    blocked = dict(candidate)
    blocked['Titulo'] = prior
    print(f"airtable_semantic_duplicate_skipped={candidate.get('Titulo','')} | existing={prior}")
    return blocked


pe.candidate_from_record = candidate_from_record_v3

if __name__ == '__main__':
    raise SystemExit(pe.main())
