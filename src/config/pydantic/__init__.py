"""Modelos Pydantic usados para validar as entradas da API."""

from src.config.pydantic.auth import PasswordTokenRequest, RefreshTokenRequest
from src.config.pydantic.chat import ChatHistoryMessage, ChatRequest
from src.config.pydantic.request import APIRequestEnvelope, PydanticRequestValidationMiddleware
from src.config.pydantic.settings import validation_bypassed
from src.config.pydantic.tickets import FollowupRequest, TicketCreateRequest, TicketUpdateRequest
from src.config.pydantic.types import PaginationParams

__all__ = [
    "APIRequestEnvelope",
    "ChatHistoryMessage",
    "ChatRequest",
    "FollowupRequest",
    "PasswordTokenRequest",
    "PaginationParams",
    "PydanticRequestValidationMiddleware",
    "RefreshTokenRequest",
    "TicketCreateRequest",
    "TicketUpdateRequest",
    "validation_bypassed",
]
