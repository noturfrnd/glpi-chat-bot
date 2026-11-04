
import unittest
from unittest.mock import Mock

from src.glpi_client import GLPIClient


class TicketsByUserClientTests(unittest.TestCase):
    def test_returns_tickets_for_user(self):
        client = GLPIClient.__new__(GLPIClient)
        client.ticket_list = Mock(
            return_value={
                "status_code": 200,
                "data": [
                    {
                        "id": 13,
                        "name": "Conta expirada",
                        "team": [
                            {"id": 7, "role": "requester"}
                        ],
                    },
                    {
                        "id": 52,
                        "name": "Conta travada",
                        "team": [
                            {"id": 9, "role": "requester"}
                        ],
                    },
                ],
            }
        )

        resultado = client.tickets_by_user(user_id=7)

        self.assertEqual(resultado["status_code"], 200)
        self.assertEqual(resultado["user_id"], 7)
        self.assertEqual(resultado["total"], 1)
        self.assertEqual(resultado["data"][0]["id"], 13)

    def test_rejects_invalid_user_id(self):
        client = GLPIClient.__new__(GLPIClient)

        with self.assertRaises(ValueError):
            client.tickets_by_user(user_id=0)


if __name__ == "__main__":
    unittest.main()