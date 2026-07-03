from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
    AuditorConfig,
    audit_incident,
    build_audit_input,
)
from arnold_pipelines.megaplan.incident import IncidentLedger


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": 1,
        "event_id": "evt-audit-1",
        "ts": "2026-07-03T10:00:00Z",
        "scope": "repair_system",
        "outcome": "started",
        "incident_id": "inc-audit-1",
        "type": "detection",
        "actor": "watchdog",
        "summary": "Repair chain failed to advance",
        "evidence": [{"kind": "file", "path": "logs/missing.log"}],
        "next_expected_event": "meta_repair.repair_attempt",
        "deadline_ts": "2026-07-03T10:30:00Z",
        "parent_event_ids": [],
        "trigger_event_id": None,
        "session_id": "session-audit-1",
        "problem_id": "prob-audit-1",
    }
    event.update(overrides)
    return event


def test_build_audit_input_resolves_brief_incident_and_problem(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event())

    payload = build_audit_input("session-audit-1", root=tmp_path, now="2026-07-03T10:10:00Z")

    assert payload["brief"]["found"] is True
    assert payload["brief"]["incident_id"] == "inc-audit-1"
    assert payload["incident"]["incident_id"] == "inc-audit-1"
    assert payload["problem"]["problem_id"] == "prob-audit-1"


def test_audit_incident_emits_layer_findings_without_mutating_state() -> None:
    brief = {
        "found": True,
        "incident_id": "inc-audit-1",
        "summary": "Repair chain stalled",
        "outcome": "started",
        "next_expected_event": "meta_repair.repair_attempt",
        "deadline_status": "overdue",
        "claims": [{"claim_id": "claim-1", "classification": "expired"}],
        "evidence": [{"kind": "file", "path": "logs/missing.log", "status": "MISSING"}],
        "placeholders": {
            "install_freshness": "stale",
            "recurrence": "recurred_after_fix",
            "shipped_fix": "pending_install",
        },
    }
    incident = {
        "incident_id": "inc-audit-1",
        "session_ids": ["session-audit-1"],
        "next_expected_event": "meta_repair.repair_attempt",
        "placeholders": brief["placeholders"],
    }
    problem = {
        "problem_id": "prob-audit-1",
        "status": "open",
        "occurrence_count": 4,
        "recurred_after_fix": True,
    }
    live_snapshot = {
        "now": "2026-07-03T20:00:00Z",
        "watchdog": {"last_reported_at": "2026-07-03T10:00:00Z"},
        "processes": [
            {
                "actor": "immediate",
                "session_id": "session-audit-1",
                "started_at": "2026-07-03T15:00:00Z",
            }
        ],
        "meta_repair": {"evidence_refs": []},
        "github_sync": {},
    }

    result = audit_incident(
        brief=brief,
        incident=incident,
        problem=problem,
        live_process_snapshot=live_snapshot,
        config=AuditorConfig(),
    )

    assert {finding["layer"] for finding in result["findings"]} == {
        "project_progress",
        "watchdog",
        "immediate_repair",
        "meta_repair",
        "install_sync",
        "github_sync",
        "live_process",
        "stale_claim",
        "missing_evidence",
        "recurrence",
    }
    finding_codes = {finding["code"] for finding in result["findings"] if finding["status"] != "ok"}
    assert "project_progress_stalled" in finding_codes
    assert "watchdog_report_stale" in finding_codes
    assert "meta_repair_missing_evidence" in finding_codes
    assert "install_sync_stale" in finding_codes
    assert "stale_claim_detected" in finding_codes
    assert "problem_recurred_after_fix" in finding_codes
    assert result["audit_complete"]["outcome"] == "escalated"
    assert result["audit_complete"]["next_expected_event"] == "watchdog.dispatch"


def test_audit_incident_flags_stale_running_immediate_repair_for_meta_repair_handoff() -> None:
    result = audit_incident(
        brief={
            "found": True,
            "incident_id": "inc-audit-2",
            "summary": "Immediate repair is still running",
            "outcome": "started",
            "next_expected_event": "immediate_repair.repair_attempt",
            "deadline_status": "on_track",
            "claims": [],
            "evidence": [],
            "placeholders": {
                "install_freshness": "unknown",
                "recurrence": "unknown",
                "shipped_fix": "unknown",
            },
        },
        incident={
            "incident_id": "inc-audit-2",
            "session_ids": ["session-audit-2"],
            "next_expected_event": "immediate_repair.repair_attempt",
            "placeholders": {
                "install_freshness": "unknown",
                "recurrence": "unknown",
                "shipped_fix": "unknown",
            },
        },
        live_process_snapshot={
            "now": "2026-07-03T20:00:00Z",
            "watchdog": {"last_reported_at": "2026-07-03T19:30:00Z"},
            "processes": [
                {
                    "actor": "immediate_repair",
                    "session_id": "session-audit-2",
                    "started_at": "2026-07-03T16:30:00Z",
                }
            ],
        },
    )

    immediate_finding = next(finding for finding in result["findings"] if finding["layer"] == "immediate_repair")
    assert immediate_finding["code"] == "immediate_repair_running_stale"
    assert immediate_finding["recommendation"] == "meta_repair.repair_attempt"
    assert result["next_expected_event"] == "meta_repair.repair_attempt"


def test_audit_incident_flags_missing_meta_repair_evidence_and_stale_watchdog() -> None:
    result = audit_incident(
        brief={
            "found": True,
            "incident_id": "inc-audit-3",
            "summary": "Meta repair expected but no corroboration",
            "outcome": "started",
            "next_expected_event": "meta_repair.repair_attempt",
            "deadline_status": "on_track",
            "claims": [],
            "evidence": [],
            "placeholders": {
                "install_freshness": "unknown",
                "recurrence": "unknown",
                "shipped_fix": "unknown",
            },
        },
        incident={
            "incident_id": "inc-audit-3",
            "session_ids": ["session-audit-3"],
            "next_expected_event": "meta_repair.repair_attempt",
            "placeholders": {
                "install_freshness": "unknown",
                "recurrence": "unknown",
                "shipped_fix": "unknown",
            },
        },
        live_process_snapshot={
            "now": "2026-07-03T20:00:00Z",
            "watchdog": {"last_reported_at": "2026-07-03T12:00:00Z"},
            "processes": [],
        },
    )

    finding_codes = {finding["code"] for finding in result["findings"] if finding["status"] != "ok"}
    assert "watchdog_report_stale" in finding_codes
    assert "meta_repair_missing_evidence" in finding_codes
    assert result["audit_complete"]["outcome"] == "escalated"
