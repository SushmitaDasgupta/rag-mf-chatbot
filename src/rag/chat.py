"""Phase 3 — chat orchestrator with guardrails: PII → intent → (refusal | RAG)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from chromadb import Collection

from src.config import get_settings
from src.guardrails.amc_scope import is_out_of_corpus_amc
from src.guardrails.groq_limits import GroqRateLimitError
from src.guardrails.intent import classify_query
from src.guardrails.pii import check_pii
from src.guardrails.refusals import (
    advisory_refusal,
    performance_refusal,
    pii_refusal,
    unsupported_scheme_message,
)
from src.ingest.index import get_chroma_collection
from src.rag.generate import MISS_TEMPLATE, generate_answer
from src.rag.retrieve import RetrievalResult, retrieve_for_query
from src.rag.scheme_resolver import SchemeResolveResult, resolve_scheme_or_id
from src.rag.validate import DISCLAIMER, ValidatedResponse, validate_and_format

ResponseType = Literal[
    "answer",
    "clarify",
    "unsupported",
    "miss",
    "refusal",
    "performance_refusal",
    "rate_limited",
]


@dataclass
class ChatResponse:
    type: ResponseType
    text: str
    citation_url: str | None = None
    last_updated_from_sources: str | None = None
    disclaimer: str = DISCLAIMER
    scheme_id: str | None = None
    facet: str | None = None
    refusal_kind: str | None = None
    retry_after_seconds: float | None = None


def _format_clarify(result: SchemeResolveResult) -> str:
    lines = ["Which Kotak scheme did you mean? Please pick one:"]
    for candidate in result.candidates:
        lines.append(f"- {candidate.display_name} (`{candidate.scheme_id}`)")
    return "\n".join(lines)


def _parse_last_updated(retrieval: RetrievalResult) -> str | None:
    if retrieval.structured_fact and retrieval.structured_fact.get("last_updated"):
        return str(retrieval.structured_fact["last_updated"])
    return retrieval.effective_date


def _refusal_response(payload, *, response_type: ResponseType = "refusal") -> ChatResponse:
    return ChatResponse(
        type=response_type,
        text=payload.text,
        citation_url=None,
        disclaimer=payload.disclaimer,
        refusal_kind=payload.kind,
    )


def handle_chat(
    message: str,
    *,
    scheme_id: str | None = None,
    collection: Collection | None = None,
    groq_client: Any | None = None,
) -> ChatResponse:
    """End-to-end chat pipeline: guardrails → resolve → retrieve → generate → validate."""
    if check_pii(message).detected:
        return _refusal_response(pii_refusal())

    if is_out_of_corpus_amc(message):
        return ChatResponse(type="unsupported", text=unsupported_scheme_message())

    intent = classify_query(message)
    if intent.intent == "advisory_or_compare":
        return _refusal_response(advisory_refusal())

    resolved = resolve_scheme_or_id(message, scheme_id=scheme_id)

    if intent.intent == "performance_request":
        return _refusal_response(performance_refusal(), response_type="performance_refusal")

    if resolved.status == "clarify":
        return ChatResponse(type="clarify", text=_format_clarify(resolved))
    if resolved.status == "unsupported":
        return ChatResponse(type="unsupported", text=unsupported_scheme_message())

    assert resolved.scheme_id is not None

    settings = get_settings()
    coll = collection
    if coll is None:
        coll = get_chroma_collection(
            vector_store_path=settings.vector_store_path,
            collection_name=settings.chroma_collection,
            embedding_model=settings.embedding_model,
        )

    retrieval = retrieve_for_query(message, resolved.scheme_id, collection=coll, intent=intent)

    if retrieval.retrieval_status == "miss":
        return ChatResponse(
            type="miss",
            text=MISS_TEMPLATE,
            scheme_id=resolved.scheme_id,
            facet=intent.facet,
            disclaimer=DISCLAIMER,
        )

    try:
        draft = generate_answer(message, retrieval, client=groq_client)
    except GroqRateLimitError as exc:
        return ChatResponse(
            type="rate_limited",
            text=str(exc),
            scheme_id=resolved.scheme_id,
            facet=intent.facet,
            disclaimer=DISCLAIMER,
            retry_after_seconds=exc.retry_after_seconds,
        )

    validated: ValidatedResponse = validate_and_format(
        draft,
        citation_url=retrieval.source_url,
        last_updated=_parse_last_updated(retrieval),
    )

    if validated.status == "rejected":
        return ChatResponse(
            type="miss",
            text=validated.text,
            scheme_id=resolved.scheme_id,
            facet=intent.facet,
            disclaimer=DISCLAIMER,
        )

    return ChatResponse(
        type="answer",
        text=validated.text,
        citation_url=validated.citation_url,
        last_updated_from_sources=validated.last_updated_from_sources,
        disclaimer=validated.disclaimer,
        scheme_id=resolved.scheme_id,
        facet=intent.facet,
    )
