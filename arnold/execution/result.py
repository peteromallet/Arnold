"""Public execution result contracts for compiled workflow manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from arnold.manifest import ManifestCursor


class ExecutionState(str, Enum):
    """Terminal or resumable states produced by the manifest runner."""

    COMPLETED = "completed"
    FAILED = "failed"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class ExecutionDiagnostic:
    """Structured diagnostic attached to an execution result."""

    code: str
    message: str
    node_id: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome returned by :func:`arnold.execution.run`."""

    state: ExecutionState
    manifest_id: str
    manifest_hash: str
    artifact_root: Path
    resume_cursor: ManifestCursor | None = None
    diagnostics: tuple[ExecutionDiagnostic, ...] = ()
    outputs: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Whether no caller-provided resume payload can advance this result."""

        return self.state in {
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.QUARANTINED,
        }


__all__ = [
    "ExecutionDiagnostic",
    "ExecutionResult",
    "ExecutionState",
]
