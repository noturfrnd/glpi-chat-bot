import os
from dataclasses import dataclass
from typing import Any

import requests
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config.pydantic import (
    ChatRequest,
    FollowupRequest,
    PasswordTokenRequest,
    PaginationParams,
    RefreshTokenRequest,
    TicketCreateRequest,
    TicketUpdateRequest,
    validation_bypassed,
)
from src.config.pydantic.jwt import decode_glpi_jwt
from src.config.pydantic.request import PydanticRequestValidationMiddleware
from src.glpi_client import GLPIClient

app = FastAPI(title="GLPI Chat Bot API", version="1.0.0")
app.add_middleware(PydanticRequestValidationMiddleware)
bearer_scheme = HTTPBearer(auto_error=False)


@app.exception_handler(RequestValidationError)
async def pydantic_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    del request
    details = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@dataclass
class GLPIAuthContext:
    client: GLPIClient
    user: Any
    jwt_claims: dict[str, Any] | None


def _new_glpi_client() -> GLPIClient:
    return GLPIClient(base_url=os.getenv("GLPI_BASE_URL"))


def get_glpi_auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> GLPIAuthContext:
    if validation_bypassed():
        context = GLPIAuthContext(client=_new_glpi_client(), user=None, jwt_claims=None)
        request.state.glpi_auth = context
        return context
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Envie um token GLPI no cabeçalho Authorization: Bearer.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    client = _new_glpi_client()
    client.access_token = credentials.credentials
    context = GLPIAuthContext(
        client=client,
        user=None,
        jwt_claims=decode_glpi_jwt(credentials.credentials),
    )
    request.state.glpi_auth = context
    return context


def _proxy_response(result: dict[str, Any]) -> Response:
    status_code = result["status_code"]
    if status_code == 204:
        return Response(status_code=status_code)
    return JSONResponse(status_code=status_code, content=result.get("data"))


def _proxy_token_response(client: GLPIClient, payload: Any) -> Response:
    status_code = client.last_status_code
    if status_code is None:
        raise HTTPException(status_code=502, detail="O GLPI não retornou um status HTTP para o token.")
    if status_code == 204:
        return Response(status_code=status_code)
    return JSONResponse(status_code=status_code, content=payload)


def _call_glpi(context: GLPIAuthContext, operation: str, *args: Any, **kwargs: Any) -> Response:
    try:
        result = getattr(context.client, operation)(*args, **kwargs)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Não foi possível concluir a chamada ao GLPI.") from exc
    return _proxy_response(result)


@app.post("/api/auth/token")
def issue_token(payload: PasswordTokenRequest) -> Response:
    client = GLPIClient(
        base_url=os.getenv("GLPI_BASE_URL"),
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        username=payload.username,
        password=payload.password,
        scope=payload.scope,
    )
    try:
        result = client.get_token()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Não foi possível solicitar um token ao GLPI.") from exc
    return _proxy_token_response(client, result)


@app.post("/api/auth/refresh")
def refresh_token(payload: RefreshTokenRequest) -> Response:
    client = GLPIClient(
        base_url=os.getenv("GLPI_BASE_URL"),
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        scope=payload.scope,
    )
    client.refresh_token = payload.refresh_token
    try:
        result = client.refresh_token_request()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Não foi possível renovar o token no GLPI.") from exc
    return _proxy_token_response(client, result)


def _validate_ticket_id(ticket_id: int) -> None:
    if not validation_bypassed() and ticket_id < 1:
        raise HTTPException(status_code=422, detail="O ID do chamado deve ser maior que zero.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/me")
def me(context: GLPIAuthContext = Depends(get_glpi_auth_context)) -> Response:
    if context.user is not None:
        return JSONResponse(content=context.user)
    return _call_glpi(context, "me")


@app.get("/api/tickets")
def list_tickets(
    pagination: PaginationParams = Depends(),
    context: GLPIAuthContext = Depends(get_glpi_auth_context),
) -> Response:
    return _call_glpi(context, "ticket_list", start=pagination.start, limit=pagination.limit)


@app.get("/api/tickets/{ticket_id}")
def ticket_detail(ticket_id: int, context: GLPIAuthContext = Depends(get_glpi_auth_context)) -> Response:
    _validate_ticket_id(ticket_id)
    return _call_glpi(context, "ticket_detail", ticket_id)


@app.get("/api/tickets/{ticket_id}/timeline")
def ticket_timeline(ticket_id: int, context: GLPIAuthContext = Depends(get_glpi_auth_context)) -> Response:
    _validate_ticket_id(ticket_id)
    return _call_glpi(context, "ticket_timeline", ticket_id)


@app.post("/api/tickets")
def create_ticket(
    payload: TicketCreateRequest,
    context: GLPIAuthContext = Depends(get_glpi_auth_context),
) -> Response:
    return _call_glpi(context, "create_ticket", payload.name, payload.content)


@app.post("/api/tickets/{ticket_id}/followups")
def add_followup(
    ticket_id: int,
    payload: FollowupRequest,
    context: GLPIAuthContext = Depends(get_glpi_auth_context),
) -> Response:
    _validate_ticket_id(ticket_id)
    return _call_glpi(context, "add_followup", ticket_id, payload.content)


@app.patch("/api/tickets/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: TicketUpdateRequest,
    context: GLPIAuthContext = Depends(get_glpi_auth_context),
) -> Response:
    _validate_ticket_id(ticket_id)
    fields = payload.model_dump(exclude_unset=True)
    return _call_glpi(context, "update_ticket", ticket_id, **fields)


@app.get("/api/articles")
def list_articles(
    pagination: PaginationParams = Depends(),
    context: GLPIAuthContext = Depends(get_glpi_auth_context),
) -> Response:
    return _call_glpi(context, "knowledgebase_articles", start=pagination.start, limit=pagination.limit)


@app.get("/api/categories")
def list_categories(
    pagination: PaginationParams = Depends(),
    context: GLPIAuthContext = Depends(get_glpi_auth_context),
) -> Response:
    return _call_glpi(context, "itil_categories", start=pagination.start, limit=pagination.limit)


@app.get("/api/users")
def list_users(
    pagination: PaginationParams = Depends(),
    context: GLPIAuthContext = Depends(get_glpi_auth_context),
) -> Response:
    return _call_glpi(context, "users", start=pagination.start, limit=pagination.limit)


@app.post("/api/chat")
def chat(payload: ChatRequest, context: GLPIAuthContext = Depends(get_glpi_auth_context)) -> None:
    del payload, context
    raise HTTPException(
        status_code=501,
        detail="O endpoint de chat está validado, mas ainda não há um motor de conversa integrado.",
    )


def main() -> None:
    uvicorn.run(
        "src.main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("APP_ENV", "").lower() == "development",
    )


if __name__ == "__main__":
    main()
