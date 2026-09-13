from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    base_url: str
    client_id: str
    client_secret: str
    username: str
    password: str
    scope: str = "api"
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "Settings":
        required = {
            "base_url": os.getenv("GLPI_BASE_URL", "http://localhost:8080"),
            "client_id": os.getenv("GLPI_CLIENT_ID", ""),
            "client_secret": os.getenv("GLPI_CLIENT_SECRET", ""),
            "username": os.getenv("GLPI_USERNAME", ""),
            "password": os.getenv("GLPI_PASSWORD", ""),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Variaveis GLPI ausentes: {', '.join(missing)}")
        return cls(
            **required,
            scope=os.getenv("GLPI_SCOPE", "api"),
            timeout_seconds=float(os.getenv("GLPI_TIMEOUT_SECONDS", "15")),
        )
