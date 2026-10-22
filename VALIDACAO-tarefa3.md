# Validação da tarefa 3 com o GLPI do laboratório

Validação concluída em **22/10/2026, às 14:47, UTC−03:00**, sobre a implementação
do commit `e053674`, na branch local `feat/tarefa3-processamento-perguntas`.

Os três critérios de aceitação foram exercitados com a aplicação GLPI real do
`glpi-agent-lab`. O laboratório contém dados fictícios. Esta execução não usou
o servidor de simulação `tests.postman_demo` nem seus artigos de IDs 9001–9004.

## Ambiente e método

- GLPI do laboratório: `http://127.0.0.1:8080`.
- Backend: `src.main:app`, em `http://127.0.0.1:8000`.
- Validação normal habilitada: `APP_ENV=production` e `DEV_BYPASS_API_VALIDATION=false`.
- Autenticação realizada por `POST /api/auth/token`, com resposta 200 e emissão de token pelo GLPI.
- Consulta direta à API `/api.php/v2/Knowledgebase/Article`, com o mesmo token usado no chat: **40 artigos acessíveis**.
- IDs, títulos, conteúdo textual e caminhos de origem dos resultados do chat foram comparados com a consulta direta ao GLPI. Na comparação do conteúdo foram desconsideradas as tags HTML e diferenças de espaços e quebras de linha.

Os testes da collection foram executados pelo **Newman**, executor das collections
do Postman. Essa evidência não representa uma execução manual na interface gráfica
do Postman. O servidor temporário do backend foi encerrado ao final da validação.

## Critérios de aceitação

| Critério | Evidência observada | Resultado |
| --- | --- | --- |
| Receber o texto da pergunta | `POST /api/chat` recebeu `message`; `pergunta` correspondeu ao texto enviado, com espaços externos removidos. | Aprovado |
| Processar texto e identificar palavras-chave | A busca natural produziu `configurar`, `vpn`, `windows`, `ajuda`; a busca de assinatura reconheceu `assinatura` e normalizou `e-mail` para `email`. | Aprovado |
| Retornar dados da API GLPI conforme as palavras-chave | As buscas retornaram os artigos de IDs **1** e **22** existentes no GLPI. ID, título, conteúdo e `fonte_api` foram conferidos contra a API do laboratório. | Aprovado |

## Cenários executados

| Cenário | HTTP do backend | Resultado |
| --- | --- | --- |
| “Oi, bom dia, estou tentando configurar a VPN no Windows e preciso de ajuda” | 200 | ID **1** — **Configurar a VPN corporativa no Windows**; `total: 1`. |
| “Como configurar assinatura de e-mail?” | 200 | ID **22** — **Configurar assinatura padrão de e-mail**; `total: 1`. |
| “Como configurar telescópio no Windows?” | 200 | `artigos: []`, `total: 0`; a ausência desse assunto foi conferida nos 40 artigos acessíveis. |
| Mensagem contendo apenas espaços | 422 | Entrada rejeitada com explicação em `detail`. |
| Pergunta válida sem Bearer | 401 | Autenticação ausente rejeitada com explicação em `detail`. |
| “Como configurar VPN no macOS?” | 200 | ID **2** — **Configurar a VPN corporativa no macOS**; não retornou o artigo de Windows. |

A busca de Windows também não retornou o artigo de macOS. O campo `total`
correspondeu ao tamanho de `artigos`, com no máximo três resultados.

Os conteúdos conferidos incluem as instruções de VPN pelo menu
“Configurações → Rede e Internet → VPN”, com tipo IKEv2, e o procedimento de
assinatura de e-mail usando `https://assinatura.exemplo.local`, endereço fictício
que faz parte do corpus do laboratório.

## Resultado da collection

Foram executados **Create Token** e os **cinco pedidos da tarefa 3** da collection
`postman/GLPI-tarefa3.postman_collection.json`: **16/16 verificações aprovadas**,
sem falhas. Os pedidos de renovação de token, perfil e listagem de chamados não
fizeram parte desta execução, pois pertencem a outros fluxos.

O roteiro adicional fez **55 verificações**, incluindo as comparações dos artigos
com o GLPI e o tratamento das entradas. Todas passaram. Esses números se referem
à integração executada nesta data; não são a contagem da suíte de testes unitários.

## Comportamento adicional observado

O GLPI deste laboratório respondeu **400** ao receber um token malformado; uma
consulta direta com assinatura de token inválida também respondeu 400. A regra
existente de `/api/chat` preserva 401, 403 e 429 do GLPI e converte os outros erros
externos para **502**. Por isso, o cenário adicional de token malformado retornou
502 com mensagem genérica e sem artigos. Esse comportamento foi registrado;
não foi alterado nesta validação. Bearer ausente continua retornando **401**.

## Reproduzir e entregar

Use as instruções de [README-tarefa3.md](README-tarefa3.md) para iniciar o backend
e executar a collection contra o laboratório. Confirme os artigos acessíveis ao
usuário utilizado, pois outra base ou outro perfil pode produzir resultados distintos.

A branch permanece local. Esta validação não publicou commits, abriu Pull Request
nem alterou a `main`. O material está pronto para revisão e publicação da branch.
Credenciais e tokens não fazem parte deste relatório nem da collection versionada.
