import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


class GLPIClient:
    """Cliente base para a API v2 do GLPI."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        scope: str = "api",
    ) -> None:
        self.base_url = (base_url or os.getenv("GLPI_BASE_URL") or "http://localhost:8080").rstrip("/")
        self.client_id = client_id or os.getenv("GLPI_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GLPI_CLIENT_SECRET")
        self.username = username or os.getenv("GLPI_USERNAME")
        self.password = password or os.getenv("GLPI_PASSWORD")
        self.scope = scope
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None

    def ensure_credentials(self) -> None:
        missing = [
            name
            for name, value in {
                "GLPI_CLIENT_ID": self.client_id,
                "GLPI_CLIENT_SECRET": self.client_secret,
                "GLPI_USERNAME": self.username,
                "GLPI_PASSWORD": self.password,
            }.items()
            if value in (None, "")
        ]
        if missing:
            raise ValueError(
                "Credenciais ausentes. Defina as variáveis de ambiente: "
                + ", ".join(missing)
                + " ou passe os parâmetros na criação do cliente."
            )

    def get_token(self) -> Dict[str, Any]:
        self.ensure_credentials()
        payload = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
            "scope": self.scope,
        }
        response = requests.post(f"{self.base_url}/api.php/token", json=payload, timeout=30)
        data = self._parse_response(response)
        if response.status_code == 200 and isinstance(data, dict):
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
        return data

    def refresh_token_request(self) -> Dict[str, Any]:
        if not self.refresh_token:
            raise ValueError("Refresh token não disponível. Faça login primeiro.")
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
        }
        response = requests.post(f"{self.base_url}/api.php/token", json=payload, timeout=30)
        data = self._parse_response(response)
        if response.status_code == 200 and isinstance(data, dict):
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
        return data
    
    def request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.access_token:
            self.get_token()

        response = self._send(method, path, params=params, json_body=json_body)

        if response.status_code == 401:
            if self.refresh_token:
                self.refresh_token_request()
            else:
                self.get_token()
            response = self._send(method, path, params=params, json_body=json_body)

        return {
            "status_code": response.status_code,
            "url": f"{self.base_url}{path}",
            "params": params,
            "data": self._parse_response(response),
        }

    def _send(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json_body: Optional[Dict[str, Any]] = None) -> requests.Response:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        return requests.request(
            method=method.upper(),
            url=f"{self.base_url}{path}",
            headers=headers,
            params=params,
            json=json_body,
            timeout=30,
        )

    @staticmethod
    def _parse_response(response: requests.Response) -> Any:
        if response.content in (b"", None):
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def me(self) -> Dict[str, Any]:
        return self.request("GET", "/api.php/v2/Administration/User/Me")

    def ticket_list(self, start: int = 0, limit: int = 5) -> Dict[str, Any]:
        return self.request(
            "GET",
            "/api.php/v2/Assistance/Ticket",
            params={"start": start, "limit": limit},
        )

    def ticket_detail(self, ticket_id: int) -> Dict[str, Any]:
        return self.request("GET", f"/api.php/v2/Assistance/Ticket/{ticket_id}")

    def ticket_timeline(self, ticket_id: int) -> Dict[str, Any]:
        return self.request("GET", f"/api.php/v2/Assistance/Ticket/{ticket_id}/Timeline")

    def knowledgebase_articles(self, start: int = 0, limit: int = 5) -> Dict[str, Any]:
        return self.request(
            "GET",
            "/api.php/v2/Knowledgebase/Article",
            params={"start": start, "limit": limit},
        )

    def itil_categories(self, start: int = 0, limit: int = 5) -> Dict[str, Any]:
        return self.request(
            "GET",
            "/api.php/v2/Dropdowns/ITILCategory",
            params={"start": start, "limit": limit},
        )

    def users(self, start: int = 0, limit: int = 5) -> Dict[str, Any]:
        return self.request(
            "GET",
            "/api.php/v2/Administration/User",
            params={"start": start, "limit": limit},
        )

    def create_ticket(self, name: str, content: str) -> Dict[str, Any]:
        return self.request(
            "POST",
            "/api.php/v2/Assistance/Ticket",
            json_body={"name": name, "content": content},
        )

    def add_followup(self, ticket_id: int, content: str) -> Dict[str, Any]:
        return self.request(
            "POST",
            f"/api.php/v2/Assistance/Ticket/{ticket_id}/Timeline/Followup",
            json_body={"content": content},
        )

    def update_ticket(self, ticket_id: int, **fields: Any) -> Dict[str, Any]:
        return self.request(
            "PATCH",
            f"/api.php/v2/Assistance/Ticket/{ticket_id}",
            json_body=fields,
        )


def pretty_print(label: str, payload: Dict[str, Any]) -> None:
    print(f"\n===== {label} =====")
    print(f"Status HTTP: {payload.get('status_code')}")
    print(f"URL: {payload.get('url')}")
    if payload.get("params"):
        print(f"Parâmetros: {payload['params']}")
    print("Retorno:")
    print(payload.get("data"))
