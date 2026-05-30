"""Tests: Governor attached to Activation at FIRING.

T24 — Governor.charge(envelope) is called as the Activation's first action
after transitioning to RUNNING (FIRING).  BudgetExceeded is surfaced as a
contained per-step failure that honors the existing escalate ladder.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

import pytest

from megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope, make_envelope
from megaplan._pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult
from megaplan.runtime.governor import (
    BudgetExceeded,
    ExceedReason,
    Governor,
    reset_governor,
    set_governor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(name: str, *, next_label: str = "halt"):
    class _Step:
        kind = "produce"
        prompt_key = ""
        slot = ""
        produces: tuple = ()
        consumes: tuple = ()

        def run(self, ctx: StepContext) -> StepResult:
            return StepResult(next=next_label, state_patch={}, outputs={})

    s = _Step()
    s.__class__.__name__ = name
    return s


def _single_stage_pipeline(step) -> Pipeline:
    stage = Stage(name="s1", step=step, edges=[Edge(label="halt", target="halt")])
    return Pipeline(entry="s1", stages={"s1": stage})


def _ctx(tmp_path: Path, envelope: RunEnvelope = EMPTY_ENVELOPE) -> StepContext:
    return StepContext(
        plan_dir=tmp_path,
        state={},
        profile={},
        mode="run",
        inputs={},
        envelope=envelope,
    )


def _run(pipeline, ctx, tmp_path):
    from megaplan._pipeline.executor import run_pipeline
    return run_pipeline(pipeline, ctx, artifact_root=tmp_path / "artifacts")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_governor_step_succeeds(tmp_path):
    """With no governor attached, pipeline runs normally."""
    pipeline = _single_stage_pipeline(_make_step("s1"))
    ctx = _ctx(tmp_path)
    result = _run(pipeline, ctx, tmp_path)
    assert result["final_stage"] == "s1"


def test_governor_charged_on_firing(tmp_path):
    """Governor.charge is called once per step at FIRING; spent_dollars accumulates."""
    gov = Governor(dollar_cap=100.0)
    token = set_governor(gov)
    try:
        pipeline = _single_stage_pipeline(_make_step("s1"))
        envelope = make_envelope(cost=3.5)
        ctx = _ctx(tmp_path, envelope=envelope)
        _run(pipeline, ctx, tmp_path)
        assert gov.spent_dollars == pytest.approx(3.5)
    finally:
        reset_governor(token)


def test_governor_charged_once_per_step_multi_step(tmp_path):
    """Each step fires one charge; 3 steps with cost=1.0 each → spent=3.0."""
    gov = Governor(dollar_cap=100.0)
    token = set_governor(gov)
    try:
        step1 = _make_step("s1", next_label="s2")
        step2 = _make_step("s2", next_label="s3")
        step3 = _make_step("s3", next_label="halt")
        s1 = Stage(name="s1", step=step1, edges=[Edge(label="s2", target="s2")])
        s2 = Stage(name="s2", step=step2, edges=[Edge(label="s3", target="s3")])
        s3 = Stage(name="s3", step=step3, edges=[Edge(label="halt", target="halt")])
        pipeline = Pipeline(entry="s1", stages={"s1": s1, "s2": s2, "s3": s3})
        envelope = make_envelope(cost=1.0)
        ctx = _ctx(tmp_path, envelope=envelope)
        _run(pipeline, ctx, tmp_path)
        assert gov.spent_dollars == pytest.approx(3.0)
    finally:
        reset_governor(token)


def test_budget_exceeded_raises_and_activation_fails(tmp_path):
    """BudgetExceeded at FIRING is a contained per-step failure: raises BudgetExceeded."""
    gov = Governor(dollar_cap=0.0)  # any cost exceeds cap
    token = set_governor(gov)
    try:
        pipeline = _single_stage_pipeline(_make_step("s1"))
        envelope = make_envelope(cost=1.0)
        ctx = _ctx(tmp_path, envelope=envelope)
        with pytest.raises(BudgetExceeded):
            _run(pipeline, ctx, tmp_path)
    finally:
        reset_governor(token)


def test_budget_exceeded_reason_is_dollar_cap(tmp_path):
    """BudgetExceeded raised at FIRING carries ExceedReason.DOLLAR_CAP."""
    gov = Governor(dollar_cap=0.5)
    token = set_governor(gov)
    try:
        pipeline = _single_stage_pipeline(_make_step("s1"))
        envelope = make_envelope(cost=1.0)
        ctx = _ctx(tmp_path, envelope=envelope)
        with pytest.raises(BudgetExceeded) as exc_info:
            _run(pipeline, ctx, tmp_path)
        assert exc_info.value.reason is ExceedReason.DOLLAR_CAP
    finally:
        reset_governor(token)


def test_budget_exceeded_step_not_executed(tmp_path):
    """When BudgetExceeded fires at FIRING, the step body never runs."""
    executed = []

    class _Sentinel:
        kind = "produce"
        prompt_key = ""
        slot = ""
        produces: tuple = ()
        consumes: tuple = ()

        def run(self, ctx):
            executed.append(True)
            return StepResult(next="halt", state_patch={}, outputs={})

    gov = Governor(dollar_cap=0.0)
    token = set_governor(gov)
    try:
        pipeline = _single_stage_pipeline(_Sentinel())
        ctx = _ctx(tmp_path, envelope=make_envelope(cost=1.0))
        with pytest.raises(BudgetExceeded):
            _run(pipeline, ctx, tmp_path)
        assert executed == [], "Step body must not run after BudgetExceeded at FIRING"
    finally:
        reset_governor(token)


def test_budget_exceeded_activation_failed_event_emitted(tmp_path, monkeypatch):
    """BudgetExceeded at FIRING triggers ACTIVATION_TRANSITIONED to FAILED."""
    os.environ["ACTIVATION_EMIT"] = "1"
    try:
        from megaplan.observability.events import EventKind
        emitted = []

        import megaplan._pipeline.executor as _exec_mod
        original_emit = None

        import megaplan.observability.events as _ev_mod
        original_emit = _ev_mod.emit

        def _capture_emit(kind, plan_dir, *, payload=None):
            emitted.append((kind, payload))

        monkeypatch.setattr(_ev_mod, "emit", _capture_emit)

        gov = Governor(dollar_cap=0.0)
        token = set_governor(gov)
        try:
            pipeline = _single_stage_pipeline(_make_step("s1"))
            ctx = _ctx(tmp_path, envelope=make_envelope(cost=1.0))
            with pytest.raises(BudgetExceeded):
                _run(pipeline, ctx, tmp_path)
        finally:
            reset_governor(token)

        lifecycle_events = [p for (k, p) in emitted if p and p.get("to") == "failed"]
        assert lifecycle_events, "Expected FAILED activation event after BudgetExceeded"
    finally:
        del os.environ["ACTIVATION_EMIT"]


def test_no_governor_zero_cost_envelope(tmp_path):
    """EMPTY_ENVELOPE with no governor: no charge, no error."""
    pipeline = _single_stage_pipeline(_make_step("s1"))
    ctx = _ctx(tmp_path, envelope=EMPTY_ENVELOPE)
    result = _run(pipeline, ctx, tmp_path)
    assert result["final_stage"] == "s1"


def test_governor_with_no_cost_envelope_succeeds(tmp_path):
    """Governor with dollar_cap=1.0 and zero-cost envelope: step succeeds, no charge."""
    gov = Governor(dollar_cap=1.0)
    token = set_governor(gov)
    try:
        pipeline = _single_stage_pipeline(_make_step("s1"))
        ctx = _ctx(tmp_path, envelope=EMPTY_ENVELOPE)
        _run(pipeline, ctx, tmp_path)
        assert gov.spent_dollars == pytest.approx(0.0)
    finally:
        reset_governor(token)


def test_budget_exceeded_is_not_swallowed(tmp_path):
    """BudgetExceeded propagates out of run_pipeline (escalate ladder can catch it)."""
    gov = Governor(dollar_cap=0.0)
    token = set_governor(gov)
    try:
        pipeline = _single_stage_pipeline(_make_step("s1"))
        ctx = _ctx(tmp_path, envelope=make_envelope(cost=0.01))
        caught = None
        try:
            _run(pipeline, ctx, tmp_path)
        except BudgetExceeded as e:
            caught = e
        assert caught is not None, "BudgetExceeded must propagate, not be swallowed"
    finally:
        reset_governor(token)
