"""Embedding model helpers (BGE prefixes)."""

from src.rag.embeddings import (
    BGE_DOCUMENT_PREFIX,
    BGE_QUERY_PREFIX,
    DEFAULT_EMBEDDING_MODEL,
    _EMBEDDING_FUNCTIONS,
    format_document_for_embedding,
    format_query_for_embedding,
    get_embedding_function,
    is_bge_model,
)


def test_default_model_is_bge_small() -> None:
    assert DEFAULT_EMBEDDING_MODEL == "BAAI/bge-small-en-v1.5"


def test_bge_prefixes_applied() -> None:
    model = DEFAULT_EMBEDDING_MODEL
    assert is_bge_model(model)
    assert format_query_for_embedding("What is the expense ratio?", model).startswith(
        BGE_QUERY_PREFIX
    )
    assert format_document_for_embedding("chunk text", model).startswith(
        BGE_DOCUMENT_PREFIX
    )


def test_non_bge_has_no_prefix() -> None:
    model = "sentence-transformers/all-MiniLM-L6-v2"
    assert not is_bge_model(model)
    q = "What is the exit load?"
    assert format_query_for_embedding(q, model) == q


def test_get_embedding_function_is_cached(monkeypatch) -> None:
    _EMBEDDING_FUNCTIONS.clear()
    calls = {"count": 0}

    class FakeEmbedding:
        def __init__(self, model_name: str) -> None:
            calls["count"] += 1
            self._model_name = model_name

    monkeypatch.setattr("src.rag.embeddings.SentenceTransformerEmbedding", FakeEmbedding)
    first = get_embedding_function("test-model")
    second = get_embedding_function("test-model")
    assert first is second
    assert calls["count"] == 1
