"""Backward-compatible re-export — canonical implementation is in src.guardrails.intent."""

from __future__ import annotations

from src.guardrails.intent import (  # noqa: F401
    FACET_PATTERNS,
    IntentLabel,
    QueryIntent,
    classify_query,
    detect_facet,
    is_advisory_query,
    is_performance_query,
)

__all__ = [
    "FACET_PATTERNS",
    "IntentLabel",
    "QueryIntent",
    "classify_query",
    "detect_facet",
    "is_advisory_query",
    "is_performance_query",
]
