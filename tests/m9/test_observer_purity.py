"""M9 observer-purity tests.

Observer reads may compute projections and diagnostics, but they must not append
progress, activity, lifecycle, delivery, repair, heartbeat-refresh, or liveness
evidence as a side effect.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from arnold.workflow.attempt_ledger_store import (
    AppendResult,
    GateStatus,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)
from arnold.workflow.wbc_queries import WbcQueries
from arnold_pipelines.megaplan.authority.views import derive_publication_view, derive_runner_view
from arnold_pipelines.megaplan.cloud.current_target import _collect_target_evidence_gaps
from arnold_pipelines.megaplan.observability.projection_rebuild import (
    ProjectionRegistry,
    capture_source_cursor_vector,
    compare_all_projections,
    rebuild_all_projections,
)
from arnold_pipelines.megaplan.watchdog.correlate import classify_worker_liveness
from arnold_pipelines.megaplan.watchdog.processes import ProcessRecord


_FORBIDDEN_OBSERVER_WRITES = (
    "append_progress_event",
    "record_epic_event",
    "append_telemetry_event",
    "log_system_event",
    "heartbeat_lease",
    "heartbeat_project_lease",
    "record_delivery",
    "append_delivery_event",
    "record_repair_event",
    "append_repair_event",
    "refresh_heartbeat",
    "append_liveness_event",
)


class MutatingObserverCall(RuntimeError):
    pass


class TripwireStore:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        if name in _FORBIDDEN_OBSERVER_WRITES:
            def _blocked(*_args: Any, **_kwargs: Any) -> None:
                self.calls.append(name)
                raise MutatingObserverCall(name)

            return _blocked
        raise AttributeError(name)


@pytest.fixture
def no_observer_writes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def blocked(name: str) -> Any:
        def _raise(*_args: Any, **_kwargs: Any) -> None:
            calls.append(name)
            raise MutatingObserverCall(name)

        return _raise

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.observability.events.emit",
        blocked("events.emit"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.observability.events.append_telemetry_event",
        blocked("events.append_telemetry_event"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.observability.events.EventWriter.emit",
        blocked("EventWriter.emit"),
    )
    return calls


def _make_identity(attempt_id: str) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-m9",
        run_id="run-m9",
        graph_revision="rev-m9",
        attempt_ordinal=1,
        attempt_id=attempt_id,
    )


def _make_event(
    attempt_id: str,
    *,
    event_type: AttemptEventType,
    idempotency_key: str,
    sequence: int,
    causal_predecessor_sequence: int = 0,
) -> LedgerEvent:
    outcome = None
    if event_type == AttemptEventType.COMPLETED:
        outcome = AttemptOutcome.SUCCEEDED
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=_make_identity(attempt_id),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="1"),
        versions=VersionSet(code_version="c"),
        grant_ref=GrantRef(grant_id="grant-1", decision_id="decision-1"),
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor_sequence,
        append_position=sequence - 1,
        occurred_at="2026-07-21T00:00:00Z",
        observed_at="2026-07-21T00:00:01Z",
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
    )


def _append(
    store: SqliteAttemptLedgerStore,
    attempt_id: str,
    event_type: AttemptEventType,
    idempotency_key: str,
    sequence: int,
    causal_predecessor_sequence: int = 0,
) -> AppendResult:
    return store.append_event(
        attempt_id,
        _make_event(
            attempt_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            sequence=sequence,
            causal_predecessor_sequence=causal_predecessor_sequence,
        ),
    )


def _store_event_count(store: SqliteAttemptLedgerStore, attempt_id: str) -> int:
    return len(store.read_events(attempt_id))


def test_wbc_observer_queries_do_not_append_or_refresh_evidence(
    no_observer_writes: list[str],
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        attempt_id = str(uuid.uuid4())
        store = SqliteAttemptLedgerStore(Path(tmp) / "wbc.db")
        try:
            _append(store, attempt_id, AttemptEventType.STARTED, "idem-start", 1)
            _append(store, attempt_id, AttemptEventType.COMPLETED, "idem-done", 2, 1)
            before_count = _store_event_count(store, attempt_id)
            before_cursor = store.query_source_cursor(attempt_id, "default")

            queries = WbcQueries(
                store,
                context={
                    "environment": "test",
                    "session": "session-observer",
                    "chain": "CHAIN-01",
                    "plan_revision": "rev-m9",
                    "phase": "execute",
                    "task": "T32",
                    "boundary_id": "observer-purity",
                },
            )

            assert queries.query_start_gate(attempt_id).status == GateStatus.VERIFIED
            assert queries.query_terminal_gate(attempt_id).status == GateStatus.VERIFIED
            assert queries.query_ledger(attempt_id).status == GateStatus.VERIFIED
            assert queries.query_events(attempt_id).status == GateStatus.VERIFIED
            assert queries.query_gaps(attempt_id).status == GateStatus.INCOMPLETE
            assert queries.query_source_cursor(attempt_id).attempt_id == attempt_id
            assert queries.query_persistence_diagnostics(attempt_id) == []

            assert _store_event_count(store, attempt_id) == before_count
            assert store.query_source_cursor(attempt_id, "default") == before_cursor
            assert no_observer_writes == []
        finally:
            store.close()


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_projection_observer_rebuilds_do_not_append_progress_or_activity(
    tmp_path: Path,
    no_observer_writes: list[str],
) -> None:
    source = tmp_path / "source.jsonl"
    records = (
        {"seq": 1, "payload": {"status": "running"}},
        {"seq": 2, "payload": {"status": "done"}},
    )
    _write_jsonl(source, records)
    source_before = source.read_bytes()

    def builder(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return {
            "projection_id": "observer-projection",
            "authority": "non_authoritative_rebuild_projection",
            "view": dict(items[-1]["payload"]) if items else {"status": "unknown"},
        }

    registry = ProjectionRegistry()
    registry.register("observer-projection", builder, source_path=source)
    views = rebuild_all_projections(registry)
    cursor_vector = capture_source_cursor_vector(registry)
    reports = compare_all_projections(registry, existing_views=views)

    assert tuple(views) == ("observer-projection",)
    assert tuple(cursor_vector) == ("observer-projection",)
    assert reports["observer-projection"].parity is True
    assert source.read_bytes() == source_before
    assert no_observer_writes == []


def test_liveness_and_marker_observers_do_not_append_heartbeat_or_liveness_evidence(
    no_observer_writes: list[str],
) -> None:
    tripwire = TripwireStore()

    liveness = classify_worker_liveness(
        ProcessRecord(
            pid=222,
            cmdline="arnold --session S1 m9",
            category="arnold",
            is_live=True,
            session_token="S1",
            birth_time_seconds=50.0,
        ),
        attempt_session_token="S1",
        attempt_start_epoch=100.0,
        runner_lease_ref=None,
        heartbeat_fresh=False,
        heartbeat_age_seconds=900.0,
        wbc_attempt_identity_supplied=True,
        source_cursor_vector={"wbc": "cursor"},
    )
    runner = derive_runner_view(
        (
            {
                "id": "heartbeat-1",
                "type": "heartbeat",
                "source": "cloud/heartbeat.json",
                "state": "live",
                "identity": "worker-1",
                "expected_identity": "worker-1",
                "heartbeat_age_seconds": 900,
            },
        ),
        expected_identity="worker-1",
    )
    marker_gaps = _collect_target_evidence_gaps(
        {"workspace": "/workspace/demo", "plan_name": "old-plan"},
        stale_evidence=[{"kind": "stale_marker_plan_ref", "path": "/markers/session.json"}],
        marker_present=True,
        tmux_live=False,
    )

    assert liveness.classification == "hung"
    assert liveness.evidence_gaps["heartbeat_freshness"]["evidence_status"] == "stale"
    assert runner.status == "stale"
    assert marker_gaps["marker_plan_ref"]["evidence_status"] == "stale"
    assert tripwire.calls == []
    assert no_observer_writes == []


def test_publication_and_runner_views_are_pure_even_with_store_write_tripwires(
    no_observer_writes: list[str],
) -> None:
    tripwire = TripwireStore()
    publication = derive_publication_view(
        (
            {
                "source": "git/status.json",
                "branch": "feature/m9",
                "branch_ancestry": "unknown",
                "dirty_workspace": True,
                "pushed_sha": None,
                "pull_request": None,
                "auth": False,
                "no_push": True,
            },
        )
    )
    runner = derive_runner_view(())

    assert publication.status == "blocked"
    assert publication.to_dict()["read_only"] is True
    assert runner.status == "unknown"
    assert runner.to_dict()["read_only"] is True
    assert tripwire.calls == []
    assert no_observer_writes == []
