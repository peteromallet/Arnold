from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.anchors import anchor_summary
from arnold_pipelines.megaplan.types import StepResponse
from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED
from arnold_pipelines.megaplan.user_actions import FALLBACK, OMIT
from arnold_pipelines.megaplan._core import (
    active_phase_name,
    build_phase_observability,
    build_next_step_runtime,
    get_effective,
    humanize_seconds,
    infer_next_steps,
    is_prose_mode,
    list_batch_artifacts,
    plan_lock_is_held,
    read_json,
)
from arnold_pipelines.megaplan.blocker_recovery import (
    PREREQUISITE,
    QUALITY,
    build_prerequisite_scopes,
    command_blocker_details,
    evaluate_blocker_recovery,
)
from arnold_pipelines.megaplan.orchestration.phase_result import (
    BlockedTask,
    Deviation,
    ExitKind,
    read_phase_result,
)
from arnold_pipelines.megaplan.orchestration.plan_structure import PLAN_STRUCTURE_REQUIRED_STEP_ISSUE
from arnold_pipelines.megaplan.control_interface import read_valid_targets
from arnold.runtime.outcome import RunOutcome

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
    from arnold_pipelines.megaplan.resolution_contract import (
        FALLBACK_STATES,
        HARD_BLOCK_STATES,
        resolution_applies_to_task,
        resolution_recommended_action,
    )
    from arnold_pipelines.megaplan.resolutions import load_user_action_resolutions

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
            applies = resolution_applies_to_task(resolution, tid, source="disk")

            if isinstance(resolution, dict):
                state = resolution.get("state", "")
                rec_action = resolution_recommended_action(resolution, source="disk")

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
    import arnold_pipelines.megaplan.cli as cli_mod

    batch_status_overlay: dict[str, str] = {}
    for batch_path in cli_mod.list_batch_artifacts(plan_dir):
        try:
            batch_data = cli_mod.read_json(batch_path)
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
    if phase_result.exit_kind == ExitKind.success.value:
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


def _projected_outcome(state: dict[str, Any]) -> RunOutcome | None:
    current_state = state.get("current_state")
    if current_state == "done":
        return RunOutcome.SUCCEEDED
    if current_state in {"failed", "aborted"}:
        return RunOutcome.FAILED
    if current_state == "blocked":
        return RunOutcome.BLOCKED
    if current_state in {"awaiting_human", "clarifying"}:
        return RunOutcome.AWAITING_HUMAN
    return None


def _projected_target_ids(
    state: dict[str, Any],
    *,
    recovery: bool,
) -> list[str]:
    targets = read_valid_targets(
        state,
        plugin_id="megaplan",
        recovery=recovery,
    )
    return [
        target.id
        for target in targets
        if isinstance(target.id, str)
        and target.id
        and target.metadata.get("actionable", True)
    ]


def _recovery_projection_state(
    state: dict[str, Any],
    *,
    plan_dir: Path,
) -> dict[str, Any]:
    resume_cursor = state.get("resume_cursor")
    cursor_phase = (
        resume_cursor.get("phase")
        if isinstance(resume_cursor, dict)
        else None
    )
    if cursor_phase not in {"recover-blocked", "resume-clarify", "status", "step"}:
        return state
    phase_result = read_phase_result(plan_dir)
    if phase_result is None or not isinstance(phase_result.phase, str) or not phase_result.phase:
        return state
    projected = dict(state)
    projected["phase_result"] = {"phase": phase_result.phase}
    return projected


def _projected_valid_next(state: dict[str, Any]) -> list[str]:
    history = state.get("history")
    last = history[-1] if isinstance(history, list) and history else None
    if (
        isinstance(last, dict)
        and last.get("result") == "error"
        and last.get("step") in {"plan", "revise"}
        and PLAN_STRUCTURE_REQUIRED_STEP_ISSUE in str(last.get("message") or "")
    ):
        return [str(last["step"])]
    use_recovery = _projected_outcome(state) in {
        RunOutcome.BLOCKED,
        RunOutcome.AWAITING_HUMAN,
        RunOutcome.FAILED,
    }
    projected = _projected_target_ids(state, recovery=use_recovery)
    if projected or use_recovery:
        return projected
    return infer_next_steps(state)


def _external_error_resume_command(state: dict[str, Any]) -> str | None:
    if _projected_outcome(state) != RunOutcome.BLOCKED:
        return None
    latest_failure = state.get("latest_failure")
    resume_cursor = state.get("resume_cursor")
    if not isinstance(latest_failure, dict):
        return None
    if latest_failure.get("kind") != "external_error":
        return None
    if not isinstance(resume_cursor, dict) or not isinstance(
        resume_cursor.get("phase"), str
    ):
        return None
    plan_name = state.get("name")
    if not isinstance(plan_name, str) or not plan_name:
        return None
    return f"resume --plan {plan_name}"


def _build_blocker_recovery_context(
    plan_dir: Path,
    finalize_data: dict[str, Any],
    state: dict[str, Any],
    *,
    active_step: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (
        isinstance(active_step, dict)
        and active_step.get("recommended_action") == "wait"
    ):
        # While a live step is still running, stale phase_result.json data and
        # partial execution_batch_*.json overlays are observational context, not
        # actionable blockers.
        return {
            "can_continue": True,
            "has_terminal_blockers": False,
            "requires_rerun": False,
            "blockers": [],
            "prerequisite_blockers": [],
            "quality_blockers": [],
            "suggested_commands": [],
        }
    phase_blocked_tasks, deviations = _phase_result_recovery_inputs(plan_dir)
    baseline_deviation_by_task: dict[str, Deviation] = {}
    if phase_blocked_tasks:
        from arnold_pipelines.megaplan.execute.batch import baseline_unavailable_checkpoint_deviations

        baseline_deviations = baseline_unavailable_checkpoint_deviations(
            finalize_data,
            [blocked.task_id for blocked in phase_blocked_tasks],
        )
        baseline_deviation_by_task = {
            deviation.task_id: deviation
            for deviation in baseline_deviations
            if deviation.task_id is not None
        }
        if baseline_deviations:
            deviations = deviations + baseline_deviations
            phase_blocked_tasks = tuple(
                blocked
                for blocked in phase_blocked_tasks
                if blocked.task_id not in baseline_deviation_by_task
            )
    prereq_blocked_tasks = phase_blocked_tasks + _synthetic_prerequisite_blocked_tasks(
        finalize_data,
        phase_blocked_tasks,
    )
    evaluation = evaluate_blocker_recovery(
        finalize_data,
        state,
        plan_dir=plan_dir,
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
    if _projected_outcome(state) == RunOutcome.BLOCKED and blockers:
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
    *,
    active_step: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build legacy-compatible blocked task status from shared recovery data."""
    blocker_recovery = _build_blocker_recovery_context(
        plan_dir,
        finalize_data,
        state,
        active_step=active_step,
    )
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
    import arnold_pipelines.megaplan.cli as cli_mod

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
    finalize_data = cli_mod.read_json(finalize_path)
    global_batches = cli_mod.compute_global_batches(finalize_data)
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
    active_step = _build_active_step(state.get("active_step"), plan_dir=plan_dir)
    blocked_tasks = _build_blocked_tasks_context(
        plan_dir,
        finalize_data,
        state,
        active_step=active_step,
    )
    blocker_recovery = _build_blocker_recovery_context(
        plan_dir,
        finalize_data,
        state,
        active_step=active_step,
    )
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
    step = active_phase_name(details)
    if not step:
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
    projection_state = _recovery_projection_state(state, plan_dir=plan_dir)
    next_steps = _projected_valid_next(projection_state) or infer_next_steps(projection_state)
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
    anchors = anchor_summary(state, plan_dir)
    summary = (
        f"Plan '{state['name']}' is currently in state '{state['current_state']}'."
    )
    if is_prose_mode(state):
        summary += f" Mode: {plan_mode}. Output: {plan_output_path}."
    if active_step:
        summary = (
            summary
            + f" Active step: {active_phase_name(active_step)} via {active_step.get('agent')}."
        )
    elif lock_file_present and not lock_held:
        summary = (
            summary
            + " No active step. The `.plan.lock` file may remain on disk even when no process holds the lock."
        )
    routing_degradations = state.get("config", {}).get("routing_degradations")
    routing_degradation_summary = None
    if isinstance(routing_degradations, list) and routing_degradations:
        routing_degradation_summary = _format_routing_degradation_summary(
            routing_degradations
        )
        summary = summary + f" WARNING routing degraded: {routing_degradation_summary}."
    if anchors.get("present"):
        anchor_bits = []
        for anchor_type in anchors.get("types", []):
            detail = anchors.get(anchor_type, {})
            scopes = ",".join(detail.get("scopes", [])) if isinstance(detail, dict) else ""
            anchor_bits.append(f"{anchor_type}({scopes})")
        summary = summary + f" Anchors: {', '.join(anchor_bits)}."
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
        "anchors": anchors,
        "notes_count": len(notes) if isinstance(notes, list) else 0,
        "notes": notes if isinstance(notes, list) else [],
        "session_summaries": [
            {"key": key, **value}
            for key, value in sorted(state.get("sessions", {}).items())
            if isinstance(value, dict)
        ],
    }
    if routing_degradation_summary is not None:
        response["routing_degradations"] = routing_degradations
        response["routing_degradation_summary"] = routing_degradation_summary
    # Add blocked_tasks resolution context when finalize.json exists
    finalize_path = plan_dir / "finalize.json"
    if finalize_path.exists():
        finalize_data = read_json(finalize_path)
        blocked_tasks = _build_blocked_tasks_context(
            plan_dir,
            finalize_data,
            state,
            active_step=active_step,
        )
        blocker_recovery = _build_blocker_recovery_context(
            plan_dir,
            finalize_data,
            state,
            active_step=active_step,
        )
        if blocked_tasks:
            response["blocked_tasks"] = blocked_tasks
        if blocker_recovery["blockers"]:
            response["blocker_recovery"] = blocker_recovery
            response["quality_blockers"] = blocker_recovery["quality_blockers"]
            response["suggested_recovery_commands"] = blocker_recovery[
                "suggested_commands"
            ]
            if (
                state.get("current_state") in {STATE_BLOCKED, "finalized"}
                and blocker_recovery.get("has_terminal_blockers") is True
            ):
                # Keep status pinned until an operator/repairer chooses a real
                # recovery action. Advertising recover-blocked or execute here
                # only causes auto loops to spend budget on a command that must
                # return to the same terminal blocker.
                response["next_step"] = None
                response["valid_next"] = []
                plan_name = state.get("name")
                if isinstance(plan_name, str) and plan_name:
                    response["suggested_recovery_commands"] = _unique_strings(
                        [
                            *response.get("suggested_recovery_commands", []),
                            f"override replan --plan {plan_name} --reason <reason>",
                        ]
                    )
    external_resume_command = _external_error_resume_command(state)
    if external_resume_command is not None:
        response["external_error_recovery"] = {
            "recommended_action": "resume",
            "resume_cursor": state.get("resume_cursor"),
            "latest_failure": state.get("latest_failure"),
            "suggested_commands": [external_resume_command],
        }
        response["suggested_recovery_commands"] = _unique_strings(
            [
                *response.get("suggested_recovery_commands", []),
                external_resume_command,
            ]
        )
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


def _format_routing_degradation_summary(degradations: list[Any]) -> str:
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for item in degradations:
        if not isinstance(item, dict):
            continue
        phase = str(item.get("phase") or "?")
        to_spec = str(item.get("to") or "?")
        reason = str(item.get("reason") or "unknown reason")
        tier = item.get("tier")
        tier_label = str(tier) if tier is not None else ""
        grouped.setdefault((phase, to_spec, reason), []).append(tier_label)

    parts: list[str] = []
    for (phase, to_spec, reason), tiers in grouped.items():
        tier_values = [tier for tier in tiers if tier]
        if tier_values:
            parts.append(f"{phase} tier {','.join(tier_values)} -> {to_spec} ({reason})")
        else:
            parts.append(f"{phase} -> {to_spec} ({reason})")
    return "; ".join(parts) or "unknown"


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
    import arnold_pipelines.megaplan.cli as cli_mod

    if getattr(args, "pending_human", False):
        items = []
        for pd in cli_mod.active_plan_dirs(root):
            # cache-tolerant: status-view read.
            st = cli_mod.read_json(pd / "state.json")
            if _projected_outcome(st) == RunOutcome.AWAITING_HUMAN:
                items.append({"name": st["name"], "state": st["current_state"]})
        return {
            "success": True,
            "step": "status",
            "summary": f"Found {len(items)} plan(s) awaiting human verification.",
            "plans": items,
        }
    plan_dir, state = cli_mod.load_plan(root, args.plan)
    return _build_status_payload(plan_dir, state)


def handle_audit(root: Path, args: argparse.Namespace) -> StepResponse:
    import arnold_pipelines.megaplan.cli as cli_mod

    if getattr(args, "audit_action", None) == "query":
        from arnold_pipelines.megaplan.receipts.query import handle_audit_query

        return handle_audit_query(root, args)
    if getattr(args, "audit_action", None) == "report":
        from arnold_pipelines.megaplan.receipts.report import handle_audit_report

        return handle_audit_report(root, args)
    plan_dir, state = cli_mod.load_plan(root, args.plan)
    anchors = anchor_summary(state, plan_dir)
    return {
        "success": True,
        "step": "audit",
        "plan": state["name"],
        "plan_dir": str(plan_dir),
        "anchors": anchors,
        "state": state,
    }


def handle_progress(root: Path, args: argparse.Namespace) -> StepResponse:
    import arnold_pipelines.megaplan.cli as cli_mod

    plan_dir, state = cli_mod.load_plan(root, args.plan)
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
