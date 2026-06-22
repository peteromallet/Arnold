"""Backend protocol for the manifest execution package."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from arnold.manifest import ManifestCursor, WorkflowManifest

from arnold.execution.registries import ExecutionRegistries
from arnold.execution.result import ExecutionResult, ExecutionState


class ExecutionBackend(Protocol):
    """Backend seam used by :func:`arnold.execution.run`."""

    def run_manifest(
        self,
        manifest: WorkflowManifest,
        *,
        artifact_root: Path,
        registries: ExecutionRegistries,
        resume_cursor: ManifestCursor | None = None,
    ) -> ExecutionResult:
        """Run or resume a compiled workflow manifest."""


class SkeletalBackend:
    """Minimal backend used until runtime behavior lands in later batches."""

    def run_manifest(
        self,
        manifest: WorkflowManifest,
        *,
        artifact_root: Path,
        registries: ExecutionRegistries,
        resume_cursor: ManifestCursor | None = None,
    ) -> ExecutionResult:
        del registries
        return ExecutionResult(
            state=ExecutionState.COMPLETED,
            manifest_id=manifest.id,
            manifest_hash=manifest.manifest_hash or "",
            artifact_root=artifact_root,
            resume_cursor=resume_cursor,
        )


__all__ = [
    "ExecutionBackend",
    "ExecutionRegistries",
    "SkeletalBackend",
]
