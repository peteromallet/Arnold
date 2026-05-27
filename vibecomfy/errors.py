"""Structured exception hierarchy for VibeComfy framework.

All VibeComfyError subclasses inherit from RuntimeError so the CLI
catch tuple ``(OSError, RuntimeError, ValueError)`` in
``commands/run.py`` catches them.
"""

from __future__ import annotations


class VibeComfyError(RuntimeError):
    """Base exception for all VibeComfy framework errors.

    Accepts an optional ``next_action`` string that callers can use to
    suggest remediation steps.  When set, ``str(exc)`` appends
    ``\\nNext action: <value>`` to the original message.
    """

    def __init__(self, message: str, *, next_action: str | None = None) -> None:
        self.message: str = str(message)
        # Preserve legacy attribute name used by Block A code paths.
        self._orig_message: str = self.message
        self.next_action: str | None = next_action
        super().__init__(self.message)

    def __str__(self) -> str:
        if not self.next_action:
            return self.message
        return f"{self.message}\nNext action: {self.next_action}"

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}({self.message!r}, next_action={self.next_action!r})"
        )


# ---------------------------------------------------------------------------
# Block A error classes
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# origin/main error classes
# ---------------------------------------------------------------------------


class WorkflowValidationError(VibeComfyError, ValueError):
    """Workflow validation failed before queue submission."""


class WorkflowBuildError(VibeComfyError, ValueError):
    """Workflow compilation or scratchpad construction failed."""


class WorkflowQueueError(VibeComfyError):
    """Prompt queue submission failed."""


class SessionBusyError(VibeComfyError):
    """A session rejected work because another operation is in flight."""


class SessionLifecycleError(VibeComfyError):
    """A session lifecycle operation failed or was refused."""


class NodePackInstallError(VibeComfyError):
    """Automatic custom-node pack installation failed."""


class RuntimeStartupError(VibeComfyError):
    """A managed runtime failed to start."""


__all__ = [
    # base
    "VibeComfyError",
    # Block A
    "ContextVarBindingError",
    "ConversionParityError",
    "DriftError",
    "ModelAssetError",
    "QueueError",
    "RuntimeNodeError",
    "SchemaValidationError",
    "SubgraphFreshnessError",
    # origin/main
    "NodePackInstallError",
    "RuntimeStartupError",
    "SessionBusyError",
    "SessionLifecycleError",
    "WorkflowBuildError",
    "WorkflowQueueError",
    "WorkflowValidationError",
]
