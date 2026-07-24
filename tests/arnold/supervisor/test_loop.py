from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native.persistence import NativePersistenceScope, OrderedPersistenceRow
from arnold.supervisor.leases import (
    ProjectLease,
    ProjectLeaseIdentity,
    ProjectLeaseState,
)
from arnold.supervisor.loop import SupervisionLoop, SupervisionLoopConfig
from arnold.supervisor.progress import (
    ProgressClassification,
    ProgressSignal,
    ProgressSnapshot,
    ProgressUsage,
    ProgressWindows,
)
from arnold.supervisor.reconcile import ExpiredTakeoverDecision
from arnold.supervisor.store import FileProjectLeaseStore


def _utc_ts(offset_seconds: int = 0) -> datetime:
    return datetime(2026, 7, 5, 0, 0, tzinfo=UTC) + timedelta(seconds=offset_seconds)


class _EventBackend:
    def __init__(self) -> None:
        self.events: list[tuple[NativePersistenceScope, str, dict[str, Any]]] = []

    def emit_event(
        self,
        scope: NativePersistenceScope,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        phase: str | None = None,
        idempotency_key: str | None = None,
        event_scope: str | None = None,
    ) -> OrderedPersistenceRow:
        self.events.append((scope, kind, dict(payload or {})))
        return OrderedPersistenceRow(
            sequence=len(self.events),
            kind=kind,
            payload=dict(payload or {}),
        )

    def read_events(self, *args, **kwargs) -> list[OrderedPersistenceRow]:
        return []

    def read_audit_records(self, *args, **kwargs) -> list[OrderedPersistenceRow]:
        return []

    def read_trace_artifact(self, *args, **kwargs) -> None:
        return None

    def write_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def read_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def delete_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def read_state_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def write_composite_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def read_composite_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def delete_composite_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def write_human_gate(self, *args, **kwargs) -> None:
        pass

    def read_human_gate(self, *args, **kwargs) -> None:
        pass

    def delete_human_gate(self, *args, **kwargs) -> None:
        pass

    def resolve_resume_surface(self, *args, **kwargs):
        from arnold.pipeline.native.persistence import ResolvedResumeSurface

        return ResolvedResumeSurface(source="none", kind="none", blocked=False)

    def append_audit_record(self, *args, **kwargs) -> OrderedPersistenceRow:
        return OrderedPersistenceRow(sequence=1, payload={}, kind="audit")

    def write_trace_artifact(self, *args, **kwargs) -> None:
        pass


def _lease(
    *,
    owner_id: str = "worker-1",
    token: str = "tok-1",
    expires_at: datetime | None = None,
    last_result: Mapping[str, Any] | None = None,
) -> ProjectLease:
    now = _utc_ts(-600)
    return ProjectLease(
        identity=ProjectLeaseIdentity(
            project_id="project-1",
            worktree_id="worktree-1",
            run_id="run-1",
        ),
        state=ProjectLeaseState.LEASED,
        owner_id=owner_id,
        lease_token=token,
        lease_expires_at=expires_at or _utc_ts(300),
        last_heartbeat_at=now,
        last_progress_at=_utc_ts(-1200),
        last_result=last_result,
        created_at=now,
        updated_at=now,
    )


def _snapshot(
    classification: ProgressClassification,
    *,
    now: datetime = _utc_ts(0),
    last_progress_at: datetime | None = None,
) -> ProgressSnapshot:
    scope = NativePersistenceScope("project-1", "run-1", "native-run")
    progress_at = last_progress_at
    signal_at = now - timedelta(seconds=30)
    return ProgressSnapshot(
        scope=scope,
        observed_at=now,
        classification=classification,
        current_path="/root/provider",
        current_stage="draft",
        checkpoint_status="running",
        terminal_status="running",
        latest_event=ProgressSignal(source="event", observed_at=signal_at, kind="phase.start"),
        latest_stage=ProgressSignal(source="stage", observed_at=progress_at, kind="stage.complete"),
        latest_audit=ProgressSignal(source="audit"),
        latest_checkpoint=ProgressSignal(source="checkpoint"),
        latest_usage=ProgressSignal(source="usage", observed_at=progress_at, kind="token_progress"),
        usage_delta=ProgressUsage(input_tokens=10, output_tokens=5),
        last_signal_at=signal_at,
        last_progress_at=progress_at,
        windows=ProgressWindows(),
    )


def _store_with(tmp_path: Path, lease: ProjectLease) -> FileProjectLeaseStore:
    store = FileProjectLeaseStore(tmp_path)
    store.create_project_lease(lease)
    return store


def test_owned_active_lease_is_heartbeated_and_progress_is_recorded(tmp_path: Path) -> None:
    now = _utc_ts(0)
    store = _store_with(tmp_path, _lease(owner_id="supervisor-a"))
    backend = _EventBackend()
    snapshot = _snapshot(ProgressClassification.HEALTHY, last_progress_at=_utc_ts(-60))

    loop = SupervisionLoop(
        lease_store=store,
        persistence_backend=backend,
        config=SupervisionLoopConfig(owner_id="supervisor-a", lease_seconds=120),
        snapshot_builder=lambda backend, scope, now, windows: snapshot,
    )
    result = loop.scan_once(now=now)

    stored = store.load_project_lease("project-1", "worktree-1")
    assert result.decisions[0].action == "heartbeat_progress"
    assert stored.last_heartbeat_at == now
    assert stored.last_progress_at == now
    assert stored.lease_expires_at == now + timedelta(seconds=120)
    assert backend.events[-1][1] == "supervisor.heartbeat"
    assert backend.events[-1][2]["usage_total_tokens"] == 15


def test_stuck_alive_lease_warns_then_notifies_before_recovery(tmp_path: Path) -> None:
    now = _utc_ts(0)
    store = _store_with(
        tmp_path,
        _lease(owner_id="worker-b", expires_at=now + timedelta(hours=1)),
    )
    backend = _EventBackend()
    snapshot = _snapshot(
        ProgressClassification.STUCK_BUT_ALIVE,
        last_progress_at=_utc_ts(-2400),
    )
    loop = SupervisionLoop(
        lease_store=store,
        persistence_backend=backend,
        config=SupervisionLoopConfig(
            owner_id="supervisor-a",
            notify_after=timedelta(minutes=10),
        ),
        snapshot_builder=lambda backend, scope, now, windows: snapshot,
    )

    first = loop.scan_once(now=now)
    second = loop.scan_once(now=now + timedelta(minutes=11))

    stored = store.load_project_lease("project-1", "worktree-1")
    assert first.decisions[0].action == "warn"
    assert second.decisions[0].action == "notify"
    assert stored.last_result is not None
    assert stored.last_result["supervision"]["stuck_escalation"] == "notified"
    assert [event[1] for event in backend.events] == [
        "supervisor.warn",
        "supervisor.notify",
    ]


def test_notified_stuck_lease_restarts_when_reconcile_is_safe(tmp_path: Path) -> None:
    now = _utc_ts(0)
    lease = _lease(
        owner_id="worker-b",
        last_result={
            "supervision": {
                "stuck_escalation": "notified",
                "warned_at": _utc_ts(-1200).isoformat(),
                "notified_at": _utc_ts(-600).isoformat(),
            }
        },
    )
    store = _store_with(tmp_path, lease)
    backend = _EventBackend()
    snapshot = _snapshot(
        ProgressClassification.STUCK_BUT_ALIVE,
        last_progress_at=_utc_ts(-2400),
    )
    restarts: list[str] = []
    safe = ExpiredTakeoverDecision(
        allowed=True,
        reason="expired_lease_takeover:clean",
        previous_owner_id="worker-b",
        reconcile_state="clean",
    )
    loop = SupervisionLoop(
        lease_store=store,
        persistence_backend=backend,
        config=SupervisionLoopConfig(owner_id="supervisor-a"),
        snapshot_builder=lambda backend, scope, now, windows: snapshot,
        reconcile_decider=lambda lease, snapshot: safe,
        restart_callback=lambda lease, snapshot, decision: restarts.append(decision.reason),
    )

    result = loop.scan_once(now=now)

    stored = store.load_project_lease("project-1", "worktree-1")
    assert result.decisions[0].action == "restart"
    assert stored.state is ProjectLeaseState.CANCELLED
    assert restarts == ["expired_lease_takeover:clean"]
    assert stored.last_result is not None
    assert stored.last_result["supervision"]["action"] == "restart"
    assert backend.events[-1][1] == "supervisor.restart"


def test_expired_unsafe_lease_is_cancelled_for_human_review(tmp_path: Path) -> None:
    now = _utc_ts(0)
    lease = _lease(owner_id="worker-b", expires_at=_utc_ts(-60))
    store = _store_with(tmp_path, lease)
    backend = _EventBackend()
    snapshot = _snapshot(ProgressClassification.DEAD, last_progress_at=None)
    unsafe = ExpiredTakeoverDecision(
        allowed=False,
        reason="reconcile:dirty",
        previous_owner_id="worker-b",
        reconcile_state="dirty",
    )
    loop = SupervisionLoop(
        lease_store=store,
        persistence_backend=backend,
        config=SupervisionLoopConfig(owner_id="supervisor-a"),
        snapshot_builder=lambda backend, scope, now, windows: snapshot,
        reconcile_decider=lambda lease, snapshot: unsafe,
    )

    result = loop.scan_once(now=now)

    stored = store.load_project_lease("project-1", "worktree-1")
    assert result.decisions[0].action == "cancel"
    assert result.decisions[0].human_review_required is True
    assert stored.state is ProjectLeaseState.CANCELLED
    assert stored.last_result is not None
    assert stored.last_result["supervision"]["human_review_required"] is True
    assert stored.last_result["supervision"]["reconcile"]["reconcile_state"] == "dirty"
    assert backend.events[-1][1] == "supervisor.cancel"
