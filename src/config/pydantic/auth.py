from pydantic import model_validator

from src.config.pydantic.base import APIInputModel


class PasswordTokenRequest(APIInputModel):
    client_id: str
    client_secret: str
    username: str
    password: str
    scope: str = "api"

    @model_validator(mode="after")
    def validate_credentials(self) -> "PasswordTokenRequest":
        if self.should_bypass_validation():
            return self
        limits = {
            "client_id": 256,
            "client_secret": 2_048,
            "username": 256,
            "password": 2_048,
            "scope": 256,
        }
        for field, max_length in limits.items():
            value = getattr(self, field)
            if not value.strip():
                raise ValueError(f"O campo '{field}' não pode ser vazio.")
            if len(value) > max_length:
                raise ValueError(f"O campo '{field}' não pode exceder {max_length} caracteres.")
        return self


class RefreshTokenRequest(APIInputModel):
    client_id: str
    client_secret: str
    refresh_token: str
    scope: str = "api"

    @model_validator(mode="after")
    def validate_credentials(self) -> "RefreshTokenRequest":
        if self.should_bypass_validation():
            return self
        limits = {
            "client_id": 256,
            "client_secret": 2_048,
            "refresh_token": 8_192,
            "scope": 256,
        }
        for field, max_length in limits.items():
            value = getattr(self, field)
            if not value.strip():
                raise ValueError(f"O campo '{field}' não pode ser vazio.")
            if len(value) > max_length:
                raise ValueError(f"O campo '{field}' não pode exceder {max_length} caracteres.")
        return self
