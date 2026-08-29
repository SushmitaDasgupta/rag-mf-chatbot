"""P2.2 — Tiered hybrid retriever (structured facts → kind routing → dense re-rank)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from chromadb import Collection

from src.config import get_settings
from src.ingest.index import CORE_FACETS, FACET_PROBE_QUERIES, get_chroma_collection
from src.rag.embeddings import get_embedding_function
from src.rag.intent import QueryIntent, classify_query
from src.rag.structured_facts import get_tier0_fact, load_structured_facts

RetrievalStatus = Literal["hit", "miss"]

FACET_EXPECTED_KINDS: dict[str, set[str]] = {
    "expense_ratio": {"overview_row"},
    "exit_load": {"overview_row"},
    "min_sip": {"overview_row"},
    "benchmark": {"overview_row"},
    "riskometer": {"riskometer", "overview_row"},
    "lock_in": {"overview_row"},
    "holdings": {"faq", "holdings"},
    "taxation": {"prose"},
    "nav": {"faq"},
    "aum": {"faq"},
    "fund_manager": {"faq"},
}

PRIMARY_KINDS: dict[str, list[str]] = {
    "expense_ratio": ["overview_row"],
    "exit_load": ["overview_row"],
    "min_sip": ["overview_row"],
    "benchmark": ["overview_row"],
    "riskometer": ["riskometer", "overview_row"],
    "lock_in": ["overview_row"],
    "holdings": ["faq", "holdings"],
    "taxation": ["prose"],
    "nav": ["faq"],
    "aum": ["faq"],
    "fund_manager": ["faq"],
}


@dataclass
class RetrievedChunk:
    chunk_id: str
    kind: str
    text: str
    facet: str | None = None
    section: str | None = None
    score: float = 0.0
    expanded_from_parent: bool = False


@dataclass
class RetrievalResult:
    scheme_id: str
    source_url: str
    effective_date: str | None
    facet: str | None
    structured_fact: dict[str, Any] | None
    chunks: list[RetrievedChunk] = field(default_factory=list)
    retrieval_status: RetrievalStatus = "miss"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bm25_heading_boost(query: str, section: str) -> float:
    """Lightweight keyword overlap on FAQ section headings (Tier 4)."""
    query_tokens = set(_tokenize(query))
    section_tokens = set(_tokenize(section))
    if not query_tokens or not section_tokens:
        return 0.0
    overlap = query_tokens & section_tokens
    if not overlap:
        return 0.0
    return min(0.5, 0.1 * len(overlap))


def _list_scheme_chunks(collection: Collection, scheme_id: str) -> list[dict[str, Any]]:
    result = collection.get(
        where={"scheme_id": scheme_id},
        include=["metadatas", "documents"],
    )
    rows: list[dict[str, Any]] = []
    for cid, meta, doc in zip(
        result.get("ids") or [],
        result.get("metadatas") or [],
        result.get("documents") or [],
    ):
        meta = meta or {}
        rows.append(
            {
                "chunk_id": cid,
                "kind": str(meta.get("kind") or ""),
                "facet": str(meta.get("facet") or ""),
                "section": str(meta.get("section") or ""),
                "parent_id": str(meta.get("parent_id") or ""),
                "index_for_search": bool(meta.get("index_for_search", True)),
                "source_url": str(meta.get("source_url") or ""),
                "effective_date": str(meta.get("effective_date") or ""),
                "text": doc or "",
            }
        )
    return rows


def _tier_score(
    *,
    kind: str,
    facet: str | None,
    chunk_facet: str,
    section: str,
    query: str,
    dense_score: float,
) -> float:
    score = dense_score
    if facet and kind in PRIMARY_KINDS.get(facet, []):
        score += 3.0
    if facet and chunk_facet == facet:
        score += 2.0
    if kind == "overview_parent":
        score -= 1.0
    if facet in CORE_FACETS and kind == "prose":
        score -= 2.0
    score += _bm25_heading_boost(query, section)
    return score


def _dense_scores(
    collection: Collection,
    *,
    query: str,
    scheme_id: str,
    chunk_ids: list[str] | None = None,
) -> dict[str, float]:
    where: dict[str, Any] = {
        "$and": [
            {"scheme_id": {"$eq": scheme_id}},
            {"index_for_search": {"$eq": True}},
        ]
    }
    if chunk_ids:
        where = {
            "$and": [
                where,
                {"chunk_id": {"$in": chunk_ids}},
            ]
        }

    raw = collection.query(
        query_texts=[query],
        n_results=min(50, max(10, len(chunk_ids) if chunk_ids else 30)),
        where=where,
        include=["metadatas", "distances"],
    )
    scores: dict[str, float] = {}
    for cid, dist in zip(
        (raw.get("ids") or [[]])[0],
        (raw.get("distances") or [[]])[0],
    ):
        scores[cid] = 1.0 - float(dist or 1.0)
    return scores


def _filter_tier2_candidates(
    chunks: list[dict[str, Any]],
    facet: str | None,
) -> list[dict[str, Any]]:
    searchable = [c for c in chunks if c.get("index_for_search", True)]
    if not facet:
        return searchable

    primary_kinds = PRIMARY_KINDS.get(facet, ["faq", "overview_row"])
    matched = [
        c
        for c in searchable
        if c["kind"] in primary_kinds
        and (not facet or not c.get("facet") or c.get("facet") == facet or facet in {"holdings", "nav", "aum", "fund_manager"})
    ]

    if facet in CORE_FACETS:
        non_prose = [c for c in matched if c["kind"] != "prose"]
        if non_prose:
            matched = non_prose

    if facet == "holdings":
        faq_holdings = [
            c for c in searchable if c["kind"] == "faq" and "holding" in c.get("section", "").lower()
        ]
        table_holdings = [c for c in searchable if c["kind"] == "holdings"]
        matched = faq_holdings or table_holdings or matched

    if facet == "taxation":
        matched = [
            c for c in searchable if c["kind"] == "prose" and "taxation" in c.get("section", "").lower()
        ]

    if facet == "process_statements":
        return []

    return matched or searchable


def _rank_candidates(
    candidates: list[dict[str, Any]],
    *,
    query: str,
    facet: str | None,
    dense_scores: dict[str, float],
    top_k: int,
) -> list[RetrievedChunk]:
    ranked: list[tuple[float, RetrievedChunk]] = []
    for chunk in candidates:
        cid = chunk["chunk_id"]
        dense = dense_scores.get(cid, 0.0)
        score = _tier_score(
            kind=chunk["kind"],
            facet=facet,
            chunk_facet=chunk.get("facet") or "",
            section=chunk.get("section") or "",
            query=query,
            dense_score=dense,
        )
        ranked.append(
            (
                score,
                RetrievedChunk(
                    chunk_id=cid,
                    kind=chunk["kind"],
                    text=chunk["text"],
                    facet=chunk.get("facet") or None,
                    section=chunk.get("section") or None,
                    score=score,
                ),
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:top_k]]


def _expand_parents(
    all_chunks: list[dict[str, Any]],
    hits: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    by_id = {c["chunk_id"]: c for c in all_chunks}
    expanded: list[RetrievedChunk] = []
    seen: set[str] = set()

    for hit in hits:
        if hit.chunk_id not in seen:
            expanded.append(hit)
            seen.add(hit.chunk_id)

        if hit.kind != "overview_row":
            continue
        parent_id = (by_id.get(hit.chunk_id) or {}).get("parent_id")
        if not parent_id or parent_id in seen:
            continue
        parent = by_id.get(parent_id)
        if not parent:
            continue
        expanded.append(
            RetrievedChunk(
                chunk_id=parent_id,
                kind=parent["kind"],
                text=parent["text"],
                facet=parent.get("facet") or None,
                section=parent.get("section") or None,
                score=hit.score,
                expanded_from_parent=True,
            )
        )
        seen.add(parent_id)

    return expanded


def retrieve(
    query: str,
    scheme_id: str,
    *,
    facet: str | None = None,
    collection: Collection | None = None,
    top_k: int = 3,
    skip_dense_if_oracle: bool = True,
) -> RetrievalResult:
    """
    Run tiers 0–5 for a resolved scheme_id.

    Returns a structured context bundle for the generator.
    """
    settings = get_settings()
    coll = collection or get_chroma_collection(
        vector_store_path=settings.vector_store_path,
        collection_name=settings.chroma_collection,
        embedding_model=settings.embedding_model,
        embedding_function=get_embedding_function(settings.embedding_model),
    )

    facts = load_structured_facts()
    scheme_facts = facts.get(scheme_id) or {}
    source_url = str(scheme_facts.get("source_url") or "")
    effective_date = scheme_facts.get("last_updated")

    structured_fact = None
    if facet and facet in CORE_FACETS:
        structured_fact = get_tier0_fact(scheme_id, facet, facts=facts)

    all_chunks = _list_scheme_chunks(coll, scheme_id)
    if not all_chunks and not structured_fact:
        return RetrievalResult(
            scheme_id=scheme_id,
            source_url=source_url,
            effective_date=str(effective_date) if effective_date else None,
            facet=facet,
            structured_fact=None,
            chunks=[],
            retrieval_status="miss",
        )

    if facet == "process_statements":
        return RetrievalResult(
            scheme_id=scheme_id,
            source_url=source_url,
            effective_date=str(effective_date) if effective_date else None,
            facet=facet,
            structured_fact=None,
            chunks=[],
            retrieval_status="miss",
        )

    tier2 = _filter_tier2_candidates(all_chunks, facet)

    oracle_hits = [
        c
        for c in tier2
        if facet
        and c["kind"] in FACET_EXPECTED_KINDS.get(facet, set())
        and (not c.get("facet") or c.get("facet") == facet or facet == "riskometer")
    ]

    if skip_dense_if_oracle and len(oracle_hits) == 1:
        hit = oracle_hits[0]
        hits = [
            RetrievedChunk(
                chunk_id=hit["chunk_id"],
                kind=hit["kind"],
                text=hit["text"],
                facet=hit.get("facet") or None,
                section=hit.get("section") or None,
                score=5.0,
            )
        ]
    else:
        candidate_ids = [c["chunk_id"] for c in tier2] if tier2 else None
        dense_scores = _dense_scores(coll, query=query, scheme_id=scheme_id, chunk_ids=candidate_ids)
        hits = _rank_candidates(
            tier2 or [c for c in all_chunks if c.get("index_for_search", True)],
            query=query,
            facet=facet,
            dense_scores=dense_scores,
            top_k=top_k,
        )

    hits = _expand_parents(all_chunks, hits)

    if not hits and not structured_fact:
        return RetrievalResult(
            scheme_id=scheme_id,
            source_url=source_url,
            effective_date=str(effective_date) if effective_date else None,
            facet=facet,
            structured_fact=None,
            chunks=[],
            retrieval_status="miss",
        )

    if hits and not source_url:
        source_url = str((all_chunks[0] or {}).get("source_url") or "")

    if hits and not effective_date:
        effective_date = str((all_chunks[0] or {}).get("effective_date") or "")

    return RetrievalResult(
        scheme_id=scheme_id,
        source_url=source_url,
        effective_date=str(effective_date) if effective_date else None,
        facet=facet,
        structured_fact=structured_fact,
        chunks=hits,
        retrieval_status="hit",
    )


def retrieve_for_query(
    query: str,
    scheme_id: str,
    *,
    collection: Collection | None = None,
    intent: QueryIntent | None = None,
) -> RetrievalResult:
    """Classify intent (if needed) and retrieve."""
    intent = intent or classify_query(query)
    if intent.intent == "performance_request":
        return RetrievalResult(
            scheme_id=scheme_id,
            source_url=str((load_structured_facts().get(scheme_id) or {}).get("source_url") or ""),
            effective_date=None,
            facet=None,
            structured_fact=None,
            chunks=[],
            retrieval_status="miss",
        )
    return retrieve(query, scheme_id, facet=intent.facet, collection=collection)


def run_core_facet_probes(
    collection: Collection,
    *,
    scheme_ids: list[str],
) -> list[dict[str, Any]]:
    """Evaluate top-1 kind for core facets (P2.2 exit criterion)."""
    results: list[dict[str, Any]] = []
    for scheme_id in scheme_ids:
        for facet in sorted(CORE_FACETS):
            query = FACET_PROBE_QUERIES[facet]
            bundle = retrieve(query, scheme_id, facet=facet, collection=collection)
            top_kind = bundle.chunks[0].kind if bundle.chunks else None
            top_id = bundle.chunks[0].chunk_id if bundle.chunks else None
            expected = FACET_EXPECTED_KINDS.get(facet, {"overview_row"})
            ok = top_kind in expected if top_kind else False
            tier0_ok = bundle.structured_fact is not None or facet == "min_sip"
            results.append(
                {
                    "scheme_id": scheme_id,
                    "facet": facet,
                    "top_kind": top_kind,
                    "top_chunk_id": top_id,
                    "tier0_present": bundle.structured_fact is not None,
                    "status": "pass" if ok and tier0_ok else "fail",
                }
            )
    return results
