from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
    AUDIT_CODEX_MODEL,
    AuditorConfig,
    audit_incident,
    audit_projection_input,
    build_audit_input,
    enqueue_audit_repair_request,
    validate_audit_model_inputs,
)
from arnold_pipelines.megaplan.cloud.incident_bridge import IncidentStoreWriter


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
    fixture_root = tmp_path / "isolated-incident-store"
    writer = IncidentStoreWriter.isolated_test(
        fixture_root,
        production_root=Path.cwd(),
        identity="test:six_hour_auditor",
    )
    writer.append_event(_event())

    payload = build_audit_input(
        "session-audit-1", root=fixture_root, now="2026-07-03T10:10:00Z"
    )

    assert payload["brief"]["found"] is True
    assert payload["brief"]["incident_id"] == "inc-audit-1"
    assert payload["incident"]["incident_id"] == "inc-audit-1"
    assert payload["problem"]["problem_id"] == "prob-audit-1"


def test_fixture_writer_cannot_alias_production_incident_paths(tmp_path: Path) -> None:
    production_root = tmp_path / "production"
    production_ledger = production_root / ".megaplan" / "incident-ledger"
    production_ledger.mkdir(parents=True)

    for alias in (
        production_root,
        production_ledger,
        production_ledger / "events.jsonl",
        production_ledger / "incidents.json",
        production_ledger / "problems.json",
    ):
        with pytest.raises(ValueError, match="production ledger, projection, or journal"):
            IncidentStoreWriter(
                root=alias,
                namespace="fixture",
                identity="fixture:six_hour_auditor",
                production_root=production_root,
            )

    isolated = IncidentStoreWriter(
        root=tmp_path / "fixture-store",
        namespace="fixture",
        identity="fixture:six_hour_auditor",
        production_root=production_root,
    )
    assert isolated.events_path != production_ledger / "events.jsonl"


def test_audit_model_pin_rejects_conflicting_inputs() -> None:
    assert validate_audit_model_inputs({}) == AUDIT_CODEX_MODEL == "gpt-5.6-sol"
    assert validate_audit_model_inputs({"CODEX_MODEL": "gpt-5.6-sol"}) == "gpt-5.6-sol"
    for name in ("CODEX_MODEL", "MEGAPLAN_AUDIT_CODEX_MODEL", "CLOUD_WATCHDOG_CODEX_MODEL"):
        with pytest.raises(ValueError, match=f"{name}=gpt-5.5"):
            validate_audit_model_inputs({name: "gpt-5.5"})


def test_unhealthy_audit_routes_only_to_central_repair_request(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    queue_root = workspace / ".megaplan" / "repair-queue"
    item = {
        "plan": "demo-plan",
        "session": "demo-session",
        "workspace": str(workspace),
        "session_header": {"kind": "chain"},
        "incident_projection": {"state": "blocked"},
        "incident_audit": {
            "incident_id": "inc-1",
            "problem_id": "problem-1",
            "diagnosis": {"summary": "watchdog evidence is stale"},
            "findings": [{
                "status": "error",
                "layer": "watchdog",
                "code": "watchdog_report_stale",
                "recommendation": "watchdog.dispatch",
            }],
        },
    }

    result = enqueue_audit_repair_request(item, queue_root=queue_root)

    assert result is not None and result["status"] == "queued"
    request = result["request"]
    assert request["source"] == "six_hour_auditor"
    assert request["queue_dir"] == str(queue_root)
    assert request["problem_signature"]["event_signature"] == (
        "six_hour_auditor:watchdog:watchdog_report_stale"
    )
    assert not (workspace / ".git").exists()
    assert not (workspace / ".megaplan" / "plans").exists()
    written = {path.relative_to(workspace).parts[:3] for path in workspace.rglob("*")}
    assert written <= {
        (".megaplan",),
        (".megaplan", "repair-queue"),
        (".megaplan", "repair-queue", "requests"),
        (".megaplan", "repair-queue", "decisions"),
    }


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
        "semantic_custody",
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


# ---------------------------------------------------------------------------
# T6: Semantic/custody auditor reason codes — five deterministic checks
#     consuming snapshot facts only (never recomputing findings independently)
# ---------------------------------------------------------------------------


class TestUnresolvedSemanticFindings:
    """Auditor detects unresolved semantic findings from snapshot data."""

    def test_detects_when_total_count_positive(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                semantic_health={
                    "schema": "arnold.workflow.cloud_counts_summary.v1",
                    "session_id": "session-audit-1",
                    "fingerprint": "abc123def456",
                    "total_count": 3,
                    "counts_by_kind": {"missing_artifact": 2, "stale_observation": 1},
                    "counts_by_boundary": {"gate": 2, "execute": 1},
                    "counts_by_phase": {"gate": 2, "execute": 1},
                    "counts_by_repair_domain": {},
                },
            ),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="unresolved_semantic_findings")
        assert finding["layer"] == "semantic_custody"
        assert finding["status"] == "error"
        assert finding["severity"] == "error"
        assert finding["total_count"] == 3
        assert finding["fingerprint"] == "abc123def456"
        assert finding["recommendation"] == "immediate_repair.repair_attempt"

    def test_no_finding_when_total_count_zero(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                semantic_health={
                    "schema": "arnold.workflow.cloud_counts_summary.v1",
                    "session_id": "session-audit-1",
                    "fingerprint": "",
                    "total_count": 0,
                    "counts_by_kind": {},
                    "counts_by_boundary": {},
                    "counts_by_phase": {},
                    "counts_by_repair_domain": {},
                },
            ),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="semantic_custody_clear")
        assert finding["layer"] == "semantic_custody"
        assert finding["status"] == "ok"

    def test_no_finding_when_semantic_health_missing(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="semantic_custody_clear")
        assert finding["layer"] == "semantic_custody"
        assert finding["status"] == "ok"


class TestStaleActiveStepWorker:
    """Auditor detects stale active-step workers from snapshot."""

    def test_detects_stale_worker(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                activity_phase="execute",
                last_activity="2026-07-03T12:00:00Z",
            ),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="stale_active_step_worker")
        assert finding["layer"] == "semantic_custody"
        assert finding["status"] == "warn"
        assert finding["severity"] == "warn"
        assert finding["activity_phase"] == "execute"
        assert finding["recommendation"] == "watchdog.dispatch"

    def test_no_finding_when_worker_is_fresh(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                activity_phase="execute",
                last_activity="2026-07-03T19:50:00Z",
            ),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="semantic_custody_clear")
        assert finding["status"] == "ok"

    def test_no_finding_when_activity_phase_missing(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(last_activity="2026-07-03T12:00:00Z"),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="semantic_custody_clear")
        assert finding["status"] == "ok"


class TestUnmanagedLiveProcess:
    """Auditor detects unmanaged live processes from custody state."""

    @pytest.mark.parametrize("custody_state", [
        "unmanaged-running-with-warning",
        "blocked-relaunch-failure",
    ])
    def test_detects_unmanaged_custody(self, custody_state: str) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(custody_state=custody_state),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="unmanaged_live_process")
        assert finding["layer"] == "semantic_custody"
        assert finding["status"] == "warn"
        assert finding["severity"] == "warn"
        assert finding["custody_state"] == custody_state
        assert finding["recommendation"] == "watchdog.dispatch"

    @pytest.mark.parametrize("custody_state", [
        "managed-running",
        "complete",
    ])
    def test_no_finding_for_managed_custody(self, custody_state: str) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(custody_state=custody_state),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="semantic_custody_clear")
        assert finding["status"] == "ok"

    def test_no_finding_when_custody_missing(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="semantic_custody_clear")
        assert finding["status"] == "ok"


class TestRepairSuccessWithoutCustody:
    """Auditor detects repair success without managed custody."""

    @pytest.mark.parametrize("repair_state", ["recovered", "completed", "fixed", "verified_recovered"])
    def test_detects_repair_success_without_custody(self, repair_state: str) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                repair_state=repair_state,
                custody_state="unmanaged-running-with-warning",
            ),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="repair_success_without_custody")
        assert finding["layer"] == "semantic_custody"
        assert finding["status"] == "warn"
        assert finding["severity"] == "warn"
        assert finding["repair_state"] == repair_state
        assert finding["recommendation"] == "watchdog.dispatch"

    def test_no_finding_when_repair_success_with_managed_custody(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                repair_state="recovered",
                custody_state="managed-running",
            ),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="semantic_custody_clear")
        assert finding["status"] == "ok"

    def test_no_finding_when_repair_state_not_success(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                repair_state="active",
                custody_state="managed-running",
            ),
            now="2026-07-03T20:00:00Z",
        )

        # repair_success_without_custody should NOT fire when repair_state is not a success state
        repair_codes = {
            f["code"]
            for f in result["findings"]
            if f["layer"] == "semantic_custody" and f["status"] != "ok"
        }
        assert "repair_success_without_custody" not in repair_codes


class TestCustodyDisagreement:
    """Auditor detects watchdog/status custody disagreement."""

    def test_detects_custody_disagreement(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                custody_state="managed-running",
                watchdog={
                    "last_reported_at": "2026-07-03T19:50:00Z",
                    "custody_state": "unmanaged-running-with-warning",
                },
            ),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="custody_disagreement")
        assert finding["layer"] == "semantic_custody"
        assert finding["status"] == "error"
        assert finding["severity"] == "error"
        assert finding["watchdog_custody"] == "unmanaged-running-with-warning"
        assert finding["status_custody"] == "managed-running"
        assert finding["recommendation"] == "auditor_escalate_to_human"

    def test_no_finding_when_custody_agrees(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                custody_state="managed-running",
                watchdog={
                    "last_reported_at": "2026-07-03T19:50:00Z",
                    "custody_state": "managed-running",
                },
            ),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="semantic_custody_clear")
        assert finding["status"] == "ok"

    def test_no_finding_when_watchdog_custody_missing(self) -> None:
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                custody_state="managed-running",
                watchdog={"last_reported_at": "2026-07-03T19:50:00Z"},
            ),
            now="2026-07-03T20:00:00Z",
        )

        finding = _finding(result, code="semantic_custody_clear")
        assert finding["status"] == "ok"


class TestSemanticCustodyDeterminism:
    """Verifies deterministic behavior across identical snapshot inputs."""

    def test_same_input_produces_same_findings(self) -> None:
        snapshot = _snapshot(
            semantic_health={
                "schema": "arnold.workflow.cloud_counts_summary.v1",
                "session_id": "session-audit-1",
                "fingerprint": "fp1",
                "total_count": 2,
                "counts_by_kind": {"missing_artifact": 2},
                "counts_by_boundary": {"execute": 2},
                "counts_by_phase": {"execute": 2},
                "counts_by_repair_domain": {},
            },
            custody_state="unmanaged-running-with-warning",
            repair_state="recovered",
            activity_phase="execute",
            last_activity="2026-07-03T12:00:00Z",
            watchdog={
                "last_reported_at": "2026-07-03T19:50:00Z",
                "custody_state": "managed-running",
            },
        )

        result1 = audit_projection_input(
            _projection_input(),
            live_process_snapshot=deepcopy(snapshot),
            now="2026-07-03T20:00:00Z",
        )
        result2 = audit_projection_input(
            _projection_input(),
            live_process_snapshot=deepcopy(snapshot),
            now="2026-07-03T20:00:00Z",
        )

        codes1 = {f["code"] for f in result1["findings"] if f["layer"] == "semantic_custody"}
        codes2 = {f["code"] for f in result2["findings"] if f["layer"] == "semantic_custody"}
        assert codes1 == codes2
        assert "unresolved_semantic_findings" in codes1
        assert "stale_active_step_worker" in codes1
        assert "unmanaged_live_process" in codes1
        assert "repair_success_without_custody" in codes1
        assert "custody_disagreement" in codes1

    def test_multiple_findings_can_coexist(self) -> None:
        """All five reason codes can fire simultaneously on a problematic snapshot."""
        result = audit_projection_input(
            _projection_input(),
            live_process_snapshot=_snapshot(
                semantic_health={
                    "schema": "arnold.workflow.cloud_counts_summary.v1",
                    "session_id": "session-audit-1",
                    "fingerprint": "fp1",
                    "total_count": 5,
                    "counts_by_kind": {"missing_artifact": 5},
                    "counts_by_boundary": {},
                    "counts_by_phase": {},
                    "counts_by_repair_domain": {},
                },
                custody_state="blocked-relaunch-failure",
                repair_state="completed",
                activity_phase="execute",
                last_activity="2026-07-03T11:00:00Z",
                watchdog={
                    "last_reported_at": "2026-07-03T19:50:00Z",
                    "custody_state": "complete",
                },
            ),
            now="2026-07-03T20:00:00Z",
        )

        semantic_codes = {
            f["code"]
            for f in result["findings"]
            if f["layer"] == "semantic_custody" and f["status"] != "ok"
        }
        assert semantic_codes == {
            "unresolved_semantic_findings",
            "stale_active_step_worker",
            "unmanaged_live_process",
            "repair_success_without_custody",
            "custody_disagreement",
        }


# ---------------------------------------------------------------------------
# T18: SixHourAuditorCompletionEvidence — audited windows, repair dispatch
#      refs, escalation verdicts, stale repair-data findings, and missing
#      repair verdict findings
# ---------------------------------------------------------------------------

from arnold_pipelines.megaplan.cloud.six_hour_auditor import (  # noqa: E402
    SixHourAuditorCompletionEvidence,
    build_auditor_completion_evidence,
    save_auditor_completion_evidence,
)


class TestSixHourAuditorCompletionEvidenceConstruction:
    """SixHourAuditorCompletionEvidence construction, defaults, immutability."""

    def test_construction_with_all_fields(self) -> None:
        evidence = SixHourAuditorCompletionEvidence(
            audited_window_hours=6.0,
            audit_timestamp="2026-07-13T14:00:00Z",
            finding_count=12,
            highest_severity="error",
            next_expected_event="immediate_repair.repair_attempt",
            outcome="escalated",
            repair_dispatch_count=3,
            repair_dispatch_refs=("req-1", "req-2", "req-3"),
            escalation_verdict_count=2,
            escalation_verdict_refs=("reconciler:DRIFT_DETECTED", "watchdog:watchdog_report_stale"),
            missing_repair_verdict_findings=(
                {"layer": "immediate_repair", "code": "missing_evidence", "finding_kind": "missing_repair_verdict"},
            ),
            stale_repair_data_findings=(
                {"layer": "meta_repair", "code": "running_stale", "finding_kind": "stale_repair_data"},
            ),
            evidence_timestamp="2026-07-13T14:00:00Z",
        )
        assert evidence.audited_window_hours == 6.0
        assert evidence.audit_timestamp == "2026-07-13T14:00:00Z"
        assert evidence.finding_count == 12
        assert evidence.highest_severity == "error"
        assert evidence.next_expected_event == "immediate_repair.repair_attempt"
        assert evidence.outcome == "escalated"
        assert evidence.repair_dispatch_count == 3
        assert evidence.repair_dispatch_refs == ("req-1", "req-2", "req-3")
        assert evidence.escalation_verdict_count == 2
        assert evidence.escalation_verdict_refs == ("reconciler:DRIFT_DETECTED", "watchdog:watchdog_report_stale")
        assert len(evidence.missing_repair_verdict_findings) == 1
        assert len(evidence.stale_repair_data_findings) == 1

    def test_default_contract_id(self) -> None:
        evidence = SixHourAuditorCompletionEvidence()
        assert evidence.contract_id == "auditor.6h_complete.1"
        assert evidence.boundary_id == "auditor_6h_completion"

    def test_default_audited_window_hours_is_6(self) -> None:
        evidence = SixHourAuditorCompletionEvidence()
        assert evidence.audited_window_hours == 6.0

    def test_defaults_are_empty(self) -> None:
        evidence = SixHourAuditorCompletionEvidence()
        assert evidence.finding_count == 0
        assert evidence.highest_severity == "ok"
        assert evidence.repair_dispatch_count == 0
        assert evidence.repair_dispatch_refs == ()
        assert evidence.escalation_verdict_count == 0
        assert evidence.escalation_verdict_refs == ()
        assert evidence.missing_repair_verdict_findings == ()
        assert evidence.stale_repair_data_findings == ()

    def test_frozen_immutability(self) -> None:
        evidence = SixHourAuditorCompletionEvidence(outcome="escalated")
        with pytest.raises(Exception):
            evidence.outcome = "changed"  # type: ignore[misc]


class TestSixHourAuditorCompletionEvidenceRoundTrip:
    """to_dict / from_dict round-trip."""

    def test_round_trip_preserves_all_fields(self) -> None:
        original = SixHourAuditorCompletionEvidence(
            audited_window_hours=6.0,
            audit_timestamp="2026-07-13T15:00:00Z",
            finding_count=5,
            highest_severity="warn",
            next_expected_event="meta_repair.repair_attempt",
            outcome="audit_cycle_complete",
            repair_dispatch_count=1,
            repair_dispatch_refs=("dispatch/req-a.json",),
            escalation_verdict_count=1,
            escalation_verdict_refs=("reconciler:DRIFT_DETECTED",),
            missing_repair_verdict_findings=(
                {"layer": "meta_repair", "code": "meta_repair_missing_evidence",
                 "status": "error", "severity": "error", "message": "m",
                 "finding_kind": "missing_repair_verdict"},
            ),
            stale_repair_data_findings=(
                {"layer": "immediate_repair", "code": "immediate_repair_running_stale",
                 "status": "error", "severity": "error", "message": "s",
                 "finding_kind": "stale_repair_data"},
            ),
            evidence_timestamp="2026-07-13T15:00:00Z",
        )
        reloaded = SixHourAuditorCompletionEvidence.from_dict(original.to_dict())
        assert reloaded == original

    def test_from_dict_empty_payload(self) -> None:
        evidence = SixHourAuditorCompletionEvidence.from_dict({})
        assert evidence.contract_id == "auditor.6h_complete.1"
        assert evidence.audited_window_hours == 6.0
        assert evidence.finding_count == 0


class TestBuildAuditorCompletionEvidence:
    """build_auditor_completion_evidence extracts findings and refs."""

    def test_build_with_audit_findings(self) -> None:
        findings = [
            {"layer": "reconciler", "code": "DRIFT_DETECTED", "status": "error",
             "severity": "error", "recommendation": "auditor_escalate_to_human"},
            {"layer": "watchdog", "code": "watchdog_report_stale", "status": "error",
             "severity": "error", "recommendation": "watchdog.dispatch"},
            {"layer": "project_progress", "code": "project_progress_stalled",
             "status": "ok", "severity": "ok"},
        ]
        evidence = build_auditor_completion_evidence(
            audit_findings=findings,
            audit_outcome="escalated",
            next_expected_event="immediate_repair.repair_attempt",
            audited_window_hours=6.0,
            repair_dispatch_refs=("dispatch/req-1.json",),
        )
        assert evidence.finding_count == 3
        assert evidence.highest_severity == "error"
        assert evidence.outcome == "escalated"
        assert evidence.next_expected_event == "immediate_repair.repair_attempt"
        assert evidence.audited_window_hours == 6.0
        assert evidence.repair_dispatch_count == 1
        assert evidence.repair_dispatch_refs == ("dispatch/req-1.json",)

    def test_build_extracts_escalation_verdicts(self) -> None:
        findings = [
            {"layer": "reconciler", "code": "DRIFT_DETECTED", "status": "error",
             "severity": "error", "recommendation": "auditor_escalate_to_human"},
            {"layer": "resolver_confidence", "code": "resolver_low_confidence",
             "status": "error", "severity": "error",
             "recommendation": "auditor_escalate_to_human"},
        ]
        evidence = build_auditor_completion_evidence(
            audit_findings=findings,
            audit_outcome="auditor_human_escalation",
        )
        assert evidence.escalation_verdict_count == 2
        assert "reconciler:DRIFT_DETECTED" in evidence.escalation_verdict_refs
        assert "resolver_confidence:resolver_low_confidence" in evidence.escalation_verdict_refs

    def test_build_extracts_missing_repair_verdict_findings(self) -> None:
        findings = [
            {"layer": "immediate_repair", "code": "missing_evidence", "status": "error",
             "severity": "error", "message": "No repair verdict found",
             "recommendation": "immediate_repair.repair_attempt"},
            {"layer": "meta_repair", "code": "meta_repair_missing_evidence",
             "status": "error", "severity": "error",
             "message": "No meta-repair completion record",
             "recommendation": "meta_repair.repair_attempt"},
        ]
        evidence = build_auditor_completion_evidence(
            audit_findings=findings,
            audit_outcome="escalated",
        )
        assert len(evidence.missing_repair_verdict_findings) == 2
        for finding in evidence.missing_repair_verdict_findings:
            assert finding["finding_kind"] == "missing_repair_verdict"

    def test_build_extracts_stale_repair_data_findings(self) -> None:
        findings = [
            {"layer": "immediate_repair", "code": "immediate_repair_running_stale",
             "status": "error", "severity": "error",
             "message": "Immediate repair has been running too long",
             "recommendation": "meta_repair.repair_attempt"},
        ]
        evidence = build_auditor_completion_evidence(
            audit_findings=findings,
            audit_outcome="escalated",
        )
        assert len(evidence.stale_repair_data_findings) == 1
        assert evidence.stale_repair_data_findings[0]["finding_kind"] == "stale_repair_data"
        assert evidence.stale_repair_data_findings[0]["code"] == "immediate_repair_running_stale"

    def test_build_with_no_findings(self) -> None:
        evidence = build_auditor_completion_evidence(
            audit_findings=[],
            audit_outcome="audit_cycle_complete",
        )
        assert evidence.finding_count == 0
        assert evidence.highest_severity == "ok"
        assert evidence.missing_repair_verdict_findings == ()
        assert evidence.stale_repair_data_findings == ()

    def test_build_preserves_audited_window(self) -> None:
        evidence = build_auditor_completion_evidence(
            audit_findings=[],
            audited_window_hours=12.0,
        )
        assert evidence.audited_window_hours == 12.0

    def test_build_default_window_is_6(self) -> None:
        evidence = build_auditor_completion_evidence()
        assert evidence.audited_window_hours == 6.0


class TestSaveAuditorCompletionEvidence:
    """save_auditor_completion_evidence persists and returns payload."""

    def test_save_and_reload_round_trip(self, tmp_path: Path) -> None:
        evidence = SixHourAuditorCompletionEvidence(
            audited_window_hours=6.0,
            audit_timestamp="2026-07-13T16:00:00Z",
            finding_count=7,
            highest_severity="error",
            next_expected_event="watchdog.dispatch",
            outcome="escalated",
            repair_dispatch_count=2,
            repair_dispatch_refs=("req-a", "req-b"),
            escalation_verdict_count=1,
            escalation_verdict_refs=("watchdog:watchdog_report_stale",),
            missing_repair_verdict_findings=(
                {"layer": "immediate_repair", "code": "missing_evidence",
                 "finding_kind": "missing_repair_verdict"},
            ),
            stale_repair_data_findings=(),
            evidence_timestamp="2026-07-13T16:00:00Z",
        )
        dest = tmp_path / "auditor-evidence.json"
        saved = save_auditor_completion_evidence(dest, evidence)
        assert dest.exists()
        assert saved["finding_count"] == 7
        assert saved["repair_dispatch_count"] == 2

        import json
        reloaded = SixHourAuditorCompletionEvidence.from_dict(
            json.loads(dest.read_text(encoding="utf-8"))
        )
        assert reloaded == evidence
