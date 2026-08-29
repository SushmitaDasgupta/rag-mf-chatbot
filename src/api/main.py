"""FastAPI chat + health endpoints (Phase 2.5 / 4)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import get_settings
from src.guardrails.citations import assert_manifest_urls_allowlisted
from src.guardrails.groq_limits import get_groq_rate_limiter
from src.ingest.index import get_chroma_collection
from src.rag.chat import ChatResponse, handle_chat

app = FastAPI(
    title="Mutual Fund FAQ Assistant",
    description="Facts-only Kotak scheme FAQ (RAG). No investment advice.",
    version="0.4.0",
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    schemes_locked: int
    vector_count: int
    embedding_model: str
    groq_configured: bool
    groq_model: str
    disclaimer: str


class GroqLimitsResponse(BaseModel):
    model: str
    usage: dict[str, int]
    limits: dict[str, int]
    remaining: dict[str, int]
    ui_min_seconds_between_requests: float


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    scheme_id: str | None = None


class ChatApiResponse(BaseModel):
    type: str
    text: str
    citation_url: str | None = None
    last_updated_from_sources: str | None = None
    disclaimer: str
    scheme_id: str | None = None
    facet: str | None = None
    refusal_kind: str | None = None
    retry_after_seconds: float | None = None


@lru_cache(maxsize=1)
def _collection():
    settings = get_settings()
    return get_chroma_collection(
        vector_store_path=settings.vector_store_path,
        collection_name=settings.chroma_collection,
        embedding_model=settings.embedding_model,
    )


@app.on_event("startup")
def _validate_corpus_on_startup() -> None:
    settings = get_settings()
    assert_manifest_urls_allowlisted(settings.manifest_path)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    urls = assert_manifest_urls_allowlisted(settings.manifest_path)
    try:
        count = _collection().count()
        status = "ok"
    except Exception:
        count = 0
        status = "degraded"
    return HealthResponse(
        status=status,
        schemes_locked=len(urls),
        vector_count=count,
        embedding_model=settings.embedding_model,
        groq_configured=bool(settings.groq_api_key),
        groq_model=settings.groq_model,
        disclaimer="Facts-only. No investment advice.",
    )


@app.get("/api/limits", response_model=GroqLimitsResponse)
def groq_limits() -> GroqLimitsResponse:
    settings = get_settings()
    payload = get_groq_rate_limiter().snapshot().to_dict()
    return GroqLimitsResponse(
        model=str(payload["model"]),
        usage={k: int(v) for k, v in payload["usage"].items()},
        limits={k: int(v) for k, v in payload["limits"].items()},
        remaining={k: int(v) for k, v in payload["remaining"].items()},
        ui_min_seconds_between_requests=settings.ui_min_seconds_between_requests,
    )


def _chat_response_to_api(result: ChatResponse) -> ChatApiResponse:
    return ChatApiResponse(
        type=result.type,
        text=result.text,
        citation_url=result.citation_url,
        last_updated_from_sources=result.last_updated_from_sources,
        disclaimer=result.disclaimer,
        scheme_id=result.scheme_id,
        facet=result.facet,
        refusal_kind=result.refusal_kind,
        retry_after_seconds=result.retry_after_seconds,
    )


@app.post("/api/chat", response_model=ChatApiResponse)
def chat(request: ChatRequest, response: Response) -> ChatApiResponse:
    settings = get_settings()

    try:
        result: ChatResponse = handle_chat(
            request.message,
            scheme_id=request.scheme_id,
            collection=_collection(),
        )
    except ValueError as exc:
        if "GROQ_API_KEY" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result.type == "answer" and not settings.groq_api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured")

    if result.type == "rate_limited":
        response.status_code = 429
        if result.retry_after_seconds is not None:
            response.headers["Retry-After"] = str(int(result.retry_after_seconds))

    return _chat_response_to_api(result)


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
