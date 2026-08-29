"""P2.3 — Groq-backed grounded answer generation."""

from __future__ import annotations

from typing import Any

from groq import Groq

from src.config import get_settings
from src.guardrails.groq_limits import (
    GroqRateLimitError,
    estimate_tokens_for_messages,
    get_groq_rate_limiter,
)
from src.rag.retrieve import RetrievalResult

SYSTEM_PROMPT = """You are a facts-only mutual fund FAQ assistant for Kotak schemes.
Answer ONLY using the provided context. Do not invent numbers, fees, URLs, or dates.
Use at most 3 short sentences. No investment advice, recommendations, or comparisons.
Do not include citations or footers — those are added by the application.
If the context does not contain the answer, say you do not have that information in the sources.
"""

MISS_TEMPLATE = (
    "I do not have enough information in the indexed scheme sources to answer that question."
)


def _format_context(retrieval: RetrievalResult) -> str:
    parts: list[str] = [
        f"Scheme: {retrieval.scheme_id}",
        f"Source URL (for citation): {retrieval.source_url}",
    ]
    if retrieval.effective_date:
        parts.append(f"Last updated: {retrieval.effective_date}")
    if retrieval.structured_fact:
        parts.append(
            "Structured fact (canonical value): "
            f"{retrieval.structured_fact['facet']} = {retrieval.structured_fact['value']}"
        )
    for i, chunk in enumerate(retrieval.chunks, 1):
        label = chunk.kind
        if chunk.expanded_from_parent:
            label += " (parent context)"
        parts.append(f"Chunk {i} [{label}]:\n{chunk.text}")
    return "\n\n".join(parts)


def build_messages(query: str, retrieval: RetrievalResult) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n{_format_context(retrieval)}\n\nQuestion: {query}",
        },
    ]


def generate_answer(
    query: str,
    retrieval: RetrievalResult,
    *,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float = 0.1,
    client: Any | None = None,
) -> str:
    """Generate a draft answer from retrieval context. Skips LLM on retrieval miss."""
    if retrieval.retrieval_status == "miss":
        return MISS_TEMPLATE

    settings = get_settings()
    key = api_key or settings.groq_api_key
    if not key:
        raise ValueError("GROQ_API_KEY is not set")

    groq_client = client or Groq(api_key=key)
    messages = build_messages(query, retrieval)
    limiter = get_groq_rate_limiter()
    estimated = estimate_tokens_for_messages(messages, max_output_tokens=256)
    limiter.acquire(estimated)

    try:
        response = groq_client.chat.completions.create(
            model=model or settings.groq_model,
            messages=messages,
            temperature=temperature,
            max_tokens=256,
        )
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if status == 429:
            raise GroqRateLimitError(
                "Groq API rate limit reached. Please wait and try again.",
                retry_after_seconds=60.0,
                snapshot=limiter.snapshot(),
            ) from exc
        raise

    usage = getattr(response, "usage", None)
    if usage is not None and getattr(usage, "total_tokens", None):
        limiter.reconcile_usage(int(usage.total_tokens))

    content = response.choices[0].message.content
    return (content or "").strip()
