# Publicador do Instagram

O publicador usa a Instagram Graph API e só é executado manualmente pelo workflow **Publicar no Instagram**.

## Proteções

- Não existe gatilho automático nesta fase.
- O modo padrão é `validate`, que valida token, conta e arquivo sem publicar.
- Uma publicação real exige simultaneamente `mode=publish`, confirmação `PUBLICAR` e `approved: true` no JSON.
- Cada post possui uma chave idempotente. Chaves registradas em `instagram/publicados.json` são bloqueadas.
- O workflow usa grupo de concorrência único e grava o ID retornado pelo Instagram no histórico.

## Fluxo editorial

1. Criar um JSON em `instagram/fila/`.
2. Revisar imagem, legenda, fonte e pertinência.
3. Executar `validate`.
4. Depois da aprovação editorial, mudar `approved` para `true`.
5. Executar `publish` com a confirmação `PUBLICAR`.
6. Confirmar o novo registro em `instagram/publicados.json`.

A ligação automática com a rotina do Radar somente deve ser habilitada depois que o teste manual for concluído com sucesso.

## Política visual automática

A política visual fica em `instagram/visual-policy.json` e altera somente a camada de arte. Ela não muda schedule, deduplicação, cooldown, reservas, reconciliação ou publicação na Meta.

- `evento` → `text_art`: arte textual própria com data e local.
- `noticia` → `radar_art`: arte editorial própria do Radar.
- `oportunidade` → `radar_art_opportunity`: arte própria com destaque para prazo e participação.
- `fallback_to_legacy=true`: se o novo renderizador falhar, o fluxo visual anterior continua disponível.
- `opportunity_instagram_enabled=true`: oportunidades abertas de `oportunidades.json` podem entrar na seleção do Instagram.

### Rollback visual seguro

Para voltar temporariamente ao comportamento visual anterior sem tocar na schedule, defina `enabled=false` em `instagram/visual-policy.json`. Para desativar apenas Oportunidades no Instagram, defina `opportunity_instagram_enabled=false`.

