import json
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from src.config.pydantic.settings import validation_bypassed


MAX_REQUEST_BODY_BYTES = 1_000_000
MAX_QUERY_PARAMETERS = 100
MAX_QUERY_KEY_LENGTH = 256
MAX_QUERY_VALUE_LENGTH = 4_096


class APIRequestEnvelope(BaseModel):
    """Pydantic guard applied to every incoming HTTP request."""

    model_config = ConfigDict(extra="forbid")
    bypass_validation: ClassVar[bool] = False

    method: str
    path: str
    query_params: list[tuple[str, str]]
    body_size: int
    body: Any = None

    @model_validator(mode="after")
    def validate_request(self) -> "APIRequestEnvelope":
        if self.bypass_validation or validation_bypassed():
            return self
        if self.method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
            raise ValueError("Método HTTP não suportado.")
        if not 1 <= len(self.path) <= 2_048:
            raise ValueError("O caminho da requisição deve ter entre 1 e 2048 caracteres.")
        if len(self.query_params) > MAX_QUERY_PARAMETERS:
            raise ValueError(f"A query string não pode exceder {MAX_QUERY_PARAMETERS} parâmetros.")
        for key, item in self.query_params:
            if len(key) > MAX_QUERY_KEY_LENGTH:
                raise ValueError(f"A chave de query não pode exceder {MAX_QUERY_KEY_LENGTH} caracteres.")
            if len(item) > MAX_QUERY_VALUE_LENGTH:
                raise ValueError(f"O valor de query não pode exceder {MAX_QUERY_VALUE_LENGTH} caracteres.")
        if not 0 <= self.body_size <= MAX_REQUEST_BODY_BYTES:
            raise ValueError("O tamanho do corpo deve estar entre 0 e 1000000 bytes.")
        return self


class PydanticRequestValidationMiddleware:
    """Validates and buffers requests before FastAPI route handling."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if (
                len(body) > MAX_REQUEST_BODY_BYTES
                and not APIRequestEnvelope.bypass_validation
                and not validation_bypassed()
            ):
                await self._respond(
                    scope,
                    receive,
                    send,
                    status_code=413,
                    detail="O corpo da requisição excede o limite de 1 MB.",
                )
                return
            if not message.get("more_body", False):
                break

        content_type = dict(scope.get("headers", [])).get(b"content-type", b"").split(b";", 1)[0].strip().lower()
        parsed_body: Any = None
        if body:
            if content_type != b"application/json" and not content_type.endswith(b"+json"):
                await self._respond(
                    scope,
                    receive,
                    send,
                    status_code=415,
                    detail="Corpos de requisição devem usar Content-Type application/json.",
                )
                return
            try:
                parsed_body = json.loads(body)
            except (UnicodeDecodeError, ValueError):
                await self._respond(
                    scope,
                    receive,
                    send,
                    status_code=422,
                    detail="O corpo da requisição não contém JSON válido.",
                )
                return

        try:
            APIRequestEnvelope.model_validate(
                {
                    "method": scope["method"].upper(),
                    "path": scope.get("path", ""),
                    "query_params": _parse_query_string(scope.get("query_string", b"")),
                    "body_size": len(body),
                    "body": parsed_body,
                }
            )
        except ValidationError as exc:
            detail = "; ".join(error["msg"] for error in exc.errors(include_input=False))
            await self._respond(scope, receive, send, status_code=422, detail=detail)
            return
        except (ValueError, TypeError) as exc:
            await self._respond(
                scope,
                receive,
                send,
                status_code=422,
                detail=f"Requisição global inválida: {exc}",
            )
            return

        body_sent = False

        async def replay_body() -> dict[str, Any]:
            nonlocal body_sent
            if body_sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            body_sent = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_body, send)

    @staticmethod
    async def _respond(
        scope: dict[str, Any],
        receive: Any,
        send: Any,
        *,
        status_code: int,
        detail: str,
    ) -> None:
        from starlette.responses import JSONResponse

        await JSONResponse(status_code=status_code, content={"detail": detail})(scope, receive, send)


def _parse_query_string(query_string: bytes) -> list[tuple[str, str]]:
    from urllib.parse import parse_qsl

    return parse_qsl(query_string.decode("utf-8"), keep_blank_values=True)
