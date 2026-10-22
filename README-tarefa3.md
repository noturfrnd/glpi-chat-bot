# Tarefa 3 — processar perguntas e buscar artigos no GLPI

A tarefa recebe o texto de uma pergunta, identifica palavras-chave e retorna até três artigos relevantes da base de conhecimento do GLPI. O endpoint é `POST /api/chat`.

Esta cópia está na branch `feat/tarefa3-processamento-perguntas`, baseada na
atualização `cd2572a` da `main` e na contribuição anterior de busca de artigos.
O desenvolvimento está local; a branch ainda não foi publicada no GitHub.

## O que foi implementado

- Validação de `message`: texto não vazio, com até 4.000 caracteres.
- Extração local de palavras-chave, sem repetição e na ordem da pergunta; normalização de acentos, maiúsculas, `e-mail/email` e `wi-fi/wi fi/wifi`; remoção de saudações e termos conversacionais.
- Consulta paginada ao GLPI com o token Bearer recebido do usuário. A opção implementada consulta os artigos disponíveis para esse token e filtra o retorno localmente por relevância lexical.
- Retorno com pergunta, palavras-chave, artigos e quantidade. A ordenação considera título, conteúdo e plataforma indicada, como Windows ou macOS.
- Tratamento de autenticação ausente, entrada inválida e falhas na consulta ao GLPI.

Nenhum modelo de IA é chamado. `history` é aceito e validado, mas não participa da pesquisa nesta tarefa. A busca usa os dados obtidos na requisição atual, sem cache compartilhado entre usuários. A pontuação não representa uma probabilidade de acerto; sinônimos ou perguntas muito diferentes do texto da base podem não encontrar um artigo existente.

## Abrir e iniciar o projeto

Abra esta pasta no VS Code ou no terminal:

```text
C:\Users\55799\Documents\Codex\2026-10-20\v\work\glpi-chat-bot
```

No PowerShell, entre nela e configure o endereço real do GLPI informado pelo grupo. `GLPI_BASE_URL` aponta para o servidor GLPI; `base_url`, usado no Postman, aponta para esta API local.

```powershell
Set-Location -LiteralPath 'C:\Users\55799\Documents\Codex\2026-10-20\v\work\glpi-chat-bot'
$env:GLPI_BASE_URL = 'https://endereco-do-glpi-do-grupo'
$env:APP_ENV = 'production'
$env:DEV_BYPASS_API_VALIDATION = 'false'
& 'C:\Users\55799\Documents\Codex\2026-10-20\v\work\venv-glpi\Scripts\python.exe' -B -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Substitua o endereço de exemplo antes de executar. Mantenha esse terminal aberto. A documentação interativa ficará em `http://127.0.0.1:8000/docs`.

O ambiente virtual citado acima foi preparado para esta cópia local. Em outro computador, crie o ambiente virtual e instale `requirements.txt` antes de iniciar o servidor.

## Importar e usar a collection no Postman

1. Clique em **Import** e selecione `GLPI-tarefa3.postman_collection.json`. No repositório, ela está na pasta `postman`.
2. Abra as variáveis da collection. `base_url` já aponta para `http://127.0.0.1:8000`.
3. Preencha localmente `client_id`, `client_secret`, `username` e `password` com os valores fornecidos pelo grupo. A collection entregue mantém esses campos vazios. Não publique nem compartilhe credenciais ou tokens; antes de exportar uma cópia, remova esses valores.
4. Deixe `access_token` e `refresh_token` vazios inicialmente. Evite criar variáveis de ambiente com os mesmos nomes, pois elas podem sobrescrever as variáveis da collection.
5. Execute **Create Token**. Em uma resposta bem-sucedida com `access_token` válido, o script salva os tokens na collection. Em resposta de erro ou corpo sem um token válido, o script limpa os tokens da collection.
6. Opcionalmente, execute **Validate Token** para consultar o usuário autenticado. Um 403 nessa consulta pode indicar falta de permissão para `/api/me`, mesmo que o token possa consultar artigos; teste **Busca natural** para verificar essa permissão específica. Os quatro pedidos originais foram preservados: **Create Token**, **Refresh Token**, **Validate Token** e **Listar Tickets**.
7. Abra a pasta **Tarefa 3 — processamento de perguntas** e execute as requisições. As quatro primeiras usam o token salvo; a última envia a pergunta sem Bearer para testar o erro 401.

Quando necessário, use **Refresh Token**. O script só salva o novo token após uma resposta bem-sucedida e limpa valores inválidos após falha. Se a conexão falhar antes de existir uma resposta, confirme as variáveis manualmente: o script de resposta do Postman pode não ter sido executado.

## Requisição e resposta

Envie JSON com o cabeçalho `Content-Type: application/json` e autenticação `Authorization: Bearer <access_token>`:

```json
{
  "message": "Oi, bom dia, estou tentando configurar a VPN no Windows e preciso de ajuda",
  "history": []
}
```

A resposta 200 tem esta estrutura. O exemplo vazio ilustra o contrato; não antecipa o resultado da base real:

```json
{
  "pergunta": "Oi, bom dia, estou tentando configurar a VPN no Windows e preciso de ajuda",
  "palavras_chave": ["configurar", "vpn", "windows", "ajuda"],
  "artigos": [],
  "total": 0
}
```

Cada item de `artigos`, quando houver resultado, contém `id`, `titulo`, `conteudo`, `pontuacao`, `termos_encontrados` e `fonte_api`. `total` deve ser igual ao tamanho de `artigos`, entre zero e três. `fonte_api` identifica o caminho do artigo no GLPI; não é um endpoint de detalhes criado por esta tarefa na API local.

## Conferir os critérios de aceitação

| Critério | Como verificar no Postman |
| --- | --- |
| Receber o texto da pergunta | Execute **Busca natural**. Confirme resposta 200 e o campo `pergunta` correspondente à mensagem enviada. |
| Processar o texto e identificar palavras-chave | Confira `palavras_chave` em **Busca natural** e **Busca com e-mail**. Saudações devem ser removidas e `e-mail` deve ser normalizado para `email`. |
| Retornar artigos do GLPI conforme as palavras-chave | Use uma pergunta sobre um artigo cuja existência e permissão de acesso sejam conhecidas no GLPI do grupo. Confira ID, título, conteúdo e relação com o assunto. |

Os scripts da collection conferem status HTTP, estrutura dos campos, palavras-chave e consistência de `total`. Eles não exigem que exista um artigo de VPN ou de e-mail no servidor real.

A requisição **Assunto fora da base — confirmar no GLPI** usa um tema candidato a não existir. Antes de usar o resultado como evidência de ausência, confira a base acessível ao usuário e ajuste a pergunta. O script valida o contrato, mas não exige `total = 0`, pois desconhecemos o conteúdo do servidor do grupo. Para esse cenário manual, o esperado é lista vazia somente após confirmar que a pergunta realmente está fora da base.

Execute também **Mensagem vazia — 422** e **Sem Bearer — 401**. O primeiro usa autenticação e envia `message` vazio; o segundo envia uma mensagem válida sem autenticação. Os scripts esperam os respectivos códigos e um campo `detail` explicando a falha.

## Interpretar falhas

| Código | Significado nesta integração |
| --- | --- |
| 401 | Bearer ausente ou autenticação rejeitada pelo GLPI. |
| 403 | O GLPI negou acesso aos artigos. |
| 422 | Entrada inválida, como pergunta vazia ou longa demais. |
| 429 | O GLPI limitou as chamadas. |
| 502 | Falha de comunicação, resposta incompatível ou limite de paginação excedido. |
| 504 | A consulta ao GLPI excedeu o tempo de espera. |

A implementação limita a consulta a 20 páginas de até 50 artigos. Se atingir o limite sem terminar a paginação, retorna erro em vez de apresentar uma base parcial como completa.

## Situação da validação

Os testes locais automatizados usam dados e respostas simuladas para verificar o comportamento do código. **A validação com o GLPI real do grupo e a execução da collection nesse ambiente ainda estão pendentes.** Em 22/10/2026, o endereço configurado `localhost:8080` recusou a conexão. Inicie o laboratório GLPI ou configure o endereço fornecido pelo grupo antes de executar a collection.

Para concluir a tarefa, execute os critérios acima com credenciais autorizadas e registre os resultados sem incluir senhas ou tokens.

Para rodar os testes automatizados, na pasta do projeto:

```powershell
& 'C:\Users\55799\Documents\Codex\2026-10-20\v\work\venv-glpi\Scripts\python.exe' -B -m unittest discover -s tests -v
```
