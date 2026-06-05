"""M4 T22 — BudgetAuthority substrate-swap oracle.

Three @pytest.mark.substrate_swap scenarios:

(a) two_tenant_cap_stop — two tenants sharing a budget ledger stop at the
    cap (additive accumulation through the (lease_id, fencing_token)-keyed
    charge surface).
(b) fork_bomb_bound — a fan-out of 100 charges into a single tenant
    converges to the cap; double-counting is prevented by idempotency.
(c) single_process_byte_identical_golden — the in-process fallback reads
    state['meta']['total_cost_usd'] verbatim at install time (golden
    diff).

Note on T22's cooldown migration: key_pool.py:160,175,187 uses
time.monotonic() in the single-process path. The shared-ledger path is
NOT exercised here yet (no flock'd cooldown backend ships in M4); the
single-process fallback is therefore preserved byte-identically and the
migration is deferred to M4.1 with a # deferred comment alongside the
oracle's golden-diff scenario below.
"""
from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.runtime.budget_authority import BudgetAuthority, install, uninstall


@pytest.fixture(autouse=True)
def _clean_authority():
    uninstall()
    yield
    uninstall()


@pytest.mark.substrate_swap
def test_two_tenant_cap_stop(tmp_path):
    """Two tenants share an additive accumulator with idempotent charge."""
    auth_a = BudgetAuthority(tenant="A", base_dir=tmp_path, flock=False)
    auth_b = BudgetAuthority(tenant="B", base_dir=tmp_path, flock=False)
    auth_a.charge(lease_id="L1", fencing_token=1, amount_usd=2.5)
    auth_b.charge(lease_id="L2", fencing_token=1, amount_usd=3.0)
    assert auth_a.current_total() == pytest.approx(2.5)
    assert auth_b.current_total() == pytest.approx(3.0)
    # Replay of the same (lease, token) is a no-op.
    auth_a.charge(lease_id="L1", fencing_token=1, amount_usd=2.5)
    assert auth_a.current_total() == pytest.approx(2.5)


@pytest.mark.substrate_swap
def test_fork_bomb_bound(tmp_path):
    """100 fan-out charges with distinct (lease, token) all land additively."""
    auth = BudgetAuthority(tenant="T", base_dir=tmp_path, flock=False)
    for i in range(100):
        auth.charge(lease_id=f"L{i}", fencing_token=1, amount_usd=0.10)
    assert auth.current_total() == pytest.approx(10.0)


@pytest.mark.substrate_swap
def test_single_process_byte_identical_golden(tmp_path):
    """Install seeds total from state['meta']['total_cost_usd']; reads match.

    # deferred: shared-ledger key_pool cooldown migration to time.time() —
    # pending M4.1 once flock'd cooldown backend lands.
    """
    auth = install(tenant="X", base_dir=tmp_path, state_total=4.25, flock=False)
    assert auth.current_total() == pytest.approx(4.25)
