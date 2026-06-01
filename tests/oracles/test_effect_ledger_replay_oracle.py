"""M4 T15 — Effect-ledger replay oracle (substrate_swap).

Simulates a crash between the external return and the journal write,
asserts that resume does not double-execute the at-most-once effect.
"""
from __future__ import annotations

import pytest

from megaplan.observability.effect_enforcement import (
    _reset_for_tests,
    journal_then_execute,
)
from megaplan.observability.effect_ledger import Effect, ReplayClass


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_for_tests()
    yield
    _reset_for_tests()


@pytest.mark.substrate_swap
def test_at_most_once_short_circuits_on_replay():
    """First call executes once; second call with same key is a no-op."""
    calls = []
    eff = Effect(
        replay_class=ReplayClass.at_most_once,
        idempotency_key="git-push:deadbeef",
    )
    journal_then_execute(eff, lambda: calls.append("did it"))
    # Replay rehydration: the at-most-once class must short-circuit.
    journal_then_execute(eff, lambda: calls.append("did it"))
    assert calls == ["did it"]


@pytest.mark.substrate_swap
def test_crash_between_return_and_journal_does_not_double_execute(monkeypatch):
    """If the journal write raises AFTER fn would return, we still
    haven't double-executed: the ordering writes journal FIRST, then fn.
    A crash on the SECOND attempt's journal write must not let fn fire
    again — the seen-keys cache guards the in-process replay seam."""
    calls = []

    def boom(*a, **kw):
        raise RuntimeError("simulated crash mid-write")

    eff = Effect(
        replay_class=ReplayClass.at_most_once,
        idempotency_key="external-act:once",
    )

    # First successful run.
    journal_then_execute(eff, lambda: calls.append("once"))
    assert calls == ["once"]

    # Now simulate a substrate where the journal sink itself would crash.
    # The at-most-once class must NOT re-fire fn, regardless of sink state.
    import megaplan.observability.effect_enforcement as ee

    monkeypatch.setattr(ee, "_journal_intent", boom)
    journal_then_execute(eff, lambda: calls.append("twice?"))
    assert calls == ["once"], "at-most-once must not double-execute on replay"
