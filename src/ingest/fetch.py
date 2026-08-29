"""
Phase 1.1 — Fetch allowlisted scheme HTML into data/raw/.

Fail closed: any URL not an exact problem-statement Reference URL is rejected.
Failed fetches (403 / timeout / empty body / non-2xx) are recorded and block
overall success for that scheme.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from src.config import REPO_ROOT, get_settings
from src.guardrails.citations import is_allowed_citation

DEFAULT_USER_AGENT = (
    "MutualFundFAQBot/0.1 (+facts-only research; contact=local-dev)"
)
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass
class SchemeFetchResult:
    scheme_id: str
    doc_id: str
    display_name: str
    source_url: str
    status: str  # success | failed
    http_status: int | None = None
    content_hash: str | None = None
    content_bytes: int | None = None
    fetched_at: str | None = None
    html_path: str | None = None
    error: str | None = None
    hash_changed: bool | None = None


@dataclass
class FetchRunSummary:
    run_id: str
    started_at: str
    finished_at: str
    overall_status: str  # success | failed
    schemes: list[SchemeFetchResult] = field(default_factory=list)

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


def load_manifest_schemes(manifest_path: str | Path) -> list[dict[str, Any]]:
    path = _resolve_path(manifest_path)
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    schemes = data.get("schemes") or []
    if not schemes:
        raise ValueError(f"No schemes found in manifest: {path}")
    return schemes


def validate_scheme_url(scheme: dict[str, Any]) -> str:
    """Return source_url or raise if missing / not allowlisted."""
    scheme_id = scheme.get("scheme_id") or "<unknown>"
    url = scheme.get("source_url")
    if not url:
        raise ValueError(f"Scheme {scheme_id} missing source_url")
    if not is_allowed_citation(url):
        raise ValueError(
            f"Rejecting non–problem-statement URL for {scheme_id}: {url}"
        )
    return url


def _previous_hash(fetch_log_path: Path, scheme_id: str) -> str | None:
    if not fetch_log_path.exists():
        return None
    with fetch_log_path.open(encoding="utf-8") as f:
        log = yaml.safe_load(f) or {}
    for entry in log.get("schemes") or []:
        if entry.get("scheme_id") == scheme_id and entry.get("status") == "success":
            return entry.get("content_hash")
    # Also check latest run history if present
    for run in reversed(log.get("runs") or []):
        for entry in run.get("schemes") or []:
            if entry.get("scheme_id") == scheme_id and entry.get("status") == "success":
                return entry.get("content_hash")
    return None


def fetch_scheme_html(
    scheme: dict[str, Any],
    *,
    raw_dir: Path,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: httpx.Client | None = None,
    previous_hash: str | None = None,
) -> SchemeFetchResult:
    """Fetch one scheme page. Never silent-skips failures."""
    scheme_id = str(scheme["scheme_id"])
    display_name = str(scheme.get("display_name") or scheme_id)
    doc_id = scheme_id
    fetched_at = _utc_now_iso()

    try:
        url = validate_scheme_url(scheme)
    except ValueError as exc:
        return SchemeFetchResult(
            scheme_id=scheme_id,
            doc_id=doc_id,
            display_name=display_name,
            source_url=str(scheme.get("source_url") or ""),
            status="failed",
            fetched_at=fetched_at,
            error=str(exc),
        )

    owns_client = client is None
    http = client or httpx.Client(
        timeout=timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/html"},
    )

    try:
        try:
            response = http.get(url)
        except httpx.TimeoutException as exc:
            return SchemeFetchResult(
                scheme_id=scheme_id,
                doc_id=doc_id,
                display_name=display_name,
                source_url=url,
                status="failed",
                fetched_at=fetched_at,
                error=f"Timeout fetching {url}: {exc}",
            )
        except httpx.HTTPError as exc:
            return SchemeFetchResult(
                scheme_id=scheme_id,
                doc_id=doc_id,
                display_name=display_name,
                source_url=url,
                status="failed",
                fetched_at=fetched_at,
                error=f"HTTP error fetching {url}: {exc}",
            )

        status_code = response.status_code
        if status_code == 403:
            return SchemeFetchResult(
                scheme_id=scheme_id,
                doc_id=doc_id,
                display_name=display_name,
                source_url=url,
                status="failed",
                http_status=status_code,
                fetched_at=fetched_at,
                error=f"HTTP 403 Forbidden for {url}",
            )
        if status_code < 200 or status_code >= 300:
            return SchemeFetchResult(
                scheme_id=scheme_id,
                doc_id=doc_id,
                display_name=display_name,
                source_url=url,
                status="failed",
                http_status=status_code,
                fetched_at=fetched_at,
                error=f"HTTP {status_code} for {url}",
            )

        body = response.content
        if not body or not body.strip():
            return SchemeFetchResult(
                scheme_id=scheme_id,
                doc_id=doc_id,
                display_name=display_name,
                source_url=url,
                status="failed",
                http_status=status_code,
                fetched_at=fetched_at,
                error=f"Empty body for {url}",
            )

        digest = content_sha256(body)
        raw_dir.mkdir(parents=True, exist_ok=True)
        html_path = raw_dir / f"{scheme_id}.html"
        html_path.write_bytes(body)

        hash_changed = previous_hash is not None and previous_hash != digest
        return SchemeFetchResult(
            scheme_id=scheme_id,
            doc_id=doc_id,
            display_name=display_name,
            source_url=url,
            status="success",
            http_status=status_code,
            content_hash=digest,
            content_bytes=len(body),
            fetched_at=fetched_at,
            html_path=_display_path(html_path),
            hash_changed=hash_changed if previous_hash is not None else True,
        )
    finally:
        if owns_client:
            http.close()


def verify_existing_raw(
    scheme: dict[str, Any],
    *,
    raw_dir: Path,
    previous_hash: str | None = None,
) -> SchemeFetchResult:
    """Validate an on-disk raw HTML file without network I/O."""
    scheme_id = str(scheme["scheme_id"])
    display_name = str(scheme.get("display_name") or scheme_id)
    fetched_at = _utc_now_iso()

    try:
        url = validate_scheme_url(scheme)
    except ValueError as exc:
        return SchemeFetchResult(
            scheme_id=scheme_id,
            doc_id=scheme_id,
            display_name=display_name,
            source_url=str(scheme.get("source_url") or ""),
            status="failed",
            fetched_at=fetched_at,
            error=str(exc),
        )

    html_path = raw_dir / f"{scheme_id}.html"
    if not html_path.exists():
        return SchemeFetchResult(
            scheme_id=scheme_id,
            doc_id=scheme_id,
            display_name=display_name,
            source_url=url,
            status="failed",
            fetched_at=fetched_at,
            error=f"Missing raw file: {html_path}",
        )

    body = html_path.read_bytes()
    if not body or not body.strip():
        return SchemeFetchResult(
            scheme_id=scheme_id,
            doc_id=scheme_id,
            display_name=display_name,
            source_url=url,
            status="failed",
            fetched_at=fetched_at,
            html_path=_display_path(html_path),
            error=f"Empty raw file: {html_path}",
        )

    digest = content_sha256(body)
    hash_changed = previous_hash is not None and previous_hash != digest
    return SchemeFetchResult(
        scheme_id=scheme_id,
        doc_id=scheme_id,
        display_name=display_name,
        source_url=url,
        status="success",
        http_status=None,
        content_hash=digest,
        content_bytes=len(body),
        fetched_at=fetched_at,
        html_path=_display_path(html_path),
        hash_changed=hash_changed if previous_hash is not None else None,
    )


def write_fetch_log(summary: FetchRunSummary, fetch_log_path: Path) -> None:
    fetch_log_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if fetch_log_path.exists():
        with fetch_log_path.open(encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}

    runs = list(existing.get("runs") or [])
    run_payload = {
        "run_id": summary.run_id,
        "started_at": summary.started_at,
        "finished_at": summary.finished_at,
        "overall_status": summary.overall_status,
        "schemes": [asdict(s) for s in summary.schemes],
    }
    runs.append(run_payload)

    # Latest-per-scheme snapshot for quick inspection / next-run hash compare
    latest_by_id: dict[str, dict[str, Any]] = {}
    for entry in existing.get("schemes") or []:
        sid = entry.get("scheme_id")
        if sid:
            latest_by_id[sid] = entry
    for result in summary.schemes:
        latest_by_id[result.scheme_id] = asdict(result)

    payload = {
        "version": 1,
        "updated_at": summary.finished_at,
        "latest_run_id": summary.run_id,
        "latest_overall_status": summary.overall_status,
        "schemes": list(latest_by_id.values()),
        "runs": runs[-20:],  # keep recent history bounded
    }
    with fetch_log_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)


def run_fetch(
    *,
    manifest_path: str | Path | None = None,
    raw_dir: str | Path | None = None,
    fetch_log_path: str | Path | None = None,
    scheme_ids: set[str] | None = None,
    verify_only: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: httpx.Client | None = None,
) -> FetchRunSummary:
    settings = get_settings()
    manifest = _resolve_path(manifest_path or settings.manifest_path)
    raw = _resolve_path(raw_dir or getattr(settings, "raw_dir", "data/raw"))
    log_path = _resolve_path(
        fetch_log_path or getattr(settings, "fetch_log_path", "data/raw/fetch_log.yaml")
    )

    schemes = load_manifest_schemes(manifest)
    if scheme_ids:
        schemes = [s for s in schemes if s.get("scheme_id") in scheme_ids]
        missing = scheme_ids - {s.get("scheme_id") for s in schemes}
        if missing:
            raise ValueError(f"Unknown scheme_id(s): {sorted(missing)}")

    started_at = _utc_now_iso()
    run_id = started_at.replace(":", "").replace("+", "Z")
    results: list[SchemeFetchResult] = []

    owns_client = client is None and not verify_only
    http = client
    if owns_client:
        http = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/html"},
        )

    try:
        for scheme in schemes:
            scheme_id = str(scheme["scheme_id"])
            prev = _previous_hash(log_path, scheme_id)
            if verify_only:
                results.append(
                    verify_existing_raw(scheme, raw_dir=raw, previous_hash=prev)
                )
            else:
                assert http is not None
                results.append(
                    fetch_scheme_html(
                        scheme,
                        raw_dir=raw,
                        timeout_seconds=timeout_seconds,
                        client=http,
                        previous_hash=prev,
                    )
                )
    finally:
        if owns_client and http is not None:
            http.close()

    finished_at = _utc_now_iso()
    overall = "success" if results and all(r.status == "success" for r in results) else "failed"
    summary = FetchRunSummary(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        overall_status=overall,
        schemes=results,
    )
    write_fetch_log(summary, log_path)
    return summary


def _print_summary(summary: FetchRunSummary) -> None:
    print(f"Fetch run {summary.run_id}: {summary.overall_status}")
    for r in summary.schemes:
        flag = "OK" if r.status == "success" else "FAIL"
        extra = r.content_hash[:12] + "…" if r.content_hash else (r.error or "")
        changed = ""
        if r.hash_changed is True:
            changed = " (hash changed)"
        elif r.hash_changed is False:
            changed = " (hash unchanged)"
        print(f"  [{flag}] {r.scheme_id}: {extra}{changed}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch allowlisted Kotak scheme HTML into data/raw/"
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Path to data/manifest.yaml (default from settings)",
    )
    parser.add_argument(
        "--raw-dir",
        default=None,
        help="Directory for raw HTML (default: data/raw)",
    )
    parser.add_argument(
        "--fetch-log",
        default=None,
        help="Fetch log YAML path (default: data/raw/fetch_log.yaml)",
    )
    parser.add_argument(
        "--scheme-id",
        action="append",
        dest="scheme_ids",
        default=None,
        help="Fetch only this scheme_id (repeatable)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate existing raw HTML files; do not download",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout seconds (default {DEFAULT_TIMEOUT_SECONDS})",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_fetch(
            manifest_path=args.manifest,
            raw_dir=args.raw_dir,
            fetch_log_path=args.fetch_log,
            scheme_ids=set(args.scheme_ids) if args.scheme_ids else None,
            verify_only=args.verify_only,
            timeout_seconds=args.timeout,
        )
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"Fetch aborted: {exc}", file=sys.stderr)
        return 2

    _print_summary(summary)
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
