"""Shared base types and helpers for Sprint 1 storage models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_dict(value: Any) -> Any:
    return {} if value is None else value


def _default_list(value: Any) -> Any:
    if value is None:
        return []
    if isinstance(value, (tuple, set)):
        return list(value)
    return value


NormalizedDict = Annotated[dict[str, Any], BeforeValidator(_default_dict)]
NormalizedList = Annotated[list[Any], BeforeValidator(_default_list)]
NormalizedStringList = Annotated[list[str], BeforeValidator(_default_list)]
HomeBackend = Literal["file", "db"]


class StorageModel(BaseModel):
    """Strict base model for backend-facing storage records."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)

    @model_validator(mode="after")
    def _normalize_datetimes(self) -> StorageModel:
        for field_name in self.__class__.model_fields:
            value = getattr(self, field_name, None)
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    normalized = value.replace(tzinfo=timezone.utc)
                else:
                    normalized = value.astimezone(timezone.utc)
                if normalized != value:
                    object.__setattr__(self, field_name, normalized)
        return self
