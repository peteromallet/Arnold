"""Operation event contracts for durable operation runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping

from .typed_resources import JSONValue, ensure_json_safe

__all__ = ["OperationEvent"]


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class OperationEvent:
    """Append-only event record for operation debug and replay history."""

    id: str
    operation_id: str
    event_type: str
    summary: str
    sequence: int = 0
    payload: Mapping[str, JSONValue] = field(default_factory=dict)
    artifact_paths: tuple[str, ...] = ()
    debug_paths: tuple[str, ...] = ()
    occurred_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        if not self.operation_id:
            raise ValueError("operation_id is required")
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.summary:
            raise ValueError("summary is required")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        object.__setattr__(
            self,
            "payload",
            ensure_json_safe(dict(self.payload), field_name="payload"),
        )
        object.__setattr__(self, "artifact_paths", tuple(self.artifact_paths))
        object.__setattr__(self, "debug_paths", tuple(self.debug_paths))
