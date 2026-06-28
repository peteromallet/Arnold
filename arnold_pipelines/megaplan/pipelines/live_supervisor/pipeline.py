"""Native-backed implementation for the first-class ``live-supervisor`` pipeline."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from arnold.pipeline import Edge, Pipeline, Stage, StepContext
from arnold.pipeline.native import NativeProgram, compile_pipeline, phase, pipeline
from arnold_pipelines.megaplan.pipelines.live_supervisor.repair_agent import RepairAgent
from arnold_pipelines.megaplan.pipelines.live_supervisor.steps import (
    ClassifyStep,
    DiagnoseStep,
    RecheckEmitStep,
    RepairDecisionStep,
)


name: str = "live-supervisor"
description: str = (
    "Megaplan Live Watchdog Supervisor: classify, diagnose, and decide "
    "safe repair actions for likely-live Megaplan/Arnold runs."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("supervise", "native")
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = (
    "plan_supervision",
    "incident_classification",
    "repair_dispatch",
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


def _ctx_from_native(raw_ctx: object) -> StepContext:
    """Adapt the native runtime's dict context to an Arnold StepContext."""
    if isinstance(raw_ctx, dict):
        return StepContext(
            artifact_root=str(raw_ctx.get("artifact_root", ".")),
            state=raw_ctx.get("state", {}),
        )
    return StepContext(
        artifact_root=str(getattr(raw_ctx, "artifact_root", ".")),
        state=getattr(raw_ctx, "state", {}),
    )


def _repair_decision_func(agent: RepairAgent | None) -> Callable[[object], Any]:
    def _run(ctx: object) -> Any:
        return RepairDecisionStep(agent=agent).run(_ctx_from_native(ctx))

    return _run


def _recheck_emit_func(recheck_after_seconds: float) -> Callable[[object], Any]:
    def _run(ctx: object) -> Any:
        return RecheckEmitStep(recheck_after_seconds=recheck_after_seconds).run(
            _ctx_from_native(ctx)
        )

    return _run


def _native_program(
    *,
    repair_agent: RepairAgent | None = None,
    recheck_after_seconds: float = 300.0,
) -> NativeProgram:
    program = compile_pipeline(live_supervisor_native)
    replacements: dict[str, Callable[[object], Any]] = {
        "repair_decision": _repair_decision_func(repair_agent),
        "recheck_emit": _recheck_emit_func(recheck_after_seconds),
    }
    instructions = tuple(
        replace(instr, func=replacements[instr.name])
        if instr.op == "phase" and instr.name in replacements
        else instr
        for instr in program.instructions
    )
    phases = tuple(
        replace(phase_ir, func=replacements[phase_ir.name])
        if phase_ir.name in replacements
        else phase_ir
        for phase_ir in program.phases
    )
    return replace(program, instructions=instructions, phases=phases)


def _native_bundle(
    *,
    repair_agent: RepairAgent | None = None,
    recheck_after_seconds: float = 300.0,
) -> NativeProgram:
    return _native_program(
        repair_agent=repair_agent,
        recheck_after_seconds=recheck_after_seconds,
    )


def _build_graph_pipeline(
    *,
    repair_agent: RepairAgent | None = None,
    recheck_after_seconds: float = 300.0,
) -> Pipeline:
    """Private transitional graph shell for forced-graph fallback and inspection."""
    stages = {
        "classify": Stage(
            name="classify",
            step=ClassifyStep(),
            edges=(Edge(label="diagnose", target="diagnose"),),
        ),
        "diagnose": Stage(
            name="diagnose",
            step=DiagnoseStep(),
            edges=(Edge(label="repair_decision", target="repair_decision"),),
        ),
        "repair_decision": Stage(
            name="repair_decision",
            step=RepairDecisionStep(agent=repair_agent),
            edges=(Edge(label="recheck_emit", target="recheck_emit"),),
        ),
        "recheck_emit": Stage(
            name="recheck_emit",
            step=RecheckEmitStep(recheck_after_seconds=recheck_after_seconds),
            edges=(),
        ),
    }
    return Pipeline(stages=stages, entry="classify")


def build_pipeline(
    *,
    repair_agent: RepairAgent | None = None,
    recheck_after_seconds: float = 300.0,
) -> Pipeline:
    """Return the canonical native-backed ``live-supervisor`` :class:`Pipeline`."""
    graph = _build_graph_pipeline(
        repair_agent=repair_agent,
        recheck_after_seconds=recheck_after_seconds,
    )
    return replace(
        graph,
        native_program=_native_program(
            repair_agent=repair_agent,
            recheck_after_seconds=recheck_after_seconds,
        ),
        resource_bundles=(),
    )


__all__ = [
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "recommended_profiles",
    "supported_modes",
]
