"""Typed resource descriptors attached to durable operation runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Mapping, TypeAlias

__all__ = [
    "JSONValue",
    "ResourceType",
    "TypedResource",
    "ensure_json_safe",
]

JSONValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["JSONValue"]
    | dict[str, "JSONValue"]
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ResourceType(str, Enum):
    """Stable resource tags for operation-linked runtime assets."""

    GIT_WORKTREE = "git_worktree"
    PROCESS_SESSION = "process_session"
    LOG = "log"
    DATA_VOLUME = "data_volume"
    EXTERNAL_SERVICE = "external_service"


def ensure_json_safe(value: Any, *, field_name: str = "value") -> JSONValue:
    """Return ``value`` after rejecting data that JSON cannot round-trip safely."""

    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{field_name} must be JSON-safe")
        return value
    if isinstance(value, list | tuple):
        return [
            ensure_json_safe(item, field_name=f"{field_name}[]") for item in value
        ]
    if isinstance(value, Mapping):
        safe: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} keys must be strings")
            safe[key] = ensure_json_safe(item, field_name=f"{field_name}.{key}")
        return safe
    raise ValueError(f"{field_name} must be JSON-safe")


@dataclass(frozen=True)
class TypedResource:
    """Concrete, tagged resource record owned by an operation run."""

    id: str
    operation_id: str
    resource_type: ResourceType
    name: str
    details: Mapping[str, JSONValue] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        if not self.operation_id:
            raise ValueError("operation_id is required")
        if not self.name:
            raise ValueError("name is required")
        if not isinstance(self.resource_type, ResourceType):
            object.__setattr__(self, "resource_type", ResourceType(self.resource_type))
        object.__setattr__(
            self,
            "details",
            ensure_json_safe(dict(self.details), field_name="details"),
        )
