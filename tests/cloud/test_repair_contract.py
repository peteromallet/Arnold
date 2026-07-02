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


def test_success_outcomes_match_planned_lattice() -> None:
    assert repair_contract.SUCCESS_OUTCOMES == frozenset(
        {"complete", "progressed", "live_with_fresh_activity", "true_human_blocker"}
    )


def test_non_success_outcomes_include_liveness_and_exhaustion() -> None:
    assert "partial_liveness" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "repair_timeout" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "repair_exhausted" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "needs_human" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "repairing" in repair_contract.NON_SUCCESS_OUTCOMES
    assert "discord_escalated" in repair_contract.NON_SUCCESS_OUTCOMES


def test_all_outcomes_union_covers_both_sets() -> None:
    assert repair_contract.ALL_OUTCOMES == (
        repair_contract.SUCCESS_OUTCOMES | repair_contract.NON_SUCCESS_OUTCOMES
    )
    # Sanity: these are disjoint
    assert repair_contract.SUCCESS_OUTCOMES.isdisjoint(repair_contract.NON_SUCCESS_OUTCOMES)


def test_is_success_outcome_only_accepts_four_values() -> None:
    for outcome in repair_contract.ALL_OUTCOMES:
        expected = outcome in repair_contract.SUCCESS_OUTCOMES
        assert repair_contract.is_success_outcome(outcome) == expected, (
            f"is_success_outcome({outcome!r}) returned unexpected {not expected}"
        )


def test_is_success_outcome_unknown_value_not_in_lattice() -> None:
    assert not repair_contract.is_success_outcome("bogus")
    assert not repair_contract.is_success_outcome("")


def test_is_terminal_outcome() -> None:
    assert repair_contract.is_terminal_outcome("complete")
    assert repair_contract.is_terminal_outcome("partial_liveness")
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
    assert (
        repair_contract.classify_verification_outcome(
            has_fresh_activity=True,
            has_true_human_blocker=True,
            is_live=True,
        )
        == repair_contract.LIVE_WITH_FRESH_ACTIVITY
    )


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
        == repair_contract.LIVE_WITH_FRESH_ACTIVITY
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
    assert rec["is_terminal"] is True


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
