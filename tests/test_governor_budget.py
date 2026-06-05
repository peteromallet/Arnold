"""Tests for :mod:`megaplan.runtime.governor` — tree-scoped budget caps."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope, make_envelope
from arnold.pipelines.megaplan._pipeline.pattern_dynamic import dynamic_fanout
from arnold.pipelines.megaplan._pipeline.types import StepContext, StepResult, Step
from arnold.pipelines.megaplan.runtime.governor import (
    BudgetExceeded,
    ExceedReason,
    Governor,
    current_governor,
    reset_governor,
    set_governor,
)


# ---------------------------------------------------------------------------
# Unit: predicate + charge
# ---------------------------------------------------------------------------


def test_would_exceed_recursion_depth():
    gov = Governor(recursion_depth_cap=2)
    env = make_envelope(lineage=("a", "b"))
    assert gov.would_exceed(env) is ExceedReason.RECURSION_DEPTH


def test_would_exceed_dollar_cap():
    gov = Governor(dollar_cap=5.0)
    assert gov.would_exceed(make_envelope(cost=4.0)) is None
    gov.charge(make_envelope(cost=4.0))
    assert gov.would_exceed(make_envelope(cost=2.0)) is ExceedReason.DOLLAR_CAP


def test_would_exceed_concurrency_cap():
    gov = Governor(concurrency_cap=1)
    assert gov.would_exceed(EMPTY_ENVELOPE) is None
    gov.charge(EMPTY_ENVELOPE)
    assert gov.would_exceed(EMPTY_ENVELOPE) is ExceedReason.CONCURRENCY_CAP


def test_would_exceed_fanout_cap():
    gov = Governor(fanout_cap=2)
    gov.note_fanout(2)
    assert gov.would_exceed(EMPTY_ENVELOPE) is ExceedReason.FANOUT_CAP


def test_charge_raises_dollar_cap():
    gov = Governor(dollar_cap=1.0)
    with pytest.raises(BudgetExceeded) as exc:
        gov.charge(make_envelope(cost=2.0))
    assert exc.value.reason is ExceedReason.DOLLAR_CAP


def test_charge_raises_concurrency_cap():
    gov = Governor(concurrency_cap=1)
    gov.charge(EMPTY_ENVELOPE)
    with pytest.raises(BudgetExceeded) as exc:
        gov.charge(EMPTY_ENVELOPE)
    assert exc.value.reason is ExceedReason.CONCURRENCY_CAP


def test_charge_no_caps_is_noop():
    gov = Governor()
    for _ in range(50):
        gov.charge(make_envelope(cost=1.0))
    assert gov.spent_dollars == 50.0


# ---------------------------------------------------------------------------
# Tree-scoped attach
# ---------------------------------------------------------------------------


def test_current_governor_default_none():
    assert current_governor() is None


def test_set_and_reset_governor():
    gov = Governor()
    token = set_governor(gov)
    try:
        assert current_governor() is gov
    finally:
        reset_governor(token)
    assert current_governor() is None


# ---------------------------------------------------------------------------
# KeyPool.acquire hook
# ---------------------------------------------------------------------------


def test_key_pool_acquire_charges_governor(monkeypatch):
    from arnold.pipelines.megaplan._pipeline.envelope import _envelope_ctx
    from arnold.pipelines.megaplan.runtime.key_pool import KeyEntry, KeyPool

    pool = KeyPool()
    pool._entries["deepseek"] = [KeyEntry(key="sk-test")]
    # Prevent reload from clobbering injected key.
    pool._next_reload = float("inf")

    gov = Governor(dollar_cap=10.0)
    gov_token = set_governor(gov)
    env_token = _envelope_ctx.set(make_envelope(cost=3.0))
    try:
        key = pool.acquire("deepseek")
        assert key == "sk-test"
        assert gov.spent_dollars == 3.0
    finally:
        _envelope_ctx.reset(env_token)
        reset_governor(gov_token)


def test_key_pool_acquire_raises_on_cap(monkeypatch):
    from arnold.pipelines.megaplan._pipeline.envelope import _envelope_ctx
    from arnold.pipelines.megaplan.runtime.key_pool import KeyEntry, KeyPool

    pool = KeyPool()
    pool._entries["deepseek"] = [KeyEntry(key="sk-test")]
    pool._next_reload = float("inf")

    gov = Governor(dollar_cap=1.0)
    gov_token = set_governor(gov)
    env_token = _envelope_ctx.set(make_envelope(cost=5.0))
    try:
        with pytest.raises(BudgetExceeded) as exc:
            pool.acquire("deepseek")
        assert exc.value.reason is ExceedReason.DOLLAR_CAP
    finally:
        _envelope_ctx.reset(env_token)
        reset_governor(gov_token)


# ---------------------------------------------------------------------------
# Fan-out hook + recursive blow-up
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ConstStep(Step):
    name: str = "noop"
    kind: str = "noop"
    prompt_key: str = ""
    slot: str = ""
    produces: tuple = ()
    consumes: tuple = ()
    payload: Any = None

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(state_patch={"result": self.payload})


def _make_specs(values):
    @dataclass(frozen=True)
    class _Gen(Step):
        name: str = "gen"
        kind: str = "gen"
        prompt_key: str = ""
        slot: str = ""
        produces: tuple = ()
        consumes: tuple = ()

        def run(self, ctx: StepContext) -> StepResult:
            return StepResult(state_patch={"specs": list(values)})

    return _Gen()


def _join_first(results, ctx):
    return results[0] if results else StepResult()


def test_fanout_raises_when_fanout_cap_exceeded():
    gen = _make_specs([{"id": 1}, {"id": 2}, {"id": 3}])
    base = _ConstStep(payload="ok")
    step = dynamic_fanout(gen, base, _join_first, name="fanout")

    ctx = StepContext(plan_dir=Path("/tmp"), state={}, profile=None, mode="run", inputs={}, envelope=EMPTY_ENVELOPE)
    gov = Governor(fanout_cap=2)
    token = set_governor(gov)
    try:
        with pytest.raises(BudgetExceeded) as exc:
            step.run(ctx)
        assert exc.value.reason is ExceedReason.FANOUT_CAP
    finally:
        reset_governor(token)


def test_fanout_raises_when_concurrency_cap_exceeded():
    gen = _make_specs([{"id": 1}, {"id": 2}])
    base = _ConstStep(payload="ok")
    step = dynamic_fanout(gen, base, _join_first, name="fanout")

    ctx = StepContext(plan_dir=Path("/tmp"), state={}, profile=None, mode="run", inputs={}, envelope=EMPTY_ENVELOPE)
    gov = Governor(concurrency_cap=1)
    gov.charge(EMPTY_ENVELOPE)  # saturate concurrency
    token = set_governor(gov)
    try:
        with pytest.raises(BudgetExceeded) as exc:
            step.run(ctx)
        assert exc.value.reason is ExceedReason.CONCURRENCY_CAP
    finally:
        reset_governor(token)


def test_fanout_raises_when_recursion_depth_exceeded():
    gen = _make_specs([{"id": 1}])
    base = _ConstStep(payload="ok")
    step = dynamic_fanout(gen, base, _join_first, name="fanout")

    env = make_envelope(lineage=("a", "b", "c"))
    ctx = StepContext(plan_dir=Path("/tmp"), state={}, profile=None, mode="run", inputs={}, envelope=env)
    gov = Governor(recursion_depth_cap=2)
    token = set_governor(gov)
    try:
        with pytest.raises(BudgetExceeded) as exc:
            step.run(ctx)
        assert exc.value.reason is ExceedReason.RECURSION_DEPTH
    finally:
        reset_governor(token)


def test_fanout_succeeds_under_caps():
    gen = _make_specs([{"id": 1}, {"id": 2}])
    base = _ConstStep(payload="ok")
    step = dynamic_fanout(gen, base, _join_first, name="fanout")

    ctx = StepContext(plan_dir=Path("/tmp"), state={}, profile=None, mode="run", inputs={}, envelope=EMPTY_ENVELOPE)
    gov = Governor(fanout_cap=10, concurrency_cap=10, dollar_cap=100.0)
    token = set_governor(gov)
    try:
        result = step.run(ctx)
        assert result is not None
        assert gov.active_fanout == 2
    finally:
        reset_governor(token)


def test_no_governor_means_no_enforcement():
    gen = _make_specs([{"id": i} for i in range(20)])
    base = _ConstStep(payload="ok")
    step = dynamic_fanout(gen, base, _join_first, name="fanout")

    ctx = StepContext(plan_dir=Path("/tmp"), state={}, profile=None, mode="run", inputs={}, envelope=EMPTY_ENVELOPE)
    # No governor attached → fan-out runs even with absurd width.
    result = step.run(ctx)
    assert result is not None


# ---------------------------------------------------------------------------
# SC22: restorable_boundary fires BEFORE BudgetExceeded when both apply
# ---------------------------------------------------------------------------


def test_restorable_boundary_precedes_budget_exceeded():
    """Sense check SC22 — when a fan-out is active AND a Governor cap would
    fire, the ``restorable_boundary`` refusal raises *first* (at __enter__,
    before any body runs).  Pins the ordering invariant documented on both
    ``restorable_boundary`` and ``Governor``.
    """

    from arnold.pipelines.megaplan._core.state import (
        RestorableBoundaryViolation,
        restorable_boundary,
    )
    from arnold.pipelines.megaplan._pipeline.envelope import _fanout_active_ctx

    gov = Governor(dollar_cap=0.001)
    gov_token = set_governor(gov)
    fan_token = _fanout_active_ctx.set(True)
    try:
        # Both conditions would trigger: fan-out active (boundary refuses)
        # AND a tiny dollar cap that any charge would blow.  The boundary
        # raises first because it fires at __enter__ before the body that
        # would call gov.charge.
        with pytest.raises(RestorableBoundaryViolation):
            with restorable_boundary("snapshot_under_test"):
                gov.charge(make_envelope(cost=10.0))  # never reached
        # And independently, charging would indeed raise BudgetExceeded —
        # proving both conditions are live, not vacuously satisfied.
        with pytest.raises(BudgetExceeded):
            gov.charge(make_envelope(cost=10.0))
    finally:
        _fanout_active_ctx.reset(fan_token)
        reset_governor(gov_token)
