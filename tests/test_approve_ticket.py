import os
import unittest
from unittest.mock import patch

import requests
from fastapi import HTTPException

from src.glpi_client import GLPIClient
from src.main import GLPIAuthContext, app, approve_ticket


class ApproveTicketTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"APP_ENV": "test", "DEV_BYPASS_API_VALIDATION": "false"})
        environment.start()
        self.addCleanup(environment.stop)
        client = GLPIClient(base_url="http://glpi.test")
        client.access_token = "token"
        self.context = GLPIAuthContext(client=client, user=None, jwt_claims=None)

    def test_routes_are_registered(self):
        paths = {route.path for route in app.routes}

        self.assertIn("/api/tickets/{ticket_id}/approve", paths)
        self.assertIn("/api/v1/tickets/{ticket_id}/approve", paths)

    def test_approve_sends_patch_with_closed_status(self):
        result = {"status_code": 200, "url": "", "params": None, "data": {"id": 5}}
        with patch.object(GLPIClient, "request", return_value=result) as request:
            response = approve_ticket(5, self.context)

        request.assert_called_once_with("PATCH", "/api.php/v2/Assistance/Ticket/5", json_body={"status": 6})
        self.assertEqual(response.status_code, 200)

    def test_approve_rejects_invalid_ticket_id(self):
        with self.assertRaises(HTTPException) as error:
            approve_ticket(0, self.context)

        self.assertEqual(error.exception.status_code, 422)

    def test_approve_keeps_glpi_error_status(self):
        result = {"status_code": 404, "url": "", "params": None, "data": {"status": "ERROR"}}
        with patch.object(GLPIClient, "request", return_value=result):
            response = approve_ticket(999, self.context)

        self.assertEqual(response.status_code, 404)

    def test_approve_returns_502_when_glpi_is_unreachable(self):
        with patch.object(GLPIClient, "request", side_effect=requests.ConnectionError):
            with self.assertRaises(HTTPException) as error:
                approve_ticket(5, self.context)

        self.assertEqual(error.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()