from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from .auth import OAuthClient, TokenStore
from .config import Settings
from .glpi_client import GLPIClient, GLPIError


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    store = TokenStore()
    app.state.glpi = GLPIClient(settings, OAuthClient(settings, store))
    yield


app = FastAPI(title="GLPI Agent Service", version="0.1.0", lifespan=lifespan)


@app.exception_handler(GLPIError)
async def glpi_error_handler(_: Request, error: GLPIError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"error": error.detail})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tickets/{ticket_id}/timeline")
async def ticket_timeline(ticket_id: int, request: Request) -> Any:
    return await request.app.state.glpi.timeline(ticket_id)


@app.get("/api/knowledge/articles")
async def articles(
    request: Request,
    start: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
) -> Any:
    return await request.app.state.glpi.list_articles(start, limit)


@app.get("/api/knowledge/articles/{article_id}")
async def article(article_id: int, request: Request) -> Any:
    return await request.app.state.glpi.article(article_id)


@app.post("/api/knowledge/articles", status_code=201)
async def create_article(payload: dict[str, str], request: Request) -> Any:
    if not payload.get("name") or not payload.get("content"):
        return JSONResponse(
            status_code=422,
            content={"error": "name e content sao obrigatorios"},
        )
    return await request.app.state.glpi.create_article(payload["name"], payload["content"])
