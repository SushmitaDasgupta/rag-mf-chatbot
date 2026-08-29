"""
Citation allowlist for scheme answers.

Normative rule: citations must be an exact full URL match against
Reference links listed in docs/problemStatement.md — not open-host matching,
and not AMC / AMFI / SEBI / other aggregator scheme pages unless that exact
URL appears in the problem statement.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

# Full candidate Reference URLs from docs/problemStatement.md (verbatim).
PROBLEM_STATEMENT_SCHEME_URLS: Final[frozenset[str]] = frozenset(
    {
        "https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth",
        "https://www.indmoney.com/mutual-funds/kotak-midcap-fund-direct-growth",
        "https://www.indmoney.com/mutual-funds/kotak-arbitrage-fund-direct-growth",
        "https://www.indmoney.com/mutual-funds/kotak-savings-fund-direct-growth",
        "https://www.indmoney.com/mutual-funds/kotak-gold-fund-growth-direct",
        "https://www.indmoney.com/mutual-funds/kotak-flexicap-fund-direct-growth",
        "https://www.indmoney.com/mutual-funds/kotak-liquid-fund-growth-direct",
    }
)

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH: Final[Path] = REPO_ROOT / "data" / "manifest.yaml"


def is_allowed_citation(url: str) -> bool:
    """Return True iff url is an exact problem-statement Reference URL."""
    return url in PROBLEM_STATEMENT_SCHEME_URLS


@lru_cache(maxsize=1)
def load_manifest_urls(manifest_path: str | None = None) -> frozenset[str]:
    """Load selected scheme source_urls from the corpus manifest."""
    import yaml

    path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST_PATH
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    urls: set[str] = set()
    for scheme in data.get("schemes") or []:
        url = scheme.get("source_url")
        if not url:
            raise ValueError(f"Manifest scheme missing source_url: {scheme!r}")
        if not is_allowed_citation(url):
            raise ValueError(
                f"Manifest source_url is not a problem-statement Reference URL: {url}"
            )
        urls.add(url)
    return frozenset(urls)


def assert_manifest_urls_allowlisted(manifest_path: str | None = None) -> frozenset[str]:
    """Validate manifest URLs; return the locked corpus URL set."""
    return load_manifest_urls(manifest_path)
