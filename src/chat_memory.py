"""Memória conversacional LangChain persistida no SQLite local."""

import json
from typing import Any

from langchain_classic.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from sqlalchemy import create_engine

from src.database import PROJECT_ROOT

DATABASE_URL = f"sqlite:///{(PROJECT_ROOT / 'database.db').as_posix()}"
chat_history_engine = create_engine(DATABASE_URL)
HISTORY_TABLE = "langchain_chat_history"
WINDOW_MESSAGE_COUNT = 10


def build_session_id(
    jwt_claims: dict[str, Any] | None,
    conversation_id: str | int | None,
) -> str:
    """Combina o subject do JWT com o ID da conversa sem colisões de separador."""
    if not isinstance(jwt_claims, dict):
        raise ValueError("Não foi possível obter claims do JWT para identificar o usuário.")
    user_id = jwt_claims.get("sub")
    if user_id is None or not str(user_id).strip():
        raise ValueError("O JWT precisa conter o claim 'sub' para identificar o usuário.")
    if conversation_id is None or not str(conversation_id).strip():
        raise ValueError("O ID da conversa não pode ser vazio.")
    return json.dumps([str(user_id), str(conversation_id)], separators=(",", ":"))


def create_chat_memory(session_id: str) -> ConversationBufferWindowMemory:
    """Abre o histórico persistido e disponibiliza a janela das últimas 10 mensagens."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id não pode ser vazio.")

    history = SQLChatMessageHistory(
        session_id=session_id,
        connection=chat_history_engine,
        table_name=HISTORY_TABLE,
    )
    return ConversationBufferWindowMemory(
        chat_memory=history,
        # A implementação do LangChain conta pares de mensagens em `k`.
        k=WINDOW_MESSAGE_COUNT // 2,
        memory_key="chat_history",
        return_messages=True,
    )
