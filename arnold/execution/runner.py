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
from arnold.workflow.native_wbc import begin_native_wbc_attempt


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
    attempt = begin_native_wbc_attempt(
        root,
        producer_family="arnold_execution",
        surface="runner",
        run_id=manifest.id,
        subject={"manifest_id": manifest.id, "resume": resume_cursor is not None},
        metadata={"entrypoint": "arnold.execution.run"},
        start_payload={"artifact_root": str(root)},
    )
    resolved_registries = registries if registries is not None else ExecutionRegistries()
    try:
        if backend is not None:
            attempt.effect(
                "dispatch_backend",
                {"backend": backend.__class__.__name__, "resume": resume_cursor is not None},
            )
            result = backend.run_manifest(
                manifest,
                artifact_root=root,
                registries=resolved_registries,
                resume_cursor=resume_cursor,
            )
        else:
            resolved_backend = LocalJournalBackend(state_store=state_store, logger=logger)
            attempt.effect(
                "dispatch_backend",
                {
                    "backend": resolved_backend.__class__.__name__,
                    "resume": resume_cursor is not None,
                },
            )
            result = resolved_backend.run_manifest(
                manifest,
                artifact_root=root,
                registries=resolved_registries,
                resume_cursor=resume_cursor,
                state_store=state_store,
                logger=logger,
            )
    except BaseException as exc:
        attempt.terminal(
            status="failed",
            outcome="error",
            payload={"error_type": exc.__class__.__name__, "error": str(exc)},
        )
        raise

    attempt.terminal(
        status="completed",
        outcome="result",
        payload={"state": getattr(result.state, "value", str(result.state))},
    )
    return result


__all__ = ["run"]
