"""Deliberation example pipeline: draft → critique → human_review → revise.

A four-stage linear pipeline demonstrating the Arnold native pipeline authoring
surface with a reusable human-review gate from
:mod:`arnold.pipelines.evidence_pack.steps`.

The native topology::

    draft ──→ critique ──→ human_review ──[emit]──→ revise ──→ halt
                                │
                                └──[failed]──→ halt

The *draft*, *critique*, and *revise* phases are simple native ``@phase``
wrappers.  The *human_review* phase uses
:class:`~arnold.pipelines.evidence_pack.steps.HumanReviewStep`, which
returns a SUSPENDED contract status on first call (triggering the native
hooks to suspend) and routes to ``emit`` or ``failed`` on resume.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline import StepContext, StepResult
from arnold.pipeline.native import compile_pipeline, decision, phase, pipeline
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.types import (
    ContractStatus,
    Edge,
    Pipeline,
    Stage,
)

from arnold.pipelines.evidence_pack.steps import (
    EvidencePackStep,
    HumanReviewStep,
)


# ── Native phase helpers ──────────────────────────────────────────────────


def _ctx_from_native(raw_ctx: object) -> StepContext:
    """Build a StepContext from a native runtime context (dict or object)."""
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
    """Make a StepResult JSON-safe by converting Path values and clearing non-suspended contract results."""
    outputs = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in result.outputs.items()
    }
    contract_result = result.contract_result
    if contract_result is not None and contract_result.status is not ContractStatus.SUSPENDED:
        contract_result = None
    return replace(result, outputs=outputs, contract_result=contract_result)


# ── Native phases ─────────────────────────────────────────────────────────


@phase(name="draft")
def draft(ctx: object) -> StepResult:
    """Produce an initial draft artifact.

    In a real pipeline this would invoke a model.  Here it produces a
    deterministic placeholder so the example runs without credentials.
    """
    step_ctx = _ctx_from_native(ctx)
    root = Path(step_ctx.artifact_root)
    draft_path = root / "draft.json"
    draft_path.write_text('{"status": "draft_complete"}', encoding="utf-8")
    return StepResult(
        outputs={"draft": str(draft_path)},
        next="critique",
    )


@phase(name="critique")
def critique(ctx: object) -> StepResult:
    """Critique the draft output.

    Reads the draft artifact and produces a critique artifact.
    """
    step_ctx = _ctx_from_native(ctx)
    root = Path(step_ctx.artifact_root)
    critique_path = root / "critique.json"
    critique_path.write_text('{"status": "critique_complete"}', encoding="utf-8")
    return StepResult(
        outputs={"critique": str(critique_path)},
        next="human_review",
    )


@phase(name="human_review")
def human_review(ctx: object) -> StepResult:
    """Human-review gate using the evidence-pack HumanReviewStep.

    On first call the step returns SUSPENDED.  The native runtime's hooks
    detect this and suspend execution.  On resume the caller supplies
    ``human_input={'approved': bool}`` and the step routes accordingly.
    """
    step_ctx = _ctx_from_native(ctx)
    inputs = dict(step_ctx.inputs)
    inputs.pop("human_input", None)
    result = HumanReviewStep().run(replace(step_ctx, inputs=inputs))
    if (
        result.contract_result is not None
        and result.contract_result.status is ContractStatus.SUSPENDED
    ):
        return replace(
            _json_safe_step_result(result),
            next="awaiting_decision",
            contract_result=None,
        )
    return _json_safe_step_result(result)


@phase(name="revise")
def revise(ctx: object) -> StepResult:
    """Revise the output after human review approval.

    Produces a final revision artifact.
    """
    step_ctx = _ctx_from_native(ctx)
    root = Path(step_ctx.artifact_root)
    revise_path = root / "revise.json"
    revise_path.write_text('{"status": "revision_complete"}', encoding="utf-8")
    return StepResult(
        outputs={"revise": str(revise_path)},
        next="halt",
    )


# ── Native decisions ──────────────────────────────────────────────────────


@decision(
    name="human_review_decision",
    vocabulary=frozenset({"emit", "failed"}),
    human_gate=True,
    artifact_stage="human_review",
    choices=("emit", "failed"),
)
def human_review_decision(ctx: object) -> str:
    """Route after human_review: emit→revise, failed→halt."""
    inputs = _ctx_from_native(ctx).inputs
    human_input = inputs.get("human_input")
    if isinstance(human_input, Mapping):
        choice = human_input.get("choice")
        if isinstance(choice, str) and choice in {"emit", "failed"}:
            return choice
        approved = human_input.get("approved")
        if isinstance(approved, bool):
            return "emit" if approved else "failed"
    return "failed"


# ── Native pipeline topology ──────────────────────────────────────────────


@pipeline(
    name="deliberation_example",
    description="Native deliberation example: draft → critique → human_review → revise",
)
def deliberation_example_native(ctx: object) -> Any:
    """Compile-time topology for the native deliberation example."""
    state = yield draft(ctx)
    state = yield critique(ctx)
    state = yield human_review(ctx)
    if human_review_decision(ctx) == "emit":
        state = yield revise(ctx)
    return state


def build_native_program() -> NativeProgram:
    """Compile and return the native program for the deliberation example."""
    return compile_pipeline(deliberation_example_native)


# ── Projected shell ───────────────────────────────────────────────────────


def _build_projected_pipeline(name: str = "deliberation-example") -> Pipeline:
    """Build the projected (native-shell) pipeline graph.

    Returns a Pipeline whose stages mirror the deliberation topology::

        draft → critique → human_review → revise
    """
    stages: dict[str, Stage] = {
        "draft": Stage(
            name="draft",
            step=EvidencePackStep(name="draft", next_label="critique"),
            edges=(Edge(label="critique", target="critique"),),
        ),
        "critique": Stage(
            name="critique",
            step=EvidencePackStep(name="critique", next_label="human_review"),
            edges=(Edge(label="human_review", target="human_review"),),
        ),
        "human_review": Stage(
            name="human_review",
            step=EvidencePackStep(name="human_review", next_label="revise"),
            edges=(
                Edge(label="emit", target="revise"),
                Edge(label="failed", target="halt"),
            ),
        ),
        "revise": Stage(
            name="revise",
            step=EvidencePackStep(name="revise", next_label="halt"),
            edges=(),
        ),
    }

    return Pipeline(stages=stages, entry="draft")


def build_pipeline(name: str = "deliberation-example", **_: object) -> Pipeline:
    """Return the canonical native-backed deliberation example pipeline.

    Attaches a compiled native program to the projected shell.  The native
    program encodes the draft→critique→human_review→revise topology with a
    human-gate decision at the human_review phase.
    """
    projected = _build_projected_pipeline(name=name)
    native_prog = build_native_program()
    return Pipeline(
        stages=projected.stages,
        entry=projected.entry,
        native_program=native_prog,
    )


__all__ = [
    "build_native_program",
    "build_pipeline",
    "critique",
    "deliberation_example_native",
    "draft",
    "human_review",
    "human_review_decision",
    "revise",
]
