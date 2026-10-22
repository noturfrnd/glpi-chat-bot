from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from src.config.pydantic.settings import validation_bypassed


class APIInputModel(BaseModel):
    bypass_validation: ClassVar[bool] = False
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def should_bypass_validation(cls) -> bool:
        return cls.bypass_validation or validation_bypassed()
