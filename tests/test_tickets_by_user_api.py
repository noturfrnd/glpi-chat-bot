
import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from src.main import GLPIAuthContext, tickets_by_user


class TicketsByUserAPITests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.context = GLPIAuthContext(
            client=self.client,
            user=None,
            jwt_claims=None,
        )

    def test_returns_tickets_for_user(self):
        self.client.tickets_by_user.return_value = {
            "status_code": 200,
            "user_id": 7,
            "total": 1,
            "data": [{"id": 13, "name": "Conta expirada"}],
        }

        response = tickets_by_user(
            user_id=7,
            limit=100,
            context=self.context,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.body,
            b'{"user_id":7,"total":1,"data":[{"id":13,"name":"Conta expirada"}]}',
        )
        self.client.tickets_by_user.assert_called_once_with(
            user_id=7,
            limit=100,
        )

    def test_rejects_invalid_user_id(self):
        with self.assertRaises(HTTPException) as error:
            tickets_by_user(
                user_id=0,
                limit=100,
                context=self.context,
            )

        self.assertEqual(error.exception.status_code, 422)
        self.client.tickets_by_user.assert_not_called()

    def test_rejects_invalid_limit(self):
        with self.assertRaises(HTTPException) as error:
            tickets_by_user(
                user_id=7,
                limit=201,
                context=self.context,
            )

        self.assertEqual(error.exception.status_code, 422)
        self.client.tickets_by_user.assert_not_called()


if __name__ == "__main__":
    unittest.main()