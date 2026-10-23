"""Processamento de perguntas com artigos obtidos do GLPI nesta requisição."""
from typing import Any, Protocol

from src.article_search import Busca, extrair_palavras_chave


class ArticlesClient(Protocol):
    def knowledgebase_articles(self, start: int, limit: int) -> dict[str, Any]: ...


class ArticlesFetchError(ValueError):
    """Falha remota ou resposta incompatível; não expõe o corpo do GLPI."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def fetch_articles(
    client: ArticlesClient, page_size: int = 50, *, max_pages: int = 20,
) -> list[dict[str, Any]]:
    if type(page_size) is not int or not 1 <= page_size <= 200:
        raise ValueError('Tamanho de página deve estar entre 1 e 200.')
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError('O limite de páginas deve ser positivo.')
    articles: list[dict[str, Any]] = []
    seen: set[int] = set()
    start = 0
    for _ in range(max_pages):
        response = client.knowledgebase_articles(start=start, limit=page_size)
        if not isinstance(response, dict) or type(response.get('status_code')) is not int:
            raise ArticlesFetchError('O GLPI não retornou um status HTTP válido.')
        status_code = response['status_code']
        if not 200 <= status_code < 300:
            raise ArticlesFetchError('Não foi possível consultar os artigos no GLPI.', status_code)
        page = response.get('data')
        if not isinstance(page, list) or len(page) > page_size:
            raise ArticlesFetchError('O GLPI retornou uma página de artigos inválida.')
        for article in page:
            if (
                not isinstance(article, dict)
                or type(article.get('id')) is not int
                or article['id'] < 1
                or not isinstance(article.get('name'), str)
                or not article['name'].strip()
                or (article.get('content') is not None and not isinstance(article['content'], str))
            ):
                raise ArticlesFetchError('O GLPI retornou um artigo inválido.')
            if article['id'] in seen:
                raise ArticlesFetchError('O GLPI repetiu um artigo durante a paginação.')
            seen.add(article['id'])
        articles.extend(page)
        start += len(page)
        if len(page) < page_size:
            return articles
    # Não apresenta uma busca parcial como se tivesse consultado a base inteira.
    raise ArticlesFetchError('A consulta excedeu o limite de páginas de artigos.')


def processar_pergunta(pergunta: str, client: ArticlesClient) -> dict[str, Any]:
    """Extrai termos e retorna até três artigos relevantes, sem cache ou LLM.

    Usa o cliente autenticado da requisição. Mesmo perguntas genéricas passam
    pela API, que valida o token e as permissões de acesso à base de conhecimento.
    A filtragem lexical ocorre localmente sobre o retorno paginado do GLPI.
    """
    palavras_chave = extrair_palavras_chave(pergunta)
    artigos = fetch_articles(client)
    resultados = Busca(artigos).pesquisar(pergunta)
    return {
        'pergunta': pergunta.strip(),
        'palavras_chave': palavras_chave,
        'artigos': resultados,
        'total': len(resultados),
    }
