import base64
import asyncio
import json
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from starlette.requests import Request

from src.config.pydantic import (
    ChatRequest,
    PasswordTokenRequest,
    PaginationParams,
    RefreshTokenRequest,
    TicketCreateRequest,
    TicketUpdateRequest,
)
from src.config.pydantic.chat import MAX_HISTORY_MESSAGES, MAX_MESSAGE_LENGTH
from src.config.pydantic.jwt import decode_glpi_jwt
from src.config.pydantic.request import APIRequestEnvelope, PydanticRequestValidationMiddleware
from src.main import app, get_glpi_auth_context, list_tickets, me


class APIValidationTests(unittest.TestCase):
    def setUp(self):
        self.bypass_environment = patch.dict(
            os.environ,
            {"APP_ENV": "test", "DEV_BYPASS_API_VALIDATION": "false"},
        )
        self.bypass_environment.start()
        self.addCleanup(self.bypass_environment.stop)

    def test_chat_request_accepts_valid_message_and_history(self):
        request = ChatRequest(
            message="Olá",
            history=[{"role": "user", "content": "Oi"}, {"role": "assistant", "content": "Olá"}],
        )

        self.assertEqual(request.message, "Olá")
        self.assertEqual(len(request.history), 2)

    def test_chat_request_rejects_oversized_message(self):
        with self.assertRaises(ValidationError):
            ChatRequest(message="x" * (MAX_MESSAGE_LENGTH + 1))

    def test_chat_request_rejects_invalid_or_oversized_history(self):
        with self.assertRaises(ValidationError):
            ChatRequest(message="Olá", history=[{"role": "system", "content": "instrução"}])

        history = [{"role": "user", "content": "x"}] * (MAX_HISTORY_MESSAGES + 1)
        with self.assertRaises(ValidationError):
            ChatRequest(message="Olá", history=history)

    def test_ticket_fields_and_pagination_are_bounded(self):
        with self.assertRaises(ValidationError):
            TicketCreateRequest(name=" ", content="Descrição")
        with self.assertRaises(ValidationError):
            PaginationParams(start=-1)
        with self.assertRaises(ValidationError):
            PaginationParams(limit=201)
        with self.assertRaises(ValidationError):
            TicketUpdateRequest()

    def test_dev_bypass_skips_custom_validations_only_in_development(self):
        with patch.dict(
            os.environ,
            {"APP_ENV": "development", "DEV_BYPASS_API_VALIDATION": "true"},
        ):
            request = ChatRequest(
                message="",
                history=[{"role": "system", "content": ""}] * (MAX_HISTORY_MESSAGES + 1),
            )
            pagination = PaginationParams(start=-1, limit=0)

        self.assertEqual(request.message, "")
        self.assertEqual(len(request.history), MAX_HISTORY_MESSAGES + 1)
        self.assertEqual(pagination.start, -1)

    def test_dev_bypass_is_ignored_outside_development(self):
        with patch.dict(
            os.environ,
            {"APP_ENV": "production", "DEV_BYPASS_API_VALIDATION": "true"},
        ):
            with self.assertRaises(ValidationError):
                ChatRequest(message="")

    def test_decode_glpi_jwt_returns_claims_without_treating_them_as_authentication(self):
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "user-1"}).encode()).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(b"signature").decode().rstrip("=")
        token = f"e30.{payload}.{signature}"

        self.assertEqual(decode_glpi_jwt(token), {"sub": "user-1"})
        self.assertIsNone(decode_glpi_jwt("not-a-jwt"))

    def test_bearer_interceptor_does_not_require_the_glpi_me_scope(self):
        class GLPIClientStub:
            def __init__(self):
                self.access_token = None

            def me(self):
                return {
                    "status_code": 403,
                    "data": {"detail": "You do not have the required scope(s) to access this endpoint."},
                }

        payload = base64.urlsafe_b64encode(json.dumps({"sub": "user-1"}).encode()).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(b"signature").decode().rstrip("=")
        token = f"e30.{payload}.{signature}"
        request = Request(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/api/tickets",
                "raw_path": b"/api/tickets",
                "query_string": b"",
                "headers": [],
                "server": ("testserver", 80),
                "client": ("testclient", 1),
            }
        )
        client = GLPIClientStub()

        with patch("src.main._new_glpi_client", return_value=client):
            context = get_glpi_auth_context(
                request,
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
            )

        self.assertEqual(context.client.access_token, token)
        self.assertEqual(context.jwt_claims, {"sub": "user-1"})
        self.assertEqual(me(context).status_code, 403)

        class TicketClientStub:
            def ticket_list(self, *, start, limit):
                return {"status_code": 206, "data": [{"id": 1}]}

        ticket_context = type(context)(client=TicketClientStub(), user=None, jwt_claims=context.jwt_claims)
        response = list_tickets(PaginationParams(start=0, limit=1), ticket_context)
        self.assertEqual(response.status_code, 206)

    def test_auth_interceptor_requires_bearer_unless_development_bypass_is_enabled(self):
        request = Request(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/api/me",
                "raw_path": b"/api/me",
                "query_string": b"",
                "headers": [],
                "server": ("testserver", 80),
                "client": ("testclient", 1),
            }
        )

        with self.assertRaises(HTTPException) as error:
            get_glpi_auth_context(request, None)
        self.assertEqual(error.exception.status_code, 401)

        with patch.dict(
            os.environ,
            {"APP_ENV": "development", "DEV_BYPASS_API_VALIDATION": "true"},
        ):
            context = get_glpi_auth_context(request, None)

        self.assertIsNone(context.user)
        self.assertIs(request.state.glpi_auth, context)

    def test_global_request_envelope_validates_every_api_request(self):
        self.assertTrue(
            any(
                middleware.cls is PydanticRequestValidationMiddleware
                for middleware in app.user_middleware
            )
        )
        request = APIRequestEnvelope.model_validate(
            {
                "method": "POST",
                "path": "/api/tickets",
                "query_params": [("start", "0")],
                "body_size": len(json.dumps({"name": "Chamado", "content": "Descrição"}).encode()),
                "body": {"name": "Chamado", "content": "Descrição"},
            }
        )
        self.assertEqual(request.method, "POST")
        self.assertIn("/api/auth/token", app.openapi()["paths"])
        self.assertIn("/api/auth/refresh", app.openapi()["paths"])

        with self.assertRaises(ValidationError):
            APIRequestEnvelope.model_validate(
                {
                    "method": "BREW",
                    "path": "/api/tickets",
                    "query_params": [],
                    "body_size": 0,
                    "body": None,
                }
            )
        with self.assertRaises(ValidationError):
            APIRequestEnvelope.model_validate(
                {
                    "method": "GET",
                    "path": "/api/tickets",
                    "query_params": [("q", "x" * 4_097)],
                    "body_size": 0,
                }
            )
        with self.assertRaises(ValidationError):
            APIRequestEnvelope.model_validate(
                {
                    "method": "GET",
                    "path": "/api/tickets",
                    "query_params": [],
                    "body_size": 1_000_001,
                }
            )

    def test_global_middleware_validates_and_replays_json_body(self):
        async def run_request():
            body = b'{"message":"Oi"}'
            messages = [{"type": "http.request", "body": body, "more_body": False}]
            sent = []
            received_by_app = []

            async def receive():
                if messages:
                    return messages.pop(0)
                return {"type": "http.request", "body": b"", "more_body": False}

            async def downstream(scope, downstream_receive, downstream_send):
                received_by_app.append(await downstream_receive())
                await downstream_send({"type": "http.response.start", "status": 200, "headers": []})
                await downstream_send({"type": "http.response.body", "body": b"ok"})

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "method": "POST",
                "path": "/api/chat",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
            }

            async def send(message):
                sent.append(message)

            middleware = PydanticRequestValidationMiddleware(downstream)
            await middleware(scope, receive, send)
            return received_by_app, sent

        received, sent = asyncio.run(run_request())
        self.assertEqual(json.loads(received[0]["body"]), {"message": "Oi"})
        self.assertEqual(sent[0]["status"], 200)

    def test_global_middleware_rejects_invalid_json_before_route_handling(self):
        async def run_request():
            messages = [{"type": "http.request", "body": b"{bad", "more_body": False}]
            sent = []

            async def receive():
                return messages.pop(0)

            async def downstream(scope, downstream_receive, downstream_send):
                self.fail("Invalid JSON reached the route.")

            async def send(message):
                sent.append(message)

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "method": "POST",
                "path": "/api/chat",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
            }
            await PydanticRequestValidationMiddleware(downstream)(scope, receive, send)
            return sent

        sent = asyncio.run(run_request())
        self.assertEqual(sent[0]["status"], 422)

    def test_fastapi_routes_apply_global_and_endpoint_pydantic_validation(self):
        async def send_request(method, path, payload=None):
            body = json.dumps(payload).encode() if payload is not None else b""
            messages = [{"type": "http.request", "body": body, "more_body": False}]
            sent = []

            async def receive():
                if messages:
                    return messages.pop(0)
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                sent.append(message)

            headers = [(b"content-type", b"application/json")] if payload is not None else []
            scope = {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "root_path": "",
                "headers": headers,
                "server": ("testserver", 80),
                "client": ("testclient", 1),
                "state": {},
            }
            await app(scope, receive, send)
            response_body = next(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
            return next(message["status"] for message in sent if message["type"] == "http.response.start"), response_body

        with patch.dict(
            os.environ,
            {"APP_ENV": "test", "DEV_BYPASS_API_VALIDATION": "false"},
        ):
            class ArticlesClientStub:
                def knowledgebase_articles(self, *, start, limit):
                    return {"status_code": 200, "data": []}

            from src.main import GLPIAuthContext
            app.dependency_overrides[get_glpi_auth_context] = lambda: GLPIAuthContext(
                client=ArticlesClientStub(), user=None, jwt_claims=None,
            )
            try:
                health_status, _ = asyncio.run(send_request("GET", "/health"))
                invalid_status, _ = asyncio.run(send_request("POST", "/api/chat", {"message": " "}))
                chat_status, _ = asyncio.run(send_request("POST", "/api/chat", {"message": "Olá"}))
            finally:
                app.dependency_overrides.pop(get_glpi_auth_context, None)

        self.assertEqual(health_status, 200)
        self.assertEqual(invalid_status, 422)
        self.assertEqual(chat_status, 200)


    def test_auth_token_requests_are_validated_by_pydantic(self):
        request = PasswordTokenRequest(
            client_id="client",
            client_secret="secret",
            username="glpi",
            password="password",
        )
        self.assertEqual(request.scope, "api")

        refresh = RefreshTokenRequest(
            client_id="client",
            client_secret="secret",
            refresh_token="refresh",
        )
        self.assertEqual(refresh.refresh_token, "refresh")

        with self.assertRaises(ValidationError):
            PasswordTokenRequest(
                client_id=" ",
                client_secret="secret",
                username="glpi",
                password="password",
            )


if __name__ == "__main__":
    unittest.main()
