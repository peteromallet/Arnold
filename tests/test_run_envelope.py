"""Tests for RunEnvelope semilattice + JSON round-trip."""
from __future__ import annotations

import json

import pytest

from megaplan._pipeline.envelope import (
    EMPTY_ENVELOPE,
    RunEnvelope,
    make_envelope,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def e(**kw) -> RunEnvelope:
    return make_envelope(**kw)


# ---------------------------------------------------------------------------
# Idempotence: x.join(x) == x
# ---------------------------------------------------------------------------

def test_join_idempotent_empty():
    assert EMPTY_ENVELOPE.join(EMPTY_ENVELOPE) == EMPTY_ENVELOPE


def test_join_idempotent_nontrivial():
    x = e(taint="tainted", cost=1.5, lineage=("a", "b"), retry_budget=1)
    assert x.join(x) == x


# ---------------------------------------------------------------------------
# Identity element: join with EMPTY_ENVELOPE
# ---------------------------------------------------------------------------

def test_empty_is_left_identity():
    x = e(taint="tainted", cost=2.0, lineage=("s1",), retry_budget=2)
    result = EMPTY_ENVELOPE.join(x)
    assert result.taint == "tainted"
    assert result.cost == pytest.approx(2.0)
    assert "s1" in result.lineage
    assert result.retry_budget == 2


def test_empty_is_right_identity():
    x = e(taint="tainted", cost=2.0, lineage=("s1",), retry_budget=2)
    result = x.join(EMPTY_ENVELOPE)
    assert result.taint == "tainted"
    assert result.cost == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Commutativity: x.join(y) == y.join(x)  (field-by-field)
# ---------------------------------------------------------------------------

def _equiv(a: RunEnvelope, b: RunEnvelope) -> bool:
    """Field-wise equivalence for commutative join (cost is summed so identical)."""
    return (
        a.taint == b.taint
        and pytest.approx(a.cost) == b.cost
        and set(a.lineage) == set(b.lineage)
        and a.deadline == b.deadline
        and a.cancellation == b.cancellation
        and a.retry_budget == b.retry_budget
        and a.error_class == b.error_class
    )


def test_join_commutative_basic():
    a = e(taint="clean", cost=1.0, lineage=("a",), retry_budget=3)
    b = e(taint="tainted", cost=2.0, lineage=("b",), retry_budget=2)
    ab = a.join(b)
    ba = b.join(a)
    assert _equiv(ab, ba)


def test_join_commutative_taint():
    a = e(taint="clean")
    b = e(taint="dirty")
    assert a.join(b).taint == b.join(a).taint


def test_join_commutative_deadline():
    a = e(deadline=100.0)
    b = e(deadline=200.0)
    assert a.join(b).deadline == b.join(a).deadline == 100.0


def test_join_commutative_cancellation():
    a = e(cancellation=True)
    b = e(cancellation=False)
    assert a.join(b).cancellation == b.join(a).cancellation is True


def test_join_commutative_retry_budget():
    a = e(retry_budget=5)
    b = e(retry_budget=2)
    assert a.join(b).retry_budget == b.join(a).retry_budget == 2


def test_join_commutative_error_class_same():
    a = e(error_class="timeout")
    b = e(error_class="timeout")
    assert a.join(b).error_class == b.join(a).error_class == "timeout"


def test_join_commutative_error_class_conflict():
    a = e(error_class="timeout")
    b = e(error_class="rate_limit")
    assert a.join(b).error_class == b.join(a).error_class == "multiple"


# ---------------------------------------------------------------------------
# Associativity: (x.join(y)).join(z) == x.join(y.join(z))
# ---------------------------------------------------------------------------

def test_join_associative():
    x = e(cost=1.0, taint="clean", lineage=("x",), retry_budget=3, deadline=300.0)
    y = e(cost=2.0, taint="tainted", lineage=("y",), retry_budget=2, deadline=200.0)
    z = e(cost=0.5, taint="clean", lineage=("z",), retry_budget=1, deadline=400.0)
    lhs = (x.join(y)).join(z)
    rhs = x.join(y.join(z))
    # cost: both should be 3.5 (1+2+0.5)
    assert pytest.approx(lhs.cost) == rhs.cost
    assert lhs.taint == rhs.taint
    assert set(lhs.lineage) == set(rhs.lineage)
    assert lhs.deadline == rhs.deadline
    assert lhs.retry_budget == rhs.retry_budget


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------

def test_json_roundtrip_empty():
    data = EMPTY_ENVELOPE.to_json()
    recovered = RunEnvelope.from_json(data)
    assert recovered == EMPTY_ENVELOPE


def test_json_roundtrip_full():
    original = e(
        taint="tainted",
        cost=3.14,
        lineage=("step-a", "step-b"),
        deadline=9999.0,
        cancellation=True,
        retry_budget=1,
        error_class="network",
    )
    data = original.to_json()
    recovered = RunEnvelope.from_json(data)
    assert recovered == original


def test_json_roundtrip_none_fields():
    original = e(deadline=None, error_class=None)
    data = original.to_json()
    recovered = RunEnvelope.from_json(data)
    assert recovered.deadline is None
    assert recovered.error_class is None


def test_json_roundtrip_via_string():
    original = e(taint="flagged", cost=0.5, lineage=("x",))
    recovered = RunEnvelope.from_json(json.loads(json.dumps(original.to_json())))
    assert recovered == original


# ---------------------------------------------------------------------------
# make_envelope convenience constructor
# ---------------------------------------------------------------------------

def test_make_envelope_defaults():
    env = make_envelope()
    assert env == EMPTY_ENVELOPE


def test_make_envelope_list_lineage_coerced():
    env = make_envelope(lineage=["a", "b"])
    assert isinstance(env.lineage, tuple)
    assert env.lineage == ("a", "b")


# ---------------------------------------------------------------------------
# StepContext and StepResult carry envelope field
# ---------------------------------------------------------------------------

def test_step_context_default_envelope():
    from pathlib import Path
    from megaplan._pipeline.types import StepContext
    ctx = StepContext(plan_dir=Path("/tmp"), state={}, profile={}, mode="run")
    assert ctx.envelope == EMPTY_ENVELOPE


def test_step_result_default_envelope():
    from megaplan._pipeline.types import StepResult
    result = StepResult()
    assert result.envelope == EMPTY_ENVELOPE


def test_step_context_custom_envelope():
    from pathlib import Path
    from megaplan._pipeline.types import StepContext
    env = e(taint="tainted", cost=1.0)
    ctx = StepContext(plan_dir=Path("/tmp"), state={}, profile={}, mode="run", envelope=env)
    assert ctx.envelope.taint == "tainted"


def test_step_result_custom_envelope():
    from megaplan._pipeline.types import StepResult
    env = e(retry_budget=1)
    result = StepResult(envelope=env)
    assert result.envelope.retry_budget == 1
