from pydantic import Field, field_validator, model_validator

from src.config.pydantic.base import APIInputModel


class TicketCreateRequest(APIInputModel):
    name: str = Field(json_schema_extra={"minLength": 1, "maxLength": 255})
    content: str = Field(json_schema_extra={"minLength": 1, "maxLength": 10_000})

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if cls.should_bypass_validation():
            return value
        if not value.strip():
            raise ValueError("O título do chamado não pode ser vazio.")
        if len(value) > 255:
            raise ValueError("O título do chamado não pode exceder 255 caracteres.")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if cls.should_bypass_validation():
            return value
        if not value.strip():
            raise ValueError("O conteúdo do chamado não pode ser vazio.")
        if len(value) > 10_000:
            raise ValueError("O conteúdo do chamado não pode exceder 10000 caracteres.")
        return value


class FollowupRequest(APIInputModel):
    content: str = Field(json_schema_extra={"minLength": 1, "maxLength": 10_000})

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if cls.should_bypass_validation():
            return value
        if not value.strip():
            raise ValueError("O comentário não pode ser vazio.")
        if len(value) > 10_000:
            raise ValueError("O comentário não pode exceder 10000 caracteres.")
        return value


class TicketUpdateRequest(APIInputModel):
    name: str | None = Field(default=None, json_schema_extra={"minLength": 1, "maxLength": 255})
    content: str | None = Field(default=None, json_schema_extra={"minLength": 1, "maxLength": 10_000})

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if cls.should_bypass_validation() or value is None:
            return value
        if not value.strip():
            raise ValueError("O título do chamado não pode ser vazio.")
        if len(value) > 255:
            raise ValueError("O título do chamado não pode exceder 255 caracteres.")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if cls.should_bypass_validation() or value is None:
            return value
        if not value.strip():
            raise ValueError("O conteúdo do chamado não pode ser vazio.")
        if len(value) > 10_000:
            raise ValueError("O conteúdo do chamado não pode exceder 10000 caracteres.")
        return value

    @model_validator(mode="after")
    def require_update_fields(self) -> "TicketUpdateRequest":
        if not self.should_bypass_validation() and not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self
