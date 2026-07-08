"""Pure incident-ledger auditor rules for the six-hour progress audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.incident.projection import build_brief, rebuild_projections

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


def build_audit_input(
    id_or_session: str,
    *,
    root: Path | str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Resolve the same bounded brief used by the CLI plus backing projections."""
    workspace_root = Path.cwd() if root is None else Path(root)
    projections = rebuild_projections(workspace_root)
    brief = build_brief(id_or_session, root=workspace_root, now=now)
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
        _github_sync_finding(problem, snapshot, effective_now),
        _live_process_finding(brief, incident, snapshot, effective_now),
        _stale_claim_finding(brief),
        _missing_evidence_finding(brief, incident, snapshot),
        _recurrence_finding(incident, problem),
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
    last_attempt = github_sync.get("last_attempt_at")
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
        "watchdog": 4,
        "stale_claim": 5,
        "missing_evidence": 6,
        "meta_repair": 7,
        "immediate_repair": 8,
        "install_sync": 9,
        "github_sync": 10,
        "recurrence": 11,
        "project_progress": 12,
        "live_process": 13,
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


__all__ = [
    "AuditorConfig",
    "audit_incident",
    "audit_projection_input",
    "build_audit_input",
]
