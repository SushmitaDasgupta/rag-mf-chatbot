#!/usr/bin/env python3
"""Golden question smoke runner for Phase 2.5."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import get_settings
from src.guardrails.citations import is_allowed_citation
from src.ingest.index import get_chroma_collection
from src.rag.chat import handle_chat


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run golden question smoke tests.")
    parser.add_argument(
        "--questions",
        default="tests/golden_questions.json",
        help="Path to golden questions JSON",
    )
    parser.add_argument("--require-groq", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.require_groq and not settings.groq_api_key:
        print("GROQ_API_KEY is required for answer-generation goldens.", file=sys.stderr)
        return 2

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    collection = get_chroma_collection(
        vector_store_path=settings.vector_store_path,
        collection_name=settings.chroma_collection,
        embedding_model=settings.embedding_model,
    )

    failures = 0
    skipped = 0
    for item in questions:
        message = item["message"]
        scheme_id = item.get("scheme_id")
        expected_type = item.get("expected_type", "answer")

        if expected_type == "answer" and not settings.groq_api_key and not args.require_groq:
            print(f"[SKIP] {item.get('id', message[:40])} (set GROQ_API_KEY or use --require-groq)")
            skipped += 1
            continue

        result = handle_chat(message, scheme_id=scheme_id, collection=collection)
        ok = result.type == expected_type

        if expected_type == "answer":
            ok = ok and bool(result.citation_url) and is_allowed_citation(result.citation_url or "")
            if item.get("expect_facet"):
                ok = ok and result.facet == item["expect_facet"]

        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {item.get('id', message[:40])} -> {result.type}")
        if not ok:
            failures += 1
            print(f"       expected={expected_type} got={result.type}")
            print(f"       {result.text[:120]}...")

    ran = len(questions) - skipped
    print(f"\n{ran - failures}/{ran} passed ({skipped} skipped)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
