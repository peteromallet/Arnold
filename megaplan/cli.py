#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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
    ROBUSTNESS_ACCEPTED,
    ROBUSTNESS_LEVELS,
    STATE_BLOCKED,
    STATE_DONE,
    STATE_REVIEWED,
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
    list_batch_artifacts,
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
    save_state,
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
from megaplan.execute.step_edit import handle_step
from megaplan.resolutions import SUPPORTED_USER_ACTION_RESOLUTION_STATES
from megaplan.user_actions import (
    FALLBACK,
    OMIT,
)
from megaplan.blocker_recovery import (
    PREREQUISITE,
    QUALITY,
    build_prerequisite_scopes,
    command_blocker_details,
    evaluate_blocker_recovery,
)
from megaplan.orchestration.phase_result import BlockedTask, read_phase_result
from megaplan.quality_resolutions import VALID_RESOLUTIONS as QUALITY_VALID_RESOLUTIONS

_PROGRESS_PHASE_COMMANDS = {
    "plan",
    "prep",
    "critique",
    "revise",
    "gate",
    "finalize",
    "execute",
    "review",
}


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
        emitter.plan_done(
            summary=str(response.get("summary") or "Plan complete"), phase=step
        )
    elif state == "failed":
        emitter.plan_failed(
            summary=str(response.get("summary") or "Plan failed"), phase=step
        )
    elif state == "blocked":
        emitter.execution_blocked(
            summary=str(response.get("summary") or "Execution blocked"), phase=step
        )


def _emit_error_progress(command: str, error: CliError, emitter: Any) -> None:
    if command not in _PROGRESS_PHASE_COMMANDS:
        return
    emitter.phase_end(
        command, success=False, error_code=error.code, message=error.message
    )


def _parse_utc_timestamp(timestamp: str | None) -> datetime | None:
    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def _compute_user_action_blockers(
    plan_dir: Path,
    finalize_data: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute user-action blocker details for progress/status payloads.

    Returns a dict with ``blocked_tasks_detail``, ``user_action_resolution_summary``,
    and a plan-level ``recommended_action``.
    """
    from megaplan.resolutions import (
        FALLBACK_STATES,
        HARD_BLOCK_STATES,
        load_user_action_resolutions,
        resolution_applies_to_task,
        resolution_recommended_action,
    )

    resolutions = load_user_action_resolutions(plan_dir)
    user_actions = finalize_data.get("user_actions", [])
    if not isinstance(user_actions, list):
        user_actions = []

    # Build mapping: task_id -> list of blocking user actions
    task_id_set = {t["id"] for t in tasks if isinstance(t.get("id"), str)}
    blocking_map: dict[str, list[dict[str, Any]]] = {}
    before_execute_actions: list[dict[str, Any]] = []

    for action in user_actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id", "unknown")
        phase = action.get("phase", "")
        blocks_task_ids = action.get("blocks_task_ids", [])

        if phase == "before_execute":
            before_execute_actions.append(action)

        if isinstance(blocks_task_ids, list) and blocks_task_ids:
            for task_id in blocks_task_ids:
                if isinstance(task_id, str) and task_id in task_id_set:
                    blocking_map.setdefault(task_id, []).append(action)

    # Attach before_execute actions without explicit blocks_task_ids to all
    # pending tasks as global pre-execute blockers.
    global_before_execute = [
        action
        for action in before_execute_actions
        if not isinstance(action.get("blocks_task_ids"), list)
        or not action.get("blocks_task_ids")
    ]
    if global_before_execute:
        for task in tasks:
            tid = task.get("id")
            if isinstance(tid, str) and task.get("status") == "pending":
                blocking_map.setdefault(tid, []).extend(global_before_execute)

    # Compute blocked_tasks_detail
    blocked_tasks_detail: list[dict[str, Any]] = []
    summary_states: dict[str, int] = {}
    any_fallback = False
    any_hard_block = False
    any_rejected = False
    any_unresolved = False

    for task in tasks:
        tid = task.get("id")
        if not isinstance(tid, str):
            continue
        task_status = task.get("status", "pending")
        blocking_actions = blocking_map.get(tid, [])

        # Only include tasks that are blocked OR pending with unresolved/hard-blocking user actions
        has_hard_block = False
        task_resolutions: list[dict[str, Any]] = []

        for action in blocking_actions:
            action_id = action.get("id", "unknown")
            resolution = resolutions.get(action_id)
            applies = resolution_applies_to_task(resolution, tid)

            if isinstance(resolution, dict):
                state = resolution.get("state", "")
                rec_action = resolution_recommended_action(resolution)

                res_detail = {
                    "action_id": action_id,
                    "state": state,
                    "reason": resolution.get("reason", ""),
                    "fallback_mode": resolution.get("fallback_mode", ""),
                    "instructions": resolution.get("instructions", ""),
                    "applies_to_task_ids": resolution.get("applies_to_task_ids", []),
                    "recommended_action": rec_action,
                }
                task_resolutions.append(res_detail)

                summary_states[state] = summary_states.get(state, 0) + 1

                if applies:
                    if state == "rejected":
                        any_rejected = True
                        has_hard_block = True
                    elif state in HARD_BLOCK_STATES or state == "manual_required":
                        any_hard_block = True
                        has_hard_block = True
                    elif state in FALLBACK_STATES:
                        any_fallback = True
                else:
                    # Resolution doesn't apply to this task — treat as unresolved
                    any_unresolved = True
                    has_hard_block = True
            else:
                # No resolution — unresolved
                any_unresolved = True
                has_hard_block = True
                summary_states["unresolved"] = summary_states.get("unresolved", 0) + 1

        if (
            task_status == "blocked"
            or (task_status == "pending" and has_hard_block)
        ):
            blocking_ua_ids = [
                action.get("id", "unknown")
                for action in blocking_actions
                if isinstance(action, dict)
            ]
            blocked_tasks_detail.append({
                "task_id": tid,
                "task_status": task_status,
                "blocking_user_actions": blocking_ua_ids,
                "resolutions": task_resolutions,
            })

    # Compute plan-level recommended_action using priority hierarchy
    if any_rejected:
        recommended_action = "cannot_continue"
    elif any_unresolved or any_hard_block:
        recommended_action = "awaiting_human"
    elif any_fallback:
        recommended_action = "continue_with_fallback"
    elif summary_states:
        # All satisfied (no fallback, no hard block, no unresolved)
        recommended_action = "retry_execute"
    else:
        recommended_action = "none"

    # Build summary
    user_action_resolution_summary = {
        "total_resolutions": len(resolutions),
        "by_state": summary_states,
    }

    return {
        "blocked_tasks_detail": blocked_tasks_detail,
        "user_action_resolution_summary": user_action_resolution_summary,
        "recommended_action": recommended_action,
    }


def _batch_status_overlay(plan_dir: Path) -> dict[str, str]:
    batch_status_overlay: dict[str, str] = {}
    for batch_path in list_batch_artifacts(plan_dir):
        try:
            batch_data = read_json(batch_path)
        except Exception:
            continue
        for update in batch_data.get("task_updates", []) or []:
            if not isinstance(update, dict):
                continue
            task_id = update.get("task_id")
            status = update.get("status")
            if isinstance(task_id, str) and isinstance(status, str) and status:
                batch_status_overlay[task_id] = status
    return batch_status_overlay


def _tasks_by_id(finalize_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = finalize_data.get("tasks", [])
    if not isinstance(tasks, list):
        return {}
    return {
        task["id"]: task
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }


def _phase_result_recovery_inputs(
    plan_dir: Path,
) -> tuple[tuple[BlockedTask, ...], tuple[Any, ...]]:
    try:
        phase_result = read_phase_result(plan_dir)
    except Exception:
        return (), ()
    if phase_result is None:
        return (), ()
    return phase_result.blocked_tasks, phase_result.deviations


def _synthetic_prerequisite_blocked_tasks(
    finalize_data: dict[str, Any],
    phase_blocked_tasks: tuple[BlockedTask, ...],
) -> tuple[BlockedTask, ...]:
    phase_task_ids = {blocked.task_id for blocked in phase_blocked_tasks}
    blocked: list[BlockedTask] = []
    for scope in build_prerequisite_scopes(finalize_data).values():
        if scope.malformed_reason is not None:
            continue
        for task_id in scope.effective_task_ids:
            if task_id in phase_task_ids:
                continue
            blocked.append(
                BlockedTask(
                    task_id=task_id,
                    reason=f"blocked by user action {scope.action_id}",
                    blocking_action_ids=(scope.action_id,),
                    blocker_kind=PREREQUISITE,
                )
            )
    return tuple(blocked)


def _unique_strings(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _build_blocker_recovery_context(
    plan_dir: Path,
    finalize_data: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    phase_blocked_tasks, deviations = _phase_result_recovery_inputs(plan_dir)
    prereq_blocked_tasks = phase_blocked_tasks + _synthetic_prerequisite_blocked_tasks(
        finalize_data,
        phase_blocked_tasks,
    )
    evaluation = evaluate_blocker_recovery(
        finalize_data,
        state,
        blocked_tasks=prereq_blocked_tasks,
        deviations=deviations,
    )
    blockers = command_blocker_details(evaluation)
    suggested_commands = _unique_strings(
        [
            command
            for blocker in blockers
            for command in blocker.get("suggested_commands", [])
            if isinstance(command, str)
        ]
    )
    if state.get("current_state") == "blocked" and blockers:
        plan_name = state.get("name")
        if isinstance(plan_name, str) and plan_name:
            suggested_commands.append(
                f"override recover-blocked --plan {plan_name} --reason <reason>"
            )
            suggested_commands = _unique_strings(suggested_commands)
    return {
        "can_continue": evaluation.can_continue,
        "has_terminal_blockers": evaluation.has_terminal_blockers,
        "requires_rerun": evaluation.requires_rerun,
        "blockers": blockers,
        "prerequisite_blockers": [
            blocker
            for blocker in blockers
            if blocker.get("blocker_kind") == PREREQUISITE
        ],
        "quality_blockers": [
            blocker for blocker in blockers if blocker.get("blocker_kind") == QUALITY
        ],
        "suggested_commands": suggested_commands,
    }


def _build_blocked_tasks_context(
    plan_dir: Path,
    finalize_data: dict[str, Any],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build legacy-compatible blocked task status from shared recovery data."""
    blocker_recovery = _build_blocker_recovery_context(plan_dir, finalize_data, state)
    prereq_blockers = blocker_recovery.get("prerequisite_blockers", [])
    if not prereq_blockers:
        return []

    tasks_by_id = _tasks_by_id(finalize_data)
    batch_status_overlay = _batch_status_overlay(plan_dir)
    blockers_by_task: dict[str, list[dict[str, Any]]] = {}
    for blocker in prereq_blockers:
        task_id = blocker.get("task_id")
        if isinstance(task_id, str):
            blockers_by_task.setdefault(task_id, []).append(blocker)

    blocked_tasks: list[dict[str, Any]] = []
    for task_id in sorted(blockers_by_task):
        task = tasks_by_id.get(task_id)
        if not task:
            continue
        task_status = batch_status_overlay.get(task_id, task.get("status", "pending"))
        blockers = sorted(
            blockers_by_task[task_id],
            key=lambda item: str(item.get("blocker_id", "")),
        )
        blocking_info: list[dict[str, Any]] = []
        all_behaviors: list[str] = []
        blocking_action_ids: list[str] = []
        effective_task_ids: list[str] = []
        protected_task_ids: list[str] = []
        suggested_commands: list[str] = []
        synthetic_gate_task_ids: list[str] = []
        for blocker in blockers:
            action_ids = [
                action_id
                for action_id in blocker.get("blocking_action_ids", [])
                if isinstance(action_id, str)
            ]
            blocking_action_ids.extend(action_ids)
            effective_task_ids.extend(
                task_id
                for task_id in blocker.get("effective_task_ids", [])
                if isinstance(task_id, str)
            )
            protected_task_ids.extend(
                task_id
                for task_id in blocker.get("protected_task_ids", [])
                if isinstance(task_id, str)
            )
            suggested_commands.extend(
                command
                for command in blocker.get("suggested_commands", [])
                if isinstance(command, str)
            )
            synthetic_gate_task_id = blocker.get("synthetic_gate_task_id")
            if isinstance(synthetic_gate_task_id, str):
                synthetic_gate_task_ids.append(synthetic_gate_task_id)
            behavior = str(blocker.get("resolution_behavior", "hard_block"))
            info: dict[str, Any] = {
                "action_id": action_ids[0] if action_ids else "unknown",
                "blocker_id": blocker.get("blocker_id"),
                "blocker_kind": blocker.get("blocker_kind"),
                "resolution_state": blocker.get("resolution_state", "unresolved"),
                "behavior": behavior,
                "is_non_terminal": blocker.get("is_non_terminal", False),
                "is_terminal": blocker.get("is_terminal", True),
                "suggested_commands": blocker.get("suggested_commands", []),
            }
            for field_name in (
                "fallback_mode",
                "instructions",
                "reason",
                "phase",
                "evidence",
                "debt_note",
                "malformed_reason",
            ):
                if field_name in blocker:
                    info[field_name] = blocker[field_name]
            blocking_info.append(info)
            all_behaviors.append(behavior)

        resolved_behaviors = {FALLBACK, OMIT}
        all_resolved = all(b in resolved_behaviors for b in all_behaviors)
        has_rejected = any(
            info.get("resolution_state") == "rejected" for info in blocking_info
        )
        if task_status == "blocked":
            if all_resolved:
                recommended_action = "rerun execute"
            elif has_rejected:
                recommended_action = "revise or abort"
            else:
                recommended_action = "record resolution"
        else:
            recommended_action = None
        blocked_tasks.append(
            {
                "task_id": task_id,
                "status": task_status,
                "blocking_action_ids": _unique_strings(blocking_action_ids),
                "resolutions": blocking_info,
                "effective_behavior": "fallback" if all_resolved else "hard_block",
                "recommended_action": recommended_action,
                "blocker_ids": _unique_strings(
                    [
                        str(blocker.get("blocker_id"))
                        for blocker in blockers
                        if blocker.get("blocker_id") is not None
                    ]
                ),
                "blocker_kinds": _unique_strings(
                    [
                        str(blocker.get("blocker_kind"))
                        for blocker in blockers
                        if blocker.get("blocker_kind") is not None
                    ]
                ),
                "blockers": blockers,
                "effective_task_ids": _unique_strings(effective_task_ids),
                "uses_synthetic_gate_scope": bool(synthetic_gate_task_ids),
                "synthetic_gate_task_id": (
                    _unique_strings(synthetic_gate_task_ids)[0]
                    if synthetic_gate_task_ids
                    else None
                ),
                "protected_task_ids": _unique_strings(protected_task_ids),
                "suggested_commands": _unique_strings(suggested_commands),
            }
        )
    return blocked_tasks


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
    # In per-batch execute mode, finalize.json is only rewritten after the
    # final batch — between batches the per-task status overlay lives in
    # execution_batch_<n>.json. Apply that overlay so progress reflects the
    # most recent on-disk truth. Single-execute mode produces no batch
    # artifacts, so this is a no-op there.
    batch_status_overlay: dict[str, str] = {}
    batch_artifacts = list_batch_artifacts(plan_dir)
    for batch_path in batch_artifacts:
        try:
            batch_data = read_json(batch_path)
        except Exception:
            continue
        for update in batch_data.get("task_updates", []) or []:
            if not isinstance(update, dict):
                continue
            task_id = update.get("task_id")
            status = update.get("status")
            if isinstance(task_id, str) and isinstance(status, str) and status:
                batch_status_overlay[task_id] = status
    progress_source = "finalize.json"
    if batch_status_overlay:
        merged_tasks: list[dict[str, Any]] = []
        for task in tasks:
            tid = task.get("id")
            if isinstance(tid, str) and tid in batch_status_overlay:
                merged = dict(task)
                merged["status"] = batch_status_overlay[tid]
                merged_tasks.append(merged)
            else:
                merged_tasks.append(task)
        tasks = merged_tasks
        progress_source = "execution_batch_*.json"
    tasks_done = sum(1 for t in tasks if t.get("status") == "done")
    tasks_skipped = sum(1 for t in tasks if t.get("status") == "skipped")
    tasks_pending = sum(1 for t in tasks if t.get("status") == "pending")
    tasks_blocked = sum(1 for t in tasks if t.get("status") == "blocked")
    tasks_total = len(tasks)
    completed_ids = {
        t["id"]
        for t in tasks
        if t.get("status") in {"done", "skipped"} and isinstance(t.get("id"), str)
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
    if progress_source == "execution_batch_*.json":
        granularity_note = "Progress reflects per-batch artifacts (latest execution_batch_*.json overlay)."
    else:
        granularity_note = "Progress reflects the last finalize.json write (between-batch granularity)."
    # Build compact resolution context for the progress payload
    blocked_tasks = _build_blocked_tasks_context(plan_dir, finalize_data, state)
    blocker_recovery = _build_blocker_recovery_context(plan_dir, finalize_data, state)
    blocked_task_resolution_summary = ""
    blocking_action_ids_map: dict[str, list[str]] = {}
    blocker_ids_map: dict[str, list[str]] = {}
    if blocked_tasks:
        resolved_count = sum(
            1 for bt in blocked_tasks if bt.get("recommended_action") == "rerun execute"
        )
        unresolved_count = len(blocked_tasks) - resolved_count
        parts = []
        if unresolved_count:
            parts.append(
                f"{unresolved_count} task(s) with unresolved/rejected blocking actions"
            )
        if resolved_count:
            parts.append(
                f"{resolved_count} task(s) with resolved actions ready for rerun"
            )
        blocked_task_resolution_summary = (
            "; ".join(parts) if parts else "all blocked actions resolved"
        )
        for bt in blocked_tasks:
            blocking_action_ids_map[bt["task_id"]] = bt["blocking_action_ids"]
            blocker_ids_map[bt["task_id"]] = bt.get("blocker_ids", [])
    ua_blockers = _compute_user_action_blockers(plan_dir, finalize_data, tasks)
    # Augment task_status_list with blocking_action_ids
    task_status_with_resolution = [
        {
            **ts,
            "blocking_action_ids": blocking_action_ids_map.get(ts["id"], []),
            "blocker_ids": blocker_ids_map.get(ts["id"], []),
        }
        for ts in task_status_list
    ]
    payload = {
        "summary": (
            f"Execution progress: {tasks_done + tasks_skipped}/{tasks_total} tasks tracked, "
            f"{batches_completed}/{len(global_batches)} batches completed. "
            f"{granularity_note}"
        ),
        "tasks_total": tasks_total,
        "tasks_done": tasks_done,
        "tasks_skipped": tasks_skipped,
        "tasks_pending": tasks_pending,
        "tasks_blocked": tasks_blocked,
        "batches_total": len(global_batches),
        "batches_completed": batches_completed,
        "tasks": task_status_with_resolution,
        "blocked_tasks_detail": ua_blockers["blocked_tasks_detail"],
        "user_action_resolution_summary": ua_blockers["user_action_resolution_summary"],
        "recommended_action": ua_blockers["recommended_action"],
        "blocked_task_resolution_summary": blocked_task_resolution_summary,
    }
    if blocker_recovery["blockers"]:
        payload["blocker_recovery"] = blocker_recovery
        payload["quality_blockers"] = blocker_recovery["quality_blockers"]
        payload["suggested_recovery_commands"] = blocker_recovery["suggested_commands"]
    return payload


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
    configured_timeout_seconds = int(
        get_effective("execution", "worker_timeout_seconds")
    )
    lock_held = plan_lock_is_held(plan_dir)
    raw_worker_pid = details.get("worker_pid")
    worker_pid: int | None
    try:
        worker_pid = int(raw_worker_pid) if raw_worker_pid is not None else None
    except (TypeError, ValueError):
        worker_pid = None
    started_at = _parse_utc_timestamp(details.get("started_at"))
    if started_at is not None:
        age_seconds = max(
            0, int((datetime.now(timezone.utc) - started_at).total_seconds())
        )
        details.update(
            build_phase_observability(
                step,
                configured_timeout_seconds=configured_timeout_seconds,
                age_seconds=age_seconds,
                lock_held=lock_held,
                worker_pid=worker_pid,
            )
        )
        last_activity_at = _parse_utc_timestamp(details.get("last_activity_at"))
        if last_activity_at is not None:
            idle_seconds = max(
                0, int((datetime.now(timezone.utc) - last_activity_at).total_seconds())
            )
            details["idle_seconds"] = idle_seconds
            hard_idle_seconds = int(
                details.get("timeout_budget_seconds")
                or details.get("escalation_threshold_seconds")
                or 0
            )
            if hard_idle_seconds > 0 and idle_seconds >= hard_idle_seconds:
                details["idle_stale"] = True
                details["health"] = "idle_stale" if lock_held else "stale"
                details["recommended_action"] = (
                    "terminate_idle_step"
                    if lock_held
                    else details.get("recommended_action", "rerun_same_step")
                )
                details["recommended_action_reason"] = (
                    f"The active step has produced no observed output or artifact activity for "
                    f"{humanize_seconds(idle_seconds)}."
                )
                details["idle_recovery_hint"] = (
                    "Terminate the idle worker, record the failed attempt, then rerun once; "
                    "if the same phase/model idles again, reroute the phase to a fallback model."
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
        max_seconds = int(
            details.get("expected_duration_seconds", {}).get("max", 0) or 0
        )
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
                details["progress_pct"] = min(
                    95, int((age_seconds / max_seconds) * 100)
                )
    else:
        details.update(
            build_phase_observability(
                step,
                configured_timeout_seconds=configured_timeout_seconds,
                lock_held=lock_held,
                worker_pid=worker_pid,
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
    if state.get("current_state") == STATE_BLOCKED:
        last_gate = state.get("last_gate") or {}
        preflight = last_gate.get("preflight_results") if isinstance(last_gate, dict) else None
        failed = (
            {name for name, passed in preflight.items() if not passed}
            if isinstance(preflight, dict)
            else set()
        )
        if (
            isinstance(last_gate, dict)
            and last_gate.get("recommendation") == "PROCEED"
            and not last_gate.get("passed", False)
            and failed
            and failed <= {"claude_available", "codex_available"}
        ):
            next_steps = ["override force-proceed", "gate"]
    notes = state.get("meta", {}).get("notes", [])
    lock_path = plan_dir / ".plan.lock"
    lock_file_present = lock_path.exists()
    lock_held = plan_lock_is_held(plan_dir)
    active_step = _build_active_step(state.get("active_step"), plan_dir=plan_dir)
    last_step = _build_last_step(state)
    plan_mode = state.get("config", {}).get("mode", "code")
    plan_output_path = state.get("config", {}).get("output_path")
    summary = (
        f"Plan '{state['name']}' is currently in state '{state['current_state']}'."
    )
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
    # Add blocked_tasks resolution context when finalize.json exists
    finalize_path = plan_dir / "finalize.json"
    if finalize_path.exists():
        finalize_data = read_json(finalize_path)
        blocked_tasks = _build_blocked_tasks_context(plan_dir, finalize_data, state)
        blocker_recovery = _build_blocker_recovery_context(
            plan_dir,
            finalize_data,
            state,
        )
        if blocked_tasks:
            response["blocked_tasks"] = blocked_tasks
        if blocker_recovery["blockers"]:
            response["blocker_recovery"] = blocker_recovery
            response["quality_blockers"] = blocker_recovery["quality_blockers"]
            response["suggested_recovery_commands"] = blocker_recovery[
                "suggested_commands"
            ]
    runtime = build_next_step_runtime(
        response.get("next_step"),
        configured_timeout_seconds=int(
            get_effective("execution", "worker_timeout_seconds")
        ),
    )
    if runtime is not None:
        response["next_step_runtime"] = runtime
    progress = (
        _build_progress_payload(plan_dir, state)
        if (plan_dir / "finalize.json").exists()
        else None
    )
    if progress is not None:
        response["progress"] = progress
        response["summary"] = response["summary"] + " " + progress["summary"]
    return response


def _parse_user_action_evidence(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    values: list[str] = []
    if isinstance(raw, str):
        raw_items = [raw]
    elif isinstance(raw, list):
        raw_items = raw
    else:
        return None
    for item in raw_items:
        if not isinstance(item, str):
            continue
        values.extend(part.strip() for part in item.split(",") if part.strip())
    return values or None


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
    if getattr(args, "audit_action", None) == "report":
        from megaplan.receipts.report import handle_audit_report

        return handle_audit_report(root, args)
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


def _collect_megaplan_roots(
    root: Path, *, tree: bool = False, all_system: bool = False
) -> list[Path]:
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
                if (
                    has_any_plan_root(candidate)
                    and candidate.resolve() != root.resolve()
                ):
                    roots.append(candidate)

    return roots


def handle_list(root: Path, args: argparse.Namespace) -> StepResponse:
    ensure_runtime_layout(root)

    # Dispatch to pipeline listing when 'pipelines' subcommand is used
    list_target = getattr(args, "list_target", None)
    if list_target == "pipelines":
        return _handle_list_pipelines(args)

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
                        entry["location"] = os.path.relpath(
                            resolved_search, resolved_root
                        )
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
        hints.append(
            f"{hidden_done} terminal plans hidden (use --include-done to show)"
        )
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
        entries = (
            registry["entries"]
            if args.all
            else [entry for entry in registry["entries"] if not entry["resolved"]]
        )
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
                "total_occurrences": (
                    subsystem_occurrence_total(entries_for_subsystem)
                    if not args.all
                    else sum(
                        entry["occurrence_count"]
                        for entry in entries_for_subsystem
                        if not entry["resolved"]
                    )
                ),
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


def handle_user_action(root: Path, args: argparse.Namespace) -> StepResponse:
    """Dispatch ``megaplan user-action ...`` subcommands."""
    from megaplan.resolutions import (
        SUPPORTED_USER_ACTION_RESOLUTION_STATES,
        upsert_user_action_resolution,
    )

    ensure_runtime_layout(root)
    action = args.user_action_action

    if action == "resolve":
        plan_dir, _state = load_plan(root, args.plan)
        finalize_path = plan_dir / "finalize.json"
        if not finalize_path.exists():
            raise CliError(
                "invalid_args",
                "No finalize.json found for this plan. Run 'megaplan finalize' first.",
            )
        finalize_data = read_json(finalize_path)
        user_actions = finalize_data.get("user_actions", [])
        if not isinstance(user_actions, list):
            raise CliError(
                "invalid_args",
                "finalize.json user_actions is not a list.",
            )

        # --- validate --state (before loading or writing) ---
        state = args.state
        if state not in SUPPORTED_USER_ACTION_RESOLUTION_STATES:
            raise CliError(
                "invalid_args",
                f"Unsupported resolution state {state!r}. "
                f"Must be one of: {', '.join(sorted(SUPPORTED_USER_ACTION_RESOLUTION_STATES))}.",
            )

        # --- validate --action matches an existing user_action ---
        action_id = args.action
        matched_action: dict[str, Any] | None = None
        for ua in user_actions:
            if isinstance(ua, dict) and ua.get("id") == action_id:
                matched_action = ua
                break
        if matched_action is None:
            raise CliError(
                "invalid_args",
                f"Unknown user action {action_id!r}. "
                f"Available action IDs: {', '.join(ua['id'] for ua in user_actions if isinstance(ua, dict) and 'id' in ua) or '(none)'}.",
            )

        # --- parse and validate --applies-to-task-ids ---
        applies_to_task_ids: list[str] = []
        raw_task_ids = args.applies_to_task_ids or ""
        if raw_task_ids.strip():
            # Split first, then reject empty entries from malformed
            # comma-separated values (e.g. "T1,,T2", ",T1", "T1,", ",").
            raw_parts = raw_task_ids.split(",")
            parts: list[str] = []
            for raw_part in raw_parts:
                part = raw_part.strip()
                if not part:
                    raise CliError(
                        "invalid_args",
                        "--applies-to-task-ids contains an empty or malformed entry.",
                    )
                parts.append(part)

            # known task IDs from finalize.json
            all_tasks = finalize_data.get("tasks", [])
            known_task_ids = {
                t["id"]
                for t in all_tasks
                if isinstance(t, dict) and isinstance(t.get("id"), str)
            }

            # validate each against known task IDs
            for tid in parts:
                if tid not in known_task_ids:
                    raise CliError(
                        "invalid_args",
                        f"Unknown task ID {tid!r} in --applies-to-task-ids. "
                        f"Known task IDs: {', '.join(sorted(known_task_ids)) or '(none)'}.",
                    )

            # validate against action's blocks_task_ids (if explicit)
            action_phase = matched_action.get("phase", "")
            blocks_task_ids = matched_action.get("blocks_task_ids", [])
            if isinstance(blocks_task_ids, list) and blocks_task_ids:
                # Explicit blockers: --applies-to-task-ids must be a subset
                explicit_blockers = set(blocks_task_ids)
                for tid in parts:
                    if tid not in explicit_blockers:
                        raise CliError(
                            "invalid_args",
                            f"Task ID {tid!r} is not in action {action_id!r}'s "
                            f"explicit blocks_task_ids: {', '.join(sorted(explicit_blockers))}. "
                            f"Use --applies-to-task-ids that are a subset of the action's blockers.",
                        )
            elif action_phase == "before_execute" and not blocks_task_ids:
                # before_execute actions without explicit blockers: any known task ID is allowed
                pass
            else:
                # Action has no explicit blockers and is not before_execute
                raise CliError(
                    "invalid_args",
                    f"Action {action_id!r} has no blocks_task_ids and is not a before_execute action. "
                    f"Cannot scope --applies-to-task-ids.",
                )

            applies_to_task_ids = parts

        # --- persist resolution ---
        upsert_user_action_resolution(
            plan_dir,
            action_id=action_id,
            state=state,
            reason=args.reason or "",
            fallback_mode=args.fallback_mode or "",
            applies_to_task_ids=applies_to_task_ids if applies_to_task_ids else None,
            instructions=args.instructions or "",
            created_by=args.created_by or "cli",
        )

        return {
            "success": True,
            "step": "user-action",
            "action": "resolve",
            "summary": (
                f"Resolution for user action {action_id!r} set to {state!r}."
            ),
            "details": {
                "action_id": action_id,
                "state": state,
                "plan": args.plan,
            },
        }

    raise CliError("invalid_args", f"Unknown user-action action: {action}")


# ---------------------------------------------------------------------------
# Setup and config
# ---------------------------------------------------------------------------


def _canonical_instructions() -> str:
    return (
        resources.files("megaplan")
        .joinpath("data", "instructions.md")
        .read_text(encoding="utf-8")
    )


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
    content = (
        resources.files("megaplan")
        .joinpath("data", filename)
        .read_text(encoding="utf-8")
    )
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


def _canonical_tickets_skill() -> str:
    return (
        resources.files("megaplan")
        .joinpath("data", "tickets_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_decision_skill() -> str:
    return (
        resources.files("megaplan")
        .joinpath("data", "decision_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_epic_skill() -> str:
    return (
        resources.files("megaplan")
        .joinpath("data", "epic_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_observe_skill() -> str:
    return (
        resources.files("megaplan")
        .joinpath("data", "observe_skill.md")
        .read_text(encoding="utf-8")
    )


def _canonical_cloud_skill() -> str:
    return resources.files("megaplan").joinpath("data", "cloud_skill.md").read_text(encoding="utf-8")


def _canonical_bakeoff_skill() -> str:
    return resources.files("megaplan").joinpath("data", "bakeoff_skill.md").read_text(encoding="utf-8")


def _canonical_composed(name: str) -> str:
    return (
        resources.files("megaplan")
        .joinpath("data", "_composed", name)
        .read_text(encoding="utf-8")
    )


def bundled_global_file(name: str) -> str:
    # Single-source skills: the canonical file already carries its frontmatter,
    # so this function just returns the canonical content unchanged. Do not
    # prepend headers — that's how the May 2026 megaplan-decision shadow-doc
    # regression happened (double frontmatter, drift between header and doc).
    if name == "tickets_skill.md":
        return _canonical_tickets_skill()
    # `decision_skill.md` is the canonical bundle name; `rubric_skill.md`
    # is accepted for back-compat with any in-flight callers.
    if name in {"decision_skill.md", "rubric_skill.md"}:
        return _canonical_decision_skill()
    if name == "epic_skill.md":
        return _canonical_epic_skill()
    if name == "observe_skill.md":
        return _canonical_observe_skill()
    if name == "cloud_skill.md":
        return _canonical_cloud_skill()
    if name == "bakeoff_skill.md":
        return _canonical_bakeoff_skill()
    # Composed bundles: pre-built at commit time via --regen-composed and
    # stored under megaplan/data/_composed/. Every _GLOBAL_TARGETS entry
    # referencing these symlinks into the pre-composed file — no runtime
    # composition needed here.
    if name == "claude_skill.md":
        return _canonical_composed("claude_skill.md")
    if name == "codex_skill.md":
        return _canonical_composed("codex_skill.md")
    if name == "cursor_rule.mdc":
        return _canonical_composed("cursor_rule.mdc")
    # skill.md: header + instructions only. No _GLOBAL_TARGETS entry
    # references this variant — it exists for callers that want the
    # instructions without any agent-specific appendix.
    content = _canonical_instructions()
    if name == "skill.md":
        return _SKILL_HEADER + content
    return content


# Every _GLOBAL_TARGETS entry uses install: "symlink". Composition moved to
# commit-time via --regen-composed, which writes pre-built bundles under
# megaplan/data/_composed/. The composed bundles are single-source from the
# installer's perspective — add_symlink_targets() creates symlinks into
# _composed/ just like it does for single-file skills.
#
# Adding a copy-mode entry is a regression — the test
# `tests/test_setup_no_shadow_skills.py` asserts every target uses symlink.
_GLOBAL_TARGETS = [
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan/SKILL.md", "data": "_composed/claude_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan", "data": "_codex_skills/megaplan", "install": "symlink"},
    {"agent": "cursor", "detect": ".cursor", "path": ".cursor/rules/megaplan.mdc", "data": "_composed/cursor_rule.mdc", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-bakeoff/SKILL.md", "data": "bakeoff_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-bakeoff", "data": "_codex_skills/megaplan-bakeoff", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-tickets/SKILL.md", "data": "tickets_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-tickets", "data": "_codex_skills/megaplan-tickets", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-decision/SKILL.md", "data": "decision_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-decision", "data": "_codex_skills/megaplan-decision", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-epic/SKILL.md", "data": "epic_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-epic", "data": "_codex_skills/megaplan-epic", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-observe/SKILL.md", "data": "observe_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-observe", "data": "_codex_skills/megaplan-observe", "install": "symlink"},
    {"agent": "claude", "detect": ".claude", "path": ".claude/skills/megaplan-cloud/SKILL.md", "data": "cloud_skill.md", "install": "symlink"},
    {"agent": "codex", "detect": ".codex", "path": ".codex/skills/megaplan-cloud", "data": "_codex_skills/megaplan-cloud", "install": "symlink"},
]


def _install_owned_file(
    path: Path, content: str, *, force: bool = False
) -> dict[str, bool | str]:
    existed = path.exists()
    if existed and not force:
        # If the target is a symlink pointing at the canonical source, leave it
        # alone. Replacing a symlink with a regular-file copy would reintroduce
        # the shadow-doc problem.
        if path.is_symlink():
            return {
                "path": str(path),
                "skipped": True,
                "existed": True,
                "reason": "symlinked",
            }
        if path.read_text(encoding="utf-8") == content:
            return {"path": str(path), "skipped": True, "existed": True}
    if path.is_symlink() or path.exists():
        path.unlink()
    atomic_write_text(path, content)
    return {"path": str(path), "skipped": False, "existed": existed}


def _install_owned_symlink(
    path: Path, target_path: Path, *, force: bool = False
) -> dict[str, bool | str]:
    """Install a symlink at `path` pointing at the canonical `target_path`.

    Replaces existing regular files or stale symlinks so the install code can
    never leave a shadow copy behind. The canonical bundle path is resolved
    through `importlib.resources`, so this works for both dev installs
    (live link into the repo) and pip installs (link into site-packages).
    """
    try:
        canonical = target_path.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        return {
            "path": str(path),
            "skipped": True,
            "existed": path.exists() or path.is_symlink(),
            "reason": f"canonical missing: {exc}",
        }
    existed = path.exists() or path.is_symlink()
    if existed and not force and path.is_symlink():
        try:
            if path.resolve(strict=True) == canonical:
                return {
                    "path": str(path),
                    "target": str(canonical),
                    "skipped": True,
                    "existed": True,
                    "symlink": True,
                }
        except (FileNotFoundError, OSError):
            pass  # stale symlink — fall through and replace
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        path.unlink()
    path.symlink_to(canonical)
    return {
        "path": str(path),
        "target": str(canonical),
        "skipped": False,
        "existed": existed,
        "symlink": True,
    }


def _install_owned_dir_symlink(path: Path, target_dir: Path, *, force: bool = False) -> dict[str, bool | str]:
    """Install a symlinked skill directory for Codex discovery."""
    try:
        canonical = target_dir.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        return {"path": str(path), "skipped": True, "existed": path.exists() or path.is_symlink(), "reason": f"canonical missing: {exc}"}
    existed = path.exists() or path.is_symlink()
    if existed and not force and path.is_symlink():
        try:
            if path.resolve(strict=True) == canonical:
                return {"path": str(path), "target": str(canonical), "skipped": True, "existed": True, "symlink": True}
        except (FileNotFoundError, OSError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)
    path.symlink_to(canonical, target_is_directory=True)
    return {"path": str(path), "target": str(canonical), "skipped": False, "existed": existed, "symlink": True}


def _resolve_bundle_path(data_name: str) -> Path:
    """Resolve the absolute filesystem path of a bundled data file.

    importlib.resources can return a Traversable that isn't a real Path
    (e.g. when reading from a zipped wheel), but for source/wheel-unpacked
    installs it resolves to a regular Path. Symlink installation requires a
    real path, so callers must invoke this only for installs that have an
    on-disk canonical (which is true for every install method megaplan
    currently supports).
    """
    return Path(str(resources.files("megaplan").joinpath("data", data_name)))


def handle_regen_composed() -> dict[str, Any]:
    """Regenerate composed skill bundles from source files.

    Reads instructions.md and the platform subagent appendices, computes
    three target strings (claude skill, codex skill, cursor rule), and
    writes them into ``megaplan/data/_composed/``.  Returns ``success: True``
    when every composed file already matches the computed content (no-op)
    and ``success: False`` when one or more files were regenerated (exit
    code 1 so the pre-commit hook / CI can detect drift).
    """
    instructions = _canonical_instructions()
    targets = {
        "claude_skill.md": _SKILL_HEADER
        + instructions
        + "\n\n"
        + _claude_subagent_appendix(),
        "codex_skill.md": _SKILL_HEADER
        + instructions
        + "\n\n"
        + _codex_subagent_appendix(),
        "cursor_rule.mdc": _CURSOR_HEADER + instructions,
    }
    codex_skill_dirs = {
        "_codex_skills/megaplan/SKILL.md": targets["codex_skill.md"],
        "_codex_skills/megaplan-bakeoff/SKILL.md": bundled_global_file("bakeoff_skill.md"),
        "_codex_skills/megaplan-tickets/SKILL.md": bundled_global_file("tickets_skill.md"),
        "_codex_skills/megaplan-decision/SKILL.md": bundled_global_file("decision_skill.md"),
        "_codex_skills/megaplan-epic/SKILL.md": bundled_global_file("epic_skill.md"),
        "_codex_skills/megaplan-observe/SKILL.md": bundled_global_file("observe_skill.md"),
        "_codex_skills/megaplan-cloud/SKILL.md": bundled_global_file("cloud_skill.md"),
    }
    composed_dir = resources.files("megaplan").joinpath("data", "_composed")
    Path(str(composed_dir)).mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for name, computed in targets.items():
        target_path = Path(str(composed_dir)) / name
        current = (
            target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
        )
        if current != computed:
            atomic_write_text(target_path, computed)
            changed.append(name)
    data_dir = Path(str(resources.files("megaplan").joinpath("data")))
    for name, computed in codex_skill_dirs.items():
        target_path = data_dir / name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        current = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
        if target_path.is_symlink() or current != computed:
            atomic_write_text(target_path, computed)
            changed.append(name)
    if changed:
        return {
            "success": False,
            "changed": changed,
            "summary": f"Regenerated {len(changed)} composed bundle(s): {', '.join(changed)}.",
        }
    return {"success": True, "changed": [], "summary": "No composed bundles changed."}


def handle_setup_global(force: bool = False, home: Path | None = None) -> StepResponse:
    if home is None:
        home = Path.home()
    installed: list[dict[str, Any]] = []
    detected_count = 0
    for target in _GLOBAL_TARGETS:
        agent_dir = home / target["detect"]
        if not agent_dir.is_dir():
            installed.append(
                {
                    "agent": target["agent"],
                    "path": str(home / target["path"]),
                    "skipped": True,
                    "reason": "not installed",
                }
            )
            continue
        detected_count += 1
        mode = target.get("install", "copy")
        if mode == "symlink":
            result = _install_owned_symlink(
                home / target["path"],
                _resolve_bundle_path(target["data"]),
                force=force,
            )
        elif mode == "dir_symlink":
            result = _install_owned_dir_symlink(
                home / target["path"],
                _resolve_bundle_path(target["data"]),
                force=force,
            )
        else:
            result = _install_owned_file(
                home / target["path"],
                bundled_global_file(target["data"]),
                force=force,
            )
        result["agent"] = target["agent"]
        installed.append(result)
    if detected_count == 0:
        return {
            "success": False,
            "step": "setup",
            "mode": "global",
            "summary": "No supported agents detected. Create one of ~/.claude/, ~/.codex/, or ~/.cursor/ and re-run.",
            "installed": installed,
        }
    available = detect_available_agents()
    config_path = None
    routing = None
    if available:
        agents_config = {
            step: (default if default in available else available[0])
            for step, default in DEFAULT_AGENT_ROUTING.items()
        }
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
            lines.append(
                f"  {rec['agent']}: {'overwrote' if rec['existed'] else 'created'} {rec['path']}"
            )
    result_data: dict[str, Any] = {
        "success": True,
        "step": "setup",
        "mode": "global",
        "summary": "Global setup complete:\n" + "\n".join(lines),
        "installed": installed,
    }
    if config_path is not None:
        result_data["config_path"] = str(config_path)
        result_data["routing"] = routing
    return result_data


def handle_setup(args: argparse.Namespace) -> StepResponse:
    if getattr(args, "regen_composed", False):
        return handle_regen_composed()
    local = args.local or args.target_dir
    if not local:
        return handle_setup_global(force=args.force)
    target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
    target = target_dir / "AGENTS.md"
    content = bundled_agents_md()
    if target.exists() and not args.force:
        existing = target.read_text(encoding="utf-8")
        if "megaplan" in existing.lower():
            return {
                "success": True,
                "step": "setup",
                "summary": f"AGENTS.md already contains megaplan instructions at {target}",
                "skipped": True,
            }
        atomic_write_text(target, existing + "\n\n" + content)
        return {
            "success": True,
            "step": "setup",
            "summary": f"Appended megaplan instructions to existing {target}",
            "file": str(target),
        }
    atomic_write_text(target, content)
    return {
        "success": True,
        "step": "setup",
        "summary": f"Created {target}",
        "file": str(target),
    }


def handle_config(args: argparse.Namespace) -> StepResponse:
    action = args.config_action
    if action == "show":
        config = load_config()
        effective_routing = {
            step: config.get("agents", {}).get(step, default)
            for step, default in DEFAULT_AGENT_ROUTING.items()
        }
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
                raise CliError(
                    "invalid_args",
                    f"Unknown step '{setting}'. Valid steps: {', '.join(DEFAULT_AGENT_ROUTING)}",
                )
            if value not in KNOWN_AGENTS:
                raise CliError(
                    "invalid_args",
                    f"Unknown agent '{value}'. Valid agents: {', '.join(KNOWN_AGENTS)}",
                )
            config.setdefault("agents", {})[setting] = value
        elif key == "orchestration.mode":
            if value not in {"inline", "subagent"}:
                raise CliError(
                    "invalid_args", "orchestration.mode must be 'inline' or 'subagent'"
                )
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
                raise CliError(
                    "invalid_args", f"{key} must be an integer, got '{value}'"
                ) from exc
            config.setdefault(section, {})[setting] = parsed_value
        else:
            raise CliError(
                "invalid_args",
                f"Unknown config key '{key}'. Valid keys: {', '.join(valid_keys)}",
            )
        save_config(config)
        return {
            "success": True,
            "step": "config",
            "action": "set",
            "key": key,
            "value": config[section][setting],
        }
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
                for source_label, profile_name, phase_map in load_profile_sources(
                    project_dir=project_dir
                )
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
    if action == "use-profile":
        project_dir = Path.cwd()
        name = args.name
        profiles = load_profiles(project_dir=project_dir)
        # resolve_profile raises CliError("unknown_profile", ...) with the list of
        # known profile names, which is what we want for a clear error.
        resolved = resolve_profile(name, profiles)
        config = load_config()
        agents_section = config.setdefault("agents", {})
        applied: dict[str, str] = {}
        for phase, spec in resolved.items():
            agents_section[phase] = spec
            applied[phase] = spec
        save_config(config)
        return {
            "success": True,
            "step": "config",
            "action": "use-profile",
            "config_path": str(config_dir() / "config.json"),
            "profile": name,
            "applied": applied,
            "summary": (
                f"Applied profile '{name}' to user config "
                f"({len(applied)} agent phase{'s' if len(applied) != 1 else ''} updated)."
            ),
        }
    if action == "reset":
        path = config_dir() / "config.json"
        if path.exists():
            path.unlink()
        return {
            "success": True,
            "step": "config",
            "action": "reset",
            "summary": "Config file removed. Using defaults.",
        }
    raise CliError("invalid_args", f"Unknown config action: {action}")


# ---------------------------------------------------------------------------
# Store factory
# ---------------------------------------------------------------------------


def build_store(args: argparse.Namespace):
    """Return a DBStore configured for writes, or None for the file backend."""
    backend = getattr(args, "backend", None) or os.environ.get("MEGAPLAN_BACKEND")
    if backend == "db":
        from megaplan.store import (
            DBStore,
            require_actor_id,
            resolve_actor_id,
            validate_actor_exists,
        )

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
        "checklist_items": [
            _jsonable_model(row) for row in entities["checklist_items"]
        ],
        "sprints": [_jsonable_model(row) for row in entities["sprints"]],
        "sprint_items": [_jsonable_model(row) for row in entities["sprint_items"]],
        "plans": [_jsonable_model(row) for row in entities["plans"]],
        "plan_artifacts_by_plan": plan_artifacts,
        "images": [_jsonable_model(row) for row in entities["images"]],
        "second_opinions": [
            _jsonable_model(row) for row in entities["second_opinions"]
        ],
        "feedback": [_jsonable_model(row) for row in entities["feedback"]],
        "code_artifacts": [_jsonable_model(row) for row in entities["code_artifacts"]],
        "epic_events": [_jsonable_model(row) for row in entities["epic_events"]],
    }


def _snapshot_dir(epic_id: str) -> Path:
    timestamp = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )
    return Path.home() / ".megaplan" / "snapshots" / f"{epic_id}-{timestamp}"


def handle_ticket(args: argparse.Namespace) -> int:
    """Dispatch ``megaplan ticket ...`` subcommands."""
    from megaplan.handlers.tickets import TICKET_DISPATCH
    from megaplan.tickets.registry import touch as _registry_touch

    # Passive registry maintenance — best-effort, never raises.
    try:
        _registry_touch(Path.cwd())
    except Exception:
        pass

    action = args.ticket_action
    handler = TICKET_DISPATCH.get(action)
    if handler is None:
        print(f"Error: unknown ticket action {action!r}", file=sys.stderr)
        return 1
    return handler(args)


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
                    raise CliError(
                        "invalid_args",
                        "epic migrate --resume does not accept an epic id",
                    )
                run = store.resume_migration(args.resume, ttl_seconds=args.ttl)
                migration_action = "resume"
            else:
                if not args.epic_id:
                    raise CliError(
                        "invalid_args",
                        "epic migrate requires an epic id unless --resume is used",
                    )
                if not args.to:
                    raise CliError(
                        "invalid_args",
                        "epic migrate requires --to file|db unless --resume is used",
                    )
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
    if action == "export":
        from megaplan.store.export import collect_epic_export, write_epic_export_tar

        store = build_epic_store(root)
        try:
            try:
                collected = collect_epic_export(
                    store,
                    args.epic_id,
                    allow_missing_blobs=bool(args.allow_missing_blobs),
                )
            except FileNotFoundError as exc:
                raise CliError("not_found", f"Epic {args.epic_id!r} not found") from exc
            if collected["errors"]:
                raise CliError(
                    "export_failed",
                    f"Epic {args.epic_id!r} export has missing or corrupt blobs",
                    extra={"errors": collected["errors"]},
                )
            output = write_epic_export_tar(
                collected, args.output, gzip_output=bool(args.gzip)
            )
        finally:
            close = getattr(store, "close", None)
            if callable(close):
                close()
        return {
            "success": True,
            "step": "epic",
            "action": "export",
            "epic_id": args.epic_id,
            "path": output["path"],
            "gzip": output["gzip"],
            "size_bytes": output["size_bytes"],
            "sha256": output["sha256"],
            "member_count": output["member_count"],
            "warnings": collected["warnings"],
            "errors": collected["errors"],
        }
    raise CliError("invalid_args", f"Unknown epic action: {action}")


def handle_migrate_local_plans(root: Path, args: argparse.Namespace) -> StepResponse:
    del root
    from megaplan.store.legacy_migration import migrate_local_plans

    try:
        return migrate_local_plans(
            source_home=Path(args.source_home).expanduser(),
            source_project=args.source_project,
            all_projects=bool(args.all_projects),
            target_project_dir=Path(args.target_project_dir).expanduser(),
            mode=args.mode,
            dry_run=bool(args.dry_run),
        )
    except ValueError as exc:
        raise CliError("invalid_args", str(exc)) from exc


def handle_resume(root: Path, args: argparse.Namespace) -> StepResponse:
    # Check for awaiting_user.json first (YAML pipeline human_gate pause).
    # When present, enter the human-gate resume flow consuming --choice.
    # When absent, fall through to existing state.json::resume_cursor recovery.
    from megaplan._core.io import find_plan_dir

    plan_dir = find_plan_dir(root, args.plan)
    if plan_dir is not None and (plan_dir / "awaiting_user.json").exists():
        return _resume_yaml_human_gate(root, plan_dir, args)

    store = None
    if (
        getattr(args, "actor", None)
        or getattr(args, "backend", None) == "db"
        or os.environ.get("MEGAPLAN_ACTOR_ID")
    ):
        store = build_epic_store(
            root,
            actor_id=getattr(args, "actor", None)
            or os.environ.get("MEGAPLAN_ACTOR_ID"),
        )
    try:
        return resume_plan(root, args.plan, store=store)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def _resume_yaml_human_gate(
    root: Path, plan_dir: Path, args: argparse.Namespace
) -> dict[str, Any]:
    """Resume a YAML pipeline paused at a human_gate stage.

    Re-reads ``awaiting_user.json``, validates the ``--choice`` argument,
    and re-enters the pipeline at the paused stage so all artifact paths
    are read fresh from disk on resume.
    """
    awaiting_path = plan_dir / "awaiting_user.json"
    try:
        data = json.loads(awaiting_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise CliError(
            "bad_awaiting_user", f"Cannot read awaiting_user.json: {exc}"
        ) from exc

    pipeline_name = data.get("pipeline")
    if not pipeline_name:
        raise CliError(
            "bad_awaiting_user", "awaiting_user.json is missing 'pipeline' field"
        )

    choices = data.get("choices", [])
    choice = getattr(args, "choice", None)
    if not choice:
        raise CliError(
            "missing_choice",
            f"Pipeline '{pipeline_name}' is paused at human_gate stage "
            f"'{data.get('stage', '?')}'. "
            f"Use --choice with one of: {', '.join(choices)}",
        )

    if choice not in choices:
        raise CliError(
            "invalid_choice",
            f"Invalid choice '{choice}'. " f"Valid choices: {', '.join(choices)}",
        )

    from megaplan._pipeline.loader import load_pipeline
    from megaplan._pipeline.compiler import compile_pipeline, inject_pipeline_context
    from megaplan._pipeline.executor import run_pipeline
    from megaplan._pipeline.resume import with_entry
    from megaplan._pipeline.types import StepContext

    lp = load_pipeline(pipeline_name)

    # Build pipeline with resume_choice so HumanGateStep returns it.
    pipeline = compile_pipeline(
        lp.spec,
        pipeline_dir=lp.dir,
        resume_choice=choice,
    )

    # Re-enter at the paused stage so prior stages are not re-run.
    paused_stage = data.get("stage")
    if paused_stage and paused_stage in pipeline.stages:
        pipeline = with_entry(pipeline, paused_stage)

    # Re-read state from disk (fresh artifact paths).
    state: dict[str, Any] = {}
    state_path = plan_dir / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            pass

    # Clear pause flags so the executor doesn't immediately halt again.
    state.pop("_pipeline_paused", None)
    state.pop("_pipeline_paused_stage", None)

    ctx = StepContext(
        plan_dir=plan_dir,
        state=state,
        profile={},
        mode=state.get("mode", "code"),
        inputs={},
    )
    ctx = inject_pipeline_context(ctx, lp.spec.name)

    result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

    # Clean up awaiting_user.json after successful resume
    if awaiting_path.exists():
        awaiting_path.unlink()

    return result


def _collect_feedback_rows(
    root: Path,
    *,
    all_system: bool = False,
    include_db: bool = True,
) -> list[dict[str, Any]]:
    """Gather feedback rows from file-mode plan trees and (optionally) the DB.

    Each row is a dict with: ``plan``, ``profile``, ``repo``, ``state``,
    ``backend`` (``file`` or ``db``), ``feedback_path`` (file mode only),
    ``feedback`` (parsed dict from PlanFeedback.to_dict), ``plan_id`` (DB only).
    Duplicates between file and DB are de-duped by (plan name, repo).
    """

    from megaplan._core.io import read_json
    from megaplan.orchestration.feedback import feedback_path, load_feedback

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    # --- File backend: walk known megaplan project roots and read feedback.md
    for search_root in _collect_megaplan_roots(
        root, tree=not all_system, all_system=all_system
    ):
        for plan_dir in active_plan_dirs(search_root):
            fb = load_feedback(plan_dir)
            if fb is None or fb.is_empty():
                continue
            try:
                state = read_json(plan_dir / "state.json")
            except (FileNotFoundError, OSError):
                continue
            config = state.get("config") or {}
            profile = config.get("profile") if isinstance(config, dict) else None
            repo = config.get("project_dir") if isinstance(config, dict) else None
            key = (state.get("name", plan_dir.name), str(repo or search_root))
            seen.add(key)
            rows.append(
                {
                    "plan": state.get("name", plan_dir.name),
                    "profile": profile,
                    "repo": repo or str(search_root),
                    "state": state.get("current_state"),
                    "backend": "file",
                    "feedback_path": str(feedback_path(plan_dir)),
                    "feedback": fb.to_dict(),
                }
            )

    # --- DB backend: if an actor is configured, pull rows with non-empty feedback
    if include_db and (
        os.environ.get("MEGAPLAN_ACTOR_ID")
        or getattr(_collect_feedback_rows, "_actor_override", None)
    ):
        actor_id = (
            getattr(_collect_feedback_rows, "_actor_override", None)
            or os.environ["MEGAPLAN_ACTOR_ID"]
        )
        try:
            store = build_epic_store(root, actor_id=actor_id)
        except Exception:
            store = None
        if store is not None:
            try:
                for plan in store.list_plans(include_orphans=True):
                    fb_dict = getattr(plan, "feedback", None)
                    if not fb_dict:
                        continue
                    config = plan.config or {}
                    profile = (
                        config.get("profile") if isinstance(config, dict) else None
                    )
                    repo = (
                        config.get("project_dir") if isinstance(config, dict) else None
                    )
                    key = (plan.name, str(repo or ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "plan": plan.name,
                            "profile": profile,
                            "repo": repo,
                            "state": plan.current_state,
                            "backend": "db",
                            "plan_id": plan.id,
                            "feedback": fb_dict,
                        }
                    )
            finally:
                close = getattr(store, "close", None)
                if callable(close):
                    close()
    return rows


def _filter_feedback_rows(
    rows: list[dict[str, Any]], args: argparse.Namespace
) -> list[dict[str, Any]]:
    profile = (getattr(args, "profile", None) or "").lower() or None
    repo = (getattr(args, "repo", None) or "").lower() or None
    min_rating = getattr(args, "min_rating", None)
    max_rating = getattr(args, "max_rating", None)
    stage = (getattr(args, "stage", None) or "").lower() or None
    has_comment = getattr(args, "has_comment", False)

    def _keep(row: dict[str, Any]) -> bool:
        if profile and profile not in (str(row.get("profile") or "")).lower():
            return False
        if repo and repo not in (str(row.get("repo") or "")).lower():
            return False
        fb = row.get("feedback") or {}
        overall = fb.get("overall") or {}
        rating = overall.get("rating")
        if rating is None:
            rating = overall.get("ai_rating")
        if min_rating is not None and (rating is None or rating < min_rating):
            return False
        if max_rating is not None and (rating is None or rating > max_rating):
            return False
        if has_comment:
            comment = (overall.get("comment") or "").strip() or (
                overall.get("ai_comment") or ""
            ).strip()
            if not comment:
                return False
        if stage:
            stage_entry = (fb.get("stages") or {}).get(stage)
            if not stage_entry:
                return False
            stage_rating = stage_entry.get("rating")
            if stage_rating is None:
                stage_rating = stage_entry.get("ai_rating")
            if stage_rating is None:
                return False
        return True

    return [r for r in rows if _keep(r)]


def _render_feedback_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no matches)"
    lines: list[str] = []
    header = f"{'PLAN':<28} {'PROFILE':<14} {'OVR':>4}  {'BK':<4} REPO"
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        fb = row.get("feedback") or {}
        overall = fb.get("overall") or {}
        rating = overall.get("rating")
        ai_only = rating is None
        if rating is None:
            rating = overall.get("ai_rating")
        if rating is None:
            rating_s = "—"
        else:
            rating_s = f"{rating}/10 (AI)" if ai_only else f"{rating}/10"
        repo = str(row.get("repo") or "")
        if len(repo) > 40:
            repo = "…" + repo[-39:]
        lines.append(
            f"{(row.get('plan') or '')[:28]:<28} "
            f"{(row.get('profile') or '—')[:14]:<14} "
            f"{rating_s:>4}  "
            f"{(row.get('backend') or '?'):<4} {repo}"
        )
        user_comment = (overall.get("comment") or "").strip()
        ai_comment = (overall.get("ai_comment") or "").strip()
        if user_comment:
            comment = user_comment
            comment_prefix = ""
        elif ai_comment:
            comment = ai_comment
            comment_prefix = "(AI) "
        else:
            comment = ""
            comment_prefix = ""
        if comment:
            first_line = comment_prefix + comment.splitlines()[0]
            if len(first_line) > 70:
                first_line = first_line[:67] + "…"
            lines.append(f"  └ {first_line}")
    return "\n".join(lines) + "\n"


def _parse_ai_feedback(payload: Any, raw_output: str) -> Any:
    """Coerce a worker payload (preferred) or raw JSON output into a PlanFeedback.

    Returns None when neither source yields a parseable feedback structure.
    Reads ``overall.rating/comment`` and ``stages.<name>.rating/comment``.
    """
    from megaplan.orchestration.feedback import PlanFeedback, StageFeedback

    data: Any = payload if isinstance(payload, dict) and payload else None
    if data is None:
        try:
            data = json.loads(raw_output)
        except (TypeError, ValueError):
            return None
    if not isinstance(data, dict):
        return None
    overall = data.get("overall")
    stages = data.get("stages") or {}
    if not isinstance(overall, dict) or not isinstance(stages, dict):
        return None

    def _coerce_rating(v: Any) -> int | None:
        if isinstance(v, bool):
            return None
        if isinstance(v, int) and 0 <= v <= 10:
            return v
        return None

    def _coerce_comment(v: Any) -> str | None:
        if isinstance(v, str) and v.strip():
            return v.strip()
        return None

    fb = PlanFeedback()
    fb.overall = StageFeedback(
        ai_rating=_coerce_rating(overall.get("rating")),
        ai_comment=_coerce_comment(overall.get("comment")),
    )
    for stage_name, entry in stages.items():
        if not isinstance(stage_name, str) or not isinstance(entry, dict):
            continue
        fb.stages[stage_name.lower()] = StageFeedback(
            ai_rating=_coerce_rating(entry.get("rating")),
            ai_comment=_coerce_comment(entry.get("comment")),
        )
    return fb if not fb.is_empty() else None


def _merge_feedback(existing: Any, ai_fb: Any) -> Any:
    """Return a PlanFeedback with user fields from ``existing`` and ai_* from ``ai_fb``.

    Either or both may be None. User ``rating`` / ``comment`` always win; AI
    fields are taken from ``ai_fb`` when present, else fall back to existing.
    """
    from megaplan.orchestration.feedback import PlanFeedback, StageFeedback

    merged = PlanFeedback()

    def _merge_stage(
        user_sf: StageFeedback | None, ai_sf: StageFeedback | None
    ) -> StageFeedback:
        rating = user_sf.rating if user_sf else None
        comment = user_sf.comment if user_sf else None
        if ai_sf is not None and ai_sf.ai_rating is not None:
            ai_rating = ai_sf.ai_rating
        elif user_sf is not None:
            ai_rating = user_sf.ai_rating
        else:
            ai_rating = None
        if ai_sf is not None and ai_sf.ai_comment:
            ai_comment = ai_sf.ai_comment
        elif user_sf is not None:
            ai_comment = user_sf.ai_comment
        else:
            ai_comment = None
        return StageFeedback(
            rating=rating,
            comment=comment,
            ai_rating=ai_rating,
            ai_comment=ai_comment,
        )

    user_overall = existing.overall if existing else None
    ai_overall = ai_fb.overall if ai_fb else None
    merged.overall = _merge_stage(user_overall, ai_overall)

    stage_names: set[str] = set()
    if existing:
        stage_names.update(existing.stages.keys())
    if ai_fb:
        stage_names.update(ai_fb.stages.keys())
    for name in stage_names:
        merged.stages[name] = _merge_stage(
            existing.stages.get(name) if existing else None,
            ai_fb.stages.get(name) if ai_fb else None,
        )
    return merged


def _push_feedback_to_db(
    root: Path, *, plan_name: str, feedback_dict: dict[str, Any]
) -> dict[str, Any]:
    """Push a parsed feedback dict to the DB plan row, if a DB actor is configured.

    Returns a small status dict describing what happened. A missing actor or
    missing DB row is a soft skip — file-mode users shouldn't need a DB at all.
    """

    actor_id = getattr(_push_feedback_to_db, "_actor_override", None) or os.environ.get(
        "MEGAPLAN_ACTOR_ID"
    )
    if not actor_id:
        return {"db_synced": False, "reason": "no actor configured"}
    store = build_epic_store(root, actor_id=actor_id)
    try:
        match = next(
            (p for p in store.list_plans(include_orphans=True) if p.name == plan_name),
            None,
        )
        if match is None:
            return {"db_synced": False, "reason": f"no DB plan named {plan_name!r}"}
        store.update_plan(
            match.id, expected_revision=match.revision, feedback=feedback_dict
        )
        return {"db_synced": True, "plan_id": match.id}
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def handle_feedback(root: Path, args: argparse.Namespace) -> StepResponse:
    """Scaffold, edit, or display ``feedback.md`` for a plan.

    The local ``feedback.md`` is always the editor surface. If a DB actor is
    configured (``--actor`` or ``MEGAPLAN_ACTOR_ID``), parsed feedback is also
    pushed to the ``plans.feedback`` column so backends stay in sync.
    """

    import subprocess

    from megaplan._core.io import atomic_write_text
    from megaplan.orchestration.feedback import (
        FEEDBACK_FILENAME,
        PlanFeedback,
        feedback_path,
        format_summary,
        load_feedback,
        render_template,
    )

    actor_override = getattr(args, "actor", None)
    if actor_override:
        _push_feedback_to_db._actor_override = actor_override  # type: ignore[attr-defined]
        _collect_feedback_rows._actor_override = actor_override  # type: ignore[attr-defined]

    operation = getattr(args, "operation", "edit")
    if getattr(args, "show", False):
        operation = "show"

    # --- search: scan plans across backends, apply filters, render
    if operation == "search":
        rows = _collect_feedback_rows(root, all_system=getattr(args, "all", False))
        filtered = _filter_feedback_rows(rows, args)
        if getattr(args, "emit_json", False):
            return {
                "success": True,
                "step": "feedback",
                "operation": "search",
                "count": len(filtered),
                "scanned": len(rows),
                "rows": filtered,
            }
        return {
            "success": True,
            "step": "feedback",
            "operation": "search",
            "count": len(filtered),
            "scanned": len(rows),
            "rows": filtered,
            "summary": (
                f"{len(filtered)} of {len(rows)} plans with feedback match.\n\n"
                + _render_feedback_table(filtered)
            ),
        }

    # edit / show both require --plan
    if not getattr(args, "plan", None):
        raise CliError(
            "invalid_args", "feedback edit/show/workflow require --plan <name>"
        )

    plan_dir, state = load_plan(root, args.plan)
    path = feedback_path(plan_dir)

    # --- workflow: AI-rated feedback for the auto-driver
    if operation == "workflow":
        current_state = state.get("current_state")
        if current_state != STATE_REVIEWED:
            raise CliError(
                "invalid_state",
                f"feedback workflow requires plan in {STATE_REVIEWED!r} state, "
                f"but plan is in {current_state!r}",
            )

        existing_fb: PlanFeedback | None = (
            load_feedback(plan_dir) if path.exists() else None
        )
        force = bool(getattr(args, "force", False))

        def _has_user_fields(fb: PlanFeedback | None) -> bool:
            if fb is None:
                return False
            if fb.overall.rating is not None or (fb.overall.comment or "").strip():
                return True
            for sf in fb.stages.values():
                if sf.rating is not None or (sf.comment or "").strip():
                    return True
            return False

        if _has_user_fields(existing_fb) and not force:
            state["current_state"] = STATE_DONE
            save_state(plan_dir, state)
            return {
                "success": True,
                "step": "feedback",
                "operation": "workflow",
                "plan": state["name"],
                "plan_dir": str(plan_dir),
                "feedback_path": str(path),
                "feedback_present": True,
                "ai_filled": False,
                "state": "done",
                "summary": "skipped AI pass — user feedback already exists",
            }

        ai_filled = False
        ai_fb: PlanFeedback | None = None
        try:
            from megaplan.handlers.shared import _run_worker

            worker, _agent, _mode, _refreshed = _run_worker(
                "feedback", state, plan_dir, args, root=root
            )
            ai_fb = _parse_ai_feedback(worker.payload, worker.raw_output)
            ai_filled = ai_fb is not None
        except (
            Exception
        ) as exc:  # noqa: BLE001 — feedback failure must not sink the plan
            sys.stderr.write(
                f"[feedback] worker failed, scaffolding empty template: {exc}\n"
            )

        merged = _merge_feedback(existing_fb, ai_fb)
        template = render_template(
            state["name"], idea=state.get("idea"), prefilled=merged
        )
        atomic_write_text(path, template)

        state["current_state"] = STATE_DONE
        save_state(plan_dir, state)

        return {
            "success": True,
            "step": "feedback",
            "operation": "workflow",
            "plan": state["name"],
            "plan_dir": str(plan_dir),
            "feedback_path": str(path),
            "feedback_present": True,
            "ai_filled": ai_filled,
            "state": "done",
            "summary": (
                "populated AI ratings — review and edit anytime"
                if ai_filled
                else "scaffolded feedback.md — fill in whenever"
            ),
        }

    if operation == "show":
        fb = load_feedback(plan_dir)
        if fb is None:
            return {
                "success": True,
                "step": "feedback",
                "plan": state["name"],
                "plan_dir": str(plan_dir),
                "feedback_path": str(path),
                "feedback_present": False,
                "summary": f"No {FEEDBACK_FILENAME} for this plan yet.",
            }
        return {
            "success": True,
            "step": "feedback",
            "plan": state["name"],
            "plan_dir": str(plan_dir),
            "feedback_path": str(path),
            "feedback_present": True,
            "summary": format_summary(fb),
            "feedback": fb.to_dict(),
        }

    created = False
    if not path.exists():
        template = render_template(state["name"], idea=state.get("idea"))
        atomic_write_text(path, template)
        created = True

    opened = False
    if not getattr(args, "no_edit", False):
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if editor:
            try:
                subprocess.run([*editor.split(), str(path)], check=False)
                opened = True
            except (FileNotFoundError, OSError):
                opened = False

    fb = load_feedback(plan_dir)
    db_status = {"db_synced": False, "reason": "no edits to push"}
    if fb is not None and not fb.is_empty():
        try:
            db_status = _push_feedback_to_db(
                root, plan_name=state["name"], feedback_dict=fb.to_dict()
            )
        except (
            Exception
        ) as exc:  # noqa: BLE001 — surface failure but don't break editor flow
            db_status = {"db_synced": False, "reason": f"db push failed: {exc}"}

    msg_parts: list[str] = []
    msg_parts.append("Created" if created else "Found existing")
    msg_parts.append(FEEDBACK_FILENAME)
    if opened:
        msg_parts.append("(opened in $EDITOR)")
    if db_status.get("db_synced"):
        msg_parts.append("→ synced to DB")
    return {
        "success": True,
        "step": "feedback",
        "plan": state["name"],
        "plan_dir": str(plan_dir),
        "feedback_path": str(path),
        "feedback_present": path.exists(),
        "created": created,
        "opened_in_editor": opened,
        "db_status": db_status,
        "summary": f"{' '.join(msg_parts)} at {path}",
    }


# ---------------------------------------------------------------------------
# Parser and dispatch
# ---------------------------------------------------------------------------


def _add_vendor_critic_args(parser: argparse.ArgumentParser) -> None:
    """Wire profile modifier flags onto a subparser.

    Kept as one helper so the wiring stays consistent across the five
    subcommands that take a ``--profile``. All flags default to
    ``None`` so ``apply_profile_expansion`` can distinguish "user
    didn't say" from "user explicitly picked claude/kimi/etc." and
    consult the config default in the former case.
    """
    parser.add_argument(
        "--vendor",
        choices=["claude", "codex"],
        default=None,
        help="Pick the premium vendor for tier-2-through-4 profile slots. "
        "Swaps claude:X <-> codex:X at the same effort tier; hermes specs "
        "untouched. Defaults to ~/.config/megaplan/config.toml "
        "[defaults].vendor (or 'claude'). Silently ignored when the "
        "active profile is vendor_locked = true.",
    )
    parser.add_argument(
        "--depth",
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
        default=None,
        help="Set author-phase thinking depth (plan / revise / loop_plan / "
        "tiebreaker_researcher / tiebreaker_challenger). Rewrites the "
        "effort suffix on claude:X / codex:X slots; critic and "
        "mechanical phases are not touched (asymmetry principle). "
        "hermes specs and profiles with no premium author slots are a "
        "silent no-op. Defaults to whatever depth the profile already "
        "sets (usually :low). Honored on vendor_locked profiles.",
    )
    parser.add_argument(
        "--critic",
        choices=["kimi", "cross"],
        default=None,
        help="Override the critique+review pair (the critique == review "
        "invariant — same mind pre- and post-execution). 'kimi' swaps "
        "in Kimi (Fireworks-hosted kimi-k2p6) for both phases; 'cross' swaps to the other "
        "premium vendor relative to --vendor. Silently ignored on "
        "vendor_locked profiles.",
    )
    parser.add_argument(
        "--deepseek-provider",
        choices=["fireworks", "direct"],
        default=None,
        help="Choose the provider for canonical DeepSeek v4-pro profile slots. "
        "'fireworks' uses hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro; "
        "'direct' uses hermes:deepseek:deepseek-v4-pro and DEEPSEEK_API_KEY. "
        "Defaults to 'direct'. Non-DeepSeek slots are untouched.",
    )
    parser.add_argument(
        "--with-prep",
        action="store_true",
        default=False,
        help="Force the visible prep phase into the workflow regardless of "
        "--robustness. By default, prep only runs at --robustness "
        "thorough|extreme; this flag adds prep to full / light / "
        "bare so the planner can do explicit research before committing "
        "to a plan. Useful for unfamiliar libraries, novel external "
        "APIs, research-heavy briefs, or ambiguous requirements. "
        "Redundant on --robustness thorough|extreme (no-op).",
    )
    parser.add_argument(
        "--with-feedback",
        action="store_true",
        default=False,
        help="Force the visible feedback phase into the workflow regardless "
        "of --robustness. By default no feedback step runs; this flag "
        "adds a feedback step between review and done that scaffolds "
        "feedback.md (a per-stage ratings template) for the user to "
        "fill in afterward. Runs non-interactively under megaplan auto "
        "\u2014 never blocks on human input.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Megaplan orchestration CLI")
    parser.add_argument(
        "--actor",
        default=None,
        metavar="ID",
        help="Actor ID for DB writes (also MEGAPLAN_ACTOR_ID)",
    )
    parser.add_argument(
        "--backend",
        choices=["file", "db"],
        default=None,
        help="Storage backend (also MEGAPLAN_BACKEND)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser(
        "setup", help="Install megaplan into agent configs (global by default)"
    )
    setup_parser.add_argument(
        "--local",
        action="store_true",
        help="Install AGENTS.md into a project instead of global agent configs",
    )
    setup_parser.add_argument(
        "--target-dir", help="Directory to install into (default: cwd, implies --local)"
    )
    setup_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing files"
    )
    setup_parser.add_argument(
        "--regen-composed",
        action="store_true",
        help="Regenerate composed skill bundles from source files",
    )

    init_parser = subparsers.add_parser("init")
    # --project-dir is normally required; the special case is --in-worktree,
    # which supplies the project-dir itself (the newly-created worktree).
    # We validate the mutual relationship in main() after parsing.
    init_parser.add_argument("--project-dir", required=False)
    init_parser.add_argument(
        "--in-worktree",
        default=None,
        metavar="NAME",
        help="Create a new git worktree at ~/Documents/.megaplan-worktrees/<name>/ "
        "on a new branch and initialize the plan inside it. Name must match "
        "^[a-z0-9][a-z0-9._-]{0,63}$. Substitutes for --project-dir.",
    )
    init_parser.add_argument(
        "--worktree-from",
        default=None,
        metavar="GITREF",
        help="Base ref for the new worktree (default: current HEAD of the repo "
        "where `megaplan init` was invoked). Only valid with --in-worktree.",
    )
    init_parser.add_argument(
        "--clean-worktree",
        action="store_true",
        default=False,
        help="With --in-worktree: fork from a clean base ref and leave any "
        "uncommitted state behind in the source repo (no carry).",
    )
    init_parser.add_argument(
        "--carry-dirty",
        action="store_true",
        default=False,
        help="With --in-worktree: explicitly opt into carrying uncommitted "
        "state from the source repo into the new worktree (this is the "
        "default already when the source is dirty; the flag exists for "
        "test/script clarity). Mutually exclusive with --clean-worktree.",
    )
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
    # Accept canonical names plus legacy aliases (tiny|standard|robust|superrobust);
    # ``normalize_robustness`` collapses them downstream.
    init_parser.add_argument(
        "--robustness", choices=list(ROBUSTNESS_ACCEPTED), default=None
    )
    init_parser.add_argument(
        "--mode",
        choices=["code", "doc", "metaplan", "joke", "creative"],
        default=None,
        help="Deliverable type: 'code' (source changes), 'doc' / 'metaplan' "
        "(design/spec artifact — 'metaplan' is an alias for 'doc'), or "
        "'joke' (film scene script; requires --output), or "
        "'creative' (creative work; requires --form and --output). "
        "Defaults to 'code' unless the idea strongly suggests a design document, "
        "in which case --mode must be passed explicitly.",
    )
    init_parser.add_argument(
        "--form",
        choices=available_form_ids(),
        default=None,
        help="Creative form to use with --mode creative.",
    )
    init_parser.add_argument(
        "--output",
        default=None,
        help="Relative path where the prose artifact will be written. "
        "Required with --mode doc, --mode joke, or --mode creative; rejected with --mode code.",
    )
    init_parser.add_argument(
        "--primary-criterion",
        default=None,
        help="Declare the creative-work primary criterion (for example: 'weirdest coherent'). "
        "Valid only with --mode joke or --mode creative.",
    )
    init_parser.add_argument(
        "--from-doc",
        default=None,
        help="Relative path to a prior doc-mode artifact whose ## Settled "
        "Decisions section should be imported. Valid with --mode "
        "code, --mode doc, --mode joke, or --mode creative.",
    )
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
    init_parser.add_argument(
        "--hermes",
        nargs="?",
        const="",
        default=None,
        help="Use Hermes agent for all phases. Optional: specify default model",
    )
    init_parser.add_argument(
        "--phase-model",
        action="append",
        default=[],
        help="Per-phase model override: --phase-model critique=hermes:openai/gpt-5",
    )
    init_parser.add_argument(
        "--profile",
        default=None,
        help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
    )
    _add_vendor_critic_args(init_parser)
    init_parser.add_argument(
        "--prep-direction",
        default=None,
        metavar="TEXT",
        help="Steering text shown to the prep worker as 'User direction for prep'. "
        "Use to point prep at specific files, subsystems, or questions to explore "
        "(e.g. 'focus on the worker shutdown path; ignore CLI plumbing'). "
        "Only effective when prep runs (robustness thorough|extreme, or --with-prep).",
    )
    init_parser.add_argument(
        "--from-arnold-epic",
        default=None,
        metavar="EPIC_ID",
        help="Load plan idea from Arnold epic via DBStore (read-only; --backend db not required for read path)",
    )
    init_parser.add_argument("idea", nargs="?")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="Search all .megaplan directories system-wide (~)",
    )
    list_parser.add_argument(
        "--no-tree",
        action="store_true",
        help="Only show plans from the current directory (default includes parent + child)",
    )
    list_parser.add_argument(
        "--include-done",
        action="store_true",
        help="Include terminal plans; excluded by default",
    )
    list_parser.add_argument(
        "--status",
        dest="filter_status",
        help="Filter by state (e.g. 'done', 'finalized', 'executed', or comma-separated 'planned,critiqued')",
    )
    list_parser.add_argument(
        "--summary", action="store_true", help="Show count breakdown by state"
    )
    list_parser.add_argument(
        "list_target",
        nargs="?",
        choices=["pipelines"],
        help="List pipelines instead of plans (use 'pipelines')",
    )
    list_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose pipeline listing (description, version, profile)",
    )

    describe_parser = subparsers.add_parser(
        "describe", help="Show metadata and SKILL.md for a YAML pipeline"
    )
    describe_parser.add_argument(
        "pipeline_name",
        help="Name of the pipeline to describe (e.g. 'writing-panel-strict')",
    )
    describe_parser.set_defaults(func=handle_describe)

    epic_parser = subparsers.add_parser("epic", help="Inspect or migrate Arnold epics")
    epic_parser.add_argument("--project-dir", default=None)
    epic_subparsers = epic_parser.add_subparsers(dest="epic_action", required=True)
    epic_snapshot_parser = epic_subparsers.add_parser(
        "snapshot", help="Write an offline JSON snapshot for an epic"
    )
    epic_snapshot_parser.add_argument("epic_id")
    epic_snapshot_parser.add_argument("--project-dir", default=None)
    epic_migrate_parser = epic_subparsers.add_parser(
        "migrate", help="Promote or demote an epic between backends"
    )
    epic_migrate_parser.add_argument("epic_id", nargs="?")
    epic_migrate_parser.add_argument("--to", choices=["file", "db"], default=None)
    epic_migrate_parser.add_argument("--resume", metavar="MIGRATION_ID", default=None)
    epic_migrate_parser.add_argument(
        "--actor", default=None, metavar="ID", help="Actor ID for migration writes"
    )
    epic_migrate_parser.add_argument("--ttl", type=int, default=300)
    epic_migrate_parser.add_argument("--project-dir", default=None)
    epic_export_parser = epic_subparsers.add_parser(
        "export", help="Write a deterministic tar backup for an epic"
    )
    epic_export_parser.add_argument("epic_id")
    epic_export_parser.add_argument("--output", required=True)
    epic_export_parser.add_argument("--gzip", action="store_true")
    epic_export_parser.add_argument("--allow-missing-blobs", action="store_true")
    epic_export_parser.add_argument("--project-dir", default=None)

    # --- ticket subcommand group ---
    ticket_parser = subparsers.add_parser(
        "ticket", help="Manage repo-scoped issue/problem tickets"
    )
    ticket_sub = ticket_parser.add_subparsers(dest="ticket_action", required=True)

    # ticket new
    ticket_new_parser = ticket_sub.add_parser("new", help="Create a new ticket")
    ticket_new_parser.add_argument("title", help="Ticket title")
    ticket_new_body_group = ticket_new_parser.add_mutually_exclusive_group(
        required=True
    )
    ticket_new_body_group.add_argument(
        "-b", dest="body", default=None, metavar="BODY", help="Body text"
    )
    ticket_new_body_group.add_argument(
        "--edit", action="store_true", help="Open $EDITOR for body"
    )
    ticket_new_body_group.add_argument(
        "-", dest="stdin_body", action="store_true", help="Read body from stdin"
    )
    ticket_new_parser.add_argument("--tags", default=None, help="Comma-separated tags")

    # ticket list
    ticket_list_parser = ticket_sub.add_parser("list", help="List tickets")
    ticket_list_parser.add_argument("--status", default=None, help="Filter by status")
    ticket_list_parser.add_argument(
        "--tags", default=None, help="Filter by tags (comma-separated)"
    )
    ticket_list_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # ticket show
    ticket_show_parser = ticket_sub.add_parser("show", help="Show a single ticket")
    ticket_show_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_show_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # ticket edit
    ticket_edit_parser = ticket_sub.add_parser("edit", help="Edit a ticket")
    ticket_edit_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_edit_parser.add_argument("--title", default=None, help="New title")
    ticket_edit_parser.add_argument("--body", default=None, help="New body")
    ticket_edit_parser.add_argument("--status", default=None, help="New status")
    ticket_edit_parser.add_argument("--add-tag", default=None, help="Tag to add")
    ticket_edit_parser.add_argument("--remove-tag", default=None, help="Tag to remove")

    # ticket link
    ticket_link_parser = ticket_sub.add_parser("link", help="Link a ticket to an epic")
    ticket_link_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_link_parser.add_argument("epic_id", help="Epic ID")
    ticket_link_parser.add_argument(
        "--resolves", action="store_true", help="Epic completion resolves this ticket"
    )

    # ticket unlink
    ticket_unlink_parser = ticket_sub.add_parser(
        "unlink", help="Unlink a ticket from an epic"
    )
    ticket_unlink_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_unlink_parser.add_argument("epic_id", help="Epic ID")

    # ticket addressed
    ticket_addressed_parser = ticket_sub.add_parser(
        "addressed", help="Mark ticket as addressed"
    )
    ticket_addressed_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_addressed_parser.add_argument("--note", default=None, help="Resolution note")

    # ticket dismiss
    ticket_dismiss_parser = ticket_sub.add_parser("dismiss", help="Dismiss a ticket")
    ticket_dismiss_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_dismiss_parser.add_argument(
        "--reason", default=None, help="Reason for dismissal"
    )

    # ticket reopen
    ticket_reopen_parser = ticket_sub.add_parser("reopen", help="Reopen a ticket")
    ticket_reopen_parser.add_argument("ticket_id", help="Ticket ULID")

    # ticket search
    ticket_search_parser = ticket_sub.add_parser(
        "search",
        help="Search tickets across local and cloud, multi-project, multi-keyword",
    )
    ticket_search_parser.add_argument(
        "keywords",
        nargs="*",
        help="Keywords to match (case-insensitive substring across title, body, tags, resolution_note). Default OR; pass --all for AND.",
    )
    ticket_search_parser.add_argument(
        "--all",
        dest="keywords_all",
        action="store_true",
        help="Require ALL keywords to match (AND). Default is OR (any).",
    )
    ticket_search_parser.add_argument(
        "--project",
        dest="projects",
        action="append",
        default=None,
        help="Repo to search — path, owner/name, or bare name. Repeatable.",
    )
    ticket_search_parser.add_argument(
        "--all-projects",
        action="store_true",
        help="Search every known repo (local) or every codebase (cloud).",
    )
    ticket_search_parser.add_argument("--status", default=None, help="Filter by status")
    ticket_search_parser.add_argument(
        "--tags", default=None, help="Filter by tags (comma-separated)"
    )
    ticket_search_parser.add_argument(
        "--sort",
        choices=["created", "edited", "length", "title"],
        default="created",
        help="Sort key (default: created)",
    )
    ticket_search_parser.add_argument(
        "--asc",
        action="store_true",
        help="Ascending order (default: descending)",
    )
    ticket_search_parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of results"
    )
    ticket_search_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    ticket_search_parser.add_argument(
        "--no-snippet",
        dest="snippet",
        action="store_false",
        default=True,
        help="Hide snippet column in human output",
    )

    migrate_local_parser = subparsers.add_parser(
        "migrate-local-plans", help="Import legacy ~/.megaplan/<project>/plans trees"
    )
    migrate_local_parser.add_argument("--source-home", default=str(Path.home()))
    migrate_local_parser.add_argument("--source-project", default=None)
    migrate_local_parser.add_argument("--all-projects", action="store_true")
    migrate_local_parser.add_argument("--target-project-dir", required=True)
    migrate_local_parser.add_argument(
        "--mode", choices=["orphan", "legacy-epic"], default="orphan"
    )
    migrate_local_parser.add_argument("--dry-run", action="store_true")

    for name in ["status", "progress", "watch"]:
        step_parser = subparsers.add_parser(name)
        step_parser.add_argument("--plan")
        if name == "status":
            step_parser.add_argument(
                "--pending-human",
                action="store_true",
                help="List plans awaiting human verification",
            )

    feedback_parser = subparsers.add_parser(
        "feedback",
        help="Scaffold, edit, or search external feedback.md for plans (per-stage 0-10 ratings + comments)",
    )
    feedback_parser.add_argument(
        "operation",
        nargs="?",
        default="edit",
        choices=["edit", "show", "search", "workflow"],
        help="edit (default): scaffold/open feedback.md. show: print parsed summary. search: query feedback across plans",
    )
    feedback_parser.add_argument(
        "--plan", required=False, help="Plan name (required for edit/show)"
    )
    feedback_parser.add_argument(
        "--show",
        action="store_true",
        help="(legacy alias) equivalent to: feedback show --plan <name>",
    )
    feedback_parser.add_argument(
        "--no-edit",
        action="store_true",
        help="edit: just scaffold the template (if missing) and print the path; do not open $EDITOR",
    )
    feedback_parser.add_argument(
        "--force",
        action="store_true",
        help="workflow: re-run the AI rating pass even if feedback.md already has user fields. "
        "Overwrites ai_rating/ai_comment only; never touches user rating:/comment:.",
    )
    feedback_parser.add_argument(
        "--profile",
        default=None,
        help="search: substring match on plan profile (e.g. 'claude', 'apex')",
    )
    feedback_parser.add_argument(
        "--repo",
        default=None,
        help="search: substring match on plan project_dir / repo path",
    )
    feedback_parser.add_argument(
        "--min-rating",
        type=int,
        default=None,
        help="search: only show plans with Overall rating >= N",
    )
    feedback_parser.add_argument(
        "--max-rating",
        type=int,
        default=None,
        help="search: only show plans with Overall rating <= N",
    )
    feedback_parser.add_argument(
        "--stage",
        default=None,
        help="search: only show plans that have a rating for this stage",
    )
    feedback_parser.add_argument(
        "--has-comment",
        action="store_true",
        help="search: only show plans whose Overall comment is non-empty",
    )
    feedback_parser.add_argument(
        "--all",
        action="store_true",
        help="search: scan all megaplan project roots on this machine, not just the current tree",
    )
    feedback_parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="search: emit raw JSON instead of a table",
    )

    resume_parser = subparsers.add_parser(
        "resume", help="Resume a failed or blocked plan from its stored cursor"
    )
    resume_parser.add_argument("--plan", required=True)
    resume_parser.add_argument(
        "--choice",
        default=None,
        help="For YAML pipelines paused at human_gate: the choice to resume with (e.g. continue, stop)",
    )

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--plan")
    audit_sub = audit_parser.add_subparsers(dest="audit_action", required=False)
    audit_query_parser = audit_sub.add_parser(
        "query", help="Query step receipts across plans"
    )
    audit_query_parser.add_argument("--model")
    audit_query_parser.add_argument("--phase")
    audit_query_parser.add_argument("--profile")
    audit_query_parser.add_argument("--since")
    audit_query_parser.add_argument("--agg", default="")
    audit_query_parser.add_argument("--json", action="store_true")
    audit_query_parser.add_argument("--audit-dir", default=None)
    audit_report_parser = audit_sub.add_parser("report", help="Render a plan retrospective from local audit artifacts")
    audit_report_parser.add_argument("--plan", help="Plan name. May also be passed before the report subcommand.")
    audit_report_parser.add_argument("--compare", help="Optional prior plan name to compare receipt totals against")
    audit_report_parser.add_argument("--output", help="Write Markdown report to this path instead of stdout")
    audit_report_parser.add_argument("--json-output", help="Write the structured report payload to this path")
    audit_report_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")

    for name in [
        "plan",
        "prep",
        "critique",
        "revise",
        "gate",
        "finalize",
        "execute",
        "review",
    ]:
        step_parser = subparsers.add_parser(name)
        step_parser.add_argument("--plan")
        step_parser.add_argument("--agent", choices=KNOWN_AGENTS)
        step_parser.add_argument(
            "--hermes",
            nargs="?",
            const="",
            default=None,
            help="Use Hermes agent for all phases. Optional: specify default model (e.g. --hermes anthropic/claude-sonnet-4.6)",
        )
        step_parser.add_argument(
            "--phase-model",
            action="append",
            default=[],
            help="Per-phase model override: --phase-model critique=hermes:openai/gpt-5",
        )
        step_parser.add_argument(
            "--profile",
            default=None,
            help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
        )
        _add_vendor_critic_args(step_parser)
        step_parser.add_argument("--fresh", action="store_true")
        step_parser.add_argument("--persist", action="store_true")
        step_parser.add_argument("--ephemeral", action="store_true")
        step_parser.add_argument(
            "--work-dir",
            default=None,
            help="Override the source-code working directory passed to subprocess workers "
            "(--add-dir / -C). Defaults to the current working directory. Use this to "
            "force a specific path (e.g. a git worktree) regardless of where the plan was created.",
        )
        if name == "prep":
            step_parser.add_argument(
                "--direction",
                dest="prep_direction",
                default=None,
                metavar="TEXT",
                help="Set or replace the prep direction (state.config.prep_direction) "
                "before the prep worker runs. Same semantics as `init --prep-direction`, "
                "but applied at prep time so you can steer prep without re-initializing.",
            )
        if name == "execute":
            step_parser.add_argument("--confirm-destructive", action="store_true")
            step_parser.add_argument("--user-approved", action="store_true")
            step_parser.add_argument(
                "--batch",
                type=int,
                default=None,
                help="Execute a specific global batch number (1-indexed)",
            )
            step_parser.add_argument(
                "--retry-blocked-tasks",
                action="store_true",
                help=(
                    "Reset any tasks persisted at status=blocked back to pending "
                    "before computing batches. Use when re-running execute after "
                    "resolving an external prerequisite that previously blocked a "
                    "task. The auto-driver passes this on every fresh invocation."
                ),
            )
        if name == "review":
            step_parser.add_argument("--confirm-self-review", action="store_true")

    config_parser = subparsers.add_parser(
        "config", help="View or edit megaplan configuration"
    )
    config_sub = config_parser.add_subparsers(dest="config_action", required=True)
    config_sub.add_parser("show")
    set_parser = config_sub.add_parser("set")
    set_parser.add_argument("key")
    set_parser.add_argument("value")
    config_sub.add_parser("reset")
    profiles_parser = config_sub.add_parser(
        "profiles",
        help="Inspect model profiles from built-in, user, and project layers",
    )
    profiles_sub = profiles_parser.add_subparsers(dest="profiles_action", required=True)
    profiles_sub.add_parser(
        "list",
        help="List profiles from all layers",
        description="List profiles from all layers. Project-layer profiles are only visible when run from that project directory.",
    )
    profiles_show_parser = profiles_sub.add_parser(
        "show", help="Show the fully resolved phase map for one profile"
    )
    profiles_show_parser.add_argument("name")
    use_profile_parser = config_sub.add_parser(
        "use-profile",
        help="Apply a profile as the user-config default agent routing (writes every agents.<phase>)",
        description=(
            "Apply a named profile from built-in/user/project layers as the persisted default "
            "agent routing in ~/.config/megaplan/config.json. Equivalent to running "
            "'config set agents.<phase> <agent>' for every phase in the profile, but accepts "
            "agent specs with model qualifiers (e.g. 'hermes:glm-5.1') the same way profiles do."
        ),
    )
    use_profile_parser.add_argument(
        "name", help="Profile name (see 'megaplan config profiles list')"
    )

    step_parser = subparsers.add_parser(
        "step", help="Edit plan step sections without hand-editing markdown"
    )
    step_subparsers = step_parser.add_subparsers(dest="step_action", required=True)

    step_add_parser = step_subparsers.add_parser(
        "add", help="Insert a new step after an existing step"
    )
    step_add_parser.add_argument("--plan")
    step_add_parser.add_argument("--after")
    step_add_parser.add_argument("description")

    step_remove_parser = step_subparsers.add_parser(
        "remove", help="Remove a step and renumber the plan"
    )
    step_remove_parser.add_argument("--plan")
    step_remove_parser.add_argument("step_id")

    step_move_parser = step_subparsers.add_parser(
        "move", help="Move a step after another step and renumber"
    )
    step_move_parser.add_argument("--plan")
    step_move_parser.add_argument("step_id")
    step_move_parser.add_argument("--after", required=True)

    override_parser = subparsers.add_parser("override")
    override_parser.add_argument(
        "override_action",
        choices=[
            "abort",
            "force-proceed",
            "add-note",
            "replan",
            "recover-blocked",
            "set-robustness",
            "set-profile",
        ],
    )
    override_parser.add_argument("--plan")
    override_parser.add_argument("--reason", default="")
    override_parser.add_argument("--note")
    override_parser.add_argument(
        "--robustness", choices=list(ROBUSTNESS_ACCEPTED), default=None
    )
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

    user_action_parser = subparsers.add_parser(
        "user-action",
        help="Resolve user action prerequisites",
    )
    ua_subparsers = user_action_parser.add_subparsers(
        dest="user_action_action", required=True
    )

    from megaplan.user_actions import VALID_RESOLUTIONS as _UA_VALID_RESOLUTIONS

    ua_resolve_parser = ua_subparsers.add_parser(
        "resolve",
        help="Record a resolution for a user action prerequisite",
    )
    ua_resolve_parser.add_argument("--plan")
    ua_resolve_parser.add_argument(
        "--action-id",
        required=True,
        help="User action ID (from finalize.json)",
    )
    ua_resolve_parser.add_argument(
        "--resolution",
        required=True,
        choices=list(_UA_VALID_RESOLUTIONS),
        help="Resolution to record",
    )
    ua_resolve_parser.add_argument(
        "--fallback-mode",
        default=None,
        help="Fallback execution mode (for accepted_blocked / waived)",
    )
    ua_resolve_parser.add_argument(
        "--tasks",
        default=None,
        help="Comma-separated task IDs this resolution applies to",
    )
    ua_resolve_parser.add_argument(
        "--instructions",
        default=None,
        help="Fallback instructions for the executor",
    )
    ua_resolve_parser.add_argument(
        "--reason",
        default=None,
        help="Human-readable reason for the resolution",
    )
    ua_resolve_parser.add_argument(
        "--phase",
        default=None,
        help="Phase where this resolution was recorded",
    )
    ua_resolve_parser.add_argument(
        "--evidence",
        action="append",
        default=None,
        help="Evidence for the resolution; repeat or comma-separate values",
    )
    ua_resolve_parser.add_argument(
        "--debt-note",
        default=None,
        help="Debt note to carry with the resolution",
    )

    quality_gate_parser = subparsers.add_parser(
        "quality-gate",
        help="Resolve quality gate blockers",
    )
    qg_subparsers = quality_gate_parser.add_subparsers(
        dest="quality_gate_action", required=True
    )
    qg_resolve_parser = qg_subparsers.add_parser(
        "resolve",
        help="Record a resolution for a quality gate blocker",
    )
    qg_resolve_parser.add_argument("--plan")
    qg_resolve_parser.add_argument(
        "--blocker-id",
        required=True,
        help="Quality blocker ID from phase_result/status output",
    )
    qg_resolve_parser.add_argument(
        "--resolution",
        required=True,
        choices=list(QUALITY_VALID_RESOLUTIONS),
        help="Resolution to record",
    )
    qg_resolve_parser.add_argument(
        "--phase",
        default=None,
        help="Phase where this resolution was recorded",
    )
    qg_resolve_parser.add_argument(
        "--evidence",
        action="append",
        default=None,
        help="Evidence for the resolution; repeat or comma-separate values",
    )
    qg_resolve_parser.add_argument(
        "--debt-note",
        default=None,
        help="Debt note for accepted_with_debt resolutions",
    )
    qg_resolve_parser.add_argument(
        "--fallback-mode",
        default=None,
        help="Fallback execution mode associated with this quality resolution",
    )

    verify_human_parser = subparsers.add_parser(
        "verify-human", help="Record human verification for a criterion"
    )
    verify_human_parser.add_argument("--plan")
    verify_human_parser.add_argument(
        "--criterion", required=False, default=None, help="Criterion name or index"
    )
    vh_group = verify_human_parser.add_mutually_exclusive_group(required=False)
    vh_group.add_argument("--pass", dest="pass_flag", action="store_true")
    vh_group.add_argument("--fail", dest="fail_flag", action="store_true")
    verify_human_parser.add_argument(
        "--evidence", required=False, default=None, help="Evidence supporting the verdict"
    )
    verify_human_parser.add_argument(
        "--list", dest="list_flag", action="store_true", help="List verification status for all criteria"
    )
    verify_human_parser.add_argument(
        "--json", dest="json_flag", action="store_true", help="Output machine-readable JSON"
    )

    audit_verifiability_parser = subparsers.add_parser(
        "audit-verifiability", help="Audit criteria verifiability"
    )
    audit_verifiability_parser.add_argument("--plan")

    debt_parser = subparsers.add_parser(
        "debt", help="Inspect or manage persistent tech debt entries"
    )
    debt_subparsers = debt_parser.add_subparsers(dest="debt_action", required=True)

    debt_list_parser = debt_subparsers.add_parser("list", help="List debt entries")
    debt_list_parser.add_argument(
        "--all", action="store_true", help="Include resolved entries"
    )

    debt_add_parser = debt_subparsers.add_parser(
        "add", help="Add or increment a debt entry"
    )
    debt_add_parser.add_argument("--subsystem", required=True)
    debt_add_parser.add_argument("--concern", required=True)
    debt_add_parser.add_argument("--flag-ids", default="")
    debt_add_parser.add_argument("--plan")

    debt_resolve_parser = debt_subparsers.add_parser(
        "resolve", help="Resolve a debt entry"
    )
    debt_resolve_parser.add_argument("debt_id")
    debt_resolve_parser.add_argument("--plan")

    loop_init_parser = subparsers.add_parser(
        "loop-init", help="Initialize a MegaLoop workflow"
    )
    loop_init_parser.add_argument("--project-dir", required=True)
    loop_init_parser.add_argument("--command", required=True)
    loop_init_parser.add_argument("--goal", dest="goal_option")
    loop_init_parser.add_argument("--name")
    loop_init_parser.add_argument("--iterations", type=int, default=3)
    loop_init_parser.add_argument("--time-budget", type=int, default=300)
    loop_init_parser.add_argument("--observe-interval", type=int)
    loop_init_parser.add_argument("--observe-break-patterns")
    loop_init_parser.add_argument("--agent", choices=KNOWN_AGENTS)
    loop_init_parser.add_argument(
        "--hermes",
        nargs="?",
        const="",
        default=None,
        help="Use Hermes agent for loop phases. Optional: specify default model",
    )
    loop_init_parser.add_argument(
        "--phase-model",
        action="append",
        default=[],
        help="Per-phase model override: --phase-model loop_execute=hermes:openai/gpt-5",
    )
    loop_init_parser.add_argument(
        "--profile",
        default=None,
        help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
    )
    _add_vendor_critic_args(loop_init_parser)
    loop_init_parser.add_argument("--fresh", action="store_true")
    loop_init_parser.add_argument("--persist", action="store_true")
    loop_init_parser.add_argument("--ephemeral", action="store_true")
    loop_init_parser.add_argument(
        "--work-dir",
        default=None,
        help="Override the source-code working directory for subprocess workers (default: CWD)",
    )
    loop_init_parser.add_argument("goal", nargs="?")

    loop_run_parser = subparsers.add_parser(
        "loop-run", help="Run an existing MegaLoop workflow"
    )
    loop_run_parser.add_argument("name")
    loop_run_parser.add_argument("--project-dir")
    loop_run_parser.add_argument("--iterations", type=int)
    loop_run_parser.add_argument("--time-budget", type=int)
    loop_run_parser.add_argument("--agent", choices=KNOWN_AGENTS)
    loop_run_parser.add_argument(
        "--hermes",
        nargs="?",
        const="",
        default=None,
        help="Use Hermes agent for loop phases. Optional: specify default model",
    )
    loop_run_parser.add_argument(
        "--phase-model",
        action="append",
        default=[],
        help="Per-phase model override: --phase-model loop_execute=hermes:openai/gpt-5",
    )
    loop_run_parser.add_argument(
        "--profile",
        default=None,
        help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
    )
    _add_vendor_critic_args(loop_run_parser)
    loop_run_parser.add_argument("--fresh", action="store_true")
    loop_run_parser.add_argument("--persist", action="store_true")
    loop_run_parser.add_argument("--ephemeral", action="store_true")
    loop_run_parser.add_argument(
        "--work-dir",
        default=None,
        help="Override the source-code working directory for subprocess workers (default: CWD)",
    )

    loop_status_parser = subparsers.add_parser(
        "loop-status", help="Show MegaLoop state"
    )
    loop_status_parser.add_argument("name")
    loop_status_parser.add_argument("--project-dir")

    loop_pause_parser = subparsers.add_parser(
        "loop-pause", help="Pause a MegaLoop workflow"
    )
    loop_pause_parser.add_argument("name")
    loop_pause_parser.add_argument("--project-dir")
    loop_pause_parser.add_argument("--reason", default="")

    from megaplan.auto import build_auto_parser

    build_auto_parser(subparsers)

    from megaplan._pipeline.run_cli import build_run_parser

    build_run_parser(subparsers)

    from megaplan.chain import build_chain_parser

    build_chain_parser(subparsers)

    cloud_parser = subparsers.add_parser(
        "cloud",
        add_help=False,
        help="Manage provider-backed megaplan cloud runners",
    )
    cloud_parser.add_argument("cloud_args", nargs=argparse.REMAINDER)

    resident_parser = subparsers.add_parser(
        "resident",
        add_help=False,
        help="Run resident Discord orchestration services",
    )
    resident_parser.add_argument("resident_args", nargs=argparse.REMAINDER)

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
    tb_run_parser.add_argument("--agent", choices=KNOWN_AGENTS, default=None)
    tb_run_parser.add_argument("--hermes", nargs="?", const="", default=None)
    tb_run_parser.add_argument("--phase-model", action="append", default=[])
    tb_run_parser.add_argument(
        "--profile",
        default=None,
        help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
    )
    _add_vendor_critic_args(tb_run_parser)
    tb_run_parser.add_argument("--fresh", action="store_true")
    tb_run_parser.add_argument("--persist", action="store_true")
    tb_run_parser.add_argument("--ephemeral", action="store_true")

    return parser


def handle_user_action(root: Path, args: argparse.Namespace) -> StepResponse:
    """Handle ``megaplan user-action resolve`` — record a resolution event.

    Validates that *action_id* exists in ``finalize.json.user_actions``,
    validates ``--tasks`` against known task IDs, builds a resolution event
    via :func:`megaplan.user_actions.build_resolution_event`, appends it to
    ``state.meta.user_action_resolutions``, and persists with
    :func:`save_state_merge_meta`.
    """
    from megaplan._core.state import save_state_merge_meta
    from megaplan.blocker_recovery import build_prerequisite_scopes
    from megaplan.handlers.shared import _append_to_meta
    from megaplan.user_actions import VALID_RESOLUTIONS, build_resolution_event

    sub_action = getattr(args, "user_action_action", None)
    if sub_action != "resolve":
        raise CliError(
            "invalid_args",
            f"Unknown user-action sub-command: {sub_action!r}. " "Expected 'resolve'.",
        )

    plan_dir, state = load_plan(root, args.plan)
    action_id: str = getattr(args, "action_id", None) or getattr(args, "action", None)
    resolution: str = getattr(args, "resolution", None) or getattr(args, "state", None)

    # --- validate resolution value -------------------------------------------
    if resolution not in VALID_RESOLUTIONS:
        raise CliError(
            "invalid_args",
            f"Unsupported resolution state {resolution!r}. "
            f"Must be one of: {', '.join(VALID_RESOLUTIONS)}.",
        )

    # --- validate action_id exists in finalize.json --------------------------
    finalize_path = plan_dir / "finalize.json"
    if not finalize_path.exists():
        raise CliError(
            "invalid_state",
            "No finalize.json — plan has not been finalized yet.",
        )
    finalize_data = read_json(finalize_path)
    user_actions: list[dict[str, Any]] = finalize_data.get("user_actions", [])
    if not isinstance(user_actions, list):
        user_actions = []

    valid_action_ids = [
        a.get("id")
        for a in user_actions
        if isinstance(a, dict) and isinstance(a.get("id"), str)
    ]
    if action_id not in valid_action_ids:
        raise CliError(
            "invalid_args",
            f"Unknown user action {action_id!r}. "
            f"Valid action IDs in finalize.json: "
            f"{', '.join(valid_action_ids) or '(none)'}.",
        )

    # --- validate --tasks against known task IDs AND effective action scope ---
    tasks_arg: str | None = getattr(args, "tasks", None) or getattr(
        args, "applies_to_task_ids", None
    )
    task_list: list[str] | None = None
    selected_scope = build_prerequisite_scopes(finalize_data).get(action_id)
    if tasks_arg is not None:
        raw_task_parts = tasks_arg.split(",") if tasks_arg else []
        if any(not part.strip() for part in raw_task_parts):
            raise CliError(
                "invalid_args",
                "--tasks / --applies-to-task-ids contains empty or malformed task IDs",
            )
        task_list = [t.strip() for t in raw_task_parts]
    if task_list:
        all_tasks: list[dict[str, Any]] = finalize_data.get("tasks", [])
        if not isinstance(all_tasks, list):
            all_tasks = []
        known_task_ids = [
            t.get("id")
            for t in all_tasks
            if isinstance(t, dict) and isinstance(t.get("id"), str)
        ]
        unknown_task_ids = [tid for tid in task_list if tid not in known_task_ids]
        if unknown_task_ids:
            raise CliError(
                "invalid_args",
                "Unknown task ID(s) in --tasks: "
                + ", ".join(repr(tid) for tid in unknown_task_ids),
                extra={
                    "requested_task_ids": task_list,
                    "unknown_task_ids": unknown_task_ids,
                    "known_task_ids": known_task_ids,
                },
            )

        allowed_task_ids = (
            list(selected_scope.effective_task_ids)
            if selected_scope is not None
            else []
        )
        invalid_scope_task_ids = [
            tid for tid in task_list if tid not in set(allowed_task_ids)
        ]
        if invalid_scope_task_ids:
            extra = {
                "action_id": action_id,
                "requested_task_ids": task_list,
                "invalid_task_ids": invalid_scope_task_ids,
                "allowed_task_ids": allowed_task_ids,
            }
            if selected_scope is not None:
                extra["effective_scope"] = selected_scope.to_dict()
            raise CliError(
                "invalid_args",
                f"Task(s) {', '.join(invalid_scope_task_ids)} are not in "
                f"action {action_id!r}'s effective task scope.",
                extra=extra,
            )

    # --- determine created_by (MEGAPLAN_ACTOR_ID → USER → operator) ----------
    created_by: str = (
        os.environ.get("MEGAPLAN_ACTOR_ID") or os.environ.get("USER") or "operator"
    )

    # --- build and persist resolution event ----------------------------------
    event = build_resolution_event(
        action_id=action_id,
        resolution=resolution,
        fallback_mode=getattr(args, "fallback_mode", None) or None,
        tasks=task_list,
        instructions=getattr(args, "instructions", None) or None,
        reason=getattr(args, "reason", None) or None,
        phase=getattr(args, "phase", None) or None,
        evidence=_parse_user_action_evidence(getattr(args, "evidence", None)),
        debt_note=getattr(args, "debt_note", None) or None,
        created_by=created_by,
    )
    _append_to_meta(state, "user_action_resolutions", event)
    from megaplan.resolutions import upsert_user_action_resolution

    upsert_user_action_resolution(
        plan_dir,
        action_id,
        resolution,
        reason=getattr(args, "reason", None) or "",
        fallback_mode=getattr(args, "fallback_mode", None) or "",
        applies_to_task_ids=task_list or [],
        instructions=getattr(args, "instructions", None) or "",
        created_by=getattr(args, "created_by", None) or created_by,
    )
    save_state_merge_meta(plan_dir, state)

    return {
        "success": True,
        "step": "user-action-resolve",
        "action": "resolve",
        "summary": (
            f"Resolution {resolution!r} recorded for action "
            f"{action_id!r} by {created_by}."
        ),
        "action_id": action_id,
        "resolution": resolution,
        "created_by": created_by,
        "timestamp": event["timestamp"],
        "phase": event.get("phase"),
        "evidence": event.get("evidence", []),
        "debt_note": event.get("debt_note"),
    }


def handle_quality_gate(root: Path, args: argparse.Namespace) -> StepResponse:
    """Handle ``megaplan quality-gate resolve`` — record a quality resolution."""
    from megaplan._core.state import save_state_merge_meta
    from megaplan.blocker_recovery import (
        command_blocker_details,
        evaluate_blocker_recovery,
    )
    from megaplan.handlers.shared import _append_to_meta
    from megaplan.orchestration.phase_result import read_phase_result
    from megaplan.quality_resolutions import (
        VALID_RESOLUTIONS,
        build_quality_resolution_event,
    )

    sub_action = getattr(args, "quality_gate_action", None)
    if sub_action != "resolve":
        raise CliError(
            "invalid_args",
            f"Unknown quality-gate sub-command: {sub_action!r}. Expected 'resolve'.",
        )

    plan_dir, state = load_plan(root, args.plan)
    blocker_id: str = args.blocker_id
    resolution: str = args.resolution

    if resolution not in VALID_RESOLUTIONS:
        raise CliError(
            "invalid_args",
            f"Invalid resolution {resolution!r}. "
            f"Must be one of: {', '.join(VALID_RESOLUTIONS)}.",
        )

    finalize_data = (
        read_json(plan_dir / "finalize.json")
        if (plan_dir / "finalize.json").exists()
        else {}
    )
    phase_result = read_phase_result(plan_dir)
    deviations = phase_result.deviations if phase_result is not None else ()
    evaluation = evaluate_blocker_recovery(
        finalize_data,
        state,
        deviations=deviations,
    )
    known_blockers = evaluation.by_id()
    if known_blockers and blocker_id not in known_blockers:
        raise CliError(
            "invalid_args",
            f"Unknown quality blocker_id {blocker_id!r}.",
            extra={
                "requested_blocker_id": blocker_id,
                "known_blocker_ids": sorted(known_blockers),
                "blockers": command_blocker_details(evaluation),
            },
        )
    if not known_blockers and not blocker_id.startswith("quality:"):
        raise CliError(
            "invalid_args",
            "quality-gate resolve requires a quality blocker ID",
            extra={"requested_blocker_id": blocker_id},
        )

    created_by: str = (
        os.environ.get("MEGAPLAN_ACTOR_ID") or os.environ.get("USER") or "operator"
    )
    event = build_quality_resolution_event(
        blocker_id=blocker_id,
        resolution=resolution,
        phase=getattr(args, "phase", None) or None,
        evidence=_parse_user_action_evidence(getattr(args, "evidence", None)),
        debt_note=getattr(args, "debt_note", None) or None,
        fallback_mode=getattr(args, "fallback_mode", None) or None,
        created_by=created_by,
    )
    _append_to_meta(state, "quality_gate_resolutions", event)
    save_state_merge_meta(plan_dir, state)

    return {
        "success": True,
        "step": "quality-gate-resolve",
        "summary": (
            f"Resolution {resolution!r} recorded for quality blocker "
            f"{blocker_id!r} by {created_by}."
        ),
        "blocker_id": blocker_id,
        "resolution": resolution,
        "created_by": created_by,
        "timestamp": event["timestamp"],
        "phase": event.get("phase"),
        "evidence": event.get("evidence", []),
        "debt_note": event.get("debt_note"),
        "fallback_mode": event.get("fallback_mode"),
        "blocker": (
            known_blockers[blocker_id].to_dict()
            if blocker_id in known_blockers
            else None
        ),
    }


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
    "feedback": handle_feedback,
    "list": handle_list,
    "loop-init": handle_loop_init,
    "loop-run": handle_loop_run,
    "loop-status": handle_loop_status,
    "loop-pause": handle_loop_pause,
    "debt": handle_debt,
    "user-action": handle_user_action,
    "ticket": handle_ticket,
    "epic": handle_epic,
    "migrate-local-plans": handle_migrate_local_plans,
    "step": handle_step,
    "override": handle_override,
    "verify-human": handle_verify_human,
    "audit-verifiability": handle_audit_verifiability,
    "tiebreaker-run": handle_tiebreaker_run,
    "user-action": handle_user_action,
    "quality-gate": handle_quality_gate,
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


def _setup_init_worktree(args: argparse.Namespace) -> None:
    """When ``--in-worktree`` is set on ``megaplan init``, create the worktree
    and rewrite ``args`` so the rest of the init flow lands inside it.

    Safety contract: this function MUST be strictly additive. It may only
    create one new branch + one new worktree directory. It never modifies the
    invoking repo, its branches (other than the one it creates), its remotes,
    its stash, or any other worktree. If anything looks ambiguous, it raises.
    """
    name = getattr(args, "in_worktree", None)
    clean_worktree = bool(getattr(args, "clean_worktree", False))
    carry_dirty_flag = bool(getattr(args, "carry_dirty", False))
    if clean_worktree and carry_dirty_flag:
        raise CliError(
            "invalid_args",
            "--clean-worktree and --carry-dirty are mutually exclusive",
        )
    if name is None:
        if getattr(args, "worktree_from", None):
            raise CliError(
                "invalid_args",
                "--worktree-from is only valid alongside --in-worktree",
            )
        if clean_worktree or carry_dirty_flag:
            raise CliError(
                "invalid_args",
                "--clean-worktree / --carry-dirty are only valid with --in-worktree",
            )
        return

    from megaplan.bakeoff.worktree import (
        branch_exists,
        carry_dirty_state_atomic,
        create_named_worktree,
        ensure_no_inprogress_op,
        has_dirty_state,
        resolve_ref,
        validate_worktree_name,
        worktree_registered,
    )

    if getattr(args, "project_dir", None):
        raise CliError(
            "invalid_args",
            "pass either --project-dir or --in-worktree, not both",
        )

    validate_worktree_name(name)

    # Locate the invoking repo. We deliberately do NOT use --project-dir here
    # (we just rejected it above); we use cwd-walk-up so the user can run
    # `megaplan init --in-worktree foo` from anywhere inside the repo.
    invoking_repo = _find_git_root(Path.cwd().resolve())
    if invoking_repo is None:
        raise CliError(
            "not_a_git_repo",
            "--in-worktree requires running from inside a git repository",
        )

    ensure_no_inprogress_op(invoking_repo)

    target = (Path.home() / "Documents" / ".megaplan-worktrees" / name).resolve()
    if target.exists():
        raise CliError(
            "worktree_target_exists",
            f"refusing to create worktree: target path already exists: {target}",
        )
    if worktree_registered(invoking_repo, target):
        raise CliError(
            "worktree_already_registered",
            f"git already has a worktree registered at {target} "
            "(run `git worktree prune` manually if it's stale)",
        )
    if branch_exists(invoking_repo, name):
        raise CliError(
            "worktree_branch_exists",
            f"branch {name!r} already exists locally or on a remote; "
            "pick a different --in-worktree name",
        )

    base_ref = getattr(args, "worktree_from", None) or "HEAD"
    base_sha = resolve_ref(invoking_repo, base_ref)

    create_named_worktree(invoking_repo, target, base_sha, name)

    # Carry uncommitted state from the source repo into the new worktree
    # unless the caller explicitly opted out via --clean-worktree. The source
    # repo is read-only throughout: we only capture a diff and copy untracked
    # files; we never run stash/checkout/reset/clean on it.
    tracked_carried = 0
    untracked_carried = 0
    if not clean_worktree:
        should_carry = carry_dirty_flag or has_dirty_state(invoking_repo)
        if should_carry:
            tracked_carried, untracked_carried = carry_dirty_state_atomic(
                invoking_repo, target
            )

    # Rewrite args so the rest of the init flow lands inside the worktree.
    args.project_dir = str(target)
    # Stash audit data on args so handle_init can persist it into plan state.
    args._worktree_meta = {
        "name": name,
        "path": str(target),
        "branch": name,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "source_repo": str(invoking_repo),
        "carried_tracked": tracked_carried,
        "carried_untracked": untracked_carried,
    }
    # Update work-dir override so subprocess workers run in the worktree.
    from megaplan.workers import set_work_dir_override

    set_work_dir_override(target)

    print(
        f"Created worktree at {target} on branch {name} "
        f"(base {base_sha[:12]}); initializing plan inside it...",
        file=sys.stderr,
    )
    if tracked_carried or untracked_carried:
        print(
            f"warning: carried {tracked_carried} uncommitted file change(s) "
            f"and {untracked_carried} untracked file(s) from {invoking_repo} "
            f"into {target}. Source worktree is unchanged.\n"
            f"  * To start the worktree from a clean base instead, commit your "
            f"changes first or re-run with --clean-worktree.\n"
            f"  * Files were carried as unstaged in the new worktree (staging "
            f"information is not preserved). Run `git diff` or `git status` "
            f"inside the worktree to inspect.",
            file=sys.stderr,
        )


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


def _handle_list_pipelines(args: argparse.Namespace) -> StepResponse:
    """Handle ``megaplan list pipelines`` — list YAML + registered pipelines."""
    from megaplan._pipeline.loader import list_pipeline_names
    from megaplan._pipeline.registry import registered_pipelines

    verbose = getattr(args, "verbose", False)

    yaml_names = list(list_pipeline_names())
    reg_names = list(registered_pipelines())

    all_names = sorted(set(yaml_names) | set(reg_names))

    items: list[dict[str, Any]] = []
    for name in all_names:
        kind = "yaml" if name in yaml_names else "python"
        if name in yaml_names and name in reg_names:
            kind = "both"
        entry: dict[str, Any] = {"name": name, "kind": kind}
        if verbose and name in yaml_names:
            from megaplan._pipeline.loader import describe_pipeline

            desc = describe_pipeline(name)
            # Extract first line of description
            first_line = desc.split("\n")[0] if desc else ""
            entry["description"] = first_line
            # Get profile info
            from megaplan._pipeline.loader import load_pipeline

            lp = load_pipeline(name)
            entry["version"] = lp.spec.version
            entry["default_profile"] = lp.spec.default_profile
            if lp.spec.supported_modes:
                entry["modes"] = lp.spec.supported_modes
        items.append(entry)

    return {
        "success": True,
        "step": "list",
        "summary": f"Found {len(items)} pipeline(s): {', '.join(n['name'] for n in items)}",
        "pipelines": items,
    }


def handle_describe(args: argparse.Namespace) -> StepResponse:
    """Handle ``megaplan describe <pipeline>`` command."""
    from megaplan._pipeline.loader import describe_pipeline

    try:
        desc = describe_pipeline(args.pipeline_name)
    except KeyError as exc:
        return {
            "success": False,
            "step": "describe",
            "error": str(exc),
        }

    # For CLI rendering, print directly (descriptions are long-form text)
    print(desc)
    return {
        "success": True,
        "step": "describe",
        "pipeline": args.pipeline_name,
    }


def _auto_sync_installed_skills() -> None:
    try:
        for target in _GLOBAL_TARGETS:
            agent_dir = Path.home() / target["detect"]
            if not agent_dir.is_dir():
                continue
            mode = target.get("install")
            if mode == "symlink":
                _install_owned_symlink(
                    Path.home() / target["path"],
                    _resolve_bundle_path(target["data"]),
                    force=False,
                )
            elif mode == "dir_symlink":
                _install_owned_dir_symlink(
                    Path.home() / target["path"],
                    _resolve_bundle_path(target["data"]),
                    force=False,
                )
            else:
                _install_owned_file(
                    Path.home() / target["path"],
                    bundled_global_file(target["data"]),
                    force=False,
                )
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
    if argv and argv[0] == "resident":
        from megaplan.resident.cli import (
            _register_resident_subcommands,
            run_resident_cli,
        )

        resident_parser = argparse.ArgumentParser(prog="megaplan resident")
        _register_resident_subcommands(resident_parser)
        resident_args = resident_parser.parse_args(argv[1:])
        root = _find_megaplan_root(Path.cwd())
        ensure_runtime_layout(root)
        try:
            return render_response(run_resident_cli(root, resident_args))
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
            result = handle_setup(args)
            if getattr(args, "regen_composed", False) and not result.get(
                "success", True
            ):
                print(json_dump(result))
                return 1
            return render_response(result)
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

    # Handle --in-worktree on `init` *before* resolving project root. This
    # creates the worktree and rewrites args.project_dir to point at it, so
    # everything downstream behaves as if the user had passed --project-dir
    # <worktree> manually.
    if args.command == "init":
        try:
            _setup_init_worktree(args)
        except CliError as error:
            return error_response(error)
        if not getattr(args, "project_dir", None):
            return error_response(
                CliError(
                    "invalid_args",
                    "megaplan init requires --project-dir or --in-worktree",
                )
            )

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

    if args.command == "run":
        from megaplan._pipeline.run_cli import cli_run

        try:
            return cli_run(args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "describe":
        try:
            response = handle_describe(args)
            return render_response(response)
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
        # Ticket handler has a different signature (no root, returns int)
        if args.command == "ticket":
            return handler(args)
        from megaplan.orchestration.progress import ProgressEmitter

        args.progress_emitter = ProgressEmitter.from_env()
        if args.command == "override" and remaining:
            if not args.note:
                args.note = " ".join(remaining)
            remaining = []
        if remaining:
            parser.error(f"unrecognized arguments: {' '.join(remaining)}")
        if (
            args.command == "override"
            and args.override_action == "add-note"
            and not args.note
        ):
            raise CliError("invalid_args", "override add-note requires a note")
        if (
            args.command == "override"
            and args.override_action == "recover-blocked"
            and not args.reason
        ):
            raise CliError("invalid_args", "override recover-blocked requires --reason")
        if (
            args.command == "override"
            and args.override_action == "set-robustness"
            and not args.robustness
        ):
            raise CliError(
                "invalid_args",
                f"override set-robustness requires --robustness {'|'.join(ROBUSTNESS_ACCEPTED)}",
            )
        if (
            args.command == "override"
            and args.override_action == "set-profile"
            and not args.profile
        ):
            raise CliError(
                "invalid_args", "override set-profile requires --profile NAME"
            )
        if (
            args.command == "user-action"
            and getattr(args, "user_action_action", None) == "resolve"
        ):
            if not getattr(args, "action_id", None):
                raise CliError(
                    "invalid_args", "user-action resolve requires --action-id"
                )
            if not getattr(args, "resolution", None):
                raise CliError(
                    "invalid_args", "user-action resolve requires --resolution"
                )
        if (
            args.command == "quality-gate"
            and getattr(args, "quality_gate_action", None) == "resolve"
        ):
            if not getattr(args, "blocker_id", None):
                raise CliError(
                    "invalid_args", "quality-gate resolve requires --blocker-id"
                )
            if not getattr(args, "resolution", None):
                raise CliError(
                    "invalid_args", "quality-gate resolve requires --resolution"
                )
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
            args.progress_emitter.phase_start(
                args.command, plan=getattr(args, "plan", None)
            )
        response = handler(root, args)
        _emit_response_progress(args.command, response, args.progress_emitter)
        return render_response(response)
    except CliError as error:
        if "args" in locals() and hasattr(args, "progress_emitter"):
            _emit_error_progress(
                getattr(args, "command", ""), error, args.progress_emitter
            )
        return error_response(error, root=root)


if __name__ == "__main__":
    sys.exit(main())
