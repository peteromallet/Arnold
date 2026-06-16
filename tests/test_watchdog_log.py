"""Tests for watchdog structured logging."""

from __future__ import annotations

import logging

import pytest

from arnold.pipelines.megaplan.watchdog.log import log_event, setup_logging


@pytest.fixture(autouse=True)
def _reset_watchdog_logger():
    logger = logging.getLogger("megaplan.watchdog")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    yield


def _read_log(log_path) -> str:
    return log_path.read_text(encoding="utf-8")


def test_setup_logging_creates_logger(tmp_path):
    log_path = tmp_path / "watchdog.log"
    logger = setup_logging(log_path=log_path, level="DEBUG")
    assert logger.name == "megaplan.watchdog"
    assert logger.level == logging.DEBUG


def test_log_event_emits_key_value_format(tmp_path):
    log_path = tmp_path / "watchdog.log"
    logger = setup_logging(log_path=log_path, level="INFO")
    log_event(logger, "scan_start", roots="/a,/b", lookback_hours=24)
    text = _read_log(log_path)
    assert "event=scan_start" in text
    assert "roots=/a,/b" in text
    assert "lookback_hours=24" in text


def test_log_event_escapes_values_with_spaces(tmp_path):
    log_path = tmp_path / "watchdog.log"
    logger = setup_logging(log_path=log_path, level="INFO")
    log_event(logger, "repair_failed", reason="has stale lock")
    text = _read_log(log_path)
    assert 'reason="has stale lock"' in text


def test_setup_logging_does_not_duplicate_handlers(tmp_path):
    log_path = tmp_path / "watchdog.log"
    logger1 = setup_logging(log_path=log_path, level="INFO")
    initial_handlers = len(logger1.handlers)
    setup_logging(log_path=log_path, level="INFO")
    assert len(logger1.handlers) == initial_handlers
