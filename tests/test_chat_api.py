"""Critérios da tarefa 3 exercitados pela aplicação ASGI, sem GLPI real."""

import asyncio
import json
import os
import unittest
from unittest.mock import patch

import requests

from src.main import app


class ArticleClientStub:
    def __init__(self, articles=None, *, status_code=200, error=None):
        self.articles = articles if articles is not None else []
        self.status_code = status_code
        self.error = error
        self.access_token = None
        self.calls = []

    def knowledgebase_articles(self, *, start, limit):
        self.calls.append((self.access_token, start, limit))
        if self.error is not None:
            raise self.error
        if self.status_code >= 400:
            return {
                "status_code": self.status_code,
                "data": {"detail": "private-upstream-detail"},
            }
        page = self.articles[start:start + limit]
        return {
            "status_code": 206 if start + limit < len(self.articles) else 200,
            "data": page,
        }


async def send_chat(payload=None, *, token="test-token", raw_body=None):
    body = raw_body if raw_body is not None else json.dumps(payload).encode("utf-8")
    messages = [{"type": "http.request", "body": body, "more_body": False}]
    sent = []

    async def receive():
        if messages:
            return messages.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    headers = [(b"content-type", b"application/json")]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/chat",
        "raw_path": b"/api/chat",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "server": ("testserver", 80),
        "client": ("testclient", 1),
        "state": {},
    }
    await app(scope, receive, send)
    status = next(item["status"] for item in sent if item["type"] == "http.response.start")
    response = b"".join(item.get("body", b"") for item in sent if item["type"] == "http.response.body")
    return status, json.loads(response)


class ChatAPITests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(
            os.environ, {"APP_ENV": "test", "DEV_BYPASS_API_VALIDATION": "false"}
        )
        environment.start()
        self.addCleanup(environment.stop)

    def call(self, client, payload=None, **kwargs):
        with patch("src.main._new_glpi_client", return_value=client):
            return asyncio.run(send_chat(payload, **kwargs))

    def test_natural_question_uses_bearer_and_returns_relevant_article(self):
        client = ArticleClientStub([
            {"id": 1, "name": "Configurar VPN Windows", "content": "<p>Configure a VPN no Windows.</p>"},
            {"id": 2, "name": "Configurar VPN macOS", "content": "<p>Configure a VPN no macOS.</p>"},
            {"id": 3, "name": "Assinatura de email", "content": "<p>Edite sua assinatura.</p>"},
        ])
        question = "  Oi, bom dia, estou tentando configurar a VPN no Windows e preciso de ajuda  "
        status, body = self.call(client, {"message": question}, token="user-a-token")

        self.assertEqual(status, 200)
        self.assertEqual(body["pergunta"], question.strip())
        self.assertIn("vpn", body["palavras_chave"])
        self.assertIn("windows", body["palavras_chave"])
        self.assertEqual(body["total"], 1)
        self.assertEqual([article["id"] for article in body["artigos"]], [1])
        self.assertEqual(body["artigos"][0]["conteudo"], "Configure a VPN no Windows.")
        self.assertEqual(client.calls, [("user-a-token", 0, 50)])

    def test_invalid_message_is_rejected_before_glpi_query(self):
        for payload in (
            {}, {"message": ""}, {"message": "   "}, {"message": "x" * 4001},
            {"message": 123}, {"message": None}, {"message": "VPN", "unexpected": True},
        ):
            with self.subTest(payload=str(payload)[:80]):
                client = ArticleClientStub()
                status, _ = self.call(client, payload)
                self.assertEqual(status, 422)
                self.assertEqual(client.calls, [])

    def test_malformed_json_is_rejected_before_glpi_query(self):
        client = ArticleClientStub()
        status, _ = self.call(client, raw_body=b'{"message":')
        self.assertEqual(status, 422)
        self.assertEqual(client.calls, [])

    def test_missing_bearer_is_rejected(self):
        client = ArticleClientStub()
        status, _ = self.call(client, {"message": "VPN"}, token=None)
        self.assertEqual(status, 401)
        self.assertEqual(client.calls, [])

    def test_glpi_auth_and_rate_limit_errors_are_preserved_without_raw_details(self):
        for upstream_status in (401, 403, 429):
            with self.subTest(status=upstream_status):
                client = ArticleClientStub(status_code=upstream_status)
                status, body = self.call(client, {"message": "VPN"})
                self.assertEqual(status, upstream_status)
                self.assertIn("detail", body)
                self.assertNotIn("private-upstream-detail", json.dumps(body))
                self.assertEqual(len(client.calls), 1)

    def test_network_failures_have_controlled_http_responses(self):
        for error, expected in (
            (requests.Timeout("private-upstream-detail"), 504),
            (requests.ConnectionError("private-upstream-detail"), 502),
        ):
            with self.subTest(error=type(error).__name__):
                status, body = self.call(ArticleClientStub(error=error), {"message": "VPN"})
                self.assertEqual(status, expected)
                self.assertNotIn("private-upstream-detail", json.dumps(body))

    def test_upstream_server_error_is_reported_as_bad_gateway(self):
        status, body = self.call(ArticleClientStub(status_code=500), {"message": "VPN"})
        self.assertEqual(status, 502)
        self.assertNotIn("private-upstream-detail", json.dumps(body))

    def test_malformed_article_is_reported_as_bad_gateway(self):
        for article in (
            {"id": 1},
            {"id": True, "name": "VPN", "content": "VPN"},
            {"id": 1, "name": "VPN", "content": {"unexpected": "object"}},
        ):
            with self.subTest(article=article):
                status, body = self.call(ArticleClientStub([article]), {"message": "VPN"})
                self.assertEqual(status, 502)
                self.assertIn("detail", body)

    def test_unknown_topic_returns_empty_articles(self):
        client = ArticleClientStub([
            {"id": 1, "name": "VPN Windows", "content": "Configurar VPN Windows"},
        ])
        status, body = self.call(client, {"message": "Como configurar telescópio no Windows?"})
        self.assertEqual(status, 200)
        self.assertEqual(body["artigos"], [])
        self.assertEqual(body["total"], 0)
        self.assertEqual(len(client.calls), 1)

    def test_generic_question_still_checks_glpi_permissions(self):
        client = ArticleClientStub(status_code=401)
        status, _ = self.call(client, {"message": "Olá"})
        self.assertEqual(status, 401)
        self.assertEqual(len(client.calls), 1)

    def test_search_includes_later_pages(self):
        articles = [
            {"id": index, "name": "Impressora", "content": "Instalar impressora"}
            for index in range(1, 51)
        ]
        articles.append({"id": 51, "name": "VPN Windows", "content": "Configurar VPN Windows"})
        client = ArticleClientStub(articles)
        status, body = self.call(client, {"message": "VPN Windows"})
        self.assertEqual(status, 200)
        self.assertEqual([article["id"] for article in body["artigos"]], [51])
        self.assertEqual(client.calls, [("test-token", 0, 50), ("test-token", 50, 50)])

    def test_requests_do_not_share_articles_between_users(self):
        first = ArticleClientStub([{"id": 1, "name": "VPN Windows", "content": "Configurar VPN"}])
        second = ArticleClientStub([])
        first_status, first_body = self.call(first, {"message": "VPN"}, token="user-a-token")
        second_status, second_body = self.call(second, {"message": "VPN"}, token="user-b-token")
        self.assertEqual((first_status, second_status), (200, 200))
        self.assertEqual([article["id"] for article in first_body["artigos"]], [1])
        self.assertEqual(second_body["artigos"], [])
        self.assertEqual(second.calls, [("user-b-token", 0, 50)])


if __name__ == "__main__":
    unittest.main()
