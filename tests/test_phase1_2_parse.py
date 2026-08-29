"""Phase 1.2 — HTML parse, table serialization, allowlisted local-only."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from src.guardrails.citations import PROBLEM_STATEMENT_SCHEME_URLS
from src.ingest.parse import (
    extract_facts_from_tables,
    parse_from_dom,
    parse_scheme_html,
    run_parse,
    serialize_table,
)

ALLOWED_URL = (
    "https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth"
)


def _scheme(**overrides):
    base = {
        "scheme_id": "kotak_large_cap_direct_growth",
        "display_name": "Kotak Large Cap Fund – Direct Growth",
        "source_url": ALLOWED_URL,
        "doc_type": "scheme_reference_page",
    }
    base.update(overrides)
    return base


def test_serialize_table_stable_rows() -> None:
    text = serialize_table(
        ["Field", "Value"],
        [["Expense ratio", "0.67%"], ["Exit Load", "1.0% — Exit Load of 1%"]],
    )
    assert text.splitlines()[0] == "Field | Value"
    assert "Expense ratio | 0.67%" in text
    assert "Exit Load | 1.0%" in text
    # no mid-cell newline splits
    assert all("\n" not in cell for cell in ["0.67%", "1.0% — Exit Load of 1%"])


def test_dom_parse_strips_chrome_and_keeps_fee_table() -> None:
    html = """
    <html><head><title>Demo Fund</title></head>
    <body>
      <nav>Home Login</nav>
      <div id="cookie-banner">Accept cookies</div>
      <main>
        <h2>Key Parameters</h2>
        <p>Overview of fees and loads for the scheme.</p>
        <table>
          <tr><th>Field</th><th>Value</th></tr>
          <tr><td>Expense ratio</td><td>0.55%</td></tr>
          <tr><td>Exit Load</td><td>1%</td></tr>
          <tr><td>Benchmark</td><td>Nifty 100</td></tr>
        </table>
        <script>window.track()</script>
      </main>
      <footer>App download</footer>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    title, sections, tables, main_text = parse_from_dom(soup)
    assert title == "Demo Fund"
    assert "Accept cookies" not in main_text
    assert "window.track" not in main_text
    assert tables
    assert tables[0].fee_load_relevant
    assert "Expense ratio | 0.55%" in tables[0].serialized
    facts = extract_facts_from_tables(tables)
    assert facts["expense_ratio"] == "0.55%"
    assert facts["exit_load"] == "1%"
    assert facts["benchmark"] == "Nifty 100"


def test_parse_rejects_non_allowlisted_url(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    parsed = tmp_path / "parsed"
    raw.mkdir()
    (raw / "bad.html").write_text("<html><body>x</body></html>", encoding="utf-8")
    result = parse_scheme_html(
        _scheme(scheme_id="bad", source_url="https://www.kotakmf.com/x"),
        raw_dir=raw,
        parsed_dir=parsed,
    )
    assert result.status == "failed"
    assert "allowlisted" in (result.error or "").lower()


def test_run_parse_writes_artifacts_from_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    parsed = tmp_path / "parsed"
    facts_path = tmp_path / "structured_facts.yaml"
    raw.mkdir()

    next_data = {
        "props": {
            "pageProps": {
                "mutualFundsDetailData": {
                    "data": {
                        "name": "Kotak Large Cap Direct Growth",
                        "nav_date": "26 Aug 2026",
                        "fund_overview": {
                            "display_name": "Overview",
                            "info": [
                                {"name": "Expense ratio", "value": "0.67%"},
                                {
                                    "name": "Exit Load",
                                    "value": "1.0%",
                                    "description": "Exit Load of 1% if redeemed in 0-1 Years",
                                },
                                {"name": "Benchmark", "value": "Nifty 100 TR INR"},
                                {"name": "Min Lumpsum/SIP", "value": "₹100/₹100"},
                            ],
                        },
                        "risk_meter": {
                            "widget_properties": {
                                "title": "Riskometer",
                                "zone_title": "Very High Risk",
                                "body": "Investors understand that their principal will be at Very High Risk",
                            }
                        },
                        "about": {"about_fund": []},
                        "holdings": {},
                        "static_content": {"faqs": []},
                    }
                }
            }
        }
    }
    html = (
        "<html><head><title>x</title>"
        f"<script id='__NEXT_DATA__' type='application/json'>{json.dumps(next_data)}</script>"
        "</head><body><h1>Fund</h1></body></html>"
    )
    (raw / "kotak_large_cap_direct_growth.html").write_text(html, encoding="utf-8")

    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"schemes": [_scheme()]}), encoding="utf-8")

    summary = run_parse(
        manifest_path=manifest,
        raw_dir=raw,
        parsed_dir=parsed,
        structured_facts_path=facts_path,
    )
    assert summary.ok
    artifact = parsed / "kotak_large_cap_direct_growth.json"
    assert artifact.exists()
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["main_text"].strip()
    assert data["source_url"] in PROBLEM_STATEMENT_SCHEME_URLS
    assert data["flags"]["network_used"] is False
    assert data["structured_fact_candidates"]["expense_ratio"] == "0.67%"
    assert "Exit Load" in data["tables"][0]["serialized"]
    assert (parsed / "SPOT_CHECK.md").exists()

    facts = yaml.safe_load(facts_path.read_text(encoding="utf-8"))
    assert facts["schemes"]["kotak_large_cap_direct_growth"]["benchmark"] == "Nifty 100 TR INR"


def test_update_structured_facts_preserves_manual_override(tmp_path: Path) -> None:
    from src.ingest.parse import SchemeParseResult, update_structured_facts

    facts_path = tmp_path / "structured_facts.yaml"
    facts_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "schemes": {
                    "kotak_large_cap_direct_growth": {
                        "source_url": ALLOWED_URL,
                        "expense_ratio": "0.70%",
                        "manual_override_expense_ratio": True,
                        "exit_load": "1.0%",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    result = SchemeParseResult(
        scheme_id="kotak_large_cap_direct_growth",
        doc_id="kotak_large_cap_direct_growth",
        display_name="Kotak Large Cap Fund – Direct Growth",
        source_url=ALLOWED_URL,
        status="success",
        parsed_at="2026-08-27T09:00:00+00:00",
        structured_fact_candidates={
            "expense_ratio": "0.67%",
            "exit_load": "1.0% — Exit Load of 1% if redeemed in 0-1 Years",
            "min_sip": "₹100",
            "riskometer": "Very High Risk",
            "benchmark": "Nifty 100 TR INR",
            "as_of_date": "26 Aug 2026",
        },
    )
    update_structured_facts([result], facts_path)
    facts = yaml.safe_load(facts_path.read_text(encoding="utf-8"))
    scheme = facts["schemes"]["kotak_large_cap_direct_growth"]
    assert scheme["expense_ratio"] == "0.70%"
    assert scheme["manual_override_expense_ratio"] is True
    assert "0.67%" not in str(scheme["expense_ratio"])
    assert scheme["exit_load"] == "1.0% — Exit Load of 1% if redeemed in 0-1 Years"
