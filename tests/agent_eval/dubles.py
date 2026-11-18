"""Dublês para avaliar o agente sem GLPI real: cliente stub e modelos de chat falsos."""

import json
import os
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from src.main import GLPIAuthContext

USUARIO_ID = 7

TECNICO = {"role": "assigned", "id": 42, "name": "carlos.souza", "display_name": "Souza Carlos", "type": "User"}
SOLICITANTE = {"role": "requester", "id": USUARIO_ID, "name": "ana.ribeiro", "display_name": "Ribeiro Ana", "type": "User"}

CHAMADOS: dict[int, dict[str, Any]] = {
    123: {"name": "Computador não liga", "status": {"id": 2, "name": "Em atendimento (atribuído)"}},
    4567: {"name": "Troca de mouse", "status": {"id": 5, "name": "Solucionado"}, "date_solve": "2026-11-10 14:00:00"},
    89: {"name": "Acesso ao sistema financeiro", "status": {"id": 4, "name": "Pendente"}},
    321: {"name": "Monitor piscando", "status": {"id": 2, "name": "Em atendimento (atribuído)"}},
    55: {"name": "Lentidão no computador", "status": {"id": 2, "name": "Em atendimento (atribuído)"}},
}

ARTIGOS: list[dict[str, Any]] = [
    {"id": 1, "name": "Como redefinir a senha de rede",
     "content": "<p>Acesse o portal de autoatendimento e clique em <b>Esqueci minha senha</b>.</p>"},
    {"id": 2, "name": "Configurar VPN corporativa",
     "content": "<p>Instale o cliente VPN e importe o perfil enviado pela TI.</p>"},
    {"id": 3, "name": "Impressora não imprime",
     "content": "<p>Verifique se a impressora está ligada e limpe a fila de impressão.</p>"},
    {"id": 4, "name": "E-mail corporativo no celular",
     "content": "<p>Instale o aplicativo Outlook e entre com seu e-mail corporativo.</p>"},
]


class GLPIClientStub:
    """Responde como o GLPI e registra todas as chamadas recebidas."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def me(self) -> dict[str, Any]:
        self.calls.append(("me",))
        return {"status_code": 200, "data": {"id": USUARIO_ID}}

    def ticket_detail(self, ticket_id: int) -> dict[str, Any]:
        self.calls.append(("ticket_detail", ticket_id))
        base = CHAMADOS.get(ticket_id)
        if base is None:
            return {"status_code": 404, "data": {"detail": "not found"}}
        return {
            "status_code": 200,
            "data": {"id": ticket_id, "date": "2026-11-01 09:00:00", "team": [SOLICITANTE, TECNICO], **base},
        }

    def knowledgebase_articles(self, start: int = 0, limit: int = 50) -> dict[str, Any]:
        self.calls.append(("knowledgebase_articles", start, limit))
        return {"status_code": 200, "data": ARTIGOS[start:start + limit]}

    def add_followup(self, ticket_id: int, content: str) -> dict[str, Any]:
        self.calls.append(("add_followup", ticket_id, content))
        return {"status_code": 201, "data": {"id": 1}}

    def approve_ticket(self, ticket_id: int) -> dict[str, Any]:
        self.calls.append(("approve_ticket", ticket_id))
        return {"status_code": 200, "data": {}}


def contexto_teste(client: GLPIClientStub) -> GLPIAuthContext:
    claims = {"sub": str(USUARIO_ID), "name": "Ana Ribeiro", "email": "ana@example.com"}
    return GLPIAuthContext(client=client, user=None, jwt_claims=claims)


def _ultima_pergunta(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


class _ModeloComFerramentas(BaseChatModel):
    """Base para modelos falsos que aceitam ``bind_tools`` e registram as ferramentas vistas."""

    ferramentas_vinculadas: list[str] = Field(default_factory=list)

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "_ModeloComFerramentas":
        self.ferramentas_vinculadas = [getattr(t, "name", None) or t["function"]["name"] for t in tools]
        return self

    def _resultado(self, message: AIMessage) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=message)])


class ModeloRoteirizado(_ModeloComFerramentas):
    """Modelo determinístico do modo offline.

    Na 1ª rodada pede as chamadas de ferramenta do roteiro da pergunta; depois que
    recebe as observações, responde citando exatamente o que a ferramenta devolveu.
    Valida a fiação (nomes, schemas, execução, laço do agente e avaliador), não a
    decisão do LLM: para isso use o modo ``llm`` (ver README da suíte).
    """

    roteiro: dict[str, list[dict[str, Any]]]
    pedido_de_numero: str = "Para consultar, por favor informe o número do chamado."

    @property
    def _llm_type(self) -> str:
        return "roteirizado"

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        observacoes = [m for m in messages if isinstance(m, ToolMessage)]
        if observacoes:
            texto = "Segundo o GLPI: " + " | ".join(str(m.content) for m in observacoes)
            return self._resultado(AIMessage(content=texto))

        chamadas = self.roteiro.get(_ultima_pergunta(messages), [])
        if not chamadas:
            return self._resultado(AIMessage(content=self.pedido_de_numero))
        tool_calls = [
            {"name": c["name"], "args": c["args"], "id": f"call_{i}", "type": "tool_call"}
            for i, c in enumerate(chamadas)
        ]
        return self._resultado(AIMessage(content="", tool_calls=tool_calls))


class ModeloInventaResposta(_ModeloComFerramentas):
    """Modelo "alucinado": responde direto, sem chamar nenhuma ferramenta."""

    resposta: str = "O chamado 123 já foi resolvido e fechado ontem."

    @property
    def _llm_type(self) -> str:
        return "inventa-resposta"

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        return self._resultado(AIMessage(content=self.resposta))


def modelo_real() -> BaseChatModel | None:
    """Modelo real para o modo ``llm``, configurado por variável de ambiente.

    ``AGENT_EVAL_MODEL`` no formato do ``init_chat_model`` (ex.: ``openai:gpt-4.1-mini``,
    ``anthropic:claude-sonnet-5-5``, ``ollama:llama3.1``); o pacote do provedor
    (``langchain-openai``, ``langchain-anthropic``...) e a chave de API precisam estar
    instalados/configurados. ``AGENT_EVAL_TEMPERATURE`` (padrão ``0``; vazio = não envia).
    """
    nome = os.getenv("AGENT_EVAL_MODEL", "").strip()
    if not nome:
        return None
    from langchain_classic.chat_models import init_chat_model

    kwargs: dict[str, Any] = {}
    temperatura = os.getenv("AGENT_EVAL_TEMPERATURE", "0").strip()
    if temperatura:
        kwargs["temperature"] = float(temperatura)
    return init_chat_model(nome, **kwargs)


def resumo_trajetoria(steps: Sequence[tuple[Any, str]]) -> str:
    return json.dumps(
        [{"ferramenta": a.tool, "args": a.tool_input, "observacao": str(o)[:200]} for a, o in steps],
        ensure_ascii=False,
    )
