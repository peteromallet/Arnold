from __future__ import annotations


class VibeComfyError(RuntimeError):
    """Base class for expected VibeComfy failures with an optional remediation hint."""

    def __init__(self, message: str, *, next_action: str | None = None) -> None:
        self.message = str(message)
        self.next_action = next_action
        super().__init__(self.message)

    def __str__(self) -> str:
        if not self.next_action:
            return self.message
        return f"{self.message}\nNext action: {self.next_action}"


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
    "VibeComfyError",
    "WorkflowValidationError",
    "WorkflowBuildError",
    "WorkflowQueueError",
    "SessionBusyError",
    "SessionLifecycleError",
    "NodePackInstallError",
    "RuntimeStartupError",
]
