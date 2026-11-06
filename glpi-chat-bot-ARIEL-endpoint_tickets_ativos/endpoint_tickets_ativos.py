"""
Endpoint: chamados ativos de um usuário específico (GLPI 11 - API v2).

    GET /users/{user}/tickets/active?role=any|requester|assigned

- {user}: ID numérico do usuário no GLPI (ex.: 7) ou login (ex.: ana.ribeiro).
- role:   requester = chamados que o usuário abriu
          assigned  = chamados em que ele é o técnico atribuído
          any       = os dois (padrão)

"Ativo" = status 1 Novo, 2 Em atendimento (atribuído), 3 Em atendimento
(planejado) e 4 Pendente. Solucionados (5), Fechados (6) e chamados na
lixeira ficam de fora.

A API v2 do GLPI não filtra no servidor, então o endpoint pagina
/Assistance/Ticket inteiro e filtra aqui no Python.

Configuração (.env na mesma pasta):
    GLPI_BASE_URL, GLPI_CLIENT_ID, GLPI_CLIENT_SECRET, GLPI_USERNAME, GLPI_PASSWORD

Dependências:
    pip install requests python-dotenv fastapi uvicorn

Executar:
    python endpoint_tickets_ativos.py
    -> http://localhost:8000/users/ana.ribeiro/tickets/active
    -> documentação interativa: http://localhost:8000/docs
"""

import os
import threading
from typing import Any, Dict, List, Literal, Optional

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

load_dotenv()

GLPI_BASE_URL = (os.getenv("GLPI_BASE_URL") or "http://localhost:8080").rstrip("/")
ACTIVE_STATUS_IDS = {1, 2, 3, 4}
PAGE_SIZE = 100


class GLPIError(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(f"GLPI respondeu {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


# ----------------------------------------------------------------------------
# Cliente GLPI (OAuth2 + paginação)
# ----------------------------------------------------------------------------

class GLPIClient:
    def __init__(self) -> None:
        self.credentials = {
            "client_id": os.getenv("GLPI_CLIENT_ID"),
            "client_secret": os.getenv("GLPI_CLIENT_SECRET"),
            "username": os.getenv("GLPI_USERNAME"),
            "password": os.getenv("GLPI_PASSWORD"),
        }
        self.access_token: Optional[str] = None
        self._lock = threading.Lock()

    def _get_token(self) -> None:
        missing = [name for name, value in self.credentials.items() if not value]
        if missing:
            raise ValueError("Credenciais ausentes no .env: " + ", ".join(f"GLPI_{m.upper()}" for m in missing))
        response = requests.post(
            f"{GLPI_BASE_URL}/api.php/token",
            json={"grant_type": "password", "scope": "api", **self.credentials},
            timeout=30,
        )
        if response.status_code != 200:
            raise GLPIError(response.status_code, _body(response))
        self.access_token = response.json()["access_token"]

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, _retry: bool = True) -> Any:
        with self._lock:
            if not self.access_token:
                self._get_token()
            token = self.access_token
        response = requests.get(
            f"{GLPI_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params=params,
            timeout=30,
        )
        if _token_rejected(response) and _retry:
            # Token expirado (dura 1h) ou invalidado (GLPI reiniciado): pega um novo e repete uma vez.
            with self._lock:
                self.access_token = None
            return self.get(path, params, _retry=False)
        # 200 = página completa, 206 = página parcial; os dois são sucesso.
        if not 200 <= response.status_code < 300:
            raise GLPIError(response.status_code, _body(response))
        return _body(response)

    def all_tickets(self) -> List[Dict[str, Any]]:
        tickets: List[Dict[str, Any]] = []
        start = 0
        while True:
            page = self.get("/api.php/v2/Assistance/Ticket", {"start": start, "limit": PAGE_SIZE}) or []
            tickets.extend(page)
            if len(page) < PAGE_SIZE:
                return tickets
            start += PAGE_SIZE


def _body(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def _token_rejected(response: requests.Response) -> bool:
    # Token expirado vem como 401; token que o GLPI não reconhece mais (ex.: após
    # reiniciar o container) vem como 400 "Invalid OAuth token".
    if response.status_code == 401:
        return True
    body = _body(response) if response.status_code == 400 else None
    return isinstance(body, dict) and body.get("title") == "Invalid OAuth token"


# ----------------------------------------------------------------------------
# Filtro de chamados ativos por usuário
# ----------------------------------------------------------------------------

def _status_id(ticket: Dict[str, Any]) -> Optional[int]:
    status = ticket.get("status")
    if isinstance(status, dict):
        status = status.get("id")
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


def _is_user(member: Dict[str, Any], user: str) -> bool:
    if member.get("type", "User") != "User":
        return False
    if user.isdigit():
        return str(member.get("id")) == user
    return str(member.get("name", "")).lower() == user.lower()


def filter_active_tickets(tickets: List[Dict[str, Any]], user: str, role: str = "any") -> List[Dict[str, Any]]:
    result = []
    for ticket in tickets:
        if ticket.get("is_deleted") or _status_id(ticket) not in ACTIVE_STATUS_IDS:
            continue
        team = [m for m in ticket.get("team") or [] if isinstance(m, dict)]
        if any(_is_user(m, user) and role in ("any", m.get("role")) for m in team):
            result.append(ticket)
    return result


def _name(value: Any) -> Any:
    return value.get("name") if isinstance(value, dict) else value


def _people(team: List[Dict[str, Any]], role: str) -> List[str]:
    return [m.get("display_name") or m.get("name") for m in team if isinstance(m, dict) and m.get("role") == role]


def to_response_item(ticket: Dict[str, Any]) -> Dict[str, Any]:
    team = ticket.get("team") or []
    return {
        "id": ticket.get("id"),
        "link": f"{GLPI_BASE_URL}/front/ticket.form.php?id={ticket.get('id')}",
        "name": ticket.get("name"),
        "content": ticket.get("content"),
        "status_id": _status_id(ticket),
        "status": _name(ticket.get("status")),
        "priority": ticket.get("priority"),
        "urgency": ticket.get("urgency"),
        "impact": ticket.get("impact"),
        "category": _name(ticket.get("category")),
        "entity": _name(ticket.get("entity")),
        "requesters": _people(team, "requester"),
        "assignees": _people(team, "assigned"),
        "date": ticket.get("date"),  # data real de abertura (date_creation não é)
        "date_mod": ticket.get("date_mod"),
    }


# ----------------------------------------------------------------------------
# API
# ----------------------------------------------------------------------------

app = FastAPI(title="GLPI - Chamados ativos por usuário")
glpi = GLPIClient()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/users/{user}/tickets/active")
def active_tickets_for_user(
    user: str,
    role: Literal["any", "requester", "assigned"] = Query(
        "any", description="requester = quem abriu, assigned = técnico atribuído, any = ambos"
    ),
) -> Dict[str, Any]:
    """Todos os chamados ativos de um usuário (ID numérico ou login)."""
    try:
        tickets = glpi.all_tickets()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except GLPIError as exc:
        raise HTTPException(status_code=502, detail={"glpi_status": exc.status_code, "glpi_detail": exc.detail})
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao conectar no GLPI: {exc}")

    active = [to_response_item(t) for t in filter_active_tickets(tickets, user, role)]
    return {"user": user, "role": role, "total": len(active), "tickets": active}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
