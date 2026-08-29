"""P3.4 — Guardrail integration and refusal suite tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.rag.chat import handle_chat

FIXTURES_PATH = Path(__file__).resolve().parent / "refusal_cases.json"


def test_pii_blocks_pipeline(monkeypatch) -> None:
    retrieve_called = False
    generate_called = False

    def _retrieve(*args, **kwargs):
        nonlocal retrieve_called
        retrieve_called = True
        raise AssertionError("retrieve should not run on PII")

    def _generate(*args, **kwargs):
        nonlocal generate_called
        generate_called = True
        raise AssertionError("generate should not run on PII")

    monkeypatch.setattr("src.rag.chat.retrieve_for_query", _retrieve)
    monkeypatch.setattr("src.rag.chat.generate_answer", _generate)

    result = handle_chat(
        "My PAN is ABCDE1234F. What is the exit load of Kotak Liquid Fund?",
        collection=MagicMock(),
    )
    assert result.type == "refusal"
    assert result.refusal_kind == "pii"
    assert "ABCDE1234F" not in result.text
    assert not retrieve_called
    assert not generate_called


def test_advisory_refusal_has_no_edu_link(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.rag.chat.generate_answer",
        lambda *args, **kwargs: pytest.fail("generate should not run"),
    )
    result = handle_chat(
        "Should I invest in Kotak Large Cap Fund?",
        collection=MagicMock(),
    )
    assert result.type == "refusal"
    assert result.refusal_kind == "advisory"
    assert "amfiindia.com" not in result.text.lower()


def test_performance_refusal_has_no_links() -> None:
    result = handle_chat(
        "What was the 3 year return on Kotak Savings Fund?",
        scheme_id="kotak_savings_direct_growth",
        collection=MagicMock(),
    )
    assert result.type == "performance_refusal"
    assert result.refusal_kind == "performance"
    assert result.citation_url is None
    assert "http" not in result.text.lower()


def test_direct_regular_comparison_not_refused(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.rag.chat.generate_answer",
        lambda *args, **kwargs: "Direct and Regular plans have different expense ratios on the page.",
    )
    result = handle_chat(
        "Is Direct expense ratio lower/better than Regular on the Kotak Flexicap scheme page?",
        scheme_id="kotak_flexicap_direct_growth",
        collection=MagicMock(),
    )
    assert result.type != "refusal"
    assert result.type != "performance_refusal"


@pytest.fixture(scope="module")
def refusal_fixtures() -> list[dict]:
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case_id",
    [
        "R-ADV-01",
        "R-ADV-02",
        "R-ADV-03",
        "R-CMP-01",
        "R-PII-01",
        "R-PII-02",
        "R-PII-03",
        "R-JB-01",
        "R-OOC-01",
        "R-PERF-01",
        "R-PERF-02",
    ],
)
def test_refusal_cases_no_groq(case_id: str, refusal_fixtures, monkeypatch) -> None:
    case = next(item for item in refusal_fixtures if item["id"] == case_id)

    monkeypatch.setattr(
        "src.rag.chat.generate_answer",
        lambda *args, **kwargs: pytest.fail("generate should not run"),
    )
    monkeypatch.setattr(
        "src.rag.chat.retrieve_for_query",
        lambda *args, **kwargs: pytest.fail("retrieve should not run"),
    )

    result = handle_chat(case["query"], scheme_id=case.get("scheme_id"), collection=MagicMock())

    expect_type = case["expect_type"]
    assert result.type == expect_type

    if result.type in {"refusal", "performance_refusal", "unsupported"}:
        assert result.citation_url is None
        assert "http" not in result.text.lower()

    for forbidden in case.get("expect_forbidden_substrings") or []:
        assert forbidden.lower() not in result.text.lower()
