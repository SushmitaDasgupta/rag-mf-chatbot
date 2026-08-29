"""
End-to-end corpus ingest: fetch → parse → chunk → index (Phase 1).

Usage:
    python -m src.ingest.run
    python -m src.ingest.run --skip-fetch --verify-only
    python -m src.ingest.run --scheme-id kotak_large_cap_direct_growth
"""

from __future__ import annotations

import os

# Configure logging before ingest imports so CI sees every checkpoint immediately.
from src.logging_config import setup_logging

setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.config import get_settings
from src.ingest.chunk import run_chunk
from src.ingest.fetch import load_manifest_schemes, run_fetch
from src.ingest.index import IndexRunSummary, run_index
from src.ingest.parse import run_parse
from src.logging_config import (
    get_logger,
    log_manifest_roster,
    log_pipeline_footer,
    log_pipeline_header,
    log_stage,
    setup_logging,
)

logger = get_logger(__name__)


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
    pipeline_started = time.perf_counter()
    started_at = _utc_now_iso()
    run_id = started_at.replace(":", "").replace("+", "Z")
    errors: list[str] = []

    manifest = manifest_path or settings.manifest_path
    schemes = load_manifest_schemes(manifest)
    if scheme_ids:
        schemes = [s for s in schemes if s.get("scheme_id") in scheme_ids]

    scheme_note = f"schemes={len(schemes)}"
    log_pipeline_header(
        logger,
        run_id,
        detail=(
            f"{scheme_note} | skip_fetch={skip_fetch} verify_only={verify_only} "
            f"skip_parse={skip_parse} skip_chunk={skip_chunk} skip_index={skip_index}"
        ),
    )
    log_manifest_roster(logger, schemes)

    fetch_status = "skipped"
    if not skip_fetch:
        fallback = (
            fetch_fallback_cached
            if fetch_fallback_cached is not None
            else settings.fetch_fallback_cached
        )
        with log_stage(
            logger,
            "P1.1 FETCH",
            detail="Download allowlisted scheme HTML → data/raw/ | "
            f"{scheme_note} | fallback_cached={fallback}",
        ):
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
            logger.warning("Skipping parse because fetch failed")
        else:
            with log_stage(
                logger,
                "P1.2 PARSE",
                detail="Extract text/tables → data/processed/parsed/ | " + scheme_note,
            ):
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
            logger.warning("Skipping chunk because parse failed")
        else:
            with log_stage(
                logger,
                "P1.3 CHUNK",
                detail="Section-aware chunks → data/processed/chunks/ | " + scheme_note,
            ):
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
            logger.warning("Skipping index because chunk failed")
        else:
            with log_stage(
                logger,
                "P1.4 INDEX",
                detail=(
                    "Embed vectors + upsert Chroma + smoke probes | "
                    f"{scheme_note} | probes={not skip_probes} recreate={recreate_collection}"
                ),
            ):
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

    summary = IngestRunSummary(
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

    log_pipeline_footer(
        logger,
        run_id,
        overall,
        elapsed_seconds=time.perf_counter() - pipeline_started,
        stages={
            "fetch": fetch_status,
            "parse": parse_status,
            "chunk": chunk_status,
            "index": index_status,
        },
        errors=errors,
    )
    if index_summary:
        logger.info(
            "Index artifacts | vectors=%d | probes=%s | collection=%s",
            index_summary.total_vectors,
            index_summary.probe_status,
            index_summary.collection_name,
        )

    return summary


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
    parser.add_argument(
        "--log-level",
        default=None,
        help="Logging level (DEBUG, INFO, WARNING; default from LOG_LEVEL env)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(args.log_level or settings.log_level)

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
        logger.exception("Ingest aborted: %s", exc)
        return 2

    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
