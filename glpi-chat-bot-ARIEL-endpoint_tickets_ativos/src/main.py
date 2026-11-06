import argparse
import json
from typing import Any, Dict

try:
    from domain_service import DomainService
    from glpi_client import GLPIClient, pretty_print
except ModuleNotFoundError:  # pragma: no cover - execução direta via python src/main.py
    from src.domain_service import DomainService
    from src.glpi_client import GLPIClient, pretty_print


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executa uma demonstração da API v2 do GLPI.")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Base URL do GLPI (ex.: http://localhost:8080)")
    parser.add_argument("--client-id", help="client_id do OAuth2")
    parser.add_argument("--client-secret", help="client_secret do OAuth2")
    parser.add_argument("--username", help="Usuário GLPI")
    parser.add_argument("--password", help="Senha do usuário GLPI")
    parser.add_argument("--scope", default="api", help="Escopo OAuth2")
    parser.add_argument("--write-demo", action="store_true", help="Executa também criação de ticket e comentário")
    return parser


def run_demo(client: GLPIClient, write_demo: bool = False) -> None:
    service = DomainService()

    print("Obtendo token OAuth2...")
    token_response = client.get_token()
    service.update_from_api_response("account", token_response)
    print(json.dumps(token_response, indent=2, ensure_ascii=False))

    me_response = client.me()
    service.update_from_api_response("users", me_response)
    pretty_print("Usuário autenticado", me_response)

    tickets_response = client.ticket_list(start=0, limit=5)
    service.update_from_api_response("tickets", tickets_response)
    pretty_print("Lista de chamados", tickets_response)

    articles_response = client.knowledgebase_articles(start=0, limit=5)
    service.update_from_api_response("articles", articles_response)
    pretty_print("Artigos da base de conhecimento", articles_response)

    categories_response = client.itil_categories(start=0, limit=5)
    service.update_from_api_response("categories", categories_response)
    pretty_print("Categorias de chamado", categories_response)

    users_response = client.users(start=0, limit=5)
    service.update_from_api_response("users", users_response)
    pretty_print("Usuários", users_response)

    print("\nCache salvo em data/glpi_cache.json")
    print(json.dumps(service.store.data, ensure_ascii=False, indent=2)[:800])

    if write_demo:
        ticket_result = client.create_ticket(
            "Ticket criado pela API Python",
            "<p>Este ticket foi gerado pela execução do cliente em Python.</p>",
        )
        pretty_print("Criação de chamado", ticket_result)

        ticket_id = None
        payload = ticket_result.get("data")
        if isinstance(payload, dict):
            ticket_id = payload.get("id") or payload.get("href")
        if ticket_id is None:
            print("Não foi possível localizar o ID do ticket criado.")
            return

        followup = client.add_followup(ticket_id, "Comentário adicionado pelo cliente Python.")
        pretty_print("Adicionar followup", followup)

        if isinstance(payload, dict):
            update = client.update_ticket(ticket_id, name="Ticket atualizado via API Python")
            pretty_print("Atualização do chamado", update)


def main() -> None:
    args = build_parser().parse_args()

    client = GLPIClient(
        base_url=args.base_url,
        client_id=args.client_id,
        client_secret=args.client_secret,
        username=args.username,
        password=args.password,
        scope=args.scope,
    )

    try:
        run_demo(client, write_demo=args.write_demo)
    except ValueError as exc:
        print(f"Erro de configuração: {exc}")
        print("Exemplo de uso:")
        print(
            "python src/main.py --base-url http://localhost:8080 "
            "--client-id <CLIENT_ID> --client-secret <CLIENT_SECRET> "
            "--username glpi --password glpi"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
