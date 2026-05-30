"""M4 T20 — BudgetAuthority + CostTracker reconciliation tests.

Covers the single-process fallback contract:

* ``install(state_total=...)`` seeds the in-process authority so that
  ``current_total()`` reads back the exact seed before any charge.
* ``charge`` is idempotent on ``(lease_id, fencing_token)`` — the seam
  where double-counting is prevented.
* :class:`megaplan._pipeline.runtime.CostTracker` is **byte-identical** to
  the legacy state-read when ``UNIFIED_BUDGET`` is unset.
* Under ``UNIFIED_BUDGET=1`` ``CostTracker.should_abort`` consults the
  authority's live total and ignores ``state['meta']['total_cost_usd']``.
"""

from __future__ import annotations

import os

import pytest

from megaplan._pipeline.runtime import CostTracker
from megaplan.runtime import budget_authority as ba


@pytest.fixture(autouse=True)
def _reset_authority(monkeypatch):
    ba.uninstall()
    monkeypatch.delenv("UNIFIED_BUDGET", raising=False)
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    yield
    ba.uninstall()


def test_install_seeds_total_from_state():
    auth = ba.install(state_total=12.5)
    assert auth.current_total() == 12.5
    assert ba.current_authority() is auth


def test_charge_is_idempotent_on_lease_fencing_pair():
    auth = ba.install(state_total=0.0)
    t1 = auth.charge(lease_id="L1", fencing_token=1, amount_usd=2.0)
    t2 = auth.charge(lease_id="L1", fencing_token=1, amount_usd=2.0)
    assert t1 == pytest.approx(2.0)
    assert t2 == pytest.approx(2.0)
    # Different fencing token = new charge.
    t3 = auth.charge(lease_id="L1", fencing_token=2, amount_usd=3.0)
    assert t3 == pytest.approx(5.0)


def test_charge_requires_lease_id():
    auth = ba.install(state_total=0.0)
    with pytest.raises(ValueError):
        auth.charge(lease_id="", fencing_token=1, amount_usd=1.0)


def test_cost_tracker_byte_identical_flag_off():
    # No UNIFIED_BUDGET / no install: legacy state['meta'] read.
    state = {"meta": {"total_cost_usd": 4.0}}
    ct = CostTracker(cap_usd=5.0)
    assert ct.current_cost(state) == 4.0
    assert ct.should_abort(state) is False
    state["meta"]["total_cost_usd"] = 6.0
    assert ct.should_abort(state) is True


def test_cost_tracker_byte_identical_when_authority_installed_flag_off():
    # Even with authority installed, flag-off => byte-identical legacy read.
    ba.install(state_total=99.0)
    state = {"meta": {"total_cost_usd": 1.0}}
    ct = CostTracker(cap_usd=2.0)
    assert ct.current_cost(state) == 1.0
    assert ct.should_abort(state) is False


def test_cost_tracker_uses_authority_when_flag_on(monkeypatch):
    monkeypatch.setenv("UNIFIED_BUDGET", "1")
    auth = ba.install(state_total=3.0)
    state = {"meta": {"total_cost_usd": 999.0}}  # ignored under flag-on
    ct = CostTracker(cap_usd=5.0)
    assert ct.current_cost(state) == 3.0
    assert ct.should_abort(state) is False
    auth.charge(lease_id="L", fencing_token=1, amount_usd=10.0)
    assert ct.current_cost(state) == 13.0
    assert ct.should_abort(state) is True


def test_cost_tracker_flag_on_no_authority_falls_back(monkeypatch):
    # Flag on but nobody installed an authority -> stay on legacy path.
    monkeypatch.setenv("UNIFIED_BUDGET", "1")
    state = {"meta": {"total_cost_usd": 7.0}}
    ct = CostTracker(cap_usd=5.0)
    assert ct.current_cost(state) == 7.0
    assert ct.should_abort(state) is True


def test_seed_matches_state_total_at_install_time():
    # The byte-identical contract: at install time, before any charge,
    # authority.current_total() == state['meta']['total_cost_usd'].
    legacy_total = 42.125
    state = {"meta": {"total_cost_usd": legacy_total}}
    auth = ba.install(state_total=state["meta"]["total_cost_usd"])
    assert auth.current_total() == legacy_total
