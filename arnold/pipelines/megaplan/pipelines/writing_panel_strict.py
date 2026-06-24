"""Python composition of the ``writing-panel-strict`` pipeline.

Sibling-file replacement for the legacy
``megaplan/pipelines/writing-panel-strict/pipeline.yaml``. The hyphenated
directory (``megaplan/pipelines/writing-panel-strict/``) stays on disk —
prompts / profiles / ``SKILL.md`` are referenced from it; only the YAML
manifest is replaced.

Topology (identical to the legacy YAML — locks done-criterion #8):

* ``panel_review`` — three reviewers (pessimist, optimist,
  structuralist) running in parallel via the builder's
  :class:`ParallelStage` fan-out.
* ``synth`` — single agent fanning in the three reviewer artifacts
  via ``panel_review.*``.
* ``revise`` — single agent producing a revised draft from the
  original draft + the synthesised critique.
* ``human_decide`` — :class:`HumanDecisionStep` with ``options=['continue',
  'stop']``. ``continue`` loops back to ``panel_review`` (re-entry into
  the ParallelStage); ``stop`` exits via the executor's ``"halt"``
  terminator (the Python-composition equivalent of the YAML compiler's
  ``to: done`` → ``target="halt"`` translation at
  ``compiler.py:245``). The brief's ``['ship','continue','escalate']``
  sketch is rejected — done-criterion #8 requires identical behaviour
  to the YAML's ``choices: [continue, stop]``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from arnold.pipeline.native import (
    compile_pipeline,
    decision,
    phase,
    pipeline,
)
from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE
from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep
from arnold.pipelines.megaplan._pipeline.steps.panel import PanelReviewerStep
from arnold.pipelines.megaplan._pipeline.types import Pipeline, StepContext, StepResult


_PIPELINE_DIR: Path = Path(__file__).parent / "writing-panel-strict"
_PROMPTS: Path = _PIPELINE_DIR / "prompts"


# ── Module-level metadata surfaced via PipelineRegistry (T9) ──────────

name: str = "writing-panel-strict"
description: str = (
    "Adversarial review of prose drafts by N reviewers, then revise. "
    "Not for code."
)
default_profile: str = "@writing-panel-strict:standard"
supported_modes: tuple[str, ...] = ("polish", "restructure", "provoke")
recommended_profiles: tuple[str, ...] = (
    "@writing-panel-strict:premium",
    "@writing-panel-strict:standard",
    "@writing-panel-strict:cheap",
)
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("writing", "critique", "revise")

_PANEL_REVIEWERS: tuple[tuple[str, str], ...] = (
    ("pessimist", str(_PROMPTS / "pessimist.md")),
    ("optimist", str(_PROMPTS / "optimist.md")),
    ("structuralist", str(_PROMPTS / "structuralist.md")),
)
_PANEL_REVIEWER_IDS: tuple[str, ...] = tuple(
    reviewer_id for reviewer_id, _prompt in _PANEL_REVIEWERS
)
_EMPTY_PANEL_ORDER: dict[str, tuple[str, ...]] = {}
_PANEL_REVIEWER_ORDER: dict[str, tuple[str, ...]] = {
    "panel_review": _PANEL_REVIEWER_IDS,
}
_SYNTH_PROMPT = str(_PROMPTS / "synth.md")
_REVISE_PROMPT = str(_PROMPTS / "revise.md")
_HUMAN_CHOICES: tuple[str, ...] = ("continue", "stop")
_HUMAN_VOCABULARY: frozenset[str] = frozenset(_HUMAN_CHOICES)


def _copy_panel_order(
    order: Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    return {panel: list(reviewers) for panel, reviewers in order.items()}


def _dict_to_step_context(ctx: object) -> StepContext:
    """Adapt native-runtime contexts to Megaplan's StepContext."""

    if isinstance(ctx, StepContext):
        return ctx
    if hasattr(ctx, "plan_dir") and hasattr(ctx, "state") and hasattr(ctx, "profile"):
        return ctx  # type: ignore[return-value]

    if isinstance(ctx, dict):
        raw_state = ctx.get("state") or {}
        raw_inputs = ctx.get("inputs") or {}
        root = ctx.get("artifact_root") or ctx.get("plan_dir") or "."
        envelope = ctx.get("envelope") or EMPTY_ENVELOPE
        mode = str(ctx.get("mode") or "polish")
        profile = ctx.get("profile") or {}
    else:
        raw_state = getattr(ctx, "state", {}) or {}
        raw_inputs = getattr(ctx, "inputs", {}) or {}
        root = getattr(ctx, "artifact_root", None) or getattr(ctx, "plan_dir", ".")
        envelope = getattr(ctx, "envelope", None) or EMPTY_ENVELOPE
        mode = str(getattr(ctx, "mode", "polish") or "polish")
        profile = getattr(ctx, "profile", {}) or {}

    state = dict(raw_state) if isinstance(raw_state, Mapping) else {}
    inputs: dict[str, Any] = {}
    if isinstance(raw_inputs, Mapping):
        inputs.update(
            {
                str(key): value
                for key, value in raw_inputs.items()
                if not str(key).startswith("_")
            }
        )
    stored_inputs = state.get("_inputs")
    if isinstance(stored_inputs, Mapping):
        inputs.update({str(key): value for key, value in stored_inputs.items()})

    return StepContext(
        plan_dir=Path(root),
        state=state if isinstance(raw_state, Mapping) else raw_state,
        profile=profile,
        mode=mode,
        inputs={
            key: Path(value) if isinstance(value, str) else value
            for key, value in inputs.items()
        },
        envelope=envelope,
    )


def _make_panel_reviewer_step(
    reviewer_id: str,
    prompt_ref: str,
) -> PanelReviewerStep:
    return PanelReviewerStep(
        name=f"panel_review.{reviewer_id}",
        kind="produce",
        prompt_key=None,
        slot=None,
        _prompt_ref=prompt_ref,
        _pipeline_dir=_PIPELINE_DIR,
        _pipeline_name=name,
        _input_refs=["draft"],
        _reviewer_id=reviewer_id,
        _panel_reviewer_order=_copy_panel_order(_EMPTY_PANEL_ORDER),
        _mode="",
    )


def _make_agent_step(
    stage_name: str,
    prompt_ref: str,
    inputs: Sequence[str],
    panel_reviewer_order: Mapping[str, Sequence[str]],
) -> AgentStep:
    return AgentStep(
        name=stage_name,
        kind="produce",
        prompt_key=None,
        slot=None,
        _prompt_ref=prompt_ref,
        _pipeline_dir=_PIPELINE_DIR,
        _pipeline_name=name,
        _input_refs=list(inputs),
        _produces="markdown",
        _panel_reviewer_order=_copy_panel_order(panel_reviewer_order),
        _mode="",
    )


def _json_safe_step_result(result: StepResult) -> StepResult:
    return replace(
        result,
        outputs={key: str(value) for key, value in result.outputs.items()},
    )


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


@pipeline("writing-panel-strict")
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


def _build_graph_pipeline() -> Pipeline:
    """Return the canonical graph ``writing-panel-strict`` Pipeline."""

    return (
        Pipeline.builder(
            "writing-panel-strict",
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
        )
        .build()
    )


def build_pipeline() -> Pipeline:
    """Return the graph-default pipeline with an opt-in native bundle."""

    graph = _build_graph_pipeline()
    return replace(
        graph,
        resource_bundles=tuple(graph.resource_bundles) + (_native_bundle(),),
    )


__all__ = [
    "build_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
    "writing_panel_strict_native",
]
