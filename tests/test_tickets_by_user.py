
import unittest
from unittest.mock import patch

from src.glpi_client import GLPIClient


class TestTicketsByUser(unittest.TestCase):

    def setUp(self):
        self.client = GLPIClient()

    # TESTE 1: Filtragem de tickets por usuario
    @patch.object(GLPIClient, "ticket_list")
    def test_filtra_tickets_do_usuario(self, mock_list):
        mock_list.return_value = {
            "status_code": 200,
            "data": [
                {
                    "id": 1,
                    "team": [{"id": 7, "role": "requester"}]
                },
                {
                    "id": 2,
                    "team": [{"id": 8, "role": "requester"}]
                },
                {
                    "id": 3,
                    "team": [{"id": 7, "role": "requester"}]
                }
            ]
        }

        resultado = self.client.tickets_by_user(user_id=7)

        self.assertEqual(resultado["total"], 2)
        self.assertEqual(
            [ticket["id"] for ticket in resultado["data"]],
            [1, 3]
        )

    # TESTE 2: Consulta com paginacao
    @patch.object(GLPIClient, "ticket_list")
    def test_paginacao(self, mock_list):
        mock_list.side_effect = [
            {
                "status_code": 206,
                "data": [
                    {"id": 1, "team": [{"id": 7, "role": "requester"}]},
                    {"id": 2, "team": [{"id": 8, "role": "requester"}]}
                ]
            },
            {
                "status_code": 200,
                "data": [
                    {"id": 3, "team": [{"id": 7, "role": "requester"}]}
                ]
            }
        ]

        resultado = self.client.tickets_by_user(
            user_id=7,
            limit=2
        )

        self.assertEqual(resultado["total"], 2)
        self.assertEqual(
            [ticket["id"] for ticket in resultado["data"]],
            [1, 3]
        )
        self.assertEqual(mock_list.call_count, 2)

    # TESTE 3: ID de usuario invalido
    def test_usuario_invalido(self):
        with self.assertRaises(ValueError):
            self.client.tickets_by_user(user_id=-1)


if __name__ == "__main__":
    unittest.main()
