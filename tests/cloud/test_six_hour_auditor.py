from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
    AuditorConfig,
    audit_incident,
    audit_projection_input,
    build_audit_input,
    github_sync_publication_due,
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


def _payload(defaults: dict[str, object], **overrides: object) -> dict[str, object]:
    payload = deepcopy(defaults)
    payload.update(overrides)
    return payload


def _placeholders(**overrides: object) -> dict[str, object]:
    return _payload(
        {
            "install_freshness": "unknown",
            "recurrence": "unknown",
            "shipped_fix": "unknown",
        },
        **overrides,
    )


def _brief(**overrides: object) -> dict[str, object]:
    return _payload(
        {
            "found": True,
            "incident_id": "inc-audit-1",
            "summary": "Repair chain stalled",
            "outcome": "started",
            "next_expected_event": "immediate_repair.repair_attempt",
            "deadline_status": "on_track",
            "claims": [],
            "evidence": [],
            "placeholders": _placeholders(),
            "last_timestamp": "2026-07-03T19:45:00Z",
        },
        **overrides,
    )


def _incident(**overrides: object) -> dict[str, object]:
    return _payload(
        {
            "incident_id": "inc-audit-1",
            "session_ids": ["session-audit-1"],
            "state": "repairing",
            "outcome": "started",
            "next_expected_event": "immediate_repair.repair_attempt",
            "placeholders": _placeholders(),
            "last_timestamp": "2026-07-03T19:45:00Z",
        },
        **overrides,
    )


def _problem(**overrides: object) -> dict[str, object]:
    return _payload(
        {
            "problem_id": "prob-audit-1",
            "status": "open",
            "occurrence_count": 1,
            "recurred_after_fix": False,
        },
        **overrides,
    )


def test_github_sync_publication_due_survives_primary_human_escalation() -> None:
    incident_audit = {
        "next_expected_event": "auditor_escalate_to_human",
        "audit_complete": {
            "outcome": "auditor_human_escalation",
            "next_expected_event": "auditor_escalate_to_human",
        },
        "findings": [
            {
                "layer": "resolver_confidence",
                "recommendation": "auditor_escalate_to_human",
            },
            {
                "layer": "github_sync",
                "code": "github_sync_publish_due",
                "recommendation": "github_sync.publish",
            },
        ],
    }

    assert github_sync_publication_due(incident_audit) is True


def test_github_sync_publication_due_is_false_without_publish_action() -> None:
    assert github_sync_publication_due(
        {
            "next_expected_event": "auditor_escalate_to_human",
            "findings": [
                {
                    "layer": "resolver_confidence",
                    "recommendation": "auditor_escalate_to_human",
                }
            ],
        }
    ) is False


def _resolver_state(**overrides: object) -> dict[str, object]:
    return _payload(
        {
            "canonical_state": "RUNNING",
            "confidence": "high",
            "source_of_truth": ["live_process", "plan_state"],
            "stale_sources": [],
            "next_action": "immediate_repair.repair_attempt",
            "reason": "live immediate repair heartbeat observed",
            "repairable": True,
            "running": True,
            "root_cause_fingerprint": {"kind": "live_process", "value": "session-audit-1"},
            "evidence": {"active_step_heartbeat": {"active": True}},
        },
        **overrides,
    )


def _current_target(**overrides: object) -> dict[str, object]:
    return _payload(
        {
            "authoritative_source": "plan_state",
            "current_refs": {
                "current_plan_name": "progress-auditor-stage-20260703-1945",
                "plan_current_state": "running",
            },
            "plan_state": {"present": True},
            "chain_state": {"present": True},
            "active_step_heartbeat": {"active": True},
            "stale_evidence": [],
        },
        **overrides,
    )


def _process(actor: str = "immediate_repair", **overrides: object) -> dict[str, object]:
    return _payload(
        {
            "actor": actor,
            "session_id": "session-audit-1",
            "started_at": "2026-07-03T19:30:00Z",
        },
        **overrides,
    )


def _snapshot(**overrides: object) -> dict[str, object]:
    return _payload(
        {
            "now": "2026-07-03T20:00:00Z",
            "watchdog": {"last_reported_at": "2026-07-03T19:50:00Z"},
            "processes": [_process()],
            "meta_repair": {"evidence_refs": []},
            "github_sync": {},
            "repair_attempts": [],
        },
        **overrides,
    )


def _projection_input(**overrides: object) -> dict[str, object]:
    return _payload(
        {
            "brief": _brief(),
            "incident": _incident(),
            "problem": _problem(),
            "resolver_state": _resolver_state(),
            "current_target": _current_target(),
            "audit_history": [],
            "ci_health": {"status": "green", "source": "mock"},
            "engine_tree": {"status": "clean", "source": "mock"},
        },
        **overrides,
    )


def _drift_finding(result: dict[str, object], *, source_pair: str) -> dict[str, object]:
    findings = result.get("findings")
    assert isinstance(findings, list)
    return next(
        finding
        for finding in findings
        if isinstance(finding, dict)
        and finding.get("code") == "DRIFT_DETECTED"
        and finding.get("source_pair") == source_pair
    )


def _finding(result: dict[str, object], *, code: str) -> dict[str, object]:
    findings = result.get("findings")
    assert isinstance(findings, list)
    return next(
        finding
        for finding in findings
        if isinstance(finding, dict) and finding.get("code") == code
    )


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


def test_audit_incident_detects_github_sync_publication_from_incident_events() -> None:
    result = audit_incident(
        brief=_brief(next_expected_event="watchdog.dispatch"),
        incident=_incident(
            next_expected_event="watchdog.dispatch",
            events=[
                {
                    "actor": "github_sync",
                    "kind": "incident.github_sync.issue_published",
                    "timestamp": "2026-07-09T03:47:07+00:00",
                }
            ],
        ),
        problem=_problem(status="open", occurrence_count=4),
        live_process_snapshot=_snapshot(github_sync={}),
    )

    github_sync_finding = next(finding for finding in result["findings"] if finding["layer"] == "github_sync")
    assert github_sync_finding["code"] == "github_sync_observed"
    assert github_sync_finding["status"] == "ok"


def test_resolver_drift_detection() -> None:
    result = audit_projection_input(
        _projection_input(
            brief=_brief(
                outcome="recovered",
                next_expected_event="audit_cycle_complete",
            ),
            incident=_incident(
                state="repairing",
                outcome="started",
                next_expected_event="immediate_repair.repair_attempt",
            ),
            resolver_state=_resolver_state(
                canonical_state="RUNNING",
                confidence="high",
                next_action="immediate_repair.repair_attempt",
            ),
        ),
        live_process_snapshot=_snapshot(
            processes=[_process(actor="immediate_repair")],
        ),
        now="2026-07-03T20:00:00Z",
    )

    finding = _drift_finding(result, source_pair="resolver_vs_ledger")
    assert finding["layer"] == "reconciler"
    assert finding["status"] == "error"
    assert finding["severity"] == "error"
    assert finding["contradiction"] == "resolver_canonical_state_conflicts_with_ledger_outcome"
    assert finding["observed"] == {
        "resolver_canonical_state": "RUNNING",
        "brief_outcome": "recovered",
        "incident_state": "repairing",
    }
    assert finding["expected"] == {
        "brief_outcome": "started",
        "incident_state": "repairing",
        "next_expected_event": "immediate_repair.repair_attempt",
    }


def test_cross_source_drift_brief_vs_incident() -> None:
    result = audit_projection_input(
        _projection_input(
            brief=_brief(
                outcome="recovered",
                next_expected_event="audit_cycle_complete",
            ),
            incident=_incident(
                state="repairing",
                outcome="started",
                next_expected_event="meta_repair.repair_attempt",
            ),
        ),
        live_process_snapshot=_snapshot(
            processes=[_process(actor="meta_repair")],
        ),
        now="2026-07-03T20:00:00Z",
    )

    finding = _drift_finding(result, source_pair="brief_vs_incident")
    assert finding["layer"] == "reconciler"
    assert finding["status"] == "error"
    assert finding["severity"] == "error"
    assert finding["contradiction"] == "brief_outcome_conflicts_with_incident_state"
    assert finding["observed"] == {
        "brief_outcome": "recovered",
        "incident_state": "repairing",
        "incident_outcome": "started",
    }
    assert finding["expected"] == {
        "brief_outcome": "started",
        "incident_state": "repairing",
        "incident_outcome": "started",
    }


@pytest.mark.parametrize(
    ("next_expected_event", "observed_actor"),
    [
        ("watchdog.dispatch", "meta_repair"),
        ("github_sync.publish", "watchdog"),
        ("install_sync.retry", "github_sync"),
        ("immediate_repair.repair_attempt", "install_sync"),
        ("meta_repair.repair_attempt", "immediate_repair"),
    ],
)
def test_cross_source_drift_brief_vs_snapshot_all_layers(
    next_expected_event: str,
    observed_actor: str,
) -> None:
    result = audit_projection_input(
        _projection_input(
            brief=_brief(next_expected_event=next_expected_event),
            incident=_incident(next_expected_event=next_expected_event),
        ),
        live_process_snapshot=_snapshot(
            processes=[_process(actor=observed_actor)],
        ),
        now="2026-07-03T20:00:00Z",
    )

    finding = _drift_finding(result, source_pair="brief_vs_snapshot")
    assert finding["layer"] == "reconciler"
    assert finding["status"] == "error"
    assert finding["severity"] == "error"
    assert finding["contradiction"] == "next_expected_actor_conflicts_with_live_process"
    assert finding["observed"] == {
        "next_expected_event": next_expected_event,
        "snapshot_actor": observed_actor,
    }
    assert finding["expected"] == {
        "snapshot_actor": next_expected_event.split(".", 1)[0],
    }


def test_false_fixed_l2_caught() -> None:
    result = audit_projection_input(
        _projection_input(
            brief=_brief(
                outcome="recovered",
                next_expected_event="audit_cycle_complete",
                placeholders=_placeholders(shipped_fix="fixed"),
            ),
            incident=_incident(
                state="repairing",
                outcome="started",
                next_expected_event="immediate_repair.repair_attempt",
                placeholders=_placeholders(shipped_fix="fixed"),
            ),
            resolver_state=_resolver_state(
                canonical_state="RUNNING",
                confidence="high",
                next_action="immediate_repair.repair_attempt",
            ),
        ),
        live_process_snapshot=_snapshot(
            processes=[_process(actor="immediate_repair")],
        ),
        now="2026-07-03T20:00:00Z",
    )

    finding = _drift_finding(result, source_pair="l2_fix_vs_resolver")
    assert finding["layer"] == "reconciler"
    assert finding["status"] == "error"
    assert finding["severity"] == "error"
    assert finding["contradiction"] == "false_fixed_l2_result"
    assert finding["observed"] == {
        "brief_outcome": "recovered",
        "incident_state": "repairing",
        "resolver_canonical_state": "RUNNING",
        "snapshot_actor": "immediate_repair",
    }
    assert finding["expected"] == {
        "brief_outcome": "started",
        "incident_state": "repairing",
        "next_expected_event": "immediate_repair.repair_attempt",
    }
    assert result["audit_complete"]["outcome"] == "escalated"
    assert result["next_expected_event"] == "immediate_repair.repair_attempt"


def test_resolver_low_confidence_gate() -> None:
    result = audit_projection_input(
        _projection_input(
            brief=_brief(
                outcome="recovered",
                next_expected_event="audit_cycle_complete",
            ),
            incident=_incident(
                state="repairing",
                outcome="started",
                next_expected_event="immediate_repair.repair_attempt",
            ),
            resolver_state=_resolver_state(
                canonical_state="UNKNOWN",
                confidence="low",
                next_action="manual_review",
                repairable=False,
                running=False,
                reason="insufficient authoritative evidence",
            ),
        ),
        live_process_snapshot=_snapshot(
            processes=[],
        ),
        now="2026-07-03T20:00:00Z",
    )

    finding = _finding(result, code="resolver_low_confidence")
    assert finding["layer"] == "resolver_confidence"
    assert finding["status"] == "error"
    assert finding["severity"] == "error"
    assert finding["recommendation"] == "auditor_escalate_to_human"
    assert finding["observed"] == {
        "resolver_confidence": "low",
        "resolver_canonical_state": "UNKNOWN",
        "resolver_next_action": "manual_review",
    }
    assert result["audit_complete"]["outcome"] == "auditor_human_escalation"
    assert result["next_expected_event"] == "auditor_escalate_to_human"


def test_lying_resolver_caught() -> None:
    result = audit_projection_input(
        _projection_input(
            resolver_state=_resolver_state(
                canonical_state="RUNNING",
                confidence="high",
                stale_sources=[],
                next_action="requeue_or_retry",
                root_cause_fingerprint={"kind": "budget_exhausted", "value": "session-audit-1"},
                evidence={"budget_exhausted": {"tokens_spent": 4096}},
            ),
        ),
        live_process_snapshot=_snapshot(
            processes=[],
        ),
        now="2026-07-03T20:00:00Z",
    )

    finding = _finding(result, code="resolver_semantic_invalid")
    assert finding["layer"] == "resolver_semantics"
    assert finding["status"] == "error"
    assert finding["severity"] == "error"
    assert finding["recommendation"] == "auditor_escalate_to_human"
    assert finding["invalid_reasons"] == [
        "wrong_canonical_state_for_evidence",
        "missing_stale_sources",
        "wrong_root_cause_fingerprint_kind",
        "next_action_mismatch",
    ]
    assert result["audit_complete"]["outcome"] == "auditor_human_escalation"
    assert result["next_expected_event"] == "auditor_escalate_to_human"


def test_auditor_recursion_guard() -> None:
    result = audit_projection_input(
        _projection_input(
            brief=_brief(
                next_expected_event="meta_repair.repair_attempt",
                deadline_status="overdue",
            ),
            incident=_incident(
                next_expected_event="meta_repair.repair_attempt",
            ),
            audit_history=[
                {
                    "audit_complete": {
                        "outcome": "escalated",
                        "next_expected_event": "meta_repair.repair_attempt",
                    },
                    "findings": [
                        {
                            "code": "watchdog_report_stale",
                            "layer": "watchdog",
                            "status": "error",
                            "severity": "error",
                            "recommendation": "watchdog.dispatch",
                            "observed_at": "2026-07-03T12:00:00Z",
                            "message": "ignore volatile prose",
                        },
                        {
                            "code": "meta_repair_missing_evidence",
                            "layer": "missing_evidence",
                            "status": "error",
                            "severity": "error",
                            "recommendation": "meta_repair.repair_attempt",
                        },
                    ],
                }
            ],
        ),
        live_process_snapshot=_snapshot(
            watchdog={"last_reported_at": "2026-07-03T12:00:00Z"},
            processes=[],
            meta_repair={"evidence_refs": []},
        ),
        now="2026-07-03T20:00:00Z",
    )

    finding = _finding(result, code="auditor_recursion_guard")
    assert finding["layer"] == "auditor_recursion"
    assert finding["status"] == "error"
    assert finding["severity"] == "error"
    assert finding["recommendation"] == "auditor_escalate_to_human"
    assert finding["repeat_count"] == 2
    assert finding["cycle_detected"] is True
    assert result["audit_complete"]["outcome"] == "auditor_human_escalation"
    assert result["next_expected_event"] == "auditor_escalate_to_human"
