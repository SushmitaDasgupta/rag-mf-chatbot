"""Shared logging setup for ingest pipeline, scripts, and API."""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Iterator

_CONFIGURED = False

LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_NOISY_LOGGERS = (
    "sentence_transformers",
    "transformers",
    "httpx",
    "httpcore",
    "chromadb",
    "urllib3",
    "filelock",
    "huggingface_hub",
    "torch",
    "accelerate",
)


class FlushingStreamHandler(logging.StreamHandler):
    """Flush after every log record so GitHub Actions shows output immediately."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def _in_github_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS", "").lower() == "true"


def _emit_ci_line(message: str) -> None:
    """Mirror important lines to stdout (unbuffered) for GitHub Actions log UI."""
    if _in_github_actions():
        print(message, flush=True)


def pipeline_echo(message: str) -> None:
    """Write a pipeline status line directly to stdout (visible in GitHub Actions)."""
    _emit_ci_line(message)


def setup_logging(level: str | int | None = None) -> None:
    """Configure root logging once with a readable, timestamped format."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = _resolve_level(level)
    handler = FlushingStreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _CONFIGURED = True


def _resolve_level(level: str | int | None) -> int:
    if level is None:
        return logging.INFO
    if isinstance(level, int):
        return level
    return getattr(logging, str(level).upper(), logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def _format_checkpoint(phase: str, step: str, message: str, **fields: object) -> str:
    if fields:
        extras = " | ".join(f"{key}={value}" for key, value in fields.items())
        return f"CHECKPOINT | {phase} | {step} | {message} | {extras}"
    return f"CHECKPOINT | {phase} | {step} | {message}"


def log_checkpoint(
    logger: logging.Logger,
    phase: str,
    step: str,
    message: str,
    **fields: object,
) -> None:
    """Emit a single-line pipeline checkpoint (maps to implementation.md P1.x steps)."""
    line = _format_checkpoint(phase, step, message, **fields)
    logger.info("%s", line)
    _emit_ci_line(line)


def log_manifest_roster(logger: logging.Logger, schemes: list[dict]) -> None:
    """Log which Kotak schemes from manifest.yaml are in scope for this run."""
    lines = [
        "-" * 72,
        f"CORPUS MANIFEST | schemes_in_scope={len(schemes)}",
    ]
    for index, scheme in enumerate(schemes, start=1):
        scheme_id = scheme.get("scheme_id")
        display_name = scheme.get("display_name") or scheme_id
        category = scheme.get("category") or "unknown"
        source_url = scheme.get("source_url") or ""
        lines.extend(
            [
                f"  [{index}/{len(schemes)}] {display_name}",
                f"         scheme_id={scheme_id} | category={category}",
                f"         source_url={source_url}",
            ]
        )
    lines.append("-" * 72)
    for line in lines:
        logger.info("%s", line)
        _emit_ci_line(line)


@contextmanager
def log_stage(
    logger: logging.Logger,
    stage: str,
    *,
    detail: str = "",
) -> Iterator[None]:
    """Log a pipeline stage with start/finish banners and elapsed time."""
    label = f"{stage} — {detail}" if detail else stage
    banner = "=" * 72
    start_line = f"STAGE START: {label}"
    logger.info(banner)
    logger.info("%s", start_line)
    _emit_ci_line(banner)
    _emit_ci_line(start_line)
    started = time.perf_counter()
    try:
        yield
    except Exception:
        elapsed = time.perf_counter() - started
        fail_line = f"STAGE FAILED: {label} ({elapsed:.1f}s)"
        logger.exception("%s", fail_line)
        logger.info(banner)
        _emit_ci_line(fail_line)
        _emit_ci_line(banner)
        raise
    else:
        elapsed = time.perf_counter() - started
        done_line = f"STAGE DONE: {label} ({elapsed:.1f}s)"
        logger.info("%s", done_line)
        logger.info(banner)
        _emit_ci_line(done_line)
        _emit_ci_line(banner)


def log_pipeline_header(logger: logging.Logger, run_id: str, *, detail: str = "") -> None:
    banner = "#" * 72
    header = f"INGEST PIPELINE | run_id={run_id}"
    logger.info("")
    logger.info(banner)
    logger.info("%s", header)
    _emit_ci_line("")
    _emit_ci_line(banner)
    _emit_ci_line(header)
    if detail:
        logger.info("%s", detail)
        _emit_ci_line(detail)
    logger.info(banner)
    _emit_ci_line(banner)


def log_pipeline_footer(
    logger: logging.Logger,
    run_id: str,
    overall_status: str,
    *,
    elapsed_seconds: float,
    stages: dict[str, str],
    errors: list[str] | None = None,
) -> None:
    banner = "#" * 72
    summary = f"INGEST COMPLETE | run_id={run_id} | status={overall_status} | elapsed={elapsed_seconds:.1f}s"
    logger.info(banner)
    logger.info("%s", summary)
    _emit_ci_line(banner)
    _emit_ci_line(summary)
    for name, status in stages.items():
        line = f"  {name:<8} {status}"
        logger.info("%s", line)
        _emit_ci_line(line)
    for err in errors or []:
        err_line = f"  ! {err}"
        logger.error("%s", err_line)
        _emit_ci_line(err_line)
    logger.info(banner)
    logger.info("")
    _emit_ci_line(banner)
    _emit_ci_line("")
