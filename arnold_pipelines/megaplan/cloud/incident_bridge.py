"""Bridge helpers that append M1 incident-ledger events from repair-actor boundaries.

This module is the single coexistence surface between the M1 event-sourced
incident ledger and the legacy repair-data subsystem.  Every helper is
explicit, append-only, and stateless — callers pass in the fields they
already own; the bridge normalises them into validated incident events and
appends them to the canonical ``events.jsonl`` journal.

Root resolution
---------------
Every helper accepts an optional *root* (``Path | str | None``).  When
supplied it is used as the workspace root; otherwise the current working
directory is used.  No side-file state is written — the bridge only
touches the incident ledger.

Event types covered
--------------------
* Watchdog detections / dispatches
* Meta-repair classification / attempts
* Install-sync applied / failed
* Repair retrigger
* Verification (verified_recovered)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

# ---------------------------------------------------------------------------
# Event-id prefix per helper so callers can trace provenance without a
# side-file registry.
# ---------------------------------------------------------------------------

_EVENT_PREFIXES = {
    "watchdog_detection": "wd",
    "watchdog_dispatch": "wdd",
    "immediate_repair_attempt": "ira",
    "managed_repair_claim": "mcl",
    "meta_repair_classification": "mrc",
    "meta_repair_attempt": "mra",
    "six_hour_auditor_diagnosis": "sha",
    "six_hour_auditor_audit_complete": "shc",
    "github_issue_published": "ghp",
    "github_issue_publish_failed": "ghf",
    "install_sync_applied": "isa",
    "install_sync_failed": "isf",
    "repair_retriggered": "rr",
    "verified_recovered": "vr",
}

_AUDIT_COMPLETE_OUTCOMES = {
    "recovered",
    "escalated",
    "audit_cycle_complete",
    "auditor_human_escalation",
}

_SIX_HOUR_AUDITOR_HANDOFFS = {
    None,
    "immediate_repair.repair_attempt",
    "meta_repair.repair_attempt",
    "github_sync.publish",
    "six_hour_auditor.diagnosis",
}

_GITHUB_SYNC_HANDOFFS = {
    None,
    "github_sync.publish",
    "github_sync.retry",
    "six_hour_auditor.diagnosis",
}


def _new_event_id(prefix: str) -> str:
    """Return a short, collision-resistant event id from *prefix* + random hex."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _resolve_root(root: Path | str | None) -> Path:
    """Resolve the workspace root: explicit *root* first, then cwd."""
    if root is not None:
        return Path(root)
    return Path.cwd()


def _append(root: Path | str | None, event: dict[str, Any]) -> dict[str, Any]:
    """Validate and append *event* to the incident ledger, return the envelope."""
    ledger = IncidentLedger(_resolve_root(root))
    return ledger.append_event(event)


def _require_handoff(next_expected_event: str | None, *, allowed: set[str | None], helper: str) -> None:
    if next_expected_event not in allowed:
        raise ValueError(
            f"{helper} next_expected_event must be one of "
            f"{sorted(value for value in allowed if value is not None)!r} or null"
        )


def _require_allowed_outcome(outcome: str, *, allowed: set[str], helper: str) -> None:
    if outcome not in allowed:
        raise ValueError(
            f"{helper} outcome must be one of {sorted(allowed)!r}"
        )


# ---------------------------------------------------------------------------
# Watchdog helpers
# ---------------------------------------------------------------------------


def append_watchdog_detection(
    *,
    incident_id: str,
    summary: str,
    outcome: str = "detected",
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    next_expected_event: str | None = "watchdog.dispatch",
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a watchdog *detection* event, e.g. failure-marker observed."""
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["watchdog_detection"]),
        "ts": _utc_now_iso(),
        "type": "detection",
        "actor": "watchdog",
        "scope": "repair_system",
        "outcome": outcome,
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": next_expected_event,
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


def append_watchdog_dispatch(
    *,
    incident_id: str,
    summary: str,
    outcome: str = "dispatched",
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    next_expected_event: str | None = "immediate_repair.repair_attempt",
    decision: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a watchdog *dispatch* event, e.g. repair-loop launched."""
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["watchdog_dispatch"]),
        "ts": _utc_now_iso(),
        "type": "dispatch",
        "actor": "watchdog",
        "scope": "repair_system",
        "outcome": outcome,
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": next_expected_event,
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if decision is not None:
        event["decision"] = decision
    return _append(root, event)


# ---------------------------------------------------------------------------
# Immediate-repair helper
# ---------------------------------------------------------------------------


def append_managed_repair_claim(
    *,
    incident_id: str,
    claim_id: str,
    actor: str,
    summary: str,
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    next_expected_event: str = "immediate_repair.repair_attempt",
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append the formal claim made by a real managed repair execution."""

    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["managed_repair_claim"]),
        "ts": _utc_now_iso(),
        "type": "claim.acquired",
        "actor": actor,
        "scope": "repair_system",
        "outcome": "acquired",
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": [],
        "trigger_event_id": None,
        "next_expected_event": next_expected_event,
        "deadline_ts": None,
        "incident_id": incident_id,
        "claim_id": claim_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


def append_immediate_repair_attempt(
    *,
    incident_id: str,
    summary: str,
    attempt_id: str,
    outcome: str = "attempted",
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    decision: dict[str, Any] | None = None,
    actions: list[dict[str, Any]] | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append an immediate-repair *attempt* event."""
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["immediate_repair_attempt"]),
        "ts": _utc_now_iso(),
        "type": "repair_attempt",
        "actor": "immediate_repair",
        "scope": "repair_system",
        "outcome": outcome,
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": "repair_attempt.verification",
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
        "attempt_id": attempt_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if decision is not None:
        event["decision"] = decision
    if actions is not None:
        event["actions"] = actions
    if links is not None:
        event["links"] = links
    return _append(root, event)


# ---------------------------------------------------------------------------
# Meta-repair helpers
# ---------------------------------------------------------------------------


def append_meta_repair_classification(
    *,
    incident_id: str,
    summary: str,
    outcome: str = "classified",
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    decision: dict[str, Any] | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a meta-repair *classification* event.

    The *decision* dict typically carries ``trigger``, ``confidence``, and
    ``evidence_summary`` keys produced by the meta-repair classifier.
    """
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["meta_repair_classification"]),
        "ts": _utc_now_iso(),
        "type": "meta_repair_classification",
        "actor": "meta_repair",
        "scope": "repair_system",
        "outcome": outcome,
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": "meta_repair.repair_attempt",
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if decision is not None:
        event["decision"] = decision
    if links is not None:
        event["links"] = links
    return _append(root, event)


def append_meta_repair_attempt(
    *,
    incident_id: str,
    summary: str,
    attempt_id: str,
    outcome: str = "attempted",
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    decision: dict[str, Any] | None = None,
    actions: list[dict[str, Any]] | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a meta-repair *attempt* event (the repair action itself)."""
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["meta_repair_attempt"]),
        "ts": _utc_now_iso(),
        "type": "repair_attempt",
        "actor": "meta_repair",
        "scope": "repair_system",
        "outcome": outcome,
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": "repair_attempt.verification",
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
        "attempt_id": attempt_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if decision is not None:
        event["decision"] = decision
    if actions is not None:
        event["actions"] = actions
    if links is not None:
        event["links"] = links
    return _append(root, event)


def append_six_hour_auditor_diagnosis(
    *,
    incident_id: str,
    summary: str,
    outcome: str = "diagnosed",
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    next_expected_event: str | None = "six_hour_auditor.audit_complete",
    decision: dict[str, Any] | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a six-hour auditor diagnosis event."""
    _require_handoff(
        next_expected_event,
        allowed=_SIX_HOUR_AUDITOR_HANDOFFS | {"six_hour_auditor.audit_complete"},
        helper="append_six_hour_auditor_diagnosis",
    )
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["six_hour_auditor_diagnosis"]),
        "ts": _utc_now_iso(),
        "type": "six_hour_auditor.diagnosis",
        "actor": "six_hour_auditor",
        "scope": "repair_system",
        "outcome": outcome,
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": next_expected_event,
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if decision is not None:
        event["decision"] = decision
    if links is not None:
        event["links"] = links
    return _append(root, event)


def append_six_hour_auditor_audit_complete(
    *,
    incident_id: str,
    summary: str,
    outcome: str,
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    next_expected_event: str | None = None,
    decision: dict[str, Any] | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a six-hour auditor audit_complete handoff event."""
    _require_allowed_outcome(
        outcome,
        allowed=_AUDIT_COMPLETE_OUTCOMES,
        helper="append_six_hour_auditor_audit_complete",
    )
    _require_handoff(
        next_expected_event,
        allowed=_SIX_HOUR_AUDITOR_HANDOFFS,
        helper="append_six_hour_auditor_audit_complete",
    )
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["six_hour_auditor_audit_complete"]),
        "ts": _utc_now_iso(),
        "type": "six_hour_auditor.audit_complete",
        "actor": "six_hour_auditor",
        "scope": "repair_system",
        "outcome": outcome,
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": next_expected_event,
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if decision is not None:
        event["decision"] = decision
    if links is not None:
        event["links"] = links
    return _append(root, event)


# ---------------------------------------------------------------------------
# Install-sync helpers
# ---------------------------------------------------------------------------


def append_install_sync_applied(
    *,
    incident_id: str,
    summary: str,
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append an *install_sync_applied* event providing runtime-identity evidence.

    The *evidence* list SHOULD include at least one item with
    ``{"kind": "runtime_identity", ...}`` so the projection can mark
    install freshness as ``"fresh"`` rather than ``"unverified"``.
    """
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["install_sync_applied"]),
        "ts": _utc_now_iso(),
        "type": "install_sync_applied",
        "actor": "install_sync",
        "scope": "repair_system",
        "outcome": "applied",
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": "repair_retrigger",
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


def append_install_sync_failed(
    *,
    incident_id: str,
    summary: str,
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append an *install_sync_failed* event.

    The *evidence* list SHOULD include at least one item with
    ``{"kind": "runtime_identity", ...}`` to avoid the
    ``install_sync_missing_runtime_identity`` integrity finding.
    """
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["install_sync_failed"]),
        "ts": _utc_now_iso(),
        "type": "install_sync_failed",
        "actor": "install_sync",
        "scope": "repair_system",
        "outcome": "failed",
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": "install_sync.retry",
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


# ---------------------------------------------------------------------------
# Repair retrigger helper
# ---------------------------------------------------------------------------


def append_repair_retriggered(
    *,
    incident_id: str,
    summary: str,
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a *repair_retriggered* event after install sync succeeded."""
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["repair_retriggered"]),
        "ts": _utc_now_iso(),
        "type": "repair_retriggered",
        "actor": "repair_system",
        "scope": "repair_system",
        "outcome": "retriggered",
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": "verified_recovered",
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


# ---------------------------------------------------------------------------
# Verification helper
# ---------------------------------------------------------------------------


def append_verified_recovered(
    *,
    incident_id: str,
    summary: str,
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a *verified_recovered* event confirming the fix chain is complete."""
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["verified_recovered"]),
        "ts": _utc_now_iso(),
        "type": "verified_recovered",
        "actor": "repair_system",
        "scope": "repair_system",
        "outcome": "recovered",
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": None,
        "deadline_ts": deadline_ts,
        "incident_id": incident_id,
    }
    if session_id:
        event["session_id"] = session_id
    if problem_id:
        event["problem_id"] = problem_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


def append_github_issue_published(
    *,
    summary: str,
    repo: str,
    number: int,
    url: str,
    action: str,
    incident_id: str | None = None,
    problem_id: str | None = None,
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    next_expected_event: str | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a successful GitHub issue publication event."""
    _require_handoff(
        next_expected_event,
        allowed=_GITHUB_SYNC_HANDOFFS,
        helper="append_github_issue_published",
    )
    event_evidence = list(evidence or [])
    event_evidence.append(
        {
            "kind": "github.issue",
            "repo": repo,
            "number": number,
            "url": url,
            "action": action,
        }
    )
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["github_issue_published"]),
        "ts": _utc_now_iso(),
        "type": "github_sync.issue_published",
        "actor": "github_sync",
        "scope": "repair_system",
        "outcome": "published",
        "summary": summary,
        "evidence": event_evidence,
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": next_expected_event,
        "deadline_ts": deadline_ts,
    }
    if incident_id:
        event["incident_id"] = incident_id
    if problem_id:
        event["problem_id"] = problem_id
    if session_id:
        event["session_id"] = session_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


def append_github_issue_publish_failed(
    *,
    summary: str,
    repo: str,
    action: str,
    error: str,
    incident_id: str | None = None,
    problem_id: str | None = None,
    evidence: list[Any] | None = None,
    session_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    next_expected_event: str | None = "github_sync.retry",
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a failed GitHub issue publication event."""
    _require_handoff(
        next_expected_event,
        allowed=_GITHUB_SYNC_HANDOFFS,
        helper="append_github_issue_publish_failed",
    )
    event_evidence = list(evidence or [])
    event_evidence.append(
        {
            "kind": "github.issue",
            "repo": repo,
            "action": action,
            "error": error,
        }
    )
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id(_EVENT_PREFIXES["github_issue_publish_failed"]),
        "ts": _utc_now_iso(),
        "type": "github_sync.issue_publish_failed",
        "actor": "github_sync",
        "scope": "repair_system",
        "outcome": "failed",
        "summary": summary,
        "evidence": event_evidence,
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": next_expected_event,
        "deadline_ts": deadline_ts,
    }
    if incident_id:
        event["incident_id"] = incident_id
    if problem_id:
        event["problem_id"] = problem_id
    if session_id:
        event["session_id"] = session_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


# ---------------------------------------------------------------------------
# Chain-runner helpers
# ---------------------------------------------------------------------------


def append_chain_lifecycle(
    *,
    summary: str,
    outcome: str = "milestone_event",
    evidence: list[Any] | None = None,
    incident_id: str | None = None,
    session_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    next_expected_event: str | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a chain-runner *lifecycle* event (milestone start, plan prepare, etc.).

    These events provide supervisor-chain provenance without any
    repair-dispatch side effects.  *outcome* is typically one of
    ``milestone_start``, ``plan_prepared``, ``driver_outcome``,
    ``milestone_complete``, ``chain_done``, or ``chain_stopped``.
    """
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id("cl"),
        "ts": _utc_now_iso(),
        "type": "chain_lifecycle",
        "actor": "chain_runner",
        "scope": "chain",
        "outcome": outcome,
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": next_expected_event,
        "deadline_ts": deadline_ts,
    }
    if incident_id:
        event["incident_id"] = incident_id
    if session_id:
        event["session_id"] = session_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


def append_dispatch_expired(
    *,
    summary: str,
    evidence: list[Any] | None = None,
    incident_id: str | None = None,
    session_id: str | None = None,
    parent_event_ids: list[str] | None = None,
    trigger_event_id: str | None = None,
    deadline_ts: str | None = None,
    links: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Append a *dispatch_expired* evidence event.

    The chain runner records that a milestone reached a terminal
    non-advance state (stopped, expired, timed out) but does **not**
    launch any repair actors.  The watchdog owns repair dispatch;
    this event is purely evidentiary.
    """
    event: dict[str, Any] = {
        "schema_version": 1,
        "event_id": _new_event_id("de"),
        "ts": _utc_now_iso(),
        "type": "dispatch_expired",
        "actor": "chain_runner",
        "scope": "chain",
        "outcome": "expired",
        "summary": summary,
        "evidence": evidence if evidence is not None else [],
        "parent_event_ids": parent_event_ids if parent_event_ids is not None else [],
        "trigger_event_id": trigger_event_id,
        "next_expected_event": "watchdog.dispatch",
        "deadline_ts": deadline_ts,
    }
    if incident_id:
        event["incident_id"] = incident_id
    if session_id:
        event["session_id"] = session_id
    if links is not None:
        event["links"] = links
    return _append(root, event)


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

__all__ = [
    "append_chain_lifecycle",
    "append_dispatch_expired",
    "append_github_issue_publish_failed",
    "append_github_issue_published",
    "append_immediate_repair_attempt",
    "append_install_sync_applied",
    "append_install_sync_failed",
    "append_managed_repair_claim",
    "append_meta_repair_attempt",
    "append_meta_repair_classification",
    "append_repair_retriggered",
    "append_six_hour_auditor_audit_complete",
    "append_six_hour_auditor_diagnosis",
    "append_verified_recovered",
    "append_watchdog_detection",
    "append_watchdog_dispatch",
]
