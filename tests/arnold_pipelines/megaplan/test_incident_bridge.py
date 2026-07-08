"""Tests for incident_bridge integration in save_repair_data().

Covers:
- JSON persistence (repair-data + index.json)
- Index updates per session
- Incident event append for meaningful transitions
- Legacy outcome mapping (repairing → meta_repair_attempt,
  success → verified_recovered, terminal non-success → meta_repair_attempt)
- No duplicate event on no-op save (same outcome)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.repair_contract import (
    COMPLETE,
    DISCORD_ESCALATED,
    NEEDS_HUMAN,
    PARTIAL_LIVENESS,
    PROGRESSED,
    REPAIR_EXHAUSTED,
    REPAIR_TIMEOUT,
    REPAIRING,
    LIVE_WITH_FRESH_ACTIVITY,
    TRUE_HUMAN_BLOCKER,
)
from arnold_pipelines.megaplan.cloud.incident_bridge import (
    append_github_issue_publish_failed,
    append_github_issue_published,
    append_meta_repair_attempt,
    append_six_hour_auditor_audit_complete,
    append_six_hour_auditor_diagnosis,
    append_verified_recovered,
)
from arnold_pipelines.megaplan.incident import IncidentLedger


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _repair_payload(
    *,
    session: str = "demo-session",
    outcome: str = REPAIRING,
    incident_id: str = "inc-100",
    workspace: str = "/workspace/project",
    plan_name: str = "m1-plan",
    run_kind: str = "chain",
) -> dict[str, object]:
    return {
        "session": session,
        "workspace": workspace,
        "run_kind": run_kind,
        "plan_name": plan_name,
        "outcome": outcome,
        "incident_id": incident_id,
        "attempt_ids": ["attempt-1"],
        "verification": {
            "outcome": outcome,
            "is_success": repair_contract.is_success_outcome(outcome),
            "is_terminal": repair_contract.is_terminal_outcome(outcome),
            "recorded_at": "2026-07-03T20:00:00+00:00",
        },
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


# ---------------------------------------------------------------------------
# JSON persistence tests
# ---------------------------------------------------------------------------


def test_save_repair_data_persists_json_correctly(tmp_path: Path) -> None:
    """save_repair_data writes valid, complete JSON to disk."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = _repair_payload(outcome=REPAIRING)

    result = repair_contract.save_repair_data(path, payload, root=tmp_path)

    # Result is the prepared (redacted) payload
    assert result["session"] == "demo-session"
    assert result["outcome"] == REPAIRING
    # File on disk matches
    disk = json.loads(path.read_text(encoding="utf-8"))
    assert disk["session"] == "demo-session"
    assert disk["outcome"] == REPAIRING


def test_save_repair_data_updates_index_json(tmp_path: Path) -> None:
    """save_repair_data writes/updates repair-data/index.json."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = _repair_payload(outcome=REPAIRING)

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    index_path = repair_dir / "index.json"
    assert index_path.exists(), "index.json must be created"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert "sessions" in index
    assert "demo-session" in index["sessions"]
    entry = index["sessions"]["demo-session"]
    assert entry["status"] == REPAIRING
    assert entry["incident_id"] == "inc-100"
    assert entry["attempt_ids"] == ["attempt-1"]


# ---------------------------------------------------------------------------
# Event append tests — meaningful transitions
# ---------------------------------------------------------------------------


def test_first_save_emits_event_for_repairing_outcome(tmp_path: Path) -> None:
    """First-ever save with outcome='repairing' appends a meta_repair_attempt event."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = _repair_payload(outcome=REPAIRING)

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1, f"expected 1 event, got {len(events)}"
    event = events[0]
    payload_inner = event["payload"]
    assert payload_inner["type"] == "repair_attempt"
    assert payload_inner["actor"] == "meta_repair"
    assert payload_inner["outcome"] == "attempted"
    assert payload_inner["incident_id"] == "inc-100"
    assert payload_inner.get("session_id") == "demo-session"


def test_first_save_emits_event_for_complete_outcome(tmp_path: Path) -> None:
    """First-ever save with outcome='complete' appends a verified_recovered event."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = _repair_payload(outcome=COMPLETE)

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1
    event = events[0]
    payload_inner = event["payload"]
    assert payload_inner["type"] == "verified_recovered"
    assert payload_inner["actor"] == "repair_system"
    assert payload_inner["outcome"] == "recovered"
    assert payload_inner["incident_id"] == "inc-100"
    assert payload_inner.get("session_id") == "demo-session"


def test_outcome_transition_emits_new_event(tmp_path: Path) -> None:
    """Transitioning from 'repairing' to 'complete' emits a new event."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"

    # First save — repairing
    repair_contract.save_repair_data(path, _repair_payload(outcome=REPAIRING), root=tmp_path)
    # Second save — complete (transition)
    repair_contract.save_repair_data(path, _repair_payload(outcome=COMPLETE), root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 2, f"expected 2 events, got {len(events)}"
    assert events[0]["payload"]["type"] == "repair_attempt"
    assert events[1]["payload"]["type"] == "verified_recovered"


def test_no_duplicate_event_on_noop_save(tmp_path: Path) -> None:
    """Saving with the same outcome twice does NOT produce duplicate events."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = _repair_payload(outcome=REPAIRING)

    # Two saves with identical outcome
    repair_contract.save_repair_data(path, payload, root=tmp_path)
    repair_contract.save_repair_data(path, payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1, f"expected exactly 1 event, got {len(events)}"


def test_noop_save_preserves_index_but_not_events(tmp_path: Path) -> None:
    """No-op save still updates the index JSON but emits no new ledger events."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"

    repair_contract.save_repair_data(path, _repair_payload(outcome=REPAIRING), root=tmp_path)
    # Modify a non-outcome field and re-save with same outcome
    modified = _repair_payload(outcome=REPAIRING)
    modified["attempt_ids"] = ["attempt-1", "attempt-2"]
    repair_contract.save_repair_data(path, modified, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1, "no new event for same-outcome save"

    # Index still updated
    index = json.loads((repair_dir / "index.json").read_text(encoding="utf-8"))
    assert index["sessions"]["demo-session"]["attempt_ids"] == ["attempt-1", "attempt-2"]


# ---------------------------------------------------------------------------
# Legacy outcome mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome,expected_type,expected_actor,expected_event_outcome",
    [
        # Terminal success → verified_recovered
        (COMPLETE, "verified_recovered", "repair_system", "recovered"),
        (PROGRESSED, "verified_recovered", "repair_system", "recovered"),
        (LIVE_WITH_FRESH_ACTIVITY, "verified_recovered", "repair_system", "recovered"),
        (TRUE_HUMAN_BLOCKER, "verified_recovered", "repair_system", "recovered"),
        # Non-terminal repairing → meta_repair_attempt with outcome="attempted"
        (REPAIRING, "repair_attempt", "meta_repair", "attempted"),
        # Terminal non-success → meta_repair_attempt with original outcome
        (REPAIR_TIMEOUT, "repair_attempt", "meta_repair", REPAIR_TIMEOUT),
        (REPAIR_EXHAUSTED, "repair_attempt", "meta_repair", REPAIR_EXHAUSTED),
        (NEEDS_HUMAN, "repair_attempt", "meta_repair", NEEDS_HUMAN),
        (PARTIAL_LIVENESS, "repair_attempt", "meta_repair", PARTIAL_LIVENESS),
        (DISCORD_ESCALATED, "repair_attempt", "meta_repair", DISCORD_ESCALATED),
    ],
)
def test_legacy_outcome_mapping(
    tmp_path: Path,
    outcome: str,
    expected_type: str,
    expected_actor: str,
    expected_event_outcome: str,
) -> None:
    """Every legacy repair outcome maps to the correct incident event type/actor/outcome."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "demo-session.repair-data.json"
    payload = _repair_payload(outcome=outcome)

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1, f"expected 1 event for outcome={outcome}, got {len(events)}"
    inner = events[0]["payload"]
    assert inner["type"] == expected_type, (
        f"outcome={outcome}: expected type={expected_type}, got {inner['type']}"
    )
    assert inner["actor"] == expected_actor, (
        f"outcome={outcome}: expected actor={expected_actor}, got {inner['actor']}"
    )
    assert inner["outcome"] == expected_event_outcome, (
        f"outcome={outcome}: expected event outcome={expected_event_outcome}, "
        f"got {inner['outcome']}"
    )
    assert inner["incident_id"] == "inc-100"
    assert inner.get("session_id") == "demo-session"


# ---------------------------------------------------------------------------
# Bridge helpers: direct unit tests
# ---------------------------------------------------------------------------


def test_bridge_append_meta_repair_attempt_creates_event(tmp_path: Path) -> None:
    """Direct call to append_meta_repair_attempt writes a valid event."""
    result = append_meta_repair_attempt(
        incident_id="inc-200",
        summary="Repair attempted with model gpt-5",
        attempt_id="attempt-abc",
        outcome="attempted",
        session_id="session-xyz",
        root=tmp_path,
    )

    assert result["kind"] == "incident.repair_attempt"
    assert result["payload"]["type"] == "repair_attempt"
    assert result["payload"]["incident_id"] == "inc-200"

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1


def test_bridge_append_verified_recovered_creates_event(tmp_path: Path) -> None:
    """Direct call to append_verified_recovered writes a valid event."""
    result = append_verified_recovered(
        incident_id="inc-300",
        summary="Full chain verified: source-fix → install-sync → retrigger → recovered",
        session_id="session-abc",
        root=tmp_path,
    )

    assert result["kind"] == "incident.verified_recovered"
    assert result["payload"]["type"] == "verified_recovered"
    assert result["payload"]["outcome"] == "recovered"
    assert result["payload"]["next_expected_event"] is None

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1


def test_bridge_append_six_hour_auditor_diagnosis_creates_event(tmp_path: Path) -> None:
    result = append_six_hour_auditor_diagnosis(
        incident_id="inc-400",
        summary="Audit found stale repair evidence",
        session_id="session-audit",
        problem_id="prob-audit",
        next_expected_event="meta_repair.repair_attempt",
        decision={"layers": [{"code": "stale_repair"}]},
        root=tmp_path,
    )

    assert result["kind"] == "incident.six_hour_auditor.diagnosis"
    assert result["payload"]["actor"] == "six_hour_auditor"
    assert result["payload"]["type"] == "six_hour_auditor.diagnosis"
    assert result["payload"]["next_expected_event"] == "meta_repair.repair_attempt"
    assert result["payload"]["decision"] == {"layers": [{"code": "stale_repair"}]}


@pytest.mark.parametrize(
    ("outcome", "next_expected_event"),
    [
        ("recovered", None),
        ("escalated", "github_sync.publish"),
        ("audit_cycle_complete", "six_hour_auditor.diagnosis"),
        ("auditor_human_escalation", None),
    ],
)
def test_bridge_append_six_hour_auditor_audit_complete_allows_expected_handoffs(
    tmp_path: Path,
    outcome: str,
    next_expected_event: str | None,
) -> None:
    result = append_six_hour_auditor_audit_complete(
        incident_id="inc-401",
        summary="Audit cycle recorded",
        outcome=outcome,
        next_expected_event=next_expected_event,
        deadline_ts="2026-07-04T00:00:00+00:00",
        root=tmp_path,
    )

    assert result["kind"] == "incident.six_hour_auditor.audit_complete"
    assert result["payload"]["outcome"] == outcome
    assert result["payload"]["next_expected_event"] == next_expected_event


def test_bridge_append_six_hour_auditor_audit_complete_rejects_invalid_outcome(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outcome must be one of"):
        append_six_hour_auditor_audit_complete(
            incident_id="inc-402",
            summary="Audit cycle recorded",
            outcome="failed",
            root=tmp_path,
        )


def test_bridge_append_six_hour_auditor_audit_complete_rejects_invalid_handoff(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="next_expected_event must be one of"):
        append_six_hour_auditor_audit_complete(
            incident_id="inc-403",
            summary="Audit cycle recorded",
            outcome="escalated",
            next_expected_event="watchdog.dispatch",
            root=tmp_path,
        )


def test_bridge_append_github_issue_events_create_schema_valid_records(tmp_path: Path) -> None:
    published = append_github_issue_published(
        incident_id="inc-404",
        problem_id="prob-404",
        summary="Published persistent problem to GitHub",
        repo="acme/repo",
        number=77,
        url="https://github.com/acme/repo/issues/77",
        action="created",
        next_expected_event="six_hour_auditor.diagnosis",
        root=tmp_path,
    )
    failed = append_github_issue_publish_failed(
        incident_id="inc-404",
        problem_id="prob-404",
        summary="GitHub publish failed",
        repo="acme/repo",
        action="commented",
        error="rate limited",
        root=tmp_path,
    )

    assert published["kind"] == "incident.github_sync.issue_published"
    assert published["payload"]["evidence"][-1] == {
        "kind": "github.issue",
        "repo": "acme/repo",
        "number": 77,
        "url": "https://github.com/acme/repo/issues/77",
        "action": "created",
    }
    assert failed["kind"] == "incident.github_sync.issue_publish_failed"
    assert failed["payload"]["next_expected_event"] == "github_sync.retry"
    assert failed["payload"]["evidence"][-1] == {
        "kind": "github.issue",
        "repo": "acme/repo",
        "action": "commented",
        "error": "rate limited",
    }


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_save_without_incident_id_does_not_emit_event(tmp_path: Path) -> None:
    """When incident_id is missing, no bridge event is emitted (but JSON is saved)."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "no-incident.repair-data.json"
    payload = _repair_payload(outcome=REPAIRING)
    payload.pop("incident_id", None)

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    # JSON is still persisted
    assert path.exists()
    # No incident event emitted
    events = _read_ledger_events(tmp_path)
    assert len(events) == 0


def test_save_without_session_uses_path_stem(tmp_path: Path) -> None:
    """When session is empty, the filename stem is used as session in index."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "auto-session.repair-data.json"
    payload = _repair_payload(outcome=COMPLETE)
    payload.pop("session", None)  # remove explicit session

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    index = json.loads((repair_dir / "index.json").read_text(encoding="utf-8"))
    assert "auto-session" in index["sessions"]
    assert index["sessions"]["auto-session"]["status"] == COMPLETE


def test_previous_corrupt_json_treated_as_first_save(tmp_path: Path) -> None:
    """Corrupt previous JSON is treated as if no previous payload exists."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "corrupt.repair-data.json"
    # Write garbled content first
    path.write_text("{not valid json!!!", encoding="utf-8")

    payload = _repair_payload(outcome=REPAIRING)
    repair_contract.save_repair_data(path, payload, root=tmp_path)

    # The save succeeds
    assert json.loads(path.read_text(encoding="utf-8"))["outcome"] == REPAIRING
    # An event is emitted (treated as first save)
    events = _read_ledger_events(tmp_path)
    assert len(events) == 1


def test_previous_payload_missing_outcome_treated_as_first_save(tmp_path: Path) -> None:
    """Previous JSON without an outcome field is treated as first save."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "no-outcome.repair-data.json"
    # Write a valid JSON payload without an outcome
    path.write_text(json.dumps({"session": "old", "workspace": "/tmp"}), encoding="utf-8")

    payload = _repair_payload(outcome=REPAIRING)
    repair_contract.save_repair_data(path, payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1  # treated as transition from None → repairing


def test_ledger_events_survive_across_multiple_sessions(tmp_path: Path) -> None:
    """Events for multiple sessions are correctly interleaved in the ledger."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()

    # Session A
    path_a = repair_dir / "session-a.repair-data.json"
    repair_contract.save_repair_data(
        path_a, _repair_payload(session="session-a", outcome=REPAIRING, incident_id="inc-a"), root=tmp_path
    )
    repair_contract.save_repair_data(
        path_a, _repair_payload(session="session-a", outcome=COMPLETE, incident_id="inc-a"), root=tmp_path
    )

    # Session B
    path_b = repair_dir / "session-b.repair-data.json"
    repair_contract.save_repair_data(
        path_b, _repair_payload(session="session-b", outcome=REPAIRING, incident_id="inc-b"), root=tmp_path
    )
    repair_contract.save_repair_data(
        path_b, _repair_payload(session="session-b", outcome=REPAIR_TIMEOUT, incident_id="inc-b"), root=tmp_path
    )

    events = _read_ledger_events(tmp_path)
    # 4 events: A-start, A-complete, B-start, B-timeout
    assert len(events) == 4

    payloads = [e["payload"] for e in events]
    types = [p["type"] for p in payloads]
    incident_ids = [p["incident_id"] for p in payloads]

    assert types == ["repair_attempt", "verified_recovered", "repair_attempt", "repair_attempt"]
    assert incident_ids == ["inc-a", "inc-a", "inc-b", "inc-b"]


def test_event_evidence_includes_verification_and_attempt_ids(tmp_path: Path) -> None:
    """Bridge events carry verification records and attempt_ids as evidence."""
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    path = repair_dir / "evidenced.repair-data.json"
    payload = _repair_payload(outcome=COMPLETE)
    payload["verification"] = {
        "outcome": COMPLETE,
        "is_success": True,
        "is_terminal": True,
        "recorded_at": "2026-07-03T20:00:00+00:00",
        "delta_summary": "All checks passed",
    }
    payload["attempt_ids"] = ["attempt-1", "attempt-2", "attempt-3"]

    repair_contract.save_repair_data(path, payload, root=tmp_path)

    events = _read_ledger_events(tmp_path)
    assert len(events) == 1
    evidence = events[0]["payload"].get("evidence", [])
    assert isinstance(evidence, list)
    # Should contain verification record and attempt_ids
    kinds = [item.get("kind") for item in evidence if isinstance(item, dict)]
    assert "verification_record" in kinds
    assert "attempt_ids" in kinds
