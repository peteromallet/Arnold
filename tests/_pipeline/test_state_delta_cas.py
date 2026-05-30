"""CAS semantics covering the executor owned-key write site (T11c).

These tests pin the StateDelta+apply_delta substrate that
``megaplan/_pipeline/executor.py`` switches to under ``typed_ports_on()``:

* ``replace`` is last-writer-wins: a later ``replace`` at the same key
  drops the prior value.
* ``accumulate`` retains both prior and new entries.
* A stale ``version`` raises :class:`StateDeltaConflict` and leaves state
  unmutated.
"""

import pytest

from megaplan._pipeline.types import StateDelta, StateDeltaConflict, apply_delta


def test_replace_lww_loses_prior_value():
    state: dict = {}
    state, v1 = apply_delta(state, StateDelta("replace", "k", "first", version=0))
    assert v1 == 1
    state, v2 = apply_delta(state, StateDelta("replace", "k", "second", version=1))
    assert v2 == 2
    assert state["k"] == "second"
    assert state["_state_meta"]["versions"]["k"] == 2


def test_accumulate_keeps_both_entries():
    state: dict = {}
    state, _ = apply_delta(state, StateDelta("accumulate", "log", "a", version=0))
    state, _ = apply_delta(state, StateDelta("accumulate", "log", "b", version=1))
    assert state["log"] == ["a", "b"]
    assert state["_state_meta"]["versions"]["log"] == 2


def test_stale_version_raises_conflict_and_does_not_mutate():
    state: dict = {}
    state, _ = apply_delta(state, StateDelta("replace", "k", "v1", version=0))
    snapshot = {k: (dict(v) if isinstance(v, dict) else v) for k, v in state.items()}
    with pytest.raises(StateDeltaConflict) as exc:
        apply_delta(state, StateDelta("replace", "k", "v2", version=0))
    assert exc.value.key == "k"
    assert exc.value.expected == 0
    assert exc.value.actual == 1
    assert state == snapshot


def test_bootstrap_version_zero_writes_meta():
    state, version = apply_delta(
        {}, StateDelta("replace", "k", "v", version=0)
    )
    assert version == 1
    assert state["_state_meta"] == {"versions": {"k": 1}}
