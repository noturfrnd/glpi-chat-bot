from pydantic import model_validator

from src.config.pydantic.base import APIInputModel


class PaginationParams(APIInputModel):
    start: int = 0
    limit: int = 100

    @model_validator(mode="after")
    def validate_pagination(self) -> "PaginationParams":
        if self.should_bypass_validation():
            return self
        if self.start < 0:
            raise ValueError("O parâmetro 'start' deve ser maior ou igual a zero.")
        if not 1 <= self.limit <= 200:
            raise ValueError("O parâmetro 'limit' deve estar entre 1 e 200.")
        return self
