from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from arnold.supervisor.leases import (
    ProjectLease,
    ProjectLeaseIdentity,
    ProjectLeaseState,
    can_transition_project_lease,
    is_terminal_project_lease_state,
)


def test_project_lease_round_trips_full_contract() -> None:
    now = datetime(2026, 7, 4, 23, 0, tzinfo=UTC)
    lease = ProjectLease(
        identity=ProjectLeaseIdentity(
            project_id="project-1",
            worktree_id="worktree-1",
            run_id="run-1",
        ),
        state=ProjectLeaseState.LEASED,
        owner_id="worker-a",
        lease_token="lease-token-1",
        lease_expires_at=now + timedelta(minutes=5),
        last_heartbeat_at=now + timedelta(minutes=1),
        last_progress_at=now + timedelta(minutes=2),
        retry_count=2,
        failure_count=1,
        max_failures=5,
        last_failure_at=now - timedelta(minutes=3),
        next_retry_at=now + timedelta(minutes=10),
        last_failure_reason="network timeout",
        last_result={"status": "recovering", "attempt": 2},
        created_at=now,
        updated_at=now + timedelta(minutes=2),
        lock_version=7,
    )

    payload = lease.to_json()
    restored = ProjectLease.from_json(payload)

    assert restored == lease
    assert restored.project_worktree_key == "project-1:worktree-1"
    assert restored.has_active_lease(now + timedelta(minutes=4))
    assert not restored.has_active_lease(now + timedelta(minutes=6))
    assert payload["lock_version"] == 7


def test_project_lease_state_contract_includes_quarantine_and_lease_identity() -> None:
    assert {
        state.value for state in ProjectLeaseState
    } == {
        "pending",
        "leased",
        "succeeded",
        "failed",
        "cancelled",
        "quarantined",
    }
    assert can_transition_project_lease(
        ProjectLeaseState.PENDING,
        ProjectLeaseState.LEASED,
    )
    assert can_transition_project_lease(
        ProjectLeaseState.LEASED,
        ProjectLeaseState.QUARANTINED,
    )
    assert is_terminal_project_lease_state(ProjectLeaseState.QUARANTINED)

    lease = ProjectLease(
        identity=ProjectLeaseIdentity(
            project_id="project-1",
            worktree_id="worktree-1",
            run_id="run-1",
        ),
        state=ProjectLeaseState.QUARANTINED,
        quarantine_reason="crash loop",
    )

    assert lease.project_id == "project-1"
    assert lease.worktree_id == "worktree-1"
    assert lease.run_id == "run-1"
    assert lease.quarantine_reason == "crash loop"


def test_project_lease_rejects_invalid_leased_and_quarantined_records() -> None:
    now = datetime(2026, 7, 4, 23, 0, tzinfo=UTC)
    identity = ProjectLeaseIdentity(
        project_id="project-1",
        worktree_id="worktree-1",
        run_id="run-1",
    )

    with pytest.raises(ValueError, match="owner_id is required while leased"):
        ProjectLease(
            identity=identity,
            state=ProjectLeaseState.LEASED,
            lease_token="lease-token-1",
            lease_expires_at=now + timedelta(minutes=5),
        )

    with pytest.raises(ValueError, match="quarantine_reason is required"):
        ProjectLease(
            identity=identity,
            state=ProjectLeaseState.QUARANTINED,
        )
