from dataclasses import dataclass
import asyncio
import time
from typing import Any

import httpx

from .config import Settings


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: float


class TokenStore:
    def __init__(self) -> None:
        self._tokens: OAuthTokens | None = None

    def get_valid(self, safety_seconds: int = 30) -> OAuthTokens | None:
        if self._tokens and self._tokens.expires_at > time.time() + safety_seconds:
            return self._tokens
        return None

    def save(self, payload: dict[str, Any]) -> OAuthTokens:
        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError("Resposta OAuth sem access_token")
        tokens = OAuthTokens(
            access_token=access_token,
            refresh_token=payload.get("refresh_token"),
            expires_at=time.time() + int(payload.get("expires_in", 3600)),
        )
        self._tokens = tokens
        return tokens

    def clear(self) -> None:
        self._tokens = None


class OAuthClient:
    def __init__(self, settings: Settings, store: TokenStore) -> None:
        self.settings = settings
        self.store = store
        self._lock = asyncio.Lock()

    async def access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh:
            cached = self.store.get_valid()
            if cached:
                return cached.access_token

        async with self._lock:
            if not force_refresh:
                cached = self.store.get_valid()
                if cached:
                    return cached.access_token
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                payload = self._refresh_payload() if self.store._tokens else self._password_payload()
                response = await client.post(self._url("/api.php/token"), json=payload)
            if response.is_error:
                raise RuntimeError(f"Falha OAuth ({response.status_code}): {response.text}")
            return self.store.save(response.json()).access_token

    def invalidate(self) -> None:
        self.store.clear()

    def _password_payload(self) -> dict[str, str]:
        return {
            "grant_type": "password",
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "username": self.settings.username,
            "password": self.settings.password,
            "scope": self.settings.scope,
        }

    def _refresh_payload(self) -> dict[str, str]:
        refresh_token = self.store._tokens.refresh_token if self.store._tokens else None
        if not refresh_token:
            return self._password_payload()
        return {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
        }

    def _url(self, path: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}{path}"
