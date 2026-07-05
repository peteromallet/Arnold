from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from arnold.supervisor.leases import (
    ProjectLease,
    ProjectLeaseIdentity,
    ProjectLeaseState,
)
from arnold.supervisor.store import (
    FileProjectLeaseStore,
    ProjectLeaseConflict,
    ProjectLeaseLockConflict,
    ProjectLeaseStore,
    ProjectLeaseTokenMismatch,
)
from tests.arnold.supervisor.project_lease_store_conformance import (
    ProjectLeaseStoreConformance,
)


NOW = datetime(2026, 7, 4, 23, 0, tzinfo=UTC)


def _pending_lease() -> ProjectLease:
    return ProjectLease(
        identity=ProjectLeaseIdentity(
            project_id="project-1",
            worktree_id="worktree-1",
            run_id="run-1",
        ),
        created_at=NOW,
        updated_at=NOW,
    )


def test_file_project_lease_store_is_protocol_conformant(tmp_path: Path) -> None:
    store = FileProjectLeaseStore(tmp_path)

    assert isinstance(store, ProjectLeaseStore)


def test_file_project_lease_store_rejects_stale_lock_version(tmp_path: Path) -> None:
    store = FileProjectLeaseStore(tmp_path)
    created = store.create_project_lease(_pending_lease())
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


def test_file_project_lease_claim_rejects_active_duplicate_across_reloads(
    tmp_path: Path,
) -> None:
    store = FileProjectLeaseStore(tmp_path)
    store.create_project_lease(_pending_lease())
    claimed = store.claim_project_lease(
        "project-1",
        "worktree-1",
        run_id="run-1",
        owner_id="worker-a",
        lease_token="token-a",
        lease_seconds=60,
        now=NOW,
    )
    reopened = FileProjectLeaseStore(tmp_path)

    assert claimed.state is ProjectLeaseState.LEASED
    assert claimed.lock_version == 1
    assert reopened.load_project_lease("project-1", "worktree-1") == claimed
    with pytest.raises(ProjectLeaseConflict):
        reopened.claim_project_lease(
            "project-1",
            "worktree-1",
            run_id="run-2",
            owner_id="worker-b",
            lease_token="token-b",
            lease_seconds=60,
            now=NOW + timedelta(seconds=1),
        )


def test_concurrent_claims_never_both_receive_active_tokens(tmp_path: Path) -> None:
    FileProjectLeaseStore(tmp_path).create_project_lease(_pending_lease())

    def claim(owner: str) -> str:
        store = FileProjectLeaseStore(tmp_path)
        lease = store.claim_project_lease(
            "project-1",
            "worktree-1",
            run_id=f"run-{owner}",
            owner_id=owner,
            lease_token=f"token-{owner}",
            lease_seconds=60,
            now=NOW,
        )
        return lease.lease_token or ""

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim, "a"), pool.submit(claim, "b")]
        results = []
        failures = 0
        for future in futures:
            try:
                results.append(future.result())
            except ProjectLeaseConflict:
                failures += 1

    stored = FileProjectLeaseStore(tmp_path).load_project_lease(
        "project-1",
        "worktree-1",
    )
    assert len(results) == 1
    assert failures == 1
    assert stored.has_active_lease(NOW + timedelta(seconds=30))
    assert stored.lease_token == results[0]


def test_expired_takeover_requires_validation_and_records_previous_owner(
    tmp_path: Path,
) -> None:
    store = FileProjectLeaseStore(tmp_path)
    store.create_project_lease(_pending_lease())
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


def test_heartbeat_and_completion_validate_lease_token(tmp_path: Path) -> None:
    store = FileProjectLeaseStore(tmp_path)
    store.create_project_lease(_pending_lease())
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


class TestFileProjectLeaseStoreConformance(ProjectLeaseStoreConformance):
    @pytest.fixture
    def store_factory(self, tmp_path: Path):
        return lambda: FileProjectLeaseStore(tmp_path)
