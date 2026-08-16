"""Focused Maintenance ledger tests (M2, T12).

These tests exercise the Maintenance ledger facade over the existing incident
``NdjsonEventJournal``: strict-only persistence, bounded redacted dead
lettering on primary I/O failure, and at-most-once replay with append-only
dispositions.  The suite is centered on the fail-closed contract (SC12): no
primary or dead-letter failure may be reported as success, and replay may
append the original logical event at most once without rewriting history.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.incident.ledger import MaintenanceEventConflict
from arnold_pipelines.megaplan.maintenance.events import (
    ClassifierInfo,
    DetectionEvent,
    MaintenanceEvent,
    OccurrenceBudget,
    RootCauseCluster,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EventWindow,
    UtcTime,
    Watermark,
    canonical_digest,
    canonical_dumps,
    canonical_json,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.ledger import (
    DEAD_LETTER_SCHEMA_VERSION,
    MAX_DEAD_LETTER_BYTES,
    DeadLetterSinkFailure,
    FailureType,
    MaintenanceAppendFailure,
    MaintenanceLedger,
    ReplayOutcome,
    ReplayReport,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    occurrence_id: str = "occ-m1",
    event_id: str = "evt-m1",
    *,
    extensions: dict | None = None,
) -> MaintenanceEvent:
    return MaintenanceEvent.build(
        event_id=event_id,
        occurrence_id=occurrence_id,
        observed_at=datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc),
        event_time=datetime(2026, 8, 15, 10, 15, tzinfo=timezone.utc),
        window=EventWindow(
            start=UtcTime("2026-08-15T10:00:00+00:00"),
            end=UtcTime("2026-08-15T11:00:00+00:00"),
        ),
        watermark=Watermark("2026-08-15T10:30:00+00:00"),
        classifier=ClassifierInfo(classifier_version="v1", confidence=0.9),
        cluster=RootCauseCluster(signature="sig-1", cluster_id="c-1"),
        budget=OccurrenceBudget(max_attempts=3, attempts_used=1),
        payload=DetectionEvent(detection_kind="watchdog", subject="chain:session"),
        environment="production",
        extensions=extensions,
    )


def _recompute_replay_id(idempotency_key: str, digest: str) -> str:
    return hashlib.sha256(
        canonical_json([idempotency_key, digest]).encode("utf-8")
    ).hexdigest()


def _read_ndjson(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _fail_primary(monkeypatch: pytest.MonkeyPatch, ledger: MaintenanceLedger) -> None:
    """Make the next primary append raise OSError (simulated disk failure)."""

    def _disk_full(*_args: object, **_kwargs: object) -> dict:
        raise OSError("disk full")

    monkeypatch.setattr(ledger._incident._journal, "_emit_locked", _disk_full)


# ---------------------------------------------------------------------------
# Strict-only persistence
# ---------------------------------------------------------------------------


def test_append_persists_strict_event_and_lookup(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)
    event = _make_event()

    appended = ledger.append(event)

    assert ledger.events_path == tmp_path / ".megaplan" / "incident-ledger" / "events.jsonl"
    assert ledger.events_path.exists()
    assert appended["kind"] == "incident.detection"
    assert appended["idempotency_key"] == "occ-m1"
    records = _read_ndjson(ledger.events_path)
    assert len(records) == 1
    assert records[0]["payload"]["occurrence_id"] == "occ-m1"
    assert ledger._incident.lookup_maintenance_event("occ-m1") == appended
    assert not ledger.dead_letter_path.exists()
    assert not ledger.disposition_path.exists()


def test_append_accepts_canonical_dict(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)
    event = _make_event()
    as_dict = json.loads(canonical_dumps(event))

    appended = ledger.append(as_dict)

    assert appended["payload"] == event.model_dump(mode="json")


def test_append_rejects_non_strict_event_before_writing(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)
    data = _make_event().model_dump(mode="json")
    del data["budget"]

    with pytest.raises(ValueError, match="maintenance event strict decode failed"):
        ledger.append(data)

    assert not ledger.events_path.exists()
    assert not ledger.dead_letter_path.exists()


def test_append_rejects_non_event_types(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)

    with pytest.raises(ValueError, match="MaintenanceEvent or a canonical dict"):
        ledger.append("not-an-event")  # type: ignore[arg-type]

    assert not ledger.events_path.exists()


# ---------------------------------------------------------------------------
# Duplicates and conflicts (never dead-lettered)
# ---------------------------------------------------------------------------


def test_exact_duplicate_returns_prior_sequence(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)
    event = _make_event()

    first = ledger.append(event)
    second = ledger.append(event)

    assert second["seq"] == first["seq"]
    assert len(_read_ndjson(ledger.events_path)) == 1
    assert not ledger.dead_letter_path.exists()


def test_divergent_duplicate_raises_conflict_without_dead_letter(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)
    ledger.append(_make_event(occurrence_id="occ-m1", event_id="evt-m1"))

    divergent = _make_event(occurrence_id="occ-m1", event_id="evt-m1-different")

    with pytest.raises(MaintenanceEventConflict, match="idempotency conflict"):
        ledger.append(divergent)

    records = _read_ndjson(ledger.events_path)
    assert len(records) == 1
    assert records[0]["payload"]["event_id"] == "evt-m1"
    assert not ledger.dead_letter_path.exists()


# ---------------------------------------------------------------------------
# Failure injection → bounded redacted dead letter
# ---------------------------------------------------------------------------


def test_primary_failure_writes_replayable_dead_letter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = MaintenanceLedger(tmp_path)
    event = _make_event()
    digest = canonical_digest(event)
    _fail_primary(monkeypatch, ledger)

    with pytest.raises(MaintenanceAppendFailure) as exc_info:
        ledger.append(event)

    # Primary event was NOT committed.
    assert not ledger.events_path.exists()
    # The raised failure carries the written dead letter and is not success.
    assert exc_info.value.dead_letter is not None
    assert exc_info.value.primary_error is not None

    dead_letters = _read_ndjson(ledger.dead_letter_path)
    assert len(dead_letters) == 1
    record = dead_letters[0]
    assert record["schema_version"] == DEAD_LETTER_SCHEMA_VERSION
    assert record["idempotency_key"] == "occ-m1"
    assert record["event_kind"] == "detection"
    assert record["digest"] == digest
    assert record["failure_type"] == FailureType.WRITE_FAILURE.value
    assert record["replay_id"] == _recompute_replay_id("occ-m1", digest)
    # Canonical bytes round-trip the ORIGINAL logical event byte-for-byte.
    assert strict_loads(MaintenanceEvent, record["canonical_bytes"]) == event
    assert canonical_digest(strict_loads(MaintenanceEvent, record["canonical_bytes"])) == digest


def test_dead_letter_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = MaintenanceLedger(tmp_path)
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    event = _make_event()

    def _leaky_disk(*args: object, **kwargs: object) -> dict:
        raise OSError(f"disk full while flushing Authorization: Bearer {secret}")

    monkeypatch.setattr(ledger._incident._journal, "_emit_locked", _leaky_disk)

    with pytest.raises(MaintenanceAppendFailure):
        ledger.append(event)

    raw = ledger.dead_letter_path.read_text(encoding="utf-8")
    assert secret not in raw
    assert "***REDACTED***" in raw


def test_dead_letter_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = MaintenanceLedger(tmp_path)
    oversized = _make_event(extensions={"blob": "x" * (MAX_DEAD_LETTER_BYTES + 1)})
    _fail_primary(monkeypatch, ledger)

    with pytest.raises(DeadLetterSinkFailure, match="bound"):
        ledger.append(oversized)

    # Nothing persisted: no primary event, no unbounded dead letter.
    assert not ledger.events_path.exists()
    assert not ledger.dead_letter_path.exists()


def test_primary_and_sink_failure_raises_dead_letter_sink_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = MaintenanceLedger(tmp_path)
    _fail_primary(monkeypatch, ledger)

    def _sink_full(*_args: object, **_kwargs: object) -> None:
        raise OSError("dead-letter disk full")

    monkeypatch.setattr(ledger, "_append_line", _sink_full)

    with pytest.raises(DeadLetterSinkFailure) as exc_info:
        ledger.append(_make_event())

    # Both failures are preserved and no success is claimed.
    assert exc_info.value.sink_error is not None
    assert not ledger.events_path.exists()
    assert not ledger.dead_letter_path.exists()


# ---------------------------------------------------------------------------
# Replay: at-most-once, validation, dispositions
# ---------------------------------------------------------------------------


def _write_dead_letter_for(
    ledger: MaintenanceLedger,
    event: MaintenanceEvent,
    *,
    tamper_digest: bool = False,
    tamper_bytes: bool = False,
) -> dict:
    canonical_bytes = canonical_dumps(event)
    digest = canonical_digest(event)
    if tamper_digest:
        digest = "0" * 64
    if tamper_bytes:
        canonical_bytes = canonical_bytes.replace("occ-m1", "occ-x", 1)
    record = {
        "schema_version": DEAD_LETTER_SCHEMA_VERSION,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "replay_id": _recompute_replay_id(event.occurrence_id, digest),
        "idempotency_key": event.occurrence_id,
        "event_kind": event.event_kind.value,
        "digest": digest,
        "failure_type": FailureType.WRITE_FAILURE.value,
        "failure_detail": "OSError: disk full",
        "canonical_bytes": canonical_bytes,
    }
    ledger._append_line(
        ledger.dead_letter_path,
        (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        ),
    )
    return record


def test_replay_appends_original_event_at_most_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = MaintenanceLedger(tmp_path)
    event = _make_event()
    digest = canonical_digest(event)

    # Simulate a primary failure that produced a dead letter.
    _fail_primary(monkeypatch, ledger)
    with pytest.raises(MaintenanceAppendFailure):
        ledger.append(event)
    monkeypatch.undo()

    first = ledger.replay_dead_letters()
    assert isinstance(first, ReplayReport)
    assert len(first.dispositions) == 1
    assert first.dispositions[0].outcome is ReplayOutcome.REPLAYED
    assert first.replayed_count == 1

    # The original logical event is committed exactly once.
    records = _read_ndjson(ledger.events_path)
    assert len(records) == 1
    assert records[0]["payload"]["occurrence_id"] == "occ-m1"
    assert canonical_digest(strict_loads(MaintenanceEvent, records[0]["payload"])) == digest

    # Replaying again must NOT append a second copy.
    second = ledger.replay_dead_letters()
    assert second.dispositions == ()  # already dispositioned
    assert len(_read_ndjson(ledger.events_path)) == 1


def test_replay_records_disposition_append_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = MaintenanceLedger(tmp_path)
    event = _make_event()
    _fail_primary(monkeypatch, ledger)
    with pytest.raises(MaintenanceAppendFailure):
        ledger.append(event)
    monkeypatch.undo()

    original_dead_letter_line = (
        ledger.dead_letter_path.read_text(encoding="utf-8").splitlines()[0]
    )

    ledger.replay_dead_letters()

    # The dead-letter line is unchanged (never rewritten); a disposition is
    # appended to a separate file.
    assert ledger.dead_letter_path.read_text(encoding="utf-8").splitlines() == [
        original_dead_letter_line
    ]
    dispositions = _read_ndjson(ledger.disposition_path)
    assert len(dispositions) == 1
    assert dispositions[0]["disposition"] == "replayed"
    assert dispositions[0]["idempotency_key"] == "occ-m1"
    assert dispositions[0]["seq"] == 0


def test_replay_validates_schema_and_digest(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)
    event = _make_event()

    _write_dead_letter_for(ledger, event, tamper_digest=True)
    report = ledger.replay_dead_letters()

    assert len(report.dispositions) == 1
    assert report.dispositions[0].outcome is ReplayOutcome.INVALID
    assert "digest" in report.dispositions[0].detail
    assert report.replayed_count == 0
    assert not ledger.events_path.exists()


def test_replay_rejects_corrupt_canonical_bytes(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)
    _write_dead_letter_for(ledger, _make_event(), tamper_bytes=True)

    report = ledger.replay_dead_letters()

    assert report.dispositions[0].outcome is ReplayOutcome.INVALID
    assert not ledger.events_path.exists()


def test_replay_reuses_idempotency_key_and_reports_conflict(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)
    # Commit a divergent event for the occurrence first.
    ledger.append(_make_event(occurrence_id="occ-m1", event_id="evt-m1"))
    # Dead-letter a DIFFERENT event that reuses the same occurrence identity.
    _write_dead_letter_for(
        ledger, _make_event(occurrence_id="occ-m1", event_id="evt-m1-other")
    )

    report = ledger.replay_dead_letters()

    assert report.dispositions[0].outcome is ReplayOutcome.CONFLICT
    assert report.dispositions[0].idempotency_key == "occ-m1"
    # History was NOT rewritten: the original committed event is still there.
    records = _read_ndjson(ledger.events_path)
    assert len(records) == 1
    assert records[0]["payload"]["event_id"] == "evt-m1"


def test_replay_reports_already_present_without_duplicate(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(tmp_path)
    event = _make_event()
    ledger.append(event)
    # A dead letter for an event that is already committed.
    _write_dead_letter_for(ledger, event)

    report = ledger.replay_dead_letters()

    assert report.dispositions[0].outcome is ReplayOutcome.ALREADY_PRESENT
    assert report.dispositions[0].seq == 0
    assert len(_read_ndjson(ledger.events_path)) == 1


def test_replay_disposition_sink_failure_reports_without_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = MaintenanceLedger(tmp_path)
    _fail_primary(monkeypatch, ledger)
    with pytest.raises(MaintenanceAppendFailure):
        ledger.append(_make_event())
    monkeypatch.undo()

    def _disposition_sink_full(*_args: object, **_kwargs: object) -> None:
        raise OSError("disposition disk full")

    monkeypatch.setattr(ledger, "_append_line", _disposition_sink_full)

    with pytest.raises(DeadLetterSinkFailure):
        ledger.replay_dead_letters()

    # The disposition was not durably recorded; no success was reported.
    assert not ledger.disposition_path.exists()


# ---------------------------------------------------------------------------
# Crash / reopen durability
# ---------------------------------------------------------------------------


def test_crash_reopen_replays_durably(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # First "process": a primary failure dead-letters the event.
    ledger = MaintenanceLedger(tmp_path)
    event = _make_event()
    _fail_primary(monkeypatch, ledger)
    with pytest.raises(MaintenanceAppendFailure):
        ledger.append(event)
    monkeypatch.undo()

    # Simulate a crash: discard the object and reopen the SAME root.
    reopened = MaintenanceLedger(tmp_path)
    report = reopened.replay_dead_letters()

    assert report.dispositions[0].outcome is ReplayOutcome.REPLAYED
    records = _read_ndjson(reopened.events_path)
    assert len(records) == 1
    assert records[0]["payload"]["occurrence_id"] == "occ-m1"
    # The dead letter and disposition both survive across reopen.
    assert len(_read_ndjson(reopened.dead_letter_path)) == 1
    assert len(_read_ndjson(reopened.disposition_path)) == 1
