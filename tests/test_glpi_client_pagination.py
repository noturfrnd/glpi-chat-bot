from unittest.mock import MagicMock, patch

from src.glpi_client import GLPIClient


def make_client() -> GLPIClient:
    client = GLPIClient(
        base_url="http://localhost:8080",
        client_id="cid",
        client_secret="secret",
        username="glpi",
        password="glpi",
    )
    client.access_token = "token-valido"
    return client


def make_response(status_code: int, data):
    response = MagicMock()
    response.status_code = status_code
    response.content = b"{}"
    response.json.return_value = data
    return response


@patch("src.glpi_client.requests.request")
def test_get_all_articles_one_page(mock_request):
    mock_request.return_value = make_response(
        200,
        [
            {"id": 1, "name": "Artigo 1"},
            {"id": 2, "name": "Artigo 2"},
        ],
    )

    client = make_client()

    articles = client.get_all_articles(page_size=50)

    assert len(articles) == 2
    assert articles[0]["id"] == 1
    assert articles[1]["id"] == 2
    assert mock_request.call_count == 1


@patch("src.glpi_client.requests.request")
def test_get_all_articles_multiple_pages(mock_request):
    mock_request.side_effect = [
        make_response(
            206,
            [
                {"id": 1},
                {"id": 2},
            ],
        ),
        make_response(
            206,
            [
                {"id": 3},
                {"id": 4},
            ],
        ),
        make_response(
            200,
            [
                {"id": 5},
            ],
        ),
    ]

    client = make_client()

    articles = client.get_all_articles(page_size=2)

    assert [article["id"] for article in articles] == [1, 2, 3, 4, 5]
    assert mock_request.call_count == 3


@patch("src.glpi_client.requests.request")
def test_get_all_articles_invalid_response(mock_request):
    mock_request.return_value = make_response(
        200,
        {"error": "resposta inesperada"},
    )

    client = make_client()

    try:
        client.get_all_articles()
        assert False, "Era esperado ValueError"
    except ValueError as error:
        assert str(error) == "Resposta inesperada ao buscar artigos do GLPI."