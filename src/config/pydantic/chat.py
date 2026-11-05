from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.config.pydantic.base import APIInputModel


MAX_MESSAGE_LENGTH = 4_000
MAX_HISTORY_MESSAGES = 50


class ArticleResult(BaseModel):
    id: int
    titulo: str
    conteudo: str
    pontuacao: float
    termos_encontrados: list[str]
    fonte_api: str


class ChatResponse(BaseModel):
    pergunta: str
    palavras_chave: list[str]
    artigos: list[ArticleResult]
    total: int


class ChatHistoryMessage(APIInputModel):
    role: str = Field(json_schema_extra={"enum": ["user", "assistant"]})
    content: str = Field(json_schema_extra={"minLength": 1, "maxLength": MAX_MESSAGE_LENGTH})

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if cls.should_bypass_validation():
            return value
        if value not in {"user", "assistant"}:
            raise ValueError("O papel do histórico deve ser 'user' ou 'assistant'.")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if cls.should_bypass_validation():
            return value
        if not value.strip():
            raise ValueError("O conteúdo do histórico não pode ser vazio.")
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"O conteúdo do histórico não pode exceder {MAX_MESSAGE_LENGTH} caracteres.")
        return value


class ChatRequest(APIInputModel):
    message: str = Field(json_schema_extra={"minLength": 1, "maxLength": MAX_MESSAGE_LENGTH})
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        json_schema_extra={"maxItems": MAX_HISTORY_MESSAGES},
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if cls.should_bypass_validation():
            return value
        if not value.strip():
            raise ValueError("A mensagem não pode ser vazia.")
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"A mensagem não pode exceder {MAX_MESSAGE_LENGTH} caracteres.")
        return value

    @field_validator("history", mode="before")
    @classmethod
    def validate_history(cls, value: Any) -> Any:
        if (
            not cls.should_bypass_validation()
            and isinstance(value, list)
            and len(value) > MAX_HISTORY_MESSAGES
        ):
            raise ValueError(f"O histórico não pode conter mais de {MAX_HISTORY_MESSAGES} mensagens.")
        return value
