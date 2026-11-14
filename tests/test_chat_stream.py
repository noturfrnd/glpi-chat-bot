"""POST /api/v1/chat: streaming SSE com modelo simulado, sem LLM e sem GLPI real.

Rode com: python -B -m unittest tests.test_chat_stream -v
"""

import json
import unittest

import jwt
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from src.chat_memory import build_session_id
from src.chat_stream import STAND_IN_ANSWER, get_chat_runnable, stream_chat_events
from src.config.pydantic.request import PydanticRequestValidationMiddleware
from src.main import app


def parse_sse(texto: str) -> list[tuple[str, dict]]:
    """Converte o texto de um stream SSE em uma lista de (evento, dados)."""
    eventos = []
    for bloco in texto.strip().split("\n\n"):
        linhas = bloco.split("\n")
        nome = next(l[len("event: "):] for l in linhas if l.startswith("event: "))
        dados = next(l[len("data: "):] for l in linhas if l.startswith("data: "))
        eventos.append((nome, json.loads(dados)))
    return eventos


def token_jwt(**claims) -> str:
    return jwt.encode(claims, "chave-de-teste-com-32-caracteres-ok", algorithm="HS256")


class RunnableEspiao:
    """Imita o contrato de astream_events e registra como foi chamado."""

    def __init__(self, textos, *, falha_depois=False):
        self.textos = textos
        self.falha_depois = falha_depois
        self.chamadas = []

    async def astream_events(self, entrada, config=None, version=None):
        self.chamadas.append({"entrada": entrada, "config": config, "version": version})
        yield {"event": "on_chain_start", "data": {}}  # ruído: deve ser ignorado
        for texto in self.textos:
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content=texto)}}
        yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="")}}
        if self.falha_depois:
            raise RuntimeError("segredo-tecnico")


async def coletar(runnable, message="oi", session_id="s", conversation_id="c1"):
    return "".join([p async for p in stream_chat_events(runnable, message, session_id, conversation_id)])


class StreamChatEventsTests(unittest.IsolatedAsyncioTestCase):
    async def test_emite_tokens_em_ordem_e_termina_com_done(self):
        eventos = parse_sse(await coletar(RunnableEspiao(["Ol", "á", "!"])))
        self.assertEqual(
            eventos,
            [
                ("token", {"text": "Ol"}),
                ("token", {"text": "á"}),
                ("token", {"text": "!"}),
                ("done", {"conversation_id": "c1"}),
            ],
        )

    async def test_envia_a_pergunta_e_a_sessao_ao_runnable(self):
        espiao = RunnableEspiao(["x"])
        await coletar(espiao, message="Como configurar VPN?", session_id="sessao-1")
        chamada = espiao.chamadas[0]
        self.assertEqual(chamada["entrada"], {"input": "Como configurar VPN?"})
        self.assertEqual(chamada["config"], {"configurable": {"session_id": "sessao-1"}})
        self.assertEqual(chamada["version"], "v2")

    async def test_erro_no_meio_vira_evento_error_sem_vazar_detalhe(self):
        texto = await coletar(RunnableEspiao(["Ol"], falha_depois=True))
        nomes = [n for n, _ in parse_sse(texto)]
        self.assertEqual(nomes, ["token", "error"])
        self.assertNotIn("segredo-tecnico", texto)
        self.assertNotIn("event: done", texto)

    async def test_extrai_texto_de_chunks_em_blocos(self):
        class RunnableBlocos(RunnableEspiao):
            async def astream_events(self, entrada, config=None, version=None):
                bloco = [{"type": "text", "text": "Oi"}, {"type": "tool_use", "id": "t1"}]
                yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content=bloco)}}

        eventos = parse_sse(await coletar(RunnableBlocos([])))
        self.assertEqual(eventos[0], ("token", {"text": "Oi"}))

    async def test_modelo_simulado_envia_caractere_por_caractere(self):
        eventos = parse_sse(await coletar(get_chat_runnable()))
        tokens = [dados["text"] for nome, dados in eventos if nome == "token"]
        self.assertEqual("".join(tokens), STAND_IN_ANSWER)
        self.assertEqual(len(tokens), len(STAND_IN_ANSWER))


class ChatV1EndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)
        self.corpo = {"message": "Como configurar VPN?", "conversation_id": "conv-1"}

    def _post(self, corpo=None, *, token=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.post("/api/v1/chat", json=corpo or self.corpo, headers=headers)

    def test_stream_sse_com_cabecalhos_e_fim_done(self):
        resp = self._post(token=token_jwt(sub="42"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers["content-type"].startswith("text/event-stream"))
        self.assertEqual(resp.headers["cache-control"], "no-cache")
        eventos = parse_sse(resp.text)
        self.assertEqual(eventos[-1], ("done", {"conversation_id": "conv-1"}))
        texto = "".join(d["text"] for n, d in eventos if n == "token")
        self.assertEqual(texto, STAND_IN_ANSWER)

    def test_sem_token_retorna_401(self):
        self.assertEqual(self._post().status_code, 401)

    def test_jwt_sem_sub_retorna_401_e_nao_abre_stream(self):
        resp = self._post(token=token_jwt(outra="coisa"))
        self.assertEqual(resp.status_code, 401)
        self.assertNotIn("text/event-stream", resp.headers["content-type"])

    def test_sessao_vem_do_sub_do_jwt_e_do_conversation_id(self):
        espiao = RunnableEspiao(["ok"])
        app.dependency_overrides[get_chat_runnable] = lambda: espiao
        self._post(token=token_jwt(sub="42"))
        esperado = build_session_id({"sub": "42"}, "conv-1")
        self.assertEqual(espiao.chamadas[0]["config"], {"configurable": {"session_id": esperado}})

    def test_entrada_invalida_retorna_422_antes_do_stream(self):
        casos = [
            {"message": "   ", "conversation_id": "conv-1"},
            {"message": "oi"},
            {"message": "oi", "conversation_id": ""},
        ]
        for corpo in casos:
            with self.subTest(corpo=corpo):
                resp = self._post(corpo, token=token_jwt(sub="42"))
                self.assertEqual(resp.status_code, 422)
                self.assertNotIn("text/event-stream", resp.headers["content-type"])


class MiddlewareRepassaDesconexaoTests(unittest.IsolatedAsyncioTestCase):
    async def test_depois_do_corpo_repassa_o_receive_original(self):
        """Regressão: o StreamingResponse só termina se receive() devolver http.disconnect."""
        mensagens = [
            {"type": "http.request", "body": b'{"a": 1}', "more_body": False},
            {"type": "http.disconnect"},
        ]

        async def receive():
            return mensagens.pop(0)

        vistos = []

        async def app_falsa(scope, receive, send):
            vistos.append(await receive())
            vistos.append(await receive())

        async def send(_):
            return None

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/x",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
        }
        await PydanticRequestValidationMiddleware(app_falsa)(scope, receive, send)
        self.assertEqual([m["type"] for m in vistos], ["http.request", "http.disconnect"])


if __name__ == "__main__":
    unittest.main()
