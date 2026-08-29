"""
Phase 1.2 — Parse allowlisted raw scheme HTML into clean text/tables.

Uses local files under data/raw/ only (no network). Prefers __NEXT_DATA__
fund payloads when present; falls back to stripped DOM extraction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag

from src.config import REPO_ROOT, get_settings
from src.guardrails.citations import is_allowed_citation
from src.ingest.fetch import load_manifest_schemes
from src.logging_config import get_logger, log_checkpoint, log_manifest_roster, setup_logging

logger = get_logger(__name__)

STRIP_TAGS = (
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "button",
)

COOKIE_BANNER_HINTS = re.compile(
    r"cookie|consent|newsletter|download.?app|login|sign.?up|advert",
    re.I,
)

FACT_LABEL_MAP = {
    "expense ratio": "expense_ratio",
    "total expense ratio": "expense_ratio",
    "ter": "expense_ratio",
    "exit load": "exit_load",
    "benchmark": "benchmark",
    "min lumpsum/sip": "min_sip",
    "minimum sip": "min_sip",
    "min sip": "min_sip",
    "risk": "riskometer",
    "riskometer": "riskometer",
    "lock in": "lock_in",
    "lock-in": "lock_in",
}


@dataclass
class ParsedTable:
    table_id: str
    caption: str
    headers: list[str]
    rows: list[list[str]]
    serialized: str
    kind: str = "generic"  # overview_kv | holdings | performance | generic
    fee_load_relevant: bool = False


@dataclass
class ParsedSection:
    heading: str
    text: str
    facet_hints: list[str] = field(default_factory=list)


@dataclass
class SchemeParseResult:
    scheme_id: str
    doc_id: str
    display_name: str
    source_url: str
    status: str
    parsed_at: str | None = None
    content_hash: str | None = None
    title: str | None = None
    as_of_date: str | None = None
    main_text: str | None = None
    sections: list[ParsedSection] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    structured_fact_candidates: dict[str, Any] = field(default_factory=dict)
    flags: dict[str, Any] = field(default_factory=dict)
    artifact_path: str | None = None
    error: str | None = None


@dataclass
class ParseRunSummary:
    run_id: str
    started_at: str
    finished_at: str
    overall_status: str
    schemes: list[SchemeParseResult] = field(default_factory=list)

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


def content_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _clean_text(text: str) -> str:
    text = unescape(text or "")
    text = BeautifulSoup(text, "lxml").get_text(" ", strip=True)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _facet_hints_for(label: str) -> list[str]:
    low = label.lower()
    hints: list[str] = []
    mapping = [
        ("expense", "expense_ratio"),
        ("ter", "expense_ratio"),
        ("exit load", "exit_load"),
        ("load structure", "exit_load"),
        ("sip", "min_sip"),
        ("minimum investment", "min_investment"),
        ("min lumpsum", "min_investment"),
        ("lock", "lock_in"),
        ("riskometer", "riskometer"),
        ("risk", "riskometer"),
        ("benchmark", "benchmark"),
        ("statement", "process_statements"),
        ("capital gains", "process_statements"),
    ]
    for needle, facet in mapping:
        if needle in low and facet not in hints:
            hints.append(facet)
    return hints


def serialize_table(headers: list[str], rows: list[list[str]]) -> str:
    """Stable pipe-separated rows; never splits mid-cell."""
    lines: list[str] = []
    if headers:
        lines.append(" | ".join(headers))
    for row in rows:
        # Pad/truncate to header width when headers exist
        if headers:
            padded = list(row) + [""] * max(0, len(headers) - len(row))
            padded = padded[: len(headers)]
            lines.append(" | ".join(padded))
        else:
            lines.append(" | ".join(row))
    return "\n".join(lines)


def _kv_table(
    table_id: str,
    caption: str,
    pairs: list[tuple[str, str]],
    *,
    kind: str = "overview_kv",
) -> ParsedTable:
    headers = ["Field", "Value"]
    rows = [[k, v] for k, v in pairs if k and v]
    fee = any(
        _facet_hints_for(k) for k, _ in pairs if "expense" in k.lower() or "exit" in k.lower()
    )
    return ParsedTable(
        table_id=table_id,
        caption=caption,
        headers=headers,
        rows=rows,
        serialized=serialize_table(headers, rows),
        kind=kind,
        fee_load_relevant=fee or any("load" in k.lower() or "expense" in k.lower() for k, _ in pairs),
    )


def _extract_next_data(soup: BeautifulSoup) -> dict[str, Any] | None:
    node = soup.find("script", id="__NEXT_DATA__")
    if not node or not node.string:
        return None
    try:
        payload = json.loads(node.string)
    except json.JSONDecodeError:
        return None
    try:
        return payload["props"]["pageProps"]["mutualFundsDetailData"]["data"]
    except (KeyError, TypeError):
        return None


def parse_from_next_data(mf: dict[str, Any]) -> tuple[
    str,
    str | None,
    list[ParsedSection],
    list[ParsedTable],
    dict[str, Any],
    str,
]:
    title = str(mf.get("name") or mf.get("short_name") or "")
    as_of = str(mf.get("nav_date") or "") or None
    sections: list[ParsedSection] = []
    tables: list[ParsedTable] = []
    facts: dict[str, Any] = {
        "expense_ratio": None,
        "exit_load": None,
        "min_sip": None,
        "riskometer": None,
        "benchmark": None,
        "lock_in": None,
        "min_lumpsum": None,
        "aum": None,
        "as_of_date": as_of,
    }

    overview = mf.get("fund_overview") or {}
    info = overview.get("info") or []
    pairs: list[tuple[str, str]] = []
    for item in info:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        desc = str(item.get("description") or "").strip()
        if not name or not value:
            continue
        cell = value if not desc else f"{value} — {desc}"
        pairs.append((name, cell))
        key = FACT_LABEL_MAP.get(name.lower())
        if key == "expense_ratio":
            facts["expense_ratio"] = value
        elif key == "exit_load":
            facts["exit_load"] = cell
        elif key == "benchmark":
            facts["benchmark"] = value
        elif key == "min_sip":
            parts = [p.strip() for p in re.split(r"[/|]", value) if p.strip()]
            if len(parts) >= 2:
                facts["min_lumpsum"] = parts[0]
                facts["min_sip"] = parts[1]
            else:
                facts["min_sip"] = value
        elif key == "lock_in":
            facts["lock_in"] = value
        elif name.lower() == "aum":
            facts["aum"] = value

    if pairs:
        tables.append(
            _kv_table(
                "fund_overview_info",
                str(overview.get("display_name") or "Fund Overview"),
                pairs,
            )
        )
        sections.append(
            ParsedSection(
                heading=str(overview.get("display_name") or "Fund Overview"),
                text="\n".join(f"{k}: {v}" for k, v in pairs),
                facet_hints=sorted({h for k, _ in pairs for h in _facet_hints_for(k)}),
            )
        )

    risk = ((mf.get("risk_meter") or {}).get("widget_properties")) or {}
    if risk:
        zone = str(risk.get("zone_title") or "").strip()
        body = str(risk.get("body") or "").strip()
        risk_text = " | ".join(x for x in (zone, body) if x)
        if risk_text:
            facts["riskometer"] = zone or body
            sections.append(
                ParsedSection(
                    heading=str(risk.get("title") or "Riskometer"),
                    text=risk_text,
                    facet_hints=["riskometer"],
                )
            )
            tables.append(
                _kv_table(
                    "riskometer",
                    "Riskometer",
                    [("Riskometer", risk_text)],
                )
            )

    about = mf.get("about") or {}
    for block in about.get("about_fund") or []:
        if not isinstance(block, dict):
            continue
        heading = _clean_text(str(block.get("title") or "")) or "About"
        texts: list[str] = []
        for part in block.get("text") or []:
            if isinstance(part, dict):
                texts.append(_clean_text(str(part.get("title") or "")))
        body = "\n".join(t for t in texts if t)
        if not body:
            continue
        sections.append(
            ParsedSection(
                heading=heading,
                text=body,
                facet_hints=_facet_hints_for(heading + " " + body),
            )
        )

    holdings = mf.get("holdings") or {}
    for bucket in holdings.get("holdings") or []:
        if not isinstance(bucket, dict):
            continue
        rows_raw = ((bucket.get("table") or {}).get("rows")) or []
        if not rows_raw:
            continue
        headers = ["Holding", "Weight%", "1M Change"]
        rows: list[list[str]] = []
        for row in rows_raw[:15]:
            if not isinstance(row, dict):
                continue
            cols = row.get("columns") or []
            weight = ""
            change = ""
            if isinstance(cols, list):
                texts = [
                    str(c.get("title") or "")
                    for c in cols
                    if isinstance(c, dict) and c.get("trait") == "text"
                ]
                if len(texts) >= 2:
                    weight = texts[1]
                if len(texts) >= 3:
                    change = texts[2]
            if not weight:
                weight = str(row.get("perc") or row.get("weight") or "")
            rows.append(
                [
                    str(row.get("name") or ""),
                    weight,
                    change or str(row.get("change") or ""),
                ]
            )
        if rows:
            caption = str(bucket.get("name") or holdings.get("display_name") or "Holdings")
            tables.append(
                ParsedTable(
                    table_id=f"holdings_{re.sub(r'[^a-z0-9]+', '_', caption.lower()).strip('_')}",
                    caption=caption,
                    headers=headers,
                    rows=rows,
                    serialized=serialize_table(headers, rows),
                    kind="holdings",
                )
            )

    for faq in ((mf.get("static_content") or {}).get("faqs")) or []:
        if not isinstance(faq, dict):
            continue
        q = faq.get("ques") or faq.get("question") or ""
        if isinstance(q, dict):
            q_text = _clean_text(str(q.get("label") or q.get("title") or q.get("text") or ""))
        else:
            q_text = _clean_text(str(q))
        ans_parts: list[str] = []
        for ans in faq.get("ans") or []:
            if not isinstance(ans, dict):
                continue
            text = ans.get("text") or {}
            if isinstance(text, dict):
                ans_parts.append(_clean_text(str(text.get("label") or text.get("title") or "")))
            else:
                ans_parts.append(_clean_text(str(text)))
        a_text = " ".join(p for p in ans_parts if p)
        if q_text and a_text:
            sections.append(
                ParsedSection(
                    heading=f"FAQ: {q_text}",
                    text=a_text,
                    facet_hints=_facet_hints_for(q_text + " " + a_text),
                )
            )

    main_parts = [f"## {s.heading}\n{s.text}" for s in sections if s.text]
    for t in tables:
        main_parts.append(f"## Table: {t.caption}\n{t.serialized}")
    main_text = "\n\n".join(main_parts).strip()
    return title, as_of, sections, tables, facts, main_text


def _dom_table_to_parsed(table: Tag, idx: int) -> ParsedTable | None:
    rows_el = table.find_all("tr")
    if not rows_el:
        return None
    matrix: list[list[str]] = []
    for tr in rows_el:
        cells = tr.find_all(["th", "td"])
        row = [_clean_text(c.get_text(" ", strip=True)) for c in cells]
        if any(row):
            matrix.append(row)
    if not matrix:
        return None

    # Heuristic: if first row is all th, treat as headers
    first_row_ths = rows_el[0].find_all("th")
    if first_row_ths and len(first_row_ths) == len(matrix[0]):
        headers = matrix[0]
        body = matrix[1:]
    elif len(matrix[0]) == 2 and all(len(r) == 2 for r in matrix):
        # Key-value style (Key Parameters)
        headers = ["Field", "Value"]
        body = matrix
    else:
        headers = [f"col_{i+1}" for i in range(len(matrix[0]))]
        body = matrix

    caption_el = table.find("caption")
    caption = _clean_text(caption_el.get_text(" ", strip=True)) if caption_el else f"table_{idx}"
    serialized = serialize_table(headers, body)
    fee = bool(
        re.search(r"expense|exit\s*load|ter", serialized, re.I)
        or re.search(r"expense|exit\s*load", caption, re.I)
    )
    return ParsedTable(
        table_id=f"dom_table_{idx}",
        caption=caption,
        headers=headers,
        rows=body,
        serialized=serialized,
        kind="overview_kv" if fee and len(headers) == 2 else "generic",
        fee_load_relevant=fee,
    )


def parse_from_dom(soup: BeautifulSoup) -> tuple[str, list[ParsedSection], list[ParsedTable], str]:
    """Strip chrome and extract visible text + HTML tables."""
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    for el in soup.find_all(True):
        if not isinstance(el, Tag):
            continue
        meta = " ".join(
            [
                " ".join(el.get("class", []) or []),
                str(el.get("id") or ""),
                str(el.get("role") or ""),
            ]
        )
        if COOKIE_BANNER_HINTS.search(meta):
            el.decompose()

    title = _clean_text(soup.title.get_text()) if soup.title else ""
    root = soup.find("main") or soup.find("article") or soup.body or soup

    tables: list[ParsedTable] = []
    for i, table in enumerate(root.find_all("table")):
        parsed = _dom_table_to_parsed(table, i)
        if parsed:
            tables.append(parsed)
        table.decompose()  # avoid duplicating table text in prose

    sections: list[ParsedSection] = []
    headings = root.find_all(["h1", "h2", "h3"])
    if headings:
        for h in headings:
            heading = _clean_text(h.get_text(" ", strip=True))
            if not heading:
                continue
            bits: list[str] = []
            for sib in h.next_siblings:
                if isinstance(sib, Tag) and sib.name in {"h1", "h2", "h3"}:
                    break
                if isinstance(sib, NavigableString):
                    t = _clean_text(str(sib))
                    if t:
                        bits.append(t)
                elif isinstance(sib, Tag):
                    if sib.name in STRIP_TAGS:
                        continue
                    t = _clean_text(sib.get_text(" ", strip=True))
                    if t:
                        bits.append(t)
            text = "\n".join(bits).strip()
            if text:
                sections.append(
                    ParsedSection(
                        heading=heading,
                        text=text,
                        facet_hints=_facet_hints_for(heading + " " + text),
                    )
                )
    else:
        text = _clean_text(root.get_text("\n", strip=True))
        if text:
            sections.append(ParsedSection(heading="Document", text=text, facet_hints=[]))

    # Drop very short marketing leftovers
    sections = [s for s in sections if len(s.text) >= 40 or _facet_hints_for(s.heading)]

    main_parts = [f"## {s.heading}\n{s.text}" for s in sections]
    for t in tables:
        main_parts.append(f"## Table: {t.caption}\n{t.serialized}")
    main_text = "\n\n".join(main_parts).strip()
    return title, sections, tables, main_text


def extract_facts_from_tables(tables: list[ParsedTable]) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "expense_ratio": None,
        "exit_load": None,
        "min_sip": None,
        "riskometer": None,
        "benchmark": None,
    }
    for table in tables:
        if len(table.headers) == 2 or table.kind == "overview_kv":
            for row in table.rows:
                if len(row) < 2:
                    continue
                label, value = row[0], row[1]
                key = FACT_LABEL_MAP.get(label.lower().strip())
                if key == "expense_ratio" and not facts["expense_ratio"]:
                    facts["expense_ratio"] = value.split("—")[0].strip()
                elif key == "exit_load" and not facts["exit_load"]:
                    facts["exit_load"] = value
                elif key == "benchmark" and not facts["benchmark"]:
                    facts["benchmark"] = value.split("—")[0].strip()
                elif key == "min_sip" and not facts["min_sip"]:
                    parts = [p.strip() for p in re.split(r"[/|]", value) if p.strip()]
                    facts["min_sip"] = parts[1] if len(parts) >= 2 else value
                elif key == "riskometer" and not facts["riskometer"]:
                    facts["riskometer"] = value
        # Single-row wide header tables (peer style) — skip for facts
    return facts


def parse_scheme_html(
    scheme: dict[str, Any],
    *,
    raw_dir: Path,
    parsed_dir: Path,
) -> SchemeParseResult:
    scheme_id = str(scheme["scheme_id"])
    display_name = str(scheme.get("display_name") or scheme_id)
    source_url = str(scheme.get("source_url") or "")
    parsed_at = _utc_now_iso()

    if not source_url or not is_allowed_citation(source_url):
        return SchemeParseResult(
            scheme_id=scheme_id,
            doc_id=scheme_id,
            display_name=display_name,
            source_url=source_url,
            status="failed",
            parsed_at=parsed_at,
            error=f"source_url not allowlisted: {source_url}",
        )

    html_path = raw_dir / f"{scheme_id}.html"
    if not html_path.exists():
        return SchemeParseResult(
            scheme_id=scheme_id,
            doc_id=scheme_id,
            display_name=display_name,
            source_url=source_url,
            status="failed",
            parsed_at=parsed_at,
            error=f"Missing raw HTML: {html_path}",
        )

    raw_bytes = html_path.read_bytes()
    digest = content_sha256(raw_bytes)
    soup = BeautifulSoup(raw_bytes, "lxml")

    mf = _extract_next_data(soup)
    parse_source = "next_data"
    if mf:
        title, as_of, sections, tables, facts, main_text = parse_from_next_data(mf)
    else:
        parse_source = "dom"
        title, sections, tables, main_text = parse_from_dom(soup)
        as_of = None
        facts = extract_facts_from_tables(tables)

    if not main_text.strip():
        # Last-resort DOM if next_data yielded empty
        if parse_source == "next_data":
            title2, sections2, tables2, main_text2 = parse_from_dom(
                BeautifulSoup(raw_bytes, "lxml")
            )
            if main_text2.strip():
                title = title or title2
                sections = sections2
                tables = tables2
                main_text = main_text2
                parse_source = "dom_fallback"
                facts = {**facts, **{k: v for k, v in extract_facts_from_tables(tables).items() if v}}

    if not main_text.strip():
        return SchemeParseResult(
            scheme_id=scheme_id,
            doc_id=scheme_id,
            display_name=display_name,
            source_url=source_url,
            status="failed",
            parsed_at=parsed_at,
            content_hash=digest,
            error="Empty parse artifact (no text/tables extracted)",
        )

    fee_tables = [t for t in tables if t.fee_load_relevant]
    fee_ok = bool(fee_tables) and all(
        " | " in t.serialized and len(t.serialized.splitlines()) >= 2 for t in fee_tables
    )
    has_expense = bool(facts.get("expense_ratio"))
    has_exit = bool(facts.get("exit_load"))
    manual = not (has_expense and has_exit)

    flags = {
        "parse_source": parse_source,
        "fee_load_tables_ok": fee_ok or (has_expense and has_exit),
        "manual_override_needed": manual,
        "section_count": len(sections),
        "table_count": len(tables),
        "network_used": False,
    }

    parsed_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "scheme_id": scheme_id,
        "doc_id": scheme_id,
        "display_name": display_name,
        "source_url": source_url,
        "doc_type": scheme.get("doc_type") or "scheme_reference_page",
        "parsed_at": parsed_at,
        "content_hash": digest,
        "title": title or display_name,
        "as_of_date": as_of or facts.get("as_of_date"),
        "main_text": main_text,
        "sections": [asdict(s) for s in sections],
        "tables": [asdict(t) for t in tables],
        "structured_fact_candidates": facts,
        "flags": flags,
    }
    out_json = parsed_dir / f"{scheme_id}.json"
    out_txt = parsed_dir / f"{scheme_id}.txt"
    out_json.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    out_txt.write_text(main_text + "\n", encoding="utf-8")

    return SchemeParseResult(
        scheme_id=scheme_id,
        doc_id=scheme_id,
        display_name=display_name,
        source_url=source_url,
        status="success",
        parsed_at=parsed_at,
        content_hash=digest,
        title=title or display_name,
        as_of_date=as_of or facts.get("as_of_date"),
        main_text=main_text,
        sections=sections,
        tables=tables,
        structured_fact_candidates=facts,
        flags=flags,
        artifact_path=_display_path(out_json),
    )


def update_structured_facts(
    results: list[SchemeParseResult],
    structured_facts_path: Path,
) -> None:
    if structured_facts_path.exists():
        data = yaml.safe_load(structured_facts_path.read_text(encoding="utf-8")) or {}
    else:
        data = {
            "version": 1,
            "fields": ["expense_ratio", "exit_load", "min_sip", "riskometer", "benchmark"],
            "schemes": {},
        }

    fact_fields = (
        "expense_ratio",
        "exit_load",
        "min_sip",
        "riskometer",
        "benchmark",
        "lock_in",
        "min_lumpsum",
        "aum",
    )

    schemes = data.setdefault("schemes", {})
    for r in results:
        if r.status != "success":
            continue
        c = r.structured_fact_candidates
        existing = schemes.get(r.scheme_id) or {}
        entry: dict[str, Any] = {
            "source_url": r.source_url,
            "last_updated": c.get("as_of_date") or (r.parsed_at[:10] if r.parsed_at else None),
            "candidates_from": "phase_1_2_parse",
        }
        for field in fact_fields:
            override_key = f"manual_override_{field}"
            if existing.get(override_key):
                entry[field] = existing.get(field)
                entry[override_key] = True
            else:
                entry[field] = c.get(field)
        schemes[r.scheme_id] = entry

    data["updated_at"] = _utc_now_iso()
    structured_facts_path.parent.mkdir(parents=True, exist_ok=True)
    structured_facts_path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def write_parse_log(summary: ParseRunSummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "run_id": summary.run_id,
        "started_at": summary.started_at,
        "finished_at": summary.finished_at,
        "overall_status": summary.overall_status,
        "schemes": [
            {
                "scheme_id": s.scheme_id,
                "status": s.status,
                "source_url": s.source_url,
                "artifact_path": s.artifact_path,
                "content_hash": s.content_hash,
                "flags": s.flags,
                "structured_fact_candidates": s.structured_fact_candidates,
                "error": s.error,
            }
            for s in summary.schemes
        ],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_spot_check_notes(results: list[SchemeParseResult], path: Path) -> None:
    lines = [
        "# Parse spot-check notes (Phase 1.2)",
        "",
        "Fee/load tables are serialized as stable `Field | Value` rows from IndMoney",
        "`fund_overview.info` (or DOM key-parameter tables). Manual override flagged",
        "when expense ratio or exit load could not be extracted.",
        "",
    ]
    for r in results:
        lines.append(f"## {r.scheme_id}")
        if r.status != "success":
            lines.append(f"- Status: FAILED — {r.error}")
            lines.append("")
            continue
        fee_tables = [t for t in r.tables if t.fee_load_relevant]
        lines.append(f"- Status: {r.status}")
        lines.append(f"- Parse source: {r.flags.get('parse_source')}")
        lines.append(f"- Fee/load tables OK: {r.flags.get('fee_load_tables_ok')}")
        lines.append(f"- Manual override needed: {r.flags.get('manual_override_needed')}")
        c = r.structured_fact_candidates
        lines.append(f"- expense_ratio: {c.get('expense_ratio')}")
        lines.append(f"- exit_load: {c.get('exit_load')}")
        lines.append(f"- min_sip: {c.get('min_sip')}")
        lines.append(f"- riskometer: {c.get('riskometer')}")
        lines.append(f"- benchmark: {c.get('benchmark')}")
        if fee_tables:
            lines.append("- Fee/load serialized sample:")
            lines.append("```")
            lines.append(fee_tables[0].serialized)
            lines.append("```")
        else:
            lines.append("- No dedicated fee/load table detected (facts may still come from overview).")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_parse(
    *,
    manifest_path: str | Path | None = None,
    raw_dir: str | Path | None = None,
    parsed_dir: str | Path | None = None,
    structured_facts_path: str | Path | None = None,
    scheme_ids: set[str] | None = None,
) -> ParseRunSummary:
    settings = get_settings()
    manifest = _resolve_path(manifest_path or settings.manifest_path)
    raw = _resolve_path(raw_dir or settings.raw_dir)
    parsed = _resolve_path(parsed_dir or getattr(settings, "parsed_dir", "data/processed/parsed"))
    facts_path = _resolve_path(structured_facts_path or settings.structured_facts_path)

    schemes = load_manifest_schemes(manifest)
    if scheme_ids:
        schemes = [s for s in schemes if s.get("scheme_id") in scheme_ids]
        missing = scheme_ids - {s.get("scheme_id") for s in schemes}
        if missing:
            raise ValueError(f"Unknown scheme_id(s): {sorted(missing)}")

    started_at = _utc_now_iso()
    run_id = started_at.replace(":", "").replace("+", "Z")
    log_checkpoint(
        logger, "P1.2", "manifest", "Parse allowlisted raw HTML", schemes=len(schemes), run_id=run_id
    )
    log_manifest_roster(logger, schemes)
    results: list[SchemeParseResult] = []
    for index, scheme in enumerate(schemes):
        scheme_id = str(scheme["scheme_id"])
        display = str(scheme.get("display_name") or scheme_id)
        step = f"[{index + 1}/{len(schemes)}]"
        log_checkpoint(
            logger, "P1.2", "parse_html", f"Extract text/tables for {display}", scheme_id=scheme_id
        )
        result = parse_scheme_html(scheme, raw_dir=raw, parsed_dir=parsed)
        results.append(result)
        if result.status == "success":
            facts = result.structured_fact_candidates or {}
            word_count = len((result.main_text or "").split())
            logger.info(
                "%s %s OK | sections=%d | words=%d | expense_ratio=%s",
                step,
                scheme_id,
                len(result.sections),
                word_count,
                facts.get("expense_ratio"),
            )
        else:
            logger.error("%s %s FAILED | %s", step, scheme_id, result.error)
    finished_at = _utc_now_iso()
    overall = (
        "success"
        if results and all(r.status == "success" for r in results)
        else "failed"
    )
    summary = ParseRunSummary(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        overall_status=overall,
        schemes=results,
    )

    update_structured_facts(results, facts_path)
    write_parse_log(summary, parsed / "parse_log.yaml")
    write_spot_check_notes(results, parsed / "SPOT_CHECK.md")
    log_checkpoint(
        logger,
        "P1.2",
        "structured_facts",
        "Updated structured_facts.yaml candidates",
        path=_display_path(facts_path),
        schemes=len(results),
    )
    _log_parse_summary(summary)
    return summary


def _log_parse_summary(summary: ParseRunSummary) -> None:
    ok = sum(1 for r in summary.schemes if r.status == "success")
    logger.info(
        "Parse summary | status=%s | ok=%d/%d | run_id=%s",
        summary.overall_status,
        ok,
        len(summary.schemes),
        summary.run_id,
    )


def _print_summary(summary: ParseRunSummary) -> None:
    _log_parse_summary(summary)
    for r in summary.schemes:
        flag = "OK" if r.status == "success" else "FAIL"
        detail = r.artifact_path or r.error or ""
        facts = r.structured_fact_candidates
        er = facts.get("expense_ratio") if facts else None
        print(f"  [{flag}] {r.scheme_id}: {detail} (expense_ratio={er})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse allowlisted raw scheme HTML into data/processed/parsed/"
    )
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--raw-dir", default=None)
    parser.add_argument("--parsed-dir", default=None)
    parser.add_argument("--structured-facts", default=None)
    parser.add_argument("--scheme-id", action="append", dest="scheme_ids", default=None)
    args = parser.parse_args(argv)
    setup_logging(get_settings().log_level)

    try:
        summary = run_parse(
            manifest_path=args.manifest,
            raw_dir=args.raw_dir,
            parsed_dir=args.parsed_dir,
            structured_facts_path=args.structured_facts,
            scheme_ids=set(args.scheme_ids) if args.scheme_ids else None,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Parse aborted: {exc}", file=sys.stderr)
        return 2

    _print_summary(summary)
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
