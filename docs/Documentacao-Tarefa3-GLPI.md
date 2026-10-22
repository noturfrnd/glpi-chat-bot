# Processamento de perguntas e busca de artigos no GLPI

GLPI Chat Bot • Squad 15 • Tarefa 3 • 22 de outubro de 2026

Implementamos o processamento de perguntas do chatbot e sua integração com a base de conhecimento do GLPI. A API recebe uma pergunta, identifica palavras-chave e retorna até três artigos relacionados ao assunto. Os três critérios de aceitação foram verificados nos cenários do laboratório, com autenticação real e conferência dos artigos retornados. Este documento descreve a contribuição e reúne material para o relatório final do projeto.

## Objetivo e escopo da contribuição

A tarefa escolhida foi “Função de processamento de perguntas”. Seu objetivo é receber o texto enviado ao chatbot, identificar palavras-chave e retornar dados da API GLPI relacionados a essas palavras. Reaproveitamos o trabalho anterior de busca de artigos e o integramos à versão atualizada do backend.

A estrutura FastAPI, o cliente GLPI, a emissão e renovação de tokens, os modelos de entrada e o middleware de validação já faziam parte da atualização do líder. Antes desta contribuição, POST /api/chat validava a entrada e retornava HTTP 501. A alteração implementou o processamento nessa rota, preservando as validações existentes e acrescentando os modelos de resposta, a consulta paginada e o tratamento de falhas da busca.

## Funcionamento da busca

1. A API recebe message, valida se o texto não está vazio e aplica o limite de 4.000 caracteres. O token é recebido no cabeçalho Authorization com o esquema Bearer.

2. O texto é normalizado quanto a maiúsculas, acentos e formas como e-mail/email e wi-fi/wifi. Saudações, palavras de ligação e alguns termos conversacionais são removidos; as palavras-chave são retornadas sem repetição.

3. O backend consulta as páginas de artigos acessíveis ao token do usuário no GLPI. As palavras-chave orientam uma filtragem local dos artigos recebidos.

4. A busca lexical usa pontuação BM25, favorece correspondências no título e diferencia plataformas indicadas na pergunta, como Windows e macOS. Resultados pouco relacionados ao tema são descartados.

5. A resposta reúne a pergunta, as palavras-chave, os artigos selecionados e o total. O HTML do conteúdo é convertido para texto, e cada artigo conserva seu ID e caminho de origem na API GLPI.

Cada pergunta consulta o GLPI com o token recebido. Não há cache compartilhado de artigos entre usuários. Nenhum modelo de linguagem é chamado nesta tarefa; o campo history é aceito e validado, mas não participa da busca.

## Interface da API

Endpoint: POST /api/chat. O corpo utiliza JSON e o cabeçalho Content-Type: application/json. Para autenticação, utiliza-se Authorization: Bearer <access_token>. O token é obtido previamente pelo fluxo Create Token da collection.

### Exemplo de entrada

```json
{
  "message": "Como configurar VPN no Windows?",
  "history": []
}
```

### Campos da resposta

| Campo | Descrição |
| --- | --- |
| pergunta | Texto recebido, com espaços externos removidos. |
| palavras_chave | Lista dos termos extraídos e normalizados. |
| artigos | Lista com até três resultados relevantes. |
| total | Quantidade de itens da lista artigos. |

Cada artigo contém id, titulo, conteudo, pontuacao, termos_encontrados e fonte_api. A pontuação expressa relevância lexical, sem representar uma probabilidade de acerto. Quando não há correspondência suficiente, a API retorna HTTP 200, artigos vazio e total igual a zero.

## Organização da implementação

| Arquivo ou grupo | Papel na entrega |
| --- | --- |
| src/main.py | Liga POST /api/chat ao processamento e converte falhas em respostas HTTP. |
| src/article_search.py | Extrai palavras-chave, normaliza texto, trata HTML e ordena artigos por relevância. |
| src/knowledge_service.py | Consulta as páginas do GLPI e coordena a seleção dos artigos. |
| src/config/pydantic/chat.py | Define os modelos de pergunta e resposta usados pela rota. |
| tests/ | Verifica entrada, extração, busca, integração da rota e erros com respostas controladas. |
| postman/ | Reúne as collections de integração real e simulação, com verificações automáticas. |

A consulta utiliza GET /api.php/v2/Knowledgebase/Article, paginada por start e limit. O endereço de fonte retornado identifica o artigo no GLPI, por exemplo /api.php/v2/Knowledgebase/Article/1.

Autenticação ausente retorna 401; entrada inválida, 422; timeout da consulta, 504. Os erros 401, 403 e 429 do GLPI são preservados, enquanto outras falhas externas são convertidas em 502 com mensagem controlada.

## Validação e critérios de aceitação

A validação de integração ocorreu em 22/10/2026 no glpi-agent-lab, iniciado com Docker. O ambiente executa a aplicação GLPI real com dados fictícios de treinamento. A consulta autenticada encontrou 40 artigos acessíveis. IDs, títulos, conteúdo textual e origem dos resultados foram comparados com respostas obtidas diretamente do GLPI usando o mesmo token.

| Critério de aceitação | Evidência obtida |
| --- | --- |
| Receber o texto da pergunta | A resposta reproduziu a pergunta enviada; entrada contendo apenas espaços foi rejeitada com 422. |
| Processar texto e identificar palavras-chave | A busca natural extraiu configurar, vpn, windows e ajuda. E-mail foi normalizado para email. |
| Retornar dados GLPI conforme as palavras-chave | As buscas selecionaram os artigos correspondentes da API real, com ID, título, conteúdo e origem conferidos. |

### Resultados observados no laboratório

| Cenário | HTTP | Resultado |
| --- | --- | --- |
| VPN no Windows | 200 | ID 1 — Configurar a VPN corporativa no Windows. |
| Assinatura de e-mail | 200 | ID 22 — Configurar assinatura padrão de e-mail. |
| Assunto telescópio | 200 | Nenhum artigo; total 0. Ausência do assunto conferida no corpus. |
| Mensagem vazia | 422 | Entrada rejeitada com explicação. |
| Sem Bearer | 401 | Requisição rejeitada por autenticação ausente. |
| VPN no macOS | 200 | ID 2 — Configurar a VPN corporativa no macOS. |

### Evidências automatizadas e manuais

A suíte local teve 55 testes de unidade e API aprovados, incluindo testes já existentes no projeto. A collection de simulação teve 23 verificações aprovadas. A collection real, executada pelo Newman, teve 16/16 verificações aprovadas em Create Token e nos cinco pedidos da tarefa 3. Um roteiro adicional realizou 55 verificações de integração, incluindo a comparação com o GLPI; essa contagem é independente da suíte local.

Também realizamos a repetição manual no Postman. A captura da busca natural comprova HTTP 200, 4/4 verificações aprovadas e o artigo ID 1. Os outros quatro cenários foram informados como concluídos pelo responsável pela execução; seus resultados individuais também estão registrados na execução automatizada.

## Como reproduzir os testes

1. Iniciar o Docker Desktop. Na pasta lab do glpi-agent-lab, executar docker compose up -d --build e confirmar que o GLPI abre em http://localhost:8080.

2. No projeto glpi-chat-bot, preparar o ambiente Python com requirements.txt. Configurar GLPI_BASE_URL=http://localhost:8080, APP_ENV=production e DEV_BYPASS_API_VALIDATION=false.

3. Iniciar a API com python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 e manter o terminal aberto durante os testes.

4. Importar postman/GLPI-tarefa3.postman_collection.json. Definir base_url=http://127.0.0.1:8000 e preencher client_id, client_secret, username e password com as credenciais autorizadas do laboratório.

5. Executar Create Token e confirmar HTTP 200. O script salva o token na collection. Em seguida, executar os cinco pedidos da tarefa 3 e conferir o corpo da resposta e Test Results.

A porta 8080 pertence ao GLPI; a porta 8000, ao backend do projeto. A porta 8001 pertence ao servidor separado de simulação. As collections versionadas mantêm vazios os campos de credenciais e tokens de acesso real.

## Limitações e estado da entrega

A busca depende da correspondência lexical e pode não reconhecer sinônimos ou formulações muito diferentes do texto dos artigos. A relevância deve ser reavaliada em outras bases e com outros perfis de acesso. O contexto de conversas e a geração de respostas por IA ficam fora do escopo desta tarefa.

A consulta é limitada a 20 páginas de até 50 artigos. Se não for possível confirmar o fim da paginação nesse limite, a API retorna erro para evitar uma resposta baseada em dados parciais. Cada busca também depende da disponibilidade do GLPI.

No laboratório, tokens malformados ou com assinatura inválida receberam HTTP 400 do GLPI, convertido em 502 pelo tratamento atual do backend. Esse comportamento foi documentado. O caso de Bearer ausente retorna 401.

A entrega está preparada na branch feat/tarefa3-processamento-perguntas, com revisão local e evidências registradas. A publicação no GitHub e a abertura do Pull Request ainda não foram confirmadas. A integração à main depende da revisão da equipe.

## Texto para incorporar ao relatório final

Na tarefa de processamento de perguntas, implementamos a integração do endpoint POST /api/chat com a base de conhecimento do GLPI, reaproveitando o módulo de busca desenvolvido anteriormente e a estrutura de API e validação fornecida pela equipe. A solução recebe a pergunta, identifica palavras-chave, consulta os artigos permitidos ao usuário e seleciona até três resultados por relevância lexical, preservando a identificação e a origem das informações.

A validação foi realizada no laboratório GLPI com 40 artigos e contemplou perguntas sobre VPN e assinatura de e-mail, ausência de resultados, entrada vazia e falta de autenticação. A collection real apresentou 16 verificações aprovadas pelo Newman, complementadas pela comparação dos resultados com a API e pela execução manual no Postman. Os cenários testados demonstraram o atendimento aos três critérios de aceitação da tarefa.
