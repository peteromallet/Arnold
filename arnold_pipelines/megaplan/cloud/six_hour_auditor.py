"""Pure incident-ledger auditor rules for the six-hour progress audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan.cloud.repair_contract import append_incident_record
from arnold_pipelines.megaplan.cloud.repair_requests import enqueue_repair_request
from arnold_pipelines.megaplan.incident.projection import build_brief, rebuild_projections

# ── auditor completion evidence constants ─────────────────────────────

_AUDITOR_6H_COMPLETION_ROW_ID = "auditor.6h_complete.1"
_AUDITOR_6H_COMPLETION_BOUNDARY_ID = "auditor_6h_completion"

AUDIT_CODEX_MODEL = "gpt-5.6-sol"
AUDIT_MODEL_INPUTS = (
    "CODEX_MODEL",
    "MEGAPLAN_AUDIT_CODEX_MODEL",
    "CLOUD_WATCHDOG_CODEX_MODEL",
)

_LAYER_ORDER = (
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
    "reconciler",
    "resolver_confidence",
    "resolver_semantics",
    "semantic_custody",
    "auditor_recursion",
    "ci_health",
    "engine_tree",
)

_RECONCILER_SUPPORTED_ACTORS = frozenset(
    {
        "watchdog",
        "github_sync",
        "install_sync",
        "immediate_repair",
        "meta_repair",
    }
)
_RECONCILER_ACTIVE_CANONICAL_STATES = frozenset({"RUNNING", "REPAIRING"})
_RECONCILER_ACTIVE_INCIDENT_STATES = frozenset({"running", "repairing", "blocked"})
_RECONCILER_ACTIVE_OUTCOMES = frozenset({"started", "running", "repairing", "blocked", "retrying"})
_RECONCILER_RECOVERED_OUTCOMES = frozenset(
    {
        "recovered",
        "completed",
        "fixed",
        "verified_recovered",
        "audit_cycle_complete",
    }
)
_AUDITOR_RECURSION_VOLATILE_KEYS = frozenset(
    {
        "message",
        "observed_at",
        "recorded_at",
        "summary",
    }
)
_AUDITOR_RECURSION_STALE_CODES = frozenset(
    {
        "live_process_absent",
        "meta_repair_missing_evidence",
        "missing_evidence_refs",
        "project_progress_stalled",
        "stale_claim_detected",
        "watchdog_report_stale",
    }
)


@dataclass(frozen=True)
class AuditorConfig:
    watchdog_stale_after: timedelta = timedelta(hours=6)
    max_running_repair_age: timedelta = timedelta(hours=2)


def validate_audit_model_inputs(environ: dict[str, str]) -> str:
    """Reject any explicit Codex pin that disagrees with the audit boundary."""
    conflicts = {
        name: value
        for name in AUDIT_MODEL_INPUTS
        if (value := str(environ.get(name) or "").strip())
        and value != AUDIT_CODEX_MODEL
    }
    if conflicts:
        rendered = ", ".join(f"{name}={value}" for name, value in sorted(conflicts.items()))
        raise ValueError(
            f"six-hour auditor model pin conflict: {rendered}; required={AUDIT_CODEX_MODEL}"
        )
    return AUDIT_CODEX_MODEL


def enqueue_audit_repair_request(
    audit_item: dict[str, Any],
    *,
    queue_root: Path | str,
) -> dict[str, Any] | None:
    """Route an unhealthy audit finding through the central repair authority.

    This is deliberately the auditor's only operational handoff.  It creates
    no claims, edits no source or run state, and performs no commit or push.
    """
    incident_audit = (
        audit_item.get("incident_audit")
        if isinstance(audit_item.get("incident_audit"), dict)
        else {}
    )
    deterministic = (
        audit_item.get("deterministic_superfixer_evidence")
        if isinstance(audit_item.get("deterministic_superfixer_evidence"), dict)
        else {}
    )
    escalation_gate = (
        audit_item.get("l3_escalation_gate")
        if isinstance(audit_item.get("l3_escalation_gate"), dict)
        else {}
    )
    deterministic_actionable = (
        deterministic.get("actionable") is True
        and escalation_gate.get("eligible") is True
        and escalation_gate.get("decision") == "true_stall"
    )
    # Ordinary reconciler/report findings are not repair authority.  The
    # separately authorized controller is the only caller that supplies this
    # coherent true-stall receipt.
    if not deterministic_actionable:
        return None
    primary = {
        "code": "stale_l1_l2_cycle",
        "layer": "superfixer_custody",
        "recommendation": "deep_superfixer_repair",
        "message": (
            "Accepted-unclaimed/exhausted L1 custody, a dead runner, an incomplete "
            "chain, and absent or stale L2 evidence require control-plane repair."
        ),
    }
    session = str(audit_item.get("session") or "").strip()
    if not session:
        raise ValueError("six-hour audit repair request requires a session")
    workspace = str(audit_item.get("workspace") or "").strip()
    plan = str(audit_item.get("plan") or "").strip()
    code = str(primary.get("code") or "six_hour_audit_finding").strip()
    layer = str(primary.get("layer") or "six_hour_auditor").strip()
    recommendation = str(primary.get("recommendation") or "").strip()
    incident_id = str(incident_audit.get("incident_id") or "").strip()
    problem_id = str(incident_audit.get("problem_id") or "").strip()
    accepted_request_ids = sorted(
        {
            str(value).strip()
            for value in deterministic.get("accepted_unclaimed_request_ids") or []
            if str(value).strip()
        }
    )
    escalation_id = str(escalation_gate.get("escalation_id") or "").strip()
    if not escalation_id:
        raise ValueError("six-hour audit repair request requires an escalation identity")
    root_cause_identity = escalation_id
    retry_ordinal = max(1, int(audit_item.get("l3_retry_ordinal") or 1))
    retry_identity = f"{root_cause_identity}:attempt:{retry_ordinal}"
    legacy_root_cause_identity = "audit:" + sha256(
        json.dumps(
            {
                "session": session,
                "plan": plan,
                "incident_id": incident_id,
                "problem_id": problem_id,
                "layer": layer,
                "code": code,
                "accepted_request_ids": accepted_request_ids,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    evidence_cursor = {
        "incident_id": incident_id,
        "problem_id": problem_id,
        "accepted_request_ids": accepted_request_ids,
        "layer": layer,
        "code": code,
        "audit_escalation_id": escalation_id,
        "finding_evidence_digest": escalation_gate.get("evidence_digest"),
        "legacy_root_cause_identity": legacy_root_cause_identity,
    }
    retry_budget = (
        dict(deterministic.get("retry_budget") or {})
        if isinstance(deterministic.get("retry_budget"), dict)
        else {}
    )
    signature = {
        "failure_kind": code,
        "current_state": str(
            audit_item.get("current_state")
            or (audit_item.get("incident_projection") or {}).get("state")
            or deterministic.get("canonical_state")
            or "machine_action_required"
        ).strip(),
        "phase_or_step": layer,
        "milestone_or_plan": plan,
        "gate_recommendation": "",
        "blocked_task_id": retry_identity,
        "event_signature": f"six_hour_auditor:{layer}:{code}:attempt:{retry_ordinal}",
    }
    diagnosis = incident_audit.get("diagnosis") if isinstance(incident_audit.get("diagnosis"), dict) else {}
    return enqueue_repair_request(
        queue_root=queue_root,
        session=session,
        problem_signature=signature,
        root_cause_hint={
            "summary": diagnosis.get("summary") or primary.get("message") or code,
            "recommendation": recommendation,
            "incident_id": incident_audit.get("incident_id"),
        },
        source="six_hour_auditor",
        target={
            "plan": plan,
            "plan_name": plan,
            "incident_id": incident_id,
            "problem_id": problem_id,
            "workspace": workspace,
            "root_cause_identity": root_cause_identity,
            "retry_ordinal": retry_ordinal,
            "retry_of_run_id": str(audit_item.get("l3_retry_of_run_id") or ""),
            "evidence_cursor": evidence_cursor,
            "retry_budget": retry_budget,
            "retry_strategy": "deep_superfixer_repair",
            "dispatch_intent": "deep_superfixer_repair",
            "deterministic_superfixer_evidence": deterministic,
            "l3_escalation_gate": escalation_gate,
            "repair_context_path": str(audit_item.get("l3_repair_context_path") or ""),
            "repair_context_digest": str(audit_item.get("l3_repair_context_digest") or ""),
            "route": escalation_gate.get("route") or {},
        },
        workspace=workspace,
        run_kind=str((audit_item.get("session_header") or {}).get("kind") or ""),
    )


def build_audit_input(
    id_or_session: str,
    *,
    root: Path | str | None = None,
    now: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Resolve the same bounded brief used by the CLI plus backing projections."""
    workspace_root = Path.cwd() if root is None else Path(root)
    projections = rebuild_projections(workspace_root, persist=persist)
    brief = build_brief(
        id_or_session,
        root=workspace_root,
        now=now,
        persist=persist,
    )
    incident = _resolve_incident(
        projections["incidents"].get("incidents", []),
        brief.get("incident_id"),
    )
    problem = _resolve_problem(
        projections["problems"].get("problems", []),
        incident.get("problem_ids", []),
    )
    return {
        "brief": brief,
        "incident": incident,
        "problem": problem,
        "projections": projections,
    }


def audit_projection_input(
    projection_input: dict[str, Any],
    *,
    live_process_snapshot: dict[str, Any] | None = None,
    now: str | None = None,
    config: AuditorConfig | None = None,
) -> dict[str, Any]:
    """Audit a projection-backed incident snapshot without mutating side state."""
    normalized_input = _normalize_projection_input(projection_input)
    brief = normalized_input["brief"]
    incident = normalized_input["incident"]
    problem = normalized_input["problem"]
    snapshot = live_process_snapshot if isinstance(live_process_snapshot, dict) else {}
    cfg = config or AuditorConfig()
    effective_now = now or snapshot.get("now") or brief.get("last_timestamp") or incident.get("last_timestamp")

    findings = [
        *_reconciler_drift_findings(
            brief=brief,
            incident=incident,
            resolver_state=normalized_input["resolver_state"],
            snapshot=snapshot,
        ),
        *_resolver_audit_findings(
            resolver_state=normalized_input["resolver_state"],
        ),
        _project_progress_finding(brief, incident, effective_now),
        _watchdog_finding(brief, snapshot, effective_now, cfg),
        _repair_layer_finding("immediate_repair", brief, incident, snapshot, effective_now, cfg),
        _repair_layer_finding("meta_repair", brief, incident, snapshot, effective_now, cfg),
        _install_sync_finding(brief, incident),
        _github_sync_finding(problem, incident, snapshot, effective_now),
        _live_process_finding(brief, incident, snapshot, effective_now),
        _stale_claim_finding(brief),
        _missing_evidence_finding(brief, incident, snapshot),
        _recurrence_finding(incident, problem),
        *_semantic_custody_findings(
            snapshot,
            now=effective_now,
            config=cfg,
        ),
    ]
    recursion_finding = _auditor_recursion_finding(
        brief=brief,
        incident=incident,
        current_target=normalized_input["current_target"],
        audit_history=normalized_input["audit_history"],
        findings=findings,
    )
    if recursion_finding is not None:
        findings.append(recursion_finding)

    unhealthy = [finding for finding in findings if finding["status"] != "ok"]
    primary = _primary_finding(unhealthy)
    diagnosis_summary = _diagnosis_summary(brief, unhealthy)
    next_expected_event = _next_expected_event(primary, brief, incident, problem)
    if _requires_human_escalation(unhealthy):
        outcome = "auditor_human_escalation"
        next_expected_event = "auditor_escalate_to_human"
    else:
        outcome = "escalated" if unhealthy else "audit_cycle_complete"
        if not unhealthy and str(brief.get("outcome") or "") == "recovered":
            outcome = "audit_cycle_complete"

    return {
        "incident_id": brief.get("incident_id") or incident.get("incident_id"),
        "problem_id": problem.get("problem_id"),
        "findings": findings,
        "diagnosis": {
            "summary": diagnosis_summary,
            "finding_count": len(unhealthy),
            "highest_severity": primary["severity"] if primary is not None else "ok",
        },
        "audit_complete": {
            "outcome": outcome,
            "summary": diagnosis_summary,
            "next_expected_event": next_expected_event,
        },
        "next_expected_event": next_expected_event,
    }


def audit_incident(
    *,
    brief: dict[str, Any],
    incident: dict[str, Any] | None = None,
    problem: dict[str, Any] | None = None,
    live_process_snapshot: dict[str, Any] | None = None,
    now: str | None = None,
    config: AuditorConfig | None = None,
) -> dict[str, Any]:
    return audit_projection_input(
        {
            "brief": brief,
            "incident": incident or {},
            "problem": problem or {},
        },
        live_process_snapshot=live_process_snapshot,
        now=now,
        config=config,
    )


def _project_progress_finding(
    brief: dict[str, Any],
    incident: dict[str, Any],
    now: str | None,
) -> dict[str, Any]:
    deadline_status = brief.get("deadline_status")
    if deadline_status == "overdue" and incident.get("next_expected_event"):
        return _finding(
            "project_progress_stalled",
            layer="project_progress",
            status="error",
            severity="error",
            message="The incident is past its deadline without reaching the next expected transition.",
            recommendation=str(incident.get("next_expected_event")),
        )
    return _finding(
        "project_progress_observed",
        layer="project_progress",
        status="ok",
        severity="ok",
        message="Projection state is bounded and ready for reconciliation.",
        recommendation=None,
    )


def _reconciler_drift_findings(
    *,
    brief: dict[str, Any],
    incident: dict[str, Any],
    resolver_state: dict[str, Any],
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    resolver_finding = _resolver_vs_ledger_drift_finding(
        brief=brief,
        incident=incident,
        resolver_state=resolver_state,
    )
    if resolver_finding is not None:
        findings.append(resolver_finding)

    brief_incident_finding = _brief_vs_incident_drift_finding(
        brief=brief,
        incident=incident,
    )
    if brief_incident_finding is not None:
        findings.append(brief_incident_finding)

    brief_snapshot_finding = _brief_vs_snapshot_drift_finding(
        brief=brief,
        incident=incident,
        snapshot=snapshot,
    )
    if brief_snapshot_finding is not None:
        findings.append(brief_snapshot_finding)

    l2_fix_finding = _l2_fix_vs_resolver_drift_finding(
        brief=brief,
        incident=incident,
        resolver_state=resolver_state,
        snapshot=snapshot,
    )
    if l2_fix_finding is not None:
        findings.append(l2_fix_finding)

    return findings


def _resolver_audit_findings(
    *,
    resolver_state: dict[str, Any],
) -> list[dict[str, Any]]:
    if not resolver_state:
        return []

    findings: list[dict[str, Any]] = []

    confidence_finding = _resolver_confidence_finding(resolver_state=resolver_state)
    if confidence_finding is not None:
        findings.append(confidence_finding)

    semantic_finding = _resolver_semantic_finding(resolver_state=resolver_state)
    if semantic_finding is not None:
        findings.append(semantic_finding)

    return findings


def _resolver_confidence_finding(
    *,
    resolver_state: dict[str, Any],
) -> dict[str, Any] | None:
    resolver_confidence = _normalized_text(resolver_state.get("confidence")).lower()
    if resolver_confidence != "low":
        return None

    return _finding(
        "resolver_low_confidence",
        layer="resolver_confidence",
        status="error",
        severity="error",
        message="Resolver confidence is too low to accept automated custody recovery.",
        recommendation="auditor_escalate_to_human",
        observed={
            "resolver_confidence": resolver_confidence,
            "resolver_canonical_state": _resolver_canonical_state_name(resolver_state),
            "resolver_next_action": _normalized_text(resolver_state.get("next_action")),
        },
    )


def _resolver_semantic_finding(
    *,
    resolver_state: dict[str, Any],
) -> dict[str, Any] | None:
    if _normalized_text(resolver_state.get("confidence")).lower() == "low":
        return None

    canonical_state = _resolver_canonical_state_name(resolver_state)
    evidence_kinds = _resolver_evidence_kinds(resolver_state)
    expected_canonical_states = _expected_canonical_states_for_evidence(evidence_kinds)
    stale_sources = _resolver_stale_sources(resolver_state)
    next_action = _normalized_text(resolver_state.get("next_action"))
    root_cause = resolver_state.get("root_cause_fingerprint")
    root_cause_kind = _resolver_root_cause_kind(root_cause)
    invalid_reasons: list[str] = []

    if expected_canonical_states and canonical_state and canonical_state not in expected_canonical_states:
        invalid_reasons.append("wrong_canonical_state_for_evidence")

    if "wrong_canonical_state_for_evidence" in invalid_reasons and not stale_sources:
        invalid_reasons.append("missing_stale_sources")

    expected_root_cause_kinds = _expected_root_cause_kinds_for_canonical_state(canonical_state)
    if root_cause_kind and expected_root_cause_kinds and root_cause_kind not in expected_root_cause_kinds:
        invalid_reasons.append("wrong_root_cause_fingerprint_kind")

    if next_action and not _next_action_matches_canonical_state(canonical_state, next_action):
        invalid_reasons.append("next_action_mismatch")

    if not invalid_reasons:
        return None

    return _finding(
        "resolver_semantic_invalid",
        layer="resolver_semantics",
        status="error",
        severity="error",
        message="Resolver output is semantically incompatible with its supporting evidence.",
        recommendation="auditor_escalate_to_human",
        invalid_reasons=invalid_reasons,
        observed={
            "resolver_canonical_state": canonical_state,
            "resolver_next_action": next_action,
            "root_cause_fingerprint_kind": root_cause_kind,
            "stale_sources": stale_sources,
        },
        expected={
            "canonical_states": sorted(expected_canonical_states) if expected_canonical_states else [],
            "root_cause_fingerprint_kinds": sorted(expected_root_cause_kinds),
        },
    )


def _resolver_vs_ledger_drift_finding(
    *,
    brief: dict[str, Any],
    incident: dict[str, Any],
    resolver_state: dict[str, Any],
) -> dict[str, Any] | None:
    resolver_canonical_state = _resolver_canonical_state_name(resolver_state)
    brief_outcome = _normalized_text(brief.get("outcome")).lower()
    incident_state = _normalized_text(incident.get("state")).lower()
    expected_brief_outcome = _expected_brief_outcome_from_incident(incident)
    next_expected_event = _normalized_text(incident.get("next_expected_event") or brief.get("next_expected_event"))

    if resolver_canonical_state not in _RECONCILER_ACTIVE_CANONICAL_STATES:
        return None
    if brief_outcome not in _RECONCILER_RECOVERED_OUTCOMES:
        return None
    if not incident_state or not _incident_represents_active_work(incident):
        return None
    if not expected_brief_outcome:
        return None

    return _drift_detected_finding(
        source_pair="resolver_vs_ledger",
        contradiction="resolver_canonical_state_conflicts_with_ledger_outcome",
        observed={
            "resolver_canonical_state": resolver_canonical_state,
            "brief_outcome": brief_outcome,
            "incident_state": incident_state,
        },
        expected={
            "brief_outcome": expected_brief_outcome,
            "incident_state": incident_state,
            "next_expected_event": next_expected_event,
        },
        recommendation=next_expected_event or None,
    )


def _brief_vs_incident_drift_finding(
    *,
    brief: dict[str, Any],
    incident: dict[str, Any],
) -> dict[str, Any] | None:
    brief_outcome = _normalized_text(brief.get("outcome")).lower()
    incident_state = _normalized_text(incident.get("state")).lower()
    incident_outcome = _normalized_text(incident.get("outcome")).lower()
    expected_brief_outcome = _expected_brief_outcome_from_incident(incident)

    if brief_outcome not in _RECONCILER_RECOVERED_OUTCOMES:
        return None
    if not incident_state or not _incident_represents_active_work(incident):
        return None
    if not expected_brief_outcome or brief_outcome == expected_brief_outcome:
        return None

    return _drift_detected_finding(
        source_pair="brief_vs_incident",
        contradiction="brief_outcome_conflicts_with_incident_state",
        observed={
            "brief_outcome": brief_outcome,
            "incident_state": incident_state,
            "incident_outcome": incident_outcome,
        },
        expected={
            "brief_outcome": expected_brief_outcome,
            "incident_state": incident_state,
            "incident_outcome": incident_outcome,
        },
        recommendation=None,
    )


def _brief_vs_snapshot_drift_finding(
    *,
    brief: dict[str, Any],
    incident: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    next_expected_event = _normalized_text(brief.get("next_expected_event") or incident.get("next_expected_event"))
    expected_actor = _expected_actor_for_event(next_expected_event)
    observed_actor = _observed_snapshot_actor(snapshot, session_ids=_session_ids(incident))

    if expected_actor is None or observed_actor is None or expected_actor == observed_actor:
        return None

    return _drift_detected_finding(
        source_pair="brief_vs_snapshot",
        contradiction="next_expected_actor_conflicts_with_live_process",
        observed={
            "next_expected_event": next_expected_event,
            "snapshot_actor": observed_actor,
        },
        expected={
            "snapshot_actor": expected_actor,
        },
        recommendation=next_expected_event or None,
    )


def _l2_fix_vs_resolver_drift_finding(
    *,
    brief: dict[str, Any],
    incident: dict[str, Any],
    resolver_state: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    placeholders = _incident_placeholders(brief, incident)
    shipped_fix = _normalized_text(placeholders.get("shipped_fix")).lower()
    install_freshness = _normalized_text(placeholders.get("install_freshness")).lower()
    resolver_canonical_state = _resolver_canonical_state_name(resolver_state)
    brief_outcome = _normalized_text(brief.get("outcome")).lower()
    incident_state = _normalized_text(incident.get("state")).lower()
    expected_brief_outcome = _expected_brief_outcome_from_incident(incident)
    next_expected_event = _normalized_text(incident.get("next_expected_event") or brief.get("next_expected_event"))
    observed_actor = _observed_snapshot_actor(snapshot, session_ids=_session_ids(incident))

    if resolver_canonical_state not in _RECONCILER_ACTIVE_CANONICAL_STATES:
        return None
    if brief_outcome not in _RECONCILER_RECOVERED_OUTCOMES:
        return None
    if not incident_state or not _incident_represents_active_work(incident):
        return None
    if observed_actor is None or expected_brief_outcome is None:
        return None
    if shipped_fix != "fixed" and install_freshness != "fresh":
        return None

    return _drift_detected_finding(
        source_pair="l2_fix_vs_resolver",
        contradiction="false_fixed_l2_result",
        observed={
            "brief_outcome": brief_outcome,
            "incident_state": incident_state,
            "resolver_canonical_state": resolver_canonical_state,
            "snapshot_actor": observed_actor,
        },
        expected={
            "brief_outcome": expected_brief_outcome,
            "incident_state": incident_state,
            "next_expected_event": next_expected_event,
        },
        recommendation=next_expected_event or None,
    )


def _normalize_projection_input(projection_input: Any) -> dict[str, Any]:
    source = projection_input if isinstance(projection_input, dict) else {}
    return {
        "brief": _coerce_mapping(source.get("brief")),
        "incident": _coerce_mapping(source.get("incident")),
        "problem": _coerce_mapping(source.get("problem")),
        "resolver_state": _coerce_resolver_state(source.get("resolver_state")),
        "current_target": _coerce_current_target(source.get("current_target")),
        "audit_history": _coerce_audit_history(source.get("audit_history")),
        "ci_health": _coerce_ci_health(source.get("ci_health")),
        "engine_tree": _coerce_engine_tree(source.get("engine_tree")),
    }


def _coerce_resolver_state(value: Any) -> dict[str, Any]:
    return _coerce_mapping(value)


def _coerce_current_target(value: Any) -> dict[str, Any]:
    return _coerce_mapping(value)


def _coerce_audit_history(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _coerce_ci_health(value: Any) -> dict[str, Any]:
    return _coerce_mapping(value)


def _coerce_engine_tree(value: Any) -> dict[str, Any]:
    return _coerce_mapping(value)


def _drift_detected_finding(
    *,
    source_pair: str,
    contradiction: str,
    observed: dict[str, Any],
    expected: dict[str, Any],
    recommendation: str | None,
) -> dict[str, Any]:
    return _finding(
        "DRIFT_DETECTED",
        layer="reconciler",
        status="error",
        severity="error",
        message=f"Cross-source reconciler drift detected for {source_pair}.",
        recommendation=recommendation,
        drift_reason=f"{source_pair}:{contradiction}",
        source_pair=source_pair,
        contradiction=contradiction,
        observed=observed,
        expected=expected,
    )


def _resolver_canonical_state_name(resolver_state: dict[str, Any]) -> str:
    return _normalized_text(resolver_state.get("canonical_state")).upper()


def _expected_brief_outcome_from_incident(incident: dict[str, Any]) -> str | None:
    incident_outcome = _normalized_text(incident.get("outcome")).lower()
    if incident_outcome:
        return incident_outcome
    if _incident_represents_active_work(incident):
        return "started"
    return None


def _incident_represents_active_work(incident: dict[str, Any]) -> bool:
    incident_state = _normalized_text(incident.get("state")).lower()
    incident_outcome = _normalized_text(incident.get("outcome")).lower()
    next_expected_event = _normalized_text(incident.get("next_expected_event"))
    expected_actor = _expected_actor_for_event(next_expected_event)
    return (
        incident_state in _RECONCILER_ACTIVE_INCIDENT_STATES
        or incident_outcome in _RECONCILER_ACTIVE_OUTCOMES
        or expected_actor in _RECONCILER_SUPPORTED_ACTORS
    )


def _incident_placeholders(brief: dict[str, Any], incident: dict[str, Any]) -> dict[str, Any]:
    incident_placeholders = incident.get("placeholders")
    if isinstance(incident_placeholders, dict):
        return incident_placeholders
    brief_placeholders = brief.get("placeholders")
    return brief_placeholders if isinstance(brief_placeholders, dict) else {}


def _session_ids(incident: dict[str, Any]) -> list[str]:
    session_ids = incident.get("session_ids")
    if not isinstance(session_ids, list):
        return []
    return [str(session_id) for session_id in session_ids if isinstance(session_id, str) and session_id]


def _observed_snapshot_actor(snapshot: dict[str, Any], *, session_ids: list[str]) -> str | None:
    process_actor = _snapshot_process_actor(snapshot, session_ids=session_ids)
    if process_actor is not None:
        return process_actor
    repair_attempt_actor = _snapshot_repair_attempt_actor(snapshot)
    if repair_attempt_actor is not None:
        return repair_attempt_actor
    github_sync = snapshot.get("github_sync")
    if isinstance(github_sync, dict) and _normalized_text(github_sync.get("last_attempt_at")):
        return "github_sync"
    return None


def _snapshot_process_actor(snapshot: dict[str, Any], *, session_ids: list[str]) -> str | None:
    processes = snapshot.get("processes")
    if not isinstance(processes, list):
        return None
    candidates: list[dict[str, Any]] = []
    for process in processes:
        if not isinstance(process, dict):
            continue
        actor = _normalized_text(process.get("actor"))
        if actor not in _RECONCILER_SUPPORTED_ACTORS:
            continue
        process_session_id = _normalized_text(process.get("session_id"))
        if session_ids and process_session_id and process_session_id not in session_ids:
            continue
        candidates.append(process)
    if not candidates:
        return None
    chosen = sorted(
        candidates,
        key=lambda item: (
            _normalized_text(item.get("actor")),
            _normalized_text(item.get("session_id")),
            _normalized_text(item.get("started_at")),
        ),
    )[0]
    actor = _normalized_text(chosen.get("actor"))
    return actor if actor in _RECONCILER_SUPPORTED_ACTORS else None


def _snapshot_repair_attempt_actor(snapshot: dict[str, Any]) -> str | None:
    attempts = snapshot.get("repair_attempts")
    if not isinstance(attempts, list):
        return None
    for attempt in reversed(attempts):
        if not isinstance(attempt, dict):
            continue
        actor = _repair_attempt_actor(attempt)
        if actor is not None:
            return actor
    return None


def _repair_attempt_actor(attempt: dict[str, Any]) -> str | None:
    for field in ("actor", "layer", "phase"):
        actor = _normalized_text(attempt.get(field))
        if actor in _RECONCILER_SUPPORTED_ACTORS:
            return actor
    next_expected_event = _normalized_text(attempt.get("next_expected_event"))
    return _expected_actor_for_event(next_expected_event)


def _expected_actor_for_event(next_expected_event: str) -> str | None:
    actor = next_expected_event.split(".", 1)[0].strip() if next_expected_event else ""
    return actor if actor in _RECONCILER_SUPPORTED_ACTORS else None


def _resolver_evidence_kinds(resolver_state: dict[str, Any]) -> set[str]:
    kinds: set[str] = set()
    root_cause_kind = _resolver_root_cause_kind(resolver_state.get("root_cause_fingerprint"))
    if root_cause_kind:
        kinds.add(root_cause_kind)

    evidence = resolver_state.get("evidence")
    if isinstance(evidence, dict):
        for key in evidence:
            if isinstance(key, str) and key:
                kinds.add(key)

    return kinds


def _resolver_root_cause_kind(value: Any) -> str:
    if isinstance(value, dict):
        kind = value.get("kind")
        return _normalized_text(kind).lower()
    return ""


def _resolver_stale_sources(resolver_state: dict[str, Any]) -> list[str]:
    stale_sources = resolver_state.get("stale_sources")
    if not isinstance(stale_sources, list):
        return []
    return [source for source in stale_sources if isinstance(source, str) and source]


def _expected_canonical_states_for_evidence(evidence_kinds: set[str]) -> set[str]:
    expected: set[str] = set()
    if evidence_kinds & {"active_step_heartbeat", "live_process"}:
        expected.update({"RUNNING", "REPAIRING"})
    if evidence_kinds & {"budget_exhausted", "retryable_execution", "mechanical_blocker"}:
        expected.add("RETRYABLE_EXECUTION_BLOCK")
    if evidence_kinds & {"broken_state_machine", "missing_workspace", "broken_repeat_count"}:
        expected.add("BROKEN_STATE_MACHINE")
    if evidence_kinds & {"awf018", "route_metadata_mismatch", "real_implementation_block"}:
        expected.add("REAL_IMPLEMENTATION_BLOCK")
    if evidence_kinds & {
        "approval",
        "explicit_approval",
        "credential",
        "credential_account",
        "needs_human",
        "policy",
        "quota",
        "rate_limit",
        "true_blocker",
        "user_action",
        "verification",
    }:
        expected.add("HUMAN_ACTION_REQUIRED")
    return expected


def _expected_root_cause_kinds_for_canonical_state(canonical_state: str) -> set[str]:
    return {
        "RUNNING": {"active_step_heartbeat", "live_process"},
        "REPAIRING": {"active_step_heartbeat", "live_process"},
        "RETRYABLE_EXECUTION_BLOCK": {"budget_exhausted", "retryable_execution", "mechanical_blocker"},
        "BROKEN_STATE_MACHINE": {"broken_state_machine", "broken_repeat_count", "missing_workspace"},
        "REAL_IMPLEMENTATION_BLOCK": {"awf018", "real_implementation_block", "route_metadata_mismatch"},
        "HUMAN_ACTION_REQUIRED": {
            "approval",
            "credential",
            "credential_account",
            "needs_human",
            "policy",
            "quota",
            "rate_limit",
            "true_blocker",
            "user_action",
            "verification",
        },
        "UNKNOWN": set(),
        "PAUSED": {"operator_pause"},
        "COMPLETED": set(),
        "STALE_DERIVED_STATE": set(),
    }.get(canonical_state, set())


def _next_action_matches_canonical_state(canonical_state: str, next_action: str) -> bool:
    if canonical_state in {"RUNNING", "REPAIRING"}:
        return next_action not in {
            "auditor_escalate_to_human",
            "await_human_action",
            "escalate_broken_state_machine",
            "inspect_evidence",
            "machine_repair_or_replan",
            "manual_review",
            "no_action_run_complete",
            "requeue_or_retry",
            "trust_live_worker_suppress_stale_label",
        }

    valid_actions = {
        "BROKEN_STATE_MACHINE": {"escalate_broken_state_machine"},
        "COMPLETED": {"audit_cycle_complete", "no_action_run_complete"},
        "PAUSED": {"explicit_operator_resume"},
        "HUMAN_ACTION_REQUIRED": {"await_human_action", "manual_review"},
        "REAL_IMPLEMENTATION_BLOCK": {"machine_repair_or_replan"},
        "RETRYABLE_EXECUTION_BLOCK": {"requeue_or_retry"},
        "STALE_DERIVED_STATE": {"trust_live_worker_suppress_stale_label"},
        "UNKNOWN": {"inspect_evidence", "manual_review"},
    }
    allowed = valid_actions.get(canonical_state)
    if allowed is None:
        return True
    return next_action in allowed


def _normalized_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _watchdog_finding(
    brief: dict[str, Any],
    snapshot: dict[str, Any],
    now: str | None,
    config: AuditorConfig,
) -> dict[str, Any]:
    watchdog = snapshot.get("watchdog") if isinstance(snapshot.get("watchdog"), dict) else {}
    last_reported_at = watchdog.get("last_reported_at")
    if _is_stale(last_reported_at, now, config.watchdog_stale_after):
        return _finding(
            "watchdog_report_stale",
            layer="watchdog",
            status="error",
            severity="error",
            message="The watchdog report is older than the configured audit cadence.",
            recommendation="watchdog.dispatch",
            observed_at=last_reported_at,
        )
    return _finding(
        "watchdog_observed",
        layer="watchdog",
        status="ok",
        severity="ok",
        message="Watchdog evidence is fresh enough for this audit cycle.",
        recommendation=brief.get("next_expected_event"),
    )


def _repair_layer_finding(
    layer: str,
    brief: dict[str, Any],
    incident: dict[str, Any],
    snapshot: dict[str, Any],
    now: str | None,
    config: AuditorConfig,
) -> dict[str, Any]:
    expected = str(brief.get("next_expected_event") or incident.get("next_expected_event") or "")
    actor = layer
    process = _matching_process(snapshot, actor=actor, session_ids=incident.get("session_ids", []))
    missing_expected = expected == f"{layer}.repair_attempt" and process is None
    running_too_long = process is not None and _is_stale(
        process.get("started_at") or process.get("last_heartbeat_at"),
        now,
        config.max_running_repair_age,
    )

    if missing_expected:
        return _finding(
            f"{layer}_missing_evidence",
            layer=layer,
            status="error",
            severity="error",
            message=f"The projection expects {layer} activity but the live snapshot has no corroborating process.",
            recommendation=f"{layer}.repair_attempt",
        )
    if running_too_long:
        return _finding(
            f"{layer}_running_stale",
            layer=layer,
            status="error",
            severity="error",
            message=f"The {layer} process has been running longer than the configured maximum.",
            recommendation="meta_repair.repair_attempt" if layer == "immediate_repair" else f"{layer}.repair_attempt",
            observed_at=process.get("started_at") or process.get("last_heartbeat_at"),
        )
    return _finding(
        f"{layer}_observed",
        layer=layer,
        status="ok",
        severity="ok",
        message=f"{layer} is not the current blocker in this audit snapshot.",
        recommendation=brief.get("next_expected_event"),
    )


def _install_sync_finding(
    brief: dict[str, Any],
    incident: dict[str, Any],
) -> dict[str, Any]:
    placeholders = brief.get("placeholders") if isinstance(brief.get("placeholders"), dict) else incident.get("placeholders", {})
    install_freshness = str(placeholders.get("install_freshness") or "unknown")
    if install_freshness in {"stale", "failed", "unverified"}:
        return _finding(
            f"install_sync_{install_freshness}",
            layer="install_sync",
            status="warn" if install_freshness == "unverified" else "error",
            severity="warn" if install_freshness == "unverified" else "error",
            message=f"Install-sync freshness is {install_freshness}.",
            recommendation="install_sync.retry",
        )
    return _finding(
        "install_sync_observed",
        layer="install_sync",
        status="ok",
        severity="ok",
        message="Install-sync placeholders do not indicate a blocking mismatch.",
        recommendation=brief.get("next_expected_event"),
    )


def _github_sync_finding(
    problem: dict[str, Any],
    incident: dict[str, Any],
    snapshot: dict[str, Any],
    now: str | None,
) -> dict[str, Any]:
    if not problem:
        return _finding(
            "github_sync_not_applicable",
            layer="github_sync",
            status="ok",
            severity="ok",
            message="No persistent problem projection is linked to this incident.",
            recommendation=None,
        )
    publish_due = (
        problem.get("status") == "open"
        and int(problem.get("occurrence_count") or 0) >= 2
    ) or bool(problem.get("recurred_after_fix"))
    github_sync = snapshot.get("github_sync") if isinstance(snapshot.get("github_sync"), dict) else {}
    last_attempt = _github_sync_last_attempt(incident, github_sync)
    if publish_due and not last_attempt:
        return _finding(
            "github_sync_publish_due",
            layer="github_sync",
            status="warn",
            severity="warn",
            message="The persistent problem meets the GitHub sync threshold but no publication attempt was observed.",
            recommendation="github_sync.publish",
        )
    return _finding(
        "github_sync_observed",
        layer="github_sync",
        status="ok",
        severity="ok",
        message="GitHub sync is not currently the blocking layer.",
        recommendation="github_sync.publish" if publish_due else None,
    )


def _github_sync_last_attempt(incident: dict[str, Any], github_sync: dict[str, Any]) -> str | None:
    last_attempt = _normalized_text(github_sync.get("last_attempt_at"))
    if last_attempt:
        return last_attempt

    if _normalized_text(incident.get("latest_actor")) == "github_sync":
        incident_last_timestamp = _normalized_text(incident.get("last_timestamp"))
        if incident_last_timestamp:
            return incident_last_timestamp

    events = incident.get("events")
    if not isinstance(events, list):
        return None
    for event in events:
        if not isinstance(event, dict):
            continue
        actor = _normalized_text(event.get("actor"))
        kind = _normalized_text(event.get("kind"))
        if actor != "github_sync" and not kind.startswith("incident.github_sync."):
            continue
        for key in ("timestamp", "recorded_at", "created_at", "timestamp_utc"):
            value = _normalized_text(event.get(key))
            if value:
                return value
    return None


def _live_process_finding(
    brief: dict[str, Any],
    incident: dict[str, Any],
    snapshot: dict[str, Any],
    now: str | None,
) -> dict[str, Any]:
    processes = snapshot.get("processes")
    process_count = len(processes) if isinstance(processes, list) else 0
    if process_count == 0 and brief.get("deadline_status") == "overdue":
        return _finding(
            "live_process_absent",
            layer="live_process",
            status="warn",
            severity="warn",
            message="No corroborating live process snapshot was supplied for an overdue incident.",
            recommendation=incident.get("next_expected_event") or brief.get("next_expected_event"),
        )
    return _finding(
        "live_process_observed",
        layer="live_process",
        status="ok",
        severity="ok",
        message="Live-process corroboration is present or not required for this incident.",
        recommendation=None,
    )


def _stale_claim_finding(brief: dict[str, Any]) -> dict[str, Any]:
    claims = brief.get("claims") if isinstance(brief.get("claims"), list) else []
    expired = [claim for claim in claims if claim.get("classification") == "expired"]
    if expired:
        return _finding(
            "stale_claim_detected",
            layer="stale_claim",
            status="error",
            severity="error",
            message="At least one incident claim expired without the expected handoff.",
            recommendation="watchdog.dispatch",
            claim_ids=[claim.get("claim_id") for claim in expired if claim.get("claim_id")],
        )
    return _finding(
        "claims_current",
        layer="stale_claim",
        status="ok",
        severity="ok",
        message="Claim deadlines are not currently stale.",
        recommendation=None,
    )


def _missing_evidence_finding(
    brief: dict[str, Any],
    incident: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    evidence = brief.get("evidence") if isinstance(brief.get("evidence"), list) else []
    missing = [item for item in evidence if item.get("status") == "MISSING"]
    expected = str(brief.get("next_expected_event") or incident.get("next_expected_event") or "")
    meta_snapshot = snapshot.get("meta_repair") if isinstance(snapshot.get("meta_repair"), dict) else {}
    meta_evidence = meta_snapshot.get("evidence_refs")
    if expected == "meta_repair.repair_attempt" and not meta_evidence:
        return _finding(
            "meta_repair_missing_evidence",
            layer="missing_evidence",
            status="error",
            severity="error",
            message="Meta-repair is expected next but no meta-repair evidence references were supplied.",
            recommendation="meta_repair.repair_attempt",
        )
    if missing:
        return _finding(
            "missing_evidence_refs",
            layer="missing_evidence",
            status="error",
            severity="error",
            message="The bounded brief references evidence paths that are no longer present.",
            recommendation="system.integrity_repair",
            missing_paths=[item.get("path") for item in missing if item.get("path")],
        )
    return _finding(
        "evidence_present",
        layer="missing_evidence",
        status="ok",
        severity="ok",
        message="No missing evidence references were detected in the bounded brief.",
        recommendation=None,
    )


def _recurrence_finding(
    incident: dict[str, Any],
    problem: dict[str, Any],
) -> dict[str, Any]:
    placeholders = incident.get("placeholders") if isinstance(incident.get("placeholders"), dict) else {}
    recurrence = placeholders.get("recurrence")
    if recurrence == "recurred_after_fix" or problem.get("recurred_after_fix") is True:
        return _finding(
            "problem_recurred_after_fix",
            layer="recurrence",
            status="error",
            severity="error",
            message="The linked persistent problem recurred after it had previously been fixed.",
            recommendation="github_sync.publish",
        )
    if recurrence == "repeated_attempts_without_new_evidence":
        return _finding(
            "repeated_attempts_without_new_evidence",
            layer="recurrence",
            status="warn",
            severity="warn",
            message="Repair attempts are cycling without adding new evidence.",
            recommendation="meta_repair.repair_attempt",
        )
    return _finding(
        "recurrence_clear",
        layer="recurrence",
        status="ok",
        severity="ok",
        message="No recurrence signal is currently projected for this incident.",
        recommendation=None,
    )



# ── S4 semantic/custody auditor reason codes ───────────────────────────
# These consume pre-computed semantic-health and custody facts from the
# status snapshot; they never recompute findings or custody independently.

_SEMANTIC_CUSTODY_LAYER = "semantic_custody"
_AUDITOR_CUSTODY_DISAGREEMENT_CODE = "custody_disagreement"
_AUDITOR_UNRESOLVED_SEMANTIC_CODE = "unresolved_semantic_findings"
_AUDITOR_STALE_ACTIVE_STEP_CODE = "stale_active_step_worker"
_AUDITOR_UNMANAGED_PROCESS_CODE = "unmanaged_live_process"
_AUDITOR_REPAIR_SUCCESS_NO_CUSTODY_CODE = "repair_success_without_custody"

_CUSTODY_MANAGED_STATES: frozenset[str] = frozenset({"managed-running", "complete"})
_CUSTODY_UNMANAGED_STATES: frozenset[str] = frozenset(
    {"unmanaged-running-with-warning", "blocked-relaunch-failure"}
)
_REPAIR_SUCCESS_STATES: frozenset[str] = frozenset({"recovered", "completed", "fixed", "verified_recovered"})


def _semantic_custody_findings(
    snapshot: dict[str, Any],
    *,
    now: str | None,
    config: AuditorConfig,
) -> list[dict[str, Any]]:
    """Gather all semantic/custody findings, consuming snapshot facts only."""
    findings: list[dict[str, Any]] = []

    unresolved = _unresolved_semantic_finding(snapshot)
    if unresolved is not None:
        findings.append(unresolved)

    stale_worker = _stale_active_step_worker_finding(snapshot, now=now, config=config)
    if stale_worker is not None:
        findings.append(stale_worker)

    unmanaged = _unmanaged_live_process_finding(snapshot)
    if unmanaged is not None:
        findings.append(unmanaged)

    repair_no_custody = _repair_success_without_custody_finding(snapshot)
    if repair_no_custody is not None:
        findings.append(repair_no_custody)

    disagreement = _custody_disagreement_finding(snapshot)
    if disagreement is not None:
        findings.append(disagreement)

    # Emit a healthy ok when all sub-checks pass.
    if not findings:
        findings.append(
            _finding(
                "semantic_custody_clear",
                layer=_SEMANTIC_CUSTODY_LAYER,
                status="ok",
                severity="ok",
                message="Semantic-health and custody facts are consistent and clear.",
                recommendation=None,
            )
        )

    return findings


def _unresolved_semantic_finding(
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    """Detect unresolved semantic findings from the status snapshot.

    Consumes the pre-computed ``semantic_health`` summary (produced by
    :func:`cloud_counts_summary`) -- never recomputes findings independently.
    """
    semantic_health = snapshot.get("semantic_health")
    if not isinstance(semantic_health, dict):
        return None
    total_count = semantic_health.get("total_count", 0)
    if not isinstance(total_count, int) or total_count <= 0:
        return None
    return _finding(
        _AUDITOR_UNRESOLVED_SEMANTIC_CODE,
        layer=_SEMANTIC_CUSTODY_LAYER,
        status="error",
        severity="error",
        message=f"Status snapshot reports {total_count} unresolved semantic finding(s).",
        recommendation="immediate_repair.repair_attempt",
        total_count=total_count,
        fingerprint=semantic_health.get("fingerprint"),
        counts_by_kind=semantic_health.get("counts_by_kind"),
        counts_by_boundary=semantic_health.get("counts_by_boundary"),
    )


def _stale_active_step_worker_finding(
    snapshot: dict[str, Any],
    *,
    now: str | None,
    config: AuditorConfig,
) -> dict[str, Any] | None:
    """Detect a stale active-step worker from the status snapshot.

    Uses the same staleness threshold as the watchdog
    (:attr:`AuditorConfig.watchdog_stale_after`).
    """
    activity_phase = snapshot.get("activity_phase")
    if not isinstance(activity_phase, str) or not activity_phase:
        return None
    last_activity = snapshot.get("last_activity")
    if not _is_stale(last_activity, now, config.watchdog_stale_after):
        return None
    return _finding(
        _AUDITOR_STALE_ACTIVE_STEP_CODE,
        layer=_SEMANTIC_CUSTODY_LAYER,
        status="warn",
        severity="warn",
        message=(
            f"Active-step worker is in phase '{activity_phase}' but its last "
            "activity is older than the audit cadence."
        ),
        recommendation="watchdog.dispatch",
        activity_phase=activity_phase,
        last_activity=last_activity,
    )


def _unmanaged_live_process_finding(
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    """Detect an unmanaged live process from custody state in the snapshot."""
    custody_state = snapshot.get("custody_state")
    if not isinstance(custody_state, str) or not custody_state:
        return None
    if custody_state not in _CUSTODY_UNMANAGED_STATES:
        return None
    return _finding(
        _AUDITOR_UNMANAGED_PROCESS_CODE,
        layer=_SEMANTIC_CUSTODY_LAYER,
        status="warn",
        severity="warn",
        message=f"Session custody is '{custody_state}' -- the process is live but not under managed supervision.",
        recommendation="watchdog.dispatch",
        custody_state=custody_state,
    )


def _repair_success_without_custody_finding(
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    """Detect repair-success claims without corroborating managed custody."""
    repair_state = snapshot.get("repair_state")
    custody_state = snapshot.get("custody_state")
    if not isinstance(repair_state, str) or not repair_state:
        return None
    if repair_state not in _REPAIR_SUCCESS_STATES:
        return None
    if isinstance(custody_state, str) and custody_state in _CUSTODY_MANAGED_STATES:
        return None
    return _finding(
        _AUDITOR_REPAIR_SUCCESS_NO_CUSTODY_CODE,
        layer=_SEMANTIC_CUSTODY_LAYER,
        status="warn",
        severity="warn",
        message=(
            f"Repair state '{repair_state}' indicates success but custody "
            f"is '{custody_state or 'unknown'}' -- not under managed supervision."
        ),
        recommendation="watchdog.dispatch",
        repair_state=repair_state,
        custody_state=custody_state or "",
    )


def _custody_disagreement_finding(
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    """Detect watchdog/status custody disagreement from snapshot facts.

    Compares the watchdog's recorded custody kind against the status
    snapshot's custody_state.  Both must be present and disagree for
    a finding to be emitted.
    """
    status_custody = snapshot.get("custody_state")
    watchdog = snapshot.get("watchdog")
    if not isinstance(watchdog, dict):
        return None
    watchdog_custody = watchdog.get("custody_state")
    if not isinstance(status_custody, str) or not status_custody:
        return None
    if not isinstance(watchdog_custody, str) or not watchdog_custody:
        return None
    if status_custody == watchdog_custody:
        return None
    return _finding(
        _AUDITOR_CUSTODY_DISAGREEMENT_CODE,
        layer=_SEMANTIC_CUSTODY_LAYER,
        status="error",
        severity="error",
        message=(
            f"Watchdog custody '{watchdog_custody}' disagrees with "
            f"status snapshot custody '{status_custody}'."
        ),
        recommendation="auditor_escalate_to_human",
        watchdog_custody=watchdog_custody,
        status_custody=status_custody,
    )


def _auditor_recursion_finding(
    *,
    brief: dict[str, Any],
    incident: dict[str, Any],
    current_target: dict[str, Any],
    audit_history: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not audit_history:
        return None

    current_non_ok = _auditor_recursion_non_ok_findings(findings)
    current_fingerprints = _auditor_recursion_fingerprint_map(current_non_ok)
    if not current_fingerprints:
        return None

    current_next_expected_event = _normalized_text(
        brief.get("next_expected_event") or incident.get("next_expected_event")
    )
    repeated_fingerprint_keys: set[str] = set()
    repeat_count = 1

    for historical_audit in reversed(audit_history):
        historical_fingerprints = _auditor_recursion_fingerprint_map(
            _auditor_recursion_history_findings(historical_audit)
        )
        shared_fingerprint_keys = set(current_fingerprints).intersection(historical_fingerprints)
        if not shared_fingerprint_keys:
            break

        historical_next_expected_event = _audit_history_next_expected_event(historical_audit)
        if (
            current_next_expected_event
            and historical_next_expected_event
            and current_next_expected_event != historical_next_expected_event
            and not _l2_fix_claimed(brief, incident)
        ):
            break

        repeated_fingerprint_keys.update(shared_fingerprint_keys)
        repeat_count += 1

    cycle_detected = repeat_count >= 2 and bool(repeated_fingerprint_keys)
    post_l2_fix_recurrence = cycle_detected and _l2_fix_claimed(brief, incident)
    stale_evidence_detected = _auditor_stale_evidence_detected(
        current_non_ok,
        current_target=current_target,
    )

    if not cycle_detected and not post_l2_fix_recurrence:
        return None

    return _finding(
        "auditor_recursion_guard",
        layer="auditor_recursion",
        status="error",
        severity="error",
        message="Repeated non-ok auditor findings indicate a self-reinforcing L3 cycle.",
        recommendation="auditor_escalate_to_human",
        cycle_detected=cycle_detected,
        post_l2_fix_recurrence=post_l2_fix_recurrence,
        stale_evidence_detected=stale_evidence_detected,
        repeat_count=repeat_count,
        repeated_findings=sorted(
            current_fingerprints[fingerprint_key] for fingerprint_key in repeated_fingerprint_keys
        ),
    )


def _diagnosis_summary(brief: dict[str, Any], unhealthy: list[dict[str, Any]]) -> str:
    if not unhealthy:
        return f"Audit completed for {brief.get('incident_id') or 'incident'} with no blocking reconciler findings."
    summary_bits = [f"{finding['layer']}:{finding['code']}" for finding in unhealthy[:3]]
    return (
        f"Audit found {len(unhealthy)} blocking layer(s) for "
        f"{brief.get('incident_id') or 'incident'}: {', '.join(summary_bits)}."
    )


def _next_expected_event(
    primary: dict[str, Any] | None,
    brief: dict[str, Any],
    incident: dict[str, Any],
    problem: dict[str, Any],
) -> str | None:
    if primary is not None:
        recommendation = primary.get("recommendation")
        return recommendation if isinstance(recommendation, str) and recommendation else None
    if (
        problem
        and problem.get("status") == "open"
        and int(problem.get("occurrence_count") or 0) >= 2
    ):
        return "github_sync.publish"
    candidate = brief.get("next_expected_event") or incident.get("next_expected_event")
    return candidate if isinstance(candidate, str) and candidate else None


def github_sync_publication_due(incident_audit: dict[str, Any]) -> bool:
    """Return whether an audit requires GitHub publication as an independent action."""
    audit_complete = (
        incident_audit.get("audit_complete")
        if isinstance(incident_audit.get("audit_complete"), dict)
        else {}
    )
    raw_handoff = audit_complete.get("next_expected_event") or incident_audit.get(
        "next_expected_event"
    )
    if raw_handoff == "github_sync.publish":
        return True
    findings = incident_audit.get("findings")
    if not isinstance(findings, list):
        return False
    return any(
        isinstance(finding, dict)
        and finding.get("recommendation") == "github_sync.publish"
        for finding in findings
    )


def _requires_human_escalation(findings: list[dict[str, Any]]) -> bool:
    return any(finding.get("recommendation") == "auditor_escalate_to_human" for finding in findings)


def _primary_finding(findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not findings:
        return None
    severity_rank = {"error": 0, "warn": 1, "ok": 2}
    layer_rank = {
        "auditor_recursion": 0,
        "reconciler": 1,
        "resolver_confidence": 2,
        "resolver_semantics": 3,
        "semantic_custody": 4,
        "watchdog": 5,
        "stale_claim": 6,
        "missing_evidence": 7,
        "meta_repair": 8,
        "immediate_repair": 9,
        "install_sync": 10,
        "github_sync": 11,
        "recurrence": 12,
        "project_progress": 13,
        "live_process": 14,
    }
    return sorted(
        findings,
        key=lambda item: (
            severity_rank.get(item["severity"], 99),
            layer_rank.get(item["layer"], len(_LAYER_ORDER)),
        ),
    )[0]


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _auditor_recursion_non_ok_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        finding
        for finding in findings
        if finding.get("status") != "ok" and finding.get("layer") != "auditor_recursion"
    ]


def _auditor_recursion_history_findings(history_entry: dict[str, Any]) -> list[dict[str, Any]]:
    findings = history_entry.get("findings")
    if not isinstance(findings, list):
        return []
    return [
        finding
        for finding in findings
        if isinstance(finding, dict)
        and finding.get("status") != "ok"
        and finding.get("layer") != "auditor_recursion"
    ]


def _auditor_recursion_fingerprint_map(findings: list[dict[str, Any]]) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for finding in findings:
        stable_payload = _auditor_recursion_stable_value(finding)
        fingerprint = json.dumps(stable_payload, sort_keys=True, separators=(",", ":"))
        fingerprints[fingerprint] = _auditor_recursion_label(finding)
    return fingerprints


def _auditor_recursion_stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        stable_items: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                continue
            if key in _AUDITOR_RECURSION_VOLATILE_KEYS:
                continue
            if key.endswith("_at") or key.endswith("_ts") or "timestamp" in key:
                continue
            stable_items[key] = _auditor_recursion_stable_value(value[key])
        return stable_items
    if isinstance(value, list):
        return [_auditor_recursion_stable_value(item) for item in value]
    return value


def _auditor_recursion_label(finding: dict[str, Any]) -> str:
    layer = _normalized_text(finding.get("layer")) or "unknown"
    code = _normalized_text(finding.get("code")) or "unknown"
    return f"{layer}:{code}"


def _audit_history_next_expected_event(history_entry: dict[str, Any]) -> str:
    audit_complete = history_entry.get("audit_complete")
    if not isinstance(audit_complete, dict):
        return ""
    return _normalized_text(audit_complete.get("next_expected_event"))


def _l2_fix_claimed(brief: dict[str, Any], incident: dict[str, Any]) -> bool:
    placeholders = _incident_placeholders(brief, incident)
    shipped_fix = _normalized_text(placeholders.get("shipped_fix")).lower()
    install_freshness = _normalized_text(placeholders.get("install_freshness")).lower()
    brief_outcome = _normalized_text(brief.get("outcome")).lower()
    return (
        brief_outcome in _RECONCILER_RECOVERED_OUTCOMES
        or shipped_fix == "fixed"
        or install_freshness == "fresh"
    )


def _auditor_stale_evidence_detected(
    findings: list[dict[str, Any]],
    *,
    current_target: dict[str, Any],
) -> bool:
    stale_evidence = current_target.get("stale_evidence")
    if isinstance(stale_evidence, list) and stale_evidence:
        return True
    return any(_normalized_text(finding.get("code")) in _AUDITOR_RECURSION_STALE_CODES for finding in findings)


def _resolve_incident(incidents: list[dict[str, Any]], incident_id: Any) -> dict[str, Any]:
    if not isinstance(incident_id, str):
        return {}
    for incident in incidents:
        if incident.get("incident_id") == incident_id:
            return incident
    return {}


def _resolve_problem(problems: list[dict[str, Any]], problem_ids: Any) -> dict[str, Any]:
    if not isinstance(problem_ids, list):
        return {}
    problem_id_set = {problem_id for problem_id in problem_ids if isinstance(problem_id, str)}
    for problem in problems:
        if problem.get("problem_id") in problem_id_set:
            return problem
    return {}


def _matching_process(
    snapshot: dict[str, Any],
    *,
    actor: str,
    session_ids: list[str],
) -> dict[str, Any] | None:
    processes = snapshot.get("processes")
    if not isinstance(processes, list):
        return None
    for process in processes:
        if not isinstance(process, dict):
            continue
        if process.get("actor") != actor:
            continue
        session_id = process.get("session_id")
        if not session_ids or session_id in session_ids:
            return process
    return None


def _is_stale(timestamp: Any, now: str | None, threshold: timedelta) -> bool:
    if not isinstance(timestamp, str) or not isinstance(now, str):
        return False
    observed = _parse_timestamp(timestamp)
    current = _parse_timestamp(now)
    if observed is None or current is None:
        return False
    return current - observed > threshold


def _parse_timestamp(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _finding(
    code: str,
    *,
    layer: str,
    status: str,
    severity: str,
    message: str,
    recommendation: str | None,
    **details: Any,
) -> dict[str, Any]:
    finding = {
        "code": code,
        "layer": layer,
        "status": status,
        "severity": severity,
        "message": message,
        "recommendation": recommendation,
    }
    finding.update(details)
    return finding


# ── Auditor completion evidence ───────────────────────────────────────


@dataclass(frozen=True)
class SixHourAuditorCompletionEvidence:
    """Structured 6h auditor completion evidence.

    Captures the audited window, findings, next expected event,
    repair dispatch refs, escalation verdicts, and structured
    findings for missing repair verdicts or stale repair-data
    in auditor inputs.

    Downstream custody/status consumers use this evidence to decide
    whether the 6h audit cycle produced a trustworthy completion.
    """

    contract_id: str = _AUDITOR_6H_COMPLETION_ROW_ID
    boundary_id: str = _AUDITOR_6H_COMPLETION_BOUNDARY_ID
    audited_window_hours: float = 6.0
    audit_timestamp: str = ""
    finding_count: int = 0
    highest_severity: str = "ok"
    next_expected_event: str = ""
    outcome: str = ""
    repair_dispatch_count: int = 0
    repair_dispatch_refs: tuple[str, ...] = ()
    escalation_verdict_count: int = 0
    escalation_verdict_refs: tuple[str, ...] = ()
    drift_findings: tuple[dict[str, Any], ...] = ()
    missing_repair_verdict_findings: tuple[dict[str, Any], ...] = ()
    stale_repair_data_findings: tuple[dict[str, Any], ...] = ()
    evidence_timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "boundary_id": self.boundary_id,
            "audited_window_hours": self.audited_window_hours,
            "audit_timestamp": self.audit_timestamp,
            "finding_count": self.finding_count,
            "highest_severity": self.highest_severity,
            "next_expected_event": self.next_expected_event,
            "outcome": self.outcome,
            "repair_dispatch_count": self.repair_dispatch_count,
            "repair_dispatch_refs": list(self.repair_dispatch_refs),
            "escalation_verdict_count": self.escalation_verdict_count,
            "escalation_verdict_refs": list(self.escalation_verdict_refs),
            "drift_findings": [dict(finding) for finding in self.drift_findings],
            "missing_repair_verdict_findings": [
                dict(finding) for finding in self.missing_repair_verdict_findings
            ],
            "stale_repair_data_findings": [
                dict(finding) for finding in self.stale_repair_data_findings
            ],
            "evidence_timestamp": self.evidence_timestamp,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, Any]
    ) -> "SixHourAuditorCompletionEvidence":
        return cls(
            contract_id=_auditor_evidence_text(
                payload.get("contract_id")
            )
            or _AUDITOR_6H_COMPLETION_ROW_ID,
            boundary_id=_auditor_evidence_text(
                payload.get("boundary_id")
            )
            or _AUDITOR_6H_COMPLETION_BOUNDARY_ID,
            audited_window_hours=float(payload.get("audited_window_hours", 6.0)),
            audit_timestamp=_auditor_evidence_text(payload.get("audit_timestamp")),
            finding_count=int(payload.get("finding_count", 0)),
            highest_severity=_auditor_evidence_text(payload.get("highest_severity"))
            or "ok",
            next_expected_event=_auditor_evidence_text(
                payload.get("next_expected_event")
            ),
            outcome=_auditor_evidence_text(payload.get("outcome")),
            repair_dispatch_count=int(payload.get("repair_dispatch_count", 0)),
            repair_dispatch_refs=tuple(
                _auditor_evidence_text(item)
                for item in _auditor_evidence_list(payload.get("repair_dispatch_refs"))
                if _auditor_evidence_text(item)
            ),
            escalation_verdict_count=int(
                payload.get("escalation_verdict_count", 0)
            ),
            escalation_verdict_refs=tuple(
                _auditor_evidence_text(item)
                for item in _auditor_evidence_list(
                    payload.get("escalation_verdict_refs")
                )
                if _auditor_evidence_text(item)
            ),
            drift_findings=tuple(
                dict(item)
                for item in _auditor_evidence_list(payload.get("drift_findings"))
                if isinstance(item, dict)
            ),
            missing_repair_verdict_findings=tuple(
                dict(item)
                for item in _auditor_evidence_list(
                    payload.get("missing_repair_verdict_findings")
                )
                if isinstance(item, dict)
            ),
            stale_repair_data_findings=tuple(
                dict(item)
                for item in _auditor_evidence_list(
                    payload.get("stale_repair_data_findings")
                )
                if isinstance(item, dict)
            ),
            evidence_timestamp=_auditor_evidence_text(
                payload.get("evidence_timestamp")
            ),
        )


def _auditor_evidence_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _auditor_evidence_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _auditor_evidence_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _auditor_utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _primary_severity(findings: list[dict[str, Any]]) -> str:
    rank = {"error": 0, "warn": 1, "ok": 2}
    best = "ok"
    best_rank = 99
    for finding in findings:
        severity = _auditor_evidence_text(finding.get("severity")) or "ok"
        r = rank.get(severity, 99)
        if r < best_rank:
            best_rank = r
            best = severity
    return best


def _extract_missing_repair_verdict_findings(
    audit_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract structured findings for missing repair verdicts in auditor inputs.

    A missing repair verdict means the auditor's input layer (immediate_repair
    or meta_repair) produced a non-ok finding whose code indicates missing
    evidence — the repair system did not produce a verdict the auditor can trust.
    """
    extracted: list[dict[str, Any]] = []
    for finding in audit_findings:
        if not isinstance(finding, dict):
            continue
        layer = _auditor_evidence_text(finding.get("layer"))
        status = _auditor_evidence_text(finding.get("status"))
        code = _auditor_evidence_text(finding.get("code"))
        if status == "ok":
            continue
        if layer not in ("immediate_repair", "meta_repair"):
            continue
        if "missing" not in code and layer not in (
            "immediate_repair",
            "meta_repair",
        ):
            continue
        # Only treat as missing-verdict when the finding explicitly
        # indicates missing evidence or missing activity.
        if "missing" in code or "absent" in code:
            extracted.append(
                {
                    "layer": layer,
                    "code": code,
                    "status": status,
                    "severity": _auditor_evidence_text(finding.get("severity")),
                    "message": _auditor_evidence_text(finding.get("message")),
                    "recommendation": _auditor_evidence_text(
                        finding.get("recommendation")
                    ),
                    "finding_kind": "missing_repair_verdict",
                }
            )
    return extracted


def _extract_drift_findings(
    audit_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    for finding in audit_findings:
        if not isinstance(finding, dict):
            continue
        if _auditor_evidence_text(finding.get("code")) != "DRIFT_DETECTED":
            continue
        extracted.append(
            {
                "layer": _auditor_evidence_text(finding.get("layer")),
                "code": "DRIFT_DETECTED",
                "source_pair": _auditor_evidence_text(finding.get("source_pair")),
                "contradiction": _auditor_evidence_text(finding.get("contradiction")),
                "recommendation": _auditor_evidence_text(finding.get("recommendation")),
                "observed": _auditor_evidence_mapping(finding.get("observed")),
                "expected": _auditor_evidence_mapping(finding.get("expected")),
            }
        )
    return extracted


def _extract_stale_repair_data_findings(
    audit_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract structured findings for stale repair-data in auditor inputs.

    Stale repair-data means the repair layer produced a finding indicating
    the repair process itself has been running too long or its data is
    older than the configured threshold.
    """
    extracted: list[dict[str, Any]] = []
    for finding in audit_findings:
        if not isinstance(finding, dict):
            continue
        layer = _auditor_evidence_text(finding.get("layer"))
        status = _auditor_evidence_text(finding.get("status"))
        code = _auditor_evidence_text(finding.get("code"))
        if status == "ok":
            continue
        if layer not in ("immediate_repair", "meta_repair"):
            continue
        if "stale" in code or "running_stale" in code:
            extracted.append(
                {
                    "layer": layer,
                    "code": code,
                    "status": status,
                    "severity": _auditor_evidence_text(finding.get("severity")),
                    "message": _auditor_evidence_text(finding.get("message")),
                    "recommendation": _auditor_evidence_text(
                        finding.get("recommendation")
                    ),
                    "finding_kind": "stale_repair_data",
                    "observed_at": _auditor_evidence_text(finding.get("observed_at")),
                }
            )
    return extracted


def build_auditor_completion_evidence(
    *,
    audit_findings: list[dict[str, Any]] | None = None,
    audit_outcome: str = "",
    next_expected_event: str = "",
    audited_window_hours: float = 6.0,
    repair_dispatch_refs: tuple[str, ...] = (),
    timestamp: str | None = None,
) -> SixHourAuditorCompletionEvidence:
    """Build structured 6h auditor completion evidence from audit output.

    Parameters
    ----------
    audit_findings:
        The per-incident/per-plan audit findings produced by
        :func:`audit_projection_input` or equivalent.
    audit_outcome:
        The canonical audit outcome (``audit_cycle_complete``,
        ``escalated``, ``auditor_human_escalation``).
    next_expected_event:
        The next expected event after audit completion.
    audited_window_hours:
        Size of the audit window in hours.
    repair_dispatch_refs:
        Paths/refs to repair requests dispatched by the auditor.
    timestamp:
        ISO-8601 evidence timestamp (defaults to now).
    """
    findings = list(audit_findings) if audit_findings is not None else []
    evidence_ts = timestamp or _auditor_utc_now_iso()

    # Repair dispatch consumes a historical evidence window.  A zero,
    # negative, NaN, or infinite window is only a probe; it cannot establish
    # health and must not produce a successful empty audit.
    valid_window = math.isfinite(audited_window_hours) and audited_window_hours > 0
    if not valid_window:
        return SixHourAuditorCompletionEvidence(
            audited_window_hours=audited_window_hours,
            audit_timestamp=evidence_ts,
            finding_count=len(findings),
            highest_severity="error",
            next_expected_event="auditor.retry_with_valid_evidence_window",
            outcome="invalid_evidence_window",
            repair_dispatch_count=0,
            repair_dispatch_refs=(),
            evidence_timestamp=evidence_ts,
        )

    missing_repair_verdict = _extract_missing_repair_verdict_findings(findings)
    drift_findings = _extract_drift_findings(findings)
    stale_repair_data = _extract_stale_repair_data_findings(findings)

    return SixHourAuditorCompletionEvidence(
        audited_window_hours=audited_window_hours,
        audit_timestamp=evidence_ts,
        finding_count=len(findings),
        highest_severity=_primary_severity(findings),
        next_expected_event=next_expected_event or "",
        outcome=audit_outcome or "",
        repair_dispatch_count=len(repair_dispatch_refs),
        repair_dispatch_refs=repair_dispatch_refs,
        escalation_verdict_count=sum(
            1
            for finding in findings
            if _auditor_evidence_text(finding.get("recommendation"))
            == "auditor_escalate_to_human"
        ),
        escalation_verdict_refs=tuple(
            f"{_auditor_evidence_text(finding.get('layer',''))}:"
            f"{_auditor_evidence_text(finding.get('code',''))}"
            for finding in findings
            if _auditor_evidence_text(finding.get("recommendation"))
            == "auditor_escalate_to_human"
        ),
        drift_findings=tuple(drift_findings),
        missing_repair_verdict_findings=tuple(missing_repair_verdict),
        stale_repair_data_findings=tuple(stale_repair_data),
        evidence_timestamp=evidence_ts,
    )


def save_auditor_completion_evidence(
    path: str | Path,
    evidence: SixHourAuditorCompletionEvidence,
    *,
    redactor: Callable[[str], str] | None = None,
    sidecar_dir: str | Path | None = None,
    session: str = "",
    plan: str = "",
) -> dict[str, Any]:
    """Validate, redact, and persist auditor completion evidence to *path*.

    The evidence is written as a JSON artifact so downstream custody/status
    consumers can read it without recomputing the audit mapping.
    """
    prepared = evidence.to_dict()
    if redactor is not None:
        prepared = _redact_auditor_evidence_payload(prepared, redactor)
    _auditor_atomic_write_json(path, prepared)
    if sidecar_dir is not None:
        append_incident_record(
            sidecar_dir,
            {
                "session": session,
                "kind": "auditor_6h_completion",
                "summary": evidence.outcome or "audit_cycle_complete",
                "plan": plan,
                "record_path": str(path),
                "next_expected_event": evidence.next_expected_event,
                "repair_dispatch_count": evidence.repair_dispatch_count,
                "escalation_verdict_refs": list(evidence.escalation_verdict_refs),
                "drift_findings": [dict(finding) for finding in evidence.drift_findings],
                "recorded_at": evidence.evidence_timestamp,
            },
        )
    return prepared


def _redact_auditor_evidence_payload(
    payload: dict[str, Any],
    redactor: Callable[[str], str],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            result[key] = redactor(value)
        elif isinstance(value, list):
            result[key] = [
                redactor(item) if isinstance(item, str) else item for item in value
            ]
        elif isinstance(value, dict):
            result[key] = _redact_auditor_evidence_payload(value, redactor)
        else:
            result[key] = value
    return result


def _auditor_atomic_write_json(path: str | Path, payload: dict[str, Any]) -> None:
    """Write *payload* to *path* atomically (write-then-rename)."""
    import tempfile

    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        suffix=".json", prefix="auditor-evidence-", dir=str(dest.parent)
    )
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        Path(tmp).rename(dest)
    except Exception:
        try:
            Path(tmp).unlink(missing_ok=True)
        except OSError:
            pass
        raise


__all__ = [
    "AuditorConfig",
    "SixHourAuditorCompletionEvidence",
    "audit_incident",
    "audit_projection_input",
    "build_audit_input",
    "build_auditor_completion_evidence",
    "save_auditor_completion_evidence",
]
