"""Pydantic schemas for resident tool boundaries."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ToolOperationKind = Literal["read", "write", "cloud_read", "cloud_start", "control"]


class ToolInput(BaseModel):
    """Base class for resident tool inputs."""


class ToolResult(BaseModel):
    ok: bool
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class EmptyToolInput(ToolInput):
    pass


class ToolCallAuditRecord(BaseModel):
    id: str
    tool_name: str
    operation_kind: ToolOperationKind
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = Field(default=0, ge=0)
