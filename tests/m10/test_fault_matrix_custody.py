"""T39 — Steps 20A-20C: custody fault-matrix scenario tests.

These tests bind the custody-related fault-matrix rows (F07, F08, F13,
F14) to installed-runtime behavior at the ``CustodyLeaseStore`` seam.
Every production effect remains action-off (SD3); only the durable
lease store is exercised.

Step 20A — custody acquisition and renewal lifecycle:
  * acquire creates an active lease with correct identity;
  * renewal preserves owner identity and enforces monotonic epoch;
  * idempotent-repeat of acquire/renew is a no-op.

Step 20B — transfer and reclaim reconciliation:
  * transfer moves ownership with monotonic-epoch fencing;
  * reclaim after a terminal event requires a strictly-greater epoch;
  * old-epoch reclaim is rejected (StaleEpochError).

Step 20C — stale-owner rejection scenarios:
  * F07 lease-expiry and F08 TTL-ceiling rows are in the fault matrix;
  * F13 epoch-staleness row is in the fault matrix;
  * acquire/renew enforce the TTL ceiling; fencing is terminal.

Action-gate verdict behavior (shadow, stale-custody, WBC) is covered by
the live action validator in
``tests/arnold_pipelines/megaplan/test_custody_action_validator.py``.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

# Ensure tests/support is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from arnold_pipelines.megaplan.custody.lease_store import (
    CustodyLeaseStore,
    LeaseNotFoundError,
    LeaseOwnerMismatchError,
    LeaseStoreError,
    LeaseTtlCeilingError,
    StaleEpochError,
    TerminalLeaseError,
    open_lease_store,
)

from arnold.workflow.effect_fault_matrix import (
    load_and_validate_fault_matrix,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def lease_store(tmp_path: Path) -> CustodyLeaseStore:
    """A fresh lease store rooted in a temp directory."""
    return open_lease_store(tmp_path / "leases", flock=False)


def _acquire_kwargs(lease_id: str | None = None, epoch: int = 1) -> dict:
    """Standard acquire keyword arguments."""
    return dict(
        lease_id=lease_id or f"lease-{uuid.uuid4().hex[:12]}",
        owner_host="host-a",
        owner_pid="12345",
        owner_boot_id="boot-aaa",
        run_authority_grant_id="grant-1",
        coordinator_fence_token=100,
        wbc_attempt_reference="att-001",
        occurrence_digest="occ-digest-1",
        custody_epoch=epoch,
    )


# ── Step 20A: acquisition and renewal lifecycle ───────────────────────────


class TestStep20AAcquisitionRenewal:
    """Step 20A — custody acquisition and renewal lifecycle."""

    def test_acquire_creates_active_lease(self, lease_store: CustodyLeaseStore) -> None:
        """Acquire creates an active lease that replays to custody_epoch."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)

        replayed = lease_store.replay_history(kw["lease_id"])
        assert replayed is not None
        assert replayed.custody_epoch == 1
        assert replayed.owner_host == "host-a"

    def test_acquisition_idempotent_repeat_is_noop(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """An exact-duplicate acquire (same idempotency key) is a no-op."""
        kw = _acquire_kwargs(epoch=1)
        first = lease_store.acquire(**kw)
        # Same idempotency key — must not raise, must not duplicate.
        second = lease_store.acquire(**kw)

        history = lease_store.load_history(kw["lease_id"])
        assert len(history) == 1
        # The replayed state is the same.
        replayed = lease_store.replay_history(kw["lease_id"])
        assert replayed is not None

    def test_renew_preserves_owner_identity(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """Renew requires the current owner and preserves identity."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)

        renew_event = lease_store.renew(
            lease_id=kw["lease_id"],
            owner_host=kw["owner_host"],
            owner_pid=kw["owner_pid"],
            owner_boot_id=kw["owner_boot_id"],
            custody_epoch=2,  # strictly greater than acquire epoch 1
        )
        assert renew_event.event_type == "renew"

        replayed = lease_store.replay_history(kw["lease_id"])
        assert replayed is not None
        assert replayed.owner_host == "host-a"

    def test_renew_wrong_owner_rejected(self, lease_store: CustodyLeaseStore) -> None:
        """Renew by a non-owner is rejected (LeaseOwnerMismatchError)."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)

        with pytest.raises(LeaseOwnerMismatchError):
            lease_store.renew(
                lease_id=kw["lease_id"],
                owner_host="host-b",  # wrong owner
                owner_pid="99999",
                owner_boot_id="boot-bbb",
                custody_epoch=2,  # valid epoch to reach owner check
            )

    def test_renew_stale_epoch_rejected(self, lease_store: CustodyLeaseStore) -> None:
        """Renew with a lower epoch is rejected (StaleEpochError). F13."""
        kw = _acquire_kwargs(epoch=5)
        lease_store.acquire(**kw)

        with pytest.raises(StaleEpochError):
            lease_store.renew(
                lease_id=kw["lease_id"],
                owner_host=kw["owner_host"],
                owner_pid=kw["owner_pid"],
                owner_boot_id=kw["owner_boot_id"],
                custody_epoch=3,  # lower than acquire epoch 5
            )

    def test_renew_terminal_lease_rejected(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """Renew on a released lease is rejected (TerminalLeaseError)."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)
        lease_store.release(
            lease_id=kw["lease_id"],
            owner_host=kw["owner_host"],
            owner_pid=kw["owner_pid"],
            owner_boot_id=kw["owner_boot_id"],
        )

        with pytest.raises(TerminalLeaseError):
            lease_store.renew(
                lease_id=kw["lease_id"],
                owner_host=kw["owner_host"],
                owner_pid=kw["owner_pid"],
                owner_boot_id=kw["owner_boot_id"],
                custody_epoch=2,  # valid epoch to reach terminal check
            )


# ── Step 20B: transfer and reclaim reconciliation ─────────────────────────


class TestStep20BTransferReclaim:
    """Step 20B — transfer and reclaim reconciliation."""

    def test_transfer_moves_ownership(self, lease_store: CustodyLeaseStore) -> None:
        """Transfer moves ownership to a new owner with monotonic epoch."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)

        lease_store.transfer(
            lease_id=kw["lease_id"],
            owner_host=kw["owner_host"],
            owner_pid=kw["owner_pid"],
            owner_boot_id=kw["owner_boot_id"],
            new_owner_host="host-b",
            new_owner_pid="67890",
            new_owner_boot_id="boot-bbb",
            custody_epoch=2,
        )

        replayed = lease_store.replay_history(kw["lease_id"])
        assert replayed is not None
        assert replayed.owner_host == "host-b"
        assert replayed.custody_epoch == 2

    def test_transfer_wrong_caller_rejected(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """Transfer by a non-owner is rejected."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)

        with pytest.raises(LeaseOwnerMismatchError):
            lease_store.transfer(
                lease_id=kw["lease_id"],
                owner_host="host-b",  # not the owner
                owner_pid="99999",
                owner_boot_id="boot-bbb",
                new_owner_host="host-c",
                new_owner_pid="11111",
                new_owner_boot_id="boot-ccc",
                custody_epoch=2,
            )

    def test_transfer_stale_epoch_rejected(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """Transfer with a non-increasing epoch is rejected. F13."""
        kw = _acquire_kwargs(epoch=3)
        lease_store.acquire(**kw)

        with pytest.raises(StaleEpochError):
            lease_store.transfer(
                lease_id=kw["lease_id"],
                owner_host=kw["owner_host"],
                owner_pid=kw["owner_pid"],
                owner_boot_id=kw["owner_boot_id"],
                new_owner_host="host-b",
                new_owner_pid="67890",
                new_owner_boot_id="boot-bbb",
                custody_epoch=3,  # equal — not strictly greater
            )

    def test_reclaim_after_release_requires_greater_epoch(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """Reclaim after release requires a strictly-greater epoch."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)
        lease_store.release(
            lease_id=kw["lease_id"],
            owner_host=kw["owner_host"],
            owner_pid=kw["owner_pid"],
            owner_boot_id=kw["owner_boot_id"],
        )

        # Old-epoch reclaim is rejected.
        with pytest.raises(StaleEpochError):
            lease_store.reclaim(
                lease_id=kw["lease_id"],
                owner_host="host-c",
                owner_pid="33333",
                owner_boot_id="boot-ccc",
                run_authority_grant_id="grant-2",
                coordinator_fence_token=200,
                wbc_attempt_reference="att-002",
                occurrence_digest="occ-digest-2",
                custody_epoch=1,  # not greater than prior epoch 1
            )

        # New-epoch reclaim succeeds.
        reclaim_event = lease_store.reclaim(
            lease_id=kw["lease_id"],
            owner_host="host-c",
            owner_pid="33333",
            owner_boot_id="boot-ccc",
            run_authority_grant_id="grant-2",
            coordinator_fence_token=200,
            wbc_attempt_reference="att-002",
            occurrence_digest="occ-digest-2",
            custody_epoch=2,  # strictly greater
        )
        assert reclaim_event.event_type == "acquire"

        replayed = lease_store.replay_history(kw["lease_id"])
        assert replayed is not None
        assert replayed.owner_host == "host-c"
        assert replayed.custody_epoch == 2

    def test_reclaim_after_expire(self, lease_store: CustodyLeaseStore) -> None:
        """Reclaim after expire restores the lease with a new epoch. F07."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)
        lease_store.expire(lease_id=kw["lease_id"])

        lease_store.reclaim(
            lease_id=kw["lease_id"],
            owner_host="host-d",
            owner_pid="44444",
            owner_boot_id="boot-ddd",
            run_authority_grant_id="grant-3",
            coordinator_fence_token=300,
            wbc_attempt_reference="att-003",
            occurrence_digest="occ-digest-3",
            custody_epoch=2,
        )

        replayed = lease_store.replay_history(kw["lease_id"])
        assert replayed is not None
        assert replayed.owner_host == "host-d"

    def test_reclaim_active_lease_rejected(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """Reclaim on an active (non-terminal) lease is rejected."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)

        with pytest.raises(LeaseStoreError):
            lease_store.reclaim(
                lease_id=kw["lease_id"],
                owner_host="host-e",
                owner_pid="55555",
                owner_boot_id="boot-eee",
                run_authority_grant_id="grant-4",
                coordinator_fence_token=400,
                wbc_attempt_reference="att-004",
                occurrence_digest="occ-digest-4",
                custody_epoch=2,
            )

    def test_reclaim_nonexistent_lease_rejected(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """Reclaim on a lease that never existed is rejected."""
        with pytest.raises(LeaseNotFoundError):
            lease_store.reclaim(
                lease_id="no-such-lease",
                owner_host="host-f",
                owner_pid="66666",
                owner_boot_id="boot-fff",
                run_authority_grant_id="grant-5",
                coordinator_fence_token=500,
                wbc_attempt_reference="att-005",
                occurrence_digest="occ-digest-5",
                custody_epoch=1,
            )


# ── Step 20C: stale-owner action gate rejection ───────────────────────────


class TestStep20CStaleOwnerAction:
    """Step 20C — stale-owner rejection scenarios (F07/F08/F13)."""

    def _load_scenario(self, scenario_id: str) -> dict:
        """Load a single scenario from the fault matrix JSON."""
        import json
        matrix_path = Path(__file__).resolve().parents[2] / "evidence" / "m10-f01-f17-fault-matrix.json"
        with open(matrix_path) as f:
            data = json.load(f)
        return [s for s in data["scenarios"] if s["id"] == scenario_id][0]

    def test_f07_lease_expiry_fault_matrix_scenario(self) -> None:
        """F07 scenario: lease-expiry-during-effect is in the fault matrix."""
        f07 = self._load_scenario("F07")
        assert f07["custody_precondition"] == "lease_expired"
        assert f07["replay_expectation"] == "indeterminate"

    def test_f08_ttl_ceiling_fault_matrix_scenario(self) -> None:
        """F08 scenario: lease-ttl-ceiling-enforcement is in the fault matrix."""
        f08 = self._load_scenario("F08")
        assert f08["custody_precondition"] == "lease_active"
        assert f08["replay_expectation"] == "ttl_clamped"

    def test_f13_epoch_staleness_fault_matrix_scenario(self) -> None:
        """F13 scenario: custody-epoch-staleness-rejection is in the matrix."""
        f13 = self._load_scenario("F13")
        assert f13["custody_precondition"] == "stale_epoch"
        assert f13["replay_expectation"] == "fenced"

    def test_ttl_ceiling_enforced_on_acquire(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """F08: acquire with a TTL exceeding the ceiling is rejected."""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        # Request a TTL far beyond the maximum (86400s = 1 day).
        far_future = now + timedelta(days=365)
        kw = _acquire_kwargs(epoch=1)
        with pytest.raises(LeaseTtlCeilingError):
            lease_store.acquire(
                **kw,
                occurred_at=now.isoformat(),
                expires_at=far_future.isoformat(),
            )

    def test_ttl_ceiling_enforced_on_renew(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """F08: renew with a TTL exceeding the ceiling is rejected."""
        from datetime import datetime, timedelta, timezone

        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)

        now = datetime.now(timezone.utc)
        far_future = now + timedelta(days=365)
        with pytest.raises(LeaseTtlCeilingError):
            lease_store.renew(
                lease_id=kw["lease_id"],
                owner_host=kw["owner_host"],
                owner_pid=kw["owner_pid"],
                owner_boot_id=kw["owner_boot_id"],
                custody_epoch=2,  # valid epoch to reach TTL ceiling check
                occurred_at=now.isoformat(),
                expires_at=far_future.isoformat(),
            )

    def test_fence_terminal_then_reject_double_terminal(
        self, lease_store: CustodyLeaseStore
    ) -> None:
        """Fencing makes the lease terminal; a second terminal is rejected."""
        kw = _acquire_kwargs(epoch=1)
        lease_store.acquire(**kw)
        lease_store.fence(
            lease_id=kw["lease_id"],
            owner_host=kw["owner_host"],
            owner_pid=kw["owner_pid"],
            owner_boot_id=kw["owner_boot_id"],
            coordinator_fence_token=999,
        )
        # A release after fence is rejected.
        with pytest.raises(TerminalLeaseError):
            lease_store.release(
                lease_id=kw["lease_id"],
                owner_host=kw["owner_host"],
                owner_pid=kw["owner_pid"],
                owner_boot_id=kw["owner_boot_id"],
            )
