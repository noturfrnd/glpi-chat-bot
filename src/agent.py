"""Agente de suporte GLPI com ferramentas (tool calling) sobre qualquer chat model LangChain."""

from typing import Any

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.glpi_read_tools import criar_ferramentas_leitura
from src.glpi_write_tools import ContextoGLPI, criar_ferramentas_escrita
from src.prompts import montar_prompt_agente

MAX_ITERACOES = 5


def criar_ferramentas(context: ContextoGLPI) -> list[BaseTool]:
    """Todas as ferramentas do agente, presas ao contexto autenticado da requisição."""
    return [*criar_ferramentas_leitura(context.client), *criar_ferramentas_escrita(context)]


def criar_agente(
    llm: BaseChatModel,
    context: ContextoGLPI,
    *,
    max_iteracoes: int = MAX_ITERACOES,
) -> AgentExecutor:
    """Monta o agente para uma requisição.

    Invocar com ``{"pergunta": "...", "historico": [...]}`` (histórico opcional).
    O resultado traz ``output`` e ``intermediate_steps`` (lista de
    ``(AgentAction, observação)``), usados pelos testes de avaliação.
    """
    ferramentas = criar_ferramentas(context)
    prompt = montar_prompt_agente(context.jwt_claims)
    agente = create_tool_calling_agent(llm, ferramentas, prompt)
    return AgentExecutor(
        agent=agente,
        tools=ferramentas,
        max_iterations=max_iteracoes,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
    )


def responder(llm: BaseChatModel, context: ContextoGLPI, pergunta: str, **extra: Any) -> dict[str, Any]:
    """Atalho: cria o agente e responde a uma pergunta."""
    return criar_agente(llm, context).invoke({"pergunta": pergunta, **extra})
