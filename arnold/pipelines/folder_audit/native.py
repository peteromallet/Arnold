"""Native runtime entrypoints for ``arnold.pipelines.folder_audit``."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline import StepContext, StepResult
from arnold.pipeline.native import compile_pipeline, phase, pipeline, run_native_pipeline

from arnold.pipelines.folder_audit.pipeline import (
    AuditStep,
    EmitStep,
    IngestStep,
    _default_worker,
)


def _ctx_from_native(raw_ctx: object) -> StepContext:
    if isinstance(raw_ctx, dict):
        raw_state = raw_ctx.get("state", {})
        state = dict(raw_state) if isinstance(raw_state, Mapping) else {}
        raw_inputs = raw_ctx.get("inputs", state)
        inputs = dict(raw_inputs) if isinstance(raw_inputs, Mapping) else {}
        return StepContext(
            artifact_root=str(raw_ctx.get("artifact_root", ".")),
            state=state,
            inputs=inputs,
            mode=str(raw_ctx.get("mode", state.get("mode", "default"))),
        )
    artifact_root = getattr(raw_ctx, "artifact_root", ".")
    raw_state = getattr(raw_ctx, "state", {}) or {}
    raw_inputs = getattr(raw_ctx, "inputs", raw_state) or {}
    return StepContext(
        artifact_root=str(artifact_root),
        state=dict(raw_state) if isinstance(raw_state, Mapping) else {},
        inputs=dict(raw_inputs) if isinstance(raw_inputs, Mapping) else {},
        mode=str(getattr(raw_ctx, "mode", "default")),
    )


def _json_safe_step_result(result: StepResult) -> StepResult:
    outputs = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in result.outputs.items()
    }
    return replace(result, outputs=outputs)


@phase(name="ingest")
def ingest(ctx: object) -> StepResult:
    return _json_safe_step_result(IngestStep().run(_ctx_from_native(ctx)))


@phase(name="audit")
def audit(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    worker = step_ctx.state.get("_worker", _default_worker)
    return _json_safe_step_result(
        AuditStep(_worker=worker, _pipeline_name="folder-audit").run(step_ctx)
    )


@phase(name="emit")
def emit(ctx: object) -> StepResult:
    return _json_safe_step_result(EmitStep().run(_ctx_from_native(ctx)))


@pipeline(name="folder-audit", description="Native linear folder-audit pipeline")
def folder_audit_native(ctx: object) -> Any:
    state = yield ingest(ctx)
    state = yield audit(ctx)
    state = yield emit(ctx)
    return state


def build_native_program():
    return compile_pipeline(folder_audit_native)


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
    """Run the native program end-to-end without opt-in env gating."""
    if artifact_root is None:
        artifact_root = Path(target_dir) / ".arnold" / "folder-audit" / "native"

    initial_state: dict[str, Any] = {
        "target_dir": str(Path(target_dir).resolve()),
        "max_depth": max_depth,
        "mode": mode,
    }
    if profile is not None:
        initial_state["profile"] = profile
    if worker is not None:
        initial_state["_worker"] = worker

    return run_native_pipeline(
        build_native_program(),
        artifact_root=artifact_root,
        initial_state=initial_state,
        max_phases=max_phases,
        resume=resume,
        trace_dir=trace_dir,
    )


__all__ = [
    "audit",
    "build_native_program",
    "emit",
    "folder_audit_native",
    "ingest",
    "run_native",
]
