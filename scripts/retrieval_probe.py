#!/usr/bin/env python3
"""Run P2.2 retrieval probes against the indexed corpus."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import get_settings
from src.ingest.fetch import load_manifest_schemes
from src.ingest.index import get_chroma_collection
from src.rag.retrieve import run_core_facet_probes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run core facet retrieval probes (P2.2).")
    parser.add_argument("--output", default="data/processed/chunks/retrieval_probe_log.yaml")
    args = parser.parse_args(argv)

    settings = get_settings()
    collection = get_chroma_collection(
        vector_store_path=settings.vector_store_path,
        collection_name=settings.chroma_collection,
        embedding_model=settings.embedding_model,
    )
    scheme_ids = [str(s["scheme_id"]) for s in load_manifest_schemes(settings.manifest_path)]
    probes = run_core_facet_probes(collection, scheme_ids=scheme_ids)

    passed = sum(1 for p in probes if p["status"] == "pass")
    payload = {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "embedding_model": settings.embedding_model,
        "summary": {
            "total": len(probes),
            "passed": passed,
            "failed": len(probes) - passed,
            "overall_status": "success" if passed == len(probes) else "failed",
        },
        "probes": probes,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    print(f"Probes: {passed}/{len(probes)} passed")
    print(f"Log: {out}")
    return 0 if passed == len(probes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
