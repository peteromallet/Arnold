"""Shared helpers for FileStore slice mixins."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any
from uuid import uuid4

from arnold.pipelines.megaplan._core.io import json_dump

_ACTIVE_EPIC_STATES = {"shaping", "sprinting", "planned", "paused"}
_TERMINAL_TURN_STATUSES = {"completed", "failed", "abandoned"}
_OBSERVATION_KINDS = {"friction", "ambiguity", "tool_failure", "confusion", "pattern_noticed"}
_SOURCE_REFERENCE_PREFIX = {
    "user_uploaded": "img_user_upload",
    "caller_uploaded": "img_caller_upload",
    "agent_generated": "img_agent_generated",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _utc_key(value: datetime | None) -> tuple[datetime, bool]:
    if value is None:
        return (datetime.min.replace(tzinfo=UTC), True)
    return (value, False)


def _model_bytes(model: Any) -> bytes:
    if hasattr(model, "model_dump"):
        return json_dump(model.model_dump(mode="json")).encode("utf-8")
    return json_dump(model).encode("utf-8")


__all__ = [
    "_ACTIVE_EPIC_STATES",
    "_OBSERVATION_KINDS",
    "_SOURCE_REFERENCE_PREFIX",
    "_TERMINAL_TURN_STATUSES",
    "_model_bytes",
    "_new_id",
    "_parse_datetime",
    "_utc_key",
]
