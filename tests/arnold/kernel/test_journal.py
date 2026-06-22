from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.kernel import (
    EventEnvelope,
    EventFamily,
    ManifestReference,
    NDJsonEventJournal,
    ReplayReference,
    fold_event_journal,
    read_event_journal,
)


def _event(
    event_id: str,
    kind: str,
    sequence: int | None = None,
    payload: dict | None = None,
    replay: ReplayReference | None = None,
    reentry_id: str | None = None,
    scope_stack: tuple[str, ...] = (),
    artifact_root: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        family=EventFamily.NODE_LIFECYCLE,
        kind=kind,
        manifest=ManifestReference(alias="demo", manifest_hash="sha256:" + "a" * 64),
        run_id="run-1",
        payload_schema_hash="sha256:" + "b" * 64,
        payload=payload or {},
        sequence=sequence,
        replay=replay,
        reentry_id=reentry_id,
        scope_stack=scope_stack,
        artifact_root=artifact_root,
    )


def test_append_assigns_monotonic_sequences(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)

    first = journal.append(_event("e1", "node-started"))
    second = journal.append(_event("e2", "node-completed"))
    third = journal.append(_event("e3", "node-failed"))

    assert first.sequence == 0
    assert second.sequence == 1
    assert third.sequence == 2


def test_append_is_append_only(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)

    journal.append(_event("e1", "node-started"))
    before = (tmp_path / "events.ndjson").read_text(encoding="utf-8")

    journal.append(_event("e2", "node-completed"))
    after = (tmp_path / "events.ndjson").read_text(encoding="utf-8")

    assert after.startswith(before)
    assert after.count("\n") == 2


def test_serialization_is_deterministic(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    event = _event(
        "e1",
        "node-started",
        payload={"node": "start", "order": 1},
        scope_stack=("parent", "child"),
        reentry_id="reentry-1",
        artifact_root=str(tmp_path),
    )

    written = journal.append(event)
    lines = (tmp_path / "events.ndjson").read_text(encoding="utf-8").strip().split("\n")

    assert len(lines) == 1
    reparsed = json.loads(lines[0])
    assert reparsed["sequence"] == 0
    assert reparsed["scope_stack"] == ["parent", "child"]
    assert reparsed["reentry_id"] == "reentry-1"
    assert reparsed["artifact_root"] == str(tmp_path)
    assert reparsed["family"] == "node-lifecycle"
    # Canonical ordering: keys sorted.
    assert list(json.loads(lines[0]).keys()) == sorted(reparsed.keys())

    # The same logical event serializes to the same bytes when re-appended.
    journal2 = NDJsonEventJournal(tmp_path / "other")
    journal2.append(written)
    lines2 = (tmp_path / "other" / "events.ndjson").read_text(encoding="utf-8").strip().split("\n")
    assert lines[0] == lines2[0]


def test_reader_returns_events_and_quarantines_malformed_lines(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    journal.append(_event("e1", "node-started"))

    # Corrupt the journal with a non-JSON line and a valid-looking but invalid event.
    with open(tmp_path / "events.ndjson", "a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
        fh.write(json.dumps({"event_id": "", "family": "node-lifecycle"}) + "\n")

    events, quarantined = journal.read_with_quarantine()

    assert len(events) == 1
    assert events[0].event_id == "e1"
    assert len(quarantined) == 2
    reasons = {record.reason for record in quarantined}
    assert any("parse" in reason.lower() for reason in reasons)
    assert any("missing" in reason.lower() for reason in reasons)


def test_manifest_hash_lineage_is_enforced(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    first = journal.append(_event("e1", "node-started"))

    second = EventEnvelope(
        event_id="e2",
        family=EventFamily.NODE_LIFECYCLE,
        kind="node-completed",
        manifest=ManifestReference(alias="demo", manifest_hash="sha256:" + "z" * 64),
        run_id="run-1",
        payload_schema_hash="sha256:" + "b" * 64,
        sequence=None,
        artifact_root=str(tmp_path),
    )
    journal.append(second)

    events, quarantined = journal.read_with_quarantine()
    assert events == (first,)
    assert len(quarantined) == 1
    assert "lineage mismatch" in quarantined[0].reason


def test_artifact_root_lineage_is_enforced(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    first = journal.append(_event("e1", "node-started", artifact_root=str(tmp_path)))

    second = _event("e2", "node-completed", artifact_root="/somewhere/else")
    journal.append(second)

    events, quarantined = journal.read_with_quarantine()
    assert events == (first,)
    assert len(quarantined) == 1
    assert "lineage mismatch" in quarantined[0].reason


def test_replay_coordinates_are_preserved(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    event = _event(
        "e1",
        "node-started",
        replay=ReplayReference(journal_uri="other.ndjson", sequence=42, cursor="cursor-1"),
    )

    written = journal.append(event)

    assert written.replay is not None
    assert written.replay.journal_uri == "other.ndjson"
    assert written.replay.sequence == 42
    assert written.replay.cursor == "cursor-1"

    events = journal.read()
    assert events[0].replay == written.replay


def test_read_module_helper(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    journal.append(_event("e1", "node-started"))

    events = read_event_journal(tmp_path)
    assert len(events) == 1
    assert events[0].event_id == "e1"


def test_fold_reduces_valid_events(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    for idx in range(3):
        journal.append(_event(f"e{idx}", "tick", payload={"n": idx}))

    total = journal.fold(0, lambda acc, event: acc + event.payload.get("n", 0))
    assert total == 3

    # Module helper works the same way.
    total2 = fold_event_journal(tmp_path, 0, lambda acc, event: acc + event.payload.get("n", 0))
    assert total2 == 3


def test_sequence_violations_are_quarantined(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    journal.append(_event("e1", "node-started"))

    # Manually inject an out-of-order event.
    with open(tmp_path / "events.ndjson", "a", encoding="utf-8") as fh:
        payload = {
            "event_id": "e0",
            "family": "node-lifecycle",
            "kind": "node-started",
            "manifest": {"alias": "demo", "manifest_hash": "sha256:" + "a" * 64},
            "run_id": "run-1",
            "payload_schema_hash": "sha256:" + "b" * 64,
            "sequence": 0,
            "artifact_root": str(tmp_path),
        }
        fh.write(json.dumps(payload, sort_keys=True) + "\n")

    events, quarantined = journal.read_with_quarantine()
    assert len(events) == 1
    assert len(quarantined) == 1
    assert "sequence violation" in quarantined[0].reason


def test_quarantine_record_can_be_persisted(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    from arnold.kernel import JournalQuarantineRecord

    record = JournalQuarantineRecord(line_number=7, raw_line="bad", reason="parse error")
    path = journal.quarantine(record)

    assert path.exists()
    persisted = json.loads(path.read_text(encoding="utf-8").strip())
    assert persisted["line_number"] == 7
    assert persisted["raw_line"] == "bad"


def test_reader_skips_blank_lines(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    journal.append(_event("e1", "node-started"))

    with open(tmp_path / "events.ndjson", "a", encoding="utf-8") as fh:
        fh.write("\n\n")

    events = journal.read()
    assert len(events) == 1
