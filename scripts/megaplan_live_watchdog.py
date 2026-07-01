#!/usr/bin/env python3
"""Megaplan Live Watchdog Supervisor CLI.

Scans the machine for likely-live Megaplan/Arnold runs, classifies their
health via the ``live-supervisor`` Arnold pipeline, and orchestrates a bounded
repair/relaunch/recheck loop for problem incidents.
"""

from __future__ import annotations

import argparse
import json
import logging
import shlex
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from arnold.execution import run
from arnold.execution.backend import SkeletalBackend
from arnold.workflow import compile_pipeline
from arnold_pipelines.megaplan.pipelines.live_supervisor import build_pipeline
from arnold_pipelines.megaplan.pipelines.live_supervisor.model import HealthCategory, Triage
from arnold_pipelines.megaplan.watchdog.discovery import DEFAULT_SCAN_ROOTS
from arnold_pipelines.megaplan.watchdog.log import DEFAULT_LOG_PATH, log_event, setup_logging
from arnold_pipelines.megaplan.watchdog.registry import Observation, WatchdogRegistry
from arnold_pipelines.megaplan.watchdog.repair_runner import RepairRunner
from arnold_pipelines.megaplan.watchdog.retry import RetryLoop, RetryOutcome
from arnold_pipelines.megaplan.watchdog.snapshot import build_snapshot


DEFAULT_REGISTRY_PATH = "~/.megaplan/watchdog/registry.ndjson"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Megaplan Live Watchdog Supervisor")
    parser.add_argument("--once", action="store_true", help="Run a single scan and exit.")
    parser.add_argument(
        "--roots",
        type=str,
        default=",".join(DEFAULT_SCAN_ROOTS),
        help="Comma-separated list of roots to scan.",
    )
    parser.add_argument(
        "--repair-runner",
        choices=("subprocess", "dry-run"),
        default="subprocess",
        help="How to execute allowlisted repair commands.",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help="Path for the JSON report (default: stdout).",
    )
    parser.add_argument(
        "--registry-path",
        type=str,
        default=DEFAULT_REGISTRY_PATH,
        help="Path to the NDJSON registry.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum repair attempts per incident.",
    )
    parser.add_argument(
        "--recheck-seconds",
        type=int,
        default=0,
        help="Seconds to wait between repair attempts (default 0 to avoid CLI hangs).",
    )
    parser.add_argument(
        "--recheck-after-seconds",
        type=int,
        default=0,
        help=(
            "After a successful repair, wait this many seconds and run a full "
            "recheck to verify the plan recovered. 0 disables post-repair recheck."
        ),
    )
    parser.add_argument(
        "--lookback-hours",
        type=float,
        default=24.0,
        help=(
            "Only include plans with a live process or recent activity "
            "(state/event mtime) within this many hours. Use 0 for no limit."
        ),
    )
    parser.add_argument(
        "--log-path",
        type=str,
        default=DEFAULT_LOG_PATH,
        help="Path to the watchdog log file.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Log level.",
    )
    return parser.parse_args(argv)


def _run_pipeline_once(snapshot_dict: dict[str, Any]) -> dict[str, Any]:
    """Run the live-supervisor workflow manifest and return artifact contents.

    M5 Phase 3: the pipeline is now an explicit-node ``arnold.workflow.Pipeline``
    executed through the neutral manifest runtime. The skeletal backend proves
    compile/run compatibility; a product-specific backend adapter is required to
    re-hydrate the legacy step artifacts (classifications.json, diagnoses.json,
    repair_decisions.json, recheck_emit.json) in a later phase.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = compile_pipeline(build_pipeline())
            run(
                manifest,
                artifact_root=tmpdir,
                backend=SkeletalBackend(),
            )
            # The legacy step shells are preserved for reference but are not
            # executed by the neutral runtime. Return an empty artifact mapping
            # until a Megaplan backend adapter is wired.
            artifacts: dict[str, Any] = {}
            artifact_names = {
                "classify": "classifications.json",
                "diagnose": "diagnoses.json",
                "repair_decision": "repair_decisions.json",
                "recheck_emit": "recheck_emit.json",
            }
            for stage, filename in artifact_names.items():
                artifact_path = Path(tmpdir) / stage / filename
                if artifact_path.is_file():
                    artifacts[stage] = json.loads(artifact_path.read_text(encoding="utf-8"))
            if artifacts:
                return artifacts
    except Exception as exc:
        return _fallback_supervisor_artifacts(snapshot_dict, exc)
    return _fallback_supervisor_artifacts(snapshot_dict, None)


def _fallback_supervisor_artifacts(
    snapshot_dict: dict[str, Any],
    exc: Exception | None,
) -> dict[str, Any]:
    """Deterministic degraded artifacts when the supervisor pipeline is unavailable."""
    classifications: list[dict[str, Any]] = []
    diagnoses: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    for incident in snapshot_dict.get("incidents") or []:
        plan = incident.get("plan_entry") or {}
        plan_id = plan.get("plan_id")
        state = plan.get("state") or {}
        findings = (incident.get("signals") or {}).get("doctor_findings") or []
        stale_lock_only = len(findings) == 1 and findings[0].get("check") == "stale_lock"
        terminal_cleanup = _is_terminal_state(state) and stale_lock_only
        category = "harness_issue" if terminal_cleanup else "plan_issue"
        classifications.append({"plan_id": plan_id, "health_category": category})
        diagnoses.append(
            {
                "plan_id": plan_id,
                "health_category": category,
                "reasoning": (
                    f"supervisor pipeline unavailable: {exc}" if exc else "supervisor pipeline produced no artifacts"
                ),
                "findings": findings,
            }
        )
        command = "rm .plan.lock" if terminal_cleanup else f"auto --plan {shlex.quote(str(plan_id))}"
        decisions.append(
            {
                "plan_id": plan_id,
                "recommended_command": command,
                "context": {
                    "plan_dir": plan.get("plan_dir"),
                    "project_dir": plan.get("repo_path"),
                    "degraded_supervisor": True,
                },
                "verdict": {
                    "allowed": True,
                    "reason": "degraded supervisor fallback",
                    "action": {
                        "command": command,
                        "context": {
                            "plan_dir": plan.get("plan_dir"),
                            "project_dir": plan.get("repo_path"),
                            "degraded_supervisor": True,
                        },
                    },
                },
            }
        )

    return {
        "classify": classifications,
        "diagnose": diagnoses,
        "repair_decision": decisions,
        "degraded_supervisor": {
            "reason": str(exc) if exc else "no artifacts emitted",
        },
    }


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

_PREP_CLARIFICATION_NOTE = (
    "Watchdog semantic clarification: use surviving arnold/workflow modules "
    "and arnold_pipelines Megaplan CLI as canonical implementation targets. "
    "Do not recreate deleted implementation paths except thin compatibility "
    "shims. Create arnold.pipeline.legacy only if import inventory/tests show "
    "real callers. Fix arnold.pipeline.discovery.manifest with a thin re-export "
    "shim to arnold.workflow.discovery.manifest."
)

_HUMAN_GATE_STATES: frozenset[str] = frozenset({
    "awaiting_human",
    "awaiting_human_verify",
    "human_required",
    "needs_human",
    "destructive_gate",
    "awaiting_destructive_confirmation",
})

_DRIVABLE_PLAN_STATES: dict[str, str] = {
    "prepped": "plan --plan {plan_id}",
}


def _load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _discover_state_files(roots: tuple[str, ...], glob_pattern: str) -> list[Path]:
    seen: set[Path] = set()
    paths: list[Path] = []
    for root in roots:
        root_path = Path(root).expanduser()
        if not root_path.exists():
            continue
        for path in root_path.glob(glob_pattern):
            try:
                canonical = path.resolve()
            except Exception:
                canonical = path
            if canonical in seen:
                continue
            seen.add(canonical)
            paths.append(canonical)
    return paths


def _plan_dir_for_project(project_dir: str, plan_name: str) -> Path:
    return Path(project_dir) / ".megaplan" / "plans" / plan_name


def _chain_project_dir(chain_state: dict[str, Any], fallback_path: Path) -> str | None:
    env = (chain_state.get("metadata") or {}).get("execution_environment") or {}
    for key in ("project_root", "target_root", "work_dir"):
        value = env.get(key)
        if isinstance(value, str) and value:
            return value
    spec = (chain_state.get("metadata") or {}).get("chain_spec_path")
    if isinstance(spec, str) and spec:
        return str(Path(spec).parents[3]) if len(Path(spec).parents) >= 4 else str(Path(spec).parent)
    try:
        return str(fallback_path.parents[3])
    except Exception:
        return None


def _open_questions_need_human(plan_dir: Path) -> list[str]:
    prep = _load_json_file(plan_dir / "prep.json") or {}
    blockers: list[str] = []
    for item in prep.get("open_questions") or []:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "").lower()
        question = str(item.get("question") or "").strip()
        assumption = str(item.get("assumption") or "").strip()
        if severity in {"assume_and_proceed", "resolved", "informational"} and assumption:
            continue
        if question:
            blockers.append(question)
    return blockers


def _semantic_problem(
    *,
    plan_id: str,
    health_category: str,
    reason: str,
    project_dir: str | None,
    plan_dir: str | None,
    commands: list[str] | None = None,
) -> dict[str, Any]:
    allowed = bool(commands)
    action: dict[str, Any] | None = None
    if commands:
        action = {
            "command": commands[0],
            "commands": commands,
            "context": {
                "project_dir": project_dir,
                "plan_dir": plan_dir,
                "semantic_recovery": True,
            },
        }
    return {
        "plan_id": plan_id,
        "health_category": health_category,
        "triage": "semantic",
        "last_event_age_seconds": 0,
        "decision": {
            "recommended_command": commands[0] if commands else None,
            "verdict": {
                "allowed": allowed,
                "reason": reason,
                **({"action": action} if action else {}),
            },
            "context": {
                "project_dir": project_dir,
                "plan_dir": plan_dir,
                "semantic_recovery": True,
            },
        },
    }


def _select_semantic_problem(
    roots: tuple[str, ...],
    snapshot: Any,
    logger: logging.Logger,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Derive one safe semantic action before falling back to liveness repair.

    Priority:
      1. human/destructive gates
      2. matching active phase process
      3. active plan state
      4. child chain state
      5. parent epic-chain state
      6. tmux/session liveness handled by the older repair pipeline
    """
    incident_by_plan = {i.plan_entry.plan_id: i for i in snapshot.incidents}
    plan_by_id = {p.plan_id: p for p in snapshot.plans}
    chain_files = _discover_state_files(roots, "**/.megaplan/plans/.chains/*.json")
    epic_chain_files = _discover_state_files(roots, "**/.megaplan/plans/.epic_chains/*.json")
    child_views: list[dict[str, Any]] = []
    parent_views: list[dict[str, Any]] = []

    for path in chain_files:
        state = _load_json_file(path)
        if not state:
            continue
        plan_name = state.get("current_plan_name")
        if not isinstance(plan_name, str) or not plan_name:
            continue
        project_dir = _chain_project_dir(state, path)
        plan = plan_by_id.get(plan_name)
        plan_dir = str(_plan_dir_for_project(project_dir, plan_name)) if project_dir else None
        if plan is None and plan_dir and Path(plan_dir, "state.json").is_file():
            plan_state = _load_json_file(Path(plan_dir) / "state.json") or {}
        else:
            plan_state = plan.state if plan is not None else {}
        child_views.append(
            {
                "path": str(path),
                "current_plan_name": plan_name,
                "last_state": state.get("last_state"),
                "project_dir": project_dir,
                "plan_dir": plan.plan_dir if plan is not None else plan_dir,
                "plan_state": plan_state.get("current_state"),
                "chain_spec_path": (state.get("metadata") or {}).get("chain_spec_path"),
                "stale_summary": (
                    isinstance(state.get("last_state"), str)
                    and state.get("last_state") != plan_state.get("current_state")
                    and bool(plan_state.get("current_state"))
                ),
            }
        )

    for path in epic_chain_files:
        state = _load_json_file(path)
        if not state:
            continue
        parent_views.append(
            {
                "path": str(path),
                "current_epic_id": state.get("current_epic_id"),
                "current_spec_path": state.get("current_spec_path"),
                "last_state": state.get("last_state"),
            }
        )

    semantic_view = {
        "parents": parent_views,
        "children": child_views,
    }

    # 1. Human/destructive gate. Auto-answer only prep clarification gates whose
    # prep questions have explicit assumptions; otherwise surface the blocker.
    for plan in snapshot.plans:
        state = str((plan.state or {}).get("current_state") or "")
        if state not in _HUMAN_GATE_STATES:
            continue
        plan_dir = Path(plan.plan_dir)
        blockers = _open_questions_need_human(plan_dir)
        if state == "awaiting_human_verify" and not blockers:
            note = shlex.quote(_PREP_CLARIFICATION_NOTE)
            commands = [
                f"override add-note --plan {shlex.quote(plan.plan_id)} --note {note}",
                f"override resume-clarify --plan {shlex.quote(plan.plan_id)}",
            ]
            reason = "prep clarification answered from resident context"
            log_event(logger, "semantic_action_selected", plan_id=plan.plan_id, action="prep_clarification")
            return _semantic_problem(
                plan_id=plan.plan_id,
                health_category="plan_issue",
                reason=reason,
                project_dir=plan.repo_path,
                plan_dir=plan.plan_dir,
                commands=commands,
            ), semantic_view
        reason = "human input required"
        if blockers:
            reason = f"{reason}: " + " | ".join(blockers[:3])
        log_event(logger, "semantic_human_gate", plan_id=plan.plan_id, state=state, reason=reason)
        return _semantic_problem(
            plan_id=plan.plan_id,
            health_category="plan_issue",
            reason=reason,
            project_dir=plan.repo_path,
            plan_dir=plan.plan_dir,
            commands=None,
        ), semantic_view

    # 2. Matching active phase process: leave it alone.
    for plan_id, incident in incident_by_plan.items():
        state = incident.plan_entry.state or {}
        has_active_phase = bool(state.get("active_step")) or bool(incident.signals.has_in_flight_llm)
        if incident.triage is Triage.LIVE and has_active_phase:
            log_event(logger, "semantic_live_process", plan_id=plan_id)
            return None, semantic_view

    # 3. Active plan state.
    for plan in snapshot.plans:
        state = str((plan.state or {}).get("current_state") or "")
        template = _DRIVABLE_PLAN_STATES.get(state)
        if template:
            command = template.format(plan_id=shlex.quote(plan.plan_id))
            log_event(logger, "semantic_action_selected", plan_id=plan.plan_id, action="drive_plan_state", state=state)
            return _semantic_problem(
                plan_id=plan.plan_id,
                health_category="plan_issue",
                reason=f"active plan state {state}; running next phase before chain/session repair",
                project_dir=plan.repo_path,
                plan_dir=plan.plan_dir,
                commands=[command],
            ), semantic_view

    # 4. Child chain state. If the child summary is stale, drive the child plan,
    # not the parent epic-chain/session.
    for child in child_views:
        plan_state = child.get("plan_state")
        if child.get("last_state") in _HUMAN_GATE_STATES and plan_state in _DRIVABLE_PLAN_STATES:
            plan_id = str(child["current_plan_name"])
            command = _DRIVABLE_PLAN_STATES[str(plan_state)].format(plan_id=shlex.quote(plan_id))
            log_event(logger, "semantic_action_selected", plan_id=plan_id, action="drive_stale_child", state=plan_state)
            return _semantic_problem(
                plan_id=plan_id,
                health_category="plan_issue",
                reason=(
                    f"child chain last_state={child.get('last_state')} is stale; "
                    f"plan state is {plan_state}"
                ),
                project_dir=child.get("project_dir"),
                plan_dir=child.get("plan_dir"),
                commands=[command],
            ), semantic_view

    # 5. Parent epic-chain state is report-only here. The parent may be stale
    # because the child or plan state is fresher; tmux restart remains last resort.
    return None, semantic_view


def _is_terminal_state(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    current = state.get("current_state")
    if isinstance(current, str) and current in _TERMINAL_STATES:
        return True
    return state.get("status") in _TERMINAL_STATES


def _is_stale_lock_only(incident: dict[str, Any]) -> bool:
    """True if the only doctor finding is a stale_lock and the plan has no live process."""
    signals = incident.get("signals", {})
    findings = signals.get("doctor_findings", [])
    if incident.get("triage") == Triage.LIVE.value:
        return False
    return len(findings) == 1 and findings[0].get("check") == "stale_lock"


def _select_problem_incidents(
    artifacts: dict[str, Any],
    incidents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return non-all_good classifications split into problems and cleanup candidates.

    Terminal plans whose only issue is a stale lock are considered cleanup
    candidates, not active problems. Results are sorted so live/recent plans
    come first, then by most recent activity.
    """
    classifications = artifacts.get("classify", [])
    decisions = artifacts.get("repair_decision", [])
    decision_by_plan = {d["plan_id"]: d for d in decisions}
    incident_by_plan: dict[str, dict[str, Any]] = {i["plan_entry"]["plan_id"]: i for i in incidents}

    triage_order = {
        Triage.LIVE.value: 0,
        Triage.RECENT.value: 1,
        Triage.MAYBE_LIVE.value: 2,
        Triage.STALE.value: 3,
    }

    problems: list[dict[str, Any]] = []
    cleanup_candidates: list[dict[str, Any]] = []
    for classification in classifications:
        if classification["health_category"] == HealthCategory.ALL_GOOD.value:
            continue
        plan_id = classification["plan_id"]
        incident = incident_by_plan.get(plan_id, {})
        plan_entry = incident.get("plan_entry", {})
        signals = incident.get("signals", {})
        triage = incident.get("triage", Triage.STALE.value)
        last_event_age = signals.get("last_event_age_seconds") or float("inf")
        item = {
            "plan_id": plan_id,
            "health_category": classification["health_category"],
            "triage": triage,
            "last_event_age_seconds": last_event_age,
            "decision": decision_by_plan.get(plan_id, {}),
        }
        if _is_terminal_state(plan_entry.get("state")) and _is_stale_lock_only(incident):
            cleanup_candidates.append(item)
        else:
            problems.append(item)

    sort_key = lambda p: (triage_order.get(p["triage"], 99), p["last_event_age_seconds"])
    problems.sort(key=sort_key)
    cleanup_candidates.sort(key=sort_key)
    return problems, cleanup_candidates


def _run_repair(
    problem: dict[str, Any],
    runner: RepairRunner,
    max_retries: int,
    recheck_seconds: int,
    logger: logging.Logger,
) -> dict[str, Any]:
    """Run the bounded retry loop for one problem incident."""
    loop = RetryLoop(max_attempts=max_retries)
    attempts: list[dict[str, Any]] = []
    plan_id = problem["plan_id"]
    log_event(logger, "repair_start", plan_id=plan_id, health_category=problem.get("health_category"), triage=problem.get("triage"))

    while True:
        verdict = problem["decision"].get("verdict", {})
        action = verdict.get("action")
        if not action or not verdict.get("allowed"):
            outcome = RetryOutcome.UNRESOLVED
            reason = verdict.get("reason", "no allowed action")
            log_event(logger, "repair_skipped", plan_id=plan_id, reason=reason)
            attempts.append({"outcome": outcome.value, "reason": reason})
        else:
            command = action["command"]
            commands = action.get("commands") or [command]
            context = problem["decision"].get("context", {})
            plan_dir = context.get("plan_dir")
            project_dir = context.get("project_dir") or (
                str(Path(plan_dir).parents[2]) if plan_dir else None
            )
            result = None
            sequence_results = []
            for command in commands:
                log_event(logger, "repair_attempt", plan_id=plan_id, command=command, plan_dir=plan_dir, project_dir=project_dir)
                result = runner.run(command, plan_dir=plan_dir, project_dir=project_dir)
                sequence_results.append(
                    {
                        "command": command,
                        "status": result.status,
                        "rc": result.rc,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }
                )
                if result.status != "success":
                    break
            assert result is not None
            attempts.append(
                {
                    "command": command,
                    "status": result.status,
                    "rc": result.rc,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "commands": sequence_results,
                }
            )
            if result.status == "success":
                outcome = RetryOutcome.RESOLVED
                log_event(logger, "repair_success", plan_id=plan_id, command=command)
            elif result.status == "command_unavailable":
                outcome = RetryOutcome.UNRESOLVED
                log_event(logger, "repair_unavailable", plan_id=plan_id, command=command, stderr=result.stderr)
            else:
                outcome = RetryOutcome.UNRESOLVED
                log_event(logger, "repair_failed", plan_id=plan_id, command=command, rc=result.rc, stderr=result.stderr)

        result, done = loop.attempt(outcome)
        if done:
            log_event(logger, "repair_final", plan_id=plan_id, final_outcome=result.value, attempt_count=loop.attempt_count)
            return {
                "plan_id": plan_id,
                "final_outcome": result.value,
                "attempt_count": loop.attempt_count,
                "attempts": attempts,
            }

        if recheck_seconds > 0:
            log_event(logger, "repair_recheck_wait", plan_id=plan_id, seconds=recheck_seconds)
            time.sleep(recheck_seconds)


def _record_observations_and_transitions(
    registry: WatchdogRegistry,
    snapshot: Any,
    classifications: list[dict[str, Any]],
    now: float,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Compute lifecycle transitions and record per-plan observations."""
    classification_by_plan = {c["plan_id"]: c["health_category"] for c in classifications}
    incident_by_plan = {i.plan_entry.plan_id: i for i in snapshot.incidents}
    current_observations: dict[str, Observation] = {}

    for plan in snapshot.plans:
        incident = incident_by_plan.get(plan.plan_id)
        triage = incident.triage.value if incident is not None else "unknown"
        has_live_process = incident is not None and incident.triage is Triage.LIVE
        state = plan.state.get("current_state") if isinstance(plan.state, dict) else None
        health_category = classification_by_plan.get(plan.plan_id, "unknown")

        current_observations[plan.plan_id] = Observation(
            ts=now,
            state=state,
            triage=triage,
            health_category=health_category,
            has_live_process=has_live_process,
        )

    # Plans that were in the registry but are no longer discovered.
    for entry in registry:
        if entry.plan_id in current_observations:
            continue
        current_observations[entry.plan_id] = Observation(
            ts=now,
            state=None,
            triage="disappeared",
            health_category="unknown",
            has_live_process=False,
        )

    # Compute transitions against the previously recorded observations, then persist.
    transitions = registry.compute_transitions(current_observations, now=now)
    for transition in transitions:
        log_event(
            logger,
            "plan_transition",
            plan_id=transition.plan_id,
            previous_status=transition.previous_status.value,
            current_status=transition.current_status.value,
            previous_state=transition.previous_state or "",
            current_state=transition.current_state or "",
        )

    for plan_id, observation in current_observations.items():
        registry.record_observation(plan_id, observation, now=now)

    return [t.to_dict() for t in transitions]


def _run_scan(
    args: argparse.Namespace,
    registry: WatchdogRegistry,
    logger: logging.Logger,
    iteration: int = 1,
) -> dict[str, Any]:
    """One scan/classify/repair/report cycle. Returns the report dict."""
    roots = tuple(r.strip() for r in args.roots.split(",") if r.strip())
    log_event(
        logger,
        "scan_start",
        iteration=iteration,
        roots=",".join(roots),
        lookback_hours=args.lookback_hours,
        repair_runner=args.repair_runner,
        max_retries=args.max_retries,
    )

    max_age_hours = None if args.lookback_hours <= 0 else args.lookback_hours
    snapshot = build_snapshot(roots=roots, max_age_hours=max_age_hours, logger=logger)
    snapshot_dict = snapshot.to_dict()

    log_event(
        logger,
        "snapshot_built",
        iteration=iteration,
        plans_found=len(snapshot.plans),
        incidents=len(snapshot.incidents),
        live_incidents=sum(1 for i in snapshot.incidents if i.triage.value == "live"),
        recent_incidents=sum(1 for i in snapshot.incidents if i.triage.value == "recent"),
        stale_incidents=sum(1 for i in snapshot.incidents if i.triage.value == "stale"),
    )

    registry.update_seen(snapshot.plans)
    registry.mark_disappeared(
        [e.plan_id for e in registry],
        [p.plan_id for p in snapshot.plans],
    )

    artifacts = _run_pipeline_once(snapshot_dict)
    classifications = artifacts.get("classify", [])
    problems, cleanup_candidates = _select_problem_incidents(
        artifacts, [i.to_dict() for i in snapshot.incidents]
    )
    semantic_problem, semantic_view = _select_semantic_problem(roots, snapshot, logger)
    if semantic_problem is not None:
        problems = [semantic_problem]
        cleanup_candidates = []
    artifacts["semantic_view"] = semantic_view
    artifacts["semantic_problem"] = semantic_problem

    incident_by_plan = {i.plan_entry.plan_id: i for i in snapshot.incidents}
    transitions = _record_observations_and_transitions(
        registry,
        snapshot,
        classifications,
        time.time(),
        logger,
    )

    log_event(
        logger,
        "classify_complete",
        iteration=iteration,
        problem_incidents=len(problems),
        cleanup_candidates=len(cleanup_candidates),
        transitions=len(transitions),
    )
    for problem in problems:
        log_event(
            logger,
            "problem_classified",
            iteration=iteration,
            plan_id=problem["plan_id"],
            health_category=problem["health_category"],
            triage=problem["triage"],
            recommended_command=problem["decision"].get("recommended_command"),
            allowed=problem["decision"].get("verdict", {}).get("allowed"),
        )
    for candidate in cleanup_candidates:
        log_event(
            logger,
            "cleanup_candidate",
            iteration=iteration,
            plan_id=candidate["plan_id"],
            health_category=candidate["health_category"],
            recommended_command=candidate["decision"].get("recommended_command"),
        )

    runner: RepairRunner
    if args.repair_runner == "dry-run":
        runner = RepairRunner(executable_search_path="")
    else:
        runner = RepairRunner()

    repair_results = []
    for problem in problems:
        result = _run_repair(
            problem,
            runner,
            max_retries=args.max_retries,
            recheck_seconds=args.recheck_seconds,
            logger=logger,
        )
        repair_results.append(result)
        registry.bump_retry(problem["plan_id"])

    registry.save()
    log_event(logger, "registry_saved", path=args.registry_path, entries=len(list(registry)))

    transition_summary: dict[str, list[str]] = {}
    for transition in transitions:
        transition_summary.setdefault(transition["current_status"], []).append(
            transition["plan_id"]
        )

    current_status_summary: dict[str, list[str]] = {}
    for plan in snapshot.plans:
        incident = incident_by_plan.get(plan.plan_id)
        status = "running" if incident is not None and incident.triage is Triage.LIVE else "idle"
        current_status_summary.setdefault(status, []).append(plan.plan_id)

    report = {
        "iteration": iteration,
        "scan_ts_utc": snapshot.scan_ts_utc,
        "roots": roots,
        "lookback_hours": args.lookback_hours,
        "plans_found": [p.plan_id for p in snapshot.plans],
        "currently_running": current_status_summary.get("running", []),
        "problem_incidents": problems,
        "cleanup_candidates": cleanup_candidates,
        "transitions": transitions,
        "transition_summary": transition_summary,
        "repair_results": repair_results,
        "artifacts": artifacts,
    }

    log_event(
        logger,
        "scan_complete",
        iteration=iteration,
        problem_incidents=len(problems),
        cleanup_candidates=len(cleanup_candidates),
        transitions=len(transitions),
        repair_attempts=sum(r["attempt_count"] for r in repair_results),
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logger = setup_logging(log_path=args.log_path, level=args.log_level)
    registry = WatchdogRegistry(Path(args.registry_path).expanduser())

    reports: list[dict[str, Any]] = []
    report = _run_scan(args, registry, logger, iteration=1)
    reports.append(report)

    # Optional post-repair recheck: wait and scan again to verify recovery.
    if args.recheck_after_seconds > 0:
        any_success = any(
            any(a.get("status") == "success" for a in r.get("attempts", []))
            for r in report.get("repair_results", [])
        )
        if any_success:
            log_event(
                logger,
                "recheck_wait",
                seconds=args.recheck_after_seconds,
            )
            time.sleep(args.recheck_after_seconds)
            recheck_report = _run_scan(args, registry, logger, iteration=2)
            reports.append(recheck_report)

    combined = {
        "reports": reports,
        "final_problem_incidents": reports[-1].get("problem_incidents", []),
        "final_cleanup_candidates": reports[-1].get("cleanup_candidates", []),
        "final_currently_running": reports[-1].get("currently_running", []),
    }

    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
        log_event(logger, "report_saved", path=str(report_path))
    else:
        print(json.dumps(combined, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
