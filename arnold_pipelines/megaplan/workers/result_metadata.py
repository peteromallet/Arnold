"""Small helpers for preserving optional WorkerResult metadata."""

from __future__ import annotations

from typing import Any


def prefer_retry_rate_limit(
    base: dict[str, Any] | None,
    retry: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Retry attempts override only when they provide rate-limit metadata."""

    return retry if retry is not None else base


def aggregate_rate_limits(values: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    """Return an opaque aggregate preserving every non-None rate-limit value."""

    non_none = [value for value in values if value is not None]
    if not non_none:
        return None
    return {"values": non_none}
