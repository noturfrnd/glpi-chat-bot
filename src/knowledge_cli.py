"""Consulta da base de conhecimento e preparação de contexto, sem LLM."""
import argparse
import json
import sys
from pathlib import Path
from src.article_search import Busca
from src.answer_context import preparar


def fetch_articles(client, page_size=50):
    if page_size < 1:
        raise ValueError('Tamanho de página inválido.')
    articles, seen, start = [], set(), 0
    while True:
        response = client.knowledgebase_articles(start=start, limit=page_size)
        if not 200 <= response['status_code'] < 300:
            raise ValueError(f"Falha na consulta de artigos: HTTP {response['status_code']}")
        page = response['data']
        if not isinstance(page, list):
            raise ValueError('A API não retornou uma lista de artigos.')
        for article in page:
            if not isinstance(article, dict) or not isinstance(article.get('id'), int):
                raise ValueError('Artigo sem ID válido.')
            if article['id'] in seen:
                raise ValueError('Paginação repetiu um artigo; cache não atualizado.')
            seen.add(article['id'])
        articles.extend(page)
        start += len(page)
        if len(page) < page_size:
            return articles


def load_articles(path):
    payload = json.loads(path.read_text(encoding='utf-8-sig'))
    articles = payload.get('articles') if isinstance(payload, dict) else payload
    if not isinstance(articles, list):
        raise ValueError('Esperava uma lista JSON ou cache com campo articles.')
    for article in articles:
        if not isinstance(article, dict) or type(article.get('id')) is not int or not isinstance(article.get('name'), str):
            raise ValueError('Artigo precisa de id inteiro e name textual.')
        if article.get('content') is not None and not isinstance(article['content'], str):
            raise ValueError('Conteúdo de artigo inválido.')
    return articles


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pergunta')
    parser.add_argument('--cache', type=Path, default=Path('data/glpi_cache.json'))
    parser.add_argument('--atualizar', action='store_true', help='Consulta todas as páginas da API antes da busca.')
    parser.add_argument('--contexto', action='store_true', help='Exibe prévia JSON de mensagens para futura IA.')
    args = parser.parse_args()
    if not args.pergunta.strip():
        parser.error('Digite uma pergunta.')
    try:
        if args.atualizar:
            from src.glpi_client import GLPIClient
            from src.domain_service import DomainService
            articles = fetch_articles(GLPIClient())
            service = DomainService(cache_path=str(args.cache))
            service.update_from_api_response('articles', {'data': articles})
        articles = load_articles(args.cache)
        busca = Busca(articles)
        if args.contexto:
            print(json.dumps(preparar(busca, args.pergunta), ensure_ascii=False, indent=2))
        else:
            results = busca.pesquisar(args.pergunta)
            print(f'Base local: {len(articles)} artigos. Candidatos; nenhuma IA consultada.')
            if not results:
                print('Nenhum artigo encontrado por esta busca. Tente reformular.')
            for result in results:
                print(f"\nArtigo {result['id']}: {result['titulo']}\nFonte: {result['fonte_api']}")
                print(result['conteudo'])
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
