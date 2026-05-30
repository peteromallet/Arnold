"""M4 T10 — EventSink + envelope schema_version + LOUD decode tests."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from megaplan.observability import (
    EventEnvelope,
    EventSink,
    NdjsonBackend,
    StoreBackend,
)
from megaplan.observability.events import emit, read_events


def test_event_envelope_pinned_schema_version():
    env = EventEnvelope(kind="test", payload={"a": 1})
    assert env.schema_version == 1
    assert env.scope is None and env.phase is None and env.idempotency_key is None


def test_ndjson_envelope_has_schema_version_and_optional_run_id(tmp_path):
    emit("test_kind", tmp_path, phase="plan", payload={"x": 1})
    line = (tmp_path / "events.ndjson").read_text(encoding="utf-8").splitlines()[0]
    obj = json.loads(line)
    assert obj["schema_version"] == 1
    # run_id is omitted when no envelope is in scope.
    assert "run_id" not in obj
    assert obj["phase"] == "plan"
    assert obj["payload"] == {"x": 1}


def test_ndjson_backend_emits_through_event_writer(tmp_path):
    backend = NdjsonBackend(tmp_path)
    backend.emit("ndjson_kind", payload={"k": "v"}, phase="prep",
                 scope="ep-1", idempotency_key="idem-1")
    events = list(read_events(tmp_path))
    assert len(events) == 1
    assert events[0]["kind"] == "ndjson_kind"
    assert events[0]["phase"] == "prep"
    # scope + idempotency_key fold into payload so the journal schema is unchanged.
    assert events[0]["payload"]["scope"] == "ep-1"
    assert events[0]["payload"]["idempotency_key"] == "idem-1"
    assert events[0]["schema_version"] == 1


def test_store_backend_projects_scope_to_epic_id():
    captured: dict = {}

    class FakeStore:
        def record_epic_event(self, **fields):
            captured.update(fields)
            return fields

    sink = StoreBackend(FakeStore())
    sink.emit("store_kind", payload={"p": 1}, scope="epic-7",
              phase="review", idempotency_key="i-9")
    assert captured["kind"] == "store_kind"
    assert captured["epic_id"] == "epic-7"
    assert captured["phase"] == "review"
    assert captured["idempotency_key"] == "i-9"
    # No run_id when ContextVar is unseated.
    assert "run_id" not in captured


def test_both_backends_protocol_satisfied():
    nb = NdjsonBackend(Path("/tmp"))
    sb = StoreBackend(SimpleNamespace(record_epic_event=lambda **k: None))
    assert callable(getattr(nb, "emit", None))
    assert callable(getattr(sb, "emit", None))


def test_read_events_decode_silent_when_unified_emit_off(tmp_path, monkeypatch):
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    monkeypatch.delenv("MEGAPLAN_UNIFIED_EMIT", raising=False)
    # Write a good event then a corrupt line.
    emit("ok", tmp_path, payload={})
    with open(tmp_path / "events.ndjson", "a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")
    # Flag-off: silent skip preserved.
    assert len(list(read_events(tmp_path))) == 1


def test_read_events_decode_loud_when_unified_emit_on(tmp_path, monkeypatch):
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    emit("ok", tmp_path, payload={})
    with open(tmp_path / "events.ndjson", "a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")
    with pytest.raises(RuntimeError, match="EVENTS_NDJSON_DECODE_ERROR"):
        list(read_events(tmp_path))
