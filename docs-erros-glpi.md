\# Tratamento global de erros



Toda resposta de erro da API segue o mesmo formato:



&#x20;   {"detail": "mensagem amigável", "codigo": "CODIGO\_DO\_ERRO"}



O erro técnico real nunca é mostrado ao usuário. Ele fica apenas no log

(logger `glpi\_chat\_bot`).



\## Erros devolvidos pelo GLPI



| Status do GLPI | Status devolvido | Código                      | Mensagem ao usuário                                            |

|----------------|------------------|-----------------------------|----------------------------------------------------------------|

| 401            | 401              | GLPI\_NAO\_AUTORIZADO         | Sua sessão expirou ou o token é inválido. Faça login novamente. |

| 400/401 (token)| 401              | GLPI\_CREDENCIAIS\_INVALIDAS  | Não foi possível autenticar no GLPI.                           |

| 403            | 403              | GLPI\_SEM\_PERMISSAO          | Você não tem permissão para realizar esta ação no GLPI.        |

| 404            | 404              | GLPI\_NAO\_ENCONTRADO         | Não encontramos o item solicitado no GLPI.                     |

| 400/422        | igual            | GLPI\_DADOS\_INVALIDOS        | O GLPI não aceitou os dados enviados.                          |

| 429            | 429              | GLPI\_MUITAS\_REQUISICOES     | O GLPI recebeu muitas requisições. Aguarde um instante.        |

| 5xx            | 502              | GLPI\_ERRO\_INTERNO           | O GLPI está com problemas no momento.                          |



\## Falhas de comunicação com o GLPI



| Situação                 | Status | Código                 |

|--------------------------|--------|------------------------|

| Timeout                  | 504    | GLPI\_TIMEOUT           |

| GLPI fora do ar          | 502    | GLPI\_INDISPONIVEL      |

| Outra falha de rede      | 502    | GLPI\_ERRO\_COMUNICACAO  |

| Credenciais no .env ausentes | 500 | GLPI\_NAO\_CONFIGURADO  |



\## Outros erros



| Situação                      | Status | Código        |

|-------------------------------|--------|---------------|

| Rota inexistente              | 404    | NAO\_ENCONTRADO |

| Erro inesperado (qualquer)    | 500    | ERRO\_INTERNO  |

| Dados da requisição inválidos | 422    | (formato próprio do Pydantic, mantido) |



\## Erros em SSE (chat)



Em SSE a conexão já está aberta, então o erro vai como evento no stream.

A função `sse\_error\_event()` em `src/errors.py` monta esse evento:



&#x20;   event: error

&#x20;   data: {"detail": "mensagem", "codigo": "CHATBOT\_ERRO"}



O `/api/chat` ainda retorna 501 (sem motor de conversa), então a função

está pronta para ser usada quando o streaming for implementado.

