# API do GLPI 11 (v2) — o que você precisa saber

Base: `http://localhost:8080/api.php`

Tudo abaixo foi confirmado ao vivo contra o lab local (GLPI 11.0.8), rodando
`docker compose up -d` na pasta `lab/`. Nada aqui é presumido.

## Antes de tudo: a API v2 vem desligada

Numa instalação nova, a "High-Level API" (a v2) está **desabilitada por
padrão**. Toda chamada em `/api.php/v2/...` retorna `403` com
`"detail":"The High-Level API is disabled"`, mesmo com um token válido, até
que as chaves `enable_api` e `enable_hlapi` sejam ligadas em `glpi_configs`
(contexto `core`) e o cache seja limpo (`php bin/console cache:clear`). No
lab isso já vem feito: o `lab/seed.sql` carrega o banco com a API habilitada
e o cliente OAuth já criado — você não precisa rodar nenhum script. Veja
`lab/oauth-client.md` para as credenciais.

## Autenticação (OAuth2)

`POST /api.php/token` com JSON:

    {"grant_type":"password","client_id":"...","client_secret":"...",
     "username":"glpi","password":"glpi","scope":"api"}

Devolve `{token_type, expires_in: 3600, access_token, refresh_token}`. Todas
as demais chamadas levam o header `Authorization: Bearer <access_token>`.

As credenciais estão em `lab/oauth-client.md`. O token expira em 1 hora —
seu agente precisa renovar (mesmo endpoint, `grant_type: refresh_token`).

O swagger completo (schema OpenAPI) fica em `GET /api.php/v2/doc.json` — é
**público**: responde `200` com o schema inteiro (1219 rotas) sem nenhum
header `Authorization`, testado tanto de fora do container quanto de dentro
dele. Ainda assim precisa da API habilitada (ver seção acima).

## Armadilhas que custam horas

- **Paginação** é por `?start=N&limit=M` (não `?range=0-199` como em notas
  de outra instância — esse parâmetro é ignorado). Confirmado ao vivo: sem
  `start`/`limit`, ou com `limit` igual ou maior que o total de registros, a
  listagem retorna **HTTP 200** com o corpo completo. Com `start`/`limit`
  cobrindo só uma fatia de uma coleção maior (confirmado com os 300
  chamados reais e `?start=0&limit=10`), a mesma rota retorna **HTTP 206
  Partial Content**. Ou seja: "listagens retornam 206" só vale quando a
  resposta é de fato parcial — uma página que cobre tudo retorna 200. Em
  ambos os casos o header `Content-Range: <inicio>-<fim>/<total>` vem
  presente. **Trate qualquer código 200–299 como sucesso** — é a regra que
  cobre os dois casos e não quebra quando a base cresce.
- **Não existe filtro server-side.** Confirmado ao vivo contra os 300
  chamados: `?filter=status==1` e `?status=1` são **ignorados
  silenciosamente** — a resposta continua sendo a listagem inteira
  (paginada), sem nenhum erro. A sintaxe com colchetes (`?filter[status]=1`)
  se comporta diferente: devolve `400 ERROR_INVALID_PARAMETER`, porque é
  interpretada como uma consulta RSQL malformada, não como um filtro por
  campo. Nas três formas, o resultado é o mesmo na prática: não tem como
  pedir ao servidor "só os chamados abertos" ou "só os de rede". Pagine a
  coleção inteira (`start`/`limit`) e filtre/agregue no código do seu
  próprio agente.
- A API legada `/apirest.php` **não existe** nesta instalação (não há
  `apirest.php` nem `api.php` como arquivo físico em `public/`; tudo é
  roteado via `index.php`/Symfony). Não use.
- Tickets na lixeira têm `is_deleted: true` — confirmado no schema do
  `PATCH /Assistance/Ticket/{id}`, mas o filtro de listagem não foi testado
  ao vivo.

## Base de conhecimento

Rota confirmada ao vivo — **não é** `/Assistance/KnowbaseItem`,
`/Tools/KnowbaseItem` nem `/KnowBaseItem` como cogitado inicialmente:

- Lista: `GET /api.php/v2/Knowledgebase/Article`
- Detalhe: `GET /api.php/v2/Knowledgebase/Article/{id}`
- Criar: `POST /api.php/v2/Knowledgebase/Article`

Campos confirmados: `id`, `name` (título), `content` (conteúdo HTML — **não**
`answer`), `date_creation`, `date_mod`, `categories` (array), `entity`,
`is_faq`, `views`. O conteúdo é **HTML** — converta para texto antes de
indexar.

Confirmado ao vivo: `POST /api.php/v2/Knowledgebase/Article` com
`{"name": "...", "content": "<p>...</p>"}` retorna `201 Created` com
`{"id": ..., "href": "/Knowledgebase/Article/{id}"}`.

## Categoria de chamado

Rota confirmada ao vivo — **não é** `/Assistance/ITILCategory` como cogitado
no brief original:

- Lista: `GET /api.php/v2/Dropdowns/ITILCategory`
- Detalhe: `GET /api.php/v2/Dropdowns/ITILCategory/{id}`

(A categoria de artigos da base de conhecimento é uma rota separada:
`GET /api.php/v2/Knowledgebase/Category`.)

## Usuário

Rota confirmada ao vivo — bate com a suposição do brief:

- Lista: `GET /api.php/v2/Administration/User`
- Detalhe: `GET /api.php/v2/Administration/User/{id}`
- Usuário autenticado: `GET /api.php/v2/Administration/User/Me`

## Chamados

- Lista: `GET /api.php/v2/Assistance/Ticket`
- Detalhe: `GET /api.php/v2/Assistance/Ticket/{id}` (mesmo shape da lista)
- Dropdowns já vêm expandidos inline: `status`, `category`, `entity` são
  objetos `{id, name}`, não IDs soltos (confirmado no `PATCH` de teste).

Campos confirmados: `id`, `name` (título), `content` (HTML), `status`,
`priority`, `urgency`, `impact`, `category`, `entity`, `user_recipient`,
`date`, `date_creation`, `date_mod`, `date_solve`, `date_close`, `team`.

**Atenção com as datas — é a armadilha mais silenciosa da API.** Medido ao
vivo contra os 300 chamados do corpus: `date_creation` **não** é a data de
abertura do chamado. Ela reflete o instante em que o laboratório foi
gerado — os 300 chamados têm `date_creation` concentrado numa janela de
poucos minutos (o tempo que o seed levou para rodar), não os últimos meses.
É inútil para qualquer análise temporal ("chamados dos últimos 60 dias",
distribuição por mês etc.). A data de abertura real, que cobre cerca de 18
meses de histórico, é o campo **`date`**. Use `date` para qualquer pergunta
sobre quando um chamado foi aberto; use `date_creation` só se precisar saber
quando o registro foi gravado no banco — raramente é o que se quer.

O campo `team[]` está presente e confirmado ao vivo. É um array de objetos,
um por pessoa envolvida no chamado, no formato:

    {
      "role": "requester" | "assigned",
      "name": "ana.ribeiro",
      "realname": "Ribeiro",
      "firstname": "Ana",
      "display_name": "Ribeiro Ana",
      "id": 7,
      "href": "/front/user.form.php?id=7",
      "type": "User"
    }

`role: "requester"` é quem abriu o chamado; `role: "assigned"` é o técnico
responsável. Um chamado pode ter os dois papéis ocupados pela mesma
pessoa — confira o `id`/`name` de cada entrada antes de assumir que são
pessoas diferentes.

## Timeline (comentários e solução)

`GET /api.php/v2/Assistance/Ticket/{id}/Timeline` — confirmado ao vivo,
retorna `200` com a lista de itens do chamado (acompanhamentos, solução
etc.); um chamado sem nenhuma interação registrada devolve lista vazia.

Cada item tem a forma `{"type": "...", "item": {...}}`. Use o campo `type`
para distinguir o subtipo, não a forma do objeto em `item`:

- `type: "Followup"` — um acompanhamento (comentário). `item` confirmado ao
  vivo com: `id`, `itemtype`, `items_id`, `content` (HTML), `is_private`,
  `date`, `date_creation`, `date_mod`, `timeline_position`, `user` (objeto
  `{id, name}` de quem escreveu), `user_editor`, `request_type`.
- `type: "Solution"` — a solução registrada do chamado. `item` confirmado
  ao vivo com: `id`, `itemtype`, `items_id`, `content` (HTML), `status`,
  `date_creation`, `date_mod`, `date_approval`, `user`, `user_editor`,
  `approver`, `approval_followup`. **Não tem** `is_private` nem
  `timeline_position` — mais um jeito de distinguir de um `Followup`, mas
  o campo `type` já é suficiente e é o que você deve checar.

Sub-recurso de escrita confirmado ao vivo:
`POST /api.php/v2/Assistance/Ticket/{id}/Timeline/Followup` com
`{"content": "..."}` retorna `201 Created` com
`{"id": ..., "href": "/Assistance/Ticket/{id}/Timeline/Followup/{id}"}`.
Isso funciona mesmo em um chamado **fechado** — confirmado ao vivo (ver a
seção de escrita abaixo, que contrasta com o comportamento do `PATCH`).

## Escrita (Sprint 4)

Confirmado ao vivo:

- Criar chamado: `POST /api.php/v2/Assistance/Ticket` com `{name, content}`
  — corpo achatado, sem envelope `input`. Resposta: `201 Created` com
  `{"id": ...,"href": "..."}`.
- Comentar: `POST /api.php/v2/Assistance/Ticket/{id}/Timeline/Followup` com
  `{content}`. É o sub-recurso `/Followup`, não `/Timeline` direto (esse é
  só GET). **Funciona em chamados fechados** — confirmado ao vivo contra um
  chamado com `status: Fechado`, retornou `201` normalmente.
- Atualizar: `PATCH /api.php/v2/Assistance/Ticket/{id}` com JSON parcial —
  confirmado com `{"name": "..."}`. O comportamento **depende do status do
  chamado**, e isso não é detalhe menor: **59% do corpus está fechado**.
  - Em chamado **não fechado** (confirmado com um chamado `Novo`): retorna
    `200` com o objeto completo atualizado, como esperado.
  - Em chamado **fechado** (confirmado com um chamado `Fechado`): retorna
    `500` com `{"status":"ERROR","title":"Failed to update item(s)",
    "detail":null}` — sem detalhe do motivo. O GLPI recusa a edição de um
    chamado fechado pela regra de negócio padrão, e a API devolve isso como
    erro genérico de servidor em vez de um `4xx` explicativo. Trate `PATCH`
    em chamado fechado como uma falha **esperada**, não um bug do seu
    código — tentar de novo ou mudar o corpo da requisição não resolve. Se
    seu agente precisa registrar algo num chamado fechado, use o
    `Followup` acima, que não tem essa restrição.

  ## API FastAPI da aplicação

  As operações do GLPI são expostas diretamente pela aplicação FastAPI em
  `src/main.py`:

      uvicorn src.main:app --host 127.0.0.1 --port 8000

  Ou inicie a aplicação com `python -m src.main`.

  O OpenAPI interativo fica em `/docs`. As rotas estão sob `/api`: usuário
  autenticado, listagem/detalhe/timeline/criação/atualização de chamados,
  acompanhamentos, artigos, categorias e usuários. O proxy preserva os códigos
  HTTP do GLPI (incluindo `201` e `206`).

  Todas as requisições HTTP passam primeiro por `PydanticRequestValidationMiddleware`,
  que valida globalmente método, caminho, query string, formato JSON e tamanho
  do corpo (limite de 1 MB). Cada rota ainda valida seus próprios campos e
  tipos usando modelos Pydantic específicos; a validação por rota não substitui
  essa validação global.

  Em uso normal, envie um access token OAuth2 do GLPI como
  `Authorization: Bearer <token>`. O serviço valida o token consultando
  `/Administration/User/Me` no GLPI. Se o token tiver formato JWT, seus claims
  são decodificados depois dessa validação remota; o conteúdo localmente
  decodificado não é usado para autenticar. Tokens opacos também são aceitos
  quando o GLPI os reconhece.

  Os corpos de criação de chamados e acompanhamentos têm limites de tamanho.
  `POST /api/chat` valida mensagem (até 4000 caracteres) e histórico (até 50
  itens, apenas papéis `user`/`assistant`). A tarefa 3 processa a mensagem,
  extrai palavras-chave e retorna até três artigos relevantes consultados no
  GLPI com o Bearer recebido. A resposta contém `pergunta`, `palavras_chave`,
  `artigos` e `total`. O histórico continua aceito, mas ainda não participa da
  busca, e não há geração de texto por IA. Veja `README-tarefa3.md` para
  executar os testes e usar a collection Postman.

  Para testes locais, o bypass das validações adicionais e da autenticação
  Bearer pode ser habilitado somente com as duas variáveis:

      APP_ENV=development
      DEV_BYPASS_API_VALIDATION=true

  O bypass não é ativado fora de `development`, mesmo se a segunda variável
  estiver ligada. Ele não desativa a validação estrutural de tipos do Pydantic.
  Não habilite essa configuração em ambientes compartilhados ou de produção.

  **Autorização por endpoint:** o middleware não pré-valida o token chamando
  `/Administration/User/Me`. Ele encaminha o Bearer para a rota GLPI solicitada
  para evitar bloquear tokens cujo escopo permite tickets, mas não o endpoint
  de usuário autenticado. Assim, `/api/me` pode retornar `403` por falta de
  escopo mesmo quando `/api/tickets` funciona; o GLPI exige que esse escopo seja
  concedido separadamente.

  A aplicação e suas rotas vivem em `src/main.py` (não em um módulo FastAPI
  separado). O fluxo OAuth existente também está exposto em
  `POST /api/auth/token` e `POST /api/auth/refresh`; os dois corpos são
  validados com modelos Pydantic antes de chamar o GLPI.

## Resumo das mudanças

- **FastAPI integrado:** a aplicação e todas as rotas ficam em `src/main.py`.
  Inicie com `uvicorn src.main:app --host 127.0.0.1 --port 8000` ou
  `python -m src.main`. A documentação interativa fica em `/docs`.
- **Rotas disponíveis:** operações de autenticação OAuth, `/api/me`,
  `/api/tickets` (lista, detalhes, timeline e escrita), `/api/articles`,
  `/api/categories` e `/api/users`.
- **Token e permissões:** envie `Authorization: Bearer <token>`. A aplicação
  encaminha o token à rota GLPI solicitada; o próprio GLPI verifica o escopo.
  `/api/me` pode responder `403` por falta de escopo mesmo quando
  `/api/tickets` funciona. Essa regra por endpoint substitui qualquer
  descrição anterior que diga que `/api/me` é chamado para pré-validar todas
  as requisições.
- **Validação Pydantic:** middleware valida globalmente método, caminho,
  query string, JSON e tamanho máximo do corpo (1 MB). Modelos por rota
  também verificam campos: paginação, autenticação, chamados, acompanhamentos
  e chat. O chat limita mensagem a 4.000 caracteres e histórico a 50 itens.
- **Bypass local:** `APP_ENV=development` e
  `DEV_BYPASS_API_VALIDATION=true` desativam as verificações extras para
  testes. Não habilite em produção.
- **Testes:** `python -m unittest discover -s tests`.
