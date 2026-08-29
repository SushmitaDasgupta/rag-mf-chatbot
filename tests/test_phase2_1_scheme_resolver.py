"""Phase 2.1 — scheme resolver tests."""

from __future__ import annotations

from src.rag.scheme_resolver import resolve_scheme, resolve_scheme_or_id


def test_resolves_canonical_display_name() -> None:
    result = resolve_scheme("What is the expense ratio of Kotak Large Cap Fund – Direct Growth?")
    assert result.status == "resolved"
    assert result.scheme_id == "kotak_large_cap_direct_growth"


def test_resolves_scheme_slug() -> None:
    result = resolve_scheme("kotak arbitrage direct growth expense ratio")
    assert result.status == "resolved"
    assert result.scheme_id == "kotak_arbitrage_direct_growth"


def test_explicit_scheme_id_bypasses_resolver() -> None:
    result = resolve_scheme_or_id(
        "What is the exit load?",
        scheme_id="kotak_liquid_growth_direct",
    )
    assert result.status == "resolved"
    assert result.scheme_id == "kotak_liquid_growth_direct"


def test_unsupported_foreign_scheme() -> None:
    result = resolve_scheme("What is the expense ratio of HDFC Top 100 Fund?")
    assert result.status == "unsupported"


def test_ambiguous_large_cap_vs_flexicap() -> None:
    result = resolve_scheme("Tell me about Kotak fund")
    assert result.status in {"clarify", "unsupported"}
