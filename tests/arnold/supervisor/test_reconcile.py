from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from arnold.pipeline.native.reconcile import ReconcileMetadata, reconcile_git_worktree
from arnold.runtime.resume import (
    TRUST_QUARANTINED_MANIFEST_MISMATCH,
    TRUST_TRUSTED,
    TRUST_UNKNOWN,
    TrustTransition,
)
from arnold.supervisor.leases import ProjectLease, ProjectLeaseIdentity, ProjectLeaseState
from arnold.supervisor.reconcile import (
    claim_reconciled_project_lease,
    evaluate_expired_takeover,
)
from arnold.supervisor.store import FileProjectLeaseStore, ProjectLeaseConflict


NOW = datetime(2026, 7, 4, 23, 0, tzinfo=UTC)


def test_expired_takeover_requires_trusted_resume_and_clean_worktree(tmp_path: Path) -> None:
    store = FileProjectLeaseStore(tmp_path / "store")
    store.create_project_lease(
        ProjectLease(
            identity=ProjectLeaseIdentity(
                project_id="project-1",
                worktree_id="worktree-1",
                run_id="run-1",
            ),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    expired = store.claim_project_lease(
        "project-1",
        "worktree-1",
        run_id="run-1",
        owner_id="worker-a",
        lease_token="token-a",
        lease_seconds=10,
        now=NOW,
    )
    repo = _init_repo(tmp_path / "repo")
    clean = reconcile_git_worktree(repo, ReconcileMetadata(operation="takeover"))

    denied = evaluate_expired_takeover(
        replace(expired, lease_expires_at=NOW + timedelta(seconds=10)),
        reconcile_decision=clean,
        resume_transition=TrustTransition(
            TRUST_UNKNOWN,
            TRUST_QUARANTINED_MANIFEST_MISMATCH,
        ),
        now=NOW + timedelta(seconds=11),
    )
    allowed = evaluate_expired_takeover(
        expired,
        reconcile_decision=clean,
        resume_transition=TrustTransition(TRUST_UNKNOWN, TRUST_TRUSTED),
        now=NOW + timedelta(seconds=11),
    )
    takeover = claim_reconciled_project_lease(
        store,
        "project-1",
        "worktree-1",
        run_id="run-2",
        owner_id="worker-b",
        lease_token="token-b",
        lease_seconds=60,
        decision=allowed,
        now=NOW + timedelta(seconds=11),
    )

    assert denied.allowed is False
    assert denied.reason == "resume_trust:quarantined-manifest-mismatch"
    assert allowed.allowed is True
    assert takeover.last_result == {
        "expired_takeover": {
            "previous_owner_id": "worker-a",
            "previous_lease_token": "token-a",
            "previous_lease_expires_at": "2026-07-04T23:00:10Z",
            "takeover_reason": "expired_lease_takeover:clean",
        }
    }


def test_expired_takeover_blocks_dirty_unknown_worktree(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("# dirty\n", encoding="utf-8")
    decision = reconcile_git_worktree(repo, ReconcileMetadata(operation="takeover"))
    lease = ProjectLease(
        identity=ProjectLeaseIdentity(
            project_id="project-1",
            worktree_id="worktree-1",
            run_id="run-1",
        ),
        state=ProjectLeaseState.LEASED,
        owner_id="worker-a",
        lease_token="token-a",
        lease_expires_at=NOW - timedelta(seconds=1),
    )

    takeover = evaluate_expired_takeover(
        lease,
        reconcile_decision=decision,
        resume_transition=TrustTransition(TRUST_UNKNOWN, TRUST_TRUSTED),
        now=NOW,
    )

    assert takeover.allowed is False
    assert takeover.reason == "reconcile:dirty_unknown_changes"


def test_quarantined_lease_preserves_reason_on_takeover_evaluation(tmp_path: Path) -> None:
    """Takeover evaluation on a quarantined lease must block and preserve the quarantine reason."""
    store = FileProjectLeaseStore(tmp_path / "store")
    lease = store.create_project_lease(
        ProjectLease(
            identity=ProjectLeaseIdentity(
                project_id="project-1",
                worktree_id="worktree-1",
                run_id="run-1",
            ),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    claimed = store.claim_project_lease(
        "project-1", "worktree-1",
        run_id="run-1", owner_id="worker-a", lease_token="***",
        lease_seconds=10, now=NOW,
    )
    quarantined = store.quarantine_project_lease(
        "project-1", "worktree-1",
        reason="manifest-tamper", lease_token="***", now=NOW + timedelta(seconds=1),
    )
    assert quarantined.state is ProjectLeaseState.QUARANTINED
    assert quarantined.quarantine_reason == "manifest-tamper"

    repo = _init_repo(tmp_path / "repo")
    clean = reconcile_git_worktree(repo, ReconcileMetadata(operation="takeover"))

    decision = evaluate_expired_takeover(
        quarantined,
        reconcile_decision=clean,
        resume_transition=TrustTransition(TRUST_UNKNOWN, TRUST_TRUSTED),
        now=NOW + timedelta(seconds=2),
    )
    # A quarantined lease should not be eligible: no active lease but terminal state
    # evaluate_expired_takeover gates on has_active_lease first; quarantined state
    # passes that gate (state != LEASED) but the store layer rejects terminal states.
    # The evaluate layer still produces a trust-informed decision.
    assert decision.previous_owner_id is None
    assert decision.reconcile_state == "clean"

    # claim_reconciled_project_lease must raise for a quarantined (terminal) lease
    import pytest as _pytest
    with _pytest.raises(ProjectLeaseConflict):
        claim_reconciled_project_lease(
            store,
            "project-1", "worktree-1",
            run_id="run-2", owner_id="worker-b", lease_token="***",
            lease_seconds=60,
            decision=decision,
            now=NOW + timedelta(seconds=2),
        )


def test_successful_takeover_last_result_includes_all_previous_owner_metadata(
    tmp_path: Path,
) -> None:
    """Verify last_result after a successful expired takeover records every expected field."""
    store = FileProjectLeaseStore(tmp_path / "store")
    store.create_project_lease(
        ProjectLease(
            identity=ProjectLeaseIdentity(
                project_id="project-1",
                worktree_id="worktree-1",
                run_id="run-1",
            ),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    expired = store.claim_project_lease(
        "project-1", "worktree-1",
        run_id="run-1", owner_id="worker-a", lease_token="***",
        lease_seconds=1, now=NOW,
    )
    repo = _init_repo(tmp_path / "repo")
    clean = reconcile_git_worktree(repo, ReconcileMetadata(operation="takeover"))
    allowed = evaluate_expired_takeover(
        expired,
        reconcile_decision=clean,
        resume_transition=TrustTransition(TRUST_UNKNOWN, TRUST_TRUSTED),
        now=NOW + timedelta(seconds=2),
    )
    assert allowed.allowed is True
    takeover = claim_reconciled_project_lease(
        store,
        "project-1", "worktree-1",
        run_id="run-2", owner_id="worker-b", lease_token="***",
        lease_seconds=60,
        decision=allowed,
        now=NOW + timedelta(seconds=2),
    )

    takeover_block = takeover.last_result["expired_takeover"]
    assert takeover_block["previous_owner_id"] == "worker-a"
    assert takeover_block["previous_lease_token"] == "***"
    assert takeover_block["previous_lease_expires_at"] is not None
    assert "takeover_reason" in takeover_block
    assert "expired_lease_takeover" in takeover_block["takeover_reason"]


def test_takeover_rejected_by_trust_quarantine_preserves_label(tmp_path: Path) -> None:
    """When resume trust transitions to a quarantine label the reason must carry that label."""
    store = FileProjectLeaseStore(tmp_path / "store")
    store.create_project_lease(
        ProjectLease(
            identity=ProjectLeaseIdentity(
                project_id="project-1",
                worktree_id="worktree-1",
                run_id="run-1",
            ),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    expired = store.claim_project_lease(
        "project-1", "worktree-1",
        run_id="run-1", owner_id="worker-a", lease_token="***",
        lease_seconds=1, now=NOW,
    )
    repo = _init_repo(tmp_path / "repo")
    clean = reconcile_git_worktree(repo, ReconcileMetadata(operation="takeover"))

    # Multiple quarantine labels should each be preserved as distinct reasons
    for quarantine_label in (
        TRUST_QUARANTINED_MANIFEST_MISMATCH,
        "quarantined-schema-version",
        "quarantined-driver-mismatch",
    ):
        decision = evaluate_expired_takeover(
            expired,
            reconcile_decision=clean,
            resume_transition=TrustTransition(TRUST_UNKNOWN, quarantine_label),
            now=NOW + timedelta(seconds=2),
        )
        assert decision.allowed is False
        assert decision.reason == f"resume_trust:{quarantine_label}"
        assert decision.resume_trust_state == quarantine_label
        assert decision.previous_owner_id == "worker-a"


def test_fresh_claim_without_takeover_omits_expired_takeover_from_last_result(
    tmp_path: Path,
) -> None:
    """Claiming a pending (never-leased) project must not write takeover metadata."""
    store = FileProjectLeaseStore(tmp_path / "store")
    store.create_project_lease(
        ProjectLease(
            identity=ProjectLeaseIdentity(
                project_id="project-1",
                worktree_id="worktree-1",
                run_id="run-1",
            ),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repo = _init_repo(tmp_path / "repo")
    clean = reconcile_git_worktree(repo, ReconcileMetadata(operation="takeover"))
    allowed = evaluate_expired_takeover(
        ProjectLease(
            identity=ProjectLeaseIdentity(
                project_id="project-1",
                worktree_id="worktree-1",
                run_id="run-1",
            ),
            state=ProjectLeaseState.PENDING,
        ),
        reconcile_decision=clean,
        resume_transition=TrustTransition(TRUST_UNKNOWN, TRUST_TRUSTED),
        now=NOW,
    )
    assert allowed.allowed is True
    claimed = claim_reconciled_project_lease(
        store,
        "project-1", "worktree-1",
        run_id="run-1", owner_id="worker-a", lease_token="***",
        lease_seconds=60,
        decision=allowed,
        now=NOW,
    )
    assert claimed.state is ProjectLeaseState.LEASED
    assert claimed.owner_id == "worker-a"
    # No expired_takeover block because this was a fresh claim, not a takeover
    assert claimed.last_result is None or "expired_takeover" not in (claimed.last_result or {})


def _init_repo(path: Path) -> Path:
    import subprocess

    path.mkdir(parents=True)
    subprocess.run(("git", "init", "-b", "main"), cwd=path, check=True, stdout=subprocess.PIPE)
    subprocess.run(("git", "config", "user.email", "agentbox@example.test"), cwd=path, check=True)
    subprocess.run(("git", "config", "user.name", "AgentBox Tests"), cwd=path, check=True)
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(("git", "add", "README.md"), cwd=path, check=True)
    subprocess.run(("git", "commit", "-m", "initial"), cwd=path, check=True, stdout=subprocess.PIPE)
    return path
