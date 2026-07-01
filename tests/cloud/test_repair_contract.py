from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.redact import REDACTION, redact_text


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


def test_repair_contract_round_trips_legacy_payload_without_shape_changes(tmp_path: Path) -> None:
    path = tmp_path / "repair-data.json"
    payload = _legacy_payload()

    repair_contract.save_repair_data(path, payload)

    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert repair_contract.load_json(path) == payload


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
