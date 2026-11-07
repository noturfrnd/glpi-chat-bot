import unittest
from unittest.mock import patch

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.errors import (
    GLPIError,
    erro_glpi_por_status,
    register_error_handlers,
    sse_error_event,
)


def criar_app() -> FastAPI:
    """App mínimo, só para testar os handlers globais."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/timeout")
    def timeout():
        raise requests.Timeout()

    @app.get("/conexao")
    def conexao():
        raise requests.ConnectionError()

    @app.get("/rede")
    def rede():
        raise requests.RequestException()

    @app.get("/glpi-404")
    def glpi_404():
        raise erro_glpi_por_status(404)

    @app.get("/inesperado")
    def inesperado():
        raise RuntimeError("detalhe tecnico secreto")

    return app


class ErrorHandlingTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(criar_app(), raise_server_exceptions=False)

    def test_timeout_do_glpi(self):
        resposta = self.client.get("/timeout")
        self.assertEqual(resposta.status_code, 504)
        self.assertEqual(resposta.json()["codigo"], "GLPI_TIMEOUT")

    def test_glpi_fora_do_ar(self):
        resposta = self.client.get("/conexao")
        self.assertEqual(resposta.status_code, 502)
        self.assertEqual(resposta.json()["codigo"], "GLPI_INDISPONIVEL")

    def test_erro_de_rede_generico(self):
        resposta = self.client.get("/rede")
        self.assertEqual(resposta.status_code, 502)
        self.assertEqual(resposta.json()["codigo"], "GLPI_ERRO_COMUNICACAO")

    def test_erro_do_glpi_vira_mensagem_amigavel(self):
        resposta = self.client.get("/glpi-404")
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json()["codigo"], "GLPI_NAO_ENCONTRADO")

    def test_erro_inesperado_nao_vaza_detalhe_tecnico(self):
        resposta = self.client.get("/inesperado")
        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(resposta.json()["codigo"], "ERRO_INTERNO")
        self.assertNotIn("secreto", resposta.text)

    def test_rota_inexistente_tem_mensagem_amigavel(self):
        resposta = self.client.get("/nao-existe")
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json()["codigo"], "NAO_ENCONTRADO")


class GLPIStatusTests(unittest.TestCase):
    def test_mapeamento_de_status(self):
        esperado = {
            401: (401, "GLPI_NAO_AUTORIZADO"),
            403: (403, "GLPI_SEM_PERMISSAO"),
            404: (404, "GLPI_NAO_ENCONTRADO"),
            422: (422, "GLPI_DADOS_INVALIDOS"),
            429: (429, "GLPI_MUITAS_REQUISICOES"),
            500: (502, "GLPI_ERRO_INTERNO"),
            503: (502, "GLPI_ERRO_INTERNO"),
        }
        for status_glpi, (status, codigo) in esperado.items():
            with self.subTest(status_glpi=status_glpi):
                erro = erro_glpi_por_status(status_glpi)
                self.assertIsInstance(erro, GLPIError)
                self.assertEqual(erro.status_code, status)
                self.assertEqual(erro.codigo, codigo)

    def test_erro_de_token_vira_credenciais_invalidas(self):
        erro = erro_glpi_por_status(401, token=True)
        self.assertEqual(erro.codigo, "GLPI_CREDENCIAIS_INVALIDAS")


class SSETests(unittest.TestCase):
    def test_evento_de_erro_sse(self):
        evento = sse_error_event("Algo deu errado", "CHATBOT_ERRO")
        self.assertTrue(evento.startswith("event: error\n"))
        self.assertIn('"codigo": "CHATBOT_ERRO"', evento)
        self.assertTrue(evento.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()