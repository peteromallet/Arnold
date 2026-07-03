from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.incident import IncidentLedger


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": 1,
        "incident_id": "inc-123",
        "type": "opened",
        "actor": "system",
        "timestamp": "2026-07-03T19:19:00Z",
        "summary": "incident created",
        "evidence": ["logs/app.log"],
        "parent": [],
    }
    event.update(overrides)
    return event


def test_incident_ledger_appends_validated_events_to_events_jsonl(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)

    appended = ledger.append_event(_event(extra_field={"kept": True}))

    assert ledger.events_path == tmp_path / ".megaplan" / "incident-ledger" / "events.jsonl"
    assert ledger.events_path.exists()
    assert not (ledger.ledger_dir / "events.ndjson").exists()
    assert not (ledger.ledger_dir / "incidents.json").exists()
    assert not (ledger.ledger_dir / "problems.json").exists()
    assert appended["seq"] == 0
    assert appended["kind"] == "incident.opened"
    assert appended["payload"]["extra_field"] == {"kept": True}

    records = [
        json.loads(line)
        for line in ledger.events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert records == [appended]


def test_incident_ledger_preserves_runtime_seq_assignment_across_appends(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)

    first = ledger.append_event(_event())
    second = ledger.append_event(_event(type="updated", summary="incident updated"))

    assert [first["seq"], second["seq"]] == [0, 1]
    assert (ledger.ledger_dir / ".events.seq").read_text(encoding="utf-8") == "1"
    assert (ledger.ledger_dir / ".events.init_ts").exists()


def test_incident_ledger_rejects_invalid_events_before_writing(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)

    with pytest.raises(ValueError, match="incident event 'summary' must be <= 2048"):
        ledger.append_event(_event(summary="x" * 2049))

    assert not ledger.events_path.exists()

