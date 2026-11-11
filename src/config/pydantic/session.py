from pydantic import BaseModel, Field, field_validator

from src.config.pydantic.base import APIInputModel


class UserIdentificationRequest(APIInputModel):
    identifier: str = Field(..., json_schema_extra={"minLength": 1, "maxLength": 256})
    session_id: str | None = Field(default=None, json_schema_extra={"maxLength": 128})

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if cls.should_bypass_validation():
            return value
        if not value or not value.strip():
            raise ValueError("O identificador (usuário ou e-mail) não pode ser vazio.")
        if len(value) > 256:
            raise ValueError("O identificador não pode exceder 256 caracteres.")
        return value.strip()


class IdentifiedUserData(BaseModel):
    id: int
    name: str
    realname: str | None = None
    firstname: str | None = None
    email: str | None = None
    is_active: bool = True


class UserIdentificationResponse(BaseModel):
    success: bool = True
    message: str
    session_id: str
    user: IdentifiedUserData
