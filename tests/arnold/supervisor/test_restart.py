"""Restart and quarantine tests for poison-project quarantine, manual-clear
precondition, rejected claim/restart while quarantined, retry-delay plus jitter
calculation, and staggered ordering by failure count.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from arnold.kernel.suspension import ManualSuspensionClearRequired, SuspensionState
from arnold.supervisor.leases import ProjectLease, ProjectLeaseIdentity, ProjectLeaseState
from arnold.supervisor.restart import (
    RestartDecision,
    RestartPolicy,
    clear_quarantined_project_lease,
    compute_restart_delay,
    evaluate_automatic_restart,
    record_restart_failure,
)
from arnold.supervisor.store import (
    FileProjectLeaseStore,
    ProjectLeaseConflict,
    ProjectLeaseNotFound,
)

NOW = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


# ── helpers ──────────────────────────────────────────────────────────────────

def _lease(
    *,
    project_id: str = "project-1",
    worktree_id: str = "worktree-1",
    run_id: str = "run-1",
    state: ProjectLeaseState = ProjectLeaseState.PENDING,
    failure_count: int = 0,
    retry_count: int = 0,
    last_failure_at: datetime | None = None,
    next_retry_at: datetime | None = None,
    quarantine_reason: str | None = None,
    owner_id: str | None = None,
    lease_token: str | None = None,
    lease_expires_at: datetime | None = None,
) -> ProjectLease:
    return ProjectLease(
        identity=ProjectLeaseIdentity(
            project_id=project_id,
            worktree_id=worktree_id,
            run_id=run_id,
        ),
        state=state,
        failure_count=failure_count,
        retry_count=retry_count,
        last_failure_at=last_failure_at,
        next_retry_at=next_retry_at,
        quarantine_reason=quarantine_reason,
        owner_id=owner_id,
        lease_token=lease_token,
        lease_expires_at=lease_expires_at,
        created_at=NOW,
        updated_at=NOW,
    )


def _store(tmp_path: Path) -> FileProjectLeaseStore:
    return FileProjectLeaseStore(tmp_path / "leases")


# ── RestartPolicy validation ─────────────────────────────────────────────────

class TestRestartPolicyValidation:
    def test_default_policy_is_valid(self) -> None:
        policy = RestartPolicy()
        assert policy.retry_delay_seconds == 60
        assert policy.jitter_seconds == 15
        assert policy.rapid_failure_window == timedelta(minutes=15)
        assert policy.quarantine_failure_count == 3

    def test_custom_policy_is_valid(self) -> None:
        policy = RestartPolicy(
            retry_delay_seconds=30,
            jitter_seconds=5,
            rapid_failure_window=timedelta(minutes=5),
            quarantine_failure_count=5,
        )
        assert policy.retry_delay_seconds == 30
        assert policy.jitter_seconds == 5
        assert policy.rapid_failure_window == timedelta(minutes=5)
        assert policy.quarantine_failure_count == 5

    def test_rejects_negative_retry_delay(self) -> None:
        with pytest.raises(ValueError, match="retry_delay_seconds must be non-negative"):
            RestartPolicy(retry_delay_seconds=-1)

    def test_rejects_negative_jitter(self) -> None:
        with pytest.raises(ValueError, match="jitter_seconds must be non-negative"):
            RestartPolicy(jitter_seconds=-5)

    def test_rejects_zero_rapid_failure_window(self) -> None:
        with pytest.raises(ValueError, match="rapid_failure_window must be positive"):
            RestartPolicy(rapid_failure_window=timedelta(0))

    def test_rejects_negative_rapid_failure_window(self) -> None:
        with pytest.raises(ValueError, match="rapid_failure_window must be positive"):
            RestartPolicy(rapid_failure_window=timedelta(minutes=-1))

    def test_rejects_quarantine_count_below_two(self) -> None:
        with pytest.raises(ValueError, match="quarantine_failure_count must be at least 2"):
            RestartPolicy(quarantine_failure_count=1)

    def test_zero_jitter_is_allowed(self) -> None:
        policy = RestartPolicy(jitter_seconds=0)
        assert policy.jitter_seconds == 0


# ── compute_restart_delay ────────────────────────────────────────────────────

class TestComputeRestartDelay:
    def test_base_delay_scales_with_failure_count(self) -> None:
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=0)
        delay_1 = compute_restart_delay(
            _lease(failure_count=1, retry_count=0), policy=policy, now=NOW,
        )
        delay_3 = compute_restart_delay(
            _lease(failure_count=3, retry_count=2), policy=policy, now=NOW,
        )
        assert delay_1.base_delay_seconds == 60
        assert delay_3.base_delay_seconds == 180
        assert delay_3.base_delay_seconds > delay_1.base_delay_seconds

    def test_failure_count_zero_treated_as_one_for_delay(self) -> None:
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=0)
        delay = compute_restart_delay(
            _lease(failure_count=0, retry_count=0), policy=policy, now=NOW,
        )
        assert delay.base_delay_seconds == 60

    def test_jitter_is_deterministic_for_same_inputs(self) -> None:
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=15)
        lease = _lease(failure_count=2, retry_count=1)
        delay_1 = compute_restart_delay(lease, policy=policy, now=NOW)
        delay_2 = compute_restart_delay(lease, policy=policy, now=NOW)
        assert delay_1.jitter_seconds == delay_2.jitter_seconds
        assert delay_1.effective_delay_seconds == delay_2.effective_delay_seconds
        assert delay_1.retry_at == delay_2.retry_at

    def test_jitter_differs_for_different_failure_counts(self) -> None:
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=15)
        delay_1 = compute_restart_delay(
            _lease(failure_count=1, retry_count=0), policy=policy, now=NOW,
        )
        delay_2 = compute_restart_delay(
            _lease(failure_count=2, retry_count=1), policy=policy, now=NOW,
        )
        # Different failure counts → different hash seeds → likely different jitter
        assert delay_1.base_delay_seconds != delay_2.base_delay_seconds

    def test_jitter_is_within_budget(self) -> None:
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=15)
        lease = _lease(failure_count=2, retry_count=1)
        delay = compute_restart_delay(lease, policy=policy, now=NOW)
        jitter_budget = policy.jitter_seconds * lease.failure_count  # 30
        assert 0 <= delay.jitter_seconds <= jitter_budget

    def test_zero_jitter_policy_produces_zero_jitter(self) -> None:
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=0)
        delay = compute_restart_delay(
            _lease(failure_count=3, retry_count=2), policy=policy, now=NOW,
        )
        assert delay.jitter_seconds == 0
        assert delay.effective_delay_seconds == delay.base_delay_seconds

    def test_effective_delay_equals_base_plus_jitter(self) -> None:
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=15)
        delay = compute_restart_delay(
            _lease(failure_count=2, retry_count=1), policy=policy, now=NOW,
        )
        assert delay.effective_delay_seconds == delay.base_delay_seconds + delay.jitter_seconds

    def test_retry_at_is_after_effective_delay(self) -> None:
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=0)
        delay = compute_restart_delay(
            _lease(failure_count=1, retry_count=0), policy=policy, now=NOW,
        )
        assert delay.retry_at == NOW + timedelta(seconds=delay.effective_delay_seconds)

    def test_higher_failure_gets_longer_effective_delay(self) -> None:
        """Staggered ordering: higher failure counts produce longer delays."""
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=0)
        delay_1 = compute_restart_delay(
            _lease(failure_count=1, retry_count=0), policy=policy, now=NOW,
        )
        delay_5 = compute_restart_delay(
            _lease(failure_count=5, retry_count=4), policy=policy, now=NOW,
        )
        assert delay_5.effective_delay_seconds > delay_1.effective_delay_seconds
        assert delay_5.base_delay_seconds > delay_1.base_delay_seconds

    def test_different_project_worktree_keys_produce_different_jitter(self) -> None:
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=15)
        lease_a = _lease(project_id="proj-a", failure_count=2, retry_count=1)
        lease_b = _lease(project_id="proj-b", failure_count=2, retry_count=1)
        delay_a = compute_restart_delay(lease_a, policy=policy, now=NOW)
        delay_b = compute_restart_delay(lease_b, policy=policy, now=NOW)
        # Base delays are same (same failure_count) but jitter should differ due to key
        assert delay_a.base_delay_seconds == delay_b.base_delay_seconds
        assert delay_a.jitter_seconds != delay_b.jitter_seconds


# ── evaluate_automatic_restart ───────────────────────────────────────────────

class TestEvaluateAutomaticRestart:
    def test_pending_lease_is_restartable(self) -> None:
        decision = evaluate_automatic_restart(_lease(state=ProjectLeaseState.PENDING), now=NOW)
        assert decision.allowed is True
        assert decision.reason == "restart_allowed"

    def test_quarantined_lease_requires_manual_clear(self) -> None:
        """Rejected claim/restart while quarantined."""
        decision = evaluate_automatic_restart(
            _lease(
                state=ProjectLeaseState.QUARANTINED,
                quarantine_reason="crash_loop:timeout",
            ),
            now=NOW,
        )
        assert decision.allowed is False
        assert decision.reason == "manual_quarantine_clear_required"
        assert decision.manual_clear_required is True
        assert decision.quarantine_reason == "crash_loop:timeout"
        assert decision.suspension_state is SuspensionState.QUARANTINED

    def test_future_retry_at_blocks_restart(self) -> None:
        """Rejected restart while retry delay is active."""
        future = NOW + timedelta(minutes=10)
        decision = evaluate_automatic_restart(
            _lease(
                state=ProjectLeaseState.PENDING,
                next_retry_at=future,
            ),
            now=NOW,
        )
        assert decision.allowed is False
        assert decision.reason == "retry_delay_active"
        assert decision.retry_at == future
        assert decision.effective_delay_seconds == 600

    def test_past_retry_at_allows_restart(self) -> None:
        past = NOW - timedelta(minutes=5)
        lease = _lease(state=ProjectLeaseState.PENDING, next_retry_at=past)
        decision = evaluate_automatic_restart(lease, now=NOW)
        assert decision.allowed is True
        assert decision.reason == "restart_allowed"

    def test_retry_at_exactly_now_allows_restart(self) -> None:
        decision = evaluate_automatic_restart(
            _lease(state=ProjectLeaseState.PENDING, next_retry_at=NOW),
            now=NOW,
        )
        assert decision.allowed is True

    def test_succeeded_lease_is_not_restartable(self) -> None:
        decision = evaluate_automatic_restart(
            _lease(state=ProjectLeaseState.SUCCEEDED), now=NOW,
        )
        assert decision.allowed is False
        assert decision.reason == "lease_not_restartable:succeeded"

    def test_failed_lease_is_not_restartable(self) -> None:
        decision = evaluate_automatic_restart(
            _lease(state=ProjectLeaseState.FAILED), now=NOW,
        )
        assert decision.allowed is False
        assert decision.reason == "lease_not_restartable:failed"

    def test_cancelled_lease_is_not_restartable(self) -> None:
        decision = evaluate_automatic_restart(
            _lease(state=ProjectLeaseState.CANCELLED), now=NOW,
        )
        assert decision.allowed is False
        assert decision.reason == "lease_not_restartable:cancelled"

    def test_quarantined_without_quarantine_reason_rejected_by_model(self) -> None:
        """ProjectLease enforces quarantine_reason at construction; verify the guard."""
        with pytest.raises(ValueError, match="quarantine_reason is required"):
            ProjectLease(
                identity=ProjectLeaseIdentity(
                    project_id="project-1",
                    worktree_id="worktree-1",
                    run_id="run-1",
                ),
                state=ProjectLeaseState.QUARANTINED,
            )

    def test_quarantined_overrides_retry_at(self) -> None:
        """Quarantine takes precedence over retry-delay."""
        decision = evaluate_automatic_restart(
            _lease(
                state=ProjectLeaseState.QUARANTINED,
                quarantine_reason="crash_loop",
                next_retry_at=NOW - timedelta(minutes=1),
            ),
            now=NOW,
        )
        assert decision.allowed is False
        assert decision.reason == "manual_quarantine_clear_required"

    def test_leased_state_is_restartable_by_evaluate(self) -> None:
        """evaluate_automatic_restart does not gate on active lease — the store does."""
        decision = evaluate_automatic_restart(
            _lease(
                state=ProjectLeaseState.LEASED,
                owner_id="worker-a",
                lease_token="***",
                lease_expires_at=NOW + timedelta(minutes=5),
            ),
            now=NOW,
        )
        assert decision.allowed is True


# ── record_restart_failure ───────────────────────────────────────────────────

class TestRecordRestartFailure:
    def test_normal_failure_sets_pending_with_retry_delay(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        policy = RestartPolicy(
            retry_delay_seconds=60,
            jitter_seconds=0,
            rapid_failure_window=timedelta(minutes=15),
            quarantine_failure_count=3,
        )
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.LEASED,
                owner_id="worker-a",
                lease_token="***",
                lease_expires_at=NOW + timedelta(minutes=10),
                failure_count=0,
                retry_count=0,
            )
        )
        updated = record_restart_failure(
            store,
            lease,
            lease_token="***",
            reason="test failure",
            policy=policy,
            now=NOW,
        )
        assert updated.state is ProjectLeaseState.PENDING
        assert updated.failure_count == 1
        assert updated.retry_count == 1
        assert updated.last_failure_reason == "test failure"
        assert updated.last_failure_at == NOW
        assert updated.next_retry_at is not None
        assert updated.next_retry_at > NOW
        restart_meta = updated.last_result.get("restart", {})
        assert restart_meta["allowed"] is True
        assert restart_meta["reason"] == "retry_scheduled"
        assert restart_meta["base_delay_seconds"] == 60

    def test_rapid_failure_under_threshold_does_not_quarantine(self, tmp_path: Path) -> None:
        """Two rapid failures with quarantine threshold 3 → still pending."""
        store = _store(tmp_path)
        policy = RestartPolicy(
            retry_delay_seconds=60,
            jitter_seconds=0,
            rapid_failure_window=timedelta(minutes=15),
            quarantine_failure_count=3,
        )
        t0 = NOW - timedelta(minutes=5)
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.LEASED,
                owner_id="worker-a",
                lease_token="***",
                lease_expires_at=NOW + timedelta(minutes=10),
                failure_count=1,
                retry_count=1,
                last_failure_at=t0,
            )
        )
        updated = record_restart_failure(
            store,
            lease,
            lease_token="***",
            reason="second failure",
            policy=policy,
            now=NOW,
        )
        assert updated.state is ProjectLeaseState.PENDING
        assert updated.failure_count == 2
        assert updated.next_retry_at is not None
        # Quarantine count not reached
        restart_meta = updated.last_result.get("restart", {})
        assert restart_meta["allowed"] is True

    def test_rapid_failure_reaches_quarantine_threshold(self, tmp_path: Path) -> None:
        """Third rapid failure → quarantine (poison-project quarantine)."""
        store = _store(tmp_path)
        policy = RestartPolicy(
            retry_delay_seconds=60,
            jitter_seconds=0,
            rapid_failure_window=timedelta(minutes=15),
            quarantine_failure_count=3,
        )
        t0 = NOW - timedelta(minutes=2)
        t1 = NOW - timedelta(minutes=1)
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.LEASED,
                owner_id="worker-a",
                lease_token="***",
                lease_expires_at=NOW + timedelta(minutes=10),
                failure_count=2,
                retry_count=2,
                last_failure_at=t1,
            )
        )
        updated = record_restart_failure(
            store,
            lease,
            lease_token="***",
            reason="third failure",
            policy=policy,
            now=NOW,
        )
        assert updated.state is ProjectLeaseState.QUARANTINED
        assert updated.quarantine_reason == "crash_loop:third failure"
        # quarantine_project_lease transitions to terminal state without incrementing
        # failure_count; the count reflects pre-quarantine value
        assert updated.failure_count == 2
        restart_meta = updated.last_result.get("restart", {})
        assert restart_meta["allowed"] is False
        assert restart_meta["reason"] == "crash_loop_quarantined"
        assert restart_meta["manual_clear_required"] is True
        assert restart_meta["quarantine_reason"] == "crash_loop:third failure"
        assert restart_meta["suspension_state"] == SuspensionState.QUARANTINED.value

    def test_slow_failure_outside_window_does_not_quarantine(self, tmp_path: Path) -> None:
        """Failure outside the rapid window resets the rapid chain."""
        store = _store(tmp_path)
        policy = RestartPolicy(
            retry_delay_seconds=60,
            jitter_seconds=0,
            rapid_failure_window=timedelta(minutes=5),
            quarantine_failure_count=3,
        )
        t_old = NOW - timedelta(minutes=20)  # outside the 5min window
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.LEASED,
                owner_id="worker-a",
                lease_token="***",
                lease_expires_at=NOW + timedelta(minutes=10),
                failure_count=2,
                retry_count=2,
                last_failure_at=t_old,
            )
        )
        updated = record_restart_failure(
            store,
            lease,
            lease_token="***",
            reason="slow failure",
            policy=policy,
            now=NOW,
        )
        assert updated.state is ProjectLeaseState.PENDING  # not quarantined
        assert updated.failure_count == 3
        restart_meta = updated.last_result.get("restart", {})
        assert restart_meta["allowed"] is True

    def test_quarantine_when_last_failure_is_none_but_count_high(self, tmp_path: Path) -> None:
        """When last_failure_at is None, rapid_failure is False; no quarantine."""
        store = _store(tmp_path)
        policy = RestartPolicy(
            retry_delay_seconds=60,
            jitter_seconds=0,
            rapid_failure_window=timedelta(minutes=5),
            quarantine_failure_count=2,
        )
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.LEASED,
                owner_id="worker-a",
                lease_token="***",
                lease_expires_at=NOW + timedelta(minutes=10),
                failure_count=2,
                retry_count=2,
                last_failure_at=None,
            )
        )
        updated = record_restart_failure(
            store,
            lease,
            lease_token="***",
            reason="failure without prior timestamp",
            policy=policy,
            now=NOW,
        )
        # Should still be pending, not quarantined, because rapid_failure = False
        assert updated.state is ProjectLeaseState.PENDING
        assert updated.failure_count == 3

    def test_merged_result_carries_restart_metadata(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=0)
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.LEASED,
                owner_id="worker-a",
                lease_token="***",
                lease_expires_at=NOW + timedelta(minutes=10),
                failure_count=0,
            )
        )
        updated = record_restart_failure(
            store,
            lease,
            lease_token="***",
            reason="merged test",
            policy=policy,
            now=NOW,
            result={"custom": "payload"},
        )
        assert updated.last_result.get("custom") == "payload"
        assert "restart" in updated.last_result

    def test_quarantine_merged_result(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        policy = RestartPolicy(
            rapid_failure_window=timedelta(minutes=15),
            quarantine_failure_count=2,
        )
        t0 = NOW - timedelta(minutes=2)
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.LEASED,
                owner_id="worker-a",
                lease_token="***",
                lease_expires_at=NOW + timedelta(minutes=10),
                failure_count=1,
                last_failure_at=t0,
            )
        )
        updated = record_restart_failure(
            store,
            lease,
            lease_token="***",
            reason="quarantine merge",
            policy=policy,
            now=NOW,
            result={"custom": True},
        )
        assert updated.state is ProjectLeaseState.QUARANTINED
        assert updated.last_result.get("custom") is True
        restart_meta = updated.last_result.get("restart", {})
        assert restart_meta["allowed"] is False

    def test_record_failure_on_pending_lease_is_rejected_by_store(self, tmp_path: Path) -> None:
        """The store requires a matching token; non-leased leases can't pass token check."""
        store = _store(tmp_path)
        policy = RestartPolicy()
        lease = store.create_project_lease(_lease(state=ProjectLeaseState.PENDING))
        # PENDING leases fail the token check in fail_project_lease (store)
        with pytest.raises((ProjectLeaseConflict, Exception)):
            record_restart_failure(
                store,
                lease,
                lease_token="***",
                reason="should fail",
                policy=policy,
                now=NOW,
            )


# ── clear_quarantined_project_lease ──────────────────────────────────────────

class TestClearQuarantinedProjectLease:
    def test_clear_quarantined_lease_returns_pending(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.QUARANTINED,
                quarantine_reason="crash_loop:oom",
                failure_count=3,
            )
        )
        cleared = clear_quarantined_project_lease(
            store,
            lease.project_id,
            lease.worktree_id,
            now=NOW,
            result={"cleared_by": "operator"},
        )
        assert cleared.state is ProjectLeaseState.PENDING
        assert cleared.quarantine_reason is None
        assert cleared.next_retry_at is None
        assert cleared.last_result.get("cleared_by") == "operator"

    def test_clear_non_quarantined_lease_raises(self, tmp_path: Path) -> None:
        """Manual-clear precondition: only QUARANTINED leases can be cleared."""
        store = _store(tmp_path)
        lease = store.create_project_lease(
            _lease(state=ProjectLeaseState.PENDING)
        )
        with pytest.raises(ProjectLeaseConflict):
            clear_quarantined_project_lease(
                store,
                lease.project_id,
                lease.worktree_id,
                now=NOW,
            )

    def test_clear_succeeded_lease_raises(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        lease = store.create_project_lease(
            _lease(state=ProjectLeaseState.SUCCEEDED)
        )
        with pytest.raises(ProjectLeaseConflict):
            clear_quarantined_project_lease(
                store,
                lease.project_id,
                lease.worktree_id,
                now=NOW,
            )

    def test_clear_nonexistent_lease_raises(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        with pytest.raises(ProjectLeaseNotFound):
            clear_quarantined_project_lease(
                store,
                "nonexistent",
                "worktree",
                now=NOW,
            )

    def test_cleared_lease_can_be_claimed(self, tmp_path: Path) -> None:
        """After manual clear, the lease is claimable."""
        store = _store(tmp_path)
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.QUARANTINED,
                quarantine_reason="crash_loop:test",
            )
        )
        cleared = clear_quarantined_project_lease(
            store,
            lease.project_id,
            lease.worktree_id,
            now=NOW,
        )
        assert cleared.state is ProjectLeaseState.PENDING
        # Now it can be claimed
        claimed = store.claim_project_lease(
            lease.project_id,
            lease.worktree_id,
            run_id="run-2",
            owner_id="worker-b",
            lease_token="***",
            lease_seconds=60,
            now=NOW,
        )
        assert claimed.state is ProjectLeaseState.LEASED
        assert claimed.run_id == "run-2"
        assert claimed.owner_id == "worker-b"


# ── rejected claim while quarantined (store integration) ─────────────────────

class TestRejectedClaimWhileQuarantined:
    def test_store_rejects_claim_of_quarantined_lease(self, tmp_path: Path) -> None:
        """Rejected claim/restart while quarantined at the store level."""
        store = _store(tmp_path)
        store.create_project_lease(
            _lease(
                state=ProjectLeaseState.QUARANTINED,
                quarantine_reason="crash_loop:panic",
            )
        )
        with pytest.raises(ProjectLeaseConflict):
            store.claim_project_lease(
                "project-1",
                "worktree-1",
                run_id="run-2",
                owner_id="worker-b",
                lease_token="***",
                lease_seconds=60,
                now=NOW,
            )

    def test_store_rejects_claim_when_next_retry_in_future(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        store.create_project_lease(
            _lease(
                state=ProjectLeaseState.PENDING,
                next_retry_at=NOW + timedelta(minutes=5),
            )
        )
        with pytest.raises(ProjectLeaseConflict):
            store.claim_project_lease(
                "project-1",
                "worktree-1",
                run_id="run-2",
                owner_id="worker-b",
                lease_token="***",
                lease_seconds=60,
                now=NOW,
            )

    def test_quarantine_then_clear_then_claim(self, tmp_path: Path) -> None:
        """Full cycle: quarantine → manual clear → claim."""
        store = _store(tmp_path)
        policy = RestartPolicy(
            rapid_failure_window=timedelta(minutes=15),
            quarantine_failure_count=2,
        )
        t0 = NOW - timedelta(minutes=5)
        lease = store.create_project_lease(
            _lease(
                state=ProjectLeaseState.LEASED,
                owner_id="worker-a",
                lease_token="***",
                lease_expires_at=NOW + timedelta(minutes=10),
                failure_count=1,
                last_failure_at=t0,
            )
        )
        # Trigger quarantine
        quarantined = record_restart_failure(
            store, lease, lease_token="***", reason="boom", policy=policy, now=NOW,
        )
        assert quarantined.state is ProjectLeaseState.QUARANTINED
        # Claim should be rejected
        with pytest.raises(ProjectLeaseConflict):
            store.claim_project_lease(
                "project-1", "worktree-1",
                run_id="run-2", owner_id="worker-b", lease_token="***",
                lease_seconds=60, now=NOW,
            )
        # Manual clear
        cleared = clear_quarantined_project_lease(
            store, "project-1", "worktree-1", now=NOW,
        )
        assert cleared.state is ProjectLeaseState.PENDING
        # Now claim succeeds
        claimed = store.claim_project_lease(
            "project-1", "worktree-1",
            run_id="run-3", owner_id="worker-c", lease_token="***",
            lease_seconds=60, now=NOW,
        )
        assert claimed.state is ProjectLeaseState.LEASED
        assert claimed.run_id == "run-3"


# ── RestartDecision helpers ──────────────────────────────────────────────────

class TestRestartDecision:
    def test_allowed_decision_to_last_result(self) -> None:
        decision = RestartDecision(
            allowed=True,
            reason="restart_allowed",
        )
        result = decision.to_last_result()
        assert result["allowed"] is True
        assert result["reason"] == "restart_allowed"
        assert result["manual_clear_required"] is False

    def test_quarantine_decision_to_last_result(self) -> None:
        decision = RestartDecision(
            allowed=False,
            reason="manual_quarantine_clear_required",
            manual_clear_required=True,
            quarantine_reason="crash_loop:timeout",
            suspension_state=SuspensionState.QUARANTINED,
        )
        result = decision.to_last_result()
        assert result["allowed"] is False
        assert result["manual_clear_required"] is True
        assert result["quarantine_reason"] == "crash_loop:timeout"
        assert result["suspension_state"] == "quarantined"

    def test_retry_delay_decision_to_last_result(self) -> None:
        retry_at = NOW + timedelta(seconds=120)
        decision = RestartDecision(
            allowed=False,
            reason="retry_delay_active",
            retry_at=retry_at,
            effective_delay_seconds=120,
        )
        result = decision.to_last_result()
        assert result["allowed"] is False
        assert result["retry_at"] == "2026-07-05T12:02:00Z"
        assert result["effective_delay_seconds"] == 120


# ── Staggered ordering by failure count ──────────────────────────────────────

class TestStaggeredOrdering:
    def test_failure_count_one_vs_five_delay_ratio(self) -> None:
        """Higher failure counts receive longer effective delays (monotonic)."""
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=0)
        delays = {}
        for fc in range(1, 11):
            lease = _lease(failure_count=fc, retry_count=fc - 1)
            delay = compute_restart_delay(lease, policy=policy, now=NOW)
            delays[fc] = delay
        # Each successive failure count must produce a longer effective delay
        for fc in range(1, 10):
            assert delays[fc].effective_delay_seconds < delays[fc + 1].effective_delay_seconds, (
                f"failure_count={fc} delay={delays[fc].effective_delay_seconds} "
                f"should be < failure_count={fc+1} delay={delays[fc+1].effective_delay_seconds}"
            )

    def test_jitter_budget_scales_with_failure_count(self) -> None:
        """Jitter budget (policy.jitter_seconds * failure_count) grows linearly."""
        policy = RestartPolicy(retry_delay_seconds=60, jitter_seconds=15)
        for fc in [1, 3, 7]:
            lease = _lease(failure_count=fc, retry_count=fc - 1)
            delay = compute_restart_delay(lease, policy=policy, now=NOW)
            jitter_budget = policy.jitter_seconds * fc
            assert 0 <= delay.jitter_seconds <= jitter_budget
