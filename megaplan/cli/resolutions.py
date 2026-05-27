from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from megaplan.types import CliError, StepResponse
from megaplan._core import load_plan, read_json


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


def handle_user_action(root: Path, args: argparse.Namespace) -> StepResponse:
    import megaplan.cli as cli_mod

    from megaplan._core.state import save_state_merge_meta
    from megaplan.blocker_recovery import build_prerequisite_scopes
    from megaplan.handlers.shared import _append_to_meta
    from megaplan.user_actions import VALID_RESOLUTIONS, build_resolution_event

    sub_action = getattr(args, "user_action_action", None)
    if sub_action != "resolve":
        raise CliError(
            "invalid_args",
            f"Unknown user-action sub-command: {sub_action!r}. Expected 'resolve'.",
        )

    plan_dir, state = cli_mod.load_plan(root, args.plan)
    action_id: str = getattr(args, "action_id", None) or getattr(args, "action", None)
    resolution: str = getattr(args, "resolution", None) or getattr(args, "state", None)
    if resolution not in VALID_RESOLUTIONS:
        raise CliError(
            "invalid_args",
            f"Unsupported resolution state {resolution!r}. "
            f"Must be one of: {', '.join(VALID_RESOLUTIONS)}.",
        )

    finalize_path = plan_dir / "finalize.json"
    if not finalize_path.exists():
        raise CliError("invalid_state", "No finalize.json — plan has not been finalized yet.")
    finalize_data = cli_mod.read_json(finalize_path)
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
            f"Valid action IDs in finalize.json: {', '.join(valid_action_ids) or '(none)'}.",
        )

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
                f"Task(s) {', '.join(invalid_scope_task_ids)} are not in action {action_id!r}'s effective task scope.",
                extra=extra,
            )

    created_by: str = (
        os.environ.get("MEGAPLAN_ACTOR_ID") or os.environ.get("USER") or "operator"
    )
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
        "summary": f"Resolution {resolution!r} recorded for action {action_id!r} by {created_by}.",
        "action_id": action_id,
        "resolution": resolution,
        "created_by": created_by,
        "timestamp": event["timestamp"],
        "phase": event.get("phase"),
        "evidence": event.get("evidence", []),
        "debt_note": event.get("debt_note"),
    }


def handle_quality_gate(root: Path, args: argparse.Namespace) -> StepResponse:
    import megaplan.cli as cli_mod

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

    plan_dir, state = cli_mod.load_plan(root, args.plan)
    blocker_id: str = args.blocker_id
    resolution: str = args.resolution
    if resolution not in VALID_RESOLUTIONS:
        raise CliError(
            "invalid_args",
            f"Invalid resolution {resolution!r}. "
            f"Must be one of: {', '.join(VALID_RESOLUTIONS)}.",
        )

    finalize_data = (
        cli_mod.read_json(plan_dir / "finalize.json")
        if (plan_dir / "finalize.json").exists()
        else {}
    )
    phase_result = read_phase_result(plan_dir)
    deviations = phase_result.deviations if phase_result is not None else ()
    evaluation = evaluate_blocker_recovery(finalize_data, state, deviations=deviations)
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
        "summary": f"Resolution {resolution!r} recorded for quality blocker {blocker_id!r} by {created_by}.",
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
