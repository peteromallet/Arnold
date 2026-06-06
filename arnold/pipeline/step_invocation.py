"""Neutral step-invocation seam primitives for adapter-backed execution.

This module defines the minimal Arnold-side invocation shape plus the
fail-closed adapter registry that later milestones can extend with concrete
adapter implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable


class ModelAdapterNotImplementedError(NotImplementedError):
    """Raised when the reserved model adapter slot is invoked before M3."""


@dataclass(frozen=True)
class StepInvocation:
    """Neutral invocation descriptor passed to an adapter.

    ``kind`` selects the adapter slot. ``metadata`` carries JSON-compatible
    invocation detail without imposing Megaplan-specific structure here.
    """

    kind: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class StepInvocationAdapter(Protocol):
    """Structural protocol for objects that can handle a step invocation."""

    def invoke(self, invocation: StepInvocation) -> Any: ...


class _ModelAdapterPlaceholder:
    """Reserved ``model`` adapter slot. Concrete behavior lands in M3."""

    def invoke(self, invocation: StepInvocation) -> Any:
        raise ModelAdapterNotImplementedError(
            "StepInvocation adapter kind 'model' is reserved for M3 and is not "
            "implemented in M2"
        )


class StepInvocationAdapterRegistry:
    """Small fail-closed registry for step-invocation adapters.

    The registry starts with only the reserved ``model`` slot wired to a
    placeholder implementation. Unknown kinds fail closed during resolution.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, StepInvocationAdapter] = {
            "model": _ModelAdapterPlaceholder(),
        }

    def register(self, kind: str, adapter: StepInvocationAdapter) -> None:
        """Register *adapter* under *kind* or reject duplicate registrations."""
        if kind in self._adapters:
            raise ValueError(f"adapter kind {kind!r} already registered")
        self._adapters[kind] = adapter

    def resolve(self, kind: str) -> StepInvocationAdapter:
        """Return the registered adapter for *kind* or fail closed."""
        if kind not in self._adapters:
            raise KeyError(
                f"unknown adapter kind {kind!r}; registered kinds: {sorted(self._adapters)}"
            )
        return self._adapters[kind]

    @property
    def registered_kinds(self) -> tuple[str, ...]:
        """Return the registry contents in deterministic order."""
        return tuple(sorted(self._adapters))

