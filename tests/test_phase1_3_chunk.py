"""Phase 1.3 — section-aware chunking over parsed JSON."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.guardrails.citations import PROBLEM_STATEMENT_SCHEME_URLS
from src.ingest.chunk import (
    HARD_MAX_TOKENS,
    chunk_parsed_document,
    estimate_tokens,
    format_prefix,
    run_chunk,
)

ALLOWED_URL = (
    "https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth"
)


def _parsed_fixture() -> dict:
    return {
        "scheme_id": "kotak_large_cap_direct_growth",
        "doc_id": "kotak_large_cap_direct_growth",
        "display_name": "Kotak Large Cap Fund – Direct Growth",
        "source_url": ALLOWED_URL,
        "doc_type": "scheme_reference_page",
        "as_of_date": "26 Aug 2026",
        "tables": [
            {
                "table_id": "fund_overview_info",
                "caption": "Fund Overview",
                "headers": ["Field", "Value"],
                "rows": [
                    ["Expense ratio", "0.67%"],
                    ["Benchmark", "Nifty 100 TR INR"],
                    ["AUM", "₹11028 Cr"],
                    ["Min Lumpsum/SIP", "₹100/₹100"],
                    ["Exit Load", "1.0% — Exit Load of 1% if redeemed in 0-1 Years"],
                    ["Lock In", "No Lock-in"],
                ],
                "serialized": (
                    "Field | Value\n"
                    "Expense ratio | 0.67%\n"
                    "Benchmark | Nifty 100 TR INR\n"
                    "AUM | ₹11028 Cr\n"
                    "Min Lumpsum/SIP | ₹100/₹100\n"
                    "Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years\n"
                    "Lock In | No Lock-in"
                ),
                "kind": "overview_kv",
                "fee_load_relevant": True,
            },
            {
                "table_id": "riskometer",
                "caption": "Riskometer",
                "headers": ["Field", "Value"],
                "rows": [["Riskometer", "Very High Risk"]],
                "serialized": "Field | Value\nRiskometer | Very High Risk",
                "kind": "overview_kv",
                "fee_load_relevant": False,
            },
            {
                "table_id": "holdings_equity",
                "caption": "Equity",
                "headers": ["Holding", "Weight%", "1M Change"],
                "rows": [["ICICI Bank Ltd", "8.05%", "4.5%"]],
                "serialized": "Holding | Weight% | 1M Change\nICICI Bank Ltd | 8.05% | 4.5%",
                "kind": "holdings",
                "fee_load_relevant": False,
            },
        ],
        "sections": [
            {
                "heading": "Kotak Large Cap Fund Overview",
                "text": "Expense ratio: 0.67%\nExit Load: 1.0%",
                "facet_hints": ["expense_ratio", "exit_load"],
            },
            {
                "heading": "Minimum Investment and lockin period",
                "text": (
                    "Minimum investment for lump sum payment is INR 100.00 and for SIP "
                    "is INR 100.00. Kotak Large Cap Fund has no lock in period."
                ),
                "facet_hints": ["min_sip", "min_investment", "lock_in"],
            },
            {
                "heading": "FAQ: What is the exit load of the fund?",
                "text": "The exit load is 1% if redeemed in 0-1 Years.",
                "facet_hints": ["exit_load"],
            },
        ],
    }


def test_prefix_and_token_estimate() -> None:
    prefix = format_prefix("Demo Fund", "scheme_reference_page", "Exit Load", "exit_load")
    assert "[Scheme: Demo Fund]" in prefix
    assert "Facet: exit_load" in prefix
    assert estimate_tokens("one two three") == 3


def test_chunk_overview_parent_and_row_children() -> None:
    chunks = chunk_parsed_document(_parsed_fixture())
    kinds = {c.kind for c in chunks}
    assert "overview_parent" in kinds
    assert "overview_row" in kinds
    assert "faq" in kinds
    assert "holdings" in kinds
    assert "prose" in kinds

    exit_rows = [c for c in chunks if c.kind == "overview_row" and c.facet == "exit_load"]
    assert len(exit_rows) == 1
    body = exit_rows[0].body
    assert body.startswith("Field | Value")
    assert "Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years" in body
    # no mid-cell split: value stays on one line
    assert body.splitlines()[1].count(" | ") == 1

    # overview prose skipped when overview table present
    assert not any(c.section.lower().endswith("overview") and c.kind == "prose" for c in chunks)

    for c in chunks:
        assert c.source_url in PROBLEM_STATEMENT_SCHEME_URLS
        assert c.token_estimate <= HARD_MAX_TOKENS
        assert c.text.startswith("[Scheme:")


def test_reject_non_allowlisted_source() -> None:
    bad = _parsed_fixture()
    bad["source_url"] = "https://www.kotakmf.com/x"
    try:
        chunk_parsed_document(bad)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "allowlisted" in str(exc).lower()


def test_run_chunk_writes_artifacts(tmp_path: Path) -> None:
    parsed_dir = tmp_path / "parsed"
    chunks_dir = tmp_path / "chunks"
    parsed_dir.mkdir()
    fixture = _parsed_fixture()
    (parsed_dir / f"{fixture['scheme_id']}.json").write_text(
        json.dumps(fixture), encoding="utf-8"
    )
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "schemes": [
                    {
                        "scheme_id": fixture["scheme_id"],
                        "display_name": fixture["display_name"],
                        "source_url": fixture["source_url"],
                        "doc_type": "scheme_reference_page",
                        "category": "Large-cap",
                        "refresh_cadence_days": 7,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    facts = tmp_path / "facts.yaml"
    facts.write_text(
        yaml.safe_dump(
            {
                "schemes": {
                    fixture["scheme_id"]: {
                        "source_url": fixture["source_url"],
                        "expense_ratio": "0.67%",
                        "exit_load": "1.0%",
                        "min_sip": "₹100",
                        "riskometer": "Very High Risk",
                        "benchmark": "Nifty 100 TR INR",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    summary = run_chunk(
        manifest_path=manifest,
        parsed_dir=parsed_dir,
        chunks_dir=chunks_dir,
        structured_facts_path=facts,
    )
    assert summary.ok
    assert (chunks_dir / f"{fixture['scheme_id']}.json").exists()
    assert (chunks_dir / f"{fixture['scheme_id']}.jsonl").exists()
    assert (chunks_dir / "CHUNK_QC.md").exists()
    data = json.loads((chunks_dir / f"{fixture['scheme_id']}.json").read_text(encoding="utf-8"))
    assert data["chunk_count"] > 0
    assert "expense_ratio" in data["coverage"]["facets_present"]
