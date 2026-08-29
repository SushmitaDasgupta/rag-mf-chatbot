"""Phase 0 checks: manifest URLs must match problem-statement allowlist exactly."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.guardrails.citations import (
    PROBLEM_STATEMENT_SCHEME_URLS,
    assert_manifest_urls_allowlisted,
    is_allowed_citation,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.yaml"
PROBLEM_STATEMENT_PATH = REPO_ROOT / "docs" / "problemStatement.md"


def test_problem_statement_urls_are_exact_full_matches() -> None:
    text = PROBLEM_STATEMENT_PATH.read_text(encoding="utf-8")
    for url in PROBLEM_STATEMENT_SCHEME_URLS:
        assert url in text, f"Allowlist URL missing from problemStatement.md: {url}"
        assert is_allowed_citation(url)


def test_manifest_urls_are_problem_statement_subset() -> None:
    urls = assert_manifest_urls_allowlisted(str(MANIFEST_PATH))
    assert 3 <= len(urls) <= len(PROBLEM_STATEMENT_SCHEME_URLS)
    assert urls <= PROBLEM_STATEMENT_SCHEME_URLS
    # Corpus includes the full problem-statement candidate set.
    assert urls == PROBLEM_STATEMENT_SCHEME_URLS


def test_manifest_has_required_fields_and_no_foreign_hosts() -> None:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    schemes = data["schemes"]
    assert 3 <= len(schemes) <= len(PROBLEM_STATEMENT_SCHEME_URLS)
    categories = {s["category"] for s in schemes}
    assert len(categories) >= 3, "Expected category diversity across schemes"

    forbidden_substrings = (
        "kotakmf.com",
        "amfiindia.com",
        "sebi.gov.in",
        "groww.in",
    )
    for scheme in schemes:
        assert scheme["scheme_id"]
        assert scheme["display_name"]
        assert scheme["category"]
        assert scheme["doc_type"] == "scheme_reference_page"
        assert scheme.get("refresh_cadence_days")
        url = scheme["source_url"]
        assert url.startswith("https://www.indmoney.com/")
        for bad in forbidden_substrings:
            assert bad not in url


def test_processed_scheme_urls_match_problem_statement() -> None:
    processed = REPO_ROOT / "data" / "processed" / "scheme_urls.yaml"
    facts = REPO_ROOT / "data" / "processed" / "structured_facts.yaml"
    urls_doc = yaml.safe_load(processed.read_text(encoding="utf-8"))
    facts_doc = yaml.safe_load(facts.read_text(encoding="utf-8"))

    processed_urls = {s["source_url"] for s in urls_doc["schemes"]}
    fact_urls = {v["source_url"] for v in facts_doc["schemes"].values()}
    assert processed_urls == PROBLEM_STATEMENT_SCHEME_URLS
    assert fact_urls == PROBLEM_STATEMENT_SCHEME_URLS
    assert set(facts_doc["schemes"]) == {
        s["scheme_id"] for s in urls_doc["schemes"]
    }


def test_reject_non_allowlisted_citation() -> None:
    assert not is_allowed_citation("https://www.kotakmf.com/some-scheme")
    assert not is_allowed_citation("https://www.indmoney.com/mutual-funds/")
