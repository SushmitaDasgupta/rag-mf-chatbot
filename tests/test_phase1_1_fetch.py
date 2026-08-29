"""Phase 1.1 — fetch allowlist, failure surfacing, hash updates."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import yaml

from src.ingest.fetch import (
    build_fetch_headers,
    content_sha256,
    fetch_scheme_html,
    fetch_scheme_with_fallback,
    run_fetch,
    validate_scheme_url,
)

ALLOWED_URL = (
    "https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth"
)


def _scheme(**overrides):
    base = {
        "scheme_id": "kotak_large_cap_direct_growth",
        "display_name": "Kotak Large Cap Fund – Direct Growth",
        "source_url": ALLOWED_URL,
    }
    base.update(overrides)
    return base


def test_validate_rejects_non_allowlisted_url() -> None:
    with pytest.raises(ValueError, match="Rejecting non–problem-statement URL"):
        validate_scheme_url(
            _scheme(source_url="https://www.kotakmf.com/schemes/large-cap")
        )


def test_fetch_writes_html_and_hash(tmp_path: Path) -> None:
    html = b"<html><body>expense ratio 0.5%</body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == ALLOWED_URL
        return httpx.Response(200, content=html)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = fetch_scheme_html(
            _scheme(),
            raw_dir=tmp_path,
            client=client,
            previous_hash=None,
        )

    assert result.status == "success"
    assert result.http_status == 200
    assert result.content_hash == content_sha256(html)
    assert (tmp_path / "kotak_large_cap_direct_growth.html").read_bytes() == html


def test_fetch_surfaces_403(tmp_path: Path) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(403, content=b"forbidden")
    )
    with httpx.Client(transport=transport) as client:
        result = fetch_scheme_html(_scheme(), raw_dir=tmp_path, client=client)

    assert result.status == "failed"
    assert result.http_status == 403
    assert "403" in (result.error or "")
    assert not (tmp_path / "kotak_large_cap_direct_growth.html").exists()


def test_fetch_surfaces_empty_body(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"   "))
    with httpx.Client(transport=transport) as client:
        result = fetch_scheme_html(_scheme(), raw_dir=tmp_path, client=client)

    assert result.status == "failed"
    assert "Empty body" in (result.error or "")


def test_fetch_surfaces_timeout(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        result = fetch_scheme_html(_scheme(), raw_dir=tmp_path, client=client)

    assert result.status == "failed"
    assert "Timeout" in (result.error or "")


def test_refetch_updates_hash_changed_flag(tmp_path: Path) -> None:
    old = b"<html>old</html>"
    new = b"<html>new</html>"
    old_hash = content_sha256(old)

    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=new))
    with httpx.Client(transport=transport) as client:
        result = fetch_scheme_html(
            _scheme(),
            raw_dir=tmp_path,
            client=client,
            previous_hash=old_hash,
        )

    assert result.status == "success"
    assert result.content_hash == content_sha256(new)
    assert result.hash_changed is True


def test_run_fetch_fail_closed_and_writes_log(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "schemes": [
                    _scheme(),
                    _scheme(
                        scheme_id="bad",
                        source_url="https://www.amfiindia.com/not-allowed",
                    ),
                ]
            }
        ),
        encoding="utf-8",
    )
    raw_dir = tmp_path / "raw"
    log_path = tmp_path / "fetch_log.yaml"

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"<html>ok</html>")
    )
    with httpx.Client(transport=transport) as client:
        summary = run_fetch(
            manifest_path=manifest,
            raw_dir=raw_dir,
            fetch_log_path=log_path,
            client=client,
        )

    assert summary.overall_status == "failed"
    assert summary.schemes[0].status == "success"
    assert summary.schemes[1].status == "failed"
    assert "Rejecting" in (summary.schemes[1].error or "")
    assert log_path.exists()
    log = yaml.safe_load(log_path.read_text(encoding="utf-8"))
    assert log["latest_overall_status"] == "failed"
    assert len(log["schemes"]) == 2


def test_build_fetch_headers_uses_browser_user_agent() -> None:
    headers = build_fetch_headers()
    assert "Mozilla" in headers["User-Agent"]
    assert "text/html" in headers["Accept"]


def test_fetch_fallback_uses_cached_raw_on_network_failure(tmp_path: Path) -> None:
    html = b"<html><body>cached corpus</body></html>"
    raw_path = tmp_path / "kotak_large_cap_direct_growth.html"
    raw_path.write_bytes(html)

    transport = httpx.MockTransport(
        lambda request: httpx.Response(403, content=b"forbidden")
    )
    with httpx.Client(transport=transport) as client:
        result = fetch_scheme_with_fallback(
            _scheme(),
            raw_dir=tmp_path,
            client=client,
            fallback_to_cached=True,
        )

    assert result.status == "success"
    assert result.fetch_mode == "cached"
    assert result.content_hash == content_sha256(html)
    assert result.warning is not None


def test_fetch_fallback_fails_without_cached_raw(tmp_path: Path) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(403, content=b"forbidden")
    )
    with httpx.Client(transport=transport) as client:
        result = fetch_scheme_with_fallback(
            _scheme(),
            raw_dir=tmp_path,
            client=client,
            fallback_to_cached=True,
        )

    assert result.status == "failed"
    assert result.http_status == 403


def test_every_success_url_is_problem_statement_url(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"schemes": [_scheme()]}), encoding="utf-8")
    raw_dir = tmp_path / "raw"
    log_path = tmp_path / "fetch_log.yaml"

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"<html>ok</html>")
    )
    with httpx.Client(transport=transport) as client:
        summary = run_fetch(
            manifest_path=manifest,
            raw_dir=raw_dir,
            fetch_log_path=log_path,
            client=client,
        )

    assert summary.ok
    assert summary.schemes[0].source_url == ALLOWED_URL
