"""Tratamento global de erros da API.

Formato padrão de resposta de erro:
    {"detail": "mensagem amigável", "codigo": "CODIGO_DO_ERRO"}
"""

import json
import logging
from http import HTTPStatus
from typing import Any

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("glpi_chat_bot")

MSG_ERRO_INESPERADO = "Ocorreu um erro inesperado. Tente novamente em instantes."

CODIGOS_HTTP = {
    400: "REQUISICAO_INVALIDA",
    401: "NAO_AUTENTICADO",
    403: "SEM_PERMISSAO",
    404: "NAO_ENCONTRADO",
    405: "METODO_NAO_PERMITIDO",
    422: "DADOS_INVALIDOS",
    429: "MUITAS_REQUISICOES",
    501: "NAO_IMPLEMENTADO",
    502: "GLPI_ERRO_COMUNICACAO",
    503: "SERVICO_INDISPONIVEL",
    504: "GLPI_TIMEOUT",
}

MENSAGENS_PADRAO = {
    404: "O endereço solicitado não foi encontrado.",
    405: "Este método HTTP não é permitido para este endereço.",
}


# ---------------------------------------------------------------------------
# Exceções customizadas
# ---------------------------------------------------------------------------
class AppError(Exception):
    """Erro da aplicação com mensagem amigável para o usuário."""

    status_code = 500
    codigo = "ERRO_INTERNO"
    mensagem = MSG_ERRO_INESPERADO

    def __init__(
        self,
        mensagem: str | None = None,
        *,
        status_code: int | None = None,
        codigo: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.mensagem = mensagem or self.mensagem
        if status_code is not None:
            self.status_code = status_code
        if codigo is not None:
            self.codigo = codigo
        self.headers = headers
        super().__init__(self.mensagem)


class GLPIError(AppError):
    status_code = 502
    codigo = "GLPI_ERRO"
    mensagem = "O GLPI não conseguiu concluir a solicitação."


class GLPIConfigError(GLPIError):
    status_code = 500
    codigo = "GLPI_NAO_CONFIGURADO"
    mensagem = (
        "A integração com o GLPI não está configurada corretamente. "
        "Avise o suporte técnico."
    )


class ChatbotError(AppError):
    status_code = 500
    codigo = "CHATBOT_ERRO"
    mensagem = "Não foi possível continuar a conversa. Tente novamente."


# ---------------------------------------------------------------------------
# Tradução de respostas de erro do GLPI
# ---------------------------------------------------------------------------
def erro_glpi_por_status(
    status_code: int,
    detalhe: Any = None,
    *,
    token: bool = False,
) -> GLPIError:
    """Converte um status HTTP de erro do GLPI em um erro amigável."""
    logger.warning("GLPI respondeu %s: %s", status_code, str(detalhe)[:500])

    if token and status_code in (400, 401):
        return GLPIError(
            "Não foi possível autenticar no GLPI. Confira os dados informados "
            "ou faça login novamente.",
            status_code=401,
            codigo="GLPI_CREDENCIAIS_INVALIDAS",
        )
    if status_code == 401:
        return GLPIError(
            "Sua sessão expirou ou o token é inválido. Faça login novamente.",
            status_code=401,
            codigo="GLPI_NAO_AUTORIZADO",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if status_code == 403:
        return GLPIError(
            "Você não tem permissão para realizar esta ação no GLPI.",
            status_code=403,
            codigo="GLPI_SEM_PERMISSAO",
        )
    if status_code == 404:
        return GLPIError(
            "Não encontramos o item solicitado no GLPI.",
            status_code=404,
            codigo="GLPI_NAO_ENCONTRADO",
        )
    if status_code in (400, 422):
        return GLPIError(
            "O GLPI não aceitou os dados enviados. Revise as informações e tente novamente.",
            status_code=status_code,
            codigo="GLPI_DADOS_INVALIDOS",
        )
    if status_code == 429:
        return GLPIError(
            "O GLPI recebeu muitas requisições. Aguarde um instante e tente novamente.",
            status_code=429,
            codigo="GLPI_MUITAS_REQUISICOES",
        )
    if status_code >= 500:
        return GLPIError(
            "O GLPI está com problemas no momento. Tente novamente em instantes.",
            status_code=502,
            codigo="GLPI_ERRO_INTERNO",
        )
    return GLPIError(status_code=status_code)


# ---------------------------------------------------------------------------
# SSE (para o endpoint de chat, quando existir streaming)
# ---------------------------------------------------------------------------
def sse_error_event(mensagem: str, codigo: str = "CHATBOT_ERRO") -> str:
    """Monta um evento de erro para enviar dentro de um stream SSE.

    Em SSE a conexão já foi aberta (status 200), então o erro vai como evento.
    """
    payload = json.dumps({"detail": mensagem, "codigo": codigo}, ensure_ascii=False)
    return f"event: error\ndata: {payload}\n\n"


# ---------------------------------------------------------------------------
# Handlers globais
# ---------------------------------------------------------------------------
def _resposta(
    status_code: int,
    mensagem: Any,
    codigo: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": mensagem, "codigo": codigo},
        headers=headers,
    )


def _eh_mensagem_padrao(status_code: int, detail: Any) -> bool:
    try:
        return detail == HTTPStatus(status_code).phrase
    except ValueError:
        return False


async def _tratar_app_error(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "%s em %s %s: %s", exc.codigo, request.method, request.url.path, exc.mensagem
    )
    return _resposta(exc.status_code, exc.mensagem, exc.codigo, exc.headers)


async def _tratar_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    del request
    detail = exc.detail
    if _eh_mensagem_padrao(exc.status_code, detail):
        detail = MENSAGENS_PADRAO.get(
            exc.status_code, "Não foi possível concluir a solicitação."
        )
    codigo = CODIGOS_HTTP.get(exc.status_code, "ERRO_HTTP")
    return _resposta(exc.status_code, detail, codigo, getattr(exc, "headers", None))


async def _tratar_erro_de_rede(
    request: Request, exc: requests.RequestException
) -> JSONResponse:
    logger.error(
        "Falha de comunicação com o GLPI em %s %s", request.method, request.url.path,
        exc_info=exc,
    )
    if isinstance(exc, requests.Timeout):
        return _resposta(
            504,
            "O GLPI demorou demais para responder. Tente novamente em instantes.",
            "GLPI_TIMEOUT",
        )
    if isinstance(exc, requests.ConnectionError):
        return _resposta(
            502,
            "Não foi possível conectar ao GLPI. Ele pode estar fora do ar.",
            "GLPI_INDISPONIVEL",
        )
    return _resposta(
        502, "Não foi possível concluir a chamada ao GLPI.", "GLPI_ERRO_COMUNICACAO"
    )


async def _tratar_erro_inesperado(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Erro inesperado em %s %s", request.method, request.url.path, exc_info=exc
    )
    return _resposta(500, MSG_ERRO_INESPERADO, "ERRO_INTERNO")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _tratar_app_error)
    app.add_exception_handler(StarletteHTTPException, _tratar_http_exception)
    app.add_exception_handler(requests.RequestException, _tratar_erro_de_rede)
    app.add_exception_handler(Exception, _tratar_erro_inesperado)