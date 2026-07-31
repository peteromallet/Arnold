"""Supervisor reconcile gates for expired project-lease takeover."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from arnold.pipeline.native.reconcile import (
    ReconcileDecision,
    ReconcileMetadata,
    reconcile_git_worktree,
)
from arnold.runtime.resume import TrustTransition, resume_trust_allows_takeover
from arnold.workflow.native_wbc import begin_native_wbc_attempt

from .leases import ProjectLease
from .store import ProjectLeaseStore

__all__ = [
    "ExpiredTakeoverDecision",
    "claim_reconciled_project_lease",
    "evaluate_expired_takeover",
    "reconcile_worktree_for_takeover",
]


@dataclass(frozen=True)
class ExpiredTakeoverDecision:
    """Decision used to gate an expired project lease takeover."""

    allowed: bool
    reason: str
    previous_owner_id: str | None
    reconcile_state: str | None = None
    resume_trust_state: str | None = None
    detail: str | None = None

    def to_last_result(self) -> dict[str, Any]:
        return {
            "takeover_reason": self.reason,
            "previous_owner_id": self.previous_owner_id,
            "reconcile_state": self.reconcile_state,
            "resume_trust_state": self.resume_trust_state,
            "detail": self.detail,
        }


def reconcile_worktree_for_takeover(
    repo_path: Path | str,
    metadata: ReconcileMetadata | None = None,
    *,
    status_path: Path | str | None = None,
) -> ReconcileDecision:
    """Run the native worktree reconcile gate used before takeover."""
    repo_root = Path(repo_path)
    evidence_root = (
        repo_root / ".git"
        if (repo_root / ".git").exists()
        else Path(status_path)
        if status_path is not None
        else repo_root
    )
    effective_metadata = metadata or ReconcileMetadata(operation="expired_lease_takeover")
    attempt = begin_native_wbc_attempt(
        evidence_root,
        producer_family="arnold_supervisor",
        surface="reconcile_takeover",
        subject={"repo_path": str(repo_path), "operation": effective_metadata.operation},
        metadata={"status_path": str(status_path) if status_path is not None else ""},
    )
    try:
        decision = reconcile_git_worktree(
            repo_path,
            effective_metadata,
            status_path=status_path,
        )
    except BaseException as exc:
        attempt.terminal(
            status="failed",
            outcome="error",
            payload={"error_type": exc.__class__.__name__, "error": str(exc)},
        )
        raise
    attempt.effect(
        "reconcile_decision",
        {"state": decision.state, "blocked": decision.blocked},
    )
    attempt.terminal(
        status="completed",
        outcome=decision.state,
        payload={"detail": decision.detail},
    )
    return decision


def evaluate_expired_takeover(
    lease: ProjectLease,
    *,
    reconcile_decision: ReconcileDecision,
    resume_transition: TrustTransition | None = None,
    current_trust_state: str | None = None,
    now: datetime | None = None,
) -> ExpiredTakeoverDecision:
    """Validate resume trust and worktree cleanliness for an expired lease."""

    if lease.has_active_lease(now):
        return ExpiredTakeoverDecision(
            allowed=False,
            reason="lease_active",
            previous_owner_id=lease.owner_id,
            reconcile_state=reconcile_decision.state,
            resume_trust_state=current_trust_state,
        )
    trust_ok, trust_reason = resume_trust_allows_takeover(
        resume_transition,
        current_trust_state=current_trust_state,
    )
    trust_state = (
        resume_transition.after if resume_transition is not None else current_trust_state
    )
    if not trust_ok:
        return ExpiredTakeoverDecision(
            allowed=False,
            reason=trust_reason,
            previous_owner_id=lease.owner_id,
            reconcile_state=reconcile_decision.state,
            resume_trust_state=trust_state,
            detail=reconcile_decision.detail,
        )
    if reconcile_decision.blocked or not (
        reconcile_decision.continue_execution or reconcile_decision.skip_execution
    ):
        return ExpiredTakeoverDecision(
            allowed=False,
            reason=f"reconcile:{reconcile_decision.state}",
            previous_owner_id=lease.owner_id,
            reconcile_state=reconcile_decision.state,
            resume_trust_state=trust_state,
            detail=reconcile_decision.detail,
        )
    return ExpiredTakeoverDecision(
        allowed=True,
        reason=f"expired_lease_takeover:{reconcile_decision.state}",
        previous_owner_id=lease.owner_id,
        reconcile_state=reconcile_decision.state,
        resume_trust_state=trust_state,
        detail=reconcile_decision.detail,
    )


def claim_reconciled_project_lease(
    store: ProjectLeaseStore,
    project_id: str,
    worktree_id: str,
    *,
    run_id: str,
    owner_id: str,
    lease_token: str,
    lease_seconds: int,
    decision: ExpiredTakeoverDecision,
    now: datetime | None = None,
) -> ProjectLease:
    """Claim a lease using a precomputed supervisor takeover decision."""

    return store.claim_project_lease(
        project_id,
        worktree_id,
        run_id=run_id,
        owner_id=owner_id,
        lease_token=lease_token,
        lease_seconds=lease_seconds,
        now=now,
        takeover_validated=decision.allowed,
        takeover_reason=decision.reason,
    )
