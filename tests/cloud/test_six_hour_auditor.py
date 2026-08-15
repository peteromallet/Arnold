from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest

from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
    AUDIT_CODEX_MODEL,
    AuditorConfig,
    audit_incident,
    audit_projection_input,
    build_audit_input,
    github_sync_publication_due,
    enqueue_audit_repair_request,
    validate_audit_model_inputs,
)
from arnold_pipelines.megaplan.cloud.incident_bridge import IncidentStoreWriter
from arnold_pipelines.megaplan.incident.ledger import RuntimeTransitionWriter
from arnold_pipelines.megaplan.cloud.repair_contract import read_jsonl_records
from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.simple_fixer import FORBIDDEN_AUTHORITY_SOURCES
from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey


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


def test_build_audit_input_can_remain_read_only(tmp_path: Path) -> None:
    payload = build_audit_input("missing-session", root=tmp_path, persist=False)

    assert payload["brief"]["found"] is False
    assert not (tmp_path / ".megaplan").exists()


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


def test_ordinary_unhealthy_audit_remains_report_only(tmp_path: Path) -> None:
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

    assert result is None
    assert not (workspace / ".git").exists()
    assert not (workspace / ".megaplan" / "plans").exists()
    assert not queue_root.exists()


def test_deterministic_superfixer_cycle_routes_to_global_queue_and_keeps_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "target-workspace"
    workspace.mkdir()
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    evidence = {
        "actionable": True,
        "accepted_unclaimed_count": 1,
        "accepted_unclaimed_request_ids": ["7473fa42"],
        "claim_count": 0,
        "attempt_count": 0,
        "repair_outcome": "repair_exhausted",
        "repair_age_min": 180,
        "runner_dead": True,
        "chain_incomplete": True,
        "absent_or_stale_l2": True,
        "retry_budget": {"claim_retries_used": 2, "claim_alerted": False},
    }

    result = enqueue_audit_repair_request(
        {
            "plan": "c1-contract-reality-20260711-1433",
            "session": "workflow-boundary-contracts-corrective-20260710",
            "workspace": str(workspace),
            "session_header": {"kind": "chain"},
            "deterministic_superfixer_evidence": evidence,
            "l3_escalation_gate": {
                "eligible": True,
                "decision": "true_stall",
                "escalation_id": "l3-escalation:fixture",
                "evidence_digest": "f" * 64,
                "route": {
                    "requested_difficulty": 9,
                    "effective_difficulty": 9,
                    "model": "gpt-5.6-sol",
                    "reasoning_effort": "high",
                    "child_difficulty_ceiling": 9,
                },
            },
            "l3_repair_context_path": "/workspace/audit-reports/escalations/fixture/repair-context.json",
            "l3_repair_context_digest": "c" * 64,
        },
        queue_root=queue_root,
        transition_writer=RuntimeTransitionWriter(tmp_path / "cycle-ledger"),
        chain_spec_sha256=_auditor_spec_and_digest(tmp_path)[1],
    )

    assert result is not None
    assert result["status"] == "zero_authority_rejected"
    assert not list((queue_root / "requests").glob("*.json"))
    assert not (workspace / ".megaplan" / "repair-queue").exists()


def test_auditor_enqueue_uses_canonical_occurrence_identity(
    tmp_path: Path,
) -> None:
    """Step 46 (T32): auditor enqueue produces an occurrence-compatible
    identity carrying grant/fence, lease/epoch, evidence cursor digest,
    root-cause identity, retry ordinal, and terminal receipt expectations.

    When the exact F01 tuple is satisfied the canonical occurrence
    fingerprint is set.  When the tuple is partial the forbidden authority
    source is recorded so no authority is minted from report state.
    """

    workspace = tmp_path / "occurrence-workspace"
    workspace.mkdir()
    queue_root = tmp_path / ".megaplan" / "repair-queue"

    base_evidence = {
        "actionable": True,
        "accepted_unclaimed_count": 1,
        "accepted_unclaimed_request_ids": ["abc123"],
        "claim_count": 0,
        "attempt_count": 0,
        "repair_outcome": "repair_exhausted",
        "repair_age_min": 180,
        "runner_dead": True,
        "chain_incomplete": True,
        "absent_or_stale_l2": True,
        "retry_budget": {"claim_retries_used": 2, "claim_alerted": False},
    }
    base_gate = {
        "eligible": True,
        "decision": "true_stall",
        "escalation_id": "l3-escalation:occurrence-test",
        "evidence_digest": "e" * 64,
        "route": {"requested_difficulty": 9},
    }

    # ── Complete F01 tuple → occurrence-compatible identity ───────────
    complete_item = {
        "plan": "demo-plan",
        "session": "demo-session-complete",
        "workspace": str(workspace),
        "session_header": {"kind": "chain", "chain": "demo-chain"},
        "deterministic_superfixer_evidence": base_evidence,
        "l3_escalation_gate": {
            **base_gate,
            "fence": "fence-token-abc",
        },
        "current_target": {
            "environment": "prod",
            "chain": "demo-chain",
            "plan_revision": "rev-1",
            "phase": "phase-A",
            "task": "task-42",
            "attempt": "3",
        },
        "repair_custody_summary": {
            "normalized_failure_kind": "stale_l1_l2_cycle",
            "blocker_id": "blocker-hash-001",
            "fence": "fence-token-abc",
            "custody_epoch": "epoch-7",
            "lease_id": "lease-99",
            "run_authority_grant_id": "grant-grant-1",
        },
    }
    identity = repair_requests.build_normalized_repair_identity(
        target=CustodyTargetKey(
            environment="prod",
            session="demo-session-complete",
            chain="demo-chain",
            plan_revision="rev-1",
            phase="phase-A",
            task="task-42",
            attempt="3",
            normalized_failure_kind="stale_l1_l2_cycle",
            blocker_or_phase_result_hash="blocker-hash-001",
            fence="runner-fence:7",
        ),
        run_id="run-audit-1",
        run_revision="rev-1",
        run_incarnation_id="run-incarnation-audit-1",
        coordinator_attempt_id="coordinator-audit-1",
        fence_token=7,
        wbc_attempt_reference="wbc-audit-1",
        run_authority_grant_id="grant-grant-1",
        lease_id="lease-99",
        custody_epoch=7,
    )
    assert identity is not None
    complete_item["repair_identity"] = identity

    from arnold_pipelines.megaplan.incident.ledger import RuntimeTransitionWriter

    _, digest = _auditor_spec_and_digest(tmp_path)
    writer = RuntimeTransitionWriter(tmp_path / "occurrence-ledger")
    result = enqueue_audit_repair_request(
        complete_item,
        queue_root=queue_root,
        transition_writer=writer,
        chain_spec_sha256=digest,
    )
    assert result is not None
    assert result["status"] == "queued"
    request = result["request"]

    ri = request["repair_identity"]
    assert ri == identity
    assert ri["occurrence"]["target"]["session"] == "demo-session-complete"
    assert ri["occurrence"]["fence_token"] == 7
    assert ri["lease_id"] == "lease-99"
    assert ri["custody_epoch"] == 7
    assert ri["run_authority_grant_id"] == "grant-grant-1"

    # ── Partial F01 tuple → forbidden authority source recorded ───────
    queue_root2 = tmp_path / "workspace2" / ".megaplan" / "repair-queue"
    partial_item = {
        "plan": "demo-plan",
        "session": "demo-session-partial",
        "workspace": str(tmp_path / "workspace2"),
        "session_header": {"kind": "chain"},
        "deterministic_superfixer_evidence": base_evidence,
        "l3_escalation_gate": base_gate,
        # No current_target or repair_custody_summary → partial F01 tuple.
    }

    result2 = enqueue_audit_repair_request(
        partial_item,
        queue_root=queue_root2,
        transition_writer=writer,
        chain_spec_sha256=digest,
    )
    assert result2 is not None
    assert result2["status"] == "zero_authority_rejected"
    assert not list((queue_root2 / "requests").glob("*.json"))


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
        assert evidence.drift_findings == ()
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
            drift_findings=(
                {"layer": "reconciler", "code": "DRIFT_DETECTED", "source_pair": "resolver_vs_ledger"},
            ),
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
        assert evidence.drift_findings == (
            {
                "layer": "reconciler",
                "code": "DRIFT_DETECTED",
                "source_pair": "",
                "contradiction": "",
                "recommendation": "auditor_escalate_to_human",
                "observed": {},
                "expected": {},
            },
        )

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

    @pytest.mark.parametrize("window", [0.0, -1.0, float("nan"), float("inf")])
    def test_invalid_evidence_window_cannot_certify_empty_audit(self, window: float) -> None:
        evidence = build_auditor_completion_evidence(
            audit_findings=[],
            audit_outcome="audit_cycle_complete",
            audited_window_hours=window,
            repair_dispatch_refs=("spurious-dispatch",),
        )

        assert evidence.outcome == "invalid_evidence_window"
        assert evidence.highest_severity == "error"
        assert evidence.next_expected_event == "auditor.retry_with_valid_evidence_window"
        assert evidence.repair_dispatch_count == 0


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

    def test_save_appends_incident_sidecar_record(self, tmp_path: Path) -> None:
        evidence = SixHourAuditorCompletionEvidence(
            outcome="auditor_human_escalation",
            next_expected_event="human_approval.pr_merge",
            escalation_verdict_refs=("reconciler:DRIFT_DETECTED",),
            drift_findings=(
                {
                    "layer": "reconciler",
                    "code": "DRIFT_DETECTED",
                    "source_pair": "l2_fix_vs_resolver",
                    "contradiction": "false_fixed_l2_result",
                    "recommendation": "immediate_repair.repair_attempt",
                    "observed": {"resolver_canonical_state": "RUNNING"},
                    "expected": {"brief_outcome": "started"},
                },
            ),
            evidence_timestamp="2026-07-13T16:30:00Z",
        )
        dest = tmp_path / "auditor-evidence.json"
        sidecar_dir = tmp_path / "repair-data.d"

        save_auditor_completion_evidence(
            dest,
            evidence,
            sidecar_dir=sidecar_dir,
            session="progress_auditor",
        )

        records = read_jsonl_records(sidecar_dir / "incidents" / "incidents.jsonl")
        assert records[-1]["session"] == "progress_auditor"
        assert records[-1]["kind"] == "auditor_6h_completion"
        assert records[-1]["summary"] == "auditor_human_escalation"
        assert records[-1]["drift_findings"] == [
            {
                "layer": "reconciler",
                "code": "DRIFT_DETECTED",
                "source_pair": "l2_fix_vs_resolver",
                "contradiction": "false_fixed_l2_result",
                "recommendation": "immediate_repair.repair_attempt",
                "observed": {"resolver_canonical_state": "RUNNING"},
                "expected": {"brief_outcome": "started"},
            }
        ]


# ── Step 47 (T33): six-hour names are compatibility-only ─────────────────


def test_six_hour_names_are_compatibility_only() -> None:
    """The ``six_hour`` module/field names must be legacy compatibility only.

    Step 47 (T33): positive proof has moved to next-three-hour
    reconciliation.  The module must (a) declare the six-hour names as
    compatibility-only, (b) expose the next-three-hour reconciliation
    interval as the positive-proof cadence, and (c) never derive the
    reconciliation interval from the six-hour constant.
    """
    import arnold_pipelines.megaplan.cloud.six_hour_auditor as mod

    # (a) The module explicitly marks six-hour names as compatibility-only.
    assert mod.LEGACY_SIX_HOUR_NAMES_COMPATIBILITY_ONLY is True

    # (b) The positive-proof cadence is next-three-hour, exported in __all__.
    assert mod.AUDITOR_RECONCILIATION_INTERVAL == "next_three_hour"
    assert "AUDITOR_RECONCILIATION_INTERVAL" in mod.__all__
    assert "THREE_HOURS_SECONDS" in mod.__all__
    assert "LEGACY_SIX_HOUR_NAMES_COMPATIBILITY_ONLY" in mod.__all__

    # (c) The reconciliation cadence is strictly shorter than the legacy
    # six-hour backstop window; six-hour may not masquerade as the cadence.
    assert mod.THREE_HOURS_SECONDS == 3 * 3600
    assert mod.SIX_HOURS_SECONDS == 6 * 3600
    assert mod.THREE_HOURS_SECONDS < mod.SIX_HOURS_SECONDS
    assert mod.AUDITOR_RECONCILIATION_INTERVAL != "six_hour"

    # (d) The reconciliation interval must not be derived from a label,
    # liveness signal, WBC receipt, or rebuildable projection — it is a fixed
    # schedule constant (SC33).
    forbidden = {str(s) for s in FORBIDDEN_AUTHORITY_SOURCES}
    assert mod.AUDITOR_RECONCILIATION_INTERVAL not in forbidden


# ── P2 typed runtime transitions: absence findings + enqueue emission ──────


def _auditor_spec_and_digest(tmp_path: Path) -> tuple[Path, str]:
    import hashlib

    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    return spec_path, "sha256:" + hashlib.sha256(spec_path.read_bytes()).hexdigest()


def test_runtime_transition_absence_findings_map_to_auditor_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The auditor maps incident-ledger runtime absences (missing events,
    invalid failure classes, digest drift, expired permits) into its finding
    shape — read-only, escalation-only."""
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)

    from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
        runtime_transition_absence_findings,
    )
    from arnold_pipelines.megaplan.incident.ledger import RuntimeTransitionWriter

    ledger_root = tmp_path / "ledger-root"
    spec_path, digest = _auditor_spec_and_digest(tmp_path)

    # An empty ledger for a session reports every runtime.* event type.
    findings = runtime_transition_absence_findings(
        ledger_root=ledger_root,
        session_id="audit-session",
        spec_path=spec_path,
    )
    codes = {finding["code"] for finding in findings}
    assert "runtime_missing_runtime_event" in codes
    assert "runtime_allow_manifestless_permit_missing" in codes
    for finding in findings:
        assert finding["layer"] == "runtime_transitions"
        assert finding["_non_authoritative"] is True
        assert finding["evidence_id"].startswith("finding:sha256:")
    missing = next(
        finding
        for finding in findings
        if finding["code"] == "runtime_missing_runtime_event"
    )
    assert missing["event_type"] == "runtime.manifest_selected"

    # A fully-typed session removes the missing-event findings.
    writer = RuntimeTransitionWriter(ledger_root)
    writer.emit_manifest_selected(
        scope="chain:audit-session",
        candidate_to="manifest-a",
        chain_spec_sha256=digest,
        actor="test",
        session_id="audit-session",
    )
    writer.emit_deviation_declared(
        scope="chain:audit-session",
        failure_class="availability",
        error="probe",
        chain_spec_sha256=digest,
        candidate_to="repair-loop",
        actor="test",
        session_id="audit-session",
    )
    writer.emit_fallback_considered(
        scope="chain:audit-session",
        failure_class="availability",
        chain_spec_sha256=digest,
        candidate_to="repair-loop",
        actor="test",
        session_id="audit-session",
    )
    writer.emit_fallback_taken(
        scope="chain:audit-session",
        failure_class="availability",
        chain_spec_sha256=digest,
        candidate_to="repair-loop",
        actor="test",
        session_id="audit-session",
    )
    writer.emit_fallback_rejected(
        scope="chain:audit-session",
        failure_class="semantic",
        error="permanent",
        chain_spec_sha256=digest,
        candidate_to="repair-loop",
        actor="test",
        session_id="audit-session",
    )
    findings_after = runtime_transition_absence_findings(
        ledger_root=ledger_root,
        session_id="audit-session",
        spec_path=spec_path,
    )
    assert all(
        finding["code"] != "runtime_missing_runtime_event"
        for finding in findings_after
    )


def test_auditor_enqueue_emits_runtime_transitions_before_request_creation(
    tmp_path: Path,
) -> None:
    """The auditor's only operational handoff (enqueue_audit_repair_request)
    mandatorily records deviation_declared + fallback_considered BEFORE the
    request is created; the ledger events are durable before the repair
    request exists."""
    from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
        enqueue_audit_repair_request,
    )
    from arnold_pipelines.megaplan.cloud.watchdog import (
        iter_incident_runtime_events,
    )
    from arnold_pipelines.megaplan.incident.ledger import RuntimeTransitionWriter

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger_root = workspace
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    _, digest = _auditor_spec_and_digest(tmp_path)
    base_evidence = {
        "actionable": True,
        "accepted_unclaimed_count": 1,
        "accepted_unclaimed_request_ids": ["abc123"],
        "claim_count": 0,
        "attempt_count": 0,
        "repair_outcome": "repair_exhausted",
        "repair_age_min": 180,
        "runner_dead": True,
        "chain_incomplete": True,
        "absent_or_stale_l2": True,
        "retry_budget": {"claim_retries_used": 2, "claim_alerted": False},
    }
    base_gate = {
        "eligible": True,
        "decision": "true_stall",
        "escalation_id": "l3-escalation:audit-transitions-test",
        "evidence_digest": "e" * 64,
        "route": {"requested_difficulty": 9},
    }
    item = {
        "plan": "demo-plan",
        "session": "demo-session",
        "workspace": str(workspace),
        "session_header": {"kind": "chain"},
        "deterministic_superfixer_evidence": base_evidence,
        "l3_escalation_gate": base_gate,
    }
    writer = RuntimeTransitionWriter(ledger_root)

    result = enqueue_audit_repair_request(
        item,
        queue_root=queue_root,
        transition_writer=writer,
        chain_spec_sha256=digest,
    )

    assert result is not None  # the handoff itself was attempted
    events = iter_incident_runtime_events(ledger_root)
    assert [event["type"] for event in events] == [
        "runtime.deviation_declared",
        "runtime.fallback_considered",
    ], events
    for event in events:
        assert event["session_id"] == "demo-session"
        assert event["failure_class"] == "availability"
        assert event["chain_spec_sha256"] == digest
        assert event["actor"] == "arnold-six-hour-auditor"
    assert "stale_l1_l2_cycle" in events[0]["error"]


def test_auditor_enqueue_blocks_when_runtime_transition_write_fails(
    tmp_path: Path,
) -> None:
    """A runtime transition write failure aborts the auditor's handoff: no
    durable event means no repair request is created."""
    from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
        enqueue_audit_repair_request,
    )
    from arnold_pipelines.megaplan.incident.ledger import RuntimeTransitionWriter

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    _, digest = _auditor_spec_and_digest(tmp_path)
    base_evidence = {
        "actionable": True,
        "accepted_unclaimed_count": 1,
        "accepted_unclaimed_request_ids": ["abc123"],
        "claim_count": 0,
        "attempt_count": 0,
        "repair_outcome": "repair_exhausted",
        "repair_age_min": 180,
        "runner_dead": True,
        "chain_incomplete": True,
        "absent_or_stale_l2": True,
        "retry_budget": {"claim_retries_used": 2, "claim_alerted": False},
    }
    base_gate = {
        "eligible": True,
        "decision": "true_stall",
        "escalation_id": "l3-escalation:audit-blocked-test",
        "evidence_digest": "e" * 64,
        "route": {"requested_difficulty": 9},
    }
    item = {
        "plan": "demo-plan",
        "session": "demo-session",
        "workspace": str(workspace),
        "session_header": {"kind": "chain"},
        "deterministic_superfixer_evidence": base_evidence,
        "l3_escalation_gate": base_gate,
    }
    writer = RuntimeTransitionWriter(workspace)
    # Sabotage the ledger AFTER construction: the journal dir becomes a file.
    ledger_dir = workspace / ".megaplan" / "incident-ledger"
    import shutil as _shutil

    if ledger_dir.exists():
        _shutil.rmtree(ledger_dir)
    ledger_dir.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ValueError, match="runtime transition not durably recorded"):
        enqueue_audit_repair_request(
            item,
            queue_root=queue_root,
            transition_writer=writer,
            chain_spec_sha256=digest,
        )
    assert not list(queue_root.glob("requests/*.json")) if queue_root.exists() else True
    # G3: an actionable handoff without a writer FAILS CLOSED — no durable
    # runtime.* event may precede the repair request, so the enqueue blocks
    # before any request is created.
    with pytest.raises(ValueError, match="runtime transition writer is mandatory"):
        enqueue_audit_repair_request(item, queue_root=queue_root)
    assert not list(queue_root.glob("requests/*.json")) if queue_root.exists() else True


def test_auditor_enqueue_report_only_finding_needs_no_writer(tmp_path: Path) -> None:
    """Ordinary report-only findings create no repair request and therefore
    require no transition writer: no side effect means no event requirement."""
    workspace = tmp_path / "report-only-workspace"
    queue_root = workspace / ".megaplan" / "repair-queue"
    item = {
        "plan": "demo-plan",
        "session": "demo-session",
        "workspace": str(workspace),
        "session_header": {"kind": "chain"},
        "incident_projection": {"state": "blocked"},
        "incident_audit": {
            "incident_id": "inc-report-only",
            "problem_id": "problem-report-only",
            "diagnosis": {"summary": "watchdog evidence is stale"},
            "findings": [
                {
                    "status": "error",
                    "layer": "watchdog",
                    "code": "watchdog_report_stale",
                    "recommendation": "watchdog.dispatch",
                }
            ],
        },
    }
    result = enqueue_audit_repair_request(item, queue_root=queue_root)
    assert result is None
    assert not queue_root.exists()


# ── M1 T12: receipt-derived automatic-launch guards ─────────────────────

from arnold_pipelines.megaplan.cloud.six_hour_auditor import (  # noqa: E402
    AuditDispatchError,
    audit_report_only,
    audit_reconciliation_receipt,
    launch_audit_maintenance_dispatch,
    require_preinitialized_audit_receipt,
    require_receipt_proven_runtime_model,
    validate_audit_launch_guards,
)
from arnold_pipelines.megaplan.cloud.maintenance_dispatch import (  # noqa: E402
    prepare_maintenance_dispatch_receipt,
)
from arnold_pipelines.megaplan.receipts import writer as receipt_writer  # noqa: E402


def test_audit_launch_requires_preinitialized_receipt(tmp_path: Path) -> None:
    """Automatic maintenance launch is blocked without a durable initialized receipt."""
    plan_dir = tmp_path / "plan"
    prepared = prepare_maintenance_dispatch_receipt(
        action="six_hour_audit",
        configured_model=AUDIT_CODEX_MODEL,
        dispatch_id="audit-dispatch-1",
    )
    with pytest.raises(AuditDispatchError, match="no durable preinitialized receipt"):
        require_preinitialized_audit_receipt(plan_dir, "audit-dispatch-1")

    launch = mock.Mock()
    with pytest.raises(AuditDispatchError, match="no durable preinitialized receipt"):
        launch_audit_maintenance_dispatch(
            plan_dir,
            prepared,
            launch,
            resolved_runtime_model=AUDIT_CODEX_MODEL,
        )
    launch.assert_not_called()

    # A durable initialized snapshot satisfies the pre-launch guard.
    receipt_writer.initialize_dispatch_receipt(plan_dir, prepared)
    snapshot = require_preinitialized_audit_receipt(plan_dir, "audit-dispatch-1")
    assert snapshot["outcome"] == "initialized"
    assert snapshot["subprocess_started"] is False


def test_audit_launch_blocks_on_conflicting_model_pins_and_model_mismatch(
    tmp_path: Path,
) -> None:
    """Launch refuses model pin conflicts and any non-gpt-5.6-sol resolved model."""
    plan_dir = tmp_path / "plan"
    prepared = prepare_maintenance_dispatch_receipt(
        action="six_hour_audit",
        configured_model=AUDIT_CODEX_MODEL,
        dispatch_id="audit-dispatch-2",
    )
    receipt_writer.initialize_dispatch_receipt(plan_dir, prepared)
    launch = mock.Mock()

    with pytest.raises(ValueError, match="model pin conflict"):
        validate_audit_launch_guards(
            plan_dir,
            "audit-dispatch-2",
            environ={"CODEX_MODEL": "gpt-5.5"},
        )
    with pytest.raises(AuditDispatchError, match="resolved runtime model must be exactly"):
        launch_audit_maintenance_dispatch(
            plan_dir,
            prepared,
            launch,
            resolved_runtime_model="deepseek:deepseek-v4-pro",
        )
    launch.assert_not_called()
    # Configured intent can never substitute for the receipt-proven model.
    with pytest.raises(AuditDispatchError, match="receipt-proven runtime model"):
        require_receipt_proven_runtime_model(prepared)


def test_audit_launch_records_receipt_proven_model_and_falsifies_report_only(
    tmp_path: Path,
) -> None:
    """A launched maintenance action records gpt-5.6-sol and permanently falsifies report_only."""
    plan_dir = tmp_path / "plan"
    prepared = prepare_maintenance_dispatch_receipt(
        action="six_hour_audit",
        configured_model=AUDIT_CODEX_MODEL,
        dispatch_id="audit-dispatch-3",
    )
    receipt_writer.initialize_dispatch_receipt(plan_dir, prepared)
    assert audit_report_only(plan_dir, "audit-dispatch-3") is True
    initialized = json.loads(
        receipt_writer.dispatch_receipt_path(plan_dir, "audit-dispatch-3").read_text(
            encoding="utf-8"
        )
    )

    launched: list[object] = []

    def launch() -> object:
        launched.append(object())
        return launched[-1]

    started, process = launch_audit_maintenance_dispatch(
        plan_dir,
        initialized,
        launch,
        resolved_runtime_model=AUDIT_CODEX_MODEL,
    )
    assert process is launched[0]
    assert started["subprocess_started"] is True
    assert started["resolved_runtime_model"] == AUDIT_CODEX_MODEL == "gpt-5.6-sol"
    assert require_receipt_proven_runtime_model(started) == AUDIT_CODEX_MODEL
    # Once any action has started, report_only is permanently false.
    assert audit_report_only(plan_dir, "audit-dispatch-3") is False
    assert audit_report_only(plan_dir) is False
    # The durable snapshot proves the exact model without configured intent.
    snapshot = json.loads(
        receipt_writer.dispatch_receipt_path(plan_dir, "audit-dispatch-3").read_text(
            encoding="utf-8"
        )
    )
    assert snapshot["resolved_runtime_model"] == AUDIT_CODEX_MODEL
    assert snapshot["subprocess_started"] is True


def test_audit_reconciliation_preserves_explicit_indeterminate_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconciliation failure keeps the explicit indeterminate receipt state."""
    plan_dir = tmp_path / "plan"
    prepared = prepare_maintenance_dispatch_receipt(
        action="six_hour_audit",
        configured_model=AUDIT_CODEX_MODEL,
        dispatch_id="audit-dispatch-4",
    )
    initialized = receipt_writer.initialize_dispatch_receipt(plan_dir, prepared)

    monkeypatch.setattr(
        receipt_writer,
        "atomic_write_json",
        mock.Mock(side_effect=OSError("snapshot unavailable")),
    )
    with pytest.raises(receipt_writer.DispatchFinalizationError) as excinfo:
        receipt_writer.record_dispatch_started(
            plan_dir,
            initialized,
            resolved_runtime_model=AUDIT_CODEX_MODEL,
        )
    indeterminate = excinfo.value.receipt
    assert indeterminate["outcome"] == "indeterminate"
    assert indeterminate["subprocess_started"] is True
    assert indeterminate["failure_stage"] == "subprocess_started"
    # The start transition reached the append-only journal, so report_only is
    # permanently falsified even though the snapshot finalization failed.
    assert audit_report_only(plan_dir, "audit-dispatch-4") is False
    # Reconciliation preserves the explicit indeterminate receipt state and
    # never rewrites or downgrades it to report-only.
    reconciled = audit_reconciliation_receipt(
        plan_dir,
        "audit-dispatch-4",
        failure_receipt=indeterminate,
    )
    assert reconciled is not None
    assert reconciled["outcome"] == "indeterminate"
    assert reconciled["subprocess_started"] is True
    assert reconciled["failure_stage"] == "subprocess_started"
