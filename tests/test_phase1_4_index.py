"""Phase 1.4 — embed, index, structured facts, retrieval smoke probes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from src.ingest.index import (
    CORE_FACETS,
    chunk_to_metadata,
    dedupe_chunks_by_content_hash,
    get_chroma_collection,
    index_for_search,
    is_tier0_fact_present,
    load_scheme_chunks,
    run_index,
    upsert_scheme_chunks,
    validate_structured_facts,
)

ALLOWED_URL = (
    "https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth"
)


class _HashEmbedding(EmbeddingFunction[Documents]):
    """Deterministic tiny embeddings for Chroma tests (no model download)."""

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


def _chunk(
    *,
    chunk_id: str,
    kind: str,
    text: str,
    facet: str | None = None,
    content_hash: str | None = None,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "doc_id": "kotak_large_cap_direct_growth",
        "scheme_id": "kotak_large_cap_direct_growth",
        "scheme_name": "Kotak Large Cap Fund – Direct Growth",
        "doc_type": "scheme_reference_page",
        "source_url": ALLOWED_URL,
        "effective_date": "26 Aug 2026",
        "ingested_at": "2026-08-27T09:45:00+00:00",
        "section": "Overview",
        "facet": facet,
        "facets": [facet] if facet else [],
        "parent_id": None,
        "ordinal": 0,
        "kind": kind,
        "text": text,
        "body": text,
        "token_estimate": 10,
        "content_hash": content_hash or f"hash-{chunk_id}",
    }


def test_dedupe_keeps_higher_priority_kind() -> None:
    chunks = [
        _chunk(
            chunk_id="a",
            kind="faq",
            text="faq body",
            content_hash="same-hash",
        ),
        _chunk(
            chunk_id="b",
            kind="overview_row",
            text="row body",
            facet="expense_ratio",
            content_hash="same-hash",
        ),
    ]
    deduped, removed = dedupe_chunks_by_content_hash(chunks)
    assert removed == 1
    assert len(deduped) == 1
    assert deduped[0]["kind"] == "overview_row"


def test_overview_parent_not_searchable() -> None:
    parent = _chunk(chunk_id="p", kind="overview_parent", text="parent table")
    row = _chunk(
        chunk_id="r",
        kind="overview_row",
        text="row",
        facet="exit_load",
    )
    assert index_for_search(parent) is False
    assert index_for_search(row) is True
    assert chunk_to_metadata(parent)["index_for_search"] is False


def test_validate_structured_facts(tmp_path: Path) -> None:
    facts_path = tmp_path / "structured_facts.yaml"
    facts_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "fields": list(CORE_FACETS),
                "schemes": {
                    "kotak_large_cap_direct_growth": {
                        "source_url": ALLOWED_URL,
                        "expense_ratio": "0.67%",
                        "exit_load": "1.0%",
                        "min_sip": "₹100",
                        "riskometer": "Very High Risk",
                        "benchmark": "Nifty 100 TR INR",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    report = validate_structured_facts(
        facts_path,
        scheme_ids=["kotak_large_cap_direct_growth"],
    )
    assert report["status"] == "success"


def test_tier0_rejects_not_in_corpus() -> None:
    assert is_tier0_fact_present("0.67%") is True
    assert is_tier0_fact_present("--") is True
    assert is_tier0_fact_present("not in corpus") is False
    assert is_tier0_fact_present(None) is False


def test_idempotent_upsert_does_not_duplicate(tmp_path: Path) -> None:
    store = tmp_path / "vs"
    coll = get_chroma_collection(
        vector_store_path=store,
        collection_name="test_chunks",
        embedding_model="unused",
        embedding_function=_HashEmbedding(),
    )
    chunks = [
        _chunk(
            chunk_id="r1",
            kind="overview_row",
            text="[Scheme] expense ratio 0.67%",
            facet="expense_ratio",
        ),
        _chunk(
            chunk_id="r2",
            kind="overview_row",
            text="[Scheme] exit load 1.0%",
            facet="exit_load",
        ),
    ]
    upsert_scheme_chunks(coll, doc_id="kotak_large_cap_direct_growth", chunks=chunks)
    assert coll.count() == 2

    upsert_scheme_chunks(coll, doc_id="kotak_large_cap_direct_growth", chunks=chunks)
    assert coll.count() == 2


def test_load_scheme_chunks_from_repo_chunks_dir() -> None:
    chunks_dir = Path("data/processed/chunks")
    if not (chunks_dir / "kotak_large_cap_direct_growth.json").exists():
        pytest.skip("chunk artifacts not present")
    chunks = load_scheme_chunks(chunks_dir, "kotak_large_cap_direct_growth")
    assert chunks
    assert all(c.get("source_url") == ALLOWED_URL for c in chunks)


def test_run_index_single_scheme(tmp_path: Path) -> None:
    chunks_dir = Path("data/processed/chunks")
    facts_src = Path("data/processed/structured_facts.yaml")
    manifest = Path("data/manifest.yaml")
    if not chunks_dir.exists() or not facts_src.exists():
        pytest.skip("corpus artifacts not present")

    work = tmp_path / "work"
    chunks_work = work / "chunks"
    chunks_work.mkdir(parents=True)
    scheme_id = "kotak_large_cap_direct_growth"
    src = chunks_dir / f"{scheme_id}.json"
    payload = json.loads(src.read_text(encoding="utf-8"))
    (chunks_work / f"{scheme_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    facts = yaml.safe_load(facts_src.read_text(encoding="utf-8"))
    facts["schemes"] = {scheme_id: facts["schemes"][scheme_id]}
    facts_path = work / "structured_facts.yaml"
    facts_path.write_text(yaml.safe_dump(facts), encoding="utf-8")

    manifest_data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    manifest_data["schemes"] = [
        s for s in manifest_data["schemes"] if s["scheme_id"] == scheme_id
    ]
    manifest_path = work / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest_data), encoding="utf-8")

    store = work / "vectorstore"
    summary = run_index(
        manifest_path=manifest_path,
        chunks_dir=chunks_work,
        structured_facts_path=facts_path,
        vector_store_path=store,
        collection_name="probe_test",
        embedding_model="unused",
        scheme_ids={scheme_id},
        embedding_function=_HashEmbedding(),
    )
    assert summary.ok
    assert summary.total_vectors > 0
    assert (chunks_work / "retrieval_probe_log.yaml").exists()
    assert (work / "structured_facts_report.yaml").exists()


def test_get_tier0_fact_from_repo_facts() -> None:
    from src.rag.structured_facts import get_tier0_fact

    facts_path = Path("data/processed/structured_facts.yaml")
    if not facts_path.exists():
        pytest.skip("structured facts not present")
    fact = get_tier0_fact(
        "kotak_large_cap_direct_growth",
        "expense_ratio",
        facts_path=facts_path,
    )
    assert fact is not None
    assert fact["value"] == "0.67%"
    assert fact["source_url"] == ALLOWED_URL
