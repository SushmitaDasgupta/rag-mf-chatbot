"""Phase 2.4 — output validator tests."""

from __future__ import annotations

from src.guardrails.citations import PROBLEM_STATEMENT_SCHEME_URLS
from src.rag.validate import DISCLAIMER, _strip_footer, validate_and_format

ALLOWED_URL = next(iter(PROBLEM_STATEMENT_SCHEME_URLS))


def test_validator_adds_citation_and_footer() -> None:
    result = validate_and_format(
        "The expense ratio is 0.67%.",
        citation_url=ALLOWED_URL,
        last_updated="2026-08-26",
    )
    assert result.status in {"ok", "repaired"}
    assert ALLOWED_URL in result.text
    assert "Last updated from sources: 2026-08-26" in result.text
    assert result.disclaimer == DISCLAIMER


def test_validator_truncates_long_answers() -> None:
    draft = "One. Two. Three. Four. Five."
    result = validate_and_format(
        draft,
        citation_url=ALLOWED_URL,
        last_updated="2026-08-26",
    )
    assert result.status == "repaired"
    body, _ = _strip_footer(result.text)
    answer_part = body.split("\n\nSource:")[0]
    assert "Four." not in answer_part
    assert "Five." not in answer_part


def test_validator_rejects_non_allowlisted_url() -> None:
    result = validate_and_format(
        "Answer text.",
        citation_url="https://example.com/bad",
        last_updated="2026-08-26",
    )
    assert result.status == "rejected"
    assert result.citation_url is None


def test_validator_strips_model_urls() -> None:
    result = validate_and_format(
        "See https://evil.example.com for details. The exit load is 1%.",
        citation_url=ALLOWED_URL,
        last_updated="2026-08-26",
    )
    assert "evil.example.com" not in result.text
    assert ALLOWED_URL in result.text
