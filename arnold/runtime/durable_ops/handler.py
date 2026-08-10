"""Operation handler protocol for durable operation adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .operation import OperationRun
from .typed_resources import JSONValue

__all__ = ["OperationHandler"]


@runtime_checkable
class OperationHandler(Protocol):
    """Neutral handler surface for driving one durable operation type."""

    def launch(self, run: OperationRun) -> OperationRun:  # pragma: no cover - protocol
        ...

    def tick(self, run: OperationRun) -> OperationRun:  # pragma: no cover - protocol
        ...

    def resume(self, run: OperationRun) -> OperationRun:  # pragma: no cover - protocol
        ...

    def summarize(self, run: OperationRun) -> str:  # pragma: no cover - protocol
        ...

    def cleanup_descriptor(self, run: OperationRun) -> dict[str, JSONValue]:  # pragma: no cover - protocol
        ...
