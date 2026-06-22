"""Pure classification and allowlist rules for the live-supervisor pipeline."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from arnold_pipelines.megaplan.watchdog.correlate import _path_contains
from arnold_pipelines.megaplan.pipelines.live_supervisor.model import (
    AllowlistVerdict,
    CheckFinding,
    HealthCategory,
    Incident,
    RepairAction,
    RepairRecommendation,
    Triage,
)


# Common terminal states observed in Megaplan plan state.json.
_TERMINAL_STATES: frozenset[str] = frozenset({
    "completed",
    "failed",
    "aborted",
    "resolved",
    "cancelled",
    "finalized",
    "executed",
    "done",
    "reviewed",
    "accepted",
})

_HARNESS_CHECKS: frozenset[str] = frozenset({
    "stale_lock",
    "orphan_subprocess",
    "multiple_checkouts",
})


def _is_terminal(state: Mapping[str, Any]) -> bool:
    current = state.get("current_state")
    if isinstance(current, str) and current in _TERMINAL_STATES:
        return True
    if state.get("status") in _TERMINAL_STATES:
        return True
    return False


def normalize_doctor_findings(
    plan_findings: Iterable[Any] | None,
    repo_findings: Iterable[Any] | None,
) -> tuple[CheckFinding, ...]:
    """Flatten mixed single-tuple / list-of-tuples doctor findings.

    Megaplan doctor checks return either ``(check, status, message)`` or a
    list of such tuples. Normalize both forms into ``CheckFinding`` objects
    tagged by scope.
    """
    results: list[CheckFinding] = []

    def _add(scope: str, item: Any) -> None:
        if item is None:
            return
        if isinstance(item, (list, tuple)) and len(item) == 3 and all(isinstance(x, str) for x in item):
            results.append(CheckFinding(scope=scope, check=item[0], status=item[1], message=item[2]))
        elif isinstance(item, CheckFinding):
            results.append(item)

    for finding in plan_findings or ():
        if isinstance(finding, (list, tuple)) and finding and isinstance(finding[0], (list, tuple)):
            for sub in finding:
                _add("plan", sub)
        else:
            _add("plan", finding)

    for finding in repo_findings or ():
        if isinstance(finding, (list, tuple)) and finding and isinstance(finding[0], (list, tuple)):
            for sub in finding:
                _add("repo", sub)
        else:
            _add("repo", finding)

    return tuple(results)


def classify_incident(incident: Incident) -> HealthCategory:
    """Map an incident's signal bundle to one of the seven health categories."""
    signals = incident.signals
    triage = incident.triage
    state = incident.plan_entry.state

    if signals.degraded:
        return HealthCategory.UNKNOWN

    # Harness issues (stale locks, orphan subprocesses, multiple checkouts) take
    # precedence even for terminal plans: a finalized plan with a leftover lock
    # still needs cleanup.
    harness_findings = [f for f in signals.doctor_findings if f.check in _HARNESS_CHECKS]
    if harness_findings:
        return HealthCategory.HARNESS_ISSUE

    if _is_terminal(state):
        return HealthCategory.ALL_GOOD

    # False stall: the only reason liveness is "progressing" is an in-flight
    # LLM call that has not produced a real event in a long time.
    if (
        signals.liveness == "progressing"
        and signals.has_in_flight_llm
        and signals.last_event_age_seconds is not None
        and signals.last_event_age_seconds > 300
    ):
        return HealthCategory.FALSE_STALL

    # Defensive fallback: stalled with an in-flight LLM is also a false stall.
    if signals.liveness == "stalled" and signals.has_in_flight_llm:
        return HealthCategory.FALSE_STALL

    # Healthy: live process correlated to the plan, or real progress.
    if triage is Triage.LIVE and signals.liveness in {"progressing", "live_process"}:
        return HealthCategory.ALL_GOOD

    # Environment issues affect the repo/workspace, not a single plan.
    repo_findings = [f for f in signals.doctor_findings if f.scope == "repo"]
    if repo_findings:
        return HealthCategory.ENVIRONMENT_ISSUE

    # Plan issues: blocked, phase timeout, or explicit recoverable_via.
    block_details = signals.block_details
    if block_details.get("is_blocked"):
        return HealthCategory.PLAN_ISSUE
    if signals.liveness == "timeout-imminent":
        return HealthCategory.PLAN_ISSUE
    if block_details.get("recoverable_via"):
        return HealthCategory.PLAN_ISSUE

    # Dead or disappeared: no live process and no recent real events.
    no_recent_events = (
        signals.last_event_age_seconds is None
        or signals.last_event_age_seconds > 3600
    )
    if triage in (Triage.STALE, Triage.MAYBE_LIVE) and no_recent_events:
        return HealthCategory.DEAD_OR_DISAPPEARED

    return HealthCategory.UNKNOWN


_UNCONDITIONALLY_SAFE: frozenset[str] = frozenset({
    "introspect",
    "trace",
    "doctor",
    "chain status",
})


def _is_destructive(command: str) -> bool:
    lowered = command.lower().strip()
    destructive_prefixes = (
        "git reset",
        "git checkout",
        "git push",
        "git merge",
        "git rebase",
    )
    if lowered.startswith(destructive_prefixes):
        return True
    if "worktree" in lowered and ("delete" in lowered or "remove" in lowered):
        return True
    if "plan" in lowered and ("delete" in lowered or "remove" in lowered):
        return True
    return False


def enforce_allowlist(
    recommendation: RepairRecommendation,
    context: Mapping[str, Any],
) -> AllowlistVerdict:
    """Decide whether a recommended repair command is safe to run.

    Unconditionally allows read-only inspection commands. Conditionally allows
    ``auto``, ``resume``, and ``chain start --one --no-git-refresh --no-push``
    when the required context is present. Rejects destructive git operations
    and worktree/plan directory deletions.
    """
    command = recommendation.command.strip()

    if _is_destructive(command):
        return AllowlistVerdict(
            allowed=False,
            reason=f"destructive command rejected by policy: {command!r}",
        )

    lowered = command.lower()

    if command in _UNCONDITIONALLY_SAFE or lowered in _UNCONDITIONALLY_SAFE:
        return AllowlistVerdict(
            allowed=True,
            reason="unconditionally safe read-only command",
            action=RepairAction(command=command, context=dict(recommendation.context)),
        )

    if lowered == "auto":
        plan_name = recommendation.context.get("plan_name") or context.get("plan_name")
        state = recommendation.context.get("state") or context.get("state")
        recoverable = (
            context.get("block_details", {}).get("recoverable_via")
            or recommendation.context.get("block_details", {}).get("recoverable_via")
        )
        if plan_name and state and recoverable:
            return AllowlistVerdict(
                allowed=True,
                reason="auto allowed with plan_name, state, and recoverable_via",
                action=RepairAction(command=command, context=dict(recommendation.context)),
            )
        return AllowlistVerdict(
            allowed=False,
            reason="auto requires plan_name, state, and block_details.recoverable_via",
        )

    if lowered == "resume":
        plan_name = recommendation.context.get("plan_name") or context.get("plan_name")
        is_resumable = context.get("is_resumable") or recommendation.context.get("is_resumable")
        if plan_name and is_resumable:
            return AllowlistVerdict(
                allowed=True,
                reason="resume allowed with plan_name and is_resumable",
                action=RepairAction(command=command, context=dict(recommendation.context)),
            )
        return AllowlistVerdict(
            allowed=False,
            reason="resume requires plan_name and is_resumable",
        )

    # Kill commands are allowed only when targeting a known orphan PID for this
    # plan and the target is not a global Claude daemon (too much collateral damage).
    kill_match = re.match(r"^kill(?:\s+-9)?\s+(\d+)$", command.strip(), re.IGNORECASE)
    if kill_match:
        target_pid = int(kill_match.group(1))
        orphan_pids = context.get("orphan_pids") or recommendation.context.get("orphan_pids") or []
        if target_pid not in orphan_pids:
            return AllowlistVerdict(
                allowed=False,
                reason=f"kill target {target_pid} is not a known orphan pid for this plan",
            )
        if recommendation.context.get("target_category") == "claude":
            return AllowlistVerdict(
                allowed=False,
                reason="killing global Claude daemon processes is not allowed",
            )
        return AllowlistVerdict(
            allowed=True,
            reason=f"kill allowed for orphan pid {target_pid}",
            action=RepairAction(command=command, context=dict(recommendation.context)),
        )

    # Clean up a stale lock file for this plan.
    clean_match = re.match(r"^rm\s+(\S+\.plan\.lock)$", command.strip(), re.IGNORECASE)
    if clean_match:
        lock_path = Path(clean_match.group(1)).resolve()
        plan_dir = Path(context.get("plan_dir") or recommendation.context.get("plan_dir") or ".").resolve()
        if _path_contains(plan_dir, lock_path):
            return AllowlistVerdict(
                allowed=True,
                reason=f"stale lock cleanup allowed inside plan dir: {lock_path}",
                action=RepairAction(command=command, context=dict(recommendation.context)),
            )
        return AllowlistVerdict(
            allowed=False,
            reason=f"lock path {lock_path} is outside plan dir {plan_dir}",
        )

    if lowered.startswith("chain start"):
        chain_spec_path = recommendation.context.get("chain_spec_path") or context.get("chain_spec_path")
        has_pending = context.get("has_pending_milestones") or recommendation.context.get("has_pending_milestones")
        if chain_spec_path and has_pending:
            return AllowlistVerdict(
                allowed=True,
                reason="chain start allowed with chain_spec_path and pending milestones",
                action=RepairAction(command=command, context=dict(recommendation.context)),
            )
        return AllowlistVerdict(
            allowed=False,
            reason="chain start requires chain_spec_path and has_pending_milestones",
        )

    return AllowlistVerdict(
        allowed=False,
        reason=f"command not in allowlist: {command!r}",
    )


__all__ = [
    "classify_incident",
    "enforce_allowlist",
    "normalize_doctor_findings",
]
