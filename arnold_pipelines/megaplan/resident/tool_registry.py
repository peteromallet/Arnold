"""Structured tool registration for resident Megaplan operations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .tool_schemas import ToolInput, ToolOperationKind, ToolResult

ToolCallable = Callable[[ToolInput], ToolResult | Awaitable[ToolResult]]


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    description: str
    operation_kind: ToolOperationKind
    input_model: type[ToolInput]
    output_model: type[BaseModel]
    handler: ToolCallable


class ToolRegistry:
    """Name-addressed registry for constrained resident tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {}

    def register(self, registration: ToolRegistration) -> None:
        if registration.name in self._tools:
            raise ValueError(f"resident tool already registered: {registration.name}")
        self._tools[registration.name] = registration

    def get(self, name: str) -> ToolRegistration:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown resident tool: {name}") from exc

    def list(self) -> tuple[ToolRegistration, ...]:
        return tuple(self._tools.values())

    def as_schema_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "operation_kind": tool.operation_kind,
                "input_schema": tool.input_model.model_json_schema(),
            }
            for tool in self.list()
        ]

    def as_compact_catalog(self) -> list[dict[str, Any]]:
        """Return CLI orientation without embedding every nested JSON Schema."""

        catalog: list[dict[str, Any]] = []
        for tool in self.list():
            schema = tool.input_model.model_json_schema()
            properties = schema.get("properties") or {}
            catalog.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "operation_kind": tool.operation_kind,
                    "arguments": list(properties),
                    "required": list(schema.get("required") or []),
                }
            )
        return catalog
