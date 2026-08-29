"""Tier-0 structured fact lookup from data/processed/structured_facts.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.config import REPO_ROOT, get_settings
from src.guardrails.citations import is_allowed_citation

CORE_FACETS = frozenset(
    {"expense_ratio", "exit_load", "min_sip", "riskometer", "benchmark"}
)

NOT_IN_CORPUS_VALUES = frozenset(
    {"", "not in corpus", "not_in_corpus", "n/a", "na", "none", "null"}
)


def _resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (REPO_ROOT / p).resolve()


def is_tier0_fact_present(value: Any) -> bool:
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized not in NOT_IN_CORPUS_VALUES


def load_structured_facts(path: str | Path | None = None) -> dict[str, Any]:
    facts_path = _resolve_path(path or get_settings().structured_facts_path)
    if not facts_path.exists():
        return {}
    data = yaml.safe_load(facts_path.read_text(encoding="utf-8")) or {}
    return data.get("schemes") or {}


def get_tier0_fact(
    scheme_id: str,
    facet: str,
    *,
    facts: dict[str, Any] | None = None,
    facts_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """
    Return Tier-0 fact payload for a scheme + facet, or None if absent.

    Respects manual_override_* fields (value is returned as stored).
    """
    schemes = facts if facts is not None else load_structured_facts(facts_path)
    entry = schemes.get(scheme_id)
    if not entry:
        return None

    value = entry.get(facet)
    if not is_tier0_fact_present(value):
        return None

    source_url = str(entry.get("source_url") or "")
    if not is_allowed_citation(source_url):
        return None

    return {
        "scheme_id": scheme_id,
        "facet": facet,
        "value": value,
        "source_url": source_url,
        "last_updated": entry.get("last_updated"),
        "manual_override": bool(entry.get(f"manual_override_{facet}")),
    }
