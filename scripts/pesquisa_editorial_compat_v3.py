#!/usr/bin/env python3
"""Camada conservadora v3 da pesquisa editorial.

Fecha duas brechas sem aumentar leituras do Airtable:
- sugestões de notícias já lidas passam pela mesma comparação semântica conservadora
  usada na pesquisa pública antes de poderem entrar em editorial/inbox.json;
- sugestões de eventos vindas do formulário podem usar os campos ``Data informada`` e
  ``Cidade informada`` como aliases dos campos já esperados pelo parser legado.

Não altera schedules e não muda merge, alertas, Instagram ou saúde operacional.
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


def _event_record_with_form_aliases(record):
    """Mapeia somente aliases já presentes no registro lido do Airtable.

    Não consulta Airtable, não altera o registro remoto e não inventa data/local.
    Só copia para os nomes já reconhecidos pelo parser quando o campo canônico está
    ausente. A validação de formato da data continua sendo feita pelo parser existente.
    """
    fields = dict(record.get('fields', {}) or {})
    normalized = {v2.compat.keynorm(k): k for k in fields}

    canonical_date_keys = {
        v2.compat.keynorm('Data'),
        v2.compat.keynorm('Data do evento'),
        v2.compat.keynorm('Data do Evento'),
    }
    has_canonical_date = any(k in normalized for k in canonical_date_keys)
    if not has_canonical_date:
        for alias in ('Data informada', 'Data do evento informada', 'Data sugerida'):
            source_key = normalized.get(v2.compat.keynorm(alias))
            if source_key and fields.get(source_key) not in (None, ''):
                fields['Data'] = fields[source_key]
                print(f"airtable_event_date_alias_used={record.get('id','')}|field={v2.compat.keynorm(alias)}")
                break

    # Mesmo princípio para cidade: aproveita somente o valor já enviado pelo formulário.
    if not fields.get('Cidade'):
        for alias in ('Cidade informada', 'Cidade do evento'):
            source_key = normalized.get(v2.compat.keynorm(alias))
            if source_key and fields.get(source_key) not in (None, ''):
                fields['Cidade'] = fields[source_key]
                break

    if fields == record.get('fields', {}):
        return record
    enriched = dict(record)
    enriched['fields'] = fields
    return enriched


def candidate_from_record_v3(record, kind):
    if kind == 'eventos':
        record = _event_record_with_form_aliases(record)

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
