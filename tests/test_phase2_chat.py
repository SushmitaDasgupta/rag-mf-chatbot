"""Phase 2.5 — chat orchestrator tests (no live Groq)."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.rag.chat import handle_chat
from src.rag.retrieve import RetrievedChunk, RetrievalResult


def test_chat_miss_without_groq(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.rag.chat.retrieve_for_query",
        lambda *args, **kwargs: RetrievalResult(
            scheme_id="kotak_flexicap_direct_growth",
            source_url="https://www.indmoney.com/mutual-funds/kotak-flexicap-fund-direct-growth",
            effective_date="26 Aug 2026",
            facet="process_statements",
            structured_fact=None,
            chunks=[],
            retrieval_status="miss",
        ),
    )
    result = handle_chat(
        "How do I download my capital gains statement?",
        scheme_id="kotak_flexicap_direct_growth",
        collection=MagicMock(),
    )
    assert result.type == "miss"


def test_chat_performance_refusal(monkeypatch) -> None:
    result = handle_chat(
        "What was the return on Kotak Arbitrage Fund?",
        scheme_id="kotak_arbitrage_direct_growth",
        collection=MagicMock(),
    )
    assert result.type == "performance_refusal"
    assert result.citation_url is None
    assert "http" not in result.text.lower()


def test_chat_answer_with_mocked_groq(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.rag.chat.retrieve_for_query",
        lambda *args, **kwargs: RetrievalResult(
            scheme_id="kotak_large_cap_direct_growth",
            source_url="https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth",
            effective_date="26 Aug 2026",
            facet="expense_ratio",
            structured_fact={
                "facet": "expense_ratio",
                "value": "0.67%",
                "last_updated": "26 Aug 2026",
            },
            chunks=[
                RetrievedChunk(
                    chunk_id="row",
                    kind="overview_row",
                    text="Expense ratio | 0.67%",
                )
            ],
            retrieval_status="hit",
        ),
    )
    monkeypatch.setattr(
        "src.rag.chat.generate_answer",
        lambda *args, **kwargs: "The expense ratio is 0.67%.",
    )
    result = handle_chat(
        "What is the expense ratio?",
        scheme_id="kotak_large_cap_direct_growth",
        collection=MagicMock(),
    )
    assert result.type == "answer"
    assert result.citation_url is not None
    assert "Last updated from sources" in result.text
