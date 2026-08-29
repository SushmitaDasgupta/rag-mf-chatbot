"""
End-to-end corpus ingest: fetch → parse → chunk → index (Phase 1).

Usage:
    python -m src.ingest.run
    python -m src.ingest.run --skip-fetch --verify-only
    python -m src.ingest.run --scheme-id kotak_large_cap_direct_growth
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.config import get_settings
from src.ingest.chunk import run_chunk
from src.ingest.fetch import run_fetch
from src.ingest.index import IndexRunSummary, run_index
from src.ingest.parse import run_parse


@dataclass
class IngestRunSummary:
    run_id: str
    started_at: str
    finished_at: str
    overall_status: str  # success | failed
    fetch_status: str = "skipped"
    parse_status: str = "skipped"
    chunk_status: str = "skipped"
    index_status: str = "skipped"
    index_summary: IndexRunSummary | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.overall_status == "success"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_ingest(
    *,
    skip_fetch: bool = False,
    verify_only: bool = False,
    fetch_fallback_cached: bool | None = None,
    skip_parse: bool = False,
    skip_chunk: bool = False,
    skip_index: bool = False,
    skip_probes: bool = False,
    recreate_collection: bool = False,
    scheme_ids: set[str] | None = None,
    manifest_path: str | None = None,
    raw_dir: str | None = None,
    parsed_dir: str | None = None,
    chunks_dir: str | None = None,
    structured_facts_path: str | None = None,
    vector_store_path: str | None = None,
    collection_name: str | None = None,
    embedding_model: str | None = None,
) -> IngestRunSummary:
    settings = get_settings()
    started_at = _utc_now_iso()
    run_id = started_at.replace(":", "").replace("+", "Z")
    errors: list[str] = []

    fetch_status = "skipped"
    if not skip_fetch:
        fallback = (
            fetch_fallback_cached
            if fetch_fallback_cached is not None
            else settings.fetch_fallback_cached
        )
        fetch_summary = run_fetch(
            manifest_path=manifest_path or settings.manifest_path,
            raw_dir=raw_dir or settings.raw_dir,
            scheme_ids=scheme_ids,
            verify_only=verify_only,
            fallback_to_cached=fallback,
            retry_count=settings.fetch_retry_count,
            inter_scheme_delay_seconds=settings.fetch_inter_scheme_delay_seconds,
        )
        fetch_status = fetch_summary.overall_status
        if not fetch_summary.ok:
            errors.append("fetch failed")

    parse_status = "skipped"
    if not skip_parse:
        if fetch_status == "failed":
            parse_status = "skipped"
            errors.append("parse skipped due to fetch failure")
        else:
            parse_summary = run_parse(
                manifest_path=manifest_path or settings.manifest_path,
                raw_dir=raw_dir or settings.raw_dir,
                parsed_dir=parsed_dir or settings.parsed_dir,
                structured_facts_path=structured_facts_path or settings.structured_facts_path,
                scheme_ids=scheme_ids,
            )
            parse_status = parse_summary.overall_status
            if not parse_summary.ok:
                errors.append("parse failed")

    chunk_status = "skipped"
    if not skip_chunk:
        if parse_status == "failed":
            chunk_status = "skipped"
            errors.append("chunk skipped due to parse failure")
        else:
            chunk_summary = run_chunk(
                manifest_path=manifest_path or settings.manifest_path,
                parsed_dir=parsed_dir or settings.parsed_dir,
                chunks_dir=chunks_dir or settings.chunks_dir,
                structured_facts_path=structured_facts_path or settings.structured_facts_path,
                scheme_ids=scheme_ids,
            )
            chunk_status = chunk_summary.overall_status
            if not chunk_summary.ok:
                errors.append("chunk failed")

    index_status = "skipped"
    index_summary: IndexRunSummary | None = None
    if not skip_index:
        if chunk_status == "failed":
            index_status = "skipped"
            errors.append("index skipped due to chunk failure")
        else:
            index_summary = run_index(
                manifest_path=manifest_path or settings.manifest_path,
                chunks_dir=chunks_dir or settings.chunks_dir,
                structured_facts_path=structured_facts_path or settings.structured_facts_path,
                vector_store_path=vector_store_path or settings.vector_store_path,
                collection_name=collection_name or settings.chroma_collection,
                embedding_model=embedding_model or settings.embedding_model,
                scheme_ids=scheme_ids,
                run_probes=not skip_probes,
                recreate_collection=recreate_collection,
            )
            index_status = index_summary.overall_status
            if not index_summary.ok:
                errors.append("index failed")

    finished_at = _utc_now_iso()
    stages = [fetch_status, parse_status, chunk_status, index_status]
    active = [s for s in stages if s != "skipped"]
    overall = "success" if active and all(s == "success" for s in active) and not errors else "failed"

    return IngestRunSummary(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        overall_status=overall,
        fetch_status=fetch_status,
        parse_status=parse_status,
        chunk_status=chunk_status,
        index_status=index_status,
        index_summary=index_summary,
        errors=errors,
    )


def _print_summary(summary: IngestRunSummary) -> None:
    print(f"Ingest run {summary.run_id}: {summary.overall_status}")
    print(
        f"  fetch={summary.fetch_status} parse={summary.parse_status} "
        f"chunk={summary.chunk_status} index={summary.index_status}"
    )
    if summary.index_summary:
        print(f"  vectors={summary.index_summary.total_vectors} probes={summary.index_summary.probe_status}")
    for err in summary.errors:
        print(f"  ! {err}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run full corpus ingest pipeline (fetch → parse → chunk → index)"
    )
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--raw-dir", default=None)
    parser.add_argument("--parsed-dir", default=None)
    parser.add_argument("--chunks-dir", default=None)
    parser.add_argument("--structured-facts", default=None)
    parser.add_argument("--vector-store", default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--scheme-id", action="append", dest="scheme_ids", default=None)
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--fetch-fallback-cached",
        action="store_true",
        help="On network failure, reuse committed raw HTML if present",
    )
    parser.add_argument("--skip-parse", action="store_true")
    parser.add_argument("--skip-chunk", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Delete and recreate the Chroma collection before indexing",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_ingest(
            skip_fetch=args.skip_fetch,
            verify_only=args.verify_only,
            fetch_fallback_cached=(
                True if args.fetch_fallback_cached else None
            ),
            skip_parse=args.skip_parse,
            skip_chunk=args.skip_chunk,
            skip_index=args.skip_index,
            skip_probes=args.skip_probes,
            recreate_collection=args.recreate_collection,
            scheme_ids=set(args.scheme_ids) if args.scheme_ids else None,
            manifest_path=args.manifest,
            raw_dir=args.raw_dir,
            parsed_dir=args.parsed_dir,
            chunks_dir=args.chunks_dir,
            structured_facts_path=args.structured_facts,
            vector_store_path=args.vector_store,
            collection_name=args.collection,
            embedding_model=args.embedding_model,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Ingest aborted: {exc}", file=sys.stderr)
        return 2

    _print_summary(summary)
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
