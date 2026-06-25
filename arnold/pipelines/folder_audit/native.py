"""Native runtime adapters for the ``folder_audit`` pipeline.

Each ``@phase``-decorated function bridges the native runtime's dict-based
context into the Megaplan :class:`StepContext` that ``IngestStep``,
``AuditStep``, and ``EmitStep`` expect, invokes the step's ``run(ctx)``,
and converts the resulting :class:`StepResult` (``state_patch`` plus
``outputs``) into a mergeable dict that the native runtime applies to
working state.

Usage::

    from arnold.pipeline.native import phase, pipeline
    from arnold.pipelines.folder_audit.native import ingest, audit, emit

    @pipeline
    def folder_audit_native(ctx):
        state = yield ingest(ctx)
        state = yield audit(ctx)
        state = yield emit(ctx)
        return state
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.pipeline.types import StepContext
from arnold.pipeline.native.decorators import phase, pipeline  # type: ignore[import-untyped]
from arnold.pipelines.folder_audit.steps import (
    AuditStep,
    EmitStep,
    IngestStep,
    _default_worker,
)

_pipeline_name: str = "folder-audit"


def _build_step_ctx(native_ctx: dict[str, Any]) -> StepContext:
    """Build a neutral :class:`StepContext` from a native-runtime context dict.

    The native runtime passes a lightweight dict with ``state``, ``inputs``,
    and ``artifact_root``.  This function maps those fields onto the fields
    that the folder-audit steps actually read:

    * ``artifact_root`` ← ``ctx["artifact_root"]``
    * ``state`` ← ``ctx["state"]``
    * ``inputs`` ← ``ctx.get("inputs", ctx["state"])``
    * ``mode`` ← ``state.get("mode", "default")``
    """
    state: dict[str, Any] = dict(native_ctx.get("state", {}))
    raw_inputs: dict[str, Any] = dict(
        native_ctx.get("inputs", state)
    )
    artifact_root = native_ctx.get("artifact_root", ".")

    return StepContext(
        artifact_root=str(artifact_root),
        state=state,
        inputs=raw_inputs,  # type: ignore[arg-type]  # Mapping[str, Any] compatible at runtime
        mode=str(state.get("mode", "default")),
    )


def _step_result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a :class:`StepResult` into a mergeable native-runtime dict.

    Combines ``state_patch`` and ``outputs`` entries into a single flat
    dict.  ``Path`` values in outputs are stringified so the state stays
    JSON-serializable for cursor persistence.
    """
    state_patch: dict[str, Any] = dict(getattr(result, "state_patch", {}))
    raw_outputs: dict[str, Any] = dict(getattr(result, "outputs", {}))

    merged: dict[str, Any] = dict(state_patch)
    for key, value in raw_outputs.items():
        if isinstance(value, Path):
            merged[key] = str(value)
        else:
            merged[key] = value

    return merged


# ── Phase wrappers ──────────────────────────────────────────────────────


@phase(name="ingest")
def ingest(ctx: dict[str, Any]) -> dict[str, Any]:
    """Ingest phase: walk the target directory and produce a tree."""
    step_ctx = _build_step_ctx(ctx)
    step = IngestStep()
    result = step.run(step_ctx)
    return _step_result_to_dict(result)


@phase(name="audit")
def audit(ctx: dict[str, Any]) -> dict[str, Any]:
    """Audit phase: classify the directory tree level-by-level.

    The worker callable is resolved from ``ctx["state"]["_worker"]`` when
    present; otherwise the pipeline default ``_default_worker`` is used
    (matching :func:`build_pipeline` behaviour).
    """
    step_ctx = _build_step_ctx(ctx)
    state = step_ctx.state
    worker = state.get("_worker", _default_worker)
    step = AuditStep(
        _worker=worker,
        _pipeline_name=_pipeline_name,
    )
    result = step.run(step_ctx)
    return _step_result_to_dict(result)


@phase(name="emit")
def emit(ctx: dict[str, Any]) -> dict[str, Any]:
    """Emit phase: write ``audit.json`` and ``audit.md`` to the artifact root."""
    step_ctx = _build_step_ctx(ctx)
    step = EmitStep()
    result = step.run(step_ctx)
    return _step_result_to_dict(result)


# ── Native pipeline generator ───────────────────────────────────────────


@pipeline(name="folder-audit", description="Native linear folder-audit pipeline")
def folder_audit_native(ctx):
    """Linear native pipeline: ingest → audit → emit."""
    state = yield ingest(ctx)
    state = yield audit(ctx)
    state = yield emit(ctx)
    return state


# ── Explicit native entrypoint ──────────────────────────────────────────


def run_native(
    *,
    target_dir: str | Path = ".",
    artifact_root: str | Path | None = None,
    max_depth: int = 3,
    profile: dict[str, Any] | None = None,
    mode: str = "default",
    worker: Any = None,
    trace_dir: str | Path | None = None,
    max_phases: int | None = None,
    resume: bool = False,
) -> Any:
    """Run the native ``folder_audit`` pipeline end-to-end.

    This is the explicit native entrypoint for callers that want to run the
    compiled native program directly.  Native execution is canonical by
    default; this function does not require ``ARNOLD_NATIVE_RUNTIME=1``.

    Graph execution via :func:`arnold.pipelines.folder_audit.build_pipeline`
    remains available through the graph entrypoint and explicit legacy
    fallback controls.

    Parameters
    ----------
    target_dir:
        Directory tree to audit.  Defaults to the current working directory.
    artifact_root:
        Directory for pipeline artifacts and resume cursors.  When *None*
        (the default), a path is derived from *target_dir*:
        ``<target_dir>/.arnold/folder-audit/native``.
    max_depth:
        Maximum directory depth for the tree walk (forwarded to
        :func:`_build_tree`).
    profile:
        Optional profile dict forwarded into audit-step spec resolution
        (stored in initial state as ``profile``).
    mode:
        Pipeline mode string, e.g. ``"code"`` or ``"default"``.
    worker:
        Optional worker callable for the audit phase.  When *None* the
        pipeline-level :func:`_default_worker` is used.
    trace_dir:
        Optional directory for parity-trace emission.  Forwarded to
        :func:`run_native_pipeline`.  When *None* (default) no trace
        files are written.
    max_phases:
        Forwarded to :func:`run_native_pipeline` — maximum number of
        ``phase`` instructions before forced suspension.
    resume:
        Forwarded to :func:`run_native_pipeline` — resume from a
        previously persisted cursor when ``True``.

    Returns
    -------
    NativeExecutionResult
        Carries final state, completed stage ids, pc, suspension flag,
        optional cursor path, and accumulated envelope.

    """
    from arnold.pipeline.native.compiler import compile_pipeline
    from arnold.pipeline.native.runtime import run_native_pipeline

    if artifact_root is None:
        artifact_root = Path(target_dir) / ".arnold" / "folder-audit" / "native"

    # Build initial state visible to every phase
    initial_state: dict[str, Any] = {
        "target_dir": str(Path(target_dir).resolve()),
        "max_depth": max_depth,
        "mode": mode,
    }
    if profile is not None:
        initial_state["profile"] = profile
    if worker is not None:
        initial_state["_worker"] = worker

    program = compile_pipeline(folder_audit_native)
    return run_native_pipeline(
        program,
        artifact_root=artifact_root,
        initial_state=initial_state,
        max_phases=max_phases,
        resume=resume,
        trace_dir=trace_dir,
    )
