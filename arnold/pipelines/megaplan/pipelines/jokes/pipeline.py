"""Native-backed implementation for the first-class ``jokes`` pipeline."""

from __future__ import annotations

from dataclasses import replace
from functools import wraps
from typing import Any, Callable

from arnold.pipeline import Edge, Pipeline, Stage, StepContext, StepResult
from arnold.pipeline.native import (
    NativeProgram,
    compile_pipeline,
    phase,
    pipeline,
)
from arnold.pipelines.megaplan.pipelines.jokes.steps import JokeStep


name: str = "jokes"
description: str = (
    "Joke pipeline: drafts a joke, tightens the beat, and emits the final artifact "
    "through a direct native program."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native", "joke")
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("creative", "joke")

STAGE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("draft", "draft_joke", "tighten"),
    ("tighten", "tighten_joke", "emit"),
    ("emit", "emit_joke", "halt"),
)


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


@phase(name="draft")
def _native_draft(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    return JokeStep(
        name="draft",
        prompt_key="draft_joke",
        topic="",
        next_label="tighten",
    ).run(step_ctx)


@phase(name="tighten")
def _native_tighten(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    return JokeStep(
        name="tighten",
        prompt_key="tighten_joke",
        topic="",
        next_label="emit",
    ).run(step_ctx)


@phase(name="emit")
def _native_emit(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    return JokeStep(
        name="emit",
        prompt_key="emit_joke",
        topic="",
        next_label="halt",
    ).run(step_ctx)


@pipeline("jokes")
def jokes_native(ctx: object) -> Any:
    state = yield _native_draft(ctx)
    state = yield _native_tighten(ctx)
    state = yield _native_emit(ctx)
    return state


def _seed_context_topic(ctx: object, topic: str) -> object:
    if not isinstance(ctx, dict):
        return ctx
    seeded = dict(ctx)
    state = dict(seeded.get("state") or {})
    state.setdefault("joke_topic", topic)
    seeded["state"] = state
    inputs = dict(seeded.get("inputs") or {})
    inputs.setdefault("joke_topic", state["joke_topic"])
    seeded["inputs"] = inputs
    return seeded


def _topic_seeded_func(
    func: Callable[[object], Any],
    topic: str,
) -> Callable[[object], Any]:
    @wraps(func)
    def _wrapped(ctx: object) -> Any:
        return func(_seed_context_topic(ctx, topic))

    return _wrapped


def _native_program(topic: str = "software release notes") -> NativeProgram:
    program = compile_pipeline(jokes_native)
    phase_funcs = {
        instr.name: _topic_seeded_func(instr.func, topic)
        for instr in program.instructions
        if instr.op == "phase" and instr.func is not None
    }
    instructions = tuple(
        replace(instr, func=phase_funcs[instr.name])
        if instr.name in phase_funcs
        else instr
        for instr in program.instructions
    )
    phases = tuple(
        replace(phase_ir, func=phase_funcs[phase_ir.name])
        if phase_ir.name in phase_funcs
        else phase_ir
        for phase_ir in program.phases
    )
    return replace(program, instructions=instructions, phases=phases)


def _stage(
    name: str,
    *,
    prompt_key: str,
    topic: str,
    next_label: str,
) -> Stage:
    edges = () if next_label == "halt" else (
        Edge(label=next_label, target=next_label),
    )
    return Stage(
        name=name,
        step=JokeStep(
            name=name,
            prompt_key=prompt_key,
            topic=topic,
            next_label=next_label,
        ),
        edges=edges,
    )


def _build_graph_pipeline(topic: str = "software release notes") -> Pipeline:
    """Private transitional graph shell for forced-graph fallback and inspection."""
    stages = {
        stage_name: _stage(
            stage_name,
            prompt_key=prompt_key,
            topic=topic,
            next_label=next_label,
        )
        for stage_name, prompt_key, next_label in STAGE_SPECS
    }
    return Pipeline(stages=stages, entry="draft")


def build_pipeline(topic: str = "software release notes") -> Pipeline:
    """Return the canonical native-backed ``jokes`` :class:`Pipeline`."""
    graph = _build_graph_pipeline(topic=topic)
    return replace(
        graph,
        native_program=_native_program(topic=topic),
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
