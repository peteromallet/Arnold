"""Policy for the six-hour auditor's separately authorized repair escalation.

The progress auditor remains a deterministic gather-and-report product.  This
module consumes a completed finding as an immutable observation and decides
whether a different, mutation-authorized controller may ask canonical repair
custody to launch a deep root-cause worker.

No function in this module launches a process or mutates plan/chain truth.
That separation is deliberate: a report finding is not repair authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from arnold_pipelines.megaplan.managed_agent import validate_automatic_managed_manifest


ESCALATION_SCHEMA = "arnold-progress-auditor-escalation-v1"
POLICY_VERSION = "l3-superfixer-v1"
DEEP_REPAIR_RUN_KIND = "automatic_root_cause_repair"
DEEP_REPAIR_MODEL = "gpt-5.6-sol"
DEEP_REPAIR_DIFFICULTY = 9
DEEP_REPAIR_REASONING = "high"

_MACHINE_ACTION_STATES = frozenset(
    {
        "MACHINE_ACTION_REQUIRED",
        "BROKEN_STATE_MACHINE",
        "REAL_IMPLEMENTATION_BLOCK",
        "RETRYABLE_EXECUTION_BLOCK",
    }
)
_INTENTIONAL_WAIT_STATES = frozenset(
    {
        "PAUSED",
        "HUMAN_ACTION_REQUIRED",
        "COMPLETED",
        "STALE_DERIVED_STATE",
    }
)
_TERMINAL_CHAIN_STATES = frozenset({"done", "complete", "completed"})
_TERMINAL_PLAN_STATES = frozenset({"done", "complete", "completed"})
_ACTIVE_MANAGED_STATUSES = frozenset({"reserved", "launching", "running", "adopting"})


@dataclass(frozen=True)
class EscalationPolicy:
    """Bounded policy applied after deterministic audit report assembly."""

    minimum_no_progress: timedelta = timedelta(hours=1)
    cooldown: timedelta = timedelta(hours=6)
    deterministic_failure_budget: int = 2
    launch_establishment_budget: int = 2
    global_concurrency_limit: int = 1
    per_session_concurrency_limit: int = 1
    recurrence_threshold: int = 2
    max_investigators: int = 3
    root_cause_owner_limit: int = 1
    execution_owner_limit: int = 1
    requested_difficulty: int = DEEP_REPAIR_DIFFICULTY
    child_difficulty_ceiling: int = DEEP_REPAIR_DIFFICULTY


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: object) -> str:
    return str(value or "").strip()


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


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


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def evidence_digest(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def semantic_cursor(finding: Mapping[str, Any]) -> dict[str, Any]:
    """Return the blocker-specific progress cursor used for re-verification."""

    chain = _mapping(_mapping(finding.get("chain_state_summary")).get("current"))
    log = _mapping(finding.get("chain_log"))
    target = _mapping(finding.get("current_target"))
    refs = _mapping(target.get("current_refs"))
    return {
        "target_id": _text(target.get("target_id")),
        "chain_path": _text(chain.get("path")),
        "chain_state_digest": _text(chain.get("state_digest")),
        "chain_spec_path": _text(chain.get("spec_path")),
        "chain_spec_digest": _text(chain.get("spec_digest")),
        "chain_execution_id": _text(chain.get("execution_id")),
        "chain_last_state": _text(chain.get("last_state")).lower(),
        "chain_complete": chain.get("chain_complete"),
        "completed_count": _integer(chain.get("completed_count")),
        "total_milestones": _integer(chain.get("total_milestones")),
        "current_milestone_index": _integer(chain.get("current_milestone_index")),
        "current_plan": _text(chain.get("current_plan_name") or finding.get("plan")),
        "plan_state": _text(finding.get("current_state")).lower(),
        "plan_state_path": _text(finding.get("state_path")),
        "plan_state_digest": _text(finding.get("state_digest")),
        "plan_iteration": _integer(finding.get("iteration")),
        "active_phase": _text(
            finding.get("active_event_phase") or finding.get("active_step_phase")
        ).lower(),
        "accepted_event_seq": _integer(finding.get("accepted_event_seq")),
        "accepted_event_digest": _text(finding.get("accepted_event_digest")),
        "accepted_artifact_digest": _text(finding.get("accepted_artifact_digest")),
        "events_size": _integer(finding.get("events_size")),
        "events_mtime_age_min": _integer(finding.get("events_mtime_age_min")),
        "chain_log_size": _integer(log.get("size_bytes") or log.get("size")),
        "chain_log_mtime_age_min": _integer(log.get("mtime_age_min")),
        "pr_number": chain.get("pr_number") or refs.get("pr_number"),
        "pr_state": _text(chain.get("pr_state") or refs.get("pr_state")).lower(),
        "blocker_id": _text(_mapping(finding.get("repair_custody_summary")).get("blocker_id")),
    }


def escalation_identity(finding: Mapping[str, Any], *, policy_version: str = POLICY_VERSION) -> str:
    superfixer = _mapping(finding.get("deterministic_superfixer_evidence"))
    cursor = semantic_cursor(finding)
    identity = {
        "policy_version": policy_version,
        "session": _text(finding.get("session")),
        # Session-level custody faults must collapse onto the authoritative
        # current target. Historical completed plan shadows are not distinct
        # controllers merely because the gather enumerated their directories.
        "plan": _text(cursor.get("current_plan")),
        "target_id": cursor.get("target_id"),
        "chain_path": cursor.get("chain_path"),
        "blocker_id": cursor.get("blocker_id"),
        "accepted_unclaimed_request_ids": sorted(
            _text(item)
            for item in _list(superfixer.get("accepted_unclaimed_request_ids"))
            if _text(item)
        ),
        "l1_failure": _l1_failure_fingerprint(finding),
        "l2_failure": _l2_failure_fingerprint(finding),
    }
    return "l3-escalation:" + evidence_digest(identity)


def _process_evidence(finding: Mapping[str, Any]) -> dict[str, Any]:
    target = _mapping(finding.get("current_target"))
    tmux = _mapping(target.get("tmux_process"))
    active = _mapping(finding.get("active_step_liveness"))
    known = any(
        value is not None and value != ""
        for value in (
            tmux.get("pid_live"),
            tmux.get("session_live"),
            tmux.get("live_status"),
            active.get("worker_pid_alive"),
        )
    )
    live = bool(
        tmux.get("pid_live") is True
        or tmux.get("session_live") is True
        or _text(tmux.get("live_status")).lower() == "alive"
        or active.get("worker_pid_alive") is True
    )
    return {
        "present": known,
        "live": live,
        "tmux": dict(tmux),
        "active_step": dict(active),
    }


def _marker_evidence(finding: Mapping[str, Any]) -> dict[str, Any]:
    header = _mapping(finding.get("session_header"))
    target = _mapping(finding.get("current_target"))
    refs = _mapping(target.get("current_refs"))
    session = _text(finding.get("session"))
    marker_session = _text(header.get("session") or target.get("session"))
    workspace = _text(finding.get("workspace"))
    marker_workspace = _text(header.get("workspace") or refs.get("workspace"))
    remote_spec = _text(header.get("remote_spec") or refs.get("remote_spec"))
    marker_path = _text(header.get("marker_path") or refs.get("marker_path"))
    consistent = bool(
        session
        and marker_session == session
        and workspace
        and marker_workspace == workspace
        and remote_spec
        and marker_path
    )
    return {
        "present": bool(marker_path),
        "consistent": consistent,
        "session": marker_session,
        "workspace": marker_workspace,
        "remote_spec": remote_spec,
        "marker_path": marker_path,
    }


def _chain_evidence(finding: Mapping[str, Any]) -> dict[str, Any]:
    chain = _mapping(_mapping(finding.get("chain_state_summary")).get("current"))
    last_state = _text(chain.get("last_state")).lower()
    completed = _integer(chain.get("completed_count"))
    total = _integer(chain.get("total_milestones"))
    terminal = bool(
        chain.get("chain_complete") is True
        or (
            last_state in _TERMINAL_CHAIN_STATES
            and (total in (None, 0) or completed is None or completed >= total)
        )
    )
    nonterminal = bool(
        chain
        and not terminal
        and (
            chain.get("chain_complete") is False
            or last_state not in _TERMINAL_CHAIN_STATES
            or (total not in (None, 0) and completed is not None and completed < total)
        )
    )
    return {
        "present": bool(chain),
        "path": _text(chain.get("path")),
        "last_state": last_state,
        "terminal": terminal,
        "nonterminal": nonterminal,
        "completed_count": completed,
        "total_milestones": total,
        "pr_state": _text(chain.get("pr_state")).lower(),
        "merge_policy": _text(chain.get("merge_policy")).lower(),
        "auto_approve": chain.get("auto_approve"),
        "spec_path": _text(chain.get("spec_path")),
        "spec_digest": _text(chain.get("spec_digest")),
        "state_digest": _text(chain.get("state_digest")),
    }


def _plan_evidence(finding: Mapping[str, Any]) -> dict[str, Any]:
    state = _text(finding.get("current_state")).lower()
    resolver = _mapping(finding.get("resolver_state"))
    canonical = _text(resolver.get("canonical_state") or "UNKNOWN").upper()
    return {
        "present": bool(_text(finding.get("state_path")) and state),
        "state_path": _text(finding.get("state_path")),
        "state": state,
        "terminal": state in _TERMINAL_PLAN_STATES,
        "canonical_state": canonical,
        "confidence": _text(resolver.get("confidence")).lower(),
    }


def _log_evidence(finding: Mapping[str, Any]) -> dict[str, Any]:
    header = _mapping(finding.get("session_header"))
    log = _mapping(finding.get("chain_log"))
    path = _text(log.get("path") or header.get("log"))
    return {
        "present": bool(path),
        "path": path,
        "mtime_age_min": _integer(log.get("mtime_age_min")),
        "repetition_summary": _list(log.get("repetition_summary")),
    }


def _external_evidence(finding: Mapping[str, Any], chain: Mapping[str, Any]) -> dict[str, Any]:
    current_target = _mapping(finding.get("current_target"))
    ci = _mapping(finding.get("ci_health") or current_target.get("ci_health"))
    pr_state = _text(chain.get("pr_state")).lower()
    applicable = bool(pr_state or chain.get("pr_number"))
    expected_pr = _integer(chain.get("pr_number"))
    observed_pr = _integer(ci.get("pr_number"))
    coherent = bool(
        not applicable
        or (
            ci
            and ci.get("available") is True
            and (expected_pr is None or observed_pr == expected_pr)
        )
    )
    merge_policy = _text(chain.get("merge_policy")).lower()
    human_policy = merge_policy in {"review", "manual"} or chain.get("auto_approve") is False
    intentional_wait = bool(
        human_policy
        and (
            pr_state in {"open", "draft", "pending", "queued"}
            or _text(chain.get("last_state")).lower()
            in {"awaiting_pr_merge", "awaiting_ci", "ci_pending"}
        )
    )
    return {
        "applicable": applicable,
        "present": coherent,
        "coherent": coherent,
        "expected_pr_number": expected_pr,
        "observed_pr_number": observed_pr,
        "ci_status": _text(ci.get("status")).lower(),
        "pr_state": pr_state,
        "intentional_wait": intentional_wait,
        "human_policy": human_policy,
        "merge_policy": merge_policy,
    }


def _fresh_progress(finding: Mapping[str, Any], policy: EscalationPolicy) -> dict[str, Any]:
    threshold_min = int(policy.minimum_no_progress.total_seconds() // 60)
    event_age = _integer(finding.get("events_mtime_age_min"))
    log_age = _integer(_mapping(finding.get("chain_log")).get("mtime_age_min"))
    active = _mapping(finding.get("active_step_liveness"))
    token_age = _integer(
        active.get("token_heartbeat_age_min")
        or active.get("heartbeat_age_min")
        or _mapping(finding.get("current_target")).get("token_heartbeat_age_min")
    )
    liveness_sources = []
    if event_age is not None and event_age < threshold_min:
        liveness_sources.append("events")
    if log_age is not None and log_age < threshold_min:
        liveness_sources.append("chain_log")
    if token_age is not None and token_age < threshold_min:
        liveness_sources.append("token_heartbeat")
    acceptance = _mapping(finding.get("acceptance_progress"))
    semantic_sources = [
        _text(item)
        for item in _list(acceptance.get("sources"))
        if _text(item)
    ] if acceptance.get("advanced") is True else []
    superfixer = _mapping(finding.get("deterministic_superfixer_evidence"))
    no_advance_age = _integer(
        acceptance.get("no_advance_age_min")
        or finding.get("no_advance_age_min")
        or superfixer.get("repair_age_min")
    )
    old_enough = bool(
        (no_advance_age is not None and no_advance_age >= threshold_min)
        or (
            event_age is not None
            and event_age >= threshold_min
            and log_age is not None
            and log_age >= threshold_min
        )
    )
    return {
        # Compatibility key: ``fresh`` now means accepted semantic progress,
        # never heartbeat/log/event-file activity by itself.
        "fresh": bool(semantic_sources),
        "fresh_sources": semantic_sources,
        "semantic_progress": bool(semantic_sources),
        "semantic_sources": semantic_sources,
        "liveness_fresh": bool(liveness_sources),
        "liveness_sources": liveness_sources,
        "threshold_min": threshold_min,
        "events_mtime_age_min": event_age,
        "chain_log_mtime_age_min": log_age,
        "token_heartbeat_age_min": token_age,
        "no_advance_age_min": no_advance_age,
        "old_enough": old_enough,
    }


def _reason_tokens(finding: Mapping[str, Any]) -> list[str]:
    return [_text(item).lower() for item in _list(finding.get("reasons")) if _text(item)]


def _l1_failure_fingerprint(finding: Mapping[str, Any]) -> dict[str, Any]:
    repair = _mapping(finding.get("repair_data_summary"))
    custody = _mapping(finding.get("repair_custody_summary"))
    superfixer = _mapping(finding.get("deterministic_superfixer_evidence"))
    retry = _mapping(custody.get("retry_budget") or superfixer.get("retry_budget"))
    deterministic = _mapping(finding.get("deterministic_retry_evidence"))
    reasons = _reason_tokens(finding)
    accepted = _list(custody.get("accepted_unclaimed_request_ids"))
    retry_used = _integer(retry.get("claim_retries_used")) or 0
    retry_remaining = _integer(retry.get("remaining_attempts"))
    if retry_remaining is None:
        retry_remaining = _integer(retry.get("claim_retries_remaining"))
    outcome = _text(repair.get("outcome")).lower()
    provisional_liveness = outcome in {
        "partial_liveness",
        "live_with_fresh_activity",
    }
    blocker_id = _text(custody.get("blocker_id"))
    active_requests = [
        _text(item)
        for item in _list(custody.get("active_request_ids"))
        if _text(item)
    ]
    missing_custody_links = bool(
        provisional_liveness and (not blocker_id or not active_requests)
    )
    liveness_without_custody = bool(
        provisional_liveness and (accepted or missing_custody_links)
    )
    false_success = bool(
        outcome in {"complete", "completed", "progressed", "success", "fixed"}
        and _chain_evidence(finding).get("nonterminal")
    ) or any("repair_complete_incomplete_chain" in item for item in reasons)
    missing_manifest = any(
        token in item
        for item in reasons
        for token in (
            "agent_claim_without_canonical_manifest",
            "managed_run_link_disagreement",
            "legacy_direct_agent_launch",
        )
    )
    repeated = _integer(deterministic.get("count")) or 0
    exhausted = bool(
        outcome in {"repair_timeout", "repair_exhausted", "failed", "failure"}
        or retry_remaining == 0
        or retry_used >= 2
        or repeated >= 3
    )
    failed = bool(
        false_success
        or missing_manifest
        or liveness_without_custody
        or (accepted and exhausted)
        or outcome
        in {
            "repair_timeout",
            "repair_exhausted",
            "failed",
            "failure",
        }
    )
    axis = (
        "FIXED"
        if false_success
        else "TRACKED"
        if missing_manifest
        else "CONTEXT"
        if accepted or missing_custody_links
        else "FIXED"
    )
    return {
        "failed": failed,
        "axis": axis if failed else "",
        "outcome": outcome,
        "accepted_unclaimed_count": len(accepted),
        "retry_used": retry_used,
        "retry_remaining": retry_remaining,
        "repeated_deterministic_failures": repeated,
        "false_success": false_success,
        "missing_canonical_manifest": missing_manifest,
        "missing_custody_links": missing_custody_links,
        "provisional_liveness": provisional_liveness,
        "liveness_without_custody": liveness_without_custody,
    }


def _l2_failure_fingerprint(finding: Mapping[str, Any]) -> dict[str, Any]:
    meta = _mapping(finding.get("meta_repair_summary"))
    superfixer = _mapping(finding.get("deterministic_superfixer_evidence"))
    reasons = _reason_tokens(finding)
    failed_launch = bool(meta.get("failed_meta_run_count") or meta.get("failed_meta_record_count"))
    missing = bool(
        meta.get("missing_meta_run_evidence")
        or superfixer.get("absent_or_stale_l2")
        or any("meta-repair trigger" in item and "no meta record" in item for item in reasons)
    )
    false_success = any(
        token in item
        for item in reasons
        for token in ("false_fixed_l2", "l2 false success", "no ordinary repair retrigger")
    )
    l1 = _l1_failure_fingerprint(finding)
    due = bool(
        meta.get("should_dispatch")
        or meta.get("trigger")
        or superfixer.get("actionable")
        or l1.get("failed")
    )
    failed = bool(due and (failed_launch or missing or false_success))
    axis = "FIXED" if false_success else "TRACKED" if failed_launch else "CONTEXT"
    return {
        "failed": failed,
        "axis": axis if failed else "",
        "due": due,
        "failed_launch": failed_launch,
        "missing_or_stale": missing,
        "false_success": false_success,
        "trigger": _text(meta.get("trigger")),
    }


def classify_true_stall(
    finding: Mapping[str, Any],
    *,
    policy: EscalationPolicy | None = None,
) -> dict[str, Any]:
    """Fail closed unless all true-stall predicates are affirmatively proven."""

    selected = policy or EscalationPolicy()
    process = _process_evidence(finding)
    marker = _marker_evidence(finding)
    chain = _chain_evidence(finding)
    plan = _plan_evidence(finding)
    log = _log_evidence(finding)
    external = _external_evidence(finding, _mapping(_mapping(finding.get("chain_state_summary")).get("current")))
    progress = _fresh_progress(finding, selected)
    l1 = _l1_failure_fingerprint(finding)
    l2 = _l2_failure_fingerprint(finding)
    resolver_state = _text(plan.get("canonical_state")).upper()
    current_state = _text(plan.get("state")).lower()
    chain_state = _text(chain.get("last_state")).lower()
    unresolved_actions = _list(
        _mapping(finding.get("user_action_context")).get("unresolved_user_actions")
    )
    finding_plan = _text(finding.get("plan"))
    authoritative_plan = _text(
        _mapping(_mapping(finding.get("chain_state_summary")).get("current")).get(
            "current_plan_name"
        )
    )
    completed_shadow = bool(
        plan.get("terminal")
        and authoritative_plan
        and finding_plan
        and authoritative_plan != finding_plan
    )
    explicit_pause = bool(
        resolver_state == "PAUSED"
        or current_state == "paused"
        or chain_state == "paused"
        or _mapping(finding.get("current_target")).get("operator_pause")
        or _mapping(_mapping(finding.get("current_target")).get("metadata")).get("operator_pause")
    )
    human_gate = bool(
        resolver_state == "HUMAN_ACTION_REQUIRED"
        or unresolved_actions
        or chain_state in {"awaiting_human", "awaiting_human_verify"}
        or external.get("human_policy")
    )
    intent_allowed = resolver_state in _MACHINE_ACTION_STATES
    intentional_wait = bool(explicit_pause or human_gate or external.get("intentional_wait"))
    health = _mapping(finding.get("chain_health_progress"))
    repair = _mapping(finding.get("repair_data_summary"))
    deterministic_retry = _mapping(finding.get("deterministic_retry_evidence"))
    recurrence_observations = max(
        _integer(health.get("no_advance_ticks")) or 0,
        _integer(health.get("stuck_ticks")) or 0,
        _integer(repair.get("iteration_count")) or len(_list(repair.get("iterations"))),
        _integer(deterministic_retry.get("count")) or 0,
        _integer(l1.get("retry_used")) or 0,
        len(_list(finding.get("prior_audit_refs"))),
    )

    evidence_sources = {
        "live_process": process,
        "session_marker": marker,
        "chain_json": chain,
        "plan_state": plan,
        "logs": log,
        "external_state": external,
    }
    missing_sources = [
        name
        for name, evidence in evidence_sources.items()
        if evidence.get("present") is not True
    ]
    if marker.get("present") and not marker.get("consistent"):
        missing_sources.append("session_marker_consistency")
    if not chain.get("path"):
        missing_sources.append("canonical_chain_path")

    blocks: list[str] = []
    if missing_sources:
        blocks.append("incomplete_or_incoherent_evidence")
    if resolver_state in _INTENTIONAL_WAIT_STATES or intentional_wait:
        blocks.append("intentional_pause_or_human_gate")
    if completed_shadow:
        blocks.append("completed_plan_shadow")
    if not intent_allowed:
        blocks.append("resolver_did_not_authorize_machine_action")
    if chain.get("terminal") or plan.get("terminal"):
        blocks.append("target_terminal")
    if not chain.get("nonterminal"):
        blocks.append("chain_not_proven_incomplete")
    if progress.get("fresh"):
        blocks.append("fresh_acceptance_progress")
    if not progress.get("old_enough"):
        blocks.append("no_progress_window_not_proven")
    if recurrence_observations < selected.recurrence_threshold:
        blocks.append("recurrence_threshold_not_met")
    if not l1.get("failed"):
        blocks.append("l1_failure_not_proven")
    if not l2.get("failed"):
        blocks.append("l2_backstop_failure_not_proven")

    eligible = not blocks
    first_broken_layer = "L1" if l1.get("failed") else ""
    first_broken_axis = _text(l1.get("axis")) if first_broken_layer else ""
    missed_by_layer = "L2" if first_broken_layer and l2.get("failed") else ""
    missed_by_axis = _text(l2.get("axis")) if missed_by_layer else ""
    custody_walk = {
        "L1": {
            "TRACKED": not bool(l1.get("missing_canonical_manifest")),
            "FIXED": not bool(l1.get("false_success")) and not bool(l1.get("failed")),
            "INTENT": not any("guard_weakening" in item for item in _reason_tokens(finding)),
            "CONTEXT": not bool(l1.get("accepted_unclaimed_count")),
            "failure": l1,
        },
        "L2": {
            "TRACKED": not bool(l2.get("failed_launch")),
            "FIXED": not bool(l2.get("false_success")) and not bool(l2.get("failed")),
            "INTENT": not any("guard_weakening" in item for item in _reason_tokens(finding)),
            "CONTEXT": not bool(l2.get("missing_or_stale")),
            "failure": l2,
        },
        "L3": {
            "TRACKED": not missing_sources,
            "FIXED": False,
            "INTENT": intent_allowed and not intentional_wait,
            "CONTEXT": not missing_sources,
        },
        "first_broken_layer": first_broken_layer,
        "first_broken_axis": first_broken_axis,
        "missed_by_layer": missed_by_layer,
        "missed_by_axis": missed_by_axis,
    }
    gate = {
        "schema_version": ESCALATION_SCHEMA,
        "policy_version": POLICY_VERSION,
        "eligible": eligible,
        "decision": "true_stall" if eligible else "report_only",
        "session": _text(finding.get("session")),
        "plan": _text(finding.get("plan")),
        "escalation_id": escalation_identity(finding),
        "idempotency_key": escalation_identity(finding),
        "blocks": sorted(set(blocks)),
        "missing_sources": sorted(set(missing_sources)),
        "evidence_sources": evidence_sources,
        "progress": progress,
        "recurrence": {
            "observations": recurrence_observations,
            "threshold": selected.recurrence_threshold,
            "satisfied": recurrence_observations >= selected.recurrence_threshold,
        },
        "custody_walk": custody_walk,
        "baseline_cursor": semantic_cursor(finding),
        "route": {
            "requested_difficulty": selected.requested_difficulty,
            "effective_difficulty": selected.requested_difficulty,
            "model": DEEP_REPAIR_MODEL,
            "reasoning_effort": DEEP_REPAIR_REASONING,
            "child_difficulty_ceiling": selected.child_difficulty_ceiling,
            "promotion_reason": "",
        },
        "quarantine": {
            "required": False,
            "state": "not_applied",
            "reason": (
                "L3 does not stop or quarantine the original chain; blocker-scoped "
                "repair custody is sufficient unless a separately proven duplicate-effect risk exists"
            ),
            "reversible": True,
        },
        "policy": {
            "minimum_no_progress_seconds": int(selected.minimum_no_progress.total_seconds()),
            "recurrence_threshold": selected.recurrence_threshold,
            "cooldown_seconds": int(selected.cooldown.total_seconds()),
            "launch_establishment_budget": selected.launch_establishment_budget,
            "deterministic_failure_budget": selected.deterministic_failure_budget,
            "max_investigators": selected.max_investigators,
            "root_cause_owner_limit": selected.root_cause_owner_limit,
            "execution_owner_limit": selected.execution_owner_limit,
            "global_concurrency_limit": selected.global_concurrency_limit,
            "per_session_concurrency_limit": selected.per_session_concurrency_limit,
        },
        "suppression": {
            "completed_plan_shadow": completed_shadow,
            "authoritative_plan": authoritative_plan,
            "finding_plan": finding_plan,
        },
    }
    gate["evidence_digest"] = evidence_digest(
        {
            "sources": evidence_sources,
            "progress": progress,
            "custody_walk": custody_walk,
            "cursor": gate["baseline_cursor"],
        }
    )
    return gate


def plan_dispatch(
    gate: Mapping[str, Any],
    prior_state: Mapping[str, Any] | None,
    *,
    authorized: bool,
    active_global: int = 0,
    active_for_session: int = 0,
    now: datetime | None = None,
    policy: EscalationPolicy | None = None,
) -> dict[str, Any]:
    """Apply idempotency, cooldown, retry budgets, and concurrency limits."""

    selected = policy or EscalationPolicy()
    effective_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    state = dict(prior_state or {})
    attempts = _list(state.get("attempts"))
    establishment_failures = sum(
        1 for item in attempts if _text(_mapping(item).get("outcome")) == "launch_failed"
    )
    deterministic_failures = sum(
        1
        for item in attempts
        if _text(_mapping(item).get("outcome"))
        in {"false_success", "recovery_not_verified", "deterministic_failure"}
    )
    active_attempts = [
        item
        for item in attempts
        if _text(_mapping(item).get("status")) in _ACTIVE_MANAGED_STATUSES
    ]
    cooldown_until = _parse_time(state.get("cooldown_until"))
    circuit_open_until = _parse_time(state.get("circuit_open_until"))

    decision = "dispatch_authorized"
    reason = "all escalation predicates and bounded policy controls passed"
    if _text(state.get("outcome")) in {"human_terminal", "exhausted_terminal"}:
        decision = "terminal_escalation"
        reason = _text(state.get("terminal_reason")) or "durable terminal escalation recorded"
    elif gate.get("eligible") is not True:
        decision = "report_only"
        reason = "true-stall gate did not pass"
    elif not authorized:
        decision = "blocked_authority"
        reason = "L3 master-plus-path mutation authority is absent"
    elif _text(state.get("outcome")) == "recovery_verified":
        decision = "recovery_verified"
        reason = "the correlated original run already advanced after canonical recovery"
    elif active_attempts:
        decision = "deduplicated_active"
        reason = "this escalation already has an active canonical managed run"
    elif circuit_open_until and effective_now < circuit_open_until:
        decision = "terminal_escalation"
        reason = "same-fingerprint repair circuit is exhausted; human approval is required"
    elif cooldown_until and effective_now < cooldown_until:
        decision = "cooldown"
        reason = "same-fingerprint escalation is cooling down"
    elif establishment_failures >= selected.launch_establishment_budget:
        decision = "terminal_escalation"
        reason = "canonical launch-establishment retry budget is exhausted; human repair authority required"
    elif deterministic_failures >= selected.deterministic_failure_budget:
        decision = "terminal_escalation"
        reason = "same-fingerprint repair budget is exhausted; a human-approved new approach is required"
    elif active_global >= selected.global_concurrency_limit:
        decision = "concurrency_limited"
        reason = "global L3 deep-repair concurrency limit reached"
    elif active_for_session >= selected.per_session_concurrency_limit:
        decision = "concurrency_limited"
        reason = "per-session L3 deep-repair concurrency limit reached"
    return {
        "decision": decision,
        "authorized": authorized,
        "dispatch": decision == "dispatch_authorized",
        "reason": reason,
        "attempt_count": len(attempts),
        "launch_establishment_failures": establishment_failures,
        "deterministic_failures": deterministic_failures,
        "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
        "circuit_open_until": circuit_open_until.isoformat() if circuit_open_until else None,
        "retry_lineage": [
            _text(_mapping(item).get("managed_run_id")) for item in attempts if _mapping(item)
        ],
    }


def validate_managed_launch(
    manifest: Mapping[str, Any],
    *,
    gate: Mapping[str, Any],
    request_id: str,
) -> dict[str, Any]:
    """Never call a repair dispatched without canonical durable launch proof."""

    links = _mapping(manifest.get("links"))
    provenance = _mapping(manifest.get("launch_provenance"))
    route = _mapping(gate.get("route"))
    run_id = _text(manifest.get("run_id"))
    errors = []
    try:
        validate_automatic_managed_manifest(manifest)
    except (TypeError, ValueError):
        errors.append("canonical_managed_contract_invalid")
    expected = {
        "schema_version": "arnold-managed-agent-run-v2",
        "custodian": "arnold.megaplan.managed_agent",
        "run_kind": DEEP_REPAIR_RUN_KIND,
        "model": DEEP_REPAIR_MODEL,
        "reasoning_effort": DEEP_REPAIR_REASONING,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            errors.append(f"manifest_{key}_mismatch")
    if not run_id:
        errors.append("managed_run_id_missing")
    if provenance.get("transport") != "automatic_system":
        errors.append("machine_origin_missing")
    if links.get("repair_request_id") != request_id:
        errors.append("repair_request_link_mismatch")
    if links.get("audit_escalation_id") != gate.get("escalation_id"):
        errors.append("audit_escalation_link_mismatch")
    if links.get("cloud_session") != gate.get("session"):
        errors.append("session_link_mismatch")
    difficulty = _integer(manifest.get("difficulty"))
    ceiling = _integer(_mapping(manifest.get("authority")).get("child_difficulty_ceiling"))
    if difficulty not in {DEEP_REPAIR_DIFFICULTY, 10}:
        errors.append("effective_difficulty_invalid")
    if difficulty == 10 and not _text(route.get("promotion_reason")):
        errors.append("d10_promotion_reason_missing")
    if ceiling is None or ceiling > (difficulty or DEEP_REPAIR_DIFFICULTY):
        errors.append("child_authority_ceiling_invalid")
    started = any(
        _mapping(item).get("status") == "running"
        for item in _list(manifest.get("status_history"))
    )
    if not started:
        errors.append("worker_start_evidence_missing")
    return {
        "valid": not errors,
        "dispatched": not errors,
        "errors": errors,
        "managed_run_id": run_id if not errors else "",
        "managed_manifest_path": _text(manifest.get("manifest_path")) if not errors else "",
    }


def validate_owner_topology(
    repair_outcome: Mapping[str, Any],
    *,
    policy: EscalationPolicy | None = None,
) -> dict[str, Any]:
    """Validate bounded investigators and exactly one execution owner receipt."""

    selected = policy or EscalationPolicy()
    topology = _mapping(repair_outcome.get("owner_topology"))
    root = _mapping(topology.get("root_cause_owner"))
    investigators = [
        _mapping(item) for item in _list(topology.get("investigators")) if isinstance(item, Mapping)
    ]
    execution = [
        _mapping(item) for item in _list(topology.get("execution_owners")) if isinstance(item, Mapping)
    ]
    errors: list[str] = []
    if not _text(root.get("run_id")) or not _text(root.get("manifest_path")):
        errors.append("root_cause_owner_receipt_missing")
    if len(investigators) > selected.max_investigators:
        errors.append("investigator_budget_exceeded")
    investigator_ids = [_text(item.get("run_id")) for item in investigators]
    if any(not item for item in investigator_ids) or len(set(investigator_ids)) != len(investigator_ids):
        errors.append("investigator_identity_invalid")
    if any(item.get("read_only") is not True for item in investigators):
        errors.append("investigator_not_read_only")
    if len(execution) != selected.execution_owner_limit:
        errors.append("execution_owner_count_not_one")
    execution_ids = [_text(item.get("run_id")) for item in execution]
    if any(not item for item in execution_ids) or len(set(execution_ids)) != len(execution_ids):
        errors.append("execution_owner_identity_invalid")
    if any(not isinstance(item.get("observed_live"), bool) for item in execution):
        errors.append("execution_owner_liveness_receipt_missing")
    active_execution = [item for item in execution if item.get("observed_live") is True]
    reported_active = _integer(topology.get("active_controller_count"))
    if reported_active is None or reported_active != len(active_execution):
        errors.append("active_controller_count_disagreement")
    if reported_active not in {0, 1}:
        errors.append("active_controller_count_not_unique")
    return {
        "valid": not errors,
        "errors": errors,
        "root_cause_owner": dict(root),
        "investigators": [dict(item) for item in investigators],
        "investigator_count": len(investigators),
        "execution_owners": [dict(item) for item in execution],
        "execution_owner_count": len(execution),
        "active_controller_count": reported_active,
        "active_execution_owner_count": len(active_execution),
    }


_PHASE_ORDER = {
    "prep": 10,
    "plan": 20,
    "critique": 30,
    "gate": 40,
    "revise": 50,
    "finalize": 60,
    "execute": 70,
    "review": 80,
    "feedback": 90,
    "done": 100,
    "completed": 100,
}


def verify_recovery(
    *,
    baseline: Mapping[str, Any],
    current_finding: Mapping[str, Any],
    repair_outcome: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a durable semantic progress receipt; liveness is never enough."""

    current = semantic_cursor(current_finding)
    guard_changes = _list(repair_outcome.get("guard_changes"))
    guard_weakened = bool(
        repair_outcome.get("guard_weakened") is True
        or guard_changes
        or repair_outcome.get("force_proceed") is True
        or repair_outcome.get("direct_state_advance") is True
    )
    fixer_fixed = repair_outcome.get("fixer_fixed") is True
    backstop_fixed = repair_outcome.get("backstop_fixed") is True
    normal_retrigger = bool(
        _text(repair_outcome.get("ordinary_retrigger_run_id"))
        and _text(repair_outcome.get("ordinary_retrigger_manifest_path"))
    )
    topology = validate_owner_topology(repair_outcome)
    baseline_completed = _integer(baseline.get("completed_count"))
    current_completed = _integer(current.get("completed_count"))
    baseline_milestone = _integer(baseline.get("current_milestone_index"))
    current_milestone = _integer(current.get("current_milestone_index"))
    milestone_advanced = bool(
        current.get("chain_complete") is True
        or (
            baseline_completed is not None
            and current_completed is not None
            and current_completed > baseline_completed
        )
        or (
            _text(current.get("current_plan"))
            and _text(current.get("current_plan")) != _text(baseline.get("current_plan"))
        )
        or (
            baseline_milestone is not None
            and current_milestone is not None
            and current_milestone > baseline_milestone
        )
    )
    baseline_phase = _text(baseline.get("active_phase")).lower()
    current_phase = _text(current.get("active_phase")).lower()
    phase_advanced = bool(
        baseline_phase
        and current_phase
        and _PHASE_ORDER.get(current_phase, -1) > _PHASE_ORDER.get(baseline_phase, -1)
    )
    same_chain_identity = bool(
        _text(baseline.get("chain_path"))
        and _text(baseline.get("chain_path")) == _text(current.get("chain_path"))
        and (
            not _text(baseline.get("chain_spec_digest"))
            or not _text(current.get("chain_spec_digest"))
            or _text(baseline.get("chain_spec_digest")) == _text(current.get("chain_spec_digest"))
        )
        and (
            not _text(baseline.get("chain_execution_id"))
            or not _text(current.get("chain_execution_id"))
            or _text(baseline.get("chain_execution_id")) == _text(current.get("chain_execution_id"))
        )
    )
    baseline_state_digest = _text(baseline.get("chain_state_digest"))
    current_state_digest = _text(current.get("chain_state_digest"))
    state_receipts_present = bool(baseline_state_digest and current_state_digest)
    chain_state_changed = bool(
        state_receipts_present and baseline_state_digest != current_state_digest
    )
    baseline_seq = _integer(baseline.get("accepted_event_seq"))
    current_seq = _integer(current.get("accepted_event_seq"))
    fresh_event = bool(
        baseline_seq is not None and current_seq is not None and current_seq > baseline_seq
    ) or bool(
        _text(current.get("accepted_event_digest"))
        and _text(current.get("accepted_event_digest"))
        != _text(baseline.get("accepted_event_digest"))
    )
    fresh_artifact = bool(
        _text(current.get("accepted_artifact_digest"))
        and _text(current.get("accepted_artifact_digest"))
        != _text(baseline.get("accepted_artifact_digest"))
    )
    fresh_evidence = fresh_event or fresh_artifact
    semantic_advanced = milestone_advanced or phase_advanced
    verified = bool(
        fixer_fixed
        and backstop_fixed
        and normal_retrigger
        and topology.get("valid")
        and same_chain_identity
        and chain_state_changed
        and semantic_advanced
        and fresh_evidence
        and not guard_weakened
    )
    approach = _mapping(repair_outcome.get("approach_receipt"))
    approach_digest = _text(approach.get("approach_digest"))
    prior_digests = {_text(item) for item in _list(approach.get("prior_approach_digests")) if _text(item)}
    new_approach = bool(
        approach.get("validated") is True
        and len(approach_digest) == 64
        and approach_digest not in prior_digests
    )
    approach_artifact_fresh = bool(
        new_approach and _list(approach.get("fresh_evidence_refs"))
    )
    approach_active = bool(
        not verified
        and topology.get("valid")
        and topology.get("active_execution_owner_count") == 1
        and approach_artifact_fresh
        and same_chain_identity
        and state_receipts_present
        and not guard_weakened
    )
    accepted = verified or approach_active
    reasons = []
    if not fixer_fixed:
        reasons.append("failed_fixer_not_repaired")
    if not backstop_fixed:
        reasons.append("missed_backstop_not_repaired")
    if not normal_retrigger:
        reasons.append("ordinary_recovery_not_retriggered")
    if not topology.get("valid"):
        reasons.extend(topology.get("errors") or ["owner_topology_invalid"])
    if not same_chain_identity:
        reasons.append("authoritative_chain_identity_disagrees")
    if not state_receipts_present:
        reasons.append("authoritative_before_after_state_receipts_missing")
    elif semantic_advanced and not chain_state_changed:
        reasons.append("authoritative_chain_state_digest_unchanged")
    if not semantic_advanced:
        reasons.append("original_run_did_not_advance")
    if not fresh_evidence:
        reasons.append("fresh_event_or_artifact_receipt_missing")
    if guard_weakened:
        reasons.append("completion_or_safety_guard_weakened")
    return {
        "verified": verified,
        "accepted": accepted,
        "outcome": (
            "recovery_verified"
            if verified
            else "validated_approach_active"
            if approach_active
            else "recovery_not_verified"
        ),
        "reasons": reasons,
        "baseline_cursor": dict(baseline),
        "current_cursor": current,
        "guard_weakened": guard_weakened,
        "fixer_fixed": fixer_fixed,
        "backstop_fixed": backstop_fixed,
        "ordinary_retriggered": normal_retrigger,
        "same_authoritative_chain": same_chain_identity,
        "authoritative_state_receipts_present": state_receipts_present,
        "authoritative_chain_state_changed": chain_state_changed,
        "original_run_advanced": semantic_advanced,
        "milestone_advanced": milestone_advanced,
        "phase_advanced": phase_advanced,
        "fresh_event_evidence": fresh_event,
        "fresh_artifact_evidence": fresh_artifact,
        "owner_topology": topology,
        "approach_active": approach_active,
        "approach_artifact_fresh": approach_artifact_fresh,
        "approach_digest": approach_digest,
    }


def next_attempt_state(
    prior_state: Mapping[str, Any] | None,
    *,
    gate: Mapping[str, Any],
    outcome: str,
    managed_run_id: str = "",
    managed_manifest_path: str = "",
    request_id: str = "",
    now: datetime | None = None,
    policy: EscalationPolicy | None = None,
) -> dict[str, Any]:
    """Return the durable correlation state after one dispatch/reverify step."""

    selected = policy or EscalationPolicy()
    effective_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    state = dict(prior_state or {})
    attempts = _list(state.get("attempts"))
    attempt = {
        "attempt": len(attempts) + 1,
        "recorded_at": effective_now.isoformat(),
        "outcome": outcome,
        "status": (
            "running"
            if outcome == "dispatched"
            else "completed"
            if outcome == "recovery_verified"
            else "failed"
        ),
        "managed_run_id": managed_run_id,
        "managed_manifest_path": managed_manifest_path,
        "repair_request_id": request_id,
        "retry_of_run_id": _text(_mapping(attempts[-1]).get("managed_run_id")) if attempts else "",
    }
    attempts.append(attempt)
    state.update(
        {
            "schema_version": ESCALATION_SCHEMA,
            "policy_version": gate.get("policy_version") or POLICY_VERSION,
            "escalation_id": gate.get("escalation_id"),
            "session": gate.get("session"),
            "plan": gate.get("plan"),
            "finding_evidence_digest": gate.get("evidence_digest"),
            "baseline_cursor": gate.get("baseline_cursor"),
            "route": gate.get("route"),
            "attempts": attempts,
            "updated_at": effective_now.isoformat(),
            "cooldown_until": (effective_now + selected.cooldown).isoformat(),
            "outcome": outcome,
        }
    )
    deterministic_failures = sum(
        1
        for item in attempts
        if _text(_mapping(item).get("outcome"))
        in {"false_success", "recovery_not_verified", "deterministic_failure"}
    )
    launch_failures = sum(
        1 for item in attempts if _text(_mapping(item).get("outcome")) == "launch_failed"
    )
    if (
        deterministic_failures >= selected.deterministic_failure_budget
        or launch_failures >= selected.launch_establishment_budget
    ):
        state["circuit_open_until"] = (effective_now + selected.cooldown).isoformat()
        state["circuit_reason"] = (
            "deterministic_failure_budget_exhausted"
            if deterministic_failures >= selected.deterministic_failure_budget
            else "launch_establishment_budget_exhausted"
        )
        state["outcome"] = "exhausted_terminal"
        state["terminal_state"] = "human_approval_required"
        state["terminal_reason"] = (
            "same-fingerprint deterministic repair budget exhausted"
            if deterministic_failures >= selected.deterministic_failure_budget
            else "canonical launch-establishment budget exhausted"
        )
    return state


def record_reverification(
    prior_state: Mapping[str, Any],
    *,
    verification: Mapping[str, Any],
    now: datetime | None = None,
    policy: EscalationPolicy | None = None,
) -> dict[str, Any]:
    """Close a dispatched attempt with independently gathered recovery truth."""

    selected = policy or EscalationPolicy()
    effective_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    state = dict(prior_state)
    attempts = [dict(item) for item in _list(state.get("attempts")) if isinstance(item, Mapping)]
    if not attempts:
        return state
    outcome = _text(verification.get("outcome")) or (
        "recovery_verified"
        if verification.get("verified") is True
        else "recovery_not_verified"
    )
    approach_active = outcome == "validated_approach_active"
    attempts[-1].update(
        {
            "status": (
                "running"
                if approach_active
                else "completed"
                if outcome == "recovery_verified"
                else "failed"
            ),
            "outcome": outcome,
            "reverified_at": effective_now.isoformat(),
            "verification": dict(verification),
        }
    )
    state.update(
        {
            "attempts": attempts,
            "outcome": outcome,
            "updated_at": effective_now.isoformat(),
            "last_verification": dict(verification),
        }
    )
    failures = sum(
        1
        for item in attempts
        if _text(item.get("outcome"))
        in {"false_success", "recovery_not_verified", "deterministic_failure"}
    )
    if failures >= selected.deterministic_failure_budget:
        state["circuit_open_until"] = (effective_now + selected.cooldown).isoformat()
        state["circuit_reason"] = "deterministic_failure_budget_exhausted"
    return state


def bounded_repair_context(finding: Mapping[str, Any]) -> dict[str, Any]:
    """Select concrete bounded artifacts and raw failure mechanics for D9."""

    latest = _mapping(finding.get("plan_latest_failure"))
    metadata = _mapping(latest.get("metadata") or finding.get("latest_failure_metadata"))
    repair = _mapping(finding.get("repair_data_summary"))
    meta = _mapping(finding.get("meta_repair_summary"))
    source_refs = _mapping(finding.get("source_refs"))
    mechanics = {
        key: metadata.get(key)
        for key in (
            "stderr",
            "exit_code",
            "returncode",
            "exception",
            "error",
            "command",
            "state",
        )
        if metadata.get(key) not in (None, "")
    }
    context = {
        "session": finding.get("session"),
        "plan": finding.get("plan"),
        "workspace": finding.get("workspace"),
        "gate": classify_true_stall(finding),
        "failure_mechanics": mechanics,
        "latest_failure": {
            "kind": latest.get("kind"),
            "phase": latest.get("phase"),
            "message": latest.get("message"),
            "recorded_at": latest.get("recorded_at"),
        },
        "repair_iterations": _list(repair.get("iterations"))[-5:],
        "repair_attempts": _list(repair.get("attempts"))[-5:],
        "meta_run_refs": _list(meta.get("meta_run_refs"))[-5:],
        "artifact_refs": {
            key: _list(value)[-10:] if isinstance(value, list) else value
            for key, value in source_refs.items()
        },
        "required_method": {
            "methodology": "superfixer-debug",
            "sequence": [
                "identify first broken TRACKED/FIXED/INTENT/CONTEXT custody layer",
                "fix that fixer and the layer above that missed it",
                "hunt sibling instances including token drift, stale projections, missing evidence, false success, guard weakening, and spinning fixers",
                "retrigger the ordinary canonical recovery path",
                "prove the original session advances without weakening completion or safety guards",
            ],
            "child_difficulty_ceiling": DEEP_REPAIR_DIFFICULTY,
        },
    }
    # Keep queue/manifests small and deterministic.  The cited paths retain the
    # complete artifacts; this payload is the bounded launch context.
    encoded = _canonical_json(context)
    if len(encoded.encode("utf-8")) > 64 * 1024:
        context["repair_iterations"] = context["repair_iterations"][-2:]
        context["repair_attempts"] = context["repair_attempts"][-2:]
        context["meta_run_refs"] = context["meta_run_refs"][-2:]
        context["context_truncated"] = True
    context["context_digest"] = evidence_digest(context)
    return context


__all__ = [
    "DEEP_REPAIR_DIFFICULTY",
    "DEEP_REPAIR_MODEL",
    "DEEP_REPAIR_REASONING",
    "DEEP_REPAIR_RUN_KIND",
    "ESCALATION_SCHEMA",
    "EscalationPolicy",
    "POLICY_VERSION",
    "bounded_repair_context",
    "classify_true_stall",
    "escalation_identity",
    "evidence_digest",
    "next_attempt_state",
    "plan_dispatch",
    "record_reverification",
    "semantic_cursor",
    "validate_managed_launch",
    "validate_owner_topology",
    "verify_recovery",
]
