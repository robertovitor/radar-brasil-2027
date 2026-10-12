# Resumo diário dos assinantes

A rotina `Resumo diário Radar` envia pelo Gmail do projeto, às 21h de Brasília,
no máximo um resumo por endereço e por data local. Notícias e novos eventos são
combinados segundo as inscrições confirmadas de cada pessoa. Sem novidade,
não há envio nem consulta ao Airtable. O primeiro período começa em 12/10/2026;
conteúdo histórico anterior fica fora do resumo.

## Dados e execução

`scripts/resumo_diario.py` é um planejador local, sem acesso de rede. O executor
usa os conectores Gmail, Airtable, GitHub e armazenamento privado. Contatos,
consentimentos, bloqueios, planos e histórico de envio ficam exclusivamente em
um arquivo privado persistente, fora deste repositório público. Caminhos de
estado/plano dentro do repositório são recusados pelo planejador.

O Gmail remetente é `radarcopafeminina2027@gmail.com`. Cada envio é individual;
não há CC/BCC para outros assinantes. O rodapé permite solicitar cancelamento
por e-mail. Pedidos recebidos no Gmail também são verificados e bloqueados no
estado privado antes dos envios.

## Leituras Airtable

- Cache das duas listas de assinantes: atualização após sete dias, apenas em
  rodada com conteúdo novo. Novas inscrições podem aguardar até essa atualização.
- Descadastros: uma leitura completa antes da rodada de envios, reutilizada
  para todos os destinatários. `Confirmar descadastro` é checkbox; um pedido
  marcado é respeitado mesmo se o processamento administrativo está pendente.
- Nenhuma escrita em fila ou ledger do Airtable e nenhuma chamada por destinatário.
- Lista incompleta, falha de leitura, verificação vencida ou orçamento esgotado
  impedem o envio. A rotina não usa cache de descadastro como substituto da leitura.
- Limite próprio conservador: 29 chamadas em outubro/2026, incluindo cinco de
  preparação, e 45 por mês depois. Paginação, erros e metadados entram na conta;
  reservar e persistir orçamento antes de chamar a API. Esses limites não medem
  consumidores externos, especialmente o Worker de confirmação no Cloudflare.

## Controle de envio

O executor persiste uma reserva `sending` antes de chamar Gmail, usando a versão
atual do arquivo privado. Só o retorno confirmado com Gmail ID muda a reserva
para `sent`. Falha ou timeout deixa o envio pendente de reconciliação no Gmail;
nunca se repete um envio incerto automaticamente. A mesma chave de endereço
(SHA-256) + data de Brasília não pode ser reservada duas vezes. O arquivo privado
deve ser salvo após cada retorno confirmado, antes de avançar ao destinatário
seguinte. Conflitos de versão interrompem a execução antes do envio.

Itens inseridos depois do fechamento entram na edição seguinte. As identidades
já conhecidas não voltam a criar pendência por alterações cosméticas. Uma
confirmação de inscrição posterior à publicação não cria dívida histórica;
quando a hora de publicação não é comprovada, usar o início do intervalo de
observação como limite conservador. Itens removidos pela curadoria não são enviados.

As antigas rotinas horárias de envio, fila e pesquisa com Airtable permanecem
suspensas. A pesquisa pública, o site e o Instagram continuam em seus fluxos.

## Validação

`python -m unittest discover -s tests -p test_resumo_diario.py -v`

Os testes cobrem combinação de preferências, data em Brasília, idempotência,
descadastro confirmado por checkbox, confirmação do assinante, corte histórico,
leituras incompletas, verificações vencidas, HTML, orçamento e proteção de caminhos.
