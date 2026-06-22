"""Structured logging utilities for the live watchdog.

Uses the standard library ``logging`` module with a plain-text formatter that
emits key=value pairs for easy grepping and NDJSON-compatible parsing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any


DEFAULT_LOG_PATH = "~/.megaplan/watchdog/watchdog.log"


class _KeyValueFormatter(logging.Formatter):
    """Formatter that emits ``timestamp level event=k1=v1 k2=v2`` lines."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{self.formatTime(record)} {record.levelname}"
        msg = record.getMessage()
        if record.exc_info:
            msg = f"{msg} exc={self.formatException(record.exc_info)}"
        return f"{base} {msg}"

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()


def _escape_value(value: Any) -> str:
    """Render a value safely for key=value output."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return ",".join(_escape_value(v) for v in value)
    text = str(value)
    if any(c in text for c in " \t\n\r=\""):
        text = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{text}"'
    return text


def log_event(logger: logging.Logger, event: str, **kwargs: Any) -> None:
    """Log a structured event at INFO level.

    Example output::

        2026-06-15T20:30:00+00:00 INFO event=scan_start roots="/a,/b" lookback_hours=24
    """
    parts = [f"event={_escape_value(event)}"]
    for key, value in kwargs.items():
        parts.append(f"{key}={_escape_value(value)}")
    logger.info(" ".join(parts))


def setup_logging(
    log_path: str | Path | None = None,
    level: str = "INFO",
) -> logging.Logger:
    """Configure watchdog logging to file and stdout.

    Returns the ``megaplan.watchdog`` logger.
    """
    logger = logging.getLogger("megaplan.watchdog")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    path = Path(log_path or DEFAULT_LOG_PATH).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    file_handler.setFormatter(_KeyValueFormatter())
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(_KeyValueFormatter())
    logger.addHandler(console_handler)

    return logger


__all__ = [
    "DEFAULT_LOG_PATH",
    "log_event",
    "setup_logging",
]
