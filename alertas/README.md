# Migração conservadora dos alertas

Este diretório contém documentação e arquivos legados de deduplicação. Desde 12/10/2026, o envio ativo é o [resumo diário](resumo-diario.md), com contatos e histórico em armazenamento privado.

## Princípios

- O Airtable continua como origem dos cadastros, consentimento, confirmação e descadastro.
- O histórico antigo de envios permanece no Airtable como arquivo legado.
- Novos históricos do resumo diário ficam no estado privado persistente, fora deste repositório. Os JSON públicos anteriores são legados.
- Nenhum endereço de e-mail pode ser gravado neste repositório público.
- O destinatário é representado por `recipient_ref`, derivado do record ID do Airtable com SHA-256.
- O ponto de corte da migração é `2026-09-06T00:00:00Z`.

## Arquivos

- `envios-eventos.json`: novos envios de eventos e lembretes.
- `envios-noticias.json`: novos envios de notícias.
- `../scripts/alertas_ledger.py`: verificação e registro idempotente de envios.

## Regra de transição

Os registros anteriores ao ponto de corte não são copiados para o GitHub, evitando exposição de dados pessoais. Eles continuam disponíveis no Airtable apenas como histórico legado. O novo processador deve considerar somente conteúdo posterior ao ponto de corte e consultar o ledger local antes de cada envio.

A migração é deliberadamente conservadora: tabelas e formulários do Airtable não são apagados nem alterados nesta etapa.
