"""Pipeline assembly for the live-supervisor pipeline.

Native bundle (M6): ``@phase`` wrappers delegate to the existing
step classes. The graph builder remains canonical and the compiled
native program is attached as an opt-in resource bundle.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from arnold.pipeline import Edge, Pipeline, Stage
from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.native import compile_pipeline, phase, pipeline
from arnold.pipelines.megaplan.pipelines.live_supervisor.steps import (
    ClassifyStep,
    DiagnoseStep,
    RecheckEmitStep,
    RepairDecisionStep,
)


@phase(name="classify")
def _native_classify(ctx: object) -> Any:
    return ClassifyStep().run(_ctx_from_native(ctx))


@phase(name="diagnose")
def _native_diagnose(ctx: object) -> Any:
    return DiagnoseStep().run(_ctx_from_native(ctx))


@phase(name="repair_decision")
def _native_repair_decision(ctx: object) -> Any:
    return RepairDecisionStep().run(_ctx_from_native(ctx))


@phase(name="recheck_emit")
def _native_recheck_emit(ctx: object) -> Any:
    return RecheckEmitStep().run(_ctx_from_native(ctx))


@pipeline("live-supervisor")
def live_supervisor_native(ctx: object) -> Any:
    state = yield _native_classify(ctx)
    state = yield _native_diagnose(ctx)
    state = yield _native_repair_decision(ctx)
    state = yield _native_recheck_emit(ctx)
    return state


def _native_bundle() -> Any:
    return compile_pipeline(live_supervisor_native)


def _ctx_from_native(raw_ctx: object) -> Any:
    """Adapt the native runtime's dict context to an Arnold StepContext."""
    from arnold.pipeline import StepContext

    if isinstance(raw_ctx, dict):
        return StepContext(
            artifact_root=str(raw_ctx.get("artifact_root", ".")),
            state=raw_ctx.get("state", {}),
        )
    return StepContext(
        artifact_root=str(getattr(raw_ctx, "artifact_root", ".")),
        state=getattr(raw_ctx, "state", {}),
    )


def _build_graph_pipeline(*, native_program: Any | None = None) -> Pipeline:
    """Build the classify→diagnose→repair_decision→recheck_emit pipeline."""
    builder = PipelineBuilder(
        name="live-supervisor",
        description=(
            "Megaplan Live Watchdog Supervisor: classify, diagnose, and decide "
            "safe repair actions for likely-live Megaplan/Arnold runs."
        ),
    )

    builder.add_stage(
        Stage(
            name="classify",
            step=ClassifyStep(),
            edges=(Edge(label="diagnose", target="diagnose"),),
        ),
        emit_label="diagnose",
    )
    builder.add_stage(
        Stage(
            name="diagnose",
            step=DiagnoseStep(),
            edges=(Edge(label="repair_decision", target="repair_decision"),),
        ),
        emit_label="repair_decision",
    )
    builder.add_stage(
        Stage(
            name="repair_decision",
            step=RepairDecisionStep(),
            edges=(Edge(label="recheck_emit", target="recheck_emit"),),
        ),
        emit_label="recheck_emit",
    )
    builder.add_stage(
        Stage(
            name="recheck_emit",
            step=RecheckEmitStep(),
            edges=(Edge(label="halt", target="halt"),),
        ),
    )

    return builder.build(native_program=native_program)


def build_pipeline() -> Pipeline:
    """Return the native-backed ``live-supervisor`` :class:`Pipeline`.

    The graph shell remains available for explicit legacy execution; the
    canonical runtime dispatches through the attached ``native_program``.
    """
    return _build_graph_pipeline(native_program=compile_pipeline(live_supervisor_native))
