"""Redaction helpers for broker-visible security payloads."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

REDACTED = "[REDACTED]"

_TOKEN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s,;]+)"),
        rf"\1{REDACTED}",
    ),
    (
        re.compile(r"(?i)\b(bearer\s+)([^\s,;]+)"),
        rf"\1{REDACTED}",
    ),
    (
        re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{10,}(?![A-Za-z0-9_-])"),
        REDACTED,
    ),
    (
        re.compile(r"(?<![A-Za-z0-9_-])gh[pousr]_[A-Za-z0-9_]{10,}(?![A-Za-z0-9_-])"),
        REDACTED,
    ),
    (
        re.compile(r"(?<![A-Za-z0-9_-])github_pat_[A-Za-z0-9_]{10,}(?![A-Za-z0-9_-])"),
        REDACTED,
    ),
    (
        re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*=\s*([^\s,;]+)"),
        rf"\1={REDACTED}",
    ),
)

_SENSITIVE_KEY_TOKENS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "credentials",
    "passwd",
    "password",
    "private_key",
    "secret",
    "session_token",
    "token",
)


def is_sensitive_key(key: str) -> bool:
    """Return True when a field name should never expose its raw value."""

    normalized = key.strip().lower().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_KEY_TOKENS)


def redact_text(text: str, *, extra_values: Iterable[str] = ()) -> str:
    """Mask credential-like substrings in arbitrary text."""

    if not isinstance(text, str):
        return text

    redacted = text
    for pattern, replacement in _TOKEN_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    for value in extra_values:
        if isinstance(value, str) and value:
            redacted = redacted.replace(value, REDACTED)
    return redacted


def redact_value(value: Any, *, extra_values: Iterable[str] = ()) -> Any:
    """Recursively sanitize JSON-like data for agent-visible responses."""

    if isinstance(value, str):
        return redact_text(value, extra_values=extra_values)
    if isinstance(value, Mapping):
        return redact_mapping(value, extra_values=extra_values)
    if isinstance(value, tuple):
        return tuple(redact_value(item, extra_values=extra_values) for item in value)
    if isinstance(value, list):
        return [redact_value(item, extra_values=extra_values) for item in value]
    return value


def redact_mapping(
    payload: Mapping[str, Any],
    *,
    extra_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Sanitize mapping values, fully masking known credential-bearing fields."""

    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if is_sensitive_key(str(key)):
            redacted[str(key)] = REDACTED
            continue
        redacted[str(key)] = redact_value(value, extra_values=extra_values)
    return redacted


__all__ = [
    "REDACTED",
    "is_sensitive_key",
    "redact_mapping",
    "redact_text",
    "redact_value",
]
