from unittest.mock import MagicMock, patch

from src.glpi_client import GLPIClient


def make_client() -> GLPIClient:
    return GLPIClient(
        base_url="http://localhost:8080",
        client_id="cid",
        client_secret="secret",
        username="glpi",
        password="glpi",
    )


def _response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = b"{}"
    resp.json.return_value = json_data or {}
    return resp


@patch("src.glpi_client.requests.request")
@patch("src.glpi_client.requests.post")
def test_401_triggers_refresh_and_retry(mock_post, mock_request):
    client = make_client()
    client.access_token = "token-expirado"
    client.refresh_token = "refresh-valido"

    mock_request.side_effect = [
        _response(401),
        _response(200, {"id": 1, "name": "Chamado teste"}),
    ]
    mock_post.return_value = _response(
        200, {"access_token": "token-novo", "refresh_token": "refresh-novo"}
    )

    result = client.request("GET", "/api.php/v2/Assistance/Ticket/1")

    assert result["status_code"] == 200
    assert client.access_token == "token-novo"
    assert mock_request.call_count == 2


@patch("src.glpi_client.requests.request")
@patch("src.glpi_client.requests.post")
def test_401_without_refresh_token_falls_back_to_login(mock_post, mock_request):
    client = make_client()
    client.access_token = "token-expirado"
    client.refresh_token = None

    mock_request.side_effect = [
        _response(401),
        _response(200, {"id": 1}),
    ]
    mock_post.return_value = _response(
        200, {"access_token": "token-via-login", "refresh_token": "novo-refresh"}
    )

    result = client.request("GET", "/api.php/v2/Assistance/Ticket/1")

    assert result["status_code"] == 200
    assert client.access_token == "token-via-login"