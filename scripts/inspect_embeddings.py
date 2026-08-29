#!/usr/bin/env python3
"""
Inspect the Chroma vector index: stats, sample embedding vectors, and retrieval demos.

Usage:
    python scripts/inspect_embeddings.py
    python scripts/inspect_embeddings.py --query "What is the exit load?" --scheme kotak_large_cap_direct_growth
    python scripts/inspect_embeddings.py --embedding-sample kotak_arbitrage_direct_growth
    python scripts/inspect_embeddings.py --list-chunks kotak_arbitrage_direct_growth
    python scripts/inspect_embeddings.py --list-chunks kotak_arbitrage_direct_growth --preview-dims 12 --text-lines 6
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

# Allow running as `python scripts/inspect_embeddings.py`
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import get_settings
from src.ingest.fetch import load_manifest_schemes
from src.ingest.index import (
    FACET_PROBE_QUERIES,
    get_chroma_collection,
    probe_retrieve,
)
from src.rag.embeddings import (
    format_document_for_embedding,
    format_query_for_embedding,
    get_embedding_function,
)
from src.rag.structured_facts import get_tier0_fact

EXAMPLE_QUERIES: list[dict[str, str]] = [
    {
        "scheme_id": "kotak_arbitrage_direct_growth",
        "facet": "expense_ratio",
        "query": "What is the expense ratio of Kotak Arbitrage Fund?",
    },
    {
        "scheme_id": "kotak_large_cap_direct_growth",
        "facet": "exit_load",
        "query": "What is the exit load for Kotak Large Cap Fund?",
    },
    {
        "scheme_id": "kotak_liquid_growth_direct",
        "facet": "min_sip",
        "query": "What is the minimum SIP for Kotak Liquid Fund?",
    },
]


def _header(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(title)
    print("=" * 72)


def _subheader(title: str) -> None:
    print(f"\n{'-' * 72}")
    print(title)
    print("-" * 72)


def _print_kv(key: str, value: Any, *, indent: int = 2) -> None:
    pad = " " * indent
    print(f"{pad}{key:14} {value}")


def _truncate(text: str, width: int = 72) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 3] + "..."


def _embedding_summary(vector: np.ndarray) -> str:
    return (
        f"{vector.shape[0]} dimensions | "
        f"L2 norm {float(np.linalg.norm(vector)):.6f} | "
        f"min {float(vector.min()):.6f} | max {float(vector.max()):.6f}"
    )


def _print_embedding(
    vector: np.ndarray,
    *,
    preview_dims: int,
    show_full: bool,
    values_per_line: int = 4,
) -> None:
    _print_kv("summary", _embedding_summary(vector))
    limit = vector.shape[0] if show_full else min(preview_dims, vector.shape[0])
    label = "all values" if show_full else f"first {limit} of {vector.shape[0]} values"
    print()
    print(f"  embedding ({label}):")
    pad = " " * 4
    for start in range(0, limit, values_per_line):
        parts: list[str] = []
        for idx in range(start, min(start + values_per_line, limit)):
            parts.append(f"[{idx:3d}] {vector[idx]:+.6f}")
        print(pad + "  ".join(parts))
    if not show_full and limit < vector.shape[0]:
        print(f"{pad}... ({vector.shape[0] - limit} more dimensions; use --full-embedding to print all)")


def _normalize_embeddings(raw: Any, count: int) -> list[np.ndarray | None]:
    """Chroma may return embeddings as a list or a 2-D numpy array."""
    if raw is None:
        return [None] * count
    if isinstance(raw, np.ndarray):
        if raw.ndim == 1:
            return [raw.astype(np.float32)]
        return [raw[i].astype(np.float32) for i in range(raw.shape[0])]
    return [
        np.array(emb, dtype=np.float32) if emb is not None else None
        for emb in raw
    ]


def print_index_status(collection, settings) -> None:
    _header("INDEX STATUS")
    print(f"Embedding model : {settings.embedding_model}")
    print(f"Vector store    : {settings.vector_store_path}")
    print(f"Collection      : {settings.chroma_collection}")
    print(f"Total vectors   : {collection.count()}")

    peek = collection.get(
        limit=500,
        include=["metadatas"],
    )
    metas = peek.get("metadatas") or []
    kinds = Counter(str(m.get("kind") or "unknown") for m in metas)
    schemes = Counter(str(m.get("scheme_id") or "unknown") for m in metas)

    _subheader("Chunks by kind")
    for kind, count in kinds.most_common():
        print(f"  {kind:16} {count}")

    _subheader("Chunks by scheme")
    for scheme_id, count in sorted(schemes.items()):
        print(f"  {scheme_id:35} {count}")


def print_embedding_sample(
    collection,
    *,
    model_name: str,
    scheme_id: str | None,
    chunk_id: str | None,
    preview_dims: int,
    show_full: bool,
) -> None:
    _header("EMBEDDING SAMPLE")

    if chunk_id:
        result = collection.get(ids=[chunk_id], include=["embeddings", "metadatas", "documents"])
        if not result["ids"]:
            print(f"No chunk found for id={chunk_id!r}")
            return
        idx = 0
    else:
        result = collection.get(
            where={"$and": [
                {"scheme_id": {"$eq": scheme_id}},
                {"index_for_search": {"$eq": True}},
            ]} if scheme_id else None,
            limit=50,
            include=["embeddings", "metadatas", "documents"],
        )
        if not result["ids"]:
            result = collection.get(
                where={"scheme_id": scheme_id} if scheme_id else None,
                limit=1,
                include=["embeddings", "metadatas", "documents"],
            )
        if not result["ids"]:
            print("No chunks found in index.")
            return
        # Prefer overview_row for a clearer facet demo
        pick = 0
        for i, meta in enumerate(result.get("metadatas") or []):
            if (meta or {}).get("kind") == "overview_row":
                pick = i
                break
        idx = pick
        chunk_id = result["ids"][idx]

    meta = result["metadatas"][idx] or {}
    doc = result["documents"][idx] or ""
    stored = _normalize_embeddings(result.get("embeddings"), len(result["ids"]))[idx]
    if stored is None:
        print("No embedding stored for this chunk.")
        return

    _subheader("Chunk identity")
    _print_kv("scheme_id", meta.get("scheme_id") or scheme_id or "(unknown)")
    _print_kv("chunk_id", chunk_id)
    _print_kv("doc_id", meta.get("doc_id") or "(none)")
    _print_kv("kind", meta.get("kind") or "(none)")
    _print_kv("facet", meta.get("facet") or "(none)")
    _print_kv("section", meta.get("section") or "(none)")
    _print_kv("searchable", "yes" if meta.get("index_for_search", True) else "no (parent-only)")

    _subheader("Chunk text")
    for line in doc.splitlines()[:8]:
        print(f"    {line}")

    _subheader("Stored embedding vector (from Chroma)")
    _print_embedding(stored, preview_dims=preview_dims, show_full=show_full)
    print("  note: BGE embeddings are L2-normalized, so norm should be ~1.0")

    # Re-embed live to show query vs document prefix effect (BGE)
    ef = get_embedding_function(model_name)
    query_text = "What is the expense ratio?"
    doc_text = doc
    live_query = np.array(ef.embed_query([query_text])[0], dtype=np.float32)
    live_doc = np.array(ef([doc_text])[0], dtype=np.float32)
    cosine = float(np.dot(live_query, live_doc))

    _subheader("Live re-embed (same model)")
    print(f"  query prefix applied : {_truncate(format_query_for_embedding(query_text, model_name), 60)}")
    print(f"  doc prefix applied   : {_truncate(format_document_for_embedding(doc_text, model_name)[:60], 60)}")
    print(f"  cosine(query, chunk) : {cosine:.4f}")


def print_retrieval(
    collection,
    *,
    query: str,
    scheme_id: str,
    facet: str | None,
    top_k: int,
) -> None:
    _header("RETRIEVAL DEMO")
    print(f"Query      : {query}")
    print(f"Scheme     : {scheme_id}")
    print(f"Facet hint : {facet or '(none)'}")

    if facet:
        fact = get_tier0_fact(scheme_id, facet)
        if fact:
            _subheader("Tier-0 structured fact")
            print(f"  {facet}: {fact['value']}")
            print(f"  source: {fact['source_url']}")

    _subheader(f"Tiered retrieval (top {top_k})")
    hits = probe_retrieve(
        collection,
        query=query,
        scheme_id=scheme_id,
        facet=facet or "expense_ratio",
        top_k=top_k,
    )
    if not hits:
        print("  (no hits)")
    for i, hit in enumerate(hits, 1):
        print(f"\n  Hit {i}:")
        _print_kv("scheme_id", hit["scheme_id"], indent=4)
        _print_kv("chunk_id", hit["chunk_id"], indent=4)
        _print_kv("kind", hit["kind"], indent=4)
        _print_kv("facet", hit["facet"] or "(none)", indent=4)
        _print_kv("score", f"{hit['score']:.4f}", indent=4)
        _print_kv("distance", f"{hit['distance']:.4f}", indent=4)

    _subheader(f"Raw dense search (top {top_k}, no kind rerank)")
    raw = collection.query(
        query_texts=[query],
        n_results=top_k,
        where={
            "$and": [
                {"scheme_id": {"$eq": scheme_id}},
                {"index_for_search": {"$eq": True}},
            ]
        },
        include=["metadatas", "distances", "documents"],
    )
    ids = raw.get("ids", [[]])[0]
    if not ids:
        print("  (no hits)")
    for i, (cid, meta, dist, doc) in enumerate(
        zip(
            ids,
            raw.get("metadatas", [[]])[0],
            raw.get("distances", [[]])[0],
            raw.get("documents", [[]])[0],
        ),
        1,
    ):
        meta = meta or {}
        snippet = (doc or "").splitlines()[-1] if doc else ""
        print(f"\n  Hit {i}:")
        _print_kv("scheme_id", meta.get("scheme_id") or scheme_id, indent=4)
        _print_kv("chunk_id", cid, indent=4)
        _print_kv("kind", meta.get("kind") or "(none)", indent=4)
        _print_kv("facet", meta.get("facet") or "(none)", indent=4)
        _print_kv("distance", f"{dist:.4f}", indent=4)
        _print_kv("text_snippet", _truncate(snippet, 64), indent=4)


def list_scheme_chunks(
    collection,
    scheme_id: str,
    *,
    preview_dims: int,
    text_lines: int,
    show_full: bool,
) -> None:
    _header(f"CHUNKS FOR scheme_id={scheme_id}")
    result = collection.get(
        where={"scheme_id": scheme_id},
        include=["metadatas", "documents", "embeddings"],
    )
    ids = result.get("ids") or []
    metas = result.get("metadatas") or []
    docs = result.get("documents") or []
    embeddings = _normalize_embeddings(result.get("embeddings"), len(ids))

    rows: list[tuple[str, dict[str, Any], str, np.ndarray | None]] = []
    for cid, meta, doc, vector in zip(ids, metas, docs, embeddings):
        rows.append((cid, meta or {}, doc or "", vector))

    rows.sort(
        key=lambda item: (
            str((item[1] or {}).get("kind")),
            str((item[1] or {}).get("ordinal", 0)),
        )
    )
    print(f"Total chunks indexed for this scheme: {len(rows)}")
    for index, (cid, meta, doc, vector) in enumerate(rows, 1):
        chunk_scheme_id = str(meta.get("scheme_id") or scheme_id)
        searchable = "yes" if meta.get("index_for_search", True) else "no (parent-only)"

        print(f"\n{'=' * 72}")
        print(f"CHUNK {index} of {len(rows)}")
        print("=" * 72)
        _print_kv("scheme_id", chunk_scheme_id)
        _print_kv("chunk_id", cid)
        _print_kv("doc_id", meta.get("doc_id") or "(none)")
        _print_kv("kind", meta.get("kind") or "(none)")
        _print_kv("facet", meta.get("facet") or "(none)")
        _print_kv("section", meta.get("section") or "(none)")
        _print_kv("ordinal", meta.get("ordinal", 0))
        _print_kv("searchable", searchable)

        _subheader(f"Chunk text (showing up to {text_lines} lines)")
        lines = doc.splitlines()
        if not lines:
            print("    (empty)")
        else:
            for line in lines[:text_lines]:
                print(f"    {line}")
            if len(lines) > text_lines:
                print(f"    ... ({len(lines) - text_lines} more lines)")

        _subheader("Embedding vector")
        if vector is None:
            print("    (missing — chunk has no stored embedding)")
        else:
            _print_embedding(vector, preview_dims=preview_dims, show_full=show_full)


def run_examples(collection, top_k: int) -> None:
    for example in EXAMPLE_QUERIES:
        print_retrieval(
            collection,
            query=example["query"],
            scheme_id=example["scheme_id"],
            facet=example["facet"],
            top_k=top_k,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect Chroma embeddings and run sample retrieval queries."
    )
    parser.add_argument("--vector-store", default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--query", default=None, help="Custom query text")
    parser.add_argument("--scheme", default=None, help="scheme_id filter")
    parser.add_argument(
        "--facet",
        default=None,
        choices=sorted(FACET_PROBE_QUERIES.keys()),
        help="Facet hint for tiered retrieval",
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--embedding-sample",
        metavar="SCHEME_ID",
        default=None,
        help="Show one stored embedding vector for a scheme (or any chunk if omitted)",
    )
    parser.add_argument("--chunk-id", default=None, help="Specific chunk_id for embedding sample")
    parser.add_argument(
        "--list-chunks",
        metavar="SCHEME_ID",
        default=None,
        help="List indexed chunks with text and stored embedding vectors for a scheme",
    )
    parser.add_argument(
        "--text-lines",
        type=int,
        default=4,
        help="How many text lines to show per chunk in --list-chunks view",
    )
    parser.add_argument(
        "--preview-dims",
        type=int,
        default=16,
        help="How many embedding dimensions to print per chunk (unless --full-embedding)",
    )
    parser.add_argument(
        "--full-embedding",
        action="store_true",
        help="Print every dimension of each embedding vector (384 values for BGE-small)",
    )
    parser.add_argument(
        "--examples-only",
        action="store_true",
        help="Skip index status / only run built-in example queries",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Only print index status",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    model = args.embedding_model or settings.embedding_model
    store = args.vector_store or settings.vector_store_path
    coll_name = args.collection or settings.chroma_collection

    try:
        collection = get_chroma_collection(
            vector_store_path=store,
            collection_name=coll_name,
            embedding_model=model,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to open vector store: {exc}", file=sys.stderr)
        print("Run: python -m src.ingest.index", file=sys.stderr)
        return 2

    if collection.count() == 0:
        print("Vector store is empty. Run: python -m src.ingest.index", file=sys.stderr)
        return 1

    if not args.examples_only:
        print_index_status(collection, settings)

    if args.status_only:
        return 0

    if args.list_chunks:
        list_scheme_chunks(
            collection,
            args.list_chunks,
            preview_dims=args.preview_dims,
            text_lines=args.text_lines,
            show_full=args.full_embedding,
        )
        return 0

    if args.embedding_sample is not None or args.chunk_id:
        print_embedding_sample(
            collection,
            model_name=model,
            scheme_id=args.embedding_sample,
            chunk_id=args.chunk_id,
            preview_dims=args.preview_dims,
            show_full=args.full_embedding,
        )
        if not args.query and not args.examples_only:
            return 0

    if args.query:
        scheme_id = args.scheme
        if not scheme_id:
            schemes = load_manifest_schemes(settings.manifest_path)
            if len(schemes) == 1:
                scheme_id = str(schemes[0]["scheme_id"])
            else:
                print("--scheme is required with --query when multiple schemes exist.", file=sys.stderr)
                return 2
        print_retrieval(
            collection,
            query=args.query,
            scheme_id=scheme_id,
            facet=args.facet,
            top_k=args.top_k,
        )
    else:
        run_examples(collection, top_k=args.top_k)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
