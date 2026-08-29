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
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from src.config import REPO_ROOT, get_settings
from src.guardrails.citations import is_allowed_citation
from src.logging_config import get_logger, log_checkpoint, log_manifest_roster, pipeline_echo, setup_logging

logger = get_logger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT_SECONDS = 30.0
RETRYABLE_HTTP_STATUS = {403, 408, 429, 500, 502, 503, 504}
RETRY_BACKOFF_SECONDS = (2.0, 5.0, 10.0)


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
    fetch_mode: str | None = None  # network | cached | verify
    warning: str | None = None


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


def build_fetch_headers(user_agent: str = DEFAULT_USER_AGENT) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Cache-Control": "no-cache",
    }


def _http_get_with_retries(
    http: httpx.Client,
    url: str,
    *,
    retry_count: int,
) -> httpx.Response:
    last_response: httpx.Response | None = None
    attempts = max(1, retry_count)
    for attempt in range(attempts):
        response = http.get(url)
        last_response = response
        if response.status_code not in RETRYABLE_HTTP_STATUS:
            return response
        if attempt < attempts - 1:
            backoff = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
            time.sleep(backoff)
    assert last_response is not None
    return last_response


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
    retry_count: int = 3,
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
        headers=build_fetch_headers(),
    )

    try:
        try:
            response = _http_get_with_retries(http, url, retry_count=retry_count)
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
            fetch_mode="network",
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
        fetch_mode="verify",
    )


def fetch_scheme_with_fallback(
    scheme: dict[str, Any],
    *,
    raw_dir: Path,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: httpx.Client,
    previous_hash: str | None = None,
    retry_count: int = 3,
    fallback_to_cached: bool = False,
) -> SchemeFetchResult:
    """Try network fetch; on failure optionally reuse committed raw HTML."""
    network_result = fetch_scheme_html(
        scheme,
        raw_dir=raw_dir,
        timeout_seconds=timeout_seconds,
        client=client,
        previous_hash=previous_hash,
        retry_count=retry_count,
    )
    if network_result.status == "success" or not fallback_to_cached:
        return network_result

    cached = verify_existing_raw(scheme, raw_dir=raw_dir, previous_hash=previous_hash)
    if cached.status != "success":
        return network_result

    cached.fetch_mode = "cached"
    cached.warning = (
        f"Network fetch failed ({network_result.error}); using cached raw HTML"
    )
    return cached


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
    fallback_to_cached: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    retry_count: int = 3,
    inter_scheme_delay_seconds: float = 0.0,
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

    mode = "verify-only" if verify_only else "network"
    if fallback_to_cached and not verify_only:
        mode = "network+cached-fallback"
    log_checkpoint(
        logger,
        "P1.1",
        "manifest",
        "Loaded allowlisted scheme manifest",
        schemes=len(schemes),
        mode=mode,
        run_id=run_id,
    )
    log_manifest_roster(logger, schemes)

    owns_client = client is None and not verify_only
    http = client
    if owns_client:
        http = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers=build_fetch_headers(),
        )

    try:
        for index, scheme in enumerate(schemes):
            scheme_id = str(scheme["scheme_id"])
            prev = _previous_hash(log_path, scheme_id)
            step = f"[{index + 1}/{len(schemes)}]"
            display = str(scheme.get("display_name") or scheme_id)
            if verify_only:
                log_checkpoint(
                    logger, "P1.1", "verify_raw", f"Verify cached HTML for {display}", scheme_id=scheme_id
                )
                result = verify_existing_raw(scheme, raw_dir=raw, previous_hash=prev)
            else:
                log_checkpoint(
                    logger, "P1.1", "fetch_url", f"Download scheme page for {display}", scheme_id=scheme_id
                )
                assert http is not None
                result = fetch_scheme_with_fallback(
                    scheme,
                    raw_dir=raw,
                    timeout_seconds=timeout_seconds,
                    client=http,
                    previous_hash=prev,
                    retry_count=retry_count,
                    fallback_to_cached=fallback_to_cached,
                )
            results.append(result)
            _log_scheme_result(step, result)
            if (
                not verify_only
                and inter_scheme_delay_seconds > 0
                and index < len(schemes) - 1
            ):
                time.sleep(inter_scheme_delay_seconds)
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
    _log_fetch_summary(summary)
    return summary


def _log_scheme_result(step: str, result: SchemeFetchResult) -> None:
    if result.status == "success":
        hash_note = "changed" if result.hash_changed else "unchanged"
        if result.hash_changed is None:
            hash_note = "n/a"
        line = (
            f"{step} {result.scheme_id} OK | mode={result.fetch_mode or 'n/a'} | "
            f"http={result.http_status if result.http_status is not None else 'n/a'} | "
            f"bytes={result.content_bytes if result.content_bytes is not None else 'n/a'} | "
            f"hash={hash_note}"
        )
        logger.info(line)
        pipeline_echo(line)
        if result.warning:
            warn = f"{step} {result.scheme_id} | {result.warning}"
            logger.warning(warn)
            pipeline_echo(f"WARNING | {warn}")
    else:
        line = f"{step} {result.scheme_id} FAILED | {result.error}"
        logger.error(line)
        pipeline_echo(f"ERROR | {line}")


def _log_fetch_summary(summary: FetchRunSummary) -> None:
    ok = sum(1 for r in summary.schemes if r.status == "success")
    cached = sum(1 for r in summary.schemes if r.fetch_mode == "cached")
    logger.info(
        "Fetch summary | status=%s | ok=%d/%d | cached_fallback=%d | run_id=%s",
        summary.overall_status,
        ok,
        len(summary.schemes),
        cached,
        summary.run_id,
    )


def _print_summary(summary: FetchRunSummary) -> None:
    _log_fetch_summary(summary)
    for r in summary.schemes:
        flag = "OK" if r.status == "success" else "FAIL"
        extra = r.content_hash[:12] + "…" if r.content_hash else (r.error or "")
        changed = ""
        if r.hash_changed is True:
            changed = " (hash changed)"
        elif r.hash_changed is False:
            changed = " (hash unchanged)"
        mode = f" [{r.fetch_mode}]" if r.fetch_mode else ""
        print(f"  [{flag}] {r.scheme_id}: {extra}{changed}{mode}")
        if r.warning:
            print(f"       ! {r.warning}")


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
        "--fetch-fallback-cached",
        action="store_true",
        help="On network failure, reuse committed raw HTML if present",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout seconds (default {DEFAULT_TIMEOUT_SECONDS})",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    setup_logging(settings.log_level)

    try:
        summary = run_fetch(
            manifest_path=args.manifest,
            raw_dir=args.raw_dir,
            fetch_log_path=args.fetch_log,
            scheme_ids=set(args.scheme_ids) if args.scheme_ids else None,
            verify_only=args.verify_only,
            fallback_to_cached=args.fetch_fallback_cached or settings.fetch_fallback_cached,
            timeout_seconds=args.timeout,
            retry_count=settings.fetch_retry_count,
            inter_scheme_delay_seconds=settings.fetch_inter_scheme_delay_seconds,
        )
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"Fetch aborted: {exc}", file=sys.stderr)
        return 2

    _print_summary(summary)
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
