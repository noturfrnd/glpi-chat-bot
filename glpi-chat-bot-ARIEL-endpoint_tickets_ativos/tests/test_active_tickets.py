import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import endpoint_tickets_ativos as ep
from endpoint_tickets_ativos import GLPIError, filter_active_tickets


def member(user_id, login, role):
    return {"role": role, "name": login, "display_name": login, "id": user_id, "type": "User"}


def ticket(ticket_id, status_id, team, **extra):
    return {
        "id": ticket_id,
        "name": f"Chamado {ticket_id}",
        "status": {"id": status_id, "name": f"status-{status_id}"},
        "team": team,
        **extra,
    }


ANA = (7, "ana.ribeiro")
BRUNO = (8, "bruno.lima")

TICKETS = [
    ticket(1, 1, [member(*ANA, "requester")]),                                # ativo, Ana abriu
    ticket(2, 2, [member(*BRUNO, "requester"), member(*ANA, "assigned")]),    # ativo, Ana atende
    ticket(3, 4, [member(*ANA, "requester")]),                                # pendente (ativo)
    ticket(4, 5, [member(*ANA, "requester")]),                                # solucionado
    ticket(5, 6, [member(*ANA, "requester")]),                                # fechado
    ticket(6, 1, [member(*BRUNO, "requester")]),                              # ativo, outro usuário
    ticket(7, 3, [member(*ANA, "requester")], is_deleted=True),               # na lixeira
    ticket(8, 1, [{"role": "assigned", "id": 7, "name": "Grupo", "type": "Group"}]),  # grupo id 7, não usuário
]


class FilterActiveTicketsTests(unittest.TestCase):
    def ids(self, user, role="any"):
        return [t["id"] for t in filter_active_tickets(TICKETS, user, role)]

    def test_returns_only_active_tickets_of_user_by_id(self):
        self.assertEqual(self.ids("7"), [1, 2, 3])

    def test_accepts_login_case_insensitive(self):
        self.assertEqual(self.ids("Ana.Ribeiro"), [1, 2, 3])

    def test_filters_by_role(self):
        self.assertEqual(self.ids("7", "requester"), [1, 3])
        self.assertEqual(self.ids("7", "assigned"), [2])

    def test_unknown_user_returns_empty(self):
        self.assertEqual(self.ids("999"), [])


class ActiveTicketsEndpointTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(ep.glpi, "all_tickets", return_value=TICKETS)
        self.all_tickets = patcher.start()
        self.addCleanup(patcher.stop)
        self.http = TestClient(ep.app)

    def test_returns_active_tickets(self):
        response = self.http.get("/users/ana.ribeiro/tickets/active")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual([t["id"] for t in body["tickets"]], [1, 2, 3])
        self.assertEqual(body["tickets"][2]["status_id"], 4)

    def test_item_has_link_and_people(self):
        item = self.http.get("/users/7/tickets/active").json()["tickets"][1]
        self.assertEqual(item["link"], f"{ep.GLPI_BASE_URL}/front/ticket.form.php?id=2")
        self.assertEqual(item["requesters"], ["bruno.lima"])
        self.assertEqual(item["assignees"], ["ana.ribeiro"])

    def test_role_query_param(self):
        body = self.http.get("/users/7/tickets/active", params={"role": "assigned"}).json()
        self.assertEqual([t["id"] for t in body["tickets"]], [2])

    def test_invalid_role_is_422(self):
        self.assertEqual(self.http.get("/users/7/tickets/active?role=x").status_code, 422)

    def test_glpi_error_is_502(self):
        self.all_tickets.side_effect = GLPIError(403, {"detail": "The High-Level API is disabled"})
        response = self.http.get("/users/7/tickets/active")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["glpi_status"], 403)

    def test_missing_credentials_is_500(self):
        self.all_tickets.side_effect = ValueError("Credenciais ausentes no .env: GLPI_CLIENT_ID")
        self.assertEqual(self.http.get("/users/7/tickets/active").status_code, 500)


class GLPIClientTests(unittest.TestCase):
    def test_all_tickets_pages_until_last_partial_page(self):
        client = ep.GLPIClient()
        pages = {0: [{"id": 1}, {"id": 2}], 2: [{"id": 3}, {"id": 4}], 4: [{"id": 5}]}
        with patch.object(ep, "PAGE_SIZE", 2), patch.object(client, "get", side_effect=lambda path, params: pages[params["start"]]) as get:
            result = client.all_tickets()
        self.assertEqual([t["id"] for t in result], [1, 2, 3, 4, 5])
        self.assertEqual(get.call_count, 3)

    def test_get_renews_token_on_401(self):
        client = ep.GLPIClient()
        client.access_token = "expirado"
        expired, ok = MagicMock(status_code=401), MagicMock(status_code=206)
        ok.json.return_value = []

        def fake_token():
            client.access_token = "novo"

        with patch.object(ep.requests, "get", side_effect=[expired, ok]) as http, patch.object(client, "_get_token", side_effect=fake_token):
            self.assertEqual(client.get("/api.php/v2/Assistance/Ticket"), [])
        self.assertEqual(http.call_args.kwargs["headers"]["Authorization"], "Bearer novo")

    def test_get_renews_token_rejected_after_glpi_restart(self):
        client = ep.GLPIClient()
        client.access_token = "de-antes-do-restart"
        rejected, ok = MagicMock(status_code=400), MagicMock(status_code=200)
        rejected.json.return_value = {"status": "ERROR_INVALID_PARAMETER", "title": "Invalid OAuth token"}
        ok.json.return_value = [{"id": 1}]

        def fake_token():
            client.access_token = "novo"

        with patch.object(ep.requests, "get", side_effect=[rejected, ok]), patch.object(client, "_get_token", side_effect=fake_token):
            self.assertEqual(client.get("/api.php/v2/Assistance/Ticket"), [{"id": 1}])

    def test_get_raises_on_error_status(self):
        client = ep.GLPIClient()
        client.access_token = "ok"
        forbidden = MagicMock(status_code=403)
        forbidden.json.return_value = {"detail": "The High-Level API is disabled"}
        with patch.object(ep.requests, "get", return_value=forbidden):
            with self.assertRaises(GLPIError) as ctx:
                client.get("/api.php/v2/Assistance/Ticket")
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
