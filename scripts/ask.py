#!/usr/bin/env python3
"""Run a single user query through the RAG pipeline and show the LLM answer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import get_settings
from src.guardrails.intent import classify_query
from src.guardrails.pii import check_pii
from src.ingest.index import get_chroma_collection
from src.rag.chat import handle_chat
from src.rag.generate import build_messages, generate_answer
from src.rag.retrieve import retrieve_for_query
from src.rag.scheme_resolver import resolve_scheme_or_id
from src.rag.validate import validate_and_format

DEFAULT_QUERY = "What is the current NAV of Kotak Arbitrage Fund?"
DEFAULT_SCHEME_ID = "kotak_arbitrage_direct_growth"


def _section(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(title)
    print("=" * 72)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ask one factual question and show retrieval + LLM + final answer.",
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=f"User question (default: {DEFAULT_QUERY!r})",
    )
    parser.add_argument(
        "--scheme-id",
        default=DEFAULT_SCHEME_ID,
        help=f"Optional scheme_id override (default: {DEFAULT_SCHEME_ID})",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Print the full Groq prompt (system + user messages)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    query = args.query.strip()
    scheme_id = args.scheme_id or None

    _section("Query")
    print(query)
    if scheme_id:
        print(f"scheme_id: {scheme_id}")

    pii = check_pii(query)
    if pii.detected:
        print(f"\nBlocked by PII gate: {', '.join(pii.kinds)}")
        result = handle_chat(query, scheme_id=scheme_id)
        print(f"\nResponse type: {result.type}")
        print(result.text)
        return 0

    intent = classify_query(query)
    print(f"\nIntent: {intent.intent} (facet={intent.facet}, confidence={intent.confidence})")

    resolved = resolve_scheme_or_id(query, scheme_id=scheme_id)
    print(f"Scheme resolution: {resolved.status}", end="")
    if resolved.scheme_id:
        print(f" -> {resolved.scheme_id}")
    else:
        print()

    if resolved.status != "resolved":
        result = handle_chat(query, scheme_id=scheme_id)
        _section("Final response (guardrail / resolver)")
        print(f"Type: {result.type}")
        print(result.text)
        return 0

    if intent.intent in {"advisory_or_compare", "performance_request"}:
        result = handle_chat(query, scheme_id=scheme_id)
        _section("Final response (refusal)")
        print(f"Type: {result.type}")
        print(result.text)
        return 0

    collection = get_chroma_collection(
        vector_store_path=settings.vector_store_path,
        collection_name=settings.chroma_collection,
        embedding_model=settings.embedding_model,
    )

    retrieval = retrieve_for_query(query, resolved.scheme_id, collection=collection, intent=intent)

    _section("Retrieval")
    print(f"Status: {retrieval.retrieval_status}")
    print(f"Facet: {retrieval.facet}")
    print(f"Source: {retrieval.source_url}")
    if retrieval.structured_fact:
        print(
            "Structured fact:",
            f"{retrieval.structured_fact.get('facet')} = {retrieval.structured_fact.get('value')}",
        )
    for i, chunk in enumerate(retrieval.chunks, 1):
        preview = chunk.text.replace("\n", " ")[:160]
        print(f"  [{i}] kind={chunk.kind} score={chunk.score:.3f} | {preview}...")

    if retrieval.retrieval_status == "miss":
        result = handle_chat(query, scheme_id=scheme_id, collection=collection)
        _section("Final response (retrieval miss)")
        print(result.text)
        return 0

    if not settings.groq_api_key:
        print(
            "\nError: GROQ_API_KEY is not set in .env — required for LLM generation.",
            file=sys.stderr,
        )
        return 2

    messages = build_messages(query, retrieval)
    if args.show_prompt:
        _section("Groq prompt")
        for msg in messages:
            print(f"\n--- {msg['role'].upper()} ---\n{msg['content']}")

    _section("LLM draft (raw Groq output)")
    print(f"Model: {settings.groq_model}")
    draft = generate_answer(query, retrieval)
    print(draft)

    last_updated = None
    if retrieval.structured_fact and retrieval.structured_fact.get("last_updated"):
        last_updated = str(retrieval.structured_fact["last_updated"])
    else:
        last_updated = retrieval.effective_date

    validated = validate_and_format(
        draft,
        citation_url=retrieval.source_url,
        last_updated=last_updated,
    )

    _section("Final answer (after validator)")
    print(f"Validator status: {validated.status}")
    print(validated.text)
    print(f"\nDisclaimer: {validated.disclaimer}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
