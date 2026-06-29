"""Runtime-agnostic helpers for ``writing-panel-strict``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from arnold.runtime.envelope import EMPTY_ENVELOPE
from arnold_pipelines.megaplan.steps.agent import AgentStep
from arnold_pipelines.megaplan.steps.panel import PanelReviewerStep
from arnold_pipelines.megaplan.step_types import StepContext, StepResult


_PIPELINE_NAME = "writing-panel-strict"
_PIPELINE_DIR: Path = Path(__file__).parent
_PROMPTS: Path = _PIPELINE_DIR / "prompts"

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
        _pipeline_name=_PIPELINE_NAME,
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
        _pipeline_name=_PIPELINE_NAME,
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
