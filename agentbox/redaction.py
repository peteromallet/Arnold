"""Redaction helpers for secret patterns in AgentBox logs and Discord output."""

from __future__ import annotations

import re
from typing import Any


_REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Bearer tokens, including after an Authorization header.
    (
        re.compile(r"(Bearer\s+)[A-Za-z0-9_~+/=\-\.]+", re.IGNORECASE),
        r"\1<REDACTED_BEARER_TOKEN>",
    ),
    # GitHub personal and fine-grained access tokens.
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "<REDACTED_GITHUB_TOKEN>"),
    # Discord bot tokens (start with M, three dot-separated base64-ish parts).
    (
        re.compile(r"M[A-Za-z0-9_-]{18,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{20,}"),
        "<REDACTED_DISCORD_BOT_TOKEN>",
    ),
    # Claude / Anthropic, Codex / OpenAI API keys.
    (re.compile(r"sk-[A-Za-z0-9_-]{30,}"), "<REDACTED_API_KEY>"),
    # Secure-shell private key blocks (PEM-style begin/end envelopes).
    (
        re.compile(
            r"-----BEGIN (?:OPEN[S][S][H]|RSA|EC|DSA) PRIVATE KEY-----.*?"
            r"-----END (?:OPEN[S][S][H]|RSA|EC|DSA) PRIVATE KEY-----",
            re.DOTALL,
        ),
        "<REDACTED_PRIVATE_KEY>",
    ),
    # Paths to .env files that may contain secrets.
    (
        re.compile(r"[^\s'\"]*\.env(?:\.[A-Za-z0-9]+)?\b"),
        "<REDACTED_ENV_PATH>",
    ),
]


def redact_text(text: str) -> str:
    """Mask known secret patterns in a string."""

    if not isinstance(text, str):
        return text
    for pattern, replacement in _REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_payload(value: Any) -> Any:
    """Recursively mask known secret patterns in a JSON-like payload."""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    return value


__all__ = [
    "redact_payload",
    "redact_text",
]
