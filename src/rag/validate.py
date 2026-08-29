"""P2.4 — Enforce the normative response contract before returning to callers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.guardrails.citations import is_allowed_citation

DISCLAIMER = "Facts-only. No investment advice."

ADVISORY_PHRASES = [
    "you should invest",
    "i recommend",
    "we recommend",
    "buy this fund",
    "sell this fund",
    "better fund",
    "will outperform",
    "guaranteed return",
]

URL_PATTERN = re.compile(r"https?://[^\s)>\"]+")


@dataclass
class ValidatedResponse:
    status: Literal["ok", "repaired", "rejected"]
    text: str
    citation_url: str | None
    last_updated_from_sources: str | None
    disclaimer: str = DISCLAIMER


def _strip_footer(text: str) -> tuple[str, str | None]:
    match = re.search(r"\n*Last updated from sources:\s*(\S+)\s*$", text, flags=re.IGNORECASE)
    if not match:
        return text.strip(), None
    body = text[: match.start()].strip()
    return body, match.group(1)


def _count_sentences(text: str) -> int:
    cleaned = text.strip()
    if not cleaned:
        return 0
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return len([p for p in parts if p.strip()])


def _truncate_to_sentences(text: str, max_sentences: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [p for p in parts if p.strip()][:max_sentences]
    return " ".join(kept).strip()


def _remove_urls(text: str) -> str:
    return URL_PATTERN.sub("", text).strip()


def _has_advisory_language(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in ADVISORY_PHRASES)


def validate_and_format(
    draft: str,
    *,
    citation_url: str | None,
    last_updated: str | None,
    max_sentences: int = 3,
) -> ValidatedResponse:
    """
    Enforce ≤3 sentences, one allowlisted citation URL, and last-updated footer.
    """
    if not citation_url or not is_allowed_citation(citation_url):
        return ValidatedResponse(
            status="rejected",
            text=(
                "I can only cite the allowlisted scheme reference URLs from the problem statement."
            ),
            citation_url=None,
            last_updated_from_sources=last_updated,
        )

    body, _ = _strip_footer(draft)
    body = _remove_urls(body)
    status: Literal["ok", "repaired"] = "ok"

    if _has_advisory_language(body):
        body = (
            "I can only share factual scheme information from the indexed sources, "
            "not investment advice."
        )
        status = "repaired"

    if _count_sentences(body) > max_sentences:
        body = _truncate_to_sentences(body, max_sentences)
        status = "repaired"

    if not body:
        body = "I do not have enough information in the indexed scheme sources to answer that question."
        status = "repaired"

    footer_date = last_updated or "unknown"
    final_text = f"{body}\n\nSource: {citation_url}\nLast updated from sources: {footer_date}"

    return ValidatedResponse(
        status=status,
        text=final_text,
        citation_url=citation_url,
        last_updated_from_sources=footer_date,
    )
