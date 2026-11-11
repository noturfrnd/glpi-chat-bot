"""Gerenciamento de sessões de usuário do ChatBot com isolamento em memória."""

from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional


class SessionStore:
    """Armazena sessões ativas do ChatBot garantindo isolamento estrito entre usuários."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def save_session(self, session_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Salva ou atualiza a sessão associando o usuário identificado ao session_id."""
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            existing = self._sessions.get(session_id)
            session = {
                "session_id": session_id,
                "user": dict(user_data),
                "created_at": existing["created_at"] if existing else now,
                "updated_at": now,
            }
            self._sessions[session_id] = session
            return dict(session)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Recupera os dados da sessão pelo seu ID."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            return {
                "session_id": session["session_id"],
                "user": dict(session["user"]),
                "created_at": session["created_at"],
                "updated_at": session["updated_at"],
            }

    def delete_session(self, session_id: str) -> bool:
        """Remove uma sessão."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def clear(self) -> None:
        """Limpa todas as sessões (útil para testes)."""
        with self._lock:
            self._sessions.clear()


session_store = SessionStore()
