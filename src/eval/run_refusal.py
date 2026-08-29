"""P3.4 — Refusal suite runner."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import get_settings
from src.guardrails.citations import is_allowed_citation
from src.ingest.index import get_chroma_collection
from src.rag.chat import handle_chat

RETURN_NUMBER_PATTERN = re.compile(r"\b\d+(\.\d+)?%")


def _evaluate_case(item: dict[str, Any], result) -> tuple[bool, list[str]]:
    errors: list[str] = []
    expect_type = item.get("expect_type")
    expect_type_not = item.get("expect_type_not")

    if expect_type and result.type != expect_type:
        errors.append(f"expected type={expect_type}, got={result.type}")
    if expect_type_not and result.type == expect_type_not:
        errors.append(f"forbidden type={expect_type_not}, got={result.type}")

    if result.type in {"refusal", "performance_refusal", "unsupported"}:
        if result.citation_url:
            errors.append(f"refusal must not include citation_url, got={result.citation_url}")
        if "http" in result.text.lower():
            errors.append("refusal text must not include URLs")

    expected_citation = item.get("expect_citation_url")
    if expected_citation:
        if result.citation_url != expected_citation:
            errors.append(f"expected citation_url={expected_citation}, got={result.citation_url}")

    for forbidden in item.get("expect_forbidden_substrings") or []:
        if forbidden.lower() in result.text.lower():
            errors.append(f"forbidden substring echoed: {forbidden}")

    if item.get("expect_no_return_numbers") and RETURN_NUMBER_PATTERN.search(result.text):
        errors.append("unexpected return-like percentage in refusal text")

    if expect_type == "answer":
        if not result.citation_url or not is_allowed_citation(result.citation_url):
            errors.append("answer missing allowlisted citation")
        if item.get("expect_facet") and result.facet != item["expect_facet"]:
            errors.append(f"expected facet={item['expect_facet']}, got={result.facet}")

    return not errors, errors


def run_refusal_suite(
    fixtures: list[dict[str, Any]],
    *,
    collection,
    groq_calls: list[str] | None = None,
) -> tuple[int, int, list[dict[str, Any]]]:
    failures = 0
    report: list[dict[str, Any]] = []

    for item in fixtures:
        groq_calls_before = len(groq_calls or [])
        result = handle_chat(
            item["query"],
            scheme_id=item.get("scheme_id"),
            collection=collection,
        )
        groq_called = groq_calls is not None and len(groq_calls) > groq_calls_before

        if item.get("expect_no_groq") and groq_called:
            ok, errors = False, ["Groq/retrieve path was invoked when expect_no_groq=true"]
        else:
            ok, errors = _evaluate_case(item, result)

        report.append(
            {
                "id": item.get("id"),
                "category": item.get("category"),
                "pass": ok,
                "type": result.type,
                "errors": errors,
            }
        )
        if not ok:
            failures += 1

    return failures, len(fixtures), report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run refusal / guardrail test suite.")
    parser.add_argument(
        "--fixtures",
        default="tests/refusal_cases.json",
        help="Path to refusal_cases.json",
    )
    parser.add_argument(
        "--report",
        default="",
        help="Optional path to write JSON report",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))

    collection = None
    if any(not item.get("expect_no_groq") for item in fixtures):
        try:
            collection = get_chroma_collection(
                vector_store_path=settings.vector_store_path,
                collection_name=settings.chroma_collection,
                embedding_model=settings.embedding_model,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: could not load vector store ({exc}); skipping RAG answer cases.")

    failures = 0
    report: list[dict[str, Any]] = []
    mock_collection = MagicMock()

    for item in fixtures:
        if not item.get("expect_no_groq") and collection is None:
            print(f"[SKIP] {item.get('id')} (vector store unavailable for answer path)")
            report.append(
                {
                    "id": item.get("id"),
                    "category": item.get("category"),
                    "pass": None,
                    "type": "skipped",
                    "errors": ["vector store unavailable"],
                }
            )
            continue

        coll = mock_collection if item.get("expect_no_groq") else collection
        result = handle_chat(
            item["query"],
            scheme_id=item.get("scheme_id"),
            collection=coll,
        )
        ok, errors = _evaluate_case(item, result)

        report.append(
            {
                "id": item.get("id"),
                "category": item.get("category"),
                "pass": ok,
                "type": result.type,
                "errors": errors,
            }
        )
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {item.get('id')} -> {result.type}")
        if errors:
            for err in errors:
                print(f"       {err}")
        if not ok:
            failures += 1

    ran = sum(1 for row in report if row["pass"] is not None)
    print(f"\n{ran - failures}/{ran} passed")
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
