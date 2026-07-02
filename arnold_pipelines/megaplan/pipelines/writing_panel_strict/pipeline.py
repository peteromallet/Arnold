"""Native declaration and builder for ``writing-panel-strict``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.pipeline import Pipeline as ArnoldPipeline
from arnold.pipeline.native import compile_pipeline, decision, phase, pipeline
from arnold.pipeline.types import Edge, ParallelStage, Stage
from arnold_pipelines.megaplan.step_types import StepResult

from .steps import (
    _HUMAN_CHOICES,
    _HUMAN_VOCABULARY,
    _PANEL_REVIEWERS,
    _PANEL_REVIEWER_ORDER,
    _PIPELINE_NAME,
    _REVISE_PROMPT,
    _SYNTH_PROMPT,
    _dict_to_step_context,
    _json_safe_step_result,
    _make_agent_step,
    _make_human_gate_step,
    _make_panel_reviewer_step,
)


_PIPELINE_DIR: Path = Path(__file__).parent

name: str = "writing-panel-strict"
description: str = (
    "Adversarial review of prose drafts by N reviewers, then revise. "
    "Not for code."
)
default_profile: str = "@writing-panel-strict:standard"
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = (
    "@writing-panel-strict:premium",
    "@writing-panel-strict:standard",
    "@writing-panel-strict:cheap",
)
driver: tuple[str, str] = ("native", "panel")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("writing", "critique", "revise")


@phase(name="panel_review")
def _native_panel_review(ctx: object) -> StepResult:
    step_ctx = _dict_to_step_context(ctx)
    outputs: dict[str, str] = {}
    for reviewer_id, prompt_ref in _PANEL_REVIEWERS:
        result = _make_panel_reviewer_step(reviewer_id, prompt_ref).run(step_ctx)
        for label, path in result.outputs.items():
            outputs[f"{reviewer_id}.{label}"] = str(path)
    return StepResult(outputs=outputs, next="next")


@phase(name="synth")
def _native_synth(ctx: object) -> StepResult:
    result = _make_agent_step(
        "synth",
        _SYNTH_PROMPT,
        ("panel_review.*",),
        _PANEL_REVIEWER_ORDER,
    ).run(_dict_to_step_context(ctx))
    return _json_safe_step_result(result)


@phase(name="revise")
def _native_revise(ctx: object) -> StepResult:
    result = _make_agent_step(
        "revise",
        _REVISE_PROMPT,
        ("draft", "synth"),
        _PANEL_REVIEWER_ORDER,
    ).run(_dict_to_step_context(ctx))
    return _json_safe_step_result(result)


@decision(
    name="human_decide",
    vocabulary=_HUMAN_VOCABULARY,
    human_gate=True,
    artifact_stage="revise",
    choices=_HUMAN_CHOICES,
)
def _native_human_decide(ctx: object) -> str:
    del ctx
    return "stop"


@pipeline(_PIPELINE_NAME)
def writing_panel_strict_native(ctx: object) -> Any:
    state = yield _native_panel_review(ctx)
    state = yield _native_synth(ctx)
    state = yield _native_revise(ctx)
    while _native_human_decide(ctx) == "continue":
        state = yield _native_panel_review(ctx)
        state = yield _native_synth(ctx)
        state = yield _native_revise(ctx)
    return state


def _native_bundle() -> Any:
    return compile_pipeline(writing_panel_strict_native)


def _build_graph_pipeline(
    *,
    name: str,
    description: str,
    default_profile: str,
    supported_modes: tuple[str, ...],
) -> ArnoldPipeline:
    """Return the canonical explicit graph shell for ``writing-panel-strict``."""

    del name, description, default_profile, supported_modes

    reviewers = tuple(
        (
            reviewer_id,
            _make_panel_reviewer_step(reviewer_id, prompt_ref),
        )
        for reviewer_id, prompt_ref in _PANEL_REVIEWERS
    )

    def join(results: dict[str, StepResult]) -> StepResult:
        outputs = {
            f"{reviewer_id}.{label}": path
            for reviewer_id, result in results.items()
            for label, path in result.outputs.items()
        }
        return StepResult(outputs=outputs, next="next")

    stages = {
        "panel_review": ParallelStage(
            name="panel_review",
            steps=reviewers,
            join=join,
            edges=(Edge("next", "synth"),),
            max_workers=None,
        ),
        "synth": Stage(
            name="synth",
            step=_make_agent_step(
                "synth",
                _SYNTH_PROMPT,
                ("panel_review.*",),
                _PANEL_REVIEWER_ORDER,
            ),
            edges=(Edge("done", "revise"),),
        ),
        "revise": Stage(
            name="revise",
            step=_make_agent_step(
                "revise",
                _REVISE_PROMPT,
                ("draft", "synth"),
                _PANEL_REVIEWER_ORDER,
            ),
            edges=(Edge("done", "human_decide"),),
        ),
        "human_decide": Stage(
            name="human_decide",
            step=_make_human_gate_step("human_decide", "revise"),
            edges=(Edge("continue", "panel_review"), Edge("stop", "halt"), Edge("done", "halt")),
        ),
    }
    return ArnoldPipeline(stages=stages, entry="panel_review")


def build_pipeline() -> ArnoldPipeline:
    """Return the native-backed ``writing-panel-strict`` pipeline."""

    graph = _build_graph_pipeline(
        name=name,
        description=description,
        default_profile=default_profile,
        supported_modes=supported_modes,
    )
    return ArnoldPipeline(
        stages=graph.stages,
        entry=graph.entry,
        binding_map=getattr(graph, "binding_map", None),
        resource_bundles=(),
        native_program=_native_bundle(),
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
    "writing_panel_strict_native",
]
