"""Redaction helpers for source-code content and tool payloads."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


REDACTION_MARKER = "[REDACTED_SECRET]"

_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
_GITHUB_TOKEN_RE = re.compile(
    r"\b(?:gh[opusr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"
)
_AWS_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_AWS_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(AWS_SECRET_ACCESS_KEY\s*[:=]\s*[\"']?)([A-Za-z0-9/+=]{32,})([\"']?)"
)
_HIGH_ENTROPY_HEX_RE = re.compile(r"\b[0-9A-Fa-f]{32,}\b")


def redact_code_secrets(value: Any) -> Any:
    """Recursively redact secret-like strings from JSON-compatible payloads."""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {
            key: redact_code_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_code_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_code_secrets(item) for item in value)
    if isinstance(value, set):
        return {redact_code_secrets(item) for item in value}
    return value


def redact_text(text: str) -> str:
    redacted = _AWS_SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{REDACTION_MARKER}{match.group(3)}",
        text,
    )
    for pattern in (
        _OPENAI_KEY_RE,
        _GITHUB_TOKEN_RE,
        _AWS_ACCESS_KEY_RE,
        _HIGH_ENTROPY_HEX_RE,
    ):
        redacted = pattern.sub(REDACTION_MARKER, redacted)
    return redacted


__all__ = ["REDACTION_MARKER", "redact_code_secrets", "redact_text"]
