from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from megaplan.types import (
    ROBUSTNESS_LEVELS,
    CliError,
    PlanState,
    STATE_ABORTED,
    STATE_CRITIQUED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FINALIZED,
    STATE_GATED,
    STATE_PLANNED,
    StepResponse,
)
from megaplan._core import (
    add_or_increment_debt,
    atomic_write_json,
    extract_subsystem_tag,
    find_command,
    infer_next_steps,
    latest_plan_path,
    load_debt_registry,
    load_flag_registry,
    load_plan,
    now_utc,
    save_debt_registry,
    save_state,
    unresolved_significant_flags,
    workflow_next,
)
from megaplan.evaluation import build_gate_artifact, build_gate_signals, run_gate_checks

from .shared import _append_to_meta, _attach_next_step_runtime

def _override_add_note(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    note = args.note
    _append_to_meta(state, "notes", {"timestamp": now_utc(), "note": note})
    _append_to_meta(state, "overrides", {"action": "add-note", "timestamp": now_utc(), "note": note})
    save_state(plan_dir, state)
    next_steps = infer_next_steps(state)
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": "Attached note to the plan.",
        "next_step": next_steps[0] if next_steps else None,
        "state": state["current_state"],
    }
    _attach_next_step_runtime(response)
    return response

def _override_abort(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    state["current_state"] = STATE_ABORTED
    _append_to_meta(state, "overrides", {"action": "abort", "timestamp": now_utc(), "reason": args.reason})
    save_state(plan_dir, state)
    return {
        "success": True,
        "step": "override",
        "summary": "Plan aborted.",
        "next_step": None,
        "state": STATE_ABORTED,
    }

def _override_force_proceed(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    if state["current_state"] == STATE_EXECUTED:
        # Force-proceed from review loop: mark as done despite review issues
        _append_to_meta(state, "overrides", {"action": "force-proceed", "timestamp": now_utc(), "reason": args.reason})
        state["current_state"] = STATE_DONE
        save_state(plan_dir, state)
        return {
            "success": True,
            "step": "override",
            "summary": "Force-proceeded past review into done state.",
            "next_step": None,
            "state": STATE_DONE,
        }
    if state["current_state"] != STATE_CRITIQUED:
        raise CliError(
            "invalid_transition",
            "force-proceed is only supported from critiqued or executed state",
            valid_next=infer_next_steps(state),
        )
    gate_checks = run_gate_checks(plan_dir, state, command_lookup=find_command)
    if not gate_checks["preflight_results"]["project_dir_exists"] or not gate_checks["preflight_results"]["success_criteria_present"]:
        raise CliError("unsafe_override", "force-proceed cannot bypass missing project directory or success criteria")
    signals = build_gate_signals(plan_dir, state, root=root)
    merged_signals = {
        "robustness": signals["robustness"],
        "signals": signals["signals"],
        "warnings": signals.get("warnings", []),
        "criteria_check": gate_checks["criteria_check"],
        "preflight_results": gate_checks["preflight_results"],
        "unresolved_flags": gate_checks["unresolved_flags"],
    }
    gate = build_gate_artifact(
        merged_signals,
        {
            "recommendation": "PROCEED",
            "rationale": args.reason or "User forced execution past the gate.",
            "signals_assessment": "Forced proceed override applied by the orchestrator.",
            "warnings": signals.get("warnings", []),
        },
        override_forced=True,
        orchestrator_guidance="Force-proceed override applied. Proceed to finalize.",
    )
    atomic_write_json(plan_dir / "gate.json", gate)
    flag_registry = load_flag_registry(plan_dir)
    unresolved_flags = unresolved_significant_flags(flag_registry)
    debt_registry = load_debt_registry(root)
    for flag in unresolved_flags:
        add_or_increment_debt(
            debt_registry,
            subsystem=extract_subsystem_tag(flag["concern"]),
            concern=flag["concern"],
            flag_ids=[flag["id"]],
            plan_id=state["name"],
        )
    save_debt_registry(root, debt_registry)
    state["current_state"] = STATE_GATED
    state["meta"].pop("user_approved_gate", None)
    state["last_gate"] = {}
    _append_to_meta(state, "overrides", {"action": "force-proceed", "timestamp": now_utc(), "reason": args.reason})
    save_state(plan_dir, state)
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": "Force-proceeded past gate judgment into gated state.",
        "next_step": "finalize",
        "state": STATE_GATED,
        "orchestrator_guidance": gate["orchestrator_guidance"],
        "debt_entries_added": len(unresolved_flags),
    }
    _attach_next_step_runtime(response)
    return response

def _override_replan(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    allowed = {STATE_GATED, STATE_FINALIZED, STATE_CRITIQUED}
    if state["current_state"] not in allowed:
        raise CliError(
            "invalid_transition",
            f"replan requires state {', '.join(sorted(allowed))}, got '{state['current_state']}'",
            valid_next=infer_next_steps(state),
        )
    reason = args.reason or args.note or "Re-entering planning loop"
    plan_file = latest_plan_path(plan_dir, state)
    state["current_state"] = STATE_PLANNED
    state["last_gate"] = {}
    _append_to_meta(state, "overrides", {"action": "replan", "timestamp": now_utc(), "reason": reason})
    if args.note:
        _append_to_meta(state, "notes", {"timestamp": now_utc(), "note": args.note})
    save_state(plan_dir, state)
    next_steps = workflow_next(state)
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": f"Re-entered planning loop at iteration {state['iteration']}. Reason: {reason}",
        "next_step": next_steps[0] if next_steps else None,
        "state": STATE_PLANNED,
        "plan_file": str(plan_file),
        "message": f"Edit {plan_file.name} to incorporate your changes, then run the next step.",
    }
    _attach_next_step_runtime(response)
    return response

def _override_set_robustness(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    new_level = getattr(args, "robustness", None)
    if new_level not in ROBUSTNESS_LEVELS:
        raise CliError(
            "invalid_args",
            f"override set-robustness requires --robustness {'|'.join(ROBUSTNESS_LEVELS)}",
        )
    if state["current_state"] in {STATE_DONE, STATE_ABORTED}:
        raise CliError(
            "invalid_transition",
            f"set-robustness cannot be applied to a plan in terminal state '{state['current_state']}'",
        )
    previous_level = state["config"].get("robustness", "standard")
    state["config"]["robustness"] = new_level
    _append_to_meta(
        state,
        "overrides",
        {
            "action": "set-robustness",
            "timestamp": now_utc(),
            "from": previous_level,
            "to": new_level,
            "reason": args.reason,
        },
    )
    save_state(plan_dir, state)
    next_steps = infer_next_steps(state)
    summary = (
        f"Robustness unchanged at '{new_level}'."
        if previous_level == new_level
        else f"Robustness changed from '{previous_level}' to '{new_level}'. Takes effect on the next phase."
    )
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": summary,
        "next_step": next_steps[0] if next_steps else None,
        "state": state["current_state"],
        "previous_robustness": previous_level,
        "robustness": new_level,
    }
    _attach_next_step_runtime(response)
    return response

_OVERRIDE_ACTIONS: dict[str, Callable[[Path, Path, PlanState, argparse.Namespace], StepResponse]] = {
    "add-note": _override_add_note,
    "abort": _override_abort,
    "force-proceed": _override_force_proceed,
    "replan": _override_replan,
    "set-robustness": _override_set_robustness,
}

def handle_override(root: Path, args: argparse.Namespace) -> StepResponse:
    plan_dir, state = load_plan(root, args.plan)
    action = args.override_action
    handler = _OVERRIDE_ACTIONS.get(action)
    if handler is None:
        raise CliError("invalid_override", f"Unknown override action: {action}")
    return handler(root, plan_dir, state, args)
