"""P2.1 — Map user text to a supported scheme_id or ask to clarify."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Literal

from src.config import get_settings
from src.ingest.fetch import load_manifest_schemes

ResolveStatus = Literal["resolved", "clarify", "unsupported"]


@dataclass
class SchemeCandidate:
    scheme_id: str
    display_name: str
    score: float
    match_reason: str


@dataclass
class SchemeResolveResult:
    status: ResolveStatus
    scheme_id: str | None = None
    display_name: str | None = None
    candidates: list[SchemeCandidate] = field(default_factory=list)


def _normalize(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^\w\s-]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _tokens(text: str) -> set[str]:
    stop = {"kotak", "fund", "direct", "growth", "the", "a", "an", "of", "for"}
    return {t for t in _normalize(text).split() if t and t not in stop}


def _aliases_for_scheme(scheme: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (alias_text, match_reason) pairs for a manifest scheme."""
    scheme_id = str(scheme["scheme_id"])
    display_name = str(scheme["display_name"])
    category = str(scheme.get("category") or "")

    aliases: list[tuple[str, str]] = [
        (scheme_id, "scheme_id"),
        (scheme_id.replace("_", " "), "scheme_id_tokens"),
        (display_name, "display_name"),
        (_normalize(display_name), "display_name_normalized"),
    ]

    slug = scheme_id.removeprefix("kotak_").replace("_", " ")
    aliases.append((slug, "scheme_slug"))

    if category:
        aliases.append((f"kotak {category.lower()}", "category"))
        aliases.append((category.lower(), "category_short"))

    # Common short forms from display names.
    short = display_name.replace("Kotak ", "").replace(" – Direct Growth", "")
    short = short.replace(" – Growth Direct", "")
    aliases.append((short.lower(), "short_name"))

    return aliases


def _score_query_to_scheme(query: str, scheme: dict[str, Any]) -> tuple[float, str]:
    norm_query = _normalize(query)
    if not norm_query:
        return 0.0, ""

    scheme_id = str(scheme["scheme_id"])
    best_score = 0.0
    best_reason = ""

    for alias, reason in _aliases_for_scheme(scheme):
        norm_alias = _normalize(alias)
        if not norm_alias:
            continue
        if norm_alias == norm_query:
            return 1.0, reason
        if norm_alias in norm_query or norm_query in norm_alias:
            score = 0.92
            if score > best_score:
                best_score, best_reason = score, reason
            continue
        ratio = SequenceMatcher(None, norm_query, norm_alias).ratio()
        if ratio > best_score:
            best_score, best_reason = ratio, reason

    query_tokens = _tokens(norm_query)
    alias_tokens = _tokens(scheme_id.replace("_", " "))
    alias_tokens |= _tokens(str(scheme["display_name"]))
    overlap = query_tokens & alias_tokens
    if overlap:
        token_score = len(overlap) / max(len(query_tokens), 1)
        token_score = min(0.88, 0.55 + token_score * 0.35)
        if token_score > best_score:
            best_score, best_reason = token_score, f"token_overlap:{','.join(sorted(overlap))}"

    return best_score, best_reason


def resolve_scheme(
    query: str,
    *,
    manifest_path: str | None = None,
    min_score: float = 0.55,
    clarify_gap: float = 0.08,
) -> SchemeResolveResult:
    """
    Resolve a user message to a scheme_id.

  * Unique strong match → resolved
  * Multiple close matches → clarify with candidates
  * No match → unsupported
    """
    settings = get_settings()
    schemes = load_manifest_schemes(manifest_path or settings.manifest_path)

    scored: list[SchemeCandidate] = []
    for scheme in schemes:
        score, reason = _score_query_to_scheme(query, scheme)
        if score >= min_score:
            scored.append(
                SchemeCandidate(
                    scheme_id=str(scheme["scheme_id"]),
                    display_name=str(scheme["display_name"]),
                    score=score,
                    match_reason=reason,
                )
            )

    scored.sort(key=lambda c: c.score, reverse=True)

    if not scored:
        return SchemeResolveResult(status="unsupported")

    top = scored[0]
    runners_up = [c for c in scored[1:] if top.score - c.score <= clarify_gap]

    if runners_up:
        return SchemeResolveResult(
            status="clarify",
            candidates=scored[:5],
        )

    return SchemeResolveResult(
        status="resolved",
        scheme_id=top.scheme_id,
        display_name=top.display_name,
        candidates=[top],
    )


def resolve_scheme_or_id(
    query: str,
    *,
    scheme_id: str | None = None,
    manifest_path: str | None = None,
) -> SchemeResolveResult:
    """If scheme_id is provided and valid, use it; otherwise resolve from query text."""
    settings = get_settings()
    schemes = load_manifest_schemes(manifest_path or settings.manifest_path)
    known_ids = {str(s["scheme_id"]) for s in schemes}

    if scheme_id:
        if scheme_id not in known_ids:
            return SchemeResolveResult(status="unsupported")
        display = next(
            str(s["display_name"]) for s in schemes if str(s["scheme_id"]) == scheme_id
        )
        return SchemeResolveResult(
            status="resolved",
            scheme_id=scheme_id,
            display_name=display,
            candidates=[
                SchemeCandidate(
                    scheme_id=scheme_id,
                    display_name=display,
                    score=1.0,
                    match_reason="explicit_scheme_id",
                )
            ],
        )

    return resolve_scheme(query, manifest_path=manifest_path)
