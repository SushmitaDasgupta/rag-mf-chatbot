"""Tests for shared logging configuration."""

from __future__ import annotations

import logging

from src.logging_config import get_logger, log_checkpoint, setup_logging


def test_setup_logging_is_idempotent() -> None:
    setup_logging("INFO")
    setup_logging("DEBUG")
    assert logging.getLogger().level == logging.INFO


def test_noisy_loggers_are_quiet() -> None:
    setup_logging("INFO")
    assert logging.getLogger("sentence_transformers").level >= logging.WARNING


def test_log_checkpoint_formats_message() -> None:
    import io
    import logging

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    test_logger = logging.getLogger("test.checkpoint")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)

    log_checkpoint(test_logger, "P1.3", "chunk_sections", "Build chunks", scheme_id="kotak_gold")
    output = stream.getvalue()
    assert "CHECKPOINT | P1.3 | chunk_sections" in output
    assert "scheme_id=kotak_gold" in output


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("src.ingest.run")
    assert logger.name == "src.ingest.run"
