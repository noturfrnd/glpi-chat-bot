# Busca de artigos — Sprint 1 em desenvolvimento

A busca reutiliza o cliente GLPIClient e o cache DomainService do projeto. Não chama uma IA e não modifica registros no GLPI.

Na raiz do repositório, com as dependências de requirements.txt instaladas e as variáveis GLPI configuradas conforme .env.example:

```powershell
python -m src.knowledge_cli "Como configurar VPN no Windows?" --atualizar
python -m src.knowledge_cli "Como configurar VPN no Windows?"
python -m src.knowledge_cli "Como configurar VPN no Windows?" --contexto
python -B -m unittest discover -s tests -v
```

`--atualizar` consulta todas as páginas de artigos antes de substituir o domínio articles no cache. Os outros domínios são preservados. Sem essa opção, a busca usa apenas o cache existente: o demo original carrega só cinco artigos, portanto atualize antes de avaliar a busca completa.

`--cache caminho.json` também aceita uma lista de artigos exportada pela Sprint 0, para teste offline. O padrão é data/glpi_cache.json. O comando informa quantos artigos estão sendo pesquisados.

A recuperação converte HTML em texto, normaliza acentos e usa BM25 com maior peso no título. Retorna até três candidatos. Uma regra separa títulos específicos de Windows/macOS quando a pergunta indica a plataforma. Pontuações não representam certeza: resultados secundários podem ser irrelevantes e perguntas fora do domínio podem coincidir lexicalmente.

`--contexto` prepara mensagens com regras e documentos separados. Não produz uma resposta real. A validação de resposta em answer_context.py verifica formato e IDs, mas não prova que afirmações são sustentadas pelos artigos e não garante resistência a instruções maliciosas em documentos.

Validação realizada: sete testes passaram, incluindo o teste original de cache, paginação HTTP 200/206, repetição de páginas, falha HTTP, plataformas e referências inválidas. A integração offline foi exercitada com os 40 artigos do laboratório coletados anteriormente. A atualização contra API ao vivo e respostas de um LLM ainda precisam ser verificadas no ambiente do grupo.

Próximos passos: escolher provedor, ligar a geração à validação, avaliar perguntas de referência e recusa por falta de informação. Esta contribuição não conclui a Sprint 1.


## Melhoria da seleção

A busca separa verbos genéricos e plataforma dos termos usados para identificar o assunto. Exige correspondência com pelo menos 60% desses termos, favorece o assunto no título e conserva apenas candidatos com pontuação de pelo menos 65% da melhor. Pode retornar menos de três artigos. Os limites são heurísticos, não probabilidades; perguntas longas com palavras desconhecidas podem perder resultados relevantes.

Verificação atual: 13 testes automatizados passaram e oito consultas foram conferidas sobre os 40 artigos reais coletados. VPN Windows retorna só artigo 1; VPN macOS, só 2; VPN sem plataforma conserva 1 e 2; lentidão retorna 8; impressora USB retorna 6; assinatura retorna 22. Perguntas sobre bolo e telescópio não retornaram artigos. Isso não garante abstinência correta para toda pergunta fora da base.
