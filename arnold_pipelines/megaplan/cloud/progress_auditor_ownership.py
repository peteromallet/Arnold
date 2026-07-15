"""Bounded existing-owner evidence for the six-hour progress auditor.

The auditor is allowed to observe managed-agent custody, but its gather phase
must never create or adopt custody.  This module therefore only reads durable
manifests, validates their observed process liveness, and reports how strongly
their stable identifiers overlap the repair objective in an audit finding.

Prose overlap is deliberately insufficient to suppress a launch.  A healthy
owner is considered plausibly aligned only when a stable objective identifier
matches, or when both the canonical session and plan match.  Ambiguity and
missing health evidence remain explicit and actionable.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable

from arnold_pipelines.megaplan.cloud.redact import redact_text
from arnold_pipelines.megaplan.managed_agent import managed_run_roots, observed_status


OWNERSHIP_SCHEMA = "arnold-progress-auditor-existing-ownership-v1"
ACTIVE_STATUSES = frozenset({"reserved", "launching", "running", "adopting"})
FAILED_STATUSES = frozenset(
    {"failed", "interrupted", "cancelled", "superseded", "unknown"}
)
NON_REPAIR_RUN_KINDS = frozenset({"automatic_progress_audit_agent"})
NON_REPAIR_TASK_KINDS = frozenset({"review"})
DEFAULT_STALE_AFTER = timedelta(hours=6)
MAX_CANDIDATES = 25

_STRONG_IDENTIFIER_FIELDS = (
    "blocker_id",
    "repair_request_id",
    "audit_escalation_id",
    "incident_id",
    "problem_id",
    "target_id",
    "custody_id",
    "correlation_id",
    "source_record_id",
)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")
_STOPWORDS = frozenset(
    {
        "agent",
        "arnold",
        "audit",
        "auditor",
        "automatic",
        "cloud",
        "existing",
        "failed",
        "progress",
        "repair",
        "running",
        "session",
        "subagent",
        "the",
        "this",
        "with",
    }
)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _parse_time(value: object) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _add_identifier(target: dict[str, set[str]], key: str, value: object) -> None:
    if isinstance(value, list):
        for item in value:
            _add_identifier(target, key, item)
        return
    token = _text(value)
    if token:
        target.setdefault(key, set()).add(token)


def _finding_identifiers(finding: Mapping[str, Any]) -> dict[str, set[str]]:
    identifiers: dict[str, set[str]] = {}
    _add_identifier(identifiers, "session", finding.get("session"))
    _add_identifier(identifiers, "plan", finding.get("plan"))

    blocks = [
        finding,
        _mapping(finding.get("session_header")),
        _mapping(finding.get("current_target")),
        _mapping(finding.get("repair_custody_summary")),
        _mapping(finding.get("deterministic_superfixer_evidence")),
        _mapping(finding.get("incident_brief")),
        _mapping(finding.get("incident_projection")),
        _mapping(finding.get("problem_projection")),
        _mapping(finding.get("l3_escalation_gate")),
    ]
    aliases = {
        "session": ("session", "cloud_session"),
        "plan": ("plan", "current_plan", "current_plan_name", "audit_finding"),
        "blocker_id": ("blocker_id",),
        "repair_request_id": (
            "repair_request_id",
            "accepted_unclaimed_request_ids",
            "claim_alert_request_ids",
        ),
        "audit_escalation_id": ("audit_escalation_id", "escalation_id"),
        "incident_id": ("incident_id",),
        "problem_id": ("problem_id",),
        "target_id": ("target_id",),
        "custody_id": ("custody_id",),
        "correlation_id": ("correlation_id",),
        "source_record_id": ("source_record_id",),
    }
    for block in blocks:
        for canonical, fields in aliases.items():
            for field in fields:
                _add_identifier(identifiers, canonical, block.get(field))
    return identifiers


def _manifest_identifiers(manifest: Mapping[str, Any]) -> dict[str, set[str]]:
    identifiers: dict[str, set[str]] = {}
    blocks = [
        manifest,
        _mapping(manifest.get("links")),
        _mapping(manifest.get("repair_claim")),
        _mapping(manifest.get("launch_provenance")),
        _mapping(manifest.get("upstream_custody")),
        _mapping(manifest.get("resident_delegation")),
    ]
    aliases = {
        "session": ("session", "cloud_session"),
        "plan": ("plan", "current_plan", "current_plan_name", "audit_finding"),
        "blocker_id": ("blocker_id",),
        "repair_request_id": ("repair_request_id",),
        "audit_escalation_id": ("audit_escalation_id", "escalation_id"),
        "incident_id": ("incident_id",),
        "problem_id": ("problem_id",),
        "target_id": ("target_id",),
        "custody_id": ("custody_id",),
        "correlation_id": ("correlation_id",),
        "source_record_id": ("source_record_id",),
    }
    for block in blocks:
        for canonical, fields in aliases.items():
            for field in fields:
                _add_identifier(identifiers, canonical, block.get(field))
    return identifiers


def _identifier_evidence(identifiers: Mapping[str, set[str]]) -> dict[str, list[str]]:
    return {
        key: sorted(values)
        for key, values in sorted(identifiers.items())
        if values
    }


def _objective_fingerprint(identifiers: Mapping[str, set[str]]) -> str:
    encoded = json.dumps(
        _identifier_evidence(identifiers),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _objective_text(manifest: Mapping[str, Any]) -> str:
    value = _text(manifest.get("description") or manifest.get("command_display"))
    return redact_text(value)[:240]


def _finding_text(finding: Mapping[str, Any]) -> str:
    reasons = finding.get("reasons") if isinstance(finding.get("reasons"), list) else []
    return " ".join(
        [
            _text(finding.get("session")),
            _text(finding.get("plan")),
            *[_text(reason) for reason in reasons],
        ]
    )


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(value.casefold())
        if token not in _STOPWORDS
    }


def _match_assessment(
    finding_ids: Mapping[str, set[str]],
    manifest_ids: Mapping[str, set[str]],
    *,
    finding_text: str,
    objective_text: str,
) -> dict[str, Any]:
    matched: dict[str, list[str]] = {}
    for key in (*_STRONG_IDENTIFIER_FIELDS, "session", "plan"):
        overlap = set(finding_ids.get(key, set())) & set(manifest_ids.get(key, set()))
        if overlap:
            matched[key] = sorted(overlap)
    strong = [field for field in _STRONG_IDENTIFIER_FIELDS if field in matched]
    session_and_plan = "session" in matched and "plan" in matched
    if strong or session_and_plan:
        return {
            "classification": "exact",
            "basis": "stable_identifier_match" if strong else "session_and_plan_match",
            "matched_identifiers": matched,
            "text_overlap": [],
        }
    if "session" in matched or "plan" in matched:
        return {
            "classification": "ambiguous",
            "basis": "session_or_plan_only",
            "matched_identifiers": matched,
            "text_overlap": [],
        }
    overlap = sorted(_tokens(finding_text) & _tokens(objective_text))
    if len(overlap) >= 2:
        return {
            "classification": "ambiguous",
            "basis": "prose_overlap_without_stable_identifier",
            "matched_identifiers": {},
            "text_overlap": overlap[:12],
        }
    return {
        "classification": "unrelated",
        "basis": "no_objective_overlap",
        "matched_identifiers": {},
        "text_overlap": overlap[:12],
    }


def _health_assessment(
    manifest: Mapping[str, Any],
    manifest_path: Path,
    *,
    now: datetime,
    stale_after: timedelta,
    status_probe: Callable[[Mapping[str, Any], Path], tuple[str, bool]],
) -> dict[str, Any]:
    persisted = _text(manifest.get("status") or "unknown").casefold()
    try:
        observed, live = status_probe(manifest, manifest_path)
    except (OSError, ValueError, TypeError):
        observed, live = "unknown", False
    observed = _text(observed or "unknown").casefold()
    anchor = _parse_time(
        manifest.get("updated_at")
        or manifest.get("worker_started_at")
        or manifest.get("started_at")
        or manifest.get("created_at")
    )
    age_seconds = int((now - anchor).total_seconds()) if anchor else None
    stale_clock = bool(age_seconds is not None and age_seconds > stale_after.total_seconds())
    if persisted in ACTIVE_STATUSES and live and not stale_clock:
        classification = "healthy"
    elif persisted in ACTIVE_STATUSES and live and stale_clock:
        classification = "uncertain_stale_manifest"
    elif persisted in ACTIVE_STATUSES:
        classification = "stale"
    elif persisted in FAILED_STATUSES or observed in FAILED_STATUSES:
        classification = "failed"
    else:
        classification = "terminal"
    return {
        "classification": classification,
        "persisted_status": persisted,
        "observed_status": observed,
        "live": bool(live),
        "evidence_at": anchor.isoformat() if anchor else None,
        "evidence_age_seconds": age_seconds,
    }


def _direction_assessment(
    manifest: Mapping[str, Any],
    *,
    match: Mapping[str, Any],
    health: Mapping[str, Any],
) -> dict[str, Any]:
    task_kind = _text(manifest.get("task_kind")).casefold()
    run_kind = _text(manifest.get("run_kind")).casefold()
    explicit = _text(
        manifest.get("direction_assessment")
        or _mapping(manifest.get("progress")).get("direction")
        or _mapping(manifest.get("links")).get("direction")
    ).casefold()
    if explicit in {"wrong", "off_course", "off-course", "drifting", "blocked"}:
        classification = "wrong_direction"
        basis = "explicit_manifest_direction"
    elif run_kind in NON_REPAIR_RUN_KINDS or task_kind in NON_REPAIR_TASK_KINDS:
        classification = "wrong_scope"
        basis = "read_only_or_audit_run_does_not_own_repair"
    elif match.get("classification") != "exact":
        classification = "uncertain"
        basis = "stable_objective_match_missing"
    elif health.get("classification") != "healthy":
        classification = "uncertain"
        basis = "owner_health_not_current"
    else:
        classification = "plausibly_moving_right_direction"
        basis = "live_owner_with_stable_objective_match"
    return {"classification": classification, "basis": basis}


def _manifest_paths(*, project_root: Path, workspace_root: Path | None) -> list[Path]:
    paths: set[Path] = set()
    for root in managed_run_roots(
        project_root=project_root,
        workspace_root=workspace_root,
    ):
        if root.is_dir():
            paths.update(path.resolve() for path in root.glob("*/manifest.json"))
    return sorted(paths, key=lambda path: str(path))


def inspect_existing_ownership(
    finding: Mapping[str, Any],
    *,
    project_root: str | Path,
    workspace_root: str | Path | None = "/workspace",
    now: datetime | None = None,
    stale_after: timedelta = DEFAULT_STALE_AFTER,
    status_probe: Callable[[Mapping[str, Any], Path], tuple[str, bool]] = observed_status,
) -> dict[str, Any]:
    """Return bounded ownership evidence and a conservative launch decision."""

    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    finding_ids = _finding_identifiers(finding)
    finding_objective_text = _finding_text(finding)
    candidates: list[dict[str, Any]] = []
    malformed_count = 0
    for manifest_path in _manifest_paths(
        project_root=Path(project_root),
        workspace_root=Path(workspace_root) if workspace_root is not None else None,
    ):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            malformed_count += 1
            continue
        if not isinstance(manifest, dict):
            malformed_count += 1
            continue
        manifest_ids = _manifest_identifiers(manifest)
        objective_text = _objective_text(manifest)
        match = _match_assessment(
            finding_ids,
            manifest_ids,
            finding_text=finding_objective_text,
            objective_text=objective_text,
        )
        health = _health_assessment(
            manifest,
            manifest_path,
            now=observed_at,
            stale_after=stale_after,
            status_probe=status_probe,
        )
        direction = _direction_assessment(manifest, match=match, health=health)
        candidates.append(
            {
                "run_id": _text(manifest.get("run_id") or manifest_path.parent.name),
                "manifest_path": str(manifest_path),
                "run_kind": _text(manifest.get("run_kind")),
                "task_kind": _text(manifest.get("task_kind")),
                "objective_summary": objective_text,
                "task_sha256": _text(manifest.get("task_sha256")),
                "objective_fingerprint": _objective_fingerprint(manifest_ids),
                "objective_identifiers": _identifier_evidence(manifest_ids),
                "match": match,
                "health": health,
                "direction": direction,
            }
        )

    priority = {"exact": 0, "ambiguous": 1, "unrelated": 2}
    candidates.sort(
        key=lambda item: (
            priority.get(_text(_mapping(item.get("match")).get("classification")), 3),
            _text(item.get("run_id")),
        )
    )
    exact = [item for item in candidates if item["match"]["classification"] == "exact"]
    ambiguous = [
        item for item in candidates if item["match"]["classification"] == "ambiguous"
    ]
    healthy_aligned = [
        item
        for item in exact
        if item["health"]["classification"] == "healthy"
        and item["direction"]["classification"]
        == "plausibly_moving_right_direction"
    ]
    if len(healthy_aligned) == 1:
        decision = "existing_owner_no_new_launch"
        rationale = "one live owner has stable objective alignment and plausible repair direction"
        suppress = True
        actionable = False
    elif len(healthy_aligned) > 1:
        decision = "duplicate_exact_owners_detected"
        rationale = "multiple live owners already claim the same stable repair objective"
        suppress = True
        actionable = True
    elif exact:
        decision = "matching_owner_actionable"
        rationale = "matching custody is stale, failed, terminal, uncertain, or directionally wrong"
        suppress = False
        actionable = True
    elif ambiguous:
        decision = "ambiguous_overlap_requires_judgement"
        rationale = "overlap lacks enough stable identifiers to infer ownership"
        suppress = False
        actionable = True
    else:
        decision = "no_matching_agent"
        rationale = "no managed manifest owns the finding's repair objective"
        suppress = False
        actionable = True

    uncertainties: list[str] = []
    if not finding_ids:
        uncertainties.append("finding_has_no_stable_objective_identifiers")
    if malformed_count:
        uncertainties.append("malformed_manifests_omitted")
    if ambiguous:
        uncertainties.append("prose_or_partial_scope_overlap_not_treated_as_ownership")
    if any(item["health"]["classification"] == "uncertain_stale_manifest" for item in exact):
        uncertainties.append("live_process_has_stale_manifest_clock")

    return {
        "schema_version": OWNERSHIP_SCHEMA,
        "observed_at": observed_at.isoformat(),
        "objective": {
            "fingerprint": _objective_fingerprint(finding_ids),
            "identifiers": _identifier_evidence(finding_ids),
        },
        "decision": decision,
        "rationale": rationale,
        "suppress_new_repair_launch": suppress,
        "actionable": actionable,
        "matching_run_ids": [item["run_id"] for item in exact],
        "healthy_aligned_run_ids": [item["run_id"] for item in healthy_aligned],
        "ambiguous_run_ids": [item["run_id"] for item in ambiguous],
        "candidate_count": len(candidates),
        "malformed_manifest_count": malformed_count,
        "uncertainties": uncertainties,
        "candidates": candidates[:MAX_CANDIDATES],
        "candidates_omitted_count": max(0, len(candidates) - MAX_CANDIDATES),
    }


def launch_suppressed_by_existing_owner(finding: Mapping[str, Any]) -> bool:
    """Read only the audited ownership decision embedded in a finding."""

    ownership = _mapping(finding.get("existing_agent_ownership"))
    return bool(
        ownership.get("schema_version") == OWNERSHIP_SCHEMA
        and ownership.get("decision") == "existing_owner_no_new_launch"
        and ownership.get("suppress_new_repair_launch") is True
        and len(ownership.get("healthy_aligned_run_ids") or []) == 1
    )


__all__ = [
    "DEFAULT_STALE_AFTER",
    "OWNERSHIP_SCHEMA",
    "inspect_existing_ownership",
    "launch_suppressed_by_existing_owner",
]
