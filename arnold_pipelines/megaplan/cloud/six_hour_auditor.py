"""Pure incident-ledger auditor rules for the six-hour progress audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    brief = projection_input.get("brief") if isinstance(projection_input.get("brief"), dict) else {}
    incident = projection_input.get("incident") if isinstance(projection_input.get("incident"), dict) else {}
    problem = projection_input.get("problem") if isinstance(projection_input.get("problem"), dict) else {}
    snapshot = live_process_snapshot if isinstance(live_process_snapshot, dict) else {}
    cfg = config or AuditorConfig()
    effective_now = now or snapshot.get("now") or brief.get("last_timestamp") or incident.get("last_timestamp")

    findings = [
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

    unhealthy = [finding for finding in findings if finding["status"] != "ok"]
    primary = _primary_finding(unhealthy)
    diagnosis_summary = _diagnosis_summary(brief, unhealthy)
    next_expected_event = _next_expected_event(primary, brief, incident, problem)
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


def _primary_finding(findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not findings:
        return None
    severity_rank = {"error": 0, "warn": 1, "ok": 2}
    layer_rank = {
        "watchdog": 0,
        "stale_claim": 1,
        "missing_evidence": 2,
        "meta_repair": 3,
        "immediate_repair": 4,
        "install_sync": 5,
        "github_sync": 6,
        "recurrence": 7,
        "project_progress": 8,
        "live_process": 9,
    }
    return sorted(
        findings,
        key=lambda item: (
            severity_rank.get(item["severity"], 99),
            layer_rank.get(item["layer"], len(_LAYER_ORDER)),
        ),
    )[0]


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
