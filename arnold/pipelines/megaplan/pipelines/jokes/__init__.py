"""First-class ``jokes`` pipeline.

This package is intentionally small but it is not a wrapper over ``creative``.
It declares: "I'm a graph driver, I need dispatch+emit"; the graph supplies
its own joke content stages and explicit stage wiring.

Native bundle (M6): ``@phase`` wrappers delegate to the existing
:class:`JokeStep` implementations.  The graph builder remains canonical;
the native bundle is attached as a resource bundle and only activated
when the feature-flag plus ``meta.executor == "native"`` is set.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline import Edge, Pipeline, Stage, StepContext, StepResult
from arnold.pipeline.native import (
    compile_pipeline,
    phase,
    pipeline,
)
from arnold.pipelines.megaplan.pipelines.jokes.steps import JokeStep


name: str = "jokes"
description: str = (
    "Joke pipeline: a graph driver that needs dispatch+emit, drafts a joke, "
    "tightens the beat, and emits the final artifact."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "joke")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("creative", "joke")

STAGE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("draft", "draft_joke", "tighten"),
    ("tighten", "tighten_joke", "emit"),
    ("emit", "emit_joke", "halt"),
)

# ── Native phase wrappers ────────────────────────────────────────────

def _ctx_from_native(raw_ctx: object) -> StepContext:
    """Adapt the native runtime's dict context to an Arnold StepContext."""
    if isinstance(raw_ctx, dict):
        return StepContext(
            artifact_root=str(raw_ctx.get("artifact_root", ".")),
            state=raw_ctx.get("state", {}),
        )
    # Already a StepContext or compatible object.
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
        topic="",  # fallback — _joke_state prefers state["joke_topic"]
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


# ── Native pipeline bundle ───────────────────────────────────────────

@pipeline("jokes")
def jokes_native(ctx: object) -> Any:
    state = yield _native_draft(ctx)
    state = yield _native_tighten(ctx)
    state = yield _native_emit(ctx)
    return state


class _JokesNativeAdapter:
    """Adapter that seeds the joke topic into native-runtime state.

    The native program is compiled once at module scope and has no access to
    the per-pipeline ``topic`` argument.  This adapter wraps the program and
    injects ``joke_topic`` into ``initial_state`` before delegating to the
    generic native runtime, so ``build_pipeline(topic=...)`` works for both
    graph and native execution.
    """

    def __init__(self, program: Any, topic: str) -> None:
        self._program = program
        self._topic = topic

    def run_native_pipeline(
        self,
        *,
        artifact_root: Any,
        initial_state: Mapping[str, Any] | None = None,
        resume: bool = False,
        initial_envelope: Any = None,
        program: Any = None,
        schema_registry: Any = None,
        initial_context: Any = None,
        **kwargs: Any,
    ) -> Any:
        from arnold.pipeline.native.runtime import run_native_pipeline

        seeded = dict(initial_state) if initial_state else {}
        seeded.setdefault("joke_topic", self._topic)
        return run_native_pipeline(
            self._program,
            artifact_root=artifact_root,
            initial_state=seeded,
            resume=resume,
            initial_envelope=initial_envelope,
            schema_registry=schema_registry,
            **kwargs,
        )


def _native_bundle(topic: str = "software release notes") -> Any:
    return _JokesNativeAdapter(compile_pipeline(jokes_native), topic)


# ── Graph builder (canonical) ────────────────────────────────────────

def _build_graph_pipeline(topic: str = "software release notes") -> Pipeline:
    """Build the standalone jokes graph.

    Each node dispatches one local joke step; the final node emits a
    durable artifact and halts.
    """

    stages: dict[str, Stage] = {}
    for stage_name, prompt_key, next_label in STAGE_SPECS:
        edges = () if next_label == "halt" else (
            Edge(label=next_label, target=next_label),
        )
        stages[stage_name] = Stage(
            name=stage_name,
            step=JokeStep(
                name=stage_name,
                prompt_key=prompt_key,
                topic=topic,
                next_label=next_label,
            ),
            edges=edges,
        )
    return Pipeline(
        stages=stages,
        entry="draft",
        resource_bundles=(),
    )


def build_pipeline(topic: str = "software release notes") -> Pipeline:
    """Return the native-backed ``jokes`` :class:`Pipeline`.

    The graph shell remains available for explicit legacy execution; the
    canonical runtime dispatches through the attached ``native_program``.
    """
    graph = _build_graph_pipeline(topic=topic)
    return replace(
        graph,
        native_program=_native_bundle(topic=topic),
        resource_bundles=(),
    )


__all__ = [
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
    "jokes_native",
]
