"""
Phase 1.4 — Embed chunks, upsert into Chroma, validate structured facts, smoke probes.

Indexing rules (implementation.md P1.4):
- Embed full chunk.text (includes scheme/doc/section prefixes).
- Idempotent upsert: delete all vectors for doc_id before re-insert.
- Deduplicate by content_hash within scheme (keep highest-priority kind).
- overview_parent indexed with index_for_search=false (parent expand in P2.2).
- structured_facts.yaml is a parallel lookup table (not embedded).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
import yaml
from chromadb import Collection

from src.config import REPO_ROOT, get_settings
from src.guardrails.citations import is_allowed_citation
from src.ingest.chunk import load_structured_facts
from src.ingest.fetch import load_manifest_schemes
from src.rag.embeddings import get_embedding_function

CORE_FACETS = frozenset(
    {"expense_ratio", "exit_load", "min_sip", "riskometer", "benchmark"}
)

KIND_PRIORITY: dict[str, int] = {
    "overview_row": 0,
    "riskometer": 1,
    "faq": 2,
    "prose": 3,
    "overview_parent": 4,
    "holdings": 5,
}

FACET_PROBE_QUERIES: dict[str, str] = {
    "expense_ratio": "What is the expense ratio?",
    "exit_load": "What is the exit load?",
    "min_sip": "What is the minimum SIP amount?",
    "riskometer": "What is the riskometer?",
    "benchmark": "What is the benchmark?",
}

FACET_EXPECTED_KINDS: dict[str, set[str]] = {
    "expense_ratio": {"overview_row"},
    "exit_load": {"overview_row"},
    "min_sip": {"overview_row"},
    "benchmark": {"overview_row"},
    "riskometer": {"riskometer", "overview_row"},
}

NOT_IN_CORPUS_VALUES = frozenset(
    {"", "not in corpus", "not_in_corpus", "n/a", "na", "none", "null"}
)


@dataclass
class SchemeIndexResult:
    scheme_id: str
    doc_id: str
    source_url: str
    status: str  # success | failed
    chunks_loaded: int = 0
    chunks_indexed: int = 0
    chunks_deduped: int = 0
    error: str | None = None


@dataclass
class IndexRunSummary:
    run_id: str
    started_at: str
    finished_at: str
    overall_status: str  # success | failed
    vector_store_path: str
    collection_name: str
    embedding_model: str
    total_vectors: int = 0
    schemes: list[SchemeIndexResult] = field(default_factory=list)
    structured_facts_status: str = "unknown"
    probe_status: str = "skipped"

    @property
    def ok(self) -> bool:
        return self.overall_status == "success"


@dataclass
class ProbeResult:
    scheme_id: str
    facet: str
    tier0_present: bool
    tier0_value: str | None
    tier2_hit: bool
    top_kinds: list[str]
    top_chunk_ids: list[str]
    top_scheme_ids: list[str]
    cross_scheme_leak: bool
    status: str  # pass | fail


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (REPO_ROOT / p).resolve()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _kind_rank(kind: str) -> int:
    return KIND_PRIORITY.get(kind, 99)


def dedupe_chunks_by_content_hash(chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep highest-priority kind when content_hash collides within a scheme."""
    best: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        scheme_id = str(chunk.get("scheme_id") or "")
        content_hash = str(chunk.get("content_hash") or "")
        if not scheme_id or not content_hash:
            continue
        key = f"{scheme_id}:{content_hash}"
        current = best.get(key)
        if current is None or _kind_rank(str(chunk.get("kind") or "")) < _kind_rank(
            str(current.get("kind") or "")
        ):
            best[key] = chunk
    deduped = list(best.values())
    removed = len(chunks) - len(deduped)
    return deduped, removed


def index_for_search(chunk: dict[str, Any]) -> bool:
    """overview_parent is stored but excluded from semantic search (P2.2 parent expand)."""
    return str(chunk.get("kind") or "") != "overview_parent"


def chunk_to_metadata(chunk: dict[str, Any]) -> dict[str, str | int | float | bool]:
    facets = chunk.get("facets") or []
    if isinstance(facets, list):
        facets_str = ",".join(str(f) for f in facets if f)
    else:
        facets_str = str(facets)

    facet = chunk.get("facet")
    parent_id = chunk.get("parent_id")

    return {
        "chunk_id": str(chunk.get("chunk_id") or ""),
        "doc_id": str(chunk.get("doc_id") or chunk.get("scheme_id") or ""),
        "scheme_id": str(chunk.get("scheme_id") or ""),
        "source_url": str(chunk.get("source_url") or ""),
        "effective_date": str(chunk.get("effective_date") or ""),
        "section": str(chunk.get("section") or ""),
        "facet": str(facet) if facet else "",
        "facets": facets_str,
        "kind": str(chunk.get("kind") or ""),
        "parent_id": str(parent_id) if parent_id else "",
        "content_hash": str(chunk.get("content_hash") or ""),
        "index_for_search": index_for_search(chunk),
        "ordinal": int(chunk.get("ordinal") or 0),
    }


def load_scheme_chunks(chunks_dir: Path, scheme_id: str) -> list[dict[str, Any]]:
    path = chunks_dir / f"{scheme_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing chunk artifact: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    chunks = data.get("chunks") or []
    if not chunks:
        raise ValueError(f"No chunks in artifact: {path}")
    return chunks


def validate_chunk_sources(chunks: list[dict[str, Any]]) -> None:
    for chunk in chunks:
        url = str(chunk.get("source_url") or "")
        if not url or not is_allowed_citation(url):
            raise ValueError(
                f"Chunk {chunk.get('chunk_id')} has missing or non-allowlisted source_url: {url!r}"
            )
        text = str(chunk.get("text") or "").strip()
        if not text:
            raise ValueError(f"Chunk {chunk.get('chunk_id')} has empty text")


def get_chroma_collection(
    *,
    vector_store_path: str | Path,
    collection_name: str,
    embedding_model: str,
    embedding_function: Any | None = None,
    recreate: bool = False,
) -> Collection:
    path = _resolve_path(vector_store_path)
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(path))
    if recreate:
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
    ef = embedding_function or get_embedding_function(embedding_model)
    return client.get_or_create_collection(name=collection_name, embedding_function=ef)


def delete_doc_vectors(collection: Collection, doc_id: str) -> None:
    try:
        collection.delete(where={"doc_id": doc_id})
    except Exception:
        # Collection may be empty on first run
        pass


def upsert_scheme_chunks(
    collection: Collection,
    *,
    doc_id: str,
    chunks: list[dict[str, Any]],
) -> tuple[int, int]:
    """Delete all vectors for doc_id, then insert deduped chunks. Returns (loaded, indexed)."""
    validate_chunk_sources(chunks)
    deduped, _ = dedupe_chunks_by_content_hash(chunks)
    delete_doc_vectors(collection, doc_id)

    if not deduped:
        return len(chunks), 0

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, str | int | float | bool]] = []

    for chunk in deduped:
        chunk_id = str(chunk.get("chunk_id") or "")
        text = str(chunk.get("text") or "")
        if not chunk_id or not text:
            continue
        ids.append(chunk_id)
        documents.append(text)
        metadatas.append(chunk_to_metadata(chunk))

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(chunks), len(ids)


def is_tier0_fact_present(value: Any) -> bool:
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized not in NOT_IN_CORPUS_VALUES


def write_structured_facts_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(report, sort_keys=False, allow_unicode=True), encoding="utf-8")


def validate_structured_facts(
    facts_path: Path,
    *,
    scheme_ids: list[str],
    core_facets: frozenset[str] = CORE_FACETS,
) -> dict[str, Any]:
    """
    Validate structured_facts.yaml has Tier-0 values for core facets.
    Preserves manual_override fields; does not overwrite parsed values.
    """
    if not facts_path.exists():
        raise FileNotFoundError(f"Missing structured facts: {facts_path}")

    data = yaml.safe_load(facts_path.read_text(encoding="utf-8")) or {}
    schemes = data.get("schemes") or {}
    report: dict[str, Any] = {
        "path": _display_path(facts_path),
        "status": "success",
        "schemes": {},
        "missing": [],
    }

    for scheme_id in scheme_ids:
        entry = schemes.get(scheme_id)
        if not entry:
            report["status"] = "failed"
            report["missing"].append(f"{scheme_id}: scheme entry missing")
            continue

        scheme_report: dict[str, Any] = {"facets": {}, "source_url": entry.get("source_url")}
        url = str(entry.get("source_url") or "")
        if not is_allowed_citation(url):
            report["status"] = "failed"
            report["missing"].append(f"{scheme_id}: non-allowlisted source_url")

        for facet in sorted(core_facets):
            value = entry.get(facet)
            present = is_tier0_fact_present(value)
            scheme_report["facets"][facet] = {
                "present": present,
                "value": value,
                "manual_override": bool(entry.get(f"manual_override_{facet}")),
            }
            if not present:
                report["status"] = "failed"
                report["missing"].append(f"{scheme_id}.{facet}: not in corpus")

        report["schemes"][scheme_id] = scheme_report

    return report


def _tier2_score(
    *,
    kind: str,
    facet: str,
    chunk_facet: str,
    distance: float,
) -> float:
    """Lightweight facet/kind routing for smoke probes (feeds P2.2)."""
    score = 1.0 - float(distance)
    if kind in FACET_EXPECTED_KINDS.get(facet, set()):
        score += 3.0
    if chunk_facet == facet:
        score += 2.0
    if kind == "prose" and facet in CORE_FACETS:
        score -= 2.0
    if kind == "overview_parent":
        score -= 1.0
    return score


def probe_retrieve(
    collection: Collection,
    *,
    query: str,
    scheme_id: str,
    facet: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Tier-1 scheme filter + Tier-2 kind/facet routing + dense re-rank."""
    raw = collection.query(
        query_texts=[query],
        n_results=min(top_k * 5, 50),
        where={
            "$and": [
                {"scheme_id": {"$eq": scheme_id}},
                {"index_for_search": {"$eq": True}},
            ]
        },
        include=["metadatas", "distances", "documents"],
    )

    ids = (raw.get("ids") or [[]])[0]
    metas = (raw.get("metadatas") or [[]])[0]
    dists = (raw.get("distances") or [[]])[0]

    ranked: list[tuple[float, dict[str, Any]]] = []
    for chunk_id, meta, dist in zip(ids, metas, dists):
        meta = meta or {}
        kind = str(meta.get("kind") or "")
        chunk_facet = str(meta.get("facet") or "")
        score = _tier2_score(
            kind=kind,
            facet=facet,
            chunk_facet=chunk_facet,
            distance=float(dist or 1.0),
        )
        ranked.append(
            (
                score,
                {
                    "chunk_id": chunk_id,
                    "kind": kind,
                    "facet": chunk_facet,
                    "scheme_id": str(meta.get("scheme_id") or ""),
                    "score": score,
                    "distance": float(dist or 0.0),
                },
            )
        )

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:top_k]]


def run_retrieval_probes(
    collection: Collection,
    *,
    facts: dict[str, Any],
    scheme_ids: list[str],
    core_facets: frozenset[str] = CORE_FACETS,
) -> list[ProbeResult]:
    results: list[ProbeResult] = []

    for scheme_id in scheme_ids:
        scheme_facts = facts.get(scheme_id) or {}
        for facet in sorted(core_facets):
            query = FACET_PROBE_QUERIES[facet]
            tier0_value = scheme_facts.get(facet)
            tier0_present = is_tier0_fact_present(tier0_value)

            hits = probe_retrieve(
                collection,
                query=query,
                scheme_id=scheme_id,
                facet=facet,
                top_k=3,
            )
            top_kinds = [h["kind"] for h in hits]
            top_chunk_ids = [h["chunk_id"] for h in hits]
            top_scheme_ids = [h["scheme_id"] for h in hits]
            cross_scheme_leak = any(sid and sid != scheme_id for sid in top_scheme_ids)

            expected_kinds = FACET_EXPECTED_KINDS.get(facet, {"overview_row"})
            tier2_hit = any(k in expected_kinds for k in top_kinds)

            status = "pass"
            if not tier0_present or not tier2_hit or cross_scheme_leak:
                status = "fail"

            results.append(
                ProbeResult(
                    scheme_id=scheme_id,
                    facet=facet,
                    tier0_present=tier0_present,
                    tier0_value=str(tier0_value) if tier0_value is not None else None,
                    tier2_hit=tier2_hit,
                    top_kinds=top_kinds,
                    top_chunk_ids=top_chunk_ids,
                    top_scheme_ids=top_scheme_ids,
                    cross_scheme_leak=cross_scheme_leak,
                    status=status,
                )
            )

    return results


def write_probe_log(
    probes: list[ProbeResult],
    path: Path,
    *,
    run_id: str,
    embedding_model: str,
) -> None:
    passed = sum(1 for p in probes if p.status == "pass")
    payload = {
        "version": 1,
        "run_id": run_id,
        "generated_at": _utc_now_iso(),
        "embedding_model": embedding_model,
        "summary": {
            "total": len(probes),
            "passed": passed,
            "failed": len(probes) - passed,
            "overall_status": "success" if passed == len(probes) else "failed",
        },
        "probes": [asdict(p) for p in probes],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_index_log(summary: IndexRunSummary, path: Path) -> None:
    payload = {
        "version": 1,
        "run_id": summary.run_id,
        "started_at": summary.started_at,
        "finished_at": summary.finished_at,
        "overall_status": summary.overall_status,
        "vector_store_path": summary.vector_store_path,
        "collection_name": summary.collection_name,
        "embedding_model": summary.embedding_model,
        "total_vectors": summary.total_vectors,
        "structured_facts_status": summary.structured_facts_status,
        "probe_status": summary.probe_status,
        "schemes": [asdict(s) for s in summary.schemes],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def run_index(
    *,
    manifest_path: str | Path | None = None,
    chunks_dir: str | Path | None = None,
    structured_facts_path: str | Path | None = None,
    vector_store_path: str | Path | None = None,
    collection_name: str | None = None,
    embedding_model: str | None = None,
    scheme_ids: set[str] | None = None,
    run_probes: bool = True,
    embedding_function: Any | None = None,
    collection: Collection | None = None,
    recreate_collection: bool = False,
) -> IndexRunSummary:
    settings = get_settings()
    manifest = _resolve_path(manifest_path or settings.manifest_path)
    chunks = _resolve_path(chunks_dir or settings.chunks_dir)
    facts_path = _resolve_path(structured_facts_path or settings.structured_facts_path)
    store_path = _resolve_path(vector_store_path or settings.vector_store_path)
    coll_name = collection_name or settings.chroma_collection
    model = embedding_model or settings.embedding_model

    schemes = load_manifest_schemes(manifest)
    if scheme_ids:
        schemes = [s for s in schemes if s.get("scheme_id") in scheme_ids]
        missing = scheme_ids - {s.get("scheme_id") for s in schemes}
        if missing:
            raise ValueError(f"Unknown scheme_id(s): {sorted(missing)}")

    scheme_id_list = [str(s["scheme_id"]) for s in schemes]
    started_at = _utc_now_iso()
    run_id = started_at.replace(":", "").replace("+", "Z")

    facts_report = validate_structured_facts(facts_path, scheme_ids=scheme_id_list)
    write_structured_facts_report(
        facts_report,
        facts_path.parent / "structured_facts_report.yaml",
    )
    facts = load_structured_facts(facts_path)

    chroma_collection = collection or get_chroma_collection(
        vector_store_path=store_path,
        collection_name=coll_name,
        embedding_model=model,
        embedding_function=embedding_function,
        recreate=recreate_collection,
    )

    results: list[SchemeIndexResult] = []
    for scheme in schemes:
        scheme_id = str(scheme["scheme_id"])
        doc_id = scheme_id
        url = str(scheme.get("source_url") or "")
        if not is_allowed_citation(url):
            results.append(
                SchemeIndexResult(
                    scheme_id=scheme_id,
                    doc_id=doc_id,
                    source_url=url,
                    status="failed",
                    error=f"source_url not allowlisted: {url}",
                )
            )
            continue

        try:
            scheme_chunks = load_scheme_chunks(chunks, scheme_id)
            loaded, indexed = upsert_scheme_chunks(
                chroma_collection,
                doc_id=doc_id,
                chunks=scheme_chunks,
            )
            deduped = loaded - indexed
            results.append(
                SchemeIndexResult(
                    scheme_id=scheme_id,
                    doc_id=doc_id,
                    source_url=url,
                    status="success",
                    chunks_loaded=loaded,
                    chunks_indexed=indexed,
                    chunks_deduped=deduped,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                SchemeIndexResult(
                    scheme_id=scheme_id,
                    doc_id=doc_id,
                    source_url=url,
                    status="failed",
                    error=str(exc),
                )
            )

    probe_status = "skipped"
    if run_probes and all(r.status == "success" for r in results):
        probes = run_retrieval_probes(
            chroma_collection,
            facts=facts,
            scheme_ids=scheme_id_list,
        )
        probe_path = chunks / "retrieval_probe_log.yaml"
        write_probe_log(probes, probe_path, run_id=run_id, embedding_model=model)
        probe_status = (
            "success" if all(p.status == "pass" for p in probes) else "failed"
        )

    finished_at = _utc_now_iso()
    index_ok = results and all(r.status == "success" for r in results)
    facts_ok = facts_report.get("status") == "success"
    probes_ok = probe_status in {"success", "skipped"}
    overall = "success" if index_ok and facts_ok and probes_ok else "failed"

    total_vectors = chroma_collection.count()
    summary = IndexRunSummary(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        overall_status=overall,
        vector_store_path=_display_path(store_path),
        collection_name=coll_name,
        embedding_model=model,
        total_vectors=total_vectors,
        schemes=results,
        structured_facts_status=str(facts_report.get("status") or "unknown"),
        probe_status=probe_status,
    )

    write_index_log(summary, store_path / "index_log.yaml")
    return summary


def _print_summary(summary: IndexRunSummary) -> None:
    print(f"Index run {summary.run_id}: {summary.overall_status}")
    print(
        f"  collection={summary.collection_name} "
        f"vectors={summary.total_vectors} "
        f"facts={summary.structured_facts_status} "
        f"probes={summary.probe_status}"
    )
    for r in summary.schemes:
        flag = "OK" if r.status == "success" else "FAIL"
        detail = (
            f"indexed {r.chunks_indexed}/{r.chunks_loaded} "
            f"(deduped {r.chunks_deduped})"
            if r.status == "success"
            else r.error
        )
        print(f"  [{flag}] {r.scheme_id}: {detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Embed chunks and upsert into Chroma (Phase 1.4)"
    )
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--chunks-dir", default=None)
    parser.add_argument("--structured-facts", default=None)
    parser.add_argument("--vector-store", default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--scheme-id", action="append", dest="scheme_ids", default=None)
    parser.add_argument("--skip-probes", action="store_true")
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Delete and recreate the Chroma collection before indexing (required after embedding model change)",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_index(
            manifest_path=args.manifest,
            chunks_dir=args.chunks_dir,
            structured_facts_path=args.structured_facts,
            vector_store_path=args.vector_store,
            collection_name=args.collection,
            embedding_model=args.embedding_model,
            scheme_ids=set(args.scheme_ids) if args.scheme_ids else None,
            run_probes=not args.skip_probes,
            recreate_collection=args.recreate_collection,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Index aborted: {exc}", file=sys.stderr)
        return 2

    _print_summary(summary)
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
