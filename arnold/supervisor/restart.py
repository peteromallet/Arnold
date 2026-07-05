"""Restart delay and crash-loop quarantine helpers for project leases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
from typing import Any

from arnold.kernel.suspension import SuspensionState

from .leases import ProjectLease, ProjectLeaseState
from .store import ProjectLeaseStore

__all__ = [
    "RestartDecision",
    "RestartDelay",
    "RestartPolicy",
    "clear_quarantined_project_lease",
    "compute_restart_delay",
    "evaluate_automatic_restart",
    "record_restart_failure",
]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _json_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RestartPolicy:
    """Policy for restart delay and crash-loop quarantine."""

    retry_delay_seconds: int = 60
    jitter_seconds: int = 15
    rapid_failure_window: timedelta = timedelta(minutes=15)
    quarantine_failure_count: int = 3

    def __post_init__(self) -> None:
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")
        if self.jitter_seconds < 0:
            raise ValueError("jitter_seconds must be non-negative")
        if self.rapid_failure_window <= timedelta(0):
            raise ValueError("rapid_failure_window must be positive")
        if self.quarantine_failure_count < 2:
            raise ValueError("quarantine_failure_count must be at least 2")


@dataclass(frozen=True)
class RestartDelay:
    """Computed delay before the next automatic restart attempt."""

    retry_at: datetime
    base_delay_seconds: int
    jitter_seconds: int
    effective_delay_seconds: int


@dataclass(frozen=True)
class RestartDecision:
    """Decision for automatic restart or quarantine handling."""

    allowed: bool
    reason: str
    retry_at: datetime | None = None
    effective_delay_seconds: int = 0
    manual_clear_required: bool = False
    quarantine_reason: str | None = None
    suspension_state: SuspensionState | None = None

    def to_last_result(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "retry_at": _json_time(self.retry_at),
            "effective_delay_seconds": self.effective_delay_seconds,
            "manual_clear_required": self.manual_clear_required,
            "quarantine_reason": self.quarantine_reason,
            "suspension_state": (
                self.suspension_state.value if self.suspension_state is not None else None
            ),
        }


def compute_restart_delay(
    lease: ProjectLease,
    *,
    policy: RestartPolicy,
    now: datetime | None = None,
) -> RestartDelay:
    """Compute deterministic retry delay plus jitter scaled by failure count."""

    timestamp = (now or _utc_now()).astimezone(UTC)
    failure_scale = max(lease.failure_count, 1)
    base_delay_seconds = policy.retry_delay_seconds * failure_scale
    jitter_budget_seconds = policy.jitter_seconds * failure_scale
    if jitter_budget_seconds <= 0:
        jitter_seconds = 0
    else:
        digest = hashlib.sha256(
            f"{lease.project_worktree_key}:{lease.failure_count}:{lease.retry_count}".encode(
                "utf-8"
            )
        ).digest()
        jitter_seconds = int.from_bytes(digest[:8], "big") % (jitter_budget_seconds + 1)
    effective_delay_seconds = base_delay_seconds + jitter_seconds
    return RestartDelay(
        retry_at=timestamp + timedelta(seconds=effective_delay_seconds),
        base_delay_seconds=base_delay_seconds,
        jitter_seconds=jitter_seconds,
        effective_delay_seconds=effective_delay_seconds,
    )


def evaluate_automatic_restart(
    lease: ProjectLease,
    *,
    now: datetime | None = None,
) -> RestartDecision:
    """Return whether an automatic claim/restart is currently allowed."""

    timestamp = (now or _utc_now()).astimezone(UTC)
    if lease.state is ProjectLeaseState.QUARANTINED:
        return RestartDecision(
            allowed=False,
            reason="manual_quarantine_clear_required",
            manual_clear_required=True,
            quarantine_reason=lease.quarantine_reason,
            suspension_state=SuspensionState.QUARANTINED,
        )
    if lease.next_retry_at is not None and lease.next_retry_at > timestamp:
        return RestartDecision(
            allowed=False,
            reason="retry_delay_active",
            retry_at=lease.next_retry_at,
            effective_delay_seconds=max(
                int((lease.next_retry_at - timestamp).total_seconds()),
                0,
            ),
        )
    if lease.state in {
        ProjectLeaseState.SUCCEEDED,
        ProjectLeaseState.FAILED,
        ProjectLeaseState.CANCELLED,
    }:
        return RestartDecision(
            allowed=False,
            reason=f"lease_not_restartable:{lease.state.value}",
        )
    return RestartDecision(
        allowed=True,
        reason="restart_allowed",
    )


def record_restart_failure(
    store: ProjectLeaseStore,
    lease: ProjectLease,
    *,
    lease_token: str,
    reason: str,
    policy: RestartPolicy,
    now: datetime | None = None,
    result: dict[str, Any] | None = None,
) -> ProjectLease:
    """Persist failure handling with retry delay or crash-loop quarantine."""

    timestamp = (now or _utc_now()).astimezone(UTC)
    projected_failure_count = lease.failure_count + 1
    rapid_failure = (
        lease.last_failure_at is not None
        and timestamp - lease.last_failure_at <= policy.rapid_failure_window
    )
    if rapid_failure and projected_failure_count >= policy.quarantine_failure_count:
        quarantine_reason = f"crash_loop:{reason}"
        merged_result = dict(result or {})
        merged_result["restart"] = RestartDecision(
            allowed=False,
            reason="crash_loop_quarantined",
            manual_clear_required=True,
            quarantine_reason=quarantine_reason,
            suspension_state=SuspensionState.QUARANTINED,
        ).to_last_result()
        return store.quarantine_project_lease(
            lease.project_id,
            lease.worktree_id,
            reason=quarantine_reason,
            lease_token=lease_token,
            result=merged_result,
            now=timestamp,
        )

    delay = compute_restart_delay(lease, policy=policy, now=timestamp)
    merged_result = dict(result or {})
    merged_result["restart"] = {
        "allowed": True,
        "reason": "retry_scheduled",
        "retry_at": _json_time(delay.retry_at),
        "effective_delay_seconds": delay.effective_delay_seconds,
        "base_delay_seconds": delay.base_delay_seconds,
        "jitter_seconds": delay.jitter_seconds,
    }
    return store.fail_project_lease(
        lease.project_id,
        lease.worktree_id,
        lease_token=lease_token,
        reason=reason,
        result=merged_result,
        retry_at=delay.retry_at,
        now=timestamp,
    )


def clear_quarantined_project_lease(
    store: ProjectLeaseStore,
    project_id: str,
    worktree_id: str,
    *,
    now: datetime | None = None,
    result: dict[str, Any] | None = None,
) -> ProjectLease:
    """Clear a crash-loop quarantine through the explicit store helper."""

    return store.clear_project_quarantine(
        project_id,
        worktree_id,
        now=now,
        result=result,
    )
