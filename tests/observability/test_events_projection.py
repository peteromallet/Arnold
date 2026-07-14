from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.observability.events import EventKind, read_events
from arnold_pipelines.megaplan.observability.events_projection import (
    _canonical_dumps,
    project_events,
    project_events_ndjson,
    schema_equivalence_triples,
)
from arnold_pipelines.megaplan.store import FileStore, PlanRepository


def _reference_line(kind: str, phase: str | None, payload: dict) -> str:
    return _canonical_dumps(
        {
            "seq": 999,
            "schema_version": 1,
            "ts_utc": "2099-01-01T00:00:00+00:00",
            "ts_rel_init_s": None,
            "kind": kind,
            "phase": phase,
            "payload": payload,
            "transaction_id": "reference-only",
        }
    )


def _reference_events() -> list[dict]:
    lines = [
        _reference_line(EventKind.PHASE_START, "plan", {"phase": "plan", "model": "sonnet"}),
        _reference_line(EventKind.LLM_CALL_END, "plan", {"model": "sonnet", "cost_usd": 0.01}),
    ]
    return [json.loads(line) for line in lines]


def test_store_events_for_plan_project_schema_equivalent_reference(tmp_path: Path) -> None:
    plan_id = "projection-plan"
    store = FileStore(tmp_path / "store")
    store.record_epic_event(
        epic_id=plan_id,
        transaction_id="tx-1",
        event_type="state_change",
        summary="phase start",
        prior_state=None,
        post_state={
            "event": {
                "kind": EventKind.PHASE_START,
                "phase": "plan",
                "payload": {"phase": "plan", "model": "sonnet"},
            }
        },
    )
    store.append_telemetry_event(
        EventKind.LLM_CALL_END,
        {"phase": "plan", "model": "sonnet", "cost_usd": 0.01},
        scope=plan_id,
    )

    projected = project_events(store, plan_id)
    reference = _reference_events()

    assert schema_equivalence_triples(projected) == schema_equivalence_triples(reference)
    assert "\n".join(_canonical_dumps(event) for event in projected) == "\n".join(
        _canonical_dumps(event) for event in project_events(store, plan_id)
    )


def test_plan_repository_load_lazily_materializes_events_ndjson(tmp_path: Path) -> None:
    plan_id = "projection-plan"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_id
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(json.dumps({"name": plan_id}), encoding="utf-8")

    store = FileStore(tmp_path / "store")
    store.record_epic_event(
        epic_id=plan_id,
        transaction_id="tx-1",
        event_type="state_change",
        summary="phase start",
        prior_state=None,
        post_state={
            "event": {
                "kind": EventKind.PHASE_START,
                "phase": "plan",
                "payload": {"phase": "plan", "model": "sonnet"},
            }
        },
    )

    assert not (plan_dir / "events.ndjson").exists()
    PlanRepository.from_plan_dir(plan_dir, store=store)

    materialized = list(read_events(plan_dir))
    assert schema_equivalence_triples(materialized) == schema_equivalence_triples(
        [json.loads(_reference_line(EventKind.PHASE_START, "plan", {"phase": "plan", "model": "sonnet"}))]
    )


def test_event_writer_appends_projection_after_single_initial_rebuild(
    tmp_path: Path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan.observability import events_projection
    from arnold_pipelines.megaplan.observability.events import EventWriter

    plan_id = "append-plan"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_id
    store = FileStore(tmp_path / "store")
    writer = EventWriter(plan_dir, store=store)
    real_write_projection = events_projection.write_projection
    rebuilds: list[int] = []

    def counted_write_projection(*args, **kwargs):
        rebuilds.append(1)
        return real_write_projection(*args, **kwargs)

    monkeypatch.setattr(events_projection, "write_projection", counted_write_projection)

    writer.emit(EventKind.PHASE_START, phase="execute", payload={"phase": "execute"})
    writer.emit(EventKind.LLM_TOKEN_HEARTBEAT, phase="execute", payload={"tokens": 1})
    writer.emit(EventKind.LLM_TOKEN_HEARTBEAT, phase="execute", payload={"tokens": 2})

    assert len(rebuilds) == 1
    assert (plan_dir / "events.ndjson").read_text(encoding="utf-8") == project_events_ndjson(
        store, plan_id
    )
    assert (plan_dir / ".events.projection.seq").read_text(encoding="ascii") == "2"


def test_event_writer_rebuilds_projection_when_cursor_is_stale(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.observability.events import EventWriter

    plan_id = "recovery-plan"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_id
    store = FileStore(tmp_path / "store")
    writer = EventWriter(plan_dir, store=store)

    writer.emit(EventKind.INIT, payload={"plan_name": plan_id})
    (plan_dir / ".events.projection.seq").write_text("-1", encoding="ascii")
    writer.emit(EventKind.NOTE_ADDED, payload={"note": "recover projection"})

    assert (plan_dir / "events.ndjson").read_text(encoding="utf-8") == project_events_ndjson(
        store, plan_id
    )
    assert [event["seq"] for event in read_events(plan_dir)] == [0, 1]
