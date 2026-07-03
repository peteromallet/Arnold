from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.incident import (
    IncidentLedger,
    build_brief,
    rebuild_projections,
)


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": 1,
        "event_id": "evt-1",
        "ts": "2026-07-03T19:19:00Z",
        "scope": "repair_system",
        "outcome": "started",
        "incident_id": "inc-123",
        "type": "detection",
        "actor": "watchdog",
        "summary": "Build runner failed on startup",
        "evidence": [{"kind": "file", "path": "logs/runner.log"}],
        "next_expected_event": "immediate_repair.repair_attempt",
        "deadline_ts": "2026-07-03T19:34:00Z",
        "parent_event_ids": [],
        "trigger_event_id": None,
        "session_id": "session-1",
        "problem_id": "prob-1",
    }
    event.update(overrides)
    return event


def test_rebuild_projections_is_deterministic_and_tracks_incident_problem_state(
    tmp_path: Path,
) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event())
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="repair_attempt",
            actor="immediate_repair",
            ts="2026-07-03T19:20:00Z",
            summary="Restarted the runner and captured output",
            parent_event_ids=["evt-1"],
            attempt_id="attempt-1",
            decision={"selected_action": "restart-runner"},
            actions=[{"kind": "command", "command": "systemctl restart runner"}],
            evidence=[{"kind": "file", "path": "logs/restart.log"}],
            outcome="failed",
        )
    )
    ledger_dir = tmp_path / ".megaplan" / "incident-ledger"
    (ledger_dir / "incidents.json").write_text(
        json.dumps(
            {"source": {"digest": "sha256:stale", "last_seq": -1}},
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    first = rebuild_projections(tmp_path)
    incidents_path = ledger_dir / "incidents.json"
    problems_path = ledger_dir / "problems.json"
    second = rebuild_projections(tmp_path)
    second_incidents_json = incidents_path.read_text(encoding="utf-8")
    second_problems_json = problems_path.read_text(encoding="utf-8")
    third = rebuild_projections(tmp_path)

    assert incidents_path.read_text(encoding="utf-8") == second_incidents_json
    assert problems_path.read_text(encoding="utf-8") == second_problems_json

    incident = first["incidents"]["incidents"][0]
    assert incident["incident_id"] == "inc-123"
    assert incident["state"] == "repair_attempt"
    assert incident["outcome"] == "failed"
    assert incident["next_expected_event"] == "immediate_repair.repair_attempt"
    assert incident["deadline_ts"] == "2026-07-03T19:34:00Z"
    assert incident["session_ids"] == ["session-1"]
    assert incident["attempts"] == [
        {
            "attempt_id": "attempt-1",
            "event_seqs": [1],
            "latest_outcome": "failed",
            "types": ["repair_attempt"],
        }
    ]
    assert incident["decisions"] == [
        {"seq": 1, "decision": {"selected_action": "restart-runner"}}
    ]
    assert incident["actions"] == [
        {
            "seq": 1,
            "actions": [{"kind": "command", "command": "systemctl restart runner"}],
        }
    ]
    assert incident["placeholders"] == {
        "install_freshness": "unknown",
        "recurrence": "unknown",
        "shipped_fix": "unknown",
    }
    assert any(
        finding["code"] == "index_divergence"
        and finding.get("projection") == "incidents"
        for finding in first["incidents"]["integrity"]
    )
    assert second["incidents"]["integrity"] == []
    assert third["incidents"]["integrity"] == []

    problem = first["problems"]["problems"][0]
    assert problem["problem_id"] == "prob-1"
    assert problem["scope"] == "repair_system"
    assert problem["occurrence_count"] == 2
    assert problem["linked_incident_ids"] == ["inc-123"]


def test_rebuild_projections_reports_malformed_schema_and_dangling_refs(
    tmp_path: Path,
) -> None:
    ledger_dir = tmp_path / ".megaplan" / "incident-ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "seq": 0,
                "kind": "incident.detection",
                "payload": _event(),
            },
            sort_keys=True,
        ),
        "{broken json",
        json.dumps(
            {
                "seq": 1,
                "kind": "incident.detection",
                "payload": {
                    "schema_version": 1,
                    "incident_id": "inc-bad",
                    "type": "detection",
                    "actor": "watchdog",
                    "ts": "2026-07-03T19:19:10Z",
                    "scope": "repair_system",
                    "outcome": "started",
                    "evidence": [],
                    "next_expected_event": None,
                    "deadline_ts": None,
                    "parent_event_ids": [],
                    "trigger_event_id": None,
                },
            },
            sort_keys=True,
        ),
        json.dumps(
            {
                "seq": 2,
                "kind": "incident.repair_attempt",
                "payload": _event(
                    event_id="evt-2",
                    type="repair_attempt",
                    actor="immediate_repair",
                    ts="2026-07-03T19:20:00Z",
                    parent_event_ids=["missing-parent"],
                    trigger_event_id="missing-trigger",
                    attempt_id="attempt-2",
                ),
            },
            sort_keys=True,
        ),
    ]
    (ledger_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ledger_dir / "problems.json").write_text("{not json", encoding="utf-8")

    result = rebuild_projections(tmp_path)

    findings = result["incidents"]["integrity"]
    codes = {(finding["code"], finding.get("projection")) for finding in findings}
    assert ("malformed_json", None) in codes
    assert ("schema_failure", None) in codes
    assert ("dangling_parent_ref", None) in codes
    assert ("dangling_trigger_ref", None) in codes
    assert ("index_divergence", "problems") in codes

    incident = result["incidents"]["incidents"][0]
    assert incident["incident_id"] == "inc-123"
    assert incident["event_count"] == 2
    assert all(
        finding["recommendation"] == "system.integrity_repair" for finding in findings
    )


def test_build_brief_reports_deadlines_claims_attempts_and_missing_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "runner.log").write_text("runner failed\n", encoding="utf-8")

    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event())
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="claim.owner_assigned",
            actor="incident-commander",
            ts="2026-07-03T19:20:00Z",
            summary="Assigned the first responder",
            parent_event_ids=["evt-1"],
            claim_id="claim-expired",
            deadline_ts="2026-07-03T19:25:00Z",
            evidence=[{"kind": "file", "path": "logs/runner.log"}],
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-3",
            type="repair_attempt",
            actor="immediate_repair",
            ts="2026-07-03T19:23:00Z",
            summary="Restarted the runner and captured output",
            parent_event_ids=["evt-2"],
            attempt_id="attempt-1",
            deadline_ts="2026-07-03T19:26:00Z",
            evidence=[
                {"kind": "file", "path": "logs/runner.log"},
                {"kind": "file", "path": "logs/missing.log"},
            ],
            outcome="failed",
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-4",
            type="claim.waiting_customer",
            actor="incident-commander",
            ts="2026-07-03T19:24:00Z",
            summary="Waiting on customer confirmation",
            parent_event_ids=["evt-3"],
            claim_id="claim-active",
            deadline_ts="2026-07-03T19:40:00Z",
            evidence=[],
        )
    )

    brief = build_brief("session-1", root=tmp_path, now="2026-07-03T19:30:00Z")

    assert brief["found"] is True
    assert brief["incident_id"] == "inc-123"
    assert brief["state"] == "claim.waiting_customer"
    assert brief["deadline_ts"] == "2026-07-03T19:40:00Z"
    assert brief["deadline_status"] == "ok"
    assert brief["next_expected_event"] == "immediate_repair.repair_attempt"
    assert brief["attempts"] == [
        {
            "attempt_id": "attempt-1",
            "event_count": 1,
            "latest_outcome": "failed",
            "types": ["repair_attempt"],
        }
    ]
    assert brief["claims"] == [
        {
            "actor": "incident-commander",
            "claim_id": "claim-expired",
            "classification": "expired",
            "deadline_ts": "2026-07-03T19:25:00Z",
            "expected_transition": "immediate_repair.repair_attempt",
            "seq": 1,
            "status": "assigned",
            "summary": "Assigned the first responder",
        },
        {
            "actor": "incident-commander",
            "claim_id": "claim-active",
            "classification": "active",
            "deadline_ts": "2026-07-03T19:40:00Z",
            "expected_transition": "immediate_repair.repair_attempt",
            "seq": 3,
            "status": "customer",
            "summary": "Waiting on customer confirmation",
        },
    ]
    assert brief["evidence"] == [
        {"kind": "file", "path": "logs/missing.log", "status": "MISSING"},
        {"kind": "file", "path": "logs/runner.log", "status": "present"},
        {"kind": "file", "path": "logs/runner.log", "status": "present"},
        {"kind": "file", "path": "logs/runner.log", "status": "present"},
    ]
    assert brief["placeholders"] == {
        "install_freshness": "unknown",
        "recurrence": "unknown",
        "shipped_fix": "unknown",
    }
    assert brief["integrity"] == {
        "finding_count": 0,
        "recommendation": "system.integrity_repair",
        "severity": "ok",
    }
