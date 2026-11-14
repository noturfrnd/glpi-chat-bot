"""Streaming SSE do chat: converte os eventos de um Runnable do LangChain em eventos SSE.

Eventos enviados ao cliente (nomes provisórios, a confirmar com o front):
    token  -> {"text": "<pedaço da resposta>"}
    done   -> {"conversation_id": "<id>"}   (fim normal)
    error  -> {"detail": "...", "codigo": "..."}   (fim com falha)

Hoje o "cérebro" é um modelo simulado. Quando o AgentExecutor existir, basta
`get_chat_runnable` devolvê-lo: o restante deste módulo não muda.
"""

import json
from typing import Any, AsyncIterator

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.errors import MSG_ERRO_INESPERADO, logger, sse_error_event

STAND_IN_ANSWER = "Esta é uma resposta simulada. O agente real ainda não foi conectado."


def get_chat_runnable() -> Runnable:
    """Devolve o Runnable que gera a resposta. Dependência do FastAPI (fácil de trocar nos testes).

    Cria um modelo novo a cada requisição porque o FakeListChatModel guarda um contador interno.
    O AgentExecutor recebe a pergunta na chave "input", por isso o prompt usa {input}.
    """
    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    return prompt | FakeListChatModel(responses=[STAND_IN_ANSWER])


def sse_event(event: str, data: Any) -> str:
    """Monta um evento SSE. O JSON fica em uma linha só (quebras viram \\n escapado)."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _texto_do_chunk(chunk: Any) -> str:
    """Extrai o texto de um chunk. Alguns modelos devolvem uma lista de blocos em vez de str."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            bloco.get("text", "")
            for bloco in content
            if isinstance(bloco, dict) and bloco.get("type") == "text"
        )
    return ""


async def stream_chat_events(
    runnable: Runnable,
    message: str,
    session_id: str,
    conversation_id: str,
) -> AsyncIterator[str]:
    """Gera os eventos SSE de uma resposta. Nunca levanta exceção: falhas viram evento `error`.

    Em SSE a resposta HTTP já saiu com status 200 quando o primeiro pedaço é enviado,
    então um erro no meio do caminho só pode ser comunicado como evento.
    """
    try:
        async for event in runnable.astream_events(
            {"input": message},
            config={"configurable": {"session_id": session_id}},
            version="v2",
        ):
            if event["event"] != "on_chat_model_stream":
                continue
            texto = _texto_do_chunk(event["data"]["chunk"])
            if texto:
                yield sse_event("token", {"text": texto})
    except Exception:
        logger.exception("Erro durante o stream do chat")
        yield sse_error_event(MSG_ERRO_INESPERADO, "ERRO_INESPERADO")
        return
    yield sse_event("done", {"conversation_id": conversation_id})
