"""Worker-fleet supervision loop over project leases and native progress."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from arnold.pipeline.native.persistence import (
    NativePersistenceBackend,
    NativePersistenceScope,
)

from .leases import ProjectLease, ProjectLeaseState
from .progress import (
    ProgressClassification,
    ProgressSnapshot,
    ProgressWindows,
    build_progress_snapshot,
)
from .reconcile import ExpiredTakeoverDecision
from .store import ProjectLeaseConflict, ProjectLeaseStore, ProjectLeaseTokenMismatch

__all__ = [
    "LeaseSupervisionDecision",
    "SupervisionLoop",
    "SupervisionLoopConfig",
    "SupervisionScanResult",
]


SnapshotBuilder = Callable[
    [NativePersistenceBackend, NativePersistenceScope, datetime, ProgressWindows],
    ProgressSnapshot,
]
ScopeBuilder = Callable[[ProjectLease], NativePersistenceScope]
ReconcileDecider = Callable[
    [ProjectLease, ProgressSnapshot],
    ExpiredTakeoverDecision,
]
RestartCallback = Callable[
    [ProjectLease, ProgressSnapshot, ExpiredTakeoverDecision],
    None,
]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _json_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SupervisionLoopConfig:
    """Tunable policy for one supervision scan."""

    owner_id: str
    lease_seconds: int = 300
    progress_windows: ProgressWindows = ProgressWindows()
    default_artifact_id: str = "native-run"
    notify_after: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if not self.owner_id:
            raise ValueError("owner_id is required")
        if self.lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if self.notify_after <= timedelta(0):
            raise ValueError("notify_after must be positive")


@dataclass(frozen=True)
class LeaseSupervisionDecision:
    """Decision made for one lease in a scan."""

    lease: ProjectLease
    snapshot: ProgressSnapshot | None
    action: str
    event_kind: str
    reason: str
    human_review_required: bool = False


@dataclass(frozen=True)
class SupervisionScanResult:
    """Summary returned by ``SupervisionLoop.scan_once``."""

    observed_at: datetime
    decisions: tuple[LeaseSupervisionDecision, ...]


class SupervisionLoop:
    """Scan active leases, heartbeat owned work, and escalate stuck runs.

    The loop is deliberately a consumer of existing native persistence and
    project-lease state.  Restart and reconcile execution are injected so this
    module does not own workflow routing or runner internals.
    """

    def __init__(
        self,
        *,
        lease_store: ProjectLeaseStore,
        persistence_backend: NativePersistenceBackend,
        config: SupervisionLoopConfig,
        scope_builder: ScopeBuilder | None = None,
        snapshot_builder: SnapshotBuilder | None = None,
        reconcile_decider: ReconcileDecider | None = None,
        restart_callback: RestartCallback | None = None,
    ) -> None:
        self._lease_store = lease_store
        self._persistence_backend = persistence_backend
        self._config = config
        self._scope_builder = scope_builder or self._default_scope
        self._snapshot_builder = snapshot_builder or _default_snapshot_builder
        self._reconcile_decider = reconcile_decider
        self._restart_callback = restart_callback

    def scan_once(self, *, now: datetime | None = None) -> SupervisionScanResult:
        observed_at = (now or _utc_now()).astimezone(UTC)
        decisions: list[LeaseSupervisionDecision] = []
        for lease in self._lease_store.list_project_leases():
            if lease.state is not ProjectLeaseState.LEASED:
                continue
            decision = self._scan_lease(lease, observed_at=observed_at)
            decisions.append(decision)
        return SupervisionScanResult(
            observed_at=observed_at,
            decisions=tuple(decisions),
        )

    def _scan_lease(
        self,
        lease: ProjectLease,
        *,
        observed_at: datetime,
    ) -> LeaseSupervisionDecision:
        scope = self._scope_builder(lease)
        snapshot = self._snapshot_builder(
            self._persistence_backend,
            scope,
            observed_at,
            self._config.progress_windows,
        )

        if lease.owner_id == self._config.owner_id and lease.has_active_lease(observed_at):
            return self._heartbeat_owned_lease(lease, snapshot, observed_at=observed_at)

        if not lease.has_active_lease(observed_at):
            return self._recover_expired_or_orphaned_lease(
                lease,
                snapshot,
                observed_at=observed_at,
            )

        if snapshot.classification is ProgressClassification.STUCK_BUT_ALIVE:
            return self._escalate_stuck_lease(lease, snapshot, observed_at=observed_at)

        decision = LeaseSupervisionDecision(
            lease=lease,
            snapshot=snapshot,
            action="observe",
            event_kind="supervisor.observe",
            reason=snapshot.classification.value,
        )
        self._emit_decision(decision, observed_at=observed_at)
        return decision

    def _heartbeat_owned_lease(
        self,
        lease: ProjectLease,
        snapshot: ProgressSnapshot,
        *,
        observed_at: datetime,
    ) -> LeaseSupervisionDecision:
        made_progress = (
            snapshot.last_progress_at is not None
            and (
                lease.last_progress_at is None
                or snapshot.last_progress_at > lease.last_progress_at
            )
        )
        stored = self._lease_store.heartbeat_project_lease(
            lease.project_id,
            lease.worktree_id,
            lease.lease_token or "",
            lease_seconds=self._config.lease_seconds,
            progress=made_progress,
            now=observed_at,
        )
        action = "heartbeat_progress" if made_progress else "heartbeat"
        decision = LeaseSupervisionDecision(
            lease=stored,
            snapshot=snapshot,
            action=action,
            event_kind="supervisor.heartbeat",
            reason=snapshot.classification.value,
        )
        self._emit_decision(decision, observed_at=observed_at)
        return decision

    def _recover_expired_or_orphaned_lease(
        self,
        lease: ProjectLease,
        snapshot: ProgressSnapshot,
        *,
        observed_at: datetime,
    ) -> LeaseSupervisionDecision:
        decision = self._reconcile(lease, snapshot)
        if decision.allowed:
            self._restart(lease, snapshot, decision)
            result = self._supervision_result(
                action="restart",
                reason=decision.reason,
                snapshot=snapshot,
                decision=decision,
            )
            stored = self._lease_store.cancel_project_lease(
                lease.project_id,
                lease.worktree_id,
                lease_token=lease.lease_token,
                result=result,
                now=observed_at,
            )
            lease_decision = LeaseSupervisionDecision(
                lease=stored,
                snapshot=snapshot,
                action="restart",
                event_kind="supervisor.restart",
                reason=decision.reason,
            )
        else:
            lease_decision = self._cancel_for_human_review(
                lease,
                snapshot,
                observed_at=observed_at,
                reason=decision.reason,
                decision=decision,
            )
        self._emit_decision(lease_decision, observed_at=observed_at)
        return lease_decision

    def _escalate_stuck_lease(
        self,
        lease: ProjectLease,
        snapshot: ProgressSnapshot,
        *,
        observed_at: datetime,
    ) -> LeaseSupervisionDecision:
        current_level = _supervision_value(lease, "stuck_escalation")
        warned_at = _parse_time(_supervision_value(lease, "warned_at"))
        if current_level is None:
            stored = self._record_escalation(
                lease,
                observed_at=observed_at,
                level="warned",
                snapshot=snapshot,
                extra={"warned_at": _json_time(observed_at)},
            )
            decision = LeaseSupervisionDecision(
                lease=stored,
                snapshot=snapshot,
                action="warn",
                event_kind="supervisor.warn",
                reason="stuck_but_alive",
            )
            self._emit_decision(decision, observed_at=observed_at)
            return decision

        if current_level == "warned" and (
            warned_at is None or observed_at - warned_at >= self._config.notify_after
        ):
            stored = self._record_escalation(
                lease,
                observed_at=observed_at,
                level="notified",
                snapshot=snapshot,
                extra={"notified_at": _json_time(observed_at)},
            )
            decision = LeaseSupervisionDecision(
                lease=stored,
                snapshot=snapshot,
                action="notify",
                event_kind="supervisor.notify",
                reason="stuck_but_alive",
            )
            self._emit_decision(decision, observed_at=observed_at)
            return decision

        if current_level == "notified":
            recovery = self._reconcile(lease, snapshot)
            if recovery.allowed:
                self._restart(lease, snapshot, recovery)
                result = self._supervision_result(
                    action="restart",
                    reason=recovery.reason,
                    snapshot=snapshot,
                    decision=recovery,
                )
                stored = self._lease_store.cancel_project_lease(
                    lease.project_id,
                    lease.worktree_id,
                    lease_token=lease.lease_token,
                    result=result,
                    now=observed_at,
                )
                decision = LeaseSupervisionDecision(
                    lease=stored,
                    snapshot=snapshot,
                    action="restart",
                    event_kind="supervisor.restart",
                    reason=recovery.reason,
                )
            else:
                decision = self._cancel_for_human_review(
                    lease,
                    snapshot,
                    observed_at=observed_at,
                    reason=recovery.reason,
                    decision=recovery,
                )
            self._emit_decision(decision, observed_at=observed_at)
            return decision

        decision = LeaseSupervisionDecision(
            lease=lease,
            snapshot=snapshot,
            action="observe",
            event_kind="supervisor.observe",
            reason="stuck_but_alive",
        )
        self._emit_decision(decision, observed_at=observed_at)
        return decision

    def _record_escalation(
        self,
        lease: ProjectLease,
        *,
        observed_at: datetime,
        level: str,
        snapshot: ProgressSnapshot,
        extra: dict[str, Any],
    ) -> ProjectLease:
        supervision = _supervision_result_base(
            action=level,
            reason="stuck_but_alive",
            snapshot=snapshot,
        )
        supervision["stuck_escalation"] = level
        supervision.update(extra)
        result = dict(lease.last_result or {})
        result["supervision"] = supervision
        updated = replace(
            lease,
            last_result=result,
            updated_at=observed_at,
        )
        return self._lease_store.update_project_lease(
            updated,
            expected_lock_version=lease.lock_version,
        )

    def _cancel_for_human_review(
        self,
        lease: ProjectLease,
        snapshot: ProgressSnapshot,
        *,
        observed_at: datetime,
        reason: str,
        decision: ExpiredTakeoverDecision,
    ) -> LeaseSupervisionDecision:
        result = self._supervision_result(
            action="cancel",
            reason=reason,
            snapshot=snapshot,
            decision=decision,
        )
        result["supervision"]["human_review_required"] = True
        try:
            stored = self._lease_store.cancel_project_lease(
                lease.project_id,
                lease.worktree_id,
                lease_token=lease.lease_token,
                result=result,
                now=observed_at,
            )
        except (ProjectLeaseConflict, ProjectLeaseTokenMismatch):
            stored = self._lease_store.quarantine_project_lease(
                lease.project_id,
                lease.worktree_id,
                reason=reason,
                lease_token=lease.lease_token,
                now=observed_at,
            )
        return LeaseSupervisionDecision(
            lease=stored,
            snapshot=snapshot,
            action="cancel",
            event_kind="supervisor.cancel",
            reason=reason,
            human_review_required=True,
        )

    def _reconcile(
        self,
        lease: ProjectLease,
        snapshot: ProgressSnapshot,
    ) -> ExpiredTakeoverDecision:
        if self._reconcile_decider is not None:
            return self._reconcile_decider(lease, snapshot)
        return ExpiredTakeoverDecision(
            allowed=False,
            reason="reconcile_unavailable",
            previous_owner_id=lease.owner_id,
        )

    def _restart(
        self,
        lease: ProjectLease,
        snapshot: ProgressSnapshot,
        decision: ExpiredTakeoverDecision,
    ) -> None:
        if self._restart_callback is not None:
            self._restart_callback(lease, snapshot, decision)

    def _supervision_result(
        self,
        *,
        action: str,
        reason: str,
        snapshot: ProgressSnapshot,
        decision: ExpiredTakeoverDecision,
    ) -> dict[str, Any]:
        result = {
            "supervision": _supervision_result_base(
                action=action,
                reason=reason,
                snapshot=snapshot,
            )
        }
        result["supervision"]["reconcile"] = decision.to_last_result()
        return result

    def _emit_decision(
        self,
        decision: LeaseSupervisionDecision,
        *,
        observed_at: datetime,
    ) -> None:
        snapshot = decision.snapshot
        payload: dict[str, Any] = {
            "action": decision.action,
            "reason": decision.reason,
            "project_id": decision.lease.project_id,
            "worktree_id": decision.lease.worktree_id,
            "run_id": decision.lease.run_id,
            "owner_id": decision.lease.owner_id,
            "lease_state": decision.lease.state.value,
            "human_review_required": decision.human_review_required,
            "observed_at": _json_time(observed_at),
        }
        if snapshot is not None:
            payload.update(
                {
                    "classification": snapshot.classification.value,
                    "current_path": snapshot.current_path,
                    "current_stage": snapshot.current_stage,
                    "checkpoint_status": snapshot.checkpoint_status,
                    "terminal_status": snapshot.terminal_status,
                    "last_signal_at": _json_time(snapshot.last_signal_at),
                    "last_progress_at": _json_time(snapshot.last_progress_at),
                    "usage_total_tokens": snapshot.usage_delta.total_tokens,
                    "usage_estimated_cost_usd": snapshot.usage_delta.estimated_cost_usd,
                }
            )
        self._persistence_backend.emit_event(
            self._scope_builder(decision.lease),
            kind=decision.event_kind,
            payload=payload,
            event_scope="supervisor",
        )

    def _default_scope(self, lease: ProjectLease) -> NativePersistenceScope:
        return NativePersistenceScope(
            project_id=lease.project_id,
            run_id=lease.run_id,
            artifact_id=self._config.default_artifact_id,
        )


def _default_snapshot_builder(
    backend: NativePersistenceBackend,
    scope: NativePersistenceScope,
    now: datetime,
    windows: ProgressWindows,
) -> ProgressSnapshot:
    return build_progress_snapshot(backend, scope, now=now, windows=windows)


def _supervision_result_base(
    *,
    action: str,
    reason: str,
    snapshot: ProgressSnapshot,
) -> dict[str, Any]:
    return {
        "action": action,
        "reason": reason,
        "classification": snapshot.classification.value,
        "current_path": snapshot.current_path,
        "current_stage": snapshot.current_stage,
        "checkpoint_status": snapshot.checkpoint_status,
        "terminal_status": snapshot.terminal_status,
        "last_signal_at": _json_time(snapshot.last_signal_at),
        "last_progress_at": _json_time(snapshot.last_progress_at),
        "usage_total_tokens": snapshot.usage_delta.total_tokens,
        "usage_estimated_cost_usd": snapshot.usage_delta.estimated_cost_usd,
    }


def _supervision_value(lease: ProjectLease, key: str) -> Any:
    result = lease.last_result
    if not isinstance(result, dict):
        return None
    supervision = result.get("supervision")
    if not isinstance(supervision, dict):
        return None
    return supervision.get(key)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
