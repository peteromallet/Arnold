"""Public synchronous runner entrypoint."""

from __future__ import annotations

from os import PathLike
from pathlib import Path

from arnold.manifest import ManifestCursor, WorkflowManifest

from arnold.execution.backend import ExecutionBackend, LocalJournalBackend, SkeletalBackend
from arnold.execution.observability import ExecutionLogger
from arnold.execution.registries import ExecutionRegistries
from arnold.execution.result import ExecutionResult
from arnold.execution.state_store import StateStore


def run(
    manifest: WorkflowManifest,
    *,
    artifact_root: str | PathLike[str],
    registries: ExecutionRegistries | None = None,
    resume_cursor: ManifestCursor | None = None,
    backend: ExecutionBackend | None = None,
    state_store: StateStore | None = None,
    logger: ExecutionLogger | None = None,
) -> ExecutionResult:
    """Run a compiled workflow manifest through a sync backend."""

    if not isinstance(manifest, WorkflowManifest):
        raise TypeError("arnold.execution.run() accepts only compiled WorkflowManifest instances")

    root = Path(artifact_root)
    resolved_registries = registries if registries is not None else ExecutionRegistries()
    if backend is not None:
        return backend.run_manifest(
            manifest,
            artifact_root=root,
            registries=resolved_registries,
            resume_cursor=resume_cursor,
        )

    resolved_backend = LocalJournalBackend(state_store=state_store, logger=logger)
    return resolved_backend.run_manifest(
        manifest,
        artifact_root=root,
        registries=resolved_registries,
        resume_cursor=resume_cursor,
        state_store=state_store,
        logger=logger,
    )


__all__ = ["run"]
