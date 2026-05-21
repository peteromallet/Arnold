"""Structured exception hierarchy for VibeComfy framework.

All VibeComfyError subclasses inherit from RuntimeError so the CLI
catch tuple ``(OSError, RuntimeError, ValueError)`` in
``commands/run.py:163`` catches them.
"""

from __future__ import annotations


class VibeComfyError(RuntimeError):
    """Base exception for all VibeComfy framework errors.

    Accepts an optional ``next_action`` string that callers can use to
    suggest remediation steps.  When set, ``str(exc)`` appends
    `` next action: <value>`` to the original message.
    """

    def __init__(self, message: str, *, next_action: str | None = None) -> None:
        self._orig_message: str = message
        self.next_action: str | None = next_action
        super().__init__(message)

    def __str__(self) -> str:
        msg = self._orig_message
        if self.next_action is not None:
            msg = f"{msg} next action: {self.next_action}"
        return msg

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._orig_message!r}, next_action={self.next_action!r})"


class ModelAssetError(VibeComfyError):
    """A model asset referenced by the workflow could not be resolved."""


class SchemaValidationError(VibeComfyError):
    """Workflow failed schema validation."""


class QueueError(VibeComfyError):
    """Workflow queue operation failed (enqueue / wait / result)."""


class ContextVarBindingError(VibeComfyError):
    """Context variable binding is missing or incorrect (e.g. no active workflow)."""


class ConversionParityError(VibeComfyError):
    """Emitted code is not equivalent to the source workflow."""


class SubgraphFreshnessError(VibeComfyError):
    """A subgraph embedded in the workflow is stale relative to its source."""


class RuntimeNodeError(VibeComfyError):
    """A node failed during ComfyUI runtime execution."""


class DriftError(VibeComfyError):
    """Custom-node or model pins have drifted from the lockfile."""


__all__ = [
    "ContextVarBindingError",
    "ConversionParityError",
    "DriftError",
    "ModelAssetError",
    "QueueError",
    "RuntimeNodeError",
    "SchemaValidationError",
    "SubgraphFreshnessError",
    "VibeComfyError",
]
