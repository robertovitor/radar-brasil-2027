# Migração conservadora dos alertas

Este diretório contém o novo estado operacional de deduplicação dos e-mails do Radar Brasil 2027.

## Princípios

- O Airtable continua como origem dos cadastros, consentimento, confirmação e descadastro.
- O histórico antigo de envios permanece no Airtable como arquivo legado.
- Novos históricos de envio devem ser registrados nos arquivos JSON deste diretório.
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
