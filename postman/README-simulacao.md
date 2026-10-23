# Testar a tarefa 3 no Postman sem o GLPI

Este roteiro usa **artigos fictícios**, identificados com `[SIMULADO]`. Ele
permite conferir o recebimento da pergunta, as palavras-chave e os resultados
esperados da busca. **Não comprova o terceiro critério contra a API real do
GLPI.** A collection do grupo para esse teste real continua separada.

## 1. Iniciar o servidor de teste

No terminal PowerShell do VS Code, execute:

```powershell
Set-Location -LiteralPath 'C:\Users\55799\Documents\Codex\2026-10-20\v\work\glpi-chat-bot'
& 'C:\Users\55799\Documents\Codex\2026-10-20\v\work\venv-glpi\Scripts\python.exe' -B -m uvicorn tests.postman_demo:app --host 127.0.0.1 --port 8001
```

Espere aparecer `Uvicorn running on http://127.0.0.1:8001`. Mantenha esse
terminal aberto enquanto usa o Postman. Para encerrar o servidor, pressione
`Ctrl+C` nesse terminal.

Este é um processo de teste separado. Para usar o GLPI real depois, inicie
`src.main:app`, conforme o guia da tarefa 3.

## 2. Importar a collection

No Postman, clique em **Import** e selecione
`Tarefa3-SIMULACAO.postman_collection.json`.

O nome exibido será **SIMULAÇÃO LOCAL — Tarefa 3 — sem GLPI real**.
As variáveis já estão preenchidas:

| Variável | Valor de teste |
| --- | --- |
| `base_url` | `http://127.0.0.1:8001` |
| `access_token` | `somente-simulacao-tarefa3` |

Esse token é um marcador público de demonstração; não é uma credencial GLPI.
Não preencha senhas reais e não execute `Create Token` nesta simulação.
Evite selecionar um ambiente do Postman que tenha variáveis com esses mesmos
nomes, pois ele pode substituir os valores da collection.

## 3. Fazer a primeira requisição

Abra **Busca natural** e clique em **Send**. O corpo enviado é:

```json
{
  "message": "Oi, bom dia, estou tentando configurar a VPN no Windows e preciso de ajuda",
  "history": []
}
```

Confira:

- Status **200 OK**.
- `pergunta` contém o texto recebido.
- `palavras_chave` contém `configurar`, `vpn`, `windows` e `ajuda`.
- `artigos` contém somente o artigo fictício **9001 — [SIMULADO] Configurar VPN no Windows**.
- `total` é **1**.
- O cabeçalho de resposta `X-GLPI-Simulation` é `true`.

Os testes da requisição conferem o formato e esse resultado conhecido.

## 4. Executar os demais casos

Você pode usar **Send** em cada requisição ou **Run collection / Run** para
executar as cinco na ordem da collection.

| Requisição | Resultado esperado |
| --- | --- |
| Busca natural | 200; artigo fictício 9001, VPN Windows |
| Busca com e-mail | 200; palavra `email`; artigo fictício 9003 |
| Assunto inexistente na base simulada | 200; `artigos: []`; `total: 0` |
| Mensagem vazia | 422; erro de validação |
| Sem Bearer | 401; autenticação ausente |

**Resultado esperado do conjunto: cinco requisições e 23 verificações aprovadas.**

## Evidência e limite da validação

Em 22/10/2026, a collection foi executada via **Newman**, o executor de
collections Postman, contra o servidor local de simulação. As cinco
requisições e 23 verificações passaram, sem falhas. O aplicativo gráfico
Postman não foi operado: a automação de aplicativos não conseguiu iniciar.

O servidor usado nessa execução foi encerrado ao fim do teste. Inicie-o com
o comando do passo 1 para repetir no Postman.

| Critério de aceitação | Evidência disponível |
| --- | --- |
| Receber o texto da pergunta | Verificado pela rota HTTP e pelos campos retornados |
| Processar texto e identificar palavras-chave | Verificado com pergunta natural e normalização de e-mail |
| Retornar dados da API GLPI conforme as palavras-chave | Seleção testada com dados fictícios; integração real pendente |

Assim que o grupo fornecer o endereço do GLPI e as credenciais apropriadas,
use `GLPI-tarefa3.postman_collection.json` para testar a base real e concluir
o último critério.
