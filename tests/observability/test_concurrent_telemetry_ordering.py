from __future__ import annotations

import threading
from pathlib import Path

from arnold.pipelines.megaplan.observability.events import EventKind, EventWriter, emit, read_events
from arnold.pipelines.megaplan.store.file import FileStore


def test_concurrent_telemetry_ordering_preserves_lines_and_seq(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    writers = [EventWriter(plan_dir), EventWriter(plan_dir)]

    def emit_many(writer_idx: int) -> None:
        writer = writers[writer_idx]
        for event_idx in range(100):
            writer.emit(
                EventKind.LLM_TOKEN_HEARTBEAT,
                phase="execute",
                payload={"writer": writer_idx, "event_idx": event_idx},
            )

    threads = [threading.Thread(target=emit_many, args=(idx,)) for idx in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    events = list(read_events(plan_dir, kinds=[EventKind.LLM_TOKEN_HEARTBEAT]))
    assert len(events) == 200
    assert len({event["seq"] for event in events}) == 200
    assert all(event["store_method"] == "append_telemetry_event" for event in events)
    assert all(event.get("transaction_id") for event in events)

    by_writer: dict[int, list[int]] = {0: [], 1: []}
    for event in events:
        payload = event["payload"]
        by_writer[payload["writer"]].append(payload["event_idx"])
    assert by_writer[0] == list(range(100))
    assert by_writer[1] == list(range(100))


def test_emit_routes_event_kinds_through_store_methods(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    store = FileStore(tmp_path / "store")

    emit(EventKind.INIT, plan_dir, phase="prep", payload={"a": 1}, store=store)
    emit(EventKind.LOCK_ACQUIRED, plan_dir, phase="prep", payload={"b": 2}, store=store)
    emit(EventKind.LLM_TOKEN_HEARTBEAT, plan_dir, phase="execute", payload={"c": 3}, store=store)

    events = list(read_events(plan_dir))
    assert [event["kind"] for event in events] == [
        EventKind.INIT,
        EventKind.LOCK_ACQUIRED,
        EventKind.LLM_TOKEN_HEARTBEAT,
    ]
    assert [event["store_method"] for event in events] == [
        "record_epic_event",
        "log_system_event",
        "append_telemetry_event",
    ]
    assert [event["seq"] for event in events] == [0, 1, 2]
