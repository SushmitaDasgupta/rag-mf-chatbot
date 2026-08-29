"""
Phase 1.3 — Section-aware chunking over parsed JSON artifacts.

Reads data/processed/parsed/<scheme_id>.json and emits inspectable chunks
under data/processed/chunks/. No embedding/index in this phase.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.config import REPO_ROOT, get_settings
from src.guardrails.citations import is_allowed_citation
from src.ingest.fetch import load_manifest_schemes

# Revised corpus defaults (implementation.md Phase 1.3)
HARD_MAX_TOKENS = 512
HARD_MIN_BODY_TOKENS = 40
TARGET_MIN_TOKENS = 80
TARGET_MAX_TOKENS = 250
SPLIT_OVERLAP_TOKENS = 30

CORE_FACETS = frozenset(
    {
        "expense_ratio",
        "exit_load",
        "min_sip",
        "min_investment",
        "lock_in",
        "riskometer",
        "benchmark",
        "process_statements",
    }
)

# Overview KV labels that get per-row child chunks
ROW_FACET_LABELS: dict[str, list[str]] = {
    "expense ratio": ["expense_ratio"],
    "total expense ratio": ["expense_ratio"],
    "ter": ["expense_ratio"],
    "exit load": ["exit_load"],
    "benchmark": ["benchmark"],
    "min lumpsum/sip": ["min_sip", "min_investment"],
    "minimum sip": ["min_sip"],
    "min sip": ["min_sip"],
    "lock in": ["lock_in"],
    "lock-in": ["lock_in"],
    "riskometer": ["riskometer"],
    "risk": ["riskometer"],
}


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    scheme_id: str
    scheme_name: str
    doc_type: str
    source_url: str
    effective_date: str | None
    ingested_at: str
    section: str
    facet: str | None
    facets: list[str]
    parent_id: str | None
    ordinal: int
    kind: str  # overview_parent | overview_row | holdings | prose | faq | riskometer
    text: str
    body: str
    token_estimate: int
    content_hash: str


@dataclass
class SchemeChunkResult:
    scheme_id: str
    source_url: str
    status: str
    chunk_count: int = 0
    facets_present: list[str] = field(default_factory=list)
    facets_absent: list[str] = field(default_factory=list)
    artifact_json: str | None = None
    artifact_jsonl: str | None = None
    max_token_estimate: int = 0
    error: str | None = None


@dataclass
class ChunkRunSummary:
    run_id: str
    started_at: str
    finished_at: str
    overall_status: str
    schemes: list[SchemeChunkResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.overall_status == "success"


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


def estimate_tokens(text: str) -> int:
    """Lightweight token estimate (words ≈ tokens for MVP sizing gates)."""
    words = re.findall(r"\S+", text or "")
    return max(1, len(words)) if text and text.strip() else 0


def body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def make_chunk_id(doc_id: str, section_path: str, ordinal: int, content_hash: str) -> str:
    raw = f"{doc_id}|{section_path}|{ordinal}|{content_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def format_prefix(
    scheme_name: str,
    doc_type: str,
    section: str,
    facet: str | None = None,
) -> str:
    facet_part = f" | Facet: {facet}" if facet else ""
    return (
        f"[Scheme: {scheme_name}]\n"
        f"[Doc: {doc_type} | Section: {section}{facet_part}]"
    )


def primary_facet(facets: list[str]) -> str | None:
    for f in (
        "expense_ratio",
        "exit_load",
        "min_sip",
        "benchmark",
        "riskometer",
        "lock_in",
        "min_investment",
        "process_statements",
    ):
        if f in facets:
            return f
    return facets[0] if facets else None


def facets_for_label(label: str) -> list[str]:
    return list(ROW_FACET_LABELS.get(label.lower().strip(), []))


def _split_oversized(body: str, max_tokens: int = HARD_MAX_TOKENS) -> list[str]:
    """Split long prose on paragraphs/sentences with small overlap."""
    if estimate_tokens(body) <= max_tokens:
        return [body]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if len(paragraphs) <= 1:
        sentences = re.split(r"(?<=[.!?])\s+", body)
        paragraphs = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for para in paragraphs:
        pt = estimate_tokens(para)
        if current and current_tokens + pt > max_tokens:
            chunks.append("\n\n".join(current))
            # overlap: keep last piece if small
            if SPLIT_OVERLAP_TOKENS > 0 and current:
                overlap = current[-1]
                if estimate_tokens(overlap) <= SPLIT_OVERLAP_TOKENS:
                    current = [overlap, para]
                    current_tokens = estimate_tokens(overlap) + pt
                else:
                    current = [para]
                    current_tokens = pt
            else:
                current = [para]
                current_tokens = pt
        else:
            current.append(para)
            current_tokens += pt
    if current:
        chunks.append("\n\n".join(current))
    return chunks or [body]


def _build_chunk(
    *,
    doc_id: str,
    scheme_id: str,
    scheme_name: str,
    doc_type: str,
    source_url: str,
    effective_date: str | None,
    ingested_at: str,
    section: str,
    section_path: str,
    ordinal: int,
    kind: str,
    body: str,
    facets: list[str] | None = None,
    parent_id: str | None = None,
) -> Chunk | None:
    body = (body or "").strip()
    if not body:
        return None

    facets = list(dict.fromkeys(f for f in (facets or []) if f in CORE_FACETS))
    facet = primary_facet(facets)
    body_tokens = estimate_tokens(body)

    # Quality gate: drop empty / too-small unless core facet tagged or structural kind
    structural = kind in {
        "overview_parent",
        "overview_row",
        "holdings",
        "riskometer",
        "faq",
    }
    if body_tokens < HARD_MIN_BODY_TOKENS and not facet and not structural:
        return None

    prefix = format_prefix(scheme_name, doc_type, section, facet)
    text = f"{prefix}\n{body}"
    chash = body_hash(body)
    chunk_id = make_chunk_id(doc_id, section_path, ordinal, chash)
    return Chunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        scheme_id=scheme_id,
        scheme_name=scheme_name,
        doc_type=doc_type,
        source_url=source_url,
        effective_date=effective_date,
        ingested_at=ingested_at,
        section=section,
        facet=facet,
        facets=facets,
        parent_id=parent_id,
        ordinal=ordinal,
        kind=kind,
        text=text,
        body=body,
        token_estimate=estimate_tokens(text),
        content_hash=chash,
    )


def _dedupe_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Drop exact body duplicates; prefer overview_row / overview_parent over FAQ/prose."""
    priority = {
        "overview_row": 0,
        "overview_parent": 1,
        "riskometer": 2,
        "faq": 3,
        "prose": 4,
        "holdings": 5,
    }
    best: dict[str, Chunk] = {}
    order: list[str] = []
    for c in chunks:
        key = c.content_hash
        if key not in best:
            best[key] = c
            order.append(key)
            continue
        prev = best[key]
        if priority.get(c.kind, 9) < priority.get(prev.kind, 9):
            best[key] = c
    return [best[k] for k in order]


def chunk_overview_tables(
    tables: list[dict[str, Any]],
    *,
    meta: dict[str, Any],
    ordinal_start: int,
) -> tuple[list[Chunk], int]:
    chunks: list[Chunk] = []
    ordinal = ordinal_start
    for table in tables:
        kind = table.get("kind") or ""
        caption = str(table.get("caption") or "Overview")
        serialized = str(table.get("serialized") or "").strip()
        rows = table.get("rows") or []
        headers = table.get("headers") or ["Field", "Value"]

        is_risk = "riskometer" in caption.lower() or table.get("table_id") == "riskometer"
        is_overview = kind == "overview_kv" and (
            table.get("fee_load_relevant")
            or "overview" in caption.lower()
            or table.get("table_id") == "fund_overview_info"
        )

        if not (is_overview or is_risk):
            if kind != "overview_kv":
                continue
            # other overview_kv (rare): still emit parent
            is_overview = True

        section = caption
        section_path = f"table/{table.get('table_id') or caption}"
        parent = _build_chunk(
            **meta,
            section=section,
            section_path=section_path,
            ordinal=ordinal,
            kind="riskometer" if is_risk else "overview_parent",
            body=serialized,
            facets=["riskometer"] if is_risk else [],
            parent_id=None,
        )
        ordinal += 1
        if not parent:
            continue
        chunks.append(parent)
        parent_id = parent.chunk_id

        if is_risk:
            continue

        # Per-row children for core facet labels
        header_line = " | ".join(str(h) for h in headers)
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            label, value = str(row[0]).strip(), str(row[1]).strip()
            row_facets = facets_for_label(label)
            if not row_facets:
                continue
            # Never split mid-cell: whole value stays on one line
            row_body = f"{header_line}\n{label} | {value}"
            child = _build_chunk(
                **meta,
                section=f"{section} / {label}",
                section_path=f"{section_path}/row/{label.lower().replace(' ', '_')}",
                ordinal=ordinal,
                kind="overview_row",
                body=row_body,
                facets=row_facets,
                parent_id=parent_id,
            )
            ordinal += 1
            if child:
                chunks.append(child)
    return chunks, ordinal


def chunk_holdings_tables(
    tables: list[dict[str, Any]],
    *,
    meta: dict[str, Any],
    ordinal_start: int,
) -> tuple[list[Chunk], int]:
    chunks: list[Chunk] = []
    ordinal = ordinal_start
    for table in tables:
        if (table.get("kind") or "") != "holdings":
            continue
        caption = str(table.get("caption") or "Holdings")
        serialized = str(table.get("serialized") or "").strip()
        if not serialized:
            continue
        bodies = _split_oversized(serialized)
        for i, body in enumerate(bodies):
            c = _build_chunk(
                **meta,
                section=caption if len(bodies) == 1 else f"{caption} ({i+1})",
                section_path=f"table/{table.get('table_id') or caption}/{i}",
                ordinal=ordinal,
                kind="holdings",
                body=body,
                facets=[],
            )
            ordinal += 1
            if c:
                chunks.append(c)
    return chunks, ordinal


def _same_theme(a_heading: str, b_heading: str) -> bool:
    """Conservative merge: only identical normalized headings."""
    return re.sub(r"\W+", "", a_heading.lower()) == re.sub(r"\W+", "", b_heading.lower())


def chunk_sections(
    sections: list[dict[str, Any]],
    *,
    meta: dict[str, Any],
    ordinal_start: int,
    skip_overview_prose: bool,
) -> tuple[list[Chunk], int]:
    chunks: list[Chunk] = []
    ordinal = ordinal_start

    # Prepare list with optional merges for tiny non-facet siblings
    prepared: list[dict[str, Any]] = []
    i = 0
    while i < len(sections):
        sec = sections[i]
        heading = str(sec.get("heading") or "").strip()
        text = str(sec.get("text") or "").strip()
        hints = list(sec.get("facet_hints") or [])
        if not heading or not text:
            i += 1
            continue

        if heading.lower().startswith("faq:"):
            prepared.append(sec)
            i += 1
            continue

        if skip_overview_prose and "overview" in heading.lower():
            i += 1
            continue

        body_tokens = estimate_tokens(text)
        core_hints = [h for h in hints if h in CORE_FACETS]
        if (
            body_tokens < HARD_MIN_BODY_TOKENS
            and not core_hints
            and i + 1 < len(sections)
        ):
            nxt = sections[i + 1]
            nh = str(nxt.get("heading") or "")
            if not nh.lower().startswith("faq:") and _same_theme(heading, nh):
                merged = {
                    "heading": heading,
                    "text": text + "\n\n" + str(nxt.get("text") or "").strip(),
                    "facet_hints": list(
                        dict.fromkeys(hints + list(nxt.get("facet_hints") or []))
                    ),
                }
                prepared.append(merged)
                i += 2
                continue

        prepared.append(sec)
        i += 1

    for sec in prepared:
        heading = str(sec.get("heading") or "").strip()
        text = str(sec.get("text") or "").strip()
        hints = [h for h in (sec.get("facet_hints") or []) if h]
        is_faq = heading.lower().startswith("faq:")
        kind = "faq" if is_faq else "prose"
        section_label = heading
        if is_faq:
            body = f"Q: {heading[4:].strip()}\nA: {text}"
        else:
            body = text

        for j, part in enumerate(_split_oversized(body)):
            c = _build_chunk(
                **meta,
                section=section_label if j == 0 else f"{section_label} ({j+1})",
                section_path=f"section/{heading}/{j}",
                ordinal=ordinal,
                kind=kind,
                body=part,
                facets=hints,
            )
            ordinal += 1
            if c:
                chunks.append(c)

    return chunks, ordinal


def chunk_parsed_document(parsed: dict[str, Any], *, ingested_at: str | None = None) -> list[Chunk]:
    source_url = str(parsed.get("source_url") or "")
    if not source_url or not is_allowed_citation(source_url):
        raise ValueError(f"source_url not allowlisted: {source_url}")

    scheme_id = str(parsed["scheme_id"])
    doc_id = str(parsed.get("doc_id") or scheme_id)
    scheme_name = str(parsed.get("display_name") or parsed.get("title") or scheme_id)
    doc_type = str(parsed.get("doc_type") or "scheme_reference_page")
    effective_date = parsed.get("as_of_date") or (
        (parsed.get("structured_fact_candidates") or {}).get("as_of_date")
    )
    ingested = ingested_at or _utc_now_iso()

    meta = {
        "doc_id": doc_id,
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
        "doc_type": doc_type,
        "source_url": source_url,
        "effective_date": effective_date,
        "ingested_at": ingested,
    }

    tables = list(parsed.get("tables") or [])
    sections = list(parsed.get("sections") or [])

    chunks: list[Chunk] = []
    ordinal = 0

    part, ordinal = chunk_overview_tables(tables, meta=meta, ordinal_start=ordinal)
    chunks.extend(part)

    has_overview_table = any(
        (t.get("kind") == "overview_kv" and t.get("fee_load_relevant"))
        or t.get("table_id") == "fund_overview_info"
        for t in tables
    )

    part, ordinal = chunk_holdings_tables(tables, meta=meta, ordinal_start=ordinal)
    chunks.extend(part)

    part, ordinal = chunk_sections(
        sections,
        meta=meta,
        ordinal_start=ordinal,
        skip_overview_prose=has_overview_table,
    )
    chunks.extend(part)

    chunks = _dedupe_chunks(chunks)

    # Hard max enforcement after prefix
    final: list[Chunk] = []
    for c in chunks:
        if c.token_estimate <= HARD_MAX_TOKENS:
            final.append(c)
            continue
        # Re-split rare oversized (prefix + body)
        for j, body_part in enumerate(_split_oversized(c.body, HARD_MAX_TOKENS - 40)):
            rebuilt = _build_chunk(
                doc_id=c.doc_id,
                scheme_id=c.scheme_id,
                scheme_name=c.scheme_name,
                doc_type=c.doc_type,
                source_url=c.source_url,
                effective_date=c.effective_date,
                ingested_at=c.ingested_at,
                section=c.section if j == 0 else f"{c.section} ({j+1})",
                section_path=f"{c.section}/{c.ordinal}/{j}",
                ordinal=c.ordinal * 100 + j,
                kind=c.kind,
                body=body_part,
                facets=c.facets,
                parent_id=c.parent_id,
            )
            if rebuilt:
                final.append(rebuilt)
    return final


def facet_coverage(chunks: list[Chunk], structured_facts: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    present = sorted({f for c in chunks for f in c.facets if f in CORE_FACETS - {"process_statements", "min_investment"}})
    # Core smoke set
    core = ["expense_ratio", "exit_load", "min_sip", "riskometer", "benchmark"]
    from_chunks = {c.facet for c in chunks if c.facet in core}
    from_chunks |= {f for c in chunks for f in c.facets if f in core}
    if structured_facts:
        for f in core:
            if structured_facts.get(f):
                from_chunks.add(f)
    present_core = [f for f in core if f in from_chunks]
    absent = [f for f in core if f not in from_chunks]
    return present_core, absent


def write_scheme_artifacts(
    scheme_id: str,
    chunks: list[Chunk],
    chunks_dir: Path,
    *,
    coverage: dict[str, Any],
) -> tuple[Path, Path]:
    chunks_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "scheme_id": scheme_id,
        "chunk_count": len(chunks),
        "coverage": coverage,
        "chunks": [asdict(c) for c in chunks],
    }
    json_path = chunks_dir / f"{scheme_id}.json"
    jsonl_path = chunks_dir / f"{scheme_id}.jsonl"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
    return json_path, jsonl_path


def write_qc_notes(results: list[SchemeChunkResult], chunks_by_scheme: dict[str, list[Chunk]], path: Path) -> None:
    lines = [
        "# Chunk QC notes (Phase 1.3)",
        "",
        "Strategy: overview parent + per-row facet children; FAQ one-shot; holdings whole-table;",
        "prose sections with scheme/doc/section prefixes. Hard max 512 tokens.",
        "",
    ]
    for r in results:
        lines.append(f"## {r.scheme_id}")
        if r.status != "success":
            lines.append(f"- FAILED: {r.error}")
            lines.append("")
            continue
        lines.append(f"- chunks: {r.chunk_count}")
        lines.append(f"- max_token_estimate: {r.max_token_estimate}")
        lines.append(f"- facets_present: {', '.join(r.facets_present) or '(none)'}")
        lines.append(f"- facets_absent: {', '.join(r.facets_absent) or '(none)'}")
        sample = chunks_by_scheme.get(r.scheme_id) or []
        row = next((c for c in sample if c.kind == "overview_row" and c.facet == "exit_load"), None)
        if row:
            lines.append("- exit_load row sample:")
            lines.append("```")
            lines.append(row.body)
            lines.append("```")
            if "\n" in row.body.split(" | ", 1)[-1] and row.body.count("\n") > 1:
                # value should be single line after header
                pass
            # mid-cell check: each data line has exactly one pipe separator group
            data_lines = row.body.splitlines()[1:]
            ok = all(line.count(" | ") >= 1 for line in data_lines)
            lines.append(f"- exit_load mid-cell intact: {ok}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_chunk_log(summary: ChunkRunSummary, path: Path) -> None:
    payload = {
        "version": 1,
        "run_id": summary.run_id,
        "started_at": summary.started_at,
        "finished_at": summary.finished_at,
        "overall_status": summary.overall_status,
        "schemes": [asdict(s) for s in summary.schemes],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_structured_facts(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("schemes") or {}


def chunk_scheme_file(
    parsed_path: Path,
    *,
    chunks_dir: Path,
    structured_facts: dict[str, Any] | None = None,
    ingested_at: str | None = None,
) -> tuple[SchemeChunkResult, list[Chunk]]:
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    scheme_id = str(parsed.get("scheme_id") or parsed_path.stem)
    try:
        chunks = chunk_parsed_document(parsed, ingested_at=ingested_at)
    except ValueError as exc:
        return (
            SchemeChunkResult(
                scheme_id=scheme_id,
                source_url=str(parsed.get("source_url") or ""),
                status="failed",
                error=str(exc),
            ),
            [],
        )

    if not chunks:
        return (
            SchemeChunkResult(
                scheme_id=scheme_id,
                source_url=str(parsed.get("source_url") or ""),
                status="failed",
                error="No chunks emitted",
            ),
            [],
        )

    facts = (structured_facts or {}).get(scheme_id)
    present, absent = facet_coverage(chunks, facts)
    coverage = {
        "facets_present": present,
        "facets_absent": absent,
        "kinds": sorted({c.kind for c in chunks}),
    }
    json_path, jsonl_path = write_scheme_artifacts(
        scheme_id, chunks, chunks_dir, coverage=coverage
    )
    return (
        SchemeChunkResult(
            scheme_id=scheme_id,
            source_url=str(parsed.get("source_url") or ""),
            status="success",
            chunk_count=len(chunks),
            facets_present=present,
            facets_absent=absent,
            artifact_json=_display_path(json_path),
            artifact_jsonl=_display_path(jsonl_path),
            max_token_estimate=max(c.token_estimate for c in chunks),
        ),
        chunks,
    )


def run_chunk(
    *,
    manifest_path: str | Path | None = None,
    parsed_dir: str | Path | None = None,
    chunks_dir: str | Path | None = None,
    structured_facts_path: str | Path | None = None,
    scheme_ids: set[str] | None = None,
) -> ChunkRunSummary:
    settings = get_settings()
    manifest = _resolve_path(manifest_path or settings.manifest_path)
    parsed = _resolve_path(parsed_dir or settings.parsed_dir)
    out = _resolve_path(chunks_dir or getattr(settings, "chunks_dir", "data/processed/chunks"))
    facts_path = _resolve_path(structured_facts_path or settings.structured_facts_path)
    facts = load_structured_facts(facts_path)

    schemes = load_manifest_schemes(manifest)
    if scheme_ids:
        schemes = [s for s in schemes if s.get("scheme_id") in scheme_ids]
        missing = scheme_ids - {s.get("scheme_id") for s in schemes}
        if missing:
            raise ValueError(f"Unknown scheme_id(s): {sorted(missing)}")

    started_at = _utc_now_iso()
    run_id = started_at.replace(":", "").replace("+", "Z")
    results: list[SchemeChunkResult] = []
    chunks_by_scheme: dict[str, list[Chunk]] = {}

    for scheme in schemes:
        scheme_id = str(scheme["scheme_id"])
        # Fail closed on manifest URL before reading parse artifact
        url = str(scheme.get("source_url") or "")
        if not is_allowed_citation(url):
            results.append(
                SchemeChunkResult(
                    scheme_id=scheme_id,
                    source_url=url,
                    status="failed",
                    error=f"source_url not allowlisted: {url}",
                )
            )
            continue

        parsed_path = parsed / f"{scheme_id}.json"
        if not parsed_path.exists():
            results.append(
                SchemeChunkResult(
                    scheme_id=scheme_id,
                    source_url=url,
                    status="failed",
                    error=f"Missing parsed artifact: {parsed_path}",
                )
            )
            continue

        result, chunks = chunk_scheme_file(
            parsed_path,
            chunks_dir=out,
            structured_facts=facts,
            ingested_at=started_at,
        )
        results.append(result)
        if chunks:
            chunks_by_scheme[scheme_id] = chunks

    finished_at = _utc_now_iso()
    overall = (
        "success"
        if results and all(r.status == "success" for r in results)
        else "failed"
    )
    summary = ChunkRunSummary(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        overall_status=overall,
        schemes=results,
    )
    out.mkdir(parents=True, exist_ok=True)
    write_chunk_log(summary, out / "chunk_log.yaml")
    write_qc_notes(results, chunks_by_scheme, out / "CHUNK_QC.md")
    return summary


def _print_summary(summary: ChunkRunSummary) -> None:
    print(f"Chunk run {summary.run_id}: {summary.overall_status}")
    for r in summary.schemes:
        flag = "OK" if r.status == "success" else "FAIL"
        detail = (
            f"{r.chunk_count} chunks, max_tok={r.max_token_estimate}, "
            f"facets={r.facets_present}"
            if r.status == "success"
            else r.error
        )
        print(f"  [{flag}] {r.scheme_id}: {detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chunk parsed scheme JSON into data/processed/chunks/"
    )
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--parsed-dir", default=None)
    parser.add_argument("--chunks-dir", default=None)
    parser.add_argument("--structured-facts", default=None)
    parser.add_argument("--scheme-id", action="append", dest="scheme_ids", default=None)
    args = parser.parse_args(argv)

    try:
        summary = run_chunk(
            manifest_path=args.manifest,
            parsed_dir=args.parsed_dir,
            chunks_dir=args.chunks_dir,
            structured_facts_path=args.structured_facts,
            scheme_ids=set(args.scheme_ids) if args.scheme_ids else None,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Chunk aborted: {exc}", file=sys.stderr)
        return 2

    _print_summary(summary)
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
