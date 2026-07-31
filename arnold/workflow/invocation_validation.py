"""Compile-side contract for validating step-invocation adapter kinds.

Workflow validation must be usable without importing the execution plane.
It therefore consumes this small structural view instead of constructing an
execution adapter registry.  Runtime registries satisfy the protocol
structurally; no adapter implementation is imported or invoked here.
"""

from __future__ import annotations

from typing import Protocol


class InvocationRegistryView(Protocol):
    """Read-only registry surface required by compile-time validation."""

    def resolve(self, kind: str) -> object:
        """Return the registered value for *kind* or raise ``KeyError``."""

    @property
    def registered_kinds(self) -> tuple[str, ...]:
        """Return registered kind names in deterministic order."""


class DefaultInvocationRegistryView:
    """Fail-closed compile-time view of Arnold's reserved adapter kinds."""

    _REGISTERED_KINDS = ("model",)

    def resolve(self, kind: str) -> object:
        if kind not in self._REGISTERED_KINDS:
            raise KeyError(
                f"unknown adapter kind {kind!r}; "
                f"registered kinds: {list(self._REGISTERED_KINDS)!r}"
            )
        return kind

    @property
    def registered_kinds(self) -> tuple[str, ...]:
        return self._REGISTERED_KINDS
