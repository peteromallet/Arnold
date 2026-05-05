#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from megaplan.types import (
    CliError,
    DEFAULT_AGENT_ROUTING,
    DEFAULTS,
    KNOWN_AGENTS,
    ROBUSTNESS_LEVELS,
    StepResponse,
    TERMINAL_STATES,
    _SETTABLE_BOOL,
    _SETTABLE_ENUM,
    _SETTABLE_NUMERIC,
)
from megaplan._core import (
    active_plan_dirs,
    add_or_increment_debt,
    atomic_write_text,
    build_next_step_runtime,
    build_phase_observability,
    compute_global_batches,
    config_dir,
    detect_available_agents,
    escalated_subsystems,
    ensure_runtime_layout,
    get_effective,
    has_any_plan_root,
    infer_next_steps,
    is_prose_mode,
    json_dump,
    load_config,
    load_debt_registry,
    load_plan,
    plan_lock_is_held,
    read_json,
    resolve_debt,
    resolve_plan_dir,
    resume_plan,
    save_debt_registry,
    save_config,
    subsystem_occurrence_total,
    humanize_seconds,
)
from megaplan.execute.core import build_monitor_hint
from megaplan.forms import available_form_ids
from megaplan.handlers import (
    handle_audit_verifiability,
    handle_critique,
    handle_execute,
    handle_finalize,
    handle_gate,
    handle_init,
    handle_override,
    handle_plan,
    handle_prep,
    handle_review,
    handle_revise,
    handle_tiebreaker_run,
    handle_verify_human,
)
from megaplan.loop.handlers import (
    handle_loop_init,
    handle_loop_pause,
    handle_loop_run,
    handle_loop_status,
)
from megaplan.profiles import (
    load_profile_sources,
    load_profiles,
    resolve_profile,
)
from megaplan.step_edit import handle_step

_PROGRESS_PHASE_COMMANDS = {"plan", "prep", "critique", "revise", "gate", "finalize", "execute", "review"}


def render_response(response: StepResponse, *, exit_code: int = 0) -> int:
    if isinstance(response, str):
        print(response, end="")
        return exit_code
    print(json_dump(response), end="")
    return exit_code


def _resolve_error_plan_dir(root: Path | None, error: CliError) -> Path | None:
    if root is None or error.code != "plan_locked" or not isinstance(error.extra, dict):
        return None
    plan_name = error.extra.get("plan")
    if not isinstance(plan_name, str) or not plan_name:
        return None
    try:
        return resolve_plan_dir(root, plan_name)
    except CliError:
        return None


def _augment_plan_locked_error(
    payload: StepResponse,
    error: CliError,
    *,
    root: Path | None,
) -> None:
    plan_dir = _resolve_error_plan_dir(root, error)
    details = payload.get("details")
    if not isinstance(details, dict):
        details = None
    plan_name = (details or {}).get("plan")
    if isinstance(plan_name, str) and plan_name:
        monitor_hint = build_monitor_hint(plan_dir or Path(plan_name))
        payload["monitor_hint"] = monitor_hint
        if details is not None:
            details["monitor_hint"] = monitor_hint
    raw_active_step = (details or {}).get("active_step")
    if isinstance(raw_active_step, dict):
        active_step = (
            _build_active_step(raw_active_step, plan_dir=plan_dir)
            if plan_dir is not None
            else dict(raw_active_step)
        )
        payload["active_step"] = active_step
        if details is not None:
            details["active_step"] = active_step


def error_response(error: CliError, *, root: Path | None = None) -> int:
    payload: StepResponse = {
        "success": False,
        "error": error.code,
        "message": error.message,
    }
    if error.valid_next:
        payload["valid_next"] = error.valid_next
    if error.extra:
        payload["details"] = dict(error.extra)
    if error.code == "plan_locked":
        _augment_plan_locked_error(payload, error, root=root)
    return render_response(payload, exit_code=error.exit_code)


def _emit_response_progress(command: str, response: StepResponse, emitter: Any) -> None:
    if command not in _PROGRESS_PHASE_COMMANDS or not isinstance(response, dict):
        return
    state = response.get("state")
    step = str(response.get("step") or command)
    emitter.phase_end(
        step,
        success=bool(response.get("success", True)),
        state=state,
        result=response.get("result"),
        next_step=response.get("next_step"),
    )
    if state == "done":
        emitter.plan_done(summary=str(response.get("summary") or "Plan complete"), phase=step)
    elif state == "failed":
        emitter.plan_failed(summary=str(response.get("summary") or "Plan failed"), phase=step)
    elif state == "blocked":
        emitter.execution_blocked(summary=str(response.get("summary") or "Execution blocked"), phase=step)


def _emit_error_progress(command: str, error: CliError, emitter: Any) -> None:
    if command not in _PROGRESS_PHASE_COMMANDS:
        return
    emitter.phase_end(command, success=False, error_code=error.code, message=error.message)


def _parse_utc_timestamp(timestamp: str | None) -> datetime | None:
    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_progress_payload(plan_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    finalize_path = plan_dir / "finalize.json"
    if not finalize_path.exists():
        return {
            "summary": "No finalize.json yet — plan has not been finalized.",
            "tasks_total": 0,
            "tasks_done": 0,
            "tasks_skipped": 0,
            "tasks_pending": 0,
            "tasks_blocked": 0,
            "batches_total": 0,
            "batches_completed": 0,
            "tasks": [],
        }
    finalize_data = read_json(finalize_path)
    global_batches = compute_global_batches(finalize_data)
    tasks = finalize_data.get("tasks", [])
    task_id_to_batch: dict[str, int] = {}
    for batch_idx, batch_ids in enumerate(global_batches, start=1):
        for task_id in batch_ids:
            task_id_to_batch[task_id] = batch_idx
    tasks_done = sum(1 for t in tasks if t.get("status") == "done")
    tasks_skipped = sum(1 for t in tasks if t.get("status") == "skipped")
    tasks_pending = sum(1 for t in tasks if t.get("status") == "pending")
    tasks_blocked = sum(1 for t in tasks if t.get("status") == "blocked")
    tasks_total = len(tasks)
    completed_ids = {
        t["id"] for t in tasks if t.get("status") in {"done", "skipped"} and isinstance(t.get("id"), str)
    }
    batches_completed = sum(
        1
        for batch_ids in global_batches
        if all(tid in completed_ids for tid in batch_ids)
    )
    task_status_list = [
        {
            "id": t.get("id", ""),
            "status": t.get("status", "pending"),
            "batch": task_id_to_batch.get(t.get("id", ""), 0),
        }
        for t in tasks
    ]
    return {
        "summary": (
            f"Execution progress: {tasks_done + tasks_skipped}/{tasks_total} tasks tracked, "
            f"{batches_completed}/{len(global_batches)} batches completed. "
            "Progress reflects the last finalize.json write (between-batch granularity)."
        ),
        "tasks_total": tasks_total,
        "tasks_done": tasks_done,
        "tasks_skipped": tasks_skipped,
        "tasks_pending": tasks_pending,
        "tasks_blocked": tasks_blocked,
        "batches_total": len(global_batches),
        "batches_completed": batches_completed,
        "tasks": task_status_list,
    }


def _build_last_step(state: dict[str, Any]) -> dict[str, Any] | None:
    history = state.get("history", [])
    if not isinstance(history, list) or not history:
        return None
    last = history[-1]
    if not isinstance(last, dict):
        return None
    return {
        "step": last.get("step"),
        "result": last.get("result"),
        "timestamp": last.get("timestamp"),
        "agent": last.get("agent"),
        "output_file": last.get("output_file"),
    }


def _build_active_step(active_step: Any, *, plan_dir: Path) -> dict[str, Any] | None:
    if not isinstance(active_step, dict):
        return None
    details = dict(active_step)
    step = details.get("step")
    if not isinstance(step, str) or not step:
        return details
    configured_timeout_seconds = int(get_effective("execution", "worker_timeout_seconds"))
    lock_held = plan_lock_is_held(plan_dir)
    started_at = _parse_utc_timestamp(details.get("started_at"))
    if started_at is not None:
        age_seconds = max(0, int((datetime.now(timezone.utc) - started_at).total_seconds()))
        details.update(
            build_phase_observability(
                step,
                configured_timeout_seconds=configured_timeout_seconds,
                age_seconds=age_seconds,
                lock_held=lock_held,
            )
        )
        if details.get("stale"):
            orphaned = not lock_held
            details["orphaned"] = orphaned
            if orphaned:
                if step == "execute":
                    details["recovery_hint"] = (
                        "The active step is stale and no process holds the plan lock. "
                        "Safe next action: rerun the same execute command on Codex without --fresh."
                    )
                else:
                    details["recovery_hint"] = (
                        "The active step is stale and no process holds the plan lock. "
                        "Safe next action: rerun the same step on the same agent before escalating."
                    )
        max_seconds = int(details.get("expected_duration_seconds", {}).get("max", 0) or 0)
        elapsed_label = humanize_seconds(age_seconds)
        if details.get("stale"):
            details["phase_progress_summary"] = (
                f"{step} stale ({elapsed_label} elapsed, expected max {humanize_seconds(max_seconds)}) "
                "see recovery_hint."
            )
        elif step in {"execute", "loop_execute"}:
            details["phase_progress_summary"] = (
                f"{step} running ({elapsed_label} elapsed, use progress for batch-level detail)."
            )
        else:
            details["phase_progress_summary"] = (
                f"{step} running ({elapsed_label} elapsed, typically completes within "
                f"{humanize_seconds(max_seconds)})."
            )
            if max_seconds > 0:
                details["progress_pct"] = min(95, int((age_seconds / max_seconds) * 100))
    else:
        details.update(
            build_phase_observability(
                step,
                configured_timeout_seconds=configured_timeout_seconds,
                lock_held=lock_held,
            )
        )
        if step in {"execute", "loop_execute"}:
            details["phase_progress_summary"] = (
                f"{step} active (start time unknown, use progress for batch-level detail)."
            )
        else:
            details["phase_progress_summary"] = f"{step} active (start time unknown)."
    return details


def _build_status_payload(plan_dir: Path, state: dict[str, Any]) -> StepResponse:
    next_steps = infer_next_steps(state)
    notes = state.get("meta", {}).get("notes", [])
    lock_path = plan_dir / ".plan.lock"
    lock_file_present = lock_path.exists()
    lock_held = plan_lock_is_held(plan_dir)
    active_step = _build_active_step(state.get("active_step"), plan_dir=plan_dir)
    last_step = _build_last_step(state)
    plan_mode = state.get("config", {}).get("mode", "code")
    plan_output_path = state.get("config", {}).get("output_path")
    summary = f"Plan '{state['name']}' is currently in state '{state['current_state']}'."
    if is_prose_mode(state):
        summary += f" Mode: {plan_mode}. Output: {plan_output_path}."
    if active_step:
        summary = (
            summary
            + f" Active step: {active_step.get('step')} via {active_step.get('agent')}."
        )
    elif lock_file_present and not lock_held:
        summary = (
            summary
            + " No active step. The `.plan.lock` file may remain on disk even when no process holds the lock."
        )
    response: StepResponse = {
        "success": True,
        "step": "status",
        "plan": state["name"],
        "state": state["current_state"],
        "iteration": state["iteration"],
        "summary": summary,
        "next_step": next_steps[0] if next_steps else None,
        "valid_next": next_steps,
        "artifacts": sorted(
            path.name
            for path in plan_dir.iterdir()
            if path.is_file() and path.name != ".plan.lock"
        ),
        "lock_file_present": lock_file_present,
        "lock_held": lock_held,
        "active_step": active_step,
        "last_step": last_step,
        "total_cost_usd": state.get("meta", {}).get("total_cost_usd", 0.0),
        "mode": plan_mode,
        "output_path": plan_output_path,
        "notes_count": len(notes) if isinstance(notes, list) else 0,
        "notes": notes if isinstance(notes, list) else [],
        "session_summaries": [
            {"key": key, **value}
            for key, value in sorted(state.get("sessions", {}).items())
            if isinstance(value, dict)
        ],
    }
    runtime = build_next_step_runtime(
        response.get("next_step"),
        configured_timeout_seconds=int(get_effective("execution", "worker_timeout_seconds")),
    )
    if runtime is not None:
        response["next_step_runtime"] = runtime
    progress = _build_progress_payload(plan_dir, state) if (plan_dir / "finalize.json").exists() else None
    if progress is not None:
        response["progress"] = progress
        response["summary"] = response["summary"] + " " + progress["summary"]
    return response


def handle_status(root: Path, args: argparse.Namespace) -> StepResponse:
    if getattr(args, "pending_human", False):
        items = []
        for pd in active_plan_dirs(root):
            st = read_json(pd / "state.json")
            if st.get("current_state") == "awaiting_human_verify":
                items.append({"name": st["name"], "state": st["current_state"]})
        return {
            "success": True,
            "step": "status",
            "summary": f"Found {len(items)} plan(s) awaiting human verification.",
            "plans": items,
        }
    plan_dir, state = load_plan(root, args.plan)
    return _build_status_payload(plan_dir, state)


def handle_audit(root: Path, args: argparse.Namespace) -> StepResponse:
    if getattr(args, "audit_action", None) == "query":
        from megaplan.receipts.query import handle_audit_query

        return handle_audit_query(root, args)
    plan_dir, state = load_plan(root, args.plan)
    return {
        "success": True,
        "step": "audit",
        "plan": state["name"],
        "plan_dir": str(plan_dir),
        "state": state,
    }


def handle_progress(root: Path, args: argparse.Namespace) -> StepResponse:
    plan_dir, state = load_plan(root, args.plan)
    progress = _build_progress_payload(plan_dir, state)
    return {
        "success": True,
        "step": "progress",
        "plan": state["name"],
        **progress,
    }


def handle_watch(root: Path, args: argparse.Namespace) -> StepResponse:
    response = handle_status(root, args)
    response["step"] = "watch"
    return response


def _collect_megaplan_roots(root: Path, *, tree: bool = False, all_system: bool = False) -> list[Path]:
    """Collect .megaplan root directories based on search mode."""
    roots: list[Path] = [root]

    if all_system:
        # Search from home directory downward for all .megaplan directories
        home = Path.home()
        for megaplan_dir in sorted(home.rglob(".megaplan")):
            if megaplan_dir.is_dir() and (megaplan_dir / "plans").is_dir():
                candidate = megaplan_dir.parent
                if candidate.resolve() != root.resolve():
                    roots.append(candidate)
    elif tree:
        # Walk up to find parent .megaplan directories
        current = root.resolve().parent
        while True:
            if has_any_plan_root(current) and current.resolve() != root.resolve():
                roots.append(current)
            parent = current.parent
            if parent == current:
                break
            current = parent
        # Walk down to find child .megaplan directories
        for megaplan_dir in sorted(root.rglob(".megaplan")):
            if megaplan_dir.is_dir():
                candidate = megaplan_dir.parent
                if has_any_plan_root(candidate) and candidate.resolve() != root.resolve():
                    roots.append(candidate)

    return roots


def handle_list(root: Path, args: argparse.Namespace) -> StepResponse:
    ensure_runtime_layout(root)
    filter_status = getattr(args, "filter_status", None)
    no_tree = getattr(args, "no_tree", False)
    include_done = getattr(args, "include_done", False)
    show_summary = getattr(args, "summary", False)
    search_all = getattr(args, "all", False)
    # Default: tree=True (parent+child), active-only (exclude terminal plans)
    # --status overrides the active filter (explicit filter = show exactly that)
    search_tree = not no_tree and not search_all
    filter_active = not include_done and not filter_status

    roots = _collect_megaplan_roots(root, tree=search_tree, all_system=search_all)
    total_scanned = 0
    allowed_states: set[str] | None = None
    if filter_status:
        allowed_states = {s.strip() for s in filter_status.split(",")}

    items = []
    state_counts: dict[str, int] = {}
    resolved_root = root.resolve()
    for search_root in roots:
        resolved_search = search_root.resolve()
        is_local = resolved_search == resolved_root
        for plan_dir in active_plan_dirs(search_root):
            state = read_json(plan_dir / "state.json")
            current_state = state["current_state"]
            state_counts[current_state] = state_counts.get(current_state, 0) + 1
            total_scanned += 1

            if filter_active and current_state in TERMINAL_STATES:
                continue
            if allowed_states and current_state not in allowed_states:
                continue

            next_steps = infer_next_steps(state)
            entry = {
                "name": state["name"],
                "idea": state["idea"],
                "state": current_state,
                "iteration": state["iteration"],
                "next_step": next_steps[0] if next_steps else None,
            }
            if not is_local:
                try:
                    rel = resolved_search.relative_to(resolved_root)
                    entry["location"] = f"./{rel}"
                    entry["direction"] = "child"
                except ValueError:
                    try:
                        resolved_root.relative_to(resolved_search)
                        entry["location"] = os.path.relpath(resolved_search, resolved_root)
                        entry["direction"] = "parent"
                    except ValueError:
                        entry["location"] = str(resolved_search)
                        entry["direction"] = "external"
            items.append(entry)

    summary_parts = [f"Found {len(items)} plans"]
    if len(roots) > 1:
        summary_parts.append(f"across {len(roots)} directories")
    if allowed_states:
        summary_parts.append(f"matching {','.join(sorted(allowed_states))}")
    if filter_active:
        summary_parts.append("(active only)")

    result: StepResponse = {
        "success": True,
        "step": "list",
        "summary": f"{'. '.join(summary_parts)}.",
        "plans": items,
    }
    if show_summary:
        result["state_summary"] = dict(sorted(state_counts.items()))

    # Hints for discovering more plans
    hidden_done = total_scanned - len(items) if filter_active else 0
    hints: list[str] = []
    if hidden_done > 0:
        hints.append(f"{hidden_done} terminal plans hidden (use --include-done to show)")
    if not search_all:
        hints.append("Use --all to search all plans system-wide")
    if hints:
        result["hints"] = hints

    return result


def handle_debt(root: Path, args: argparse.Namespace) -> StepResponse:
    ensure_runtime_layout(root)
    action = args.debt_action
    registry = load_debt_registry(root)
    default_plan_id = getattr(args, "plan", None) or "manual"

    if action == "list":
        entries = registry["entries"] if args.all else [entry for entry in registry["entries"] if not entry["resolved"]]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            grouped.setdefault(entry["subsystem"], []).append(entry)
        escalated = {
            subsystem: total
            for subsystem, total, _entries in escalated_subsystems(registry)
        }
        by_subsystem = [
            {
                "subsystem": subsystem,
                "escalated": subsystem in escalated,
                "total_occurrences": subsystem_occurrence_total(entries_for_subsystem)
                if not args.all
                else sum(entry["occurrence_count"] for entry in entries_for_subsystem if not entry["resolved"]),
                "entries": entries_for_subsystem,
            }
            for subsystem, entries_for_subsystem in sorted(grouped.items())
        ]
        return {
            "success": True,
            "step": "debt",
            "action": "list",
            "summary": f"Found {len(entries)} debt entries across {len(by_subsystem)} subsystem groups.",
            "details": {
                "entries": entries,
                "by_subsystem": by_subsystem,
                "escalated_subsystems": [
                    {"subsystem": subsystem, "total_occurrences": total}
                    for subsystem, total in sorted(escalated.items())
                ],
            },
        }

    if action == "add":
        flag_ids = [
            flag_id.strip()
            for flag_id in (args.flag_ids or "").split(",")
            if flag_id.strip()
        ]
        entry = add_or_increment_debt(
            registry,
            subsystem=args.subsystem,
            concern=args.concern,
            flag_ids=flag_ids,
            plan_id=default_plan_id,
        )
        save_debt_registry(root, registry)
        return {
            "success": True,
            "step": "debt",
            "action": "add",
            "summary": f"Tracked debt entry {entry['id']} for subsystem '{entry['subsystem']}'.",
            "details": {"entry": entry},
        }

    if action == "resolve":
        entry = resolve_debt(registry, args.debt_id, default_plan_id)
        save_debt_registry(root, registry)
        return {
            "success": True,
            "step": "debt",
            "action": "resolve",
            "summary": f"Resolved debt entry {entry['id']}.",
            "details": {"entry": entry},
        }

    raise CliError("invalid_args", f"Unknown debt action: {action}")


# ---------------------------------------------------------------------------
# Setup and config
# ---------------------------------------------------------------------------

def _canonical_instructions() -> str:
    return resources.files("megaplan").joinpath("data", "instructions.md").read_text(encoding="utf-8")


_SKILL_HEADER = """\
---
name: megaplan
description: AI agent harness for coordinating Claude and GPT to make and execute extremely robust plans.
---

"""

_CURSOR_HEADER = """\
---
description: Use megaplan for high-rigor planning on complex, high-risk, or multi-stage tasks.
alwaysApply: false
---

"""


def bundled_agents_md() -> str:
    return _canonical_instructions()


def _subagent_appendix(filename: str) -> str:
    content = resources.files("megaplan").joinpath("data", filename).read_text(encoding="utf-8")
    content = content.replace(
        "{max_execute_no_progress}",
        str(get_effective("execution", "max_execute_no_progress")),
    )
    content = content.replace(
        "{max_review_rework_cycles}",
        str(get_effective("execution", "max_review_rework_cycles")),
    )
    return content


def _claude_subagent_appendix() -> str:
    return _subagent_appendix("claude_subagent_appendix.md")


def _codex_subagent_appendix() -> str:
    return _subagent_appendix("codex_subagent_appendix.md")


def bundled_global_file(name: str) -> str:
    content = _canonical_instructions()
    if name == "claude_skill.md":
        return _SKILL_HEADER + content + "\n\n" + _claude_subagent_appendix()
    if name == "codex_skill.md":
        return _SKILL_HEADER + content + "\n\n" + _codex_subagent_appendix()
    if name == "skill.md":
        return _SKILL_HEADER + content
    if name == "cursor_rule.mdc":
        return _CURSOR_HEADER + content
    return content


_GLOBAL_TARGETS = [
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan/SKILL.md", "data": "claude_skill.md"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan/SKILL.md", "data": "codex_skill.md"},
    {"agent": "cursor", "detect": ".cursor", "path": ".cursor/rules/megaplan.mdc", "data": "cursor_rule.mdc"},
]


def _install_owned_file(path: Path, content: str, *, force: bool = False) -> dict[str, bool | str]:
    existed = path.exists()
    if existed and not force:
        if path.read_text(encoding="utf-8") == content:
            return {"path": str(path), "skipped": True, "existed": True}
    atomic_write_text(path, content)
    return {"path": str(path), "skipped": False, "existed": existed}


def handle_setup_global(force: bool = False, home: Path | None = None) -> StepResponse:
    if home is None:
        home = Path.home()
    installed: list[dict[str, Any]] = []
    detected_count = 0
    for target in _GLOBAL_TARGETS:
        agent_dir = home / target["detect"]
        if not agent_dir.is_dir():
            installed.append({"agent": target["agent"], "path": str(home / target["path"]), "skipped": True, "reason": "not installed"})
            continue
        detected_count += 1
        result = _install_owned_file(home / target["path"], bundled_global_file(target["data"]), force=force)
        result["agent"] = target["agent"]
        installed.append(result)
    if detected_count == 0:
        return {
            "success": False, "step": "setup", "mode": "global",
            "summary": "No supported agents detected. Create one of ~/.claude/, ~/.codex/, or ~/.cursor/ and re-run.",
            "installed": installed,
        }
    available = detect_available_agents()
    config_path = None
    routing = None
    if available:
        agents_config = {step: (default if default in available else available[0]) for step, default in DEFAULT_AGENT_ROUTING.items()}
        config = load_config(home)
        config["agents"] = agents_config
        config_path = save_config(config, home)
        routing = agents_config
    lines = []
    for rec in installed:
        if rec.get("reason") == "not installed":
            lines.append(f"  {rec['agent']}: skipped (not installed)")
        elif rec["skipped"]:
            lines.append(f"  {rec['agent']}: up to date")
        else:
            lines.append(f"  {rec['agent']}: {'overwrote' if rec['existed'] else 'created'} {rec['path']}")
    result_data: dict[str, Any] = {"success": True, "step": "setup", "mode": "global", "summary": "Global setup complete:\n" + "\n".join(lines), "installed": installed}
    if config_path is not None:
        result_data["config_path"] = str(config_path)
        result_data["routing"] = routing
    return result_data


def handle_setup(args: argparse.Namespace) -> StepResponse:
    local = args.local or args.target_dir
    if not local:
        return handle_setup_global(force=args.force)
    target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
    target = target_dir / "AGENTS.md"
    content = bundled_agents_md()
    if target.exists() and not args.force:
        existing = target.read_text(encoding="utf-8")
        if "megaplan" in existing.lower():
            return {"success": True, "step": "setup", "summary": f"AGENTS.md already contains megaplan instructions at {target}", "skipped": True}
        atomic_write_text(target, existing + "\n\n" + content)
        return {"success": True, "step": "setup", "summary": f"Appended megaplan instructions to existing {target}", "file": str(target)}
    atomic_write_text(target, content)
    return {"success": True, "step": "setup", "summary": f"Created {target}", "file": str(target)}


def handle_config(args: argparse.Namespace) -> StepResponse:
    action = args.config_action
    if action == "show":
        config = load_config()
        effective_routing = {step: config.get("agents", {}).get(step, default) for step, default in DEFAULT_AGENT_ROUTING.items()}
        effective_settings = {
            dot_key: get_effective(section, setting)
            for dot_key in sorted(DEFAULTS)
            for section, setting in [dot_key.split(".", 1)]
        }
        return {
            "success": True,
            "step": "config",
            "action": "show",
            "config_path": str(config_dir() / "config.json"),
            "routing": effective_routing,
            "effective_settings": effective_settings,
            "raw_config": config,
        }
    if action == "set":
        key, value = args.key, args.value
        parts = key.split(".", 1)
        config = load_config()
        valid_keys = [
            *(f"agents.{step}" for step in DEFAULT_AGENT_ROUTING),
            "orchestration.mode",
            *sorted(_SETTABLE_BOOL),
            *sorted(_SETTABLE_ENUM),
            *sorted(_SETTABLE_NUMERIC),
        ]
        if len(parts) != 2:
            raise CliError(
                "invalid_args",
                f"Unknown config key '{key}'. Valid keys: {', '.join(valid_keys)}",
            )
        section, setting = parts
        normalized_value = value.strip().lower()
        if section == "agents":
            if setting not in DEFAULT_AGENT_ROUTING:
                raise CliError("invalid_args", f"Unknown step '{setting}'. Valid steps: {', '.join(DEFAULT_AGENT_ROUTING)}")
            if value not in KNOWN_AGENTS:
                raise CliError("invalid_args", f"Unknown agent '{value}'. Valid agents: {', '.join(KNOWN_AGENTS)}")
            config.setdefault("agents", {})[setting] = value
        elif key == "orchestration.mode":
            if value not in {"inline", "subagent"}:
                raise CliError("invalid_args", "orchestration.mode must be 'inline' or 'subagent'")
            config.setdefault("orchestration", {})["mode"] = value
        elif key in _SETTABLE_BOOL:
            if normalized_value in {"true", "1", "yes", "on"}:
                parsed_value = True
            elif normalized_value in {"false", "0", "no", "off"}:
                parsed_value = False
            else:
                raise CliError(
                    "invalid_args",
                    f"{key} must be one of: true, false, 1, 0, yes, no, on, off",
                )
            config.setdefault(section, {})[setting] = parsed_value
        elif key in _SETTABLE_ENUM:
            allowed_values = _SETTABLE_ENUM[key]
            if value not in allowed_values:
                raise CliError(
                    "invalid_args",
                    f"{key} must be one of: {', '.join(allowed_values)}",
                )
            config.setdefault(section, {})[setting] = value
        elif key in _SETTABLE_NUMERIC:
            try:
                parsed_value = int(value)
            except ValueError as exc:
                raise CliError("invalid_args", f"{key} must be an integer, got '{value}'") from exc
            config.setdefault(section, {})[setting] = parsed_value
        else:
            raise CliError(
                "invalid_args",
                f"Unknown config key '{key}'. Valid keys: {', '.join(valid_keys)}",
            )
        save_config(config)
        return {"success": True, "step": "config", "action": "set", "key": key, "value": config[section][setting]}
    if action == "profiles":
        project_dir = Path.cwd()
        profiles_action = args.profiles_action
        if profiles_action == "list":
            profiles = [
                {
                    "source": source_label,
                    "name": profile_name,
                    "phases": phase_map,
                }
                for source_label, profile_name, phase_map in load_profile_sources(project_dir=project_dir)
            ]
            return {
                "success": True,
                "step": "config",
                "action": "profiles",
                "profiles_action": "list",
                "project_dir": str(project_dir),
                "profiles": profiles,
            }
        if profiles_action == "show":
            profiles = load_profiles(project_dir=project_dir)
            resolved = resolve_profile(args.name, profiles)
            return {
                "success": True,
                "step": "config",
                "action": "profiles",
                "profiles_action": "show",
                "project_dir": str(project_dir),
                "name": args.name,
                "profile": resolved,
            }
        raise CliError("invalid_args", f"Unknown profiles action: {profiles_action}")
    if action == "reset":
        path = config_dir() / "config.json"
        if path.exists():
            path.unlink()
        return {"success": True, "step": "config", "action": "reset", "summary": "Config file removed. Using defaults."}
    raise CliError("invalid_args", f"Unknown config action: {action}")


# ---------------------------------------------------------------------------
# Store factory
# ---------------------------------------------------------------------------

def build_store(args: argparse.Namespace):
    """Return a DBStore configured for writes, or None for the file backend."""
    backend = getattr(args, "backend", None) or os.environ.get("MEGAPLAN_BACKEND")
    if backend == "db":
        from megaplan.store import DBStore, require_actor_id, resolve_actor_id, validate_actor_exists
        actor_id = require_actor_id(resolve_actor_id(args))
        store = DBStore(actor_id=actor_id)
        validate_actor_exists(store, actor_id)
        return store
    return None  # Sprint 3: write-back to DB


def build_epic_store(root: Path, *, actor_id: str | None = None):
    from megaplan.store import MultiStore

    return MultiStore.for_project(root, actor_id=actor_id)


def _jsonable_model(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _snapshot_payload(store: Any, epic_id: str) -> dict[str, Any]:
    epic = store.load_epic(epic_id)
    if epic is None:
        raise CliError("not_found", f"Epic {epic_id!r} not found")
    source = store._route_for_epic(epic_id)
    entities = store._migration_entities(source, epic_id)
    plan_artifacts: dict[str, list[dict[str, Any]]] = {}
    for plan_id, artifacts in entities["plan_artifacts"].items():
        plan_artifacts[plan_id] = [
            {
                "name": ref.name,
                "kind": ref.kind,
                "role": ref.role,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "content_text": data.decode("utf-8", errors="replace"),
            }
            for ref, data in artifacts
        ]
    return {
        "epic": _jsonable_model(entities["epic"]),
        "body": store.load_body(epic_id),
        "checklist_items": [_jsonable_model(row) for row in entities["checklist_items"]],
        "sprints": [_jsonable_model(row) for row in entities["sprints"]],
        "sprint_items": [_jsonable_model(row) for row in entities["sprint_items"]],
        "plans": [_jsonable_model(row) for row in entities["plans"]],
        "plan_artifacts_by_plan": plan_artifacts,
        "images": [_jsonable_model(row) for row in entities["images"]],
        "second_opinions": [_jsonable_model(row) for row in entities["second_opinions"]],
        "feedback": [_jsonable_model(row) for row in entities["feedback"]],
        "code_artifacts": [_jsonable_model(row) for row in entities["code_artifacts"]],
        "epic_events": [_jsonable_model(row) for row in entities["epic_events"]],
    }


def _snapshot_dir(epic_id: str) -> Path:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    return Path.home() / ".megaplan" / "snapshots" / f"{epic_id}-{timestamp}"


def handle_epic(root: Path, args: argparse.Namespace) -> StepResponse:
    action = args.epic_action
    if action == "snapshot":
        store = build_epic_store(root)
        try:
            payload = _snapshot_payload(store, args.epic_id)
        finally:
            close = getattr(store, "close", None)
            if callable(close):
                close()
        snapshot_dir = _snapshot_dir(args.epic_id)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / "snapshot.json"
        atomic_write_text(snapshot_path, json_dump(payload))
        return {
            "success": True,
            "step": "epic",
            "action": "snapshot",
            "epic_id": args.epic_id,
            "path": str(snapshot_path),
        }
    if action == "migrate":
        actor_id = getattr(args, "actor", None) or os.environ.get("MEGAPLAN_ACTOR_ID")
        if not actor_id:
            raise CliError(
                "missing_actor",
                "actor ID required for epic migration. Set MEGAPLAN_ACTOR_ID or pass --actor <id>.",
            )
        store = build_epic_store(root, actor_id=actor_id)
        try:
            warnings = store.warn_incomplete_migrations()
            if args.resume:
                if args.epic_id:
                    raise CliError("invalid_args", "epic migrate --resume does not accept an epic id")
                run = store.resume_migration(args.resume, ttl_seconds=args.ttl)
                migration_action = "resume"
            else:
                if not args.epic_id:
                    raise CliError("invalid_args", "epic migrate requires an epic id unless --resume is used")
                if not args.to:
                    raise CliError("invalid_args", "epic migrate requires --to file|db unless --resume is used")
                run = store.migrate_epic(args.epic_id, to=args.to, ttl_seconds=args.ttl)
                migration_action = "migrate"
        finally:
            close = getattr(store, "close", None)
            if callable(close):
                close()
        return {
            "success": True,
            "step": "epic",
            "action": migration_action,
            "migration_id": run.id,
            "phase": run.phase,
            "epic_id": run.epic_id,
            "source_backend": run.source_backend,
            "target_backend": run.target_backend,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "migration": run.model_dump(mode="json"),
            "warnings": warnings,
        }
    raise CliError("invalid_args", f"Unknown epic action: {action}")


def handle_resume(root: Path, args: argparse.Namespace) -> StepResponse:
    store = None
    if getattr(args, "actor", None) or getattr(args, "backend", None) == "db" or os.environ.get("MEGAPLAN_ACTOR_ID"):
        store = build_epic_store(root, actor_id=getattr(args, "actor", None) or os.environ.get("MEGAPLAN_ACTOR_ID"))
    try:
        return resume_plan(root, args.plan, store=store)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


# ---------------------------------------------------------------------------
# Parser and dispatch
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Megaplan orchestration CLI")
    parser.add_argument("--actor", default=None, metavar="ID", help="Actor ID for DB writes (also MEGAPLAN_ACTOR_ID)")
    parser.add_argument("--backend", choices=["file", "db"], default=None, help="Storage backend (also MEGAPLAN_BACKEND)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="Install megaplan into agent configs (global by default)")
    setup_parser.add_argument("--local", action="store_true", help="Install AGENTS.md into a project instead of global agent configs")
    setup_parser.add_argument("--target-dir", help="Directory to install into (default: cwd, implies --local)")
    setup_parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project-dir", required=True)
    init_parser.add_argument("--name")
    init_parser.add_argument("--auto-approve", action="store_true", default=None)
    init_parser.add_argument(
        "--strict-notes",
        action="store_true",
        default=None,
        help=(
            "Reject force-proceed while unabsorbed user notes exist; turn ESCALATE "
            "guidance into a hard human-required signal. Auto-on for --mode metaplan/doc."
        ),
    )
    init_parser.add_argument("--robustness", choices=list(ROBUSTNESS_LEVELS), default=None)
    init_parser.add_argument("--mode", choices=["code", "doc", "metaplan", "joke", "creative"], default=None,
                             help="Deliverable type: 'code' (source changes), 'doc' / 'metaplan' "
                                  "(design/spec artifact — 'metaplan' is an alias for 'doc'), or "
                                  "'joke' (film scene script; requires --output), or "
                                  "'creative' (creative work; requires --form and --output). "
                                  "Defaults to 'code' unless the idea strongly suggests a design document, "
                                  "in which case --mode must be passed explicitly.")
    init_parser.add_argument("--form", choices=available_form_ids(), default=None,
                             help="Creative form to use with --mode creative.")
    init_parser.add_argument("--output", default=None,
                             help="Relative path where the prose artifact will be written. "
                                  "Required with --mode doc, --mode joke, or --mode creative; rejected with --mode code.")
    init_parser.add_argument(
        "--primary-criterion",
        default=None,
        help="Declare the creative-work primary criterion (for example: 'weirdest coherent'). "
             "Valid only with --mode joke or --mode creative.",
    )
    init_parser.add_argument("--from-doc", default=None,
                             help="Relative path to a prior doc-mode artifact whose ## Settled "
                                  "Decisions section should be imported. Valid with --mode "
                                  "code, --mode doc, --mode joke, or --mode creative.")
    init_parser.add_argument(
        "--idea-file",
        default=None,
        help="Read the idea text from a UTF-8 file instead of the positional CLI argument.",
    )
    init_parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Immediately run the in-process auto driver after initializing the plan.",
    )
    init_parser.add_argument("--hermes", nargs="?", const="", default=None,
                             help="Use Hermes agent for all phases. Optional: specify default model")
    init_parser.add_argument("--phase-model", action="append", default=[],
                             help="Per-phase model override: --phase-model critique=hermes:openai/gpt-5")
    init_parser.add_argument("--profile", default=None,
                             help="Named preset from profiles.toml; see 'megaplan config profiles list'.")
    init_parser.add_argument(
        "--from-arnold-epic",
        default=None,
        metavar="EPIC_ID",
        help="Load plan idea from Arnold epic via DBStore (read-only; --backend db not required for read path)",
    )
    init_parser.add_argument("idea", nargs="?")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--all", action="store_true",
                             help="Search all .megaplan directories system-wide (~)")
    list_parser.add_argument("--no-tree", action="store_true",
                             help="Only show plans from the current directory (default includes parent + child)")
    list_parser.add_argument("--include-done", action="store_true",
                             help="Include terminal plans; excluded by default")
    list_parser.add_argument("--status", dest="filter_status",
                             help="Filter by state (e.g. 'done', 'finalized', 'executed', or comma-separated 'planned,critiqued')")
    list_parser.add_argument("--summary", action="store_true",
                             help="Show count breakdown by state")

    epic_parser = subparsers.add_parser("epic", help="Inspect or migrate Arnold epics")
    epic_parser.add_argument("--project-dir", default=None)
    epic_subparsers = epic_parser.add_subparsers(dest="epic_action", required=True)
    epic_snapshot_parser = epic_subparsers.add_parser("snapshot", help="Write an offline JSON snapshot for an epic")
    epic_snapshot_parser.add_argument("epic_id")
    epic_snapshot_parser.add_argument("--project-dir", default=None)
    epic_migrate_parser = epic_subparsers.add_parser("migrate", help="Promote or demote an epic between backends")
    epic_migrate_parser.add_argument("epic_id", nargs="?")
    epic_migrate_parser.add_argument("--to", choices=["file", "db"], default=None)
    epic_migrate_parser.add_argument("--resume", metavar="MIGRATION_ID", default=None)
    epic_migrate_parser.add_argument("--actor", default=None, metavar="ID", help="Actor ID for migration writes")
    epic_migrate_parser.add_argument("--ttl", type=int, default=300)
    epic_migrate_parser.add_argument("--project-dir", default=None)

    for name in ["status", "progress", "watch"]:
        step_parser = subparsers.add_parser(name)
        step_parser.add_argument("--plan")
        if name == "status":
            step_parser.add_argument("--pending-human", action="store_true",
                                     help="List plans awaiting human verification")

    resume_parser = subparsers.add_parser("resume", help="Resume a failed or blocked plan from its stored cursor")
    resume_parser.add_argument("--plan", required=True)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--plan")
    audit_sub = audit_parser.add_subparsers(dest="audit_action", required=False)
    audit_query_parser = audit_sub.add_parser("query", help="Query step receipts across plans")
    audit_query_parser.add_argument("--model")
    audit_query_parser.add_argument("--phase")
    audit_query_parser.add_argument("--profile")
    audit_query_parser.add_argument("--since")
    audit_query_parser.add_argument("--agg", default="")
    audit_query_parser.add_argument("--json", action="store_true")
    audit_query_parser.add_argument("--audit-dir", default=None)

    for name in ["plan", "prep", "critique", "revise", "gate", "finalize", "execute", "review"]:
        step_parser = subparsers.add_parser(name)
        step_parser.add_argument("--plan")
        step_parser.add_argument("--agent", choices=["claude", "codex", "hermes"])
        step_parser.add_argument("--hermes", nargs="?", const="", default=None,
                                 help="Use Hermes agent for all phases. Optional: specify default model (e.g. --hermes anthropic/claude-sonnet-4.6)")
        step_parser.add_argument("--phase-model", action="append", default=[],
                                 help="Per-phase model override: --phase-model critique=hermes:openai/gpt-5")
        step_parser.add_argument("--profile", default=None,
                                 help="Named preset from profiles.toml; see 'megaplan config profiles list'.")
        step_parser.add_argument("--fresh", action="store_true")
        step_parser.add_argument("--persist", action="store_true")
        step_parser.add_argument("--ephemeral", action="store_true")
        step_parser.add_argument("--work-dir", default=None,
                                 help="Override the source-code working directory passed to subprocess workers "
                                      "(--add-dir / -C). Defaults to the current working directory. Use this to "
                                      "force a specific path (e.g. a git worktree) regardless of where the plan was created.")
        if name == "execute":
            step_parser.add_argument("--confirm-destructive", action="store_true")
            step_parser.add_argument("--user-approved", action="store_true")
            step_parser.add_argument("--batch", type=int, default=None, help="Execute a specific global batch number (1-indexed)")
        if name == "review":
            step_parser.add_argument("--confirm-self-review", action="store_true")

    config_parser = subparsers.add_parser("config", help="View or edit megaplan configuration")
    config_sub = config_parser.add_subparsers(dest="config_action", required=True)
    config_sub.add_parser("show")
    set_parser = config_sub.add_parser("set")
    set_parser.add_argument("key")
    set_parser.add_argument("value")
    config_sub.add_parser("reset")
    profiles_parser = config_sub.add_parser("profiles", help="Inspect model profiles from built-in, user, and project layers")
    profiles_sub = profiles_parser.add_subparsers(dest="profiles_action", required=True)
    profiles_sub.add_parser(
        "list",
        help="List profiles from all layers",
        description="List profiles from all layers. Project-layer profiles are only visible when run from that project directory.",
    )
    profiles_show_parser = profiles_sub.add_parser("show", help="Show the fully resolved phase map for one profile")
    profiles_show_parser.add_argument("name")

    step_parser = subparsers.add_parser("step", help="Edit plan step sections without hand-editing markdown")
    step_subparsers = step_parser.add_subparsers(dest="step_action", required=True)

    step_add_parser = step_subparsers.add_parser("add", help="Insert a new step after an existing step")
    step_add_parser.add_argument("--plan")
    step_add_parser.add_argument("--after")
    step_add_parser.add_argument("description")

    step_remove_parser = step_subparsers.add_parser("remove", help="Remove a step and renumber the plan")
    step_remove_parser.add_argument("--plan")
    step_remove_parser.add_argument("step_id")

    step_move_parser = step_subparsers.add_parser("move", help="Move a step after another step and renumber")
    step_move_parser.add_argument("--plan")
    step_move_parser.add_argument("step_id")
    step_move_parser.add_argument("--after", required=True)

    override_parser = subparsers.add_parser("override")
    override_parser.add_argument("override_action", choices=["abort", "force-proceed", "add-note", "replan", "set-robustness", "set-profile"])
    override_parser.add_argument("--plan")
    override_parser.add_argument("--reason", default="")
    override_parser.add_argument("--note")
    override_parser.add_argument("--robustness", choices=list(ROBUSTNESS_LEVELS), default=None)
    override_parser.add_argument("--profile", default=None)
    # strict-notes plumbing. Only meaningful for specific override_action values, but
    # the override parser is flat (single positional + flags), so the flags live here.
    override_parser.add_argument(
        "--source",
        choices=["user", "driver"],
        default="user",
        help="(add-note) Note source. Driver-attached notes don't block strict-notes force-proceed.",
    )
    override_parser.add_argument(
        "--user-approved",
        action="store_true",
        help="(force-proceed) Acknowledge a strict-notes ESCALATE before forcing proceed.",
    )

    verify_human_parser = subparsers.add_parser("verify-human", help="Record human verification for a criterion")
    verify_human_parser.add_argument("--plan")
    verify_human_parser.add_argument("--criterion", required=True, help="Criterion name or index")
    vh_group = verify_human_parser.add_mutually_exclusive_group(required=True)
    vh_group.add_argument("--pass", dest="pass_flag", action="store_true")
    vh_group.add_argument("--fail", dest="fail_flag", action="store_true")
    verify_human_parser.add_argument("--evidence", required=True, help="Evidence supporting the verdict")

    audit_verifiability_parser = subparsers.add_parser("audit-verifiability", help="Audit criteria verifiability")
    audit_verifiability_parser.add_argument("--plan")

    debt_parser = subparsers.add_parser("debt", help="Inspect or manage persistent tech debt entries")
    debt_subparsers = debt_parser.add_subparsers(dest="debt_action", required=True)

    debt_list_parser = debt_subparsers.add_parser("list", help="List debt entries")
    debt_list_parser.add_argument("--all", action="store_true", help="Include resolved entries")

    debt_add_parser = debt_subparsers.add_parser("add", help="Add or increment a debt entry")
    debt_add_parser.add_argument("--subsystem", required=True)
    debt_add_parser.add_argument("--concern", required=True)
    debt_add_parser.add_argument("--flag-ids", default="")
    debt_add_parser.add_argument("--plan")

    debt_resolve_parser = debt_subparsers.add_parser("resolve", help="Resolve a debt entry")
    debt_resolve_parser.add_argument("debt_id")
    debt_resolve_parser.add_argument("--plan")

    loop_init_parser = subparsers.add_parser("loop-init", help="Initialize a MegaLoop workflow")
    loop_init_parser.add_argument("--project-dir", required=True)
    loop_init_parser.add_argument("--command", required=True)
    loop_init_parser.add_argument("--goal", dest="goal_option")
    loop_init_parser.add_argument("--name")
    loop_init_parser.add_argument("--iterations", type=int, default=3)
    loop_init_parser.add_argument("--time-budget", type=int, default=300)
    loop_init_parser.add_argument("--observe-interval", type=int)
    loop_init_parser.add_argument("--observe-break-patterns")
    loop_init_parser.add_argument("--agent", choices=["claude", "codex", "hermes"])
    loop_init_parser.add_argument("--hermes", nargs="?", const="", default=None,
                                  help="Use Hermes agent for loop phases. Optional: specify default model")
    loop_init_parser.add_argument("--phase-model", action="append", default=[],
                                  help="Per-phase model override: --phase-model loop_execute=hermes:openai/gpt-5")
    loop_init_parser.add_argument("--profile", default=None,
                                  help="Named preset from profiles.toml; see 'megaplan config profiles list'.")
    loop_init_parser.add_argument("--fresh", action="store_true")
    loop_init_parser.add_argument("--persist", action="store_true")
    loop_init_parser.add_argument("--ephemeral", action="store_true")
    loop_init_parser.add_argument("--work-dir", default=None,
                                  help="Override the source-code working directory for subprocess workers (default: CWD)")
    loop_init_parser.add_argument("goal", nargs="?")

    loop_run_parser = subparsers.add_parser("loop-run", help="Run an existing MegaLoop workflow")
    loop_run_parser.add_argument("name")
    loop_run_parser.add_argument("--project-dir")
    loop_run_parser.add_argument("--iterations", type=int)
    loop_run_parser.add_argument("--time-budget", type=int)
    loop_run_parser.add_argument("--agent", choices=["claude", "codex", "hermes"])
    loop_run_parser.add_argument("--hermes", nargs="?", const="", default=None,
                                 help="Use Hermes agent for loop phases. Optional: specify default model")
    loop_run_parser.add_argument("--phase-model", action="append", default=[],
                                 help="Per-phase model override: --phase-model loop_execute=hermes:openai/gpt-5")
    loop_run_parser.add_argument("--profile", default=None,
                                 help="Named preset from profiles.toml; see 'megaplan config profiles list'.")
    loop_run_parser.add_argument("--fresh", action="store_true")
    loop_run_parser.add_argument("--persist", action="store_true")
    loop_run_parser.add_argument("--ephemeral", action="store_true")
    loop_run_parser.add_argument("--work-dir", default=None,
                                 help="Override the source-code working directory for subprocess workers (default: CWD)")

    loop_status_parser = subparsers.add_parser("loop-status", help="Show MegaLoop state")
    loop_status_parser.add_argument("name")
    loop_status_parser.add_argument("--project-dir")

    loop_pause_parser = subparsers.add_parser("loop-pause", help="Pause a MegaLoop workflow")
    loop_pause_parser.add_argument("name")
    loop_pause_parser.add_argument("--project-dir")
    loop_pause_parser.add_argument("--reason", default="")

    from megaplan.auto import build_auto_parser
    build_auto_parser(subparsers)

    from megaplan.chain import build_chain_parser
    build_chain_parser(subparsers)

    cloud_parser = subparsers.add_parser(
        "cloud",
        add_help=False,
        help="Manage provider-backed megaplan cloud runners",
    )
    cloud_parser.add_argument("cloud_args", nargs=argparse.REMAINDER)

    bakeoff_parser = subparsers.add_parser(
        "bakeoff",
        add_help=False,
        help="Run concurrent multi-profile bake-offs",
    )
    bakeoff_parser.add_argument("bakeoff_args", nargs=argparse.REMAINDER)

    from megaplan.prompts.tiebreaker_orchestrator import build_tiebreaker_parser
    build_tiebreaker_parser(subparsers)

    # tiebreaker-run is a top-level command because auto.py:_phase_command
    # translates next_step directly to CLI args.
    tb_run_parser = subparsers.add_parser(
        "tiebreaker-run",
        help="Run tiebreaker researcher+challenger (used by auto driver)",
    )
    tb_run_parser.add_argument("--plan", required=True, help="Plan name")
    tb_run_parser.add_argument("--agent", choices=["claude", "codex", "hermes"], default=None)
    tb_run_parser.add_argument("--hermes", nargs="?", const="", default=None)
    tb_run_parser.add_argument("--phase-model", action="append", default=[])
    tb_run_parser.add_argument("--profile", default=None,
                               help="Named preset from profiles.toml; see 'megaplan config profiles list'.")
    tb_run_parser.add_argument("--fresh", action="store_true")
    tb_run_parser.add_argument("--persist", action="store_true")
    tb_run_parser.add_argument("--ephemeral", action="store_true")

    return parser


COMMAND_HANDLERS: dict[str, Callable[..., StepResponse]] = {
    "init": handle_init,
    "plan": handle_plan,
    "prep": handle_prep,
    "critique": handle_critique,
    "revise": handle_revise,
    "gate": handle_gate,
    "finalize": handle_finalize,
    "execute": handle_execute,
    "review": handle_review,
    "status": handle_status,
    "audit": handle_audit,
    "progress": handle_progress,
    "watch": handle_watch,
    "resume": handle_resume,
    "list": handle_list,
    "loop-init": handle_loop_init,
    "loop-run": handle_loop_run,
    "loop-status": handle_loop_status,
    "loop-pause": handle_loop_pause,
    "debt": handle_debt,
    "epic": handle_epic,
    "step": handle_step,
    "override": handle_override,
    "verify-human": handle_verify_human,
    "audit-verifiability": handle_audit_verifiability,
    "tiebreaker-run": handle_tiebreaker_run,
}


def cli_entry() -> None:
    sys.exit(main())


def _resolve_project_root(args: argparse.Namespace) -> Path:
    """Pick the authoritative project root for handlers that take ``root``.

    Precedence:

    1. ``--project-dir`` (when set on *args*) wins. The CLI flag is a deliberate
       caller override; honoring CWD-based discovery here lets a stray
       ``.megaplan/`` in an ancestor directory hijack the run. That's how
       parallel `megaplan init` invocations from sibling worktrees under
       ``~/Documents/.megaplan-worktrees/<exp>/<profile>/`` collide on a
       ``duplicate_plan`` error — the walk-up hits ``~/Documents/.megaplan/``
       and they all try to write into the same plans dir. See
       ``megaplan/bakeoff/orchestrator.py:_init_profile`` for the spawning side.
    2. Otherwise fall back to ``_find_megaplan_root(Path.cwd())`` — the legacy
       behavior that lets ``megaplan plan`` / ``status`` / etc. find the
       enclosing project without an explicit flag.
    """
    project_dir = getattr(args, "project_dir", None)
    if project_dir:
        resolved = Path(project_dir).expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise CliError(
                "invalid_project_dir",
                f"--project-dir does not exist or is not a directory: {project_dir}",
            )
        return resolved
    return _find_megaplan_root(Path.cwd())


def _find_megaplan_root(start: Path) -> Path:
    """Walk up from *start* to find the git-root directory containing ``.megaplan/``.

    Strategy: find the git root first (like ``git rev-parse --show-toplevel``),
    then check if it has a ``.megaplan/`` directory.  This avoids ambiguity when
    nested subdirectories also have their own ``.megaplan/``.  Falls back to the
    nearest ancestor with ``.megaplan/`` if not in a git repo, and finally to
    *start* if nothing is found.
    """
    resolved = start.resolve()

    # Try git root first — the canonical project root.
    git_root = _find_git_root(resolved)
    if git_root and (git_root / ".megaplan").is_dir():
        return git_root

    # Fallback: walk up to find nearest .megaplan
    current = resolved
    while True:
        if (current / ".megaplan").is_dir():
            return current
        parent = current.parent
        if parent == current:
            return start
        current = parent


def _find_git_root(start: Path) -> Path | None:
    """Walk up to find the directory containing ``.git``."""
    current = start
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _auto_sync_installed_skills() -> None:
    try:
        for target in _GLOBAL_TARGETS:
            agent_dir = Path.home() / target["detect"]
            if not agent_dir.is_dir():
                continue
            _install_owned_file(Path.home() / target["path"], bundled_global_file(target["data"]), force=False)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "cloud":
        from megaplan.cloud.cli import _register_cloud_subcommands, run_cloud_cli

        cloud_parser = argparse.ArgumentParser(prog="megaplan cloud")
        _register_cloud_subcommands(cloud_parser)
        cloud_args = cloud_parser.parse_args(argv[1:])
        root = _find_megaplan_root(Path.cwd())
        ensure_runtime_layout(root)
        try:
            return run_cloud_cli(root, cloud_args)
        except CliError as error:
            return error_response(error, root=root)
    if argv and argv[0] == "bakeoff":
        from megaplan.bakeoff.cli import _register_bakeoff_subcommands, run_bakeoff_cli

        bakeoff_parser = argparse.ArgumentParser(prog="megaplan bakeoff")
        _register_bakeoff_subcommands(bakeoff_parser)
        bakeoff_args = bakeoff_parser.parse_args(argv[1:])
        root = _find_megaplan_root(Path.cwd())
        ensure_runtime_layout(root)
        try:
            return run_bakeoff_cli(root, bakeoff_args)
        except CliError as error:
            return error_response(error, root=root)

    parser = build_parser()
    args, remaining = parser.parse_known_args(argv)
    if args.command != "setup":
        _auto_sync_installed_skills()
    try:
        if args.command == "setup":
            return render_response(handle_setup(args))
        if args.command == "config":
            return render_response(handle_config(args))
    except CliError as error:
        return error_response(error)

    # Capture an explicit --work-dir override for subprocess workers
    # (--add-dir / -C). When the flag is NOT passed, leave the override unset
    # so :func:`resolve_work_dir` can default to the plan's stored project_dir
    # (persisted at ``megaplan init``). Defaulting to CWD here silently
    # sandboxes codex to whatever subdirectory the shell happened to be in,
    # which breaks cross-subrepo writes — see resolve_work_dir for the
    # precedence rules.
    from megaplan.workers import set_work_dir_override
    work_dir_override = getattr(args, "work_dir", None)
    set_work_dir_override(Path(work_dir_override) if work_dir_override else None)

    try:
        root = _resolve_project_root(args)
    except CliError as error:
        return error_response(error)
    ensure_runtime_layout(root)

    if args.command == "auto":
        from megaplan.auto import run_auto
        try:
            return run_auto(root, args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "chain":
        from megaplan.chain import run_chain_cli
        try:
            return run_chain_cli(root, args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "tiebreaker":
        from megaplan.prompts.tiebreaker_orchestrator import run_tiebreaker_cli
        try:
            return run_tiebreaker_cli(root, args)
        except CliError as error:
            return error_response(error, root=root)

    try:
        handler = COMMAND_HANDLERS.get(args.command)
        if handler is None:
            raise CliError("invalid_command", f"Unknown command {args.command!r}")
        from megaplan.progress import ProgressEmitter
        args.progress_emitter = ProgressEmitter.from_env()
        if args.command == "override" and remaining:
            if not args.note:
                args.note = " ".join(remaining)
            remaining = []
        if remaining:
            parser.error(f"unrecognized arguments: {' '.join(remaining)}")
        if args.command == "override" and args.override_action == "add-note" and not args.note:
            raise CliError("invalid_args", "override add-note requires a note")
        if args.command == "override" and args.override_action == "set-robustness" and not args.robustness:
            raise CliError("invalid_args", f"override set-robustness requires --robustness {'|'.join(ROBUSTNESS_LEVELS)}")
        if args.command == "override" and args.override_action == "set-profile" and not args.profile:
            raise CliError("invalid_args", "override set-profile requires --profile NAME")
        if args.command == "init" and getattr(args, "from_arnold_epic", None):
            from megaplan.store import DBStore
            epic_id = args.from_arnold_epic
            store = DBStore(actor_id=None)  # read-only path
            try:
                epic = store.load_epic(epic_id)
                # Sprint 3: write-back to DB — load_hot_context for future context injection
            except Exception as exc:
                print(f"Error: failed to load epic {epic_id!r}: {exc}", file=sys.stderr)
                return 1
            finally:
                store.close()
            if epic is None:
                print(f"Error: epic {epic_id!r} not found.", file=sys.stderr)
                return 1
            parts = [epic.title]
            if epic.goal:
                parts.append(epic.goal)
            if epic.body:
                parts.append(epic.body)
            args.idea = "\n\n".join(parts)
        if args.command in _PROGRESS_PHASE_COMMANDS:
            args.progress_emitter.phase_start(args.command, plan=getattr(args, "plan", None))
        response = handler(root, args)
        _emit_response_progress(args.command, response, args.progress_emitter)
        return render_response(response)
    except CliError as error:
        if "args" in locals() and hasattr(args, "progress_emitter"):
            _emit_error_progress(getattr(args, "command", ""), error, args.progress_emitter)
        return error_response(error, root=root)


if __name__ == "__main__":
    sys.exit(main())
