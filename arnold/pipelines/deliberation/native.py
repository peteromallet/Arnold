"""Native runtime implementation for the deliberation pipeline.

This module provides the phase/decision functions and pipeline generator that
:func:`arnold.pipeline.native.compiler.compile_pipeline` lowers into a
resumable :class:`~arnold.pipeline.native.ir.NativeProgram`.  It reuses the
existing graph stage builders from :mod:`arnold.pipelines.deliberation.steps`
so the native trace stays byte-for-byte aligned with the graph baseline.

Boundary discipline: no ``arnold.pipelines.megaplan`` imports.
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline.native.compiler import compile_pipeline
from arnold.pipeline.native.decorators import decision, phase, pipeline
from arnold.pipeline.resources import PromptSource
from arnold.pipeline.types import StepContext

from arnold.pipelines.deliberation.steps import (
    build_critique_panel_stage,
    build_draft_plan_stage,
    build_final_report_stage,
    build_question_gen_stage,
    build_skeptical_synthesis_stage,
)

_pipeline_name: str = "deliberation"

_bundle_config: dict[str, Any] = {}


def _set_bundle_config(profile: Any, workers: Any, prompts: Any) -> None:
    """Store runtime configuration for the native phase functions.

    Called by :func:`arnold.pipelines.deliberation.pipeline._native_bundle`
    before (and after) compilation so the compiled program can resolve
    workers, prompts, and profile overrides at execution time.
    """
    _bundle_config.clear()
    _bundle_config.update(
        {"profile": profile, "workers": workers, "prompts": prompts}
    )


class _NoopEventSink:
    """Discard events for native synthesis stages that expect a journal."""

    def emit(
        self,
        kind: str,
        *,
        payload: Any = None,
        scope: Any = None,
        phase: Any = None,
        idempotency_key: Any = None,
    ) -> None:
        del kind, payload, scope, phase, idempotency_key


_NOOP_SINK = _NoopEventSink()


def _profile() -> dict[str, Any]:
    cfg = _bundle_config.get("profile")
    return dict(cfg) if isinstance(cfg, dict) else {}


def _workers() -> dict[str, Any]:
    cfg = _bundle_config.get("workers")
    return dict(cfg) if isinstance(cfg, dict) else {}


def _prompts() -> PromptSource | None:
    return _bundle_config.get("prompts")


def _resolve_worker(stage_key: str) -> Any:
    """Resolve a worker for *stage_key* using the active bundle config."""
    profile = _profile()
    workers = _workers()
    entry = profile.get(stage_key)
    if isinstance(entry, str):
        worker = workers.get(entry)
        if worker is not None:
            return worker
        # String is an abstraction-level shorthand; fall through to any worker.
    if workers:
        return next(iter(workers.values()))
    raise ValueError(f"No workers available for {stage_key!r}")


def _step_ctx(
    artifact_root: str,
    state: dict[str, Any],
    inputs: dict[str, Any] | None = None,
) -> StepContext:
    return StepContext(
        artifact_root=artifact_root,
        state=state,
        inputs=inputs or {},
    )


def _artifact_path_from_result(result: Any) -> str:
    cr = getattr(result, "contract_result", None)
    if cr is not None:
        payload = getattr(cr, "payload", None) or {}
        path = payload.get("artifact_path")
        if path is not None:
            return str(path)
    return ""


def _rename_panel_stage(stage: Any, layer_name: str) -> None:
    """Mutate a numeric-named panel stage to use the descriptive layer name."""
    new_name = f"layer_{layer_name}_panel"
    object.__setattr__(stage, "name", new_name)
    renamed: list[Any] = []
    for step in stage.steps:
        step.name = f"{new_name}.{step._reviewer_id}"
        renamed.append(step)
    object.__setattr__(stage, "steps", tuple(renamed))


@phase(name="question_gen")
def question_gen(ctx: dict[str, Any]) -> dict[str, Any]:
    """Generate clarifying questions and suspend at the human gate."""
    from pathlib import Path

    root = Path(ctx.get("artifact_root", "."))
    state = dict(ctx.get("state", {})) if isinstance(ctx.get("state"), dict) else {}
    worker = _resolve_worker("question_gen")
    step = build_question_gen_stage(_prompts(), worker).step
    result = step.run(_step_ctx(str(root), state))
    return {"questions": _artifact_path_from_result(result)}


@decision(
    name="human_gate",
    human_gate=True,
    artifact_stage="question_gen",
    choices=("answers_collected",),
)
def human_gate(ctx: dict[str, Any]) -> str:
    """Human gate: the runtime suspends here and resumes on user input."""
    del ctx
    return "answers_collected"


@phase(name="draft_plan")
def draft_plan(ctx: dict[str, Any]) -> dict[str, Any]:
    """Draft an initial plan from the generated questions and user answers."""
    from pathlib import Path

    root = Path(ctx.get("artifact_root", "."))
    state = dict(ctx.get("state", {})) if isinstance(ctx.get("state"), dict) else {}
    worker = _resolve_worker("draft_plan")
    step = build_draft_plan_stage(_prompts(), worker).step
    inputs = {
        "questions": state.get("questions"),
        "answers": str(root / "answers.json"),
    }
    result = step.run(_step_ctx(str(root), state, inputs))
    return {"plan": _artifact_path_from_result(result)}


def _run_panel(ctx: dict[str, Any], layer_name: str, layer_idx: int) -> dict[str, Any]:
    """Run one critique panel and return aggregated ``panel_reviews``."""
    from pathlib import Path

    root = Path(ctx.get("artifact_root", "."))
    state = dict(ctx.get("state", {})) if isinstance(ctx.get("state"), dict) else {}
    stage_key = f"layer_{layer_name}_panel"
    profile_layer_config = _profile().get(stage_key, layer_name)
    worker = _resolve_worker(stage_key)

    panel_stage = build_critique_panel_stage(
        layer=layer_idx,
        profile_layer_config=profile_layer_config,
        prompt_source=_prompts(),
        worker=worker,
    )
    _rename_panel_stage(panel_stage, layer_name)

    inputs = {"plan": state.get("plan")}
    step_ctx = _step_ctx(str(root), state, inputs)
    results = [step.run(step_ctx) for step in panel_stage.steps]

    outputs: dict[str, Any] = {}
    review_paths: list[str] = []
    for result in results:
        for reviewer_id, path in (getattr(result, "outputs", {}) or {}).items():
            outputs[reviewer_id] = str(path)
            review_paths.append(str(path))

    reviews = [Path(p).read_text(encoding="utf-8") for p in sorted(review_paths)]
    outputs["panel_reviews"] = "\n\n".join(reviews)
    outputs["panel_usage"] = {}
    return outputs


@phase(name="layer_high_panel")
def layer_high_panel(ctx: dict[str, Any]) -> dict[str, Any]:
    return _run_panel(ctx, "high", 0)


@phase(name="layer_high_synth")
def layer_high_synth(ctx: dict[str, Any]) -> dict[str, Any]:
    return _run_synth(ctx, "high", 0)


@phase(name="layer_mid_panel")
def layer_mid_panel(ctx: dict[str, Any]) -> dict[str, Any]:
    return _run_panel(ctx, "mid", 1)


@phase(name="layer_mid_synth")
def layer_mid_synth(ctx: dict[str, Any]) -> dict[str, Any]:
    return _run_synth(ctx, "mid", 1)


@phase(name="layer_low_panel")
def layer_low_panel(ctx: dict[str, Any]) -> dict[str, Any]:
    return _run_panel(ctx, "low", 2)


@phase(name="layer_low_synth")
def layer_low_synth(ctx: dict[str, Any]) -> dict[str, Any]:
    return _run_synth(ctx, "low", 2)


def _run_synth(ctx: dict[str, Any], layer_name: str, layer_idx: int) -> dict[str, Any]:
    """Run skeptical synthesis for *layer* and return the revised plan path."""
    state = dict(ctx.get("state", {})) if isinstance(ctx.get("state"), dict) else {}
    stage_key = f"layer_{layer_name}_synth"
    worker = _resolve_worker(stage_key)

    synth_stage = build_skeptical_synthesis_stage(
        layer=layer_idx,
        next_target="halt",
        prompt_source=_prompts(),
        worker=worker,
        journal=_NOOP_SINK,
    )
    synth_stage.step.name = stage_key

    inputs = {
        "plan": state.get("plan"),
        "panel_reviews": state.get("panel_reviews", ""),
    }
    result = synth_stage.step.run(
        _step_ctx(ctx.get("artifact_root", "."), state, inputs)
    )
    return {"plan": _artifact_path_from_result(result)}


@phase(name="final_report")
def final_report(ctx: dict[str, Any]) -> dict[str, Any]:
    """Emit the final lineage-aware report."""
    state = dict(ctx.get("state", {})) if isinstance(ctx.get("state"), dict) else {}
    worker = _resolve_worker("final_report")
    step = build_final_report_stage(_prompts(), worker).step
    inputs = {"plan": state.get("plan")}
    result = step.run(_step_ctx(ctx.get("artifact_root", "."), state, inputs))
    return {"report": _artifact_path_from_result(result)}


@pipeline(
    name="deliberation",
    description="Layered idea-refinement pipeline with human gate and critique panels",
)
def deliberation_native(ctx: dict[str, Any]) -> dict[str, Any]:
    """Native generator for the deliberation pipeline.

    The runtime lowers this into a sequence of phase instructions with a
    single human-gate decision point after question generation.
    """
    state = yield question_gen(ctx)
    if human_gate(ctx) == "answers_collected":
        state = yield draft_plan(ctx)
        state = yield layer_high_panel(ctx)
        state = yield layer_high_synth(ctx)
        state = yield layer_mid_panel(ctx)
        state = yield layer_mid_synth(ctx)
        state = yield layer_low_panel(ctx)
        state = yield layer_low_synth(ctx)
        state = yield final_report(ctx)
    return state


__all__ = [
    "_set_bundle_config",
    "compile_pipeline",
    "deliberation_native",
]
