"""Shared logging setup for ingest pipeline, scripts, and API."""

from __future__ import annotations

import logging
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
)


def setup_logging(level: str | int | None = None) -> None:
    """Configure root logging once with a readable, timestamped format."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = _resolve_level(level)
    handler = logging.StreamHandler(sys.stdout)
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


@contextmanager
def log_stage(
    logger: logging.Logger,
    stage: str,
    *,
    detail: str = "",
) -> Iterator[None]:
    """Log a pipeline stage with start/finish banners and elapsed time."""
    label = f"{stage} — {detail}" if detail else stage
    logger.info("=" * 72)
    logger.info("STAGE START: %s", label)
    started = time.perf_counter()
    try:
        yield
    except Exception:
        elapsed = time.perf_counter() - started
        logger.exception("STAGE FAILED: %s (%.1fs)", label, elapsed)
        logger.info("=" * 72)
        raise
    else:
        elapsed = time.perf_counter() - started
        logger.info("STAGE DONE: %s (%.1fs)", label, elapsed)
        logger.info("=" * 72)


def log_pipeline_header(logger: logging.Logger, run_id: str, *, detail: str = "") -> None:
    logger.info("")
    logger.info("#" * 72)
    logger.info("INGEST PIPELINE | run_id=%s", run_id)
    if detail:
        logger.info("%s", detail)
    logger.info("#" * 72)


def log_pipeline_footer(
    logger: logging.Logger,
    run_id: str,
    overall_status: str,
    *,
    elapsed_seconds: float,
    stages: dict[str, str],
    errors: list[str] | None = None,
) -> None:
    logger.info("#" * 72)
    logger.info("INGEST COMPLETE | run_id=%s | status=%s | elapsed=%.1fs", run_id, overall_status, elapsed_seconds)
    for name, status in stages.items():
        logger.info("  %-8s %s", name, status)
    for err in errors or []:
        logger.error("  ! %s", err)
    logger.info("#" * 72)
    logger.info("")
