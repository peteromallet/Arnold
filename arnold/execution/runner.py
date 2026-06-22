"""Public synchronous runner entrypoint."""

from __future__ import annotations

from os import PathLike
from pathlib import Path

from arnold.manifest import ManifestCursor, WorkflowManifest

from arnold.execution.backend import ExecutionBackend, ExecutionRegistries, SkeletalBackend
from arnold.execution.result import ExecutionResult


def run(
    manifest: WorkflowManifest,
    *,
    artifact_root: str | PathLike[str],
    registries: ExecutionRegistries | None = None,
    resume_cursor: ManifestCursor | None = None,
    backend: ExecutionBackend | None = None,
) -> ExecutionResult:
    """Run a compiled workflow manifest through a sync backend."""

    if not isinstance(manifest, WorkflowManifest):
        raise TypeError("arnold.execution.run() accepts only compiled WorkflowManifest instances")

    root = Path(artifact_root)
    resolved_registries = registries if registries is not None else ExecutionRegistries()
    resolved_backend = backend if backend is not None else SkeletalBackend()
    return resolved_backend.run_manifest(
        manifest,
        artifact_root=root,
        registries=resolved_registries,
        resume_cursor=resume_cursor,
    )


__all__ = ["run"]
