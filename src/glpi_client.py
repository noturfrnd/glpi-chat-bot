from typing import Any

import httpx

from .auth import OAuthClient
from .config import Settings


class GLPIError(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"GLPI respondeu {status_code}: {detail}")


class GLPIClient:
    def __init__(self, settings: Settings, oauth: OAuthClient) -> None:
        self.settings = settings
        self.oauth = oauth

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        for attempt in range(2):
            token = await self.oauth.access_token(force_refresh=attempt == 1)
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.request(
                    method,
                    self._url(path),
                    params=params,
                    json=json,
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.status_code == 401 and attempt == 0:
                self.oauth.invalidate()
                continue
            if not 200 <= response.status_code < 300:
                try:
                    detail = response.json()
                except ValueError:
                    detail = response.text
                raise GLPIError(response.status_code, detail)
            return response.json()
        raise RuntimeError("Nao foi possivel autenticar no GLPI")

    async def timeline(self, ticket_id: int) -> Any:
        return await self.request("GET", f"/api.php/v2/Assistance/Ticket/{ticket_id}/Timeline")

    async def list_articles(self, start: int = 0, limit: int = 50) -> Any:
        return await self.request(
            "GET",
            "/api.php/v2/Knowledgebase/Article",
            params={"start": start, "limit": limit},
        )

    async def article(self, article_id: int) -> Any:
        return await self.request("GET", f"/api.php/v2/Knowledgebase/Article/{article_id}")

    async def create_article(self, name: str, content: str) -> Any:
        return await self.request(
            "POST",
            "/api.php/v2/Knowledgebase/Article",
            json={"name": name, "content": content},
        )

    def _url(self, path: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}{path}"
