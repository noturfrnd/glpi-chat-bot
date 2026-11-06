import unittest
from unittest.mock import MagicMock, patch

from src.glpi_client import GLPIClient


class GLPIClientTests(unittest.TestCase):
    def test_ticket_list_all_pages_until_last_partial_page(self):
        client = GLPIClient(client_id="x", client_secret="x", username="x", password="x")
        pages = {0: [{"id": 1}, {"id": 2}], 2: [{"id": 3}, {"id": 4}], 4: [{"id": 5}]}
        with patch.object(client, "ticket_list", side_effect=lambda start, limit: {"status_code": 206, "data": pages[start]}) as ticket_list:
            result = client.ticket_list_all(page_size=2)
        self.assertEqual([t["id"] for t in result], [1, 2, 3, 4, 5])
        self.assertEqual(ticket_list.call_count, 3)

    def test_request_renews_token_on_401(self):
        client = GLPIClient(client_id="x", client_secret="x", username="x", password="x")
        client.access_token = "expirado"
        expired, ok = MagicMock(status_code=401, content=b""), MagicMock(status_code=200, content=b"[]")
        ok.json.return_value = []

        def fake_token():
            client.access_token = "novo"

        with patch("src.glpi_client.requests.request", side_effect=[expired, ok]) as http, patch.object(client, "get_token", side_effect=fake_token):
            result = client.request("GET", "/api.php/v2/Assistance/Ticket")
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(http.call_args.kwargs["headers"]["Authorization"], "Bearer novo")

    def test_request_renews_token_rejected_after_glpi_restart(self):
        client = GLPIClient(client_id="x", client_secret="x", username="x", password="x")
        client.access_token = "de-antes-do-restart"
        rejected, ok = MagicMock(status_code=400, content=b"{}"), MagicMock(status_code=200, content=b"[]")
        rejected.json.return_value = {"status": "ERROR_INVALID_PARAMETER", "title": "Invalid OAuth token"}
        ok.json.return_value = []

        def fake_token():
            client.access_token = "novo"

        with patch("src.glpi_client.requests.request", side_effect=[rejected, ok]), patch.object(client, "get_token", side_effect=fake_token):
            result = client.request("GET", "/api.php/v2/Assistance/Ticket")
        self.assertEqual(result["status_code"], 200)


if __name__ == "__main__":
    unittest.main()
