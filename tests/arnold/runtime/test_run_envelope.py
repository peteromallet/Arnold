"""Tests for ``arnold.runtime.envelope.RunEnvelope`` (T3 / SC3).

Covers: join() algebraic laws, error_class merging, LeaseIdConflict,
fencing/capacity semantics, JSON round-trip via the canonical method
names (to_jsonable / from_jsonable), and RunContext isinstance check.
"""
from __future__ import annotations

import json

import pytest

from arnold.runtime.envelope import (
    EMPTY_ENVELOPE,
    LeaseIdConflict,
    RunContext,
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
    assert _equiv(a.join(b), b.join(a))


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


# ---------------------------------------------------------------------------
# error_class merging
# ---------------------------------------------------------------------------

def test_join_error_class_none_absorbs():
    a = e(error_class="timeout")
    b = e(error_class=None)
    assert a.join(b).error_class == "timeout"
    assert b.join(a).error_class == "timeout"


def test_join_error_class_same_kept():
    a = e(error_class="timeout")
    b = e(error_class="timeout")
    assert a.join(b).error_class == b.join(a).error_class == "timeout"


def test_join_error_class_conflict_becomes_multiple():
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
    assert pytest.approx(lhs.cost) == rhs.cost
    assert lhs.taint == rhs.taint
    assert set(lhs.lineage) == set(rhs.lineage)
    assert lhs.deadline == rhs.deadline
    assert lhs.retry_budget == rhs.retry_budget


# ---------------------------------------------------------------------------
# JSON round-trip via canonical to_jsonable / from_jsonable
# ---------------------------------------------------------------------------

def test_to_jsonable_returns_dict():
    env = e(taint="tainted", cost=1.5)
    data = env.to_jsonable()
    assert isinstance(data, dict)
    assert data["taint"] == "tainted"
    assert data["cost"] == pytest.approx(1.5)


def test_from_jsonable_reconstructs():
    original = e(taint="tainted", cost=3.14, lineage=("s1", "s2"), retry_budget=1)
    data = original.to_jsonable()
    recovered = RunEnvelope.from_jsonable(data)
    assert recovered == original


def test_to_jsonable_from_jsonable_roundtrip_empty():
    data = EMPTY_ENVELOPE.to_jsonable()
    assert RunEnvelope.from_jsonable(data) == EMPTY_ENVELOPE


def test_to_jsonable_from_jsonable_none_fields():
    original = e(deadline=None, error_class=None)
    data = original.to_jsonable()
    recovered = RunEnvelope.from_jsonable(data)
    assert recovered.deadline is None
    assert recovered.error_class is None


def test_to_jsonable_json_serializable():
    env = e(taint="tainted", cost=0.5, lineage=("x",))
    data = env.to_jsonable()
    serialized = json.dumps(data)
    recovered = RunEnvelope.from_jsonable(json.loads(serialized))
    assert recovered == env


def test_to_json_alias_still_works():
    env = e(cost=1.0)
    assert env.to_json() == env.to_jsonable()


def test_from_json_alias_still_works():
    env = e(cost=1.0)
    data = env.to_jsonable()
    assert RunEnvelope.from_json(data) == RunEnvelope.from_jsonable(data)


# ---------------------------------------------------------------------------
# LeaseIdConflict
# ---------------------------------------------------------------------------

def test_join_lease_id_none_absorbs():
    a = make_envelope(lease_id="L1")
    b = make_envelope(lease_id=None)
    assert a.join(b).lease_id == "L1"
    assert b.join(a).lease_id == "L1"


def test_join_lease_id_equal_merges():
    a = make_envelope(lease_id="L1", capacity_grant=1)
    b = make_envelope(lease_id="L1", capacity_grant=2)
    joined = a.join(b)
    assert joined.lease_id == "L1"
    assert joined.capacity_grant == 3


def test_join_unequal_lease_ids_raises_commutatively():
    a = make_envelope(lease_id="L1")
    b = make_envelope(lease_id="L2")
    with pytest.raises(LeaseIdConflict):
        a.join(b)
    with pytest.raises(LeaseIdConflict):
        b.join(a)


# ---------------------------------------------------------------------------
# Fencing / capacity semantics
# ---------------------------------------------------------------------------

def test_fencing_token_max_treats_none_as_minus_one():
    a = make_envelope(fencing_token=None)
    b = make_envelope(fencing_token=3)
    assert a.join(b).fencing_token == 3
    assert b.join(a).fencing_token == 3
    c = make_envelope(fencing_token=10)
    d = make_envelope(fencing_token=4)
    assert c.join(d).fencing_token == 10
    assert d.join(c).fencing_token == 10
    assert make_envelope().join(make_envelope()).fencing_token is None


def test_capacity_grant_additive_commutative():
    a = make_envelope(capacity_grant=2)
    b = make_envelope(capacity_grant=5)
    assert a.join(b).capacity_grant == 7
    assert b.join(a).capacity_grant == 7


def test_new_fields_default_to_empty():
    env = RunEnvelope()
    assert env.lease_id is None
    assert env.fencing_token is None
    assert env.capacity_grant == 0


def test_json_roundtrip_preserves_lease_fencing_capacity():
    env = make_envelope(lease_id="L42", fencing_token=11, capacity_grant=3)
    recovered = RunEnvelope.from_jsonable(env.to_jsonable())
    assert recovered == env


def test_legacy_payload_without_new_fields_defaults():
    full = e(taint="tainted", cost=1.5, lineage=("a",), retry_budget=2).to_jsonable()
    for k in ("lease_id", "fencing_token", "capacity_grant"):
        full.pop(k)
    restored = RunEnvelope.from_jsonable(full)
    assert restored.lease_id is None
    assert restored.fencing_token is None
    assert restored.capacity_grant == 0


# ---------------------------------------------------------------------------
# RunContext isinstance check
# ---------------------------------------------------------------------------

def test_run_envelope_satisfies_run_context_protocol():
    env = RunEnvelope()
    assert isinstance(env, RunContext), (
        "RunEnvelope must satisfy the RunContext @runtime_checkable Protocol"
    )


def test_run_envelope_with_values_satisfies_run_context():
    env = e(taint="tainted", cost=1.0, lineage=("x",), cancellation=True, retry_budget=1)
    assert isinstance(env, RunContext)
    assert env.taint == "tainted"
    assert env.cost == pytest.approx(1.0)
    assert env.lineage == ("x",)
    assert env.cancellation is True
    assert env.retry_budget == 1


def test_run_context_protocol_surface():
    env = e(deadline=500.0)
    ctx: RunContext = env
    assert ctx.taint == "clean"
    assert ctx.cost == pytest.approx(0.0)
    assert ctx.lineage == ()
    assert ctx.deadline == pytest.approx(500.0)
    assert ctx.cancellation is False
    assert ctx.retry_budget == 3
