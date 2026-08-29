"""P3.2 — Rules-first intent classifier for guardrails and retrieval routing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

IntentLabel = Literal[
    "factual_scheme_fact",
    "process_howto",
    "performance_request",
    "advisory_or_compare",
    "unclear",
]

FACET_PATTERNS: list[tuple[str, list[str]]] = [
    ("expense_ratio", ["expense ratio", "ter", "total expense", "expense"]),
    ("exit_load", ["exit load", "redemption charge", "redemption fee"]),
    ("min_sip", ["minimum sip", "min sip", "minimum investment", "min lumpsum", "min lump"]),
    ("benchmark", ["benchmark", "index against"]),
    ("riskometer", ["riskometer", "risk level", "risk rating", "risk category"]),
    ("lock_in", ["lock in", "lock-in", "lockin"]),
    ("holdings", ["top holdings", "holdings", "portfolio holdings"]),
    ("taxation", ["taxation", "tax ", "capital gains tax", "ltcg", "stcg"]),
    ("process_statements", ["account statement", "capital gains statement", "download statement"]),
    ("nav", [" nav", "net asset value", "current nav"]),
    ("aum", ["aum", "assets under management"]),
    ("fund_manager", ["fund manager", "who manages"]),
]

PERFORMANCE_PATTERNS = [
    "return on the fund",
    "what was the return",
    "3 year return",
    "3y return",
    "5 year return",
    "past performance",
    "historical return",
    "cagr",
    "how much return",
    "returns generated",
    "returned more",
    "xirr",
    "annualized return",
]

ADVISORY_PATTERNS = [
    "should i invest",
    "should i buy",
    "should i sell",
    "good fund for me",
    "good fund for you",
    "how much should i put",
    "how much should i invest",
    "recommend a fund",
    "recommend this fund",
    "recommend a ",
    "recommend ",
    "which fund saves",
    "ignore rules",
    "ignore your instructions",
    "investment advice",
    "allocate my portfolio",
    "portfolio allocation",
]

COMPARE_MARKERS = (
    "compare",
    " versus ",
    " vs ",
    "which is better",
    "which fund is better",
    "better fund",
)

SCHEME_KEYWORDS = (
    "large cap",
    "midcap",
    "mid cap",
    "flexicap",
    "flexi cap",
    "arbitrage",
    "liquid",
    "savings",
    "gold",
)


@dataclass
class QueryIntent:
    intent: IntentLabel
    facet: str | None
    confidence: float


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def detect_facet(query: str) -> str | None:
    norm = _normalize(query)
    for facet, patterns in FACET_PATTERNS:
        for pattern in patterns:
            if pattern in norm:
                return facet
    return None


def is_performance_query(query: str) -> bool:
    norm = _normalize(query)
    return any(p in norm for p in PERFORMANCE_PATTERNS)


def _is_factual_direct_regular_comparison(query: str) -> bool:
    """Direct vs Regular fee wording on the same scheme page — not advisory."""
    norm = _normalize(query)
    if not re.search(r"\b(direct|regular)\b", norm):
        return False
    if not re.search(r"\b(lower|better|cheaper|less|higher|more|worse)\b", norm):
        return False
    factual_markers = ("expense", "ter", "ratio", "exit load", "fee", "scheme page")
    return any(marker in norm for marker in factual_markers)


def _is_cross_scheme_comparison(query: str) -> bool:
    norm = _normalize(query)
    if not any(marker in norm for marker in COMPARE_MARKERS):
        return False
    scheme_hits = sum(1 for keyword in SCHEME_KEYWORDS if keyword in norm)
    if scheme_hits >= 2:
        return True
    if "compare" in norm and " and " in norm:
        return True
    return "which is better" in norm or "which fund is better" in norm


def is_advisory_query(query: str) -> bool:
    if _is_factual_direct_regular_comparison(query):
        return False

    norm = _normalize(query)
    if any(pattern in norm for pattern in ADVISORY_PATTERNS):
        return True
    return _is_cross_scheme_comparison(query)


def classify_query(query: str) -> QueryIntent:
    """Classify user intent with rules-first routing (no Groq classify call)."""
    if is_performance_query(query):
        return QueryIntent(intent="performance_request", facet=None, confidence=0.9)

    if is_advisory_query(query):
        return QueryIntent(intent="advisory_or_compare", facet=None, confidence=0.9)

    facet = detect_facet(query)
    if facet == "process_statements":
        return QueryIntent(intent="process_howto", facet=facet, confidence=0.85)

    if facet:
        return QueryIntent(intent="factual_scheme_fact", facet=facet, confidence=0.85)

    if any(w in _normalize(query) for w in ("how do i", "how to", "steps to")):
        return QueryIntent(intent="process_howto", facet=None, confidence=0.6)

    return QueryIntent(intent="unclear", facet=None, confidence=0.4)
