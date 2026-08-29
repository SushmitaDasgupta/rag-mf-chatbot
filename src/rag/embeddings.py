"""Embedding model helpers (BGE-aware prefixes + Chroma integration)."""

from __future__ import annotations

import os

# Suppress HuggingFace / tqdm progress bars before heavy imports (critical in CI logs).
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from typing import Any

import numpy as np
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer

from src.logging_config import get_logger, log_checkpoint

try:
    from transformers.utils.logging import disable_progress_bar

    disable_progress_bar()
except Exception:  # noqa: BLE001
    pass

logger = get_logger(__name__)

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
BGE_DOCUMENT_PREFIX = "Represent this document for retrieval: "

_EMBEDDING_FUNCTIONS: dict[str, "SentenceTransformerEmbedding"] = {}


def is_bge_model(model_name: str) -> bool:
    return "bge-" in model_name.lower()


def format_query_for_embedding(query: str, model_name: str) -> str:
    if is_bge_model(model_name):
        return f"{BGE_QUERY_PREFIX}{query}"
    return query


def format_document_for_embedding(text: str, model_name: str) -> str:
    if is_bge_model(model_name):
        return f"{BGE_DOCUMENT_PREFIX}{text}"
    return text


class SentenceTransformerEmbedding(EmbeddingFunction[Documents]):
    """Chroma embedding function with optional BGE query/document prefixes."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self._model_name = model_name
        log_checkpoint(
            logger,
            "P1.4",
            "load_embedding_model",
            "Loading sentence-transformers model for vector embeddings",
            model=model_name,
        )
        self._model = SentenceTransformer(model_name)
        log_checkpoint(
            logger,
            "P1.4",
            "embedding_model_ready",
            "Embedding model loaded",
            model=model_name,
            dims=self._model.get_sentence_embedding_dimension(),
        )

    def __call__(self, input: Documents) -> Embeddings:
        texts = [format_document_for_embedding(t, self._model_name) for t in input]
        return self._encode(texts)

    def embed_query(self, input: Documents) -> Embeddings:
        texts = [format_query_for_embedding(t, self._model_name) for t in input]
        return self._encode(texts)

    def _encode(self, texts: list[str]) -> Embeddings:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [np.asarray(v, dtype=np.float32).tolist() for v in vectors]

    @staticmethod
    def name() -> str:
        return "sentence_transformer_bge_aware"

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "SentenceTransformerEmbedding":
        return get_embedding_function(str(config["model_name"]))

    def get_config(self) -> dict[str, Any]:
        return {"model_name": self._model_name}


def get_embedding_function(model_name: str) -> SentenceTransformerEmbedding:
    """Return a cached embedding function (Chroma may call build_from_config repeatedly)."""
    cached = _EMBEDDING_FUNCTIONS.get(model_name)
    if cached is not None:
        return cached
    cached = SentenceTransformerEmbedding(model_name=model_name)
    _EMBEDDING_FUNCTIONS[model_name] = cached
    return cached
