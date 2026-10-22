# Tarefa 3 — processar perguntas e buscar artigos no GLPI

A tarefa recebe o texto de uma pergunta, identifica palavras-chave e retorna até três artigos relevantes da base de conhecimento do GLPI. O endpoint é `POST /api/chat`.

Esta cópia está na branch `feat/tarefa3-processamento-perguntas`, baseada na
atualização `cd2572a` da `main` e na contribuição anterior de busca de artigos.
O desenvolvimento está local; a branch ainda não foi publicada no GitHub.

**Sem acesso ao GLPI no momento?** Use a collection de simulação e o
[roteiro local](postman/README-simulacao.md). Essa opção usa artigos fictícios
para testar a entrada e a extração de palavras-chave sem iniciar o GLPI.
A integração com a aplicação GLPI do laboratório foi validada em 22/10/2026;
veja o [registro de validação](VALIDACAO-tarefa3.md).

## O que foi implementado

- Validação de `message`: texto não vazio, com até 4.000 caracteres.
- Extração local de palavras-chave, sem repetição e na ordem da pergunta; normalização de acentos, maiúsculas, `e-mail/email` e `wi-fi/wi fi/wifi`; remoção de saudações e termos conversacionais.
- Consulta paginada ao GLPI com o token Bearer recebido do usuário. A opção implementada consulta os artigos disponíveis para esse token e filtra o retorno localmente por relevância lexical.
- Retorno com pergunta, palavras-chave, artigos e quantidade. A ordenação considera título, conteúdo e plataforma indicada, como Windows ou macOS.
- Tratamento de autenticação ausente, entrada inválida e falhas na consulta ao GLPI.

Nenhum modelo de IA é chamado. `history` é aceito e validado, mas não participa da pesquisa nesta tarefa. A busca usa os dados obtidos na requisição atual, sem cache compartilhado entre usuários. A pontuação não representa uma probabilidade de acerto; sinônimos ou perguntas muito diferentes do texto da base podem não encontrar um artigo existente.

## Abrir e iniciar o projeto

O ambiente do grupo usa o GLPI local do repositório `glpi-agent-lab`.
Abra o Docker Desktop e aguarde o serviço iniciar. Em uma janela do PowerShell,
inicie o laboratório já baixado:

```powershell
Set-Location -LiteralPath 'C:\Users\55799\Documents\glpi-agent-lab-main\lab'
docker compose up -d --build
```

O arquivo `.env` desse laboratório já existe. Quando os contêineres estiverem
prontos, a tela de login do GLPI deve abrir em `http://localhost:8080`.
Esse ambiente executa a aplicação GLPI real com dados fictícios de treinamento.

Abra esta pasta no VS Code ou no terminal:

```text
C:\Users\55799\Documents\Codex\2026-10-20\v\work\glpi-chat-bot
```

Em outra janela do PowerShell, entre nela e configure o endereço do laboratório. `GLPI_BASE_URL` aponta para o servidor GLPI na porta 8080; `base_url`, usado no Postman, aponta para esta API local na porta 8000. A porta 8001 pertence à simulação separada.

```powershell
Set-Location -LiteralPath 'C:\Users\55799\Documents\Codex\2026-10-20\v\work\glpi-chat-bot'
$env:GLPI_BASE_URL = 'http://localhost:8080'
$env:APP_ENV = 'production'
$env:DEV_BYPASS_API_VALIDATION = 'false'
& 'C:\Users\55799\Documents\Codex\2026-10-20\v\work\venv-glpi\Scripts\python.exe' -B -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Mantenha esse terminal aberto e o Docker Desktop em execução. A documentação interativa ficará em `http://127.0.0.1:8000/docs`.

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

A resposta 200 tem esta estrutura. O exemplo vazio abaixo apenas ilustra o contrato; a busca de VPN retornou um artigo no laboratório, conforme o registro de validação:

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

A requisição **Assunto fora da base — confirmar no GLPI** usa um tema candidato a não existir. Antes de usar o resultado como evidência de ausência em outra base, confira os artigos acessíveis ao usuário e ajuste a pergunta. O script valida o contrato, mas não exige `total = 0`, para permitir uso em bases diferentes. No laboratório validado em 22/10/2026, a pergunta sobre telescópio retornou `artigos: []` e `total: 0`.

Execute também **Mensagem vazia — 422** e **Sem Bearer — 401**. O primeiro usa autenticação e envia `message` vazio; o segundo envia uma mensagem válida sem autenticação. Os scripts esperam os respectivos códigos e um campo `detail` explicando a falha.

## Interpretar falhas

| Código | Significado nesta integração |
| --- | --- |
| 401 | Bearer ausente ou resposta 401 do GLPI. |
| 403 | O GLPI negou acesso aos artigos. |
| 422 | Entrada inválida, como pergunta vazia ou longa demais. |
| 429 | O GLPI limitou as chamadas. |
| 502 | Falha de comunicação, resposta incompatível, limite de paginação excedido ou erro HTTP do GLPI não preservado pela rota. |
| 504 | A consulta ao GLPI excedeu o tempo de espera. |

A implementação limita a consulta a 20 páginas de até 50 artigos. Se atingir o limite sem terminar a paginação, retorna erro em vez de apresentar uma base parcial como completa.

Na verificação adicional do laboratório, tokens malformados ou com assinatura
inválida receberam HTTP 400 do GLPI. A regra atual de `/api/chat` converte esse
400 em 502; portanto, nem todo token inválido resulta em 401. Bearer ausente
retornou 401, como esperado pelo teste da collection.

## Situação da validação

**A integração com o GLPI do laboratório foi validada em 22/10/2026.**
O GLPI em `http://localhost:8080` disponibilizou 40 artigos, consultados pelo
backend `src.main:app` na porta 8000. Esses testes usaram a aplicação GLPI real
com os dados fictícios do laboratório.

O Newman executou **Create Token** e os cinco pedidos da tarefa 3 da collection
real, com **16 de 16 verificações aprovadas**. Essa execução foi automatizada
pelo Newman; a interface gráfica do Postman não foi usada para a validação real.

| Cenário | Resultado observado |
| --- | --- |
| Busca natural sobre VPN no Windows | 200; artigo ID 1, **Configurar a VPN corporativa no Windows**. |
| Busca com e-mail | 200; artigo ID 22, **Configurar assinatura padrão de e-mail**. |
| Assunto fora da base: telescópio | 200; `artigos: []`, `total: 0`. |
| Mensagem vazia | 422. |
| Sem Bearer | 401. |

Uma verificação de integração adicional comparou IDs, títulos e conteúdo dos
resultados com respostas obtidas diretamente do GLPI usando o mesmo token.
Também confirmou a busca de VPN no macOS com o artigo ID 2,
**Configurar a VPN corporativa no macOS**. O conteúdo foi comparado após a
remoção de HTML aplicada pelo backend.

Essas evidências cobrem o recebimento da pergunta, a extração de palavras-chave
e o retorno de artigos correspondentes da API do GLPI no laboratório.
Consulte o [registro de validação](VALIDACAO-tarefa3.md) para os detalhes.
A branch continua local e ainda não foi publicada no GitHub.

Os testes locais automatizados continuam usando dados e respostas simuladas
para verificar isoladamente o comportamento do código.

Para rodar os testes automatizados, na pasta do projeto:

```powershell
& 'C:\Users\55799\Documents\Codex\2026-10-20\v\work\venv-glpi\Scripts\python.exe' -B -m unittest discover -s tests -v
```
