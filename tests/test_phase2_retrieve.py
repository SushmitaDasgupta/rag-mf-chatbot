"""Phase 2 — intent and retrieval unit tests."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from src.rag.intent import classify_query, detect_facet
from src.rag.retrieve import retrieve

ALLOWED_URL = (
    "https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth"
)


class _HashEmbedding(EmbeddingFunction[Documents]):
    def __call__(self, input: Documents) -> Embeddings:
        vectors: list[list[float]] = []
        for text in input:
            vec = np.zeros(32, dtype=np.float32)
            vec[hash(text) % 32] = 1.0
            vectors.append(vec.tolist())
        return vectors

    @staticmethod
    def name() -> str:
        return "hash_test"

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "_HashEmbedding":
        return _HashEmbedding()

    def get_config(self) -> dict[str, Any]:
        return {}


def _meta(**kwargs: Any) -> dict[str, Any]:
    base = {
        "scheme_id": "kotak_large_cap_direct_growth",
        "source_url": ALLOWED_URL,
        "effective_date": "26 Aug 2026",
        "index_for_search": True,
        "parent_id": "",
        "ordinal": 0,
    }
    base.update(kwargs)
    return base


@pytest.fixture()
def collection(tmp_path):
    import chromadb

    from src.ingest.index import get_chroma_collection

    client = chromadb.PersistentClient(path=str(tmp_path / "vs"))
    coll = get_chroma_collection(
        vector_store_path=str(tmp_path / "vs"),
        collection_name="test",
        embedding_model="hash-test",
        embedding_function=_HashEmbedding(),
        recreate=True,
    )
    coll.add(
        ids=["row-expense", "faq-expense", "prose-tax"],
        documents=[
            "[Scheme] Field | Value\nExpense ratio | 0.67%",
            "Q: expense ratio?\nA: 0.67%",
            "Taxation section prose about expense ratio tags",
        ],
        metadatas=[
            _meta(chunk_id="row-expense", kind="overview_row", facet="expense_ratio", section="Overview / Expense ratio"),
            _meta(chunk_id="faq-expense", kind="faq", facet="", section="FAQ expense"),
            _meta(chunk_id="prose-tax", kind="prose", facet="expense_ratio", section="Taxation"),
        ],
    )
    return coll


def test_detect_facet_expense_ratio() -> None:
    assert detect_facet("What is the expense ratio?") == "expense_ratio"


def test_classify_performance_intent() -> None:
    intent = classify_query("What was the 3 year return on the fund?")
    assert intent.intent == "performance_request"


def test_retrieve_prefers_overview_row(collection) -> None:
    result = retrieve(
        "What is the expense ratio?",
        "kotak_large_cap_direct_growth",
        facet="expense_ratio",
        collection=collection,
        skip_dense_if_oracle=True,
    )
    assert result.retrieval_status == "hit"
    assert result.chunks[0].kind == "overview_row"


def test_process_statements_miss(collection) -> None:
    result = retrieve(
        "How do I download my capital gains statement?",
        "kotak_large_cap_direct_growth",
        facet="process_statements",
        collection=collection,
    )
    assert result.retrieval_status == "miss"
    assert result.chunks == []
