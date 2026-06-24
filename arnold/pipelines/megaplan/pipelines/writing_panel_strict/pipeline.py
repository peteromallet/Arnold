"""Native declaration and graph builder for ``writing-panel-strict``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.pipeline.native import compile_pipeline, decision, phase, pipeline
from arnold.pipelines.megaplan._pipeline.types import Pipeline, StepResult

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
)


_PIPELINE_DIR: Path = Path(__file__).parent


@phase(name="panel_review")
def _native_panel_review(ctx: object) -> StepResult:
    from . import _make_panel_reviewer_step

    step_ctx = _dict_to_step_context(ctx)
    outputs: dict[str, str] = {}
    for reviewer_id, prompt_ref in _PANEL_REVIEWERS:
        result = _make_panel_reviewer_step(reviewer_id, prompt_ref).run(step_ctx)
        for label, path in result.outputs.items():
            outputs[f"{reviewer_id}.{label}"] = str(path)
    return StepResult(outputs=outputs, next="next")


@phase(name="synth")
def _native_synth(ctx: object) -> StepResult:
    from . import _make_agent_step

    result = _make_agent_step(
        "synth",
        _SYNTH_PROMPT,
        ("panel_review.*",),
        _PANEL_REVIEWER_ORDER,
    ).run(_dict_to_step_context(ctx))
    return _json_safe_step_result(result)


@phase(name="revise")
def _native_revise(ctx: object) -> StepResult:
    from . import _make_agent_step

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
) -> Pipeline:
    """Return the canonical graph ``writing-panel-strict`` Pipeline."""

    return (
        Pipeline.builder(
            name,
            description=description,
            default_profile=default_profile,
            supported_modes=supported_modes,
            pipeline_dir=_PIPELINE_DIR,
        )
        .input("draft", file=True)
        .panel(
            "panel_review",
            reviewers=_PANEL_REVIEWERS,
            inputs=["draft"],
            merge="none",
        )
        .agent(
            "synth",
            prompt=_SYNTH_PROMPT,
            inputs=["panel_review.*"],
        )
        .agent(
            "revise",
            prompt=_REVISE_PROMPT,
            inputs=["draft", "synth"],
        )
        .human_gate(
            "human_decide",
            artifact="revise",
            options=_HUMAN_CHOICES,
            edges={"continue": "panel_review", "stop": "halt"},
            # Loop guard for static validators. Always False so the gate
            # still suspends/continues based on its decision edges.
            loop_condition=lambda _state: False,
        )
        .build()
    )
