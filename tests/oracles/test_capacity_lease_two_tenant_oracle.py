"""M4 T4 — Capacity-lease two-tenant substrate-swap oracle.

Substrate-swap oracles must remain green whether the underlying lease/budget
substrate is the in-process Governor accumulator or a future cross-process
ledger.  These tests exercise three substrate properties:

(a) ``test_two_tenants_share_backoff_and_spend_cap`` — two tenants sharing the
    Governor's lease accumulator each charge their own ``capacity_grant``; the
    total folded grant is the sum, and once the dollar_cap is reached neither
    tenant can charge further.  Property: *isolated leases compose additively
    without cross-talk*.

(b) ``test_fork_bomb_fanout_bounded_by_tree_budget`` — a single tenant fans out
    ``N`` shards, each with its own fencing_token; the Governor's accumulator
    rejects further charges once ``dollar_cap`` is hit, regardless of how many
    shards the caller spawned.  Property: *the tree budget is the upper bound
    on observable spend even under unbounded fan-out*.

(c) ``test_clock_rewind_does_not_double_grant`` — a stale fencing_token (one
    less than the highest seen for the same lease) poisons the accumulator so
    the *next* fold raises :class:`BudgetExceeded`.  Property: *fencing-token
    monotonicity makes clock-rewind / replay double-grant impossible*.

Each test owns its harness fixture (no shared state between tests).
"""
from __future__ import annotations

import pytest

from megaplan._pipeline.envelope import RunEnvelope, make_envelope
from megaplan.runtime.governor import (
    BudgetExceeded,
    ExceedReason,
    Governor,
)


@pytest.fixture
def gov():
    """Per-test Governor with a finite dollar cap so charge can fail loudly."""
    return Governor(dollar_cap=10.0)


@pytest.mark.substrate_swap
def test_two_tenants_share_backoff_and_spend_cap(gov: Governor):
    """Property (a): isolated leases compose additively without cross-talk."""
    tenant_a = make_envelope(
        cost=3.0, lease_id="tenant-a", fencing_token=1, capacity_grant=3
    )
    tenant_b = make_envelope(
        cost=4.0, lease_id="tenant-b", fencing_token=1, capacity_grant=4
    )

    gov.fold_shard_spend(tenant_a)
    gov.fold_shard_spend(tenant_b)
    assert gov._shard_grants == 7.0

    # Both tenants charge cost against the shared dollar_cap.
    gov.charge(tenant_a)
    gov.charge(tenant_b)
    assert gov.spent_dollars == 7.0

    # Now a 4-dollar charge from either tenant would exceed the cap of 10.
    overflow = make_envelope(
        cost=4.0, lease_id="tenant-a", fencing_token=2, capacity_grant=4
    )
    verdict = gov.would_exceed(overflow)
    assert verdict == ExceedReason.DOLLAR_CAP
    with pytest.raises(BudgetExceeded) as exc:
        gov.charge(overflow)
    assert exc.value.reason == ExceedReason.DOLLAR_CAP


@pytest.mark.substrate_swap
def test_fork_bomb_fanout_bounded_by_tree_budget():
    """Property (b): tree budget upper-bounds observable spend under fan-out."""
    # Tight cap so a small fork-bomb saturates it.
    gov = Governor(dollar_cap=5.0)

    # Spawn 100 shards each costing $1 — far above the cap.
    spent = 0.0
    blocked_at = None
    for i in range(100):
        env = make_envelope(
            cost=1.0,
            lease_id="forked",
            fencing_token=i + 1,
            capacity_grant=1,
        )
        gov.fold_shard_spend(env)
        try:
            gov.charge(env)
        except BudgetExceeded as exc:
            assert exc.reason == ExceedReason.DOLLAR_CAP
            blocked_at = i
            break
        spent += 1.0

    # Tree budget is the upper bound — the loop must have been blocked.
    assert blocked_at is not None, "fork-bomb breached dollar_cap"
    assert spent <= 5.0
    assert gov.spent_dollars <= 5.0


@pytest.mark.substrate_swap
def test_clock_rewind_does_not_double_grant(gov: Governor):
    """Property (c): fencing-token monotonicity defeats replay."""
    fresh = make_envelope(
        cost=1.0, lease_id="lease-x", fencing_token=5, capacity_grant=2
    )
    gov.fold_shard_spend(fresh)
    assert gov._shard_grants == 2.0

    # A stale write with a smaller fencing_token poisons the accumulator —
    # no double-grant is recorded.
    stale = make_envelope(
        cost=1.0, lease_id="lease-x", fencing_token=4, capacity_grant=99
    )
    gov.fold_shard_spend(stale)
    assert gov._shard_grants == 2.0  # NOT 2 + 99 — stale rejected.

    # The very next fold_shard_spend write must raise BudgetExceeded.
    next_write = make_envelope(
        cost=1.0, lease_id="lease-x", fencing_token=6, capacity_grant=1
    )
    with pytest.raises(BudgetExceeded) as exc:
        gov.fold_shard_spend(next_write)
    assert exc.value.reason == ExceedReason.DOLLAR_CAP

    # The poisoned flag is cleared after raising — subsequent writes proceed.
    follow_up = make_envelope(
        cost=1.0, lease_id="lease-x", fencing_token=7, capacity_grant=1
    )
    gov.fold_shard_spend(follow_up)
    # 2 (original) + 1 (follow-up) — the poisoning write's grant was discarded.
    assert gov._shard_grants == 3.0
