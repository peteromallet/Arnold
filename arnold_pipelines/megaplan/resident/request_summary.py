"""Canonical semantic one-line presentation for resident work.

Raw inbound text remains authoritative evidence in the message store.  It is
deliberately *not* treated as a semantic summary here: callers must provide a
purpose-built description or receive the explicit unavailable fallback.
"""

from __future__ import annotations

import unicodedata

from agentbox.redaction import redact_text


REQUEST_SUMMARY_PREFIX = "Current request: "
REQUEST_SUMMARY_TEXT_MAX_CHARS = 240
REQUEST_DESCRIPTION_MAX_CHARS = 180
REQUEST_SUMMARY_UNAVAILABLE = "unavailable from the authoritative inbound request"


def canonical_request_description(description: object) -> str | None:
    """Normalize one model-authored semantic description for durable reuse."""

    if not isinstance(description, str):
        return None
    visible = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in redact_text(description)
    )
    normalized = " ".join(visible.split())
    if not normalized:
        return None
    if normalized.rstrip(".") == REQUEST_SUMMARY_UNAVAILABLE.rstrip("."):
        return None
    if len(normalized) > REQUEST_DESCRIPTION_MAX_CHARS:
        raise ValueError(
            f"semantic request description exceeds {REQUEST_DESCRIPTION_MAX_CHARS} characters"
        )
    return normalized.rstrip(".") + "."


def current_request_summary_line(semantic_description: object) -> str:
    """Render a bounded semantic header without guessing from raw/history text."""

    normalized = canonical_request_description(semantic_description)
    if normalized is None:
        return REQUEST_SUMMARY_PREFIX + REQUEST_SUMMARY_UNAVAILABLE
    return REQUEST_SUMMARY_PREFIX + normalized


def source_request_fallback_line(authoritative_request: object) -> str:
    """Render a bounded raw-source fallback, never used as semantic authority."""

    if not isinstance(authoritative_request, str):
        return current_request_summary_line(None)
    visible = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in redact_text(authoritative_request)
    )
    normalized = " ".join(visible.split())
    if not normalized:
        return current_request_summary_line(None)
    if len(normalized) > REQUEST_SUMMARY_TEXT_MAX_CHARS:
        normalized = normalized[: REQUEST_SUMMARY_TEXT_MAX_CHARS - 1].rstrip() + "…"
    return REQUEST_SUMMARY_PREFIX + normalized


def content_with_request_summary(
    content: object,
    *,
    semantic_description: object | None = None,
    summary_line: object | None = None,
    max_chars: int | None = None,
    trusted_summary_line: bool = False,
) -> tuple[str, str]:
    """Put the trusted request summary first and return it with the full content."""

    if (
        trusted_summary_line
        and isinstance(summary_line, str)
        and summary_line.startswith(REQUEST_SUMMARY_PREFIX)
        and "\n" not in summary_line
        and "\r" not in summary_line
        and len(summary_line) <= len(REQUEST_SUMMARY_PREFIX) + REQUEST_SUMMARY_TEXT_MAX_CHARS
    ):
        line = summary_line
    elif isinstance(summary_line, str) and summary_line.startswith(REQUEST_SUMMARY_PREFIX):
        line = current_request_summary_line(summary_line[len(REQUEST_SUMMARY_PREFIX) :])
    else:
        line = current_request_summary_line(semantic_description)
    body = str(content or "").strip()
    if body.startswith(REQUEST_SUMMARY_PREFIX):
        body = body.partition("\n")[2].lstrip()
    rendered = line if not body else f"{line}\n\n{body}"
    if max_chars is not None and len(rendered) > max_chars:
        if max_chars <= len(line):
            rendered = line[:max_chars]
        else:
            suffix = "…"
            body_limit = max_chars - len(line) - 2
            shortened = body[: max(0, body_limit - len(suffix))].rstrip() + suffix
            rendered = f"{line}\n\n{shortened}"
    return rendered, line
