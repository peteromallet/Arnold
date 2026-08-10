from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from arnold.supervisor.leases import (
    ProjectLease,
    ProjectLeaseIdentity,
    ProjectLeaseState,
)
from arnold.supervisor.store import (
    ProjectLeaseConflict,
    ProjectLeaseLockConflict,
    ProjectLeaseStore,
    ProjectLeaseTokenMismatch,
)


NOW = datetime(2026, 7, 4, 23, 0, tzinfo=UTC)
StoreFactory = Callable[[], ProjectLeaseStore]


def pending_lease() -> ProjectLease:
    return ProjectLease(
        identity=ProjectLeaseIdentity(
            project_id="project-1",
            worktree_id="worktree-1",
            run_id="run-1",
        ),
        created_at=NOW,
        updated_at=NOW,
    )


class ProjectLeaseStoreConformance:
    def test_store_is_protocol_conformant(self, store_factory: StoreFactory) -> None:
        assert isinstance(store_factory(), ProjectLeaseStore)

    def test_rejects_stale_lock_version(self, store_factory: StoreFactory) -> None:
        store = store_factory()
        created = store.create_project_lease(pending_lease())
        updated = store.update_project_lease(
            replace(created, last_result={"phase": "claimed"}),
            expected_lock_version=created.lock_version,
        )

        assert updated.lock_version == created.lock_version + 1
        with pytest.raises(ProjectLeaseLockConflict):
            store.update_project_lease(
                replace(created, last_result={"phase": "stale"}),
                expected_lock_version=created.lock_version,
            )

    def test_claim_rejects_active_duplicate(
        self,
        store_factory: StoreFactory,
    ) -> None:
        store = store_factory()
        store.create_project_lease(pending_lease())
        claimed = store.claim_project_lease(
            "project-1",
            "worktree-1",
            run_id="run-1",
            owner_id="worker-a",
            lease_token="token-a",
            lease_seconds=60,
            now=NOW,
        )

        assert claimed.state is ProjectLeaseState.LEASED
        assert claimed.lock_version == 1
        assert store.load_project_lease("project-1", "worktree-1") == claimed
        with pytest.raises(ProjectLeaseConflict):
            store.claim_project_lease(
                "project-1",
                "worktree-1",
                run_id="run-2",
                owner_id="worker-b",
                lease_token="token-b",
                lease_seconds=60,
                now=NOW + timedelta(seconds=1),
            )

    def test_expired_takeover_requires_validation_and_records_previous_owner(
        self,
        store_factory: StoreFactory,
    ) -> None:
        store = store_factory()
        store.create_project_lease(pending_lease())
        store.claim_project_lease(
            "project-1",
            "worktree-1",
            run_id="run-1",
            owner_id="worker-a",
            lease_token="token-a",
            lease_seconds=10,
            now=NOW,
        )

        with pytest.raises(ProjectLeaseConflict):
            store.claim_project_lease(
                "project-1",
                "worktree-1",
                run_id="run-2",
                owner_id="worker-b",
                lease_token="token-b",
                lease_seconds=60,
                now=NOW + timedelta(seconds=11),
            )

        takeover = store.claim_project_lease(
            "project-1",
            "worktree-1",
            run_id="run-2",
            owner_id="worker-b",
            lease_token="token-b",
            lease_seconds=60,
            now=NOW + timedelta(seconds=11),
            takeover_validated=True,
        )

        assert takeover.owner_id == "worker-b"
        assert takeover.lease_token == "token-b"
        assert takeover.lock_version == 2
        assert takeover.last_result == {
            "expired_takeover": {
                "previous_owner_id": "worker-a",
                "previous_lease_token": "token-a",
                "previous_lease_expires_at": "2026-07-04T23:00:10Z",
                "takeover_reason": "expired_lease_takeover",
            }
        }

    def test_heartbeat_and_completion_validate_lease_token(
        self,
        store_factory: StoreFactory,
    ) -> None:
        store = store_factory()
        store.create_project_lease(pending_lease())
        store.claim_project_lease(
            "project-1",
            "worktree-1",
            run_id="run-1",
            owner_id="worker-a",
            lease_token="token-a",
            lease_seconds=60,
            now=NOW,
        )

        with pytest.raises(ProjectLeaseTokenMismatch):
            store.heartbeat_project_lease(
                "project-1",
                "worktree-1",
                "wrong-token",
                lease_seconds=60,
                now=NOW + timedelta(seconds=5),
            )

        heartbeat = store.heartbeat_project_lease(
            "project-1",
            "worktree-1",
            "token-a",
            lease_seconds=120,
            progress=True,
            now=NOW + timedelta(seconds=5),
        )
        completed = store.complete_project_lease(
            "project-1",
            "worktree-1",
            lease_token="token-a",
            result={"status": "ok"},
            now=NOW + timedelta(seconds=6),
        )

        assert heartbeat.last_progress_at == NOW + timedelta(seconds=5)
        assert completed.state is ProjectLeaseState.SUCCEEDED
        assert completed.lease_token is None
        assert completed.last_result == {"status": "ok"}
