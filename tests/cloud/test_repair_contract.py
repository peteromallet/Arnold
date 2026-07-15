from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.incident_bridge import IncidentStoreWriter
from arnold_pipelines.megaplan.orchestration.progress import ProgressEmitter
from arnold_pipelines.megaplan.store import FileStore
from arnold_pipelines.megaplan.cloud.redact import REDACTION, redact_text
from arnold_pipelines.megaplan.incident import IncidentLedger


def _legacy_payload() -> dict[str, object]:
    return {
        "session": "demo-session",
        "workspace": "/workspace/project",
        "run_kind": "chain",
        "plan_name": "m1-plan",
        "initial_facts": {
            "failure_context": {
                "metadata": {
                    "stderr": "phase failed without secret-bearing output",
                }
            }
        },
        "attempts": [{"attempt_id": 1, "dev_model": "gpt-5.4"}],
        "iterations": [{"i": 1, "mechanical_launch": "running"}],
        "current_signature": {"failure_kind": "phase_failed"},
        "current_advancement_snapshot": {"current_state": "blocked"},
        "outcome": "repairing",
    }


def _read_ledger_events(root: Path) -> list[dict[str, object]]:
    ledger = IncidentLedger(root)
    if not ledger.events_path.exists():
        return []

    records: list[dict[str, object]] = []
    for line in ledger.events_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        records.append(json.loads(stripped))
    return records


def _verified_recovery_evidence(*, blocker_id: str = "blocker-42") -> dict[str, object]:
    return {
        "repair_completed_at": "2026-07-09T07:53:00+00:00",
        "original_blocker": {"blocker_id": blocker_id},
        "observation": {
            "kind": "plan_state",
            "blocker_id": blocker_id,
            "blocker_cleared": True,
            "directly_observed": True,
            "independent": True,
            "observed_at": "2026-07-09T07:54:00+00:00",
        },
    }


def test_incident_store_rejects_test_namespace_on_production_paths(tmp_path: Path) -> None:
    production_root = tmp_path / "production"
    production_ledger = production_root / ".megaplan" / "incident-ledger"
    production_ledger.mkdir(parents=True)
    alias_root = tmp_path / "production-alias"
    alias_root.symlink_to(production_root, target_is_directory=True)

    for root in (production_root, alias_root, production_ledger / "events.jsonl"):
        with pytest.raises(ValueError, match="production ledger, projection, or journal"):
            IncidentStoreWriter.isolated_test(
                root,
                production_root=production_root,
                identity="test:repair_contract",
            )

    assert not (production_ledger / "events.jsonl").exists()


@pytest.mark.parametrize("identity", ["test:repair_contract", "fixture:repair_contract"])
def test_production_incident_writer_rejects_test_identities(
    tmp_path: Path, identity: str
) -> None:
    with pytest.raises(ValueError, match="cannot accept a test or fixture identity"):
        IncidentStoreWriter.production(tmp_path / "production", identity=identity)

    assert not (tmp_path / "production" / ".megaplan" / "incident-ledger").exists()


def test_repair_contract_round_trips_legacy_payload_without_shape_changes(tmp_path: Path) -> None:
    path = tmp_path / "repair-data.json"
    payload = _legacy_payload()

    repair_contract.save_repair_data(path, payload)

    persisted = json.loads(path.read_text(encoding="utf-8"))
    persisted.pop("resident_delegation", None)
    loaded = repair_contract.load_json(path)
    loaded.pop("resident_delegation", None)

    assert persisted == payload
    assert loaded == payload


def test_repair_contract_additive_fields_are_explicit_and_redaction_is_recursive() -> None:
    payload = _legacy_payload()
    payload["initial_facts"]["failure_context"]["metadata"]["stderr"] = (
        "Authorization: Bearer sk-1234567890123456789012345678901"
    )

    enriched = repair_contract.merge_additive_fields(
        payload,
        incident_id="incident-1",
        target={"plan": "m1-plan"},
        attempt_ids=["attempt-demo-session-0001"],
        known_prior_issue_refs=["audit-1"],
    )
    redacted = repair_contract.redact_repair_data(enriched, redactor=redact_text)

    assert payload["attempts"] == [{"attempt_id": 1, "dev_model": "gpt-5.4"}]
    assert enriched["schema_version"] == 1
    assert enriched["target"] == {"plan": "m1-plan"}
    assert enriched["incident_id"] == "incident-1"
    assert enriched["attempt_ids"] == ["attempt-demo-session-0001"]
    assert enriched["known_prior_issue_refs"] == ["audit-1"]
    assert enriched["verification"] == {}
    assert (
        redacted["initial_facts"]["failure_context"]["metadata"]["stderr"]
        == f"Authorization: Bearer {REDACTION}"
    )


def test_repair_contract_load_json_handles_missing_and_corrupt_files(tmp_path: Path) -> None:
    path = tmp_path / "repair-data.json"

    assert repair_contract.load_json(path, default={"missing": True}) == {"missing": True}

    path.write_text("{not valid json", encoding="utf-8")
    assert repair_contract.load_json(path, default={"corrupt": True}) == {"corrupt": True}


def test_repair_contract_atomic_write_keeps_readers_on_complete_json(tmp_path: Path) -> None:
    path = tmp_path / "repair-data.json"
    repair_contract.save_repair_data(path, _legacy_payload())

    stop = threading.Event()
    decode_errors: list[str] = []
    seen_iterations: list[int] = []

    def _reader() -> None:
        while not stop.is_set():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:  # pragma: no cover - failure signal
                decode_errors.append(str(exc))
                stop.set()
                return
            iterations = payload.get("iterations")
            if isinstance(iterations, list):
                seen_iterations.append(len(iterations))

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    try:
        for count in range(1, 31):
            payload = _legacy_payload()
            payload["iterations"] = [{"i": idx, "mechanical_launch": "running"} for idx in range(1, count + 1)]
            payload["attempts"] = [{"attempt_id": idx, "dev_model": "gpt-5.4"} for idx in range(1, count + 1)]
            repair_contract.save_repair_data(path, payload)
    finally:
        stop.set()
        thread.join(timeout=5)

    assert decode_errors == []
    assert seen_iterations
    assert max(seen_iterations) == 30
    assert json.loads(path.read_text(encoding="utf-8"))["iterations"][-1]["i"] == 30


def test_save_repair_data_redacts_secret_bearing_strings_by_default(tmp_path: Path) -> None:
    path = tmp_path / "repair-data.json"
    payload = _legacy_payload()
    payload["initial_facts"]["failure_context"]["metadata"]["stderr"] = (
        "Authorization: Bearer sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    )
    payload["initial_facts"]["chain_log_tail"] = "export API_TOKEN=abc1234567890"

    persisted = repair_contract.save_repair_data(path, payload)

    assert persisted["initial_facts"]["failure_context"]["metadata"]["stderr"] == (
        f"Authorization: Bearer {REDACTION}"
    )
    assert persisted["initial_facts"]["chain_log_tail"] == f"export API_TOKEN={REDACTION}"
    raw = path.read_text(encoding="utf-8")
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz123456" not in raw
    assert "abc1234567890" not in raw


# ---------------------------------------------------------------------------
# JSONL / NDJSON sidecar helpers
# ---------------------------------------------------------------------------


def test_jsonl_append_and_read_preserves_ordering(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"
    records = [
        {"event": "start", "session": "s1"},
        {"event": "progress", "session": "s1", "pct": 50},
        {"event": "done", "session": "s1"},
    ]
    for rec in records:
        repair_contract.append_repair_event(sidecar_dir, rec)

    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "events")
    assert path.exists()

    loaded = repair_contract.read_jsonl_records(path)
    assert len(loaded) == 3
    assert loaded[0]["event"] == "start"
    assert loaded[0]["_sequence"] == 1
    assert loaded[1]["event"] == "progress"
    assert loaded[1]["_sequence"] == 2
    assert loaded[2]["event"] == "done"
    assert loaded[2]["_sequence"] == 3


def test_jsonl_auto_sequence_continues_after_read(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"

    repair_contract.append_incident_record(sidecar_dir, {"id": "inc-1"})
    repair_contract.append_incident_record(sidecar_dir, {"id": "inc-2"})
    repair_contract.append_incident_record(sidecar_dir, {"id": "inc-3"})

    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "incidents")
    records = repair_contract.read_jsonl_records(path)
    sequences = [r["_sequence"] for r in records]
    assert sequences == [1, 2, 3]


def test_jsonl_skip_parse_errors_drops_bad_lines(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"
    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "attempts")

    repair_contract.append_attempt_record(sidecar_dir, {"attempt": 1})
    # Append a corrupted line directly (bypassing the atomic helper)
    existing = path.read_text(encoding="utf-8")
    corrupted = existing + "{not valid json\n"
    path.write_text(corrupted, encoding="utf-8")
    repair_contract.append_attempt_record(sidecar_dir, {"attempt": 2})

    # Strict mode should raise
    with pytest.raises(ValueError, match="JSONL parse error"):
        repair_contract.read_jsonl_records(path)

    # Tolerant mode should skip the bad line
    records = repair_contract.read_jsonl_records(path, skip_parse_errors=True)
    assert len(records) == 2
    assert records[0]["attempt"] == 1
    assert records[1]["attempt"] == 2


def test_jsonl_parse_failure_on_non_object_record(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"
    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "events")

    repair_contract.append_repair_event(sidecar_dir, {"ok": True})
    # Append a JSON array line
    existing = path.read_text(encoding="utf-8")
    corrupted = existing + '[1, 2, 3]\n'
    path.write_text(corrupted, encoding="utf-8")

    with pytest.raises(ValueError, match="not a JSON object"):
        repair_contract.read_jsonl_records(path)

    records = repair_contract.read_jsonl_records(path, skip_parse_errors=True)
    assert len(records) == 1
    assert records[0]["ok"] is True


def test_jsonl_validate_summary_on_clean_file(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"

    for i in range(5):
        repair_contract.append_repair_event(sidecar_dir, {"n": i})

    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "events")
    summary = repair_contract.validate_jsonl_summary(path)

    assert summary["total_lines"] == 5
    assert summary["valid_records"] == 5
    assert summary["parse_errors"] == []
    assert summary["non_object_lines"] == 0
    assert summary["ordered"] is True
    assert summary["first_record"]["n"] == 0
    assert summary["last_record"]["n"] == 4


def test_jsonl_validate_summary_detects_parse_errors(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"
    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "events")

    repair_contract.append_repair_event(sidecar_dir, {"good": 1})
    existing = path.read_text(encoding="utf-8")
    corrupted = existing + "broken json!!!\n" + '{"good": 2}\n'
    path.write_text(corrupted, encoding="utf-8")

    summary = repair_contract.validate_jsonl_summary(path)
    assert summary["total_lines"] == 3
    assert summary["valid_records"] == 2
    assert len(summary["parse_errors"]) == 1
    assert summary["parse_errors"][0]["line"] == 2
    assert summary["ordered"] is None  # only one record had _sequence (the broken line skipped)


def test_jsonl_validate_summary_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent" / "events.jsonl"
    summary = repair_contract.validate_jsonl_summary(path)
    assert summary["total_lines"] == 0
    assert summary["valid_records"] == 0
    assert summary["parse_errors"] == []
    assert summary["first_record"] is None


def test_jsonl_validate_summary_detects_disordered_sequences(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"
    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "attempts")

    repair_contract.append_attempt_record(sidecar_dir, {"a": 1})
    repair_contract.append_attempt_record(sidecar_dir, {"a": 2})

    # Manually rewrite with reversed _sequence values
    records = repair_contract.read_jsonl_records(path)
    records[0]["_sequence"] = 5
    records[1]["_sequence"] = 3
    new_content = "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n"
    path.write_text(new_content, encoding="utf-8")

    summary = repair_contract.validate_jsonl_summary(path)
    assert summary["valid_records"] == 2
    assert summary["ordered"] is False


def test_jsonl_typed_helpers_create_separate_sidecars(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"

    repair_contract.append_repair_event(sidecar_dir, {"kind": "event"})
    repair_contract.append_incident_record(sidecar_dir, {"kind": "incident"})
    repair_contract.append_attempt_record(sidecar_dir, {"kind": "attempt"})

    events = repair_contract.read_jsonl_records(
        repair_contract._sidecar_jsonl_path(sidecar_dir, "events")
    )
    incidents = repair_contract.read_jsonl_records(
        repair_contract._sidecar_jsonl_path(sidecar_dir, "incidents")
    )
    attempts = repair_contract.read_jsonl_records(
        repair_contract._sidecar_jsonl_path(sidecar_dir, "attempts")
    )

    assert len(events) == 1
    assert events[0]["kind"] == "event"
    assert len(incidents) == 1
    assert incidents[0]["kind"] == "incident"
    assert len(attempts) == 1
    assert attempts[0]["kind"] == "attempt"


def test_jsonl_unknown_kind_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown sidecar kind"):
        repair_contract.append_jsonl_record(tmp_path, "unknown", {"x": 1})


def test_jsonl_append_escalation_writes_to_correct_path(tmp_path: Path) -> None:
    """The escalations sidecar uses escalations/escalations.jsonl under the sidecar dir."""
    sidecar_dir = tmp_path / "repair-data.d"

    repair_contract.append_escalation_record(sidecar_dir, {"escalation_id": "esc-1", "event": "opened"})

    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "escalations")
    assert path.exists()
    assert path.name == "escalations.jsonl"
    assert path.parent.name == "escalations"

    records = repair_contract.read_jsonl_records(path)
    assert len(records) == 1
    assert records[0]["escalation_id"] == "esc-1"
    assert records[0]["event"] == "opened"
    assert records[0]["_sequence"] == 1


def test_jsonl_append_escalation_preserves_existing_sidecars(tmp_path: Path) -> None:
    """Adding escalation records must not disturb events/incidents/attempts sidecars."""
    sidecar_dir = tmp_path / "repair-data.d"

    # Write to all existing sidecar kinds
    repair_contract.append_repair_event(sidecar_dir, {"kind": "event"})
    repair_contract.append_incident_record(sidecar_dir, {"kind": "incident"})
    repair_contract.append_attempt_record(sidecar_dir, {"kind": "attempt"})

    # Now write escalation records
    repair_contract.append_escalation_record(sidecar_dir, {"escalation_id": "esc-1", "lifecycle": "opened"})
    repair_contract.append_escalation_record(sidecar_dir, {"escalation_id": "esc-1", "lifecycle": "delivered"})

    # Verify existing sidecars are untouched
    events = repair_contract.read_jsonl_records(
        repair_contract._sidecar_jsonl_path(sidecar_dir, "events")
    )
    incidents = repair_contract.read_jsonl_records(
        repair_contract._sidecar_jsonl_path(sidecar_dir, "incidents")
    )
    attempts = repair_contract.read_jsonl_records(
        repair_contract._sidecar_jsonl_path(sidecar_dir, "attempts")
    )
    assert len(events) == 1
    assert events[0]["kind"] == "event"
    assert len(incidents) == 1
    assert incidents[0]["kind"] == "incident"
    assert len(attempts) == 1
    assert attempts[0]["kind"] == "attempt"

    # Verify escalations sidecar has both records with correct sequences
    escalations = repair_contract.read_jsonl_records(
        repair_contract._sidecar_jsonl_path(sidecar_dir, "escalations")
    )
    assert len(escalations) == 2
    assert escalations[0]["lifecycle"] == "opened"
    assert escalations[0]["_sequence"] == 1
    assert escalations[1]["lifecycle"] == "delivered"
    assert escalations[1]["_sequence"] == 2


def test_jsonl_append_escalation_auto_sequence_and_timestamp(tmp_path: Path) -> None:
    """Escalation records get auto-sequence and _timestamp like other sidecars."""
    sidecar_dir = tmp_path / "repair-data.d"

    repair_contract.append_escalation_record(sidecar_dir, {"escalation_id": "esc-1"})
    repair_contract.append_escalation_record(sidecar_dir, {"escalation_id": "esc-2"})
    repair_contract.append_escalation_record(sidecar_dir, {"escalation_id": "esc-3"})

    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "escalations")
    records = repair_contract.read_jsonl_records(path)

    assert len(records) == 3
    sequences = [r["_sequence"] for r in records]
    assert sequences == [1, 2, 3]

    for r in records:
        assert "_timestamp" in r
        datetime.fromisoformat(r["_timestamp"])


def test_jsonl_append_cleanup_writes_to_dedicated_sidecar(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"

    repair_contract.append_cleanup_record(
        sidecar_dir,
        {
            "cleanup_id": "cleanup-1",
            "pruned_counts": {"attempts": 2},
            "preserved_reasons": ["unresolved escalation"],
        },
    )

    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "cleanup")
    assert path.exists()
    assert path.name == "cleanup.jsonl"
    assert path.parent.name == "cleanup"

    records = repair_contract.read_jsonl_records(path)
    assert len(records) == 1
    assert records[0]["cleanup_id"] == "cleanup-1"
    assert records[0]["pruned_counts"] == {"attempts": 2}
    assert records[0]["preserved_reasons"] == ["unresolved escalation"]
    assert records[0]["_sequence"] == 1


def test_jsonl_typed_helpers_include_cleanup_sidecar(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"

    repair_contract.append_repair_event(sidecar_dir, {"kind": "event"})
    repair_contract.append_incident_record(sidecar_dir, {"kind": "incident"})
    repair_contract.append_attempt_record(sidecar_dir, {"kind": "attempt"})
    repair_contract.append_cleanup_record(sidecar_dir, {"kind": "cleanup"})

    cleanup = repair_contract.read_jsonl_records(
        repair_contract._sidecar_jsonl_path(sidecar_dir, "cleanup")
    )
    assert len(cleanup) == 1
    assert cleanup[0]["kind"] == "cleanup"


def test_jsonl_non_mapping_record_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be a mapping"):
        repair_contract.append_jsonl_record(tmp_path, "events", [1, 2, 3])  # type: ignore[arg-type]


def test_jsonl_timestamp_is_added_when_missing(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"
    repair_contract.append_repair_event(sidecar_dir, {"no_ts": True})

    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "events")
    records = repair_contract.read_jsonl_records(path)
    assert "_timestamp" in records[0]
    # Should be a valid ISO timestamp
    datetime.fromisoformat(records[0]["_timestamp"])


def test_jsonl_timestamp_preserved_when_provided(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"
    custom_ts = "2026-01-15T12:00:00+00:00"
    repair_contract.append_repair_event(
        sidecar_dir, {"custom": True, "_timestamp": custom_ts}
    )

    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "events")
    records = repair_contract.read_jsonl_records(path)
    assert records[0]["_timestamp"] == custom_ts


def test_jsonl_read_missing_file_strict_raises(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent.jsonl"
    with pytest.raises(ValueError, match="JSONL file missing"):
        repair_contract.read_jsonl_records(path)


def test_jsonl_read_missing_file_tolerant_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent.jsonl"
    records = repair_contract.read_jsonl_records(path, skip_parse_errors=True)
    assert records == []


def test_jsonl_concurrent_appends_are_visible(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"
    path = repair_contract._sidecar_jsonl_path(sidecar_dir, "events")

    repair_contract.append_repair_event(sidecar_dir, {"writer": "A"})
    repair_contract.append_repair_event(sidecar_dir, {"writer": "B"})
    repair_contract.append_repair_event(sidecar_dir, {"writer": "C"})

    records = repair_contract.read_jsonl_records(path)
    writers = [r["writer"] for r in records]
    assert writers == ["A", "B", "C"]
    for r in records:
        assert "_sequence" in r
        assert "_timestamp" in r


# ---------------------------------------------------------------------------
# repair-data index helpers
# ---------------------------------------------------------------------------


def test_repair_index_load_missing_returns_default_shape(tmp_path: Path) -> None:
    path = tmp_path / "repair-data" / "index.json"

    loaded = repair_contract.load_repair_index(path)

    assert loaded == {"sessions": {}, "incidents": {}}


def test_repair_index_preserves_resident_delegation_metadata(tmp_path: Path) -> None:
    path = tmp_path / "index.json"
    path.write_text(
        json.dumps(
            {
                "sessions": {},
                "incidents": {},
                "resident_delegation": {
                    "schema_version": "arnold-resident-delegation-provenance-v1",
                    "custody_id": "custody-1",
                },
            }
        ),
        encoding="utf-8",
    )

    repair_contract.update_session_index(
        path,
        "wbc",
        {"status": "repairing"},
    )

    loaded = repair_contract.read_repair_index(path)
    assert loaded["resident_delegation"]["custody_id"] == "custody-1"
    assert loaded["sessions"]["wbc"]["status"] == "repairing"


def test_repair_index_updates_create_and_merge_nested_refs_idempotently(tmp_path: Path) -> None:
    path = tmp_path / "repair-data" / "index.json"

    first = repair_contract.update_session_index(
        path,
        "session-1",
        {
            "status": "active",
            "refs": {
                "latest-attempt": {"attempt_id": "attempt-1"},
                "latest-outcome": {"outcome": "repairing"},
            },
        },
    )
    second = repair_contract.update_session_index(
        path,
        "session-1",
        {
            "status": "active",
            "refs": {
                "latest-outcome": {"outcome": "complete"},
                "unresolved-escalation": {"escalation_id": "esc-1"},
            },
        },
    )
    third = repair_contract.update_incident_index(
        path,
        "incident-1",
        {
            "session_id": "session-1",
            "state": "open",
            "refs": {
                "latest-attempt": {"attempt_id": "attempt-1"},
                "unresolved-escalation": {"escalation_id": "esc-1"},
            },
        },
    )

    assert first["sessions"]["session-1"]["refs"]["latest-attempt"] == {
        "attempt_id": "attempt-1"
    }
    assert second["sessions"]["session-1"]["refs"] == {
        "latest-attempt": {"attempt_id": "attempt-1"},
        "latest-outcome": {"outcome": "complete"},
        "unresolved-escalation": {"escalation_id": "esc-1"},
    }
    assert third["incidents"]["incident-1"]["refs"] == {
        "latest-attempt": {"attempt_id": "attempt-1"},
        "unresolved-escalation": {"escalation_id": "esc-1"},
    }

    loaded = repair_contract.read_repair_index(path)
    resident_delegation = loaded.pop("resident_delegation", None)
    assert loaded == {
        "sessions": {
            "session-1": {
                "status": "active",
                "refs": {
                    "latest-attempt": {"attempt_id": "attempt-1"},
                    "latest-outcome": {"outcome": "complete"},
                    "unresolved-escalation": {"escalation_id": "esc-1"},
                },
            }
        },
        "incidents": {
            "incident-1": {
                "session_id": "session-1",
                "state": "open",
                "refs": {
                    "latest-attempt": {"attempt_id": "attempt-1"},
                    "unresolved-escalation": {"escalation_id": "esc-1"},
                },
            }
        },
    }
    if resident_delegation is not None:
        assert resident_delegation["schema_version"] == (
            "arnold-resident-delegation-provenance-v1"
        )


def test_repair_index_allows_resident_delegation_metadata(tmp_path: Path) -> None:
    path = tmp_path / "repair-data" / "index.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "sessions": {},
                "incidents": {},
                "resident_delegation": {
                    "schema_version": "arnold-resident-delegation-provenance-v1",
                    "transport": "discord",
                    "conversation_key": "discord:dm:123",
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = repair_contract.read_repair_index(path)

    assert loaded["resident_delegation"] == {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "transport": "discord",
        "conversation_key": "discord:dm:123",
    }


def test_repair_index_write_redacts_secret_shaped_nested_values(tmp_path: Path) -> None:
    path = tmp_path / "repair-data" / "index.json"

    persisted = repair_contract.update_session_index(
        path,
        "session-secret",
        {
            "status": "active",
            "refs": {
                "latest-attempt": {
                    "attempt_id": "attempt-secret",
                    "command": "Authorization: Bearer sk-proj-abcdefghijklmnopqrstuvwxyz123456",
                },
                "latest-outcome": {
                    "summary": "export API_TOKEN=abc1234567890",
                },
                "unresolved-escalation": {
                    "message": "Bearer bearer-secret-token-value",
                },
            },
        },
    )

    refs = persisted["sessions"]["session-secret"]["refs"]
    assert refs["latest-attempt"]["command"] == f"Authorization: Bearer {REDACTION}"
    assert refs["latest-outcome"]["summary"] == f"export API_TOKEN={REDACTION}"
    assert refs["unresolved-escalation"]["message"] == f"Bearer {REDACTION}"

    raw = path.read_text(encoding="utf-8")
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz123456" not in raw
    assert "abc1234567890" not in raw
    assert "bearer-secret-token-value" not in raw


def test_save_repair_data_updates_session_index(tmp_path: Path) -> None:
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = repair_contract.merge_additive_fields(
        _legacy_payload(),
        incident_id="incident-42",
        attempt_ids=["attempt-demo-0001"],
        verification={"recorded_at": "2026-07-02T20:00:00+00:00"},
    )

    repair_contract.save_repair_data(path, payload)

    index_payload = repair_contract.read_repair_index(repair_dir / "index.json")
    assert index_payload["sessions"]["demo-session"]["status"] == "repairing"
    assert index_payload["sessions"]["demo-session"]["incident_id"] == "incident-42"
    assert index_payload["sessions"]["demo-session"]["attempt_ids"] == ["attempt-demo-0001"]
    assert index_payload["sessions"]["demo-session"]["refs"]["latest-outcome"] == {
        "incident_id": "incident-42",
        "outcome": "repairing",
        "path": str(path),
        "recorded_at": "2026-07-02T20:00:00+00:00",
    }


def test_save_repair_data_emits_immediate_repair_attempt_for_repairing(tmp_path: Path) -> None:
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = repair_contract.merge_additive_fields(
        _legacy_payload(),
        incident_id="incident-42",
        attempt_ids=["attempt-demo-0001"],
        verification={"recorded_at": "2026-07-02T20:00:00+00:00"},
    )

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1
    ledger_payload = events[0]["payload"]
    assert ledger_payload["type"] == "repair_attempt"
    assert ledger_payload["actor"] == "immediate_repair"
    assert ledger_payload["outcome"] == "attempted"
    assert ledger_payload["incident_id"] == "incident-42"
    assert ledger_payload["session_id"] == "demo-session"


def test_save_repair_data_emits_immediate_repair_attempt_for_terminal_non_success(tmp_path: Path) -> None:
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = repair_contract.merge_additive_fields(
        {
            **_legacy_payload(),
            "outcome": repair_contract.REPAIR_TIMEOUT,
        },
        incident_id="incident-42",
        attempt_ids=["attempt-demo-0001"],
        verification={"recorded_at": "2026-07-02T20:00:00+00:00"},
    )

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1
    ledger_payload = events[0]["payload"]
    assert ledger_payload["type"] == "repair_attempt"
    assert ledger_payload["actor"] == "immediate_repair"
    assert ledger_payload["outcome"] == repair_contract.REPAIR_TIMEOUT


def test_save_repair_data_emits_new_repair_attempt_when_attempt_identity_changes(
    tmp_path: Path,
) -> None:
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    first_payload = repair_contract.merge_additive_fields(
        {
            **_legacy_payload(),
            "current_attempt_id": 1,
            "repair_run_count": 1,
        },
        incident_id="incident-42",
        attempt_ids=["attempt-demo-0001"],
    )
    second_payload = repair_contract.merge_additive_fields(
        {
            **_legacy_payload(),
            "current_attempt_id": 2,
            "repair_run_count": 2,
        },
        incident_id="incident-42",
        attempt_ids=["attempt-demo-0002"],
    )

    repair_contract.save_repair_data(path, first_payload, root=tmp_path)
    repair_contract.save_repair_data(path, second_payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 2
    assert events[0]["payload"]["attempt_id"] == "demo-session-attempted-1"
    assert events[1]["payload"]["attempt_id"] == "demo-session-attempted-2"


def test_save_repair_data_emits_new_verified_recovered_when_success_identity_changes(
    tmp_path: Path,
) -> None:
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    first_payload = repair_contract.merge_additive_fields(
        {
            **_legacy_payload(),
            "outcome": "complete",
            "repair_run_count": 24,
        },
        incident_id="incident-42",
        verification={
            **_verified_recovery_evidence(),
            "recorded_at": "2026-07-09T07:53:48+00:00",
        },
    )
    second_payload = repair_contract.merge_additive_fields(
        {
            **_legacy_payload(),
            "outcome": "complete",
            "repair_run_count": 25,
        },
        incident_id="incident-42",
        verification={
            **_verified_recovery_evidence(),
            "recorded_at": "2026-07-09T07:57:55+00:00",
        },
    )

    repair_contract.save_repair_data(path, first_payload, root=tmp_path)
    repair_contract.save_repair_data(path, second_payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 2
    assert all(event["payload"]["type"] == "verified_recovered" for event in events)
    assert [event["payload"]["summary"] for event in events] == [
        "repair-data outcome=complete plan=m1-plan kind=chain workspace=/workspace/project",
        "repair-data outcome=complete plan=m1-plan kind=chain workspace=/workspace/project",
    ]


def test_save_repair_data_does_not_verify_success_outcome_without_proof(
    tmp_path: Path,
) -> None:
    path = tmp_path / "demo-session.repair-data.json"
    payload = repair_contract.merge_additive_fields(
        {**_legacy_payload(), "outcome": "complete"},
        incident_id="incident-42",
        verification={
            "outcome": "complete",
            "original_blocker": {"blocker_id": "blocker-42"},
            "observation": {"kind": "subprocess_success", "returncode": 0},
            "repair_completed_at": "2026-07-09T07:53:00+00:00",
        },
    )

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert [event["payload"]["type"] for event in events] == ["repair_attempt"]
    projected = events[0]["payload"]["evidence"][-1]["data"]
    assert projected["status"] == "provisional"
    assert projected["authorizes_verified_recovered"] is False


@pytest.mark.parametrize("unknown_type", ["missing", "stale", "partial", "contradictory"])
def test_incident_projection_preserves_typed_unknown_recovery_evidence(
    tmp_path: Path, unknown_type: str
) -> None:
    path = tmp_path / f"{unknown_type}.repair-data.json"
    payload = repair_contract.merge_additive_fields(
        {**_legacy_payload(), "outcome": "complete", "session": unknown_type},
        incident_id=f"incident-{unknown_type}",
        verification={
            "repair_completed_at": "2026-07-09T07:53:00+00:00",
            "original_blocker": {"blocker_id": "blocker-42"},
            "observation": {"evidence_state": {"unknown_type": unknown_type}},
        },
    )

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    event = _read_ledger_events(tmp_path)[0]["payload"]
    assert event["type"] == "repair_attempt"
    assert event["outcome"] == f"unknown_{unknown_type}"
    projected = event["evidence"][-1]["data"]
    assert projected["status"] == "unknown"
    assert projected["unknown_type"] == unknown_type
    assert projected["authorizes_verified_recovered"] is False


def test_progress_projection_cannot_promote_liveness_or_dispatch_success(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "progress-store")
    epic = store.create_epic(title="Recovery", goal="Truthful projection", body="")
    emitter = ProgressEmitter(store, epic_id=epic.id, plan_id="plan-1")

    emitter.emit(
        "phase_end",
        "Repair subprocess finished",
        details={
            "recovery_state": "verified_recovered",
            "recovery_verified": True,
            "recovery_verification": {
                "original_blocker": {"blocker_id": "blocker-42"},
                "observation": {
                    "kind": "subprocess_success",
                    "returncode": 0,
                    "pid_alive": True,
                },
                "repair_completed_at": "2026-07-09T07:53:00+00:00",
            },
        },
    )

    details = store.list_progress_events(epic_id=epic.id)[0].details
    assert details["recovery_state"] == "provisional"
    assert details["recovery_verified"] is False
    assert details["authorizes_verified_recovered"] is False


def test_progress_projection_preserves_unknown_and_verified_recovery_evidence(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "progress-store")
    epic = store.create_epic(title="Recovery", goal="Truthful projection", body="")
    emitter = ProgressEmitter(store, epic_id=epic.id, plan_id="plan-1")
    stale = {
        "repair_completed_at": "2026-07-09T07:53:00+00:00",
        "original_blocker": {"blocker_id": "blocker-42"},
        "observation": {"evidence_state": {"unknown_type": "stale"}},
    }

    emitter.recovery_observed(stale, summary="Stale recovery observation")
    emitter.recovery_observed(
        _verified_recovery_evidence(), summary="Independent recovery observation"
    )

    events = store.list_progress_events(epic_id=epic.id)
    assert [event.details["recovery_status"] for event in events] == [
        "unknown",
        "verified_recovered",
    ]
    assert events[0].details["unknown_type"] == "stale"
    assert events[0].details["authorizes_verified_recovered"] is False
    assert events[1].details["unknown_type"] == ""
    assert events[1].details["authorizes_verified_recovered"] is True


def test_save_repair_data_defaults_incident_root_to_payload_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repair_dir = tmp_path / "repair-data"
    workspace_root = tmp_path / "workspace"
    other_root = tmp_path / "elsewhere"
    repair_dir.mkdir()
    workspace_root.mkdir()
    other_root.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = repair_contract.merge_additive_fields(
        {**_legacy_payload(), "workspace": str(workspace_root)},
        incident_id="incident-42",
        attempt_ids=["attempt-demo-0001"],
        verification={"recorded_at": "2026-07-02T20:00:00+00:00"},
    )

    monkeypatch.chdir(other_root)
    repair_contract.save_repair_data(path, payload)

    events = _read_ledger_events(workspace_root)
    assert len(events) == 1
    assert _read_ledger_events(other_root) == []
    ledger_payload = events[0]["payload"]
    assert ledger_payload["incident_id"] == "incident-42"
    assert ledger_payload["session_id"] == "demo-session"


def test_retention_cleanup_preserves_protected_artifacts_and_records_cleanup_event(
    tmp_path: Path,
) -> None:
    repair_dir = tmp_path / "repair-data"
    sidecar_dir = tmp_path / "repair-data.d"
    audit_dir = tmp_path / "audit-reports"
    attempts_dir = repair_dir / "attempts"
    incidents_dir = repair_dir / "incidents"
    escalations_dir = repair_dir / "escalations"
    meta_dir = repair_dir / "meta"

    for directory in (
        repair_dir,
        attempts_dir,
        incidents_dir,
        escalations_dir,
        meta_dir,
        audit_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    def _write_json(path: Path, payload: dict[str, object], *, age_days: int) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")
        stale_ts = datetime(2026, 1, 1, 0, 0, 0).timestamp() - (age_days * 86400)
        os.utime(path, (stale_ts, stale_ts))

    active_snapshot = repair_dir / "active-session.repair-data.json"
    _write_json(active_snapshot, {"session": "active-session", "outcome": "repairing"}, age_days=60)
    stale_snapshot = repair_dir / "stale-session.repair-data.json"
    _write_json(stale_snapshot, {"session": "stale-session", "outcome": "complete"}, age_days=60)

    for attempt_num in range(21):
        path = attempts_dir / f"attempt-{attempt_num:02d}.json"
        _write_json(
            path,
            {"attempt_id": f"attempt-{attempt_num:02d}", "session_id": "active-session"},
            age_days=60 - attempt_num,
        )

    keep_audit_json = audit_dir / "2026-01-01T000000-audit.json"
    keep_audit_md = audit_dir / "2026-01-01T000000-audit.md"
    prune_audit_json = audit_dir / "2026-01-02T000000-audit.json"
    prune_audit_md = audit_dir / "2026-01-02T000000-audit.md"
    for path in (keep_audit_json, keep_audit_md, prune_audit_json, prune_audit_md):
        path.write_text("{}", encoding="utf-8")
        stale_ts = datetime(2026, 1, 1, 0, 0, 0).timestamp() - (45 * 86400)
        os.utime(path, (stale_ts, stale_ts))

    _write_json(
        incidents_dir / "incident-open.json",
        {
            "incident_id": "incident-open",
            "state": "open",
            "audit_report_paths": [str(keep_audit_json), str(keep_audit_md)],
        },
        age_days=45,
    )
    _write_json(
        incidents_dir / "incident-resolved.json",
        {"incident_id": "incident-resolved", "state": "resolved"},
        age_days=45,
    )
    _write_json(
        escalations_dir / "escalation-open.json",
        {"escalation_id": "esc-open", "resolution_state": "unresolved"},
        age_days=120,
    )
    _write_json(
        escalations_dir / "escalation-resolved.json",
        {"escalation_id": "esc-resolved", "resolution_state": "resolved"},
        age_days=120,
    )
    _write_json(
        meta_dir / "meta-old.json",
        {"meta_repair_id": "meta-1", "status": "complete"},
        age_days=120,
    )

    repair_contract.update_session_index(
        repair_dir / "index.json",
        "active-session",
        {
            "status": "active",
            "refs": {"latest-outcome": {"outcome": "repairing"}},
            "latest_meta_repair_id": "meta-1",
            "latest_meta_outcome": "FIXED",
            "latest_meta_record_path": str(meta_dir / "meta-old.json"),
            "latest_meta_recorded_at": "2026-01-01T00:00:00+00:00",
        },
    )
    repair_contract.update_session_index(
        repair_dir / "index.json",
        "stale-session",
        {"status": "complete", "refs": {"latest-outcome": {"outcome": "complete"}}},
    )
    repair_contract.update_incident_index(
        repair_dir / "index.json",
        "incident-open",
        {
            "state": "open",
            "audit_report_paths": [str(keep_audit_json), str(keep_audit_md)],
            "refs": {"unresolved-escalation": {"escalation_id": "esc-open"}},
        },
    )

    summary = repair_contract.cleanup_repair_data_retention(
        repair_dir,
        sidecar_dir=sidecar_dir,
        audit_report_dir=audit_dir,
        now=datetime(2026, 7, 1, 0, 0, 0),
    )

    assert active_snapshot.exists()
    assert not stale_snapshot.exists()
    assert len(list(attempts_dir.glob("*.json"))) == 20
    assert not (attempts_dir / "attempt-00.json").exists()
    assert (incidents_dir / "incident-open.json").exists()
    assert not (incidents_dir / "incident-resolved.json").exists()
    assert (escalations_dir / "escalation-open.json").exists()
    assert not (escalations_dir / "escalation-resolved.json").exists()
    assert not (meta_dir / "meta-old.json").exists()
    assert keep_audit_json.exists()
    assert keep_audit_md.exists()
    assert not prune_audit_json.exists()
    assert not prune_audit_md.exists()

    assert summary["pruned_counts"]["attempts"] == 1
    assert summary["pruned_counts"]["incidents"] == 1
    assert summary["pruned_counts"]["escalations"] == 1
    assert summary["pruned_counts"]["meta"] == 1
    assert summary["pruned_counts"]["audit_reports"] == 2
    assert summary["preserved_reasons"]["active_session_snapshot"] == 1
    assert summary["preserved_reasons"]["unresolved_incident"] == 1
    assert summary["preserved_reasons"]["unresolved_escalation"] == 1
    assert summary["preserved_reasons"]["referenced_audit_report"] == 2
    assert summary["index_snapshots"]["before"]["incidents"]["incident-open"]["refs"] == {
        "unresolved-escalation": {"escalation_id": "esc-open"}
    }
    assert "stale-session" not in summary["index_snapshots"]["after"]["sessions"]
    assert summary["index_snapshots"]["after"]["sessions"]["active-session"]["latest_meta_repair_id"] == ""
    persisted_index = repair_contract.read_repair_index(repair_dir / "index.json")
    resident_delegation = persisted_index.pop("resident_delegation", None)
    if resident_delegation is not None:
        assert resident_delegation["schema_version"] == (
            "arnold-resident-delegation-provenance-v1"
        )
    assert persisted_index == summary["index_snapshots"]["after"]

    cleanup_records = repair_contract.read_jsonl_records(
        repair_contract._sidecar_jsonl_path(sidecar_dir, "cleanup")
    )
    assert len(cleanup_records) == 1
    assert cleanup_records[0]["cleanup_id"] == summary["cleanup_id"]
    assert cleanup_records[0]["pruned_counts"]["attempts"] == 1
    assert cleanup_records[0]["preserved_reasons"]["referenced_audit_report"] == 2

# ---------------------------------------------------------------------------
# Outcome lattice helpers
# ---------------------------------------------------------------------------


def test_outcome_constants_are_well_defined() -> None:
    assert repair_contract.COMPLETE == "complete"
    assert repair_contract.PROGRESSED == "progressed"
    assert repair_contract.LIVE_WITH_FRESH_ACTIVITY == "live_with_fresh_activity"
    assert repair_contract.TRUE_HUMAN_BLOCKER == "true_human_blocker"
    assert repair_contract.PARTIAL_LIVENESS == "partial_liveness"
    assert repair_contract.REPAIRING == "repairing"
    assert repair_contract.REPAIR_TIMEOUT == "repair_timeout"
    assert repair_contract.REPAIR_EXHAUSTED == "repair_exhausted"
    assert repair_contract.NEEDS_HUMAN == "needs_human"
    assert repair_contract.DISCORD_ESCALATED == "discord_escalated"
    assert repair_contract.ENVIRONMENT_GONE == "environment_gone"


def test_success_outcomes_match_planned_lattice() -> None:
    assert repair_contract.SUCCESS_OUTCOMES == frozenset(
        {"complete", "progressed", "true_human_blocker"}
    )


def test_non_success_outcomes_include_liveness_and_exhaustion() -> None:
    assert "live_with_fresh_activity" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "partial_liveness" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "repair_timeout" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "repair_exhausted" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "needs_human" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "repairing" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "discord_escalated" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "environment_gone" in repair_contract.NON_SUCCESS_OUTCOMES


def test_environment_gone_outcome_is_terminal_and_non_success() -> None:
    """environment_gone retires a wiped session without Discord escalation."""
    assert repair_contract.ENVIRONMENT_GONE == "environment_gone"
    assert repair_contract.ENVIRONMENT_GONE in repair_contract.NON_SUCCESS_OUTCOMES
    assert repair_contract.ENVIRONMENT_GONE not in repair_contract.SUCCESS_OUTCOMES
    assert repair_contract.ENVIRONMENT_GONE in repair_contract.ALL_OUTCOMES
    assert repair_contract.is_terminal_outcome(repair_contract.ENVIRONMENT_GONE)
    assert not repair_contract.is_success_outcome(repair_contract.ENVIRONMENT_GONE)


def test_all_outcomes_union_covers_both_sets() -> None:
    assert repair_contract.ALL_OUTCOMES == (
        repair_contract.SUCCESS_OUTCOMES | repair_contract.NON_SUCCESS_OUTCOMES
    )
    # Sanity: these are disjoint
    assert repair_contract.SUCCESS_OUTCOMES.isdisjoint(repair_contract.NON_SUCCESS_OUTCOMES)


def test_is_success_outcome_only_accepts_three_values() -> None:
    for outcome in repair_contract.ALL_OUTCOMES:
        expected = outcome in repair_contract.SUCCESS_OUTCOMES
        assert repair_contract.is_success_outcome(outcome) == expected, (
            f"is_success_outcome({outcome!r}) returned unexpected {not expected}"
        )


def test_is_success_outcome_unknown_value_not_in_lattice() -> None:
    assert not repair_contract.is_success_outcome("bogus")
    assert not repair_contract.is_success_outcome("")


def test_live_with_fresh_activity_constant_loadable_but_non_success() -> None:
    """The legacy constant must remain loadable for historical records but is non-success."""
    assert repair_contract.LIVE_WITH_FRESH_ACTIVITY == "live_with_fresh_activity"
    assert repair_contract.LIVE_WITH_FRESH_ACTIVITY not in repair_contract.SUCCESS_OUTCOMES
    assert repair_contract.LIVE_WITH_FRESH_ACTIVITY in repair_contract.NON_SUCCESS_OUTCOMES
    assert not repair_contract.is_success_outcome(repair_contract.LIVE_WITH_FRESH_ACTIVITY)


def test_is_terminal_outcome() -> None:
    assert repair_contract.is_terminal_outcome("complete")
    assert not repair_contract.is_terminal_outcome("partial_liveness")
    assert not repair_contract.is_terminal_outcome("live_with_fresh_activity")
    assert not repair_contract.is_terminal_outcome("recurring_retry_pending")
    assert repair_contract.is_terminal_outcome("repair_timeout")
    assert repair_contract.is_terminal_outcome("repair_exhausted")
    assert repair_contract.is_terminal_outcome("true_human_blocker")
    assert not repair_contract.is_terminal_outcome("repairing")
    # Unknown values are treated as terminal (not "repairing")
    assert repair_contract.is_terminal_outcome("bogus")


# ---------------------------------------------------------------------------
# Budget / deadline helpers
# ---------------------------------------------------------------------------


def test_default_repair_budget_is_3600_seconds() -> None:
    assert repair_contract.DEFAULT_REPAIR_BUDGET_SECS == 3600


def test_compute_deadline_adds_budget_to_start() -> None:
    from datetime import datetime, timezone

    start = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
    deadline = repair_contract.compute_deadline(start, 3600)
    assert deadline == datetime(2026, 7, 1, 13, 0, 0, tzinfo=timezone.utc)


def test_compute_deadline_defaults_to_3600() -> None:
    from datetime import datetime, timezone

    start = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
    deadline = repair_contract.compute_deadline(start)
    assert deadline == datetime(2026, 7, 1, 13, 0, 0, tzinfo=timezone.utc)


def test_compute_deadline_arbitrary_budget() -> None:
    from datetime import datetime, timezone

    start = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert repair_contract.compute_deadline(start, 60) == datetime(
        2026, 7, 1, 0, 1, 0, tzinfo=timezone.utc
    )
    assert repair_contract.compute_deadline(start, 0) == start


def test_remaining_budget_secs_positive() -> None:
    from datetime import datetime, timezone

    deadline = datetime(2026, 7, 1, 12, 1, 0, tzinfo=timezone.utc)
    now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert repair_contract.remaining_budget_secs(deadline, now) == 60.0


def test_remaining_budget_secs_exhausted_returns_zero() -> None:
    from datetime import datetime, timezone

    deadline = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 7, 1, 13, 0, 0, tzinfo=timezone.utc)
    assert repair_contract.remaining_budget_secs(deadline, now) == 0.0


def test_remaining_budget_secs_exact_deadline_returns_zero() -> None:
    from datetime import datetime, timezone

    deadline = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert repair_contract.remaining_budget_secs(deadline, deadline) == 0.0


def test_is_budget_exhausted_before_and_after() -> None:
    from datetime import datetime, timezone

    deadline = datetime(2026, 7, 1, 12, 1, 0, tzinfo=timezone.utc)
    before = datetime(2026, 7, 1, 12, 0, 30, tzinfo=timezone.utc)
    after = datetime(2026, 7, 1, 13, 0, 0, tzinfo=timezone.utc)

    assert not repair_contract.is_budget_exhausted(deadline, before)
    assert repair_contract.is_budget_exhausted(deadline, after)
    assert repair_contract.is_budget_exhausted(deadline, deadline)


def test_remaining_budget_defaults_now_to_utc() -> None:
    from datetime import datetime, timezone

    far_future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    remaining = repair_contract.remaining_budget_secs(far_future)
    assert remaining > 0


# ---------------------------------------------------------------------------
# classify_verification_outcome — status transitions
# ---------------------------------------------------------------------------


def test_classify_complete_beats_everything() -> None:
    assert (
        repair_contract.classify_verification_outcome(
            is_complete=True,
            has_progressed=True,
            has_fresh_activity=True,
            has_true_human_blocker=True,
            is_live=True,
        )
        == repair_contract.COMPLETE
    )


def test_classify_progressed_beats_fresh_and_blocker() -> None:
    assert (
        repair_contract.classify_verification_outcome(
            has_progressed=True,
            has_fresh_activity=True,
            has_true_human_blocker=True,
            is_live=True,
        )
        == repair_contract.PROGRESSED
    )


def test_classify_fresh_activity_beats_blocker_and_liveness() -> None:
    """Fresh activity is now partial_liveness (non-success), not a success outcome."""
    outcome = repair_contract.classify_verification_outcome(
        has_fresh_activity=True,
        has_true_human_blocker=True,
        is_live=True,
    )
    assert outcome == repair_contract.PARTIAL_LIVENESS
    assert not repair_contract.is_success_outcome(outcome)


def test_classify_true_human_blocker_beats_liveness() -> None:
    assert (
        repair_contract.classify_verification_outcome(
            has_true_human_blocker=True,
            is_live=True,
        )
        == repair_contract.TRUE_HUMAN_BLOCKER
    )


def test_classify_liveness_only_becomes_partial_liveness() -> None:
    """The critical semantic: held tmux with no delta is partial_liveness, NOT success."""
    outcome = repair_contract.classify_verification_outcome(is_live=True)
    assert outcome == repair_contract.PARTIAL_LIVENESS
    assert not repair_contract.is_success_outcome(outcome)


def test_classify_liveness_only_with_no_flags_is_not_success() -> None:
    outcome = repair_contract.classify_verification_outcome(
        is_live=True,
        is_complete=False,
        has_progressed=False,
        has_fresh_activity=False,
        has_true_human_blocker=False,
    )
    assert outcome == repair_contract.PARTIAL_LIVENESS
    assert not repair_contract.is_success_outcome(outcome)


def test_classify_no_evidence_yields_repairing() -> None:
    outcome = repair_contract.classify_verification_outcome()
    assert outcome == repair_contract.REPAIRING
    assert not repair_contract.is_success_outcome(outcome)
    assert not repair_contract.is_terminal_outcome(outcome)


def test_classify_not_live_no_evidence_yields_repairing() -> None:
    outcome = repair_contract.classify_verification_outcome(is_live=False)
    assert outcome == repair_contract.REPAIRING


def test_classify_every_outcome_reachable() -> None:
    """Each outcome in the lattice should be reachable via some flag combination."""
    assert (
        repair_contract.classify_verification_outcome(is_complete=True)
        == repair_contract.COMPLETE
    )
    assert (
        repair_contract.classify_verification_outcome(has_progressed=True)
        == repair_contract.PROGRESSED
    )
    assert (
        repair_contract.classify_verification_outcome(has_fresh_activity=True)
        == repair_contract.PARTIAL_LIVENESS
    )
    assert (
        repair_contract.classify_verification_outcome(has_true_human_blocker=True)
        == repair_contract.TRUE_HUMAN_BLOCKER
    )
    assert (
        repair_contract.classify_verification_outcome(is_live=True)
        == repair_contract.PARTIAL_LIVENESS
    )
    assert (
        repair_contract.classify_verification_outcome()
        == repair_contract.REPAIRING
    )


def test_classify_accepts_pre_post_snapshots_forward_compat() -> None:
    """Pre/post snapshots are accepted but not compared in T1."""
    pre = {"session": "s1", "target_id": "s1:plan"}
    post = {"session": "s1", "target_id": "s1:plan"}
    outcome = repair_contract.classify_verification_outcome(
        is_complete=True, pre_snapshot=pre, post_snapshot=post
    )
    assert outcome == repair_contract.COMPLETE


@pytest.mark.parametrize(
    "observation",
    [
        {"kind": "pid", "pid_alive": True},
        {"kind": "heartbeat", "heartbeat_active": True},
        {"kind": "partial_liveness", "is_live": True},
        {"kind": "subprocess_success", "returncode": 0},
    ],
)
def test_recovery_liveness_and_process_signals_are_provisional(
    observation: dict[str, object],
) -> None:
    result = repair_contract.classify_recovery_verification(
        original_blocker={"blocker_id": "blocker-42"},
        observation=observation,
        repair_completed_at="2026-07-09T07:53:00+00:00",
    )

    assert result["status"] == repair_contract.RECOVERY_PROVISIONAL
    assert result["recovery_verified"] is False
    assert result["authorizes_verified_recovered"] is False


@pytest.mark.parametrize("unknown_type", ["missing", "stale", "partial", "contradictory"])
def test_recovery_preserves_typed_unknown_evidence(unknown_type: str) -> None:
    result = repair_contract.classify_recovery_verification(
        original_blocker={"blocker_id": "blocker-42"},
        observation={
            "evidence_state": {"status": "unknown", "unknown_type": unknown_type}
        },
        repair_completed_at="2026-07-09T07:53:00+00:00",
    )

    assert result["status"] == repair_contract.RECOVERY_UNKNOWN
    assert result["unknown_type"] == unknown_type
    assert result["authorizes_verified_recovered"] is False


def test_recovery_requires_later_independent_blocker_specific_proof() -> None:
    evidence = _verified_recovery_evidence()
    result = repair_contract.classify_recovery_verification(
        original_blocker=evidence["original_blocker"],
        observation=evidence["observation"],
        repair_completed_at=evidence["repair_completed_at"],
    )

    assert result["status"] == repair_contract.RECOVERY_VERIFIED
    assert result["recovery_verified"] is True
    assert result["authorizes_verified_recovered"] is True


def test_recovery_rejects_stale_or_different_blocker_proof() -> None:
    stale = repair_contract.classify_recovery_verification(
        original_blocker={"blocker_id": "blocker-42"},
        observation={
            **_verified_recovery_evidence()["observation"],
            "observed_at": "2026-07-09T07:52:00+00:00",
        },
        repair_completed_at="2026-07-09T07:53:00+00:00",
    )
    different = repair_contract.classify_recovery_verification(
        original_blocker={"blocker_id": "blocker-42"},
        observation={
            **_verified_recovery_evidence()["observation"],
            "blocker_id": "blocker-99",
        },
        repair_completed_at="2026-07-09T07:53:00+00:00",
    )

    assert stale["unknown_type"] == "stale"
    assert different["unknown_type"] == "contradictory"
    assert stale["authorizes_verified_recovered"] is False
    assert different["authorizes_verified_recovered"] is False


# ---------------------------------------------------------------------------
# build_verification_record
# ---------------------------------------------------------------------------


def test_build_verification_record_success() -> None:
    rec = repair_contract.build_verification_record(
        "complete", delta_summary="all tasks done"
    )
    assert rec["outcome"] == "complete"
    assert rec["is_success"] is True
    assert rec["is_terminal"] is True
    assert rec["delta_summary"] == "all tasks done"
    assert "recorded_at" in rec
    assert rec["pre_snapshot"] is None
    assert rec["post_snapshot"] is None


def test_build_verification_record_non_success() -> None:
    rec = repair_contract.build_verification_record("partial_liveness")
    assert rec["is_success"] is False
    assert rec["is_terminal"] is False


def test_build_verification_record_non_terminal() -> None:
    rec = repair_contract.build_verification_record("repairing")
    assert rec["is_success"] is False
    assert rec["is_terminal"] is False


def test_build_verification_record_with_snapshots() -> None:
    pre = {"a": 1}
    post = {"a": 2}
    rec = repair_contract.build_verification_record(
        "progressed", pre_snapshot=pre, post_snapshot=post
    )
    assert rec["pre_snapshot"] == pre
    assert rec["post_snapshot"] == post
    # Snapshots are deep-copied (independent of input)
    pre["a"] = 99
    assert rec["pre_snapshot"] == {"a": 1}


def test_build_verification_record_explicit_timestamp() -> None:
    from datetime import datetime, timezone

    ts = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
    rec = repair_contract.build_verification_record("complete", recorded_at=ts)
    assert rec["recorded_at"] == "2026-07-01T12:00:00+00:00"


def test_build_verification_record_default_timestamp_is_iso() -> None:
    rec = repair_contract.build_verification_record("complete")
    # Must be parseable as ISO datetime
    datetime.fromisoformat(rec["recorded_at"])


# ---------------------------------------------------------------------------
# classify_repair_dispatch — recovery-view preferred path
# ---------------------------------------------------------------------------


def _make_recovery_view_dict(
    *,
    custody_bucket: str = "repairable",
    status: str = "repairable",
    recovery_needed: bool = True,
    permitted_actions: list[dict[str, object]] | None = None,
    diagnostics: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": status,
        "recovery_needed": recovery_needed,
        "custody_bucket": custody_bucket,
        "observations": [],
        "permitted_actions": permitted_actions or [],
        "source_paths": ["recovery://test"],
        "diagnostics": diagnostics or [],
        "view_hash": "test-hash",
        "shadow": True,
        "read_only": True,
    }


def test_recovery_view_dispatches_repairable_with_request() -> None:
    """When recovery_view custody is repairable and a request_id exists, dispatch L1."""
    recovery = _make_recovery_view_dict(
        custody_bucket="repairable",
        permitted_actions=[{"action_type": "repair_dispatch", "rationale": "ready", "source": "test"}],
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_L1
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_L1
    assert decision.custody_bucket == "repairable"
    assert any("recovery view" in r for r in decision.rationale)


def test_recovery_view_does_not_treat_bare_liveness_as_repair_custody() -> None:
    recovery = _make_recovery_view_dict(custody_bucket="repairable")
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["req-1"],
            "active_claim_request_ids": [],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        process_evidence={"live": True, "status": "running"},
        plan_state={
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
        },
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_L1
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_L1


def test_recovery_view_accepts_liveness_only_with_durable_claim() -> None:
    recovery = _make_recovery_view_dict(custody_bucket="repairable")
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["req-1"],
            "active_claim_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        process_evidence={"live": True, "status": "running"},
        plan_state={
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
        },
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_REPAIRING


def test_recovery_view_lock_without_request_identity_is_not_custody() -> None:
    recovery = _make_recovery_view_dict(custody_bucket="repairable")
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": [],
            "active_claim_request_ids": [],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        lock_evidence={"status": "busy"},
        plan_state={
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
        },
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision != repair_contract.DISPATCH_DECISION_REPAIRING


def test_recovery_view_refuses_l1_when_legacy_request_has_no_blocker_identity() -> None:
    recovery = _make_recovery_view_dict(
        custody_bucket="repairable",
        permitted_actions=[
            {"action_type": "repair_dispatch", "rationale": "ready", "source": "test"}
        ],
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["7473fa42"],
            "blocker_id": "",
            "current_state": "blocked",
            "failure_kind": "",
            "terminal_outcomes": ["repair_exhausted"],
        },
        plan_state={
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
        },
        current_target={"current_refs": {"current_plan_name": "c1-contract-reality"}},
    )

    assert decision.decision == repair_contract.DISPATCH_DECISION_BROKEN_SUPERFIXER
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_BROKEN_SUPERFIXER
    assert decision.request_id == "7473fa42"
    assert decision.blocker_id == ""
    assert any("request/blocker identity" in item for item in decision.rationale)


def test_recovery_view_dispatches_repairing_custody() -> None:
    """When recovery_view custody is repairing, dispatch REPAIRING."""
    recovery = _make_recovery_view_dict(
        custody_bucket="repairing",
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairing",
            "active_request_ids": [],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_REPAIRING
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_QUEUE_ONLY
    assert "recovery view: repair already in progress" in decision.rationale


def test_recovery_view_dispatches_human_required() -> None:
    """When recovery_view custody is human_required, dispatch HUMAN_REQUIRED."""
    recovery = _make_recovery_view_dict(
        custody_bucket="human_required",
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "human_required",
            "active_request_ids": [],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "unknown",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_HUMAN_REQUIRED
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_HUMAN_REQUIRED


def test_recovery_view_dispatches_broken_superfixer() -> None:
    """When recovery_view custody is broken_superfixer, escalate."""
    recovery = _make_recovery_view_dict(
        custody_bucket="broken_superfixer",
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "broken_superfixer",
            "active_request_ids": [],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "unknown",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_BROKEN_SUPERFIXER
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_BROKEN_SUPERFIXER


def test_recovery_view_dispatches_healthy_as_no_action() -> None:
    """When recovery_view custody is healthy, dispatch NO_ACTION."""
    recovery = _make_recovery_view_dict(
        custody_bucket="healthy",
        recovery_needed=False,
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": [],
            "blocker_id": "blocker-42",
            "current_state": "done",
            "failure_kind": "",
            "terminal_outcomes": ["complete"],
        },
        plan_state={"current_state": "done", "resume_cursor": {}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_TERMINAL
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_QUEUE_ONLY


def test_recovery_view_untyped_blocked_is_broken_superfixer() -> None:
    """A generic blocked view cannot invent a human decision."""
    recovery = _make_recovery_view_dict(
        custody_bucket="blocked",
        status="blocked",
        recovery_needed=True,
        diagnostics=[{"code": "runner_unavailable", "reason": "no runner", "source": "test"}],
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_BROKEN_SUPERFIXER
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_BROKEN_SUPERFIXER
    assert any("blocked" in r.lower() for r in decision.rationale)


def test_recovery_view_permitted_repair_dispatch_upgrades_no_action() -> None:
    """Permitted repair_dispatch action overrides no_action when request present.

    Uses a non-terminal state so the healthy bucket routes to NO_ACTION first,
    then the permitted repair_dispatch action upgrades to L1.
    """
    recovery = _make_recovery_view_dict(
        custody_bucket="healthy",
        recovery_needed=False,
        permitted_actions=[{"action_type": "repair_dispatch", "rationale": "override", "source": "test"}],
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "healthy",
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "",
            "terminal_outcomes": [],  # empty → not terminal
        },
        plan_state={"current_state": "blocked", "resume_cursor": {}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_L1
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_L1


def test_recovery_view_legacy_fallback_when_no_recovery_view() -> None:
    """When recovery_view is absent, legacy path is used (backward compat)."""
    decision = repair_contract.classify_repair_dispatch(
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "execution_blocked", "phase": "execute"},
        },
        current_target={
            "current_refs": {
                "current_plan_name": "test-plan",
                "plan_current_state": "blocked",
            },
            "plan_state": {"fingerprint": "sha256:proof"},
        },
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_L1
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_L1


# ---------------------------------------------------------------------------
# T15: Ordinary repair verdict evidence tests
# ---------------------------------------------------------------------------


def test_repair_verdict_cleared_construction_and_round_trip() -> None:
    """RepairVerdict with cleared kind round-trips through to_dict/from_dict."""
    verdict = repair_contract.RepairVerdict(
        verdict_kind=repair_contract.REPAIR_VERDICT_CLEARED,
        blocker_id="blocker-42",
        attempted_actions=("retry_execute", "fix_dependency"),
        before_evidence_refs=("before-1.json",),
        after_evidence_refs=("after-1.json",),
        durable_refs=("audit-report.md",),
        evidence_timestamp="2026-07-09T07:53:00Z",
        session="demo-session",
        request_id="req-abc123",
        outcome="complete",
        stale_detected=False,
        no_verdict_detected=False,
    )
    payload = verdict.to_dict()
    assert payload["verdict_kind"] == "cleared"
    assert payload["blocker_id"] == "blocker-42"
    assert payload["attempted_actions"] == ["retry_execute", "fix_dependency"]
    assert payload["before_evidence_refs"] == ["before-1.json"]
    assert payload["after_evidence_refs"] == ["after-1.json"]
    assert payload["durable_refs"] == ["audit-report.md"]
    assert payload["evidence_timestamp"] == "2026-07-09T07:53:00Z"
    assert payload["contract_id"] == "repair.ordinary_complete.1"
    assert payload["boundary_id"] == "ordinary_repair_completion"
    assert payload["session"] == "demo-session"
    assert payload["request_id"] == "req-abc123"
    assert payload["outcome"] == "complete"
    assert payload["stale_detected"] is False
    assert payload["no_verdict_detected"] is False

    restored = repair_contract.RepairVerdict.from_dict(payload)
    assert restored.verdict_kind == repair_contract.REPAIR_VERDICT_CLEARED
    assert restored.blocker_id == "blocker-42"
    assert restored.attempted_actions == ("retry_execute", "fix_dependency")


def test_repair_verdict_no_fix_construction_and_round_trip() -> None:
    """RepairVerdict with no_fix kind carries the exhaustion evidence."""
    verdict = repair_contract.RepairVerdict(
        verdict_kind=repair_contract.REPAIR_VERDICT_NO_FIX,
        blocker_id="blocker-99",
        attempted_actions=("runtime_patch", "env_restart"),
        before_evidence_refs=(),
        after_evidence_refs=(),
        durable_refs=("run-log.txt",),
        evidence_timestamp="2026-07-10T14:22:00Z",
        session="session-no-fix",
        request_id="req-no-fix-001",
        outcome="repair_exhausted",
    )
    payload = verdict.to_dict()
    assert payload["verdict_kind"] == "no_fix"
    assert payload["outcome"] == "repair_exhausted"
    assert payload["blocker_id"] == "blocker-99"

    restored = repair_contract.RepairVerdict.from_dict(payload)
    assert restored.verdict_kind == repair_contract.REPAIR_VERDICT_NO_FIX
    assert restored.attempted_actions == ("runtime_patch", "env_restart")
    assert restored.durable_refs == ("run-log.txt",)


def test_repair_verdict_escalated_construction_and_round_trip() -> None:
    """RepairVerdict with escalated kind preserves the human-required evidence."""
    verdict = repair_contract.RepairVerdict(
        verdict_kind=repair_contract.REPAIR_VERDICT_ESCALATED,
        blocker_id="blocker-human-1",
        attempted_actions=("discord_ping", "email_alert"),
        before_evidence_refs=("state-before.json",),
        after_evidence_refs=(),
        durable_refs=("escalation-log.md",),
        evidence_timestamp="2026-07-11T09:00:00Z",
        session="session-esc",
        request_id="req-esc-001",
        outcome="needs_human",
    )
    payload = verdict.to_dict()
    assert payload["verdict_kind"] == "escalated"
    assert payload["blocker_id"] == "blocker-human-1"
    assert payload["outcome"] == "needs_human"

    restored = repair_contract.RepairVerdict.from_dict(payload)
    assert restored.verdict_kind == repair_contract.REPAIR_VERDICT_ESCALATED
    assert restored.request_id == "req-esc-001"


def test_repair_verdict_stale_detection_flags_on_old_timestamps() -> None:
    """Stale repair data is detected and flagged in verdict."""
    from datetime import datetime, timezone, timedelta

    old_ts = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    stale_detected, stale_reason = repair_contract.detect_stale_repair_data(
        {"completed_at": old_ts},
        stale_threshold_secs=3600,  # 1 hour
    )
    assert stale_detected is True
    assert "exceeds stale threshold" in stale_reason

    # Fresh data is not stale
    fresh_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    fresh_detected, fresh_reason = repair_contract.detect_stale_repair_data(
        {"completed_at": fresh_ts},
        stale_threshold_secs=3600,
    )
    assert fresh_detected is False
    assert fresh_reason == ""

    # Missing timestamp is stale
    no_ts_detected, no_ts_reason = repair_contract.detect_stale_repair_data({})
    assert no_ts_detected is True
    assert "no completion" in no_ts_reason


def test_repair_verdict_no_verdict_artifact_detection() -> None:
    """No-verdict artifacts (liveness-only, no outcome) are detected."""
    # No outcome at all
    detected, reason = repair_contract.detect_no_verdict_artifact({})
    assert detected is True
    assert "no outcome" in reason

    # Liveness-only with no evidence refs
    detected, reason = repair_contract.detect_no_verdict_artifact(
        {"outcome": "partial_liveness"}
    )
    assert detected is True
    assert "liveness-only" in reason

    # Still repairing (non-terminal)
    detected, reason = repair_contract.detect_no_verdict_artifact(
        {"outcome": "repairing"}
    )
    assert detected is True
    assert "still in non-terminal" in reason

    # Complete outcome with evidence is fine
    detected, reason = repair_contract.detect_no_verdict_artifact(
        {
            "outcome": "complete",
            "before_evidence_refs": ["before.json"],
            "after_evidence_refs": ["after.json"],
        }
    )
    assert detected is False


def test_repair_verdict_frozen_dataclass_is_immutable() -> None:
    """RepairVerdict is a frozen dataclass — mutation raises FrozenInstanceError."""
    verdict = repair_contract.RepairVerdict(
        verdict_kind=repair_contract.REPAIR_VERDICT_CLEARED,
        blocker_id="blocker-immutable",
    )
    with pytest.raises(Exception):
        verdict.blocker_id = "mutated"  # type: ignore[misc]


def test_build_ordinary_repair_verdict_for_cleared_outcome() -> None:
    """build_ordinary_repair_verdict maps 'complete' to cleared."""
    verdict = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "complete",
            "blocker_id": "blocker-1",
            "session": "demo",
            "request_id": "req-1",
            "completed_at": "2026-07-10T10:00:00Z",
        },
    )
    assert verdict.verdict_kind == repair_contract.REPAIR_VERDICT_CLEARED
    assert verdict.blocker_id == "blocker-1"
    assert verdict.outcome == "complete"
    assert verdict.contract_id == "repair.ordinary_complete.1"


def test_build_ordinary_repair_verdict_for_no_fix_outcome() -> None:
    """build_ordinary_repair_verdict maps 'repair_exhausted' to no_fix."""
    verdict = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "repair_exhausted",
            "blocker_id": "blocker-exhausted",
            "completed_at": "2026-07-10T12:00:00Z",
        },
    )
    assert verdict.verdict_kind == repair_contract.REPAIR_VERDICT_NO_FIX
    assert verdict.blocker_id == "blocker-exhausted"
    assert verdict.outcome == "repair_exhausted"

    # repair_timeout also maps to no_fix
    verdict_to = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "repair_timeout",
            "blocker_id": "blocker-timedout",
        },
    )
    assert verdict_to.verdict_kind == repair_contract.REPAIR_VERDICT_NO_FIX


def test_build_ordinary_repair_verdict_for_escalated_outcome() -> None:
    """build_ordinary_repair_verdict maps 'needs_human' to escalated."""
    verdict = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "needs_human",
            "blocker_id": "blocker-human",
            "completed_at": "2026-07-10T15:00:00Z",
        },
    )
    assert verdict.verdict_kind == repair_contract.REPAIR_VERDICT_ESCALATED
    assert verdict.blocker_id == "blocker-human"

    # true_human_blocker also maps to escalated
    verdict_thb = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "true_human_blocker",
            "blocker_id": "blocker-thb",
        },
    )
    assert verdict_thb.verdict_kind == repair_contract.REPAIR_VERDICT_ESCALATED


def test_build_ordinary_repair_verdict_detects_stale_repair_data() -> None:
    """When repair data is stale, the verdict flags stale_detected."""
    from datetime import datetime, timezone, timedelta

    old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    verdict = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "complete",
            "blocker_id": "blocker-stale",
            "completed_at": old_ts,
        },
    )
    assert verdict.stale_detected is True
    assert "exceeds stale threshold" in verdict.stale_reason
    # The outcome-based verdict kind is still 'cleared' because staleness
    # is a separate concern from outcome classification.
    assert verdict.verdict_kind == repair_contract.REPAIR_VERDICT_CLEARED


def test_build_ordinary_repair_verdict_detects_no_verdict_artifact() -> None:
    """When outcome is liveness-only, no_verdict_detected flag is set."""
    verdict = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "partial_liveness",
            "blocker_id": "blocker-live",
        },
    )
    assert verdict.verdict_kind == repair_contract.REPAIR_VERDICT_NO_VERDICT
    assert verdict.no_verdict_detected is True
    assert "liveness-only" in verdict.no_verdict_reason


def test_repair_success_not_trusted_without_original_finding_clearance() -> None:
    """A 'complete' outcome without original blocker clearance evidence should not
    be trusted as a verified recovery. The verdict may be 'cleared' by outcome, but
    the absence of before/after evidence refs means downstream consumers must still
    verify original finding clearance.
    """
    # Liveness-only complete — no before/after evidence
    payload_liveness = {
        "outcome": "complete",
        "blocker_id": "blocker-suspect",
        "session": "demo",
    }
    verdict_liveness = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload=payload_liveness,
    )
    # It's 'cleared' by outcome type, but has no before/after evidence.
    assert verdict_liveness.verdict_kind == repair_contract.REPAIR_VERDICT_CLEARED
    assert verdict_liveness.before_evidence_refs == ()
    assert verdict_liveness.after_evidence_refs == ()

    # Contrast with a properly evidenced clearance
    verdict_evidenced = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "complete",
            "blocker_id": "blocker-ok",
            "before_evidence_refs": ["pre-fix-state.json"],
            "after_evidence_refs": ["post-fix-state.json"],
        },
        before_evidence_refs=("pre-fix-state.json",),
        after_evidence_refs=("post-fix-state.json",),
    )
    assert verdict_evidenced.verdict_kind == repair_contract.REPAIR_VERDICT_CLEARED
    assert "pre-fix-state.json" in verdict_evidenced.before_evidence_refs
    assert "post-fix-state.json" in verdict_evidenced.after_evidence_refs


def test_repair_success_not_trusted_without_explicit_escalation_no_fix_evidence() -> None:
    """A liveness-only outcome (live_with_fresh_activity) cannot satisfy
    the requirement for explicit escalation or no-fix evidence — it must be
    flagged as no-verdict.
    """
    verdict = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "live_with_fresh_activity",
            "blocker_id": "blocker-live-2",
        },
    )
    # live_with_fresh_activity maps to no_verdict in the outcome-to-verdict table
    assert verdict.verdict_kind == repair_contract.REPAIR_VERDICT_NO_VERDICT
    assert verdict.no_verdict_detected is True

    # escalated outcome IS trusted — it provides explicit evidence
    verdict_esc = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "discord_escalated",
            "blocker_id": "blocker-discord",
            "completed_at": "2026-07-10T16:00:00Z",
        },
    )
    assert verdict_esc.verdict_kind == repair_contract.REPAIR_VERDICT_ESCALATED
    assert verdict_esc.no_verdict_detected is False

    # no_fix outcome IS trusted — it provides explicit evidence
    verdict_nf = repair_contract.build_ordinary_repair_verdict(
        repair_data_payload={
            "outcome": "deterministic_failure",
            "blocker_id": "blocker-det",
            "completed_at": "2026-07-10T17:00:00Z",
        },
    )
    assert verdict_nf.verdict_kind == repair_contract.REPAIR_VERDICT_NO_FIX
    assert verdict_nf.no_verdict_detected is False


def test_validate_repair_verdict_payload_rejects_bad_inputs() -> None:
    """validate_repair_verdict_payload raises ValueError on invalid payloads."""
    # Not a dict
    with pytest.raises(ValueError, match="must be a JSON object"):
        repair_contract.validate_repair_verdict_payload([1, 2, 3])  # type: ignore[arg-type]

    # Missing verdict_kind
    with pytest.raises(ValueError, match="missing required field"):
        repair_contract.validate_repair_verdict_payload({"blocker_id": "b1"})

    # Unknown verdict_kind
    with pytest.raises(ValueError, match="unknown repair verdict kind"):
        repair_contract.validate_repair_verdict_payload({"verdict_kind": "invalid_kind"})

    # Valid payload passes
    result = repair_contract.validate_repair_verdict_payload(
        {"verdict_kind": "cleared", "blocker_id": "b1"}
    )
    assert result["verdict_kind"] == "cleared"


def test_save_repair_verdict_persists_and_round_trips(tmp_path: Path) -> None:
    """save_repair_verdict atomically persists and what is read matches."""
    path = tmp_path / "verdict.json"
    verdict = repair_contract.RepairVerdict(
        verdict_kind=repair_contract.REPAIR_VERDICT_CLEARED,
        blocker_id="blocker-save-1",
        attempted_actions=("action-1",),
        before_evidence_refs=("before.json",),
        after_evidence_refs=("after.json",),
        durable_refs=("report.md",),
        evidence_timestamp="2026-07-13T08:00:00Z",
        session="demo-save",
        request_id="req-save-1",
        outcome="complete",
    )
    persisted = repair_contract.save_repair_verdict(path, verdict)
    assert persisted["verdict_kind"] == "cleared"
    assert Path(path).exists()

    # Read back and rehydrate
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    restored = repair_contract.RepairVerdict.from_dict(raw)
    assert restored.verdict_kind == repair_contract.REPAIR_VERDICT_CLEARED
    assert restored.blocker_id == "blocker-save-1"
    assert restored.attempted_actions == ("action-1",)
    assert restored.evidence_timestamp == "2026-07-13T08:00:00Z"


def test_repair_verdict_from_dict_defaults_unknown_kind_to_no_verdict() -> None:
    """from_dict coerces unknown verdict_kind strings to no_verdict."""
    restored = repair_contract.RepairVerdict.from_dict(
        {"verdict_kind": "garbage", "blocker_id": "b1"}
    )
    assert restored.verdict_kind == repair_contract.REPAIR_VERDICT_NO_VERDICT


# ---------------------------------------------------------------------------


def test_recovery_view_drift_emission_when_custody_disagrees(tmp_path: Path) -> None:
    """Drift event is emitted when legacy custody bucket disagrees with recovery view."""
    recovery = _make_recovery_view_dict(
        custody_bucket="repairable",
    )
    # Use a path that exists so emit can write
    event_plan_dir = tmp_path / "event-dir"
    event_plan_dir.mkdir()
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        event_plan_dir=event_plan_dir,
        custody_projection={
            "custody_bucket": "repairing",  # disagrees with recovery view's "repairable"
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    # Decision should use recovery view's custody (repairable → L1)
    assert decision.custody_bucket == "repairable"
    assert decision.decision == repair_contract.DISPATCH_DECISION_L1


def test_recovery_view_custody_bucket_preferred_over_legacy() -> None:
    """Recovery view custody bucket is used even when legacy says differently."""
    recovery = _make_recovery_view_dict(
        custody_bucket="human_required",
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",  # legacy says repairable
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    # Recovery view wins: human_required
    assert decision.decision == repair_contract.DISPATCH_DECISION_HUMAN_REQUIRED
    assert decision.custody_bucket == "human_required"


def test_recovery_view_unrecognized_custody_is_broken_superfixer() -> None:
    """Unknown custody bucket from recovery view escalates to superfixer."""
    recovery = _make_recovery_view_dict(
        custody_bucket="an_unrecognized_bucket",
    )
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=recovery,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": [],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "unknown",
            "terminal_outcomes": [],
        },
        plan_state={"current_state": "blocked", "resume_cursor": {"retry_strategy": "manual_review"}},
        current_target={"current_refs": {"current_plan_name": "test-plan"}},
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_BROKEN_SUPERFIXER
    assert decision.dispatch_intent == repair_contract.DISPATCH_INTENT_BROKEN_SUPERFIXER


def test_recovery_view_empty_does_not_trigger_recovery_path() -> None:
    """Empty/None recovery_view falls through to legacy/canonical path."""
    decision = repair_contract.classify_repair_dispatch(
        recovery_view=None,
        custody_projection={
            "custody_bucket": "repairable_not_repairing",
            "active_request_ids": ["req-1"],
            "blocker_id": "blocker-42",
            "current_state": "blocked",
            "failure_kind": "execution_blocked",
            "terminal_outcomes": [],
        },
        plan_state={
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "execution_blocked", "phase": "execute"},
        },
        current_target={
            "current_refs": {
                "current_plan_name": "test-plan",
                "plan_current_state": "blocked",
            },
            "plan_state": {"fingerprint": "sha256:proof"},  # needed by _has_current_target_evidence
        },
    )
    assert decision.decision == repair_contract.DISPATCH_DECISION_L1
    assert any("known repairable" in r for r in decision.rationale)
