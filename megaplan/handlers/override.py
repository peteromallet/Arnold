from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from megaplan.types import (
    ROBUSTNESS_LEVELS,
    CliError,
    PlanState,
    STATE_ABORTED,
    STATE_CRITIQUED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FINALIZED,
    STATE_FAILED,
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
    save_state_merge_meta,
    unresolved_significant_flags,
    workflow_next,
)
from megaplan.evaluation import build_gate_artifact, build_gate_signals, run_gate_checks

from .shared import _append_to_meta, _attach_next_step_runtime


_REVISE_STRUCTURAL_OVERRIDE_ACTIONS = {"step-add", "step-remove", "step-move", "replan"}


def _latest_revise_start_iso(plan_dir: Path, state: PlanState) -> str | None:
    """Return the ISO-8601 timestamp of the most recent "absorption" event for
    user notes — i.e., the start of the latest revise, or the timestamp of the
    most recent structural-edit/replan override. Returns None when no
    absorption event has happened yet (in that case, every user note is
    unabsorbed).

    Notes with timestamps strictly greater than the returned cutoff are
    considered unabsorbed. When the cutoff is None, all user notes are
    treated as unabsorbed regardless of timestamp.
    """
    candidates: list[str] = []
    # Revise receipts: prefer metrics["start_timestamp_utc"] (added by the
    # strict-notes audit-fields change) but fall back to the receipt's
    # top-level timestamp_utc for back-compat with pre-existing receipts.
    for receipt_path in plan_dir.glob("step_receipt_revise_v*.json"):
        try:
            import json as _json

            data = _json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        metrics = data.get("metrics") if isinstance(data, dict) else None
        ts = None
        if isinstance(metrics, dict):
            ts = metrics.get("start_timestamp_utc")
        if not isinstance(ts, str) or not ts:
            ts = data.get("timestamp_utc") if isinstance(data, dict) else None
        if isinstance(ts, str) and ts:
            candidates.append(ts)
    # Structural-edit / replan overrides also "absorb" notes, since the user
    # can no longer be reasoning about a stale step list after a structural
    # change.
    for entry in state.get("meta", {}).get("overrides", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("action") in _REVISE_STRUCTURAL_OVERRIDE_ACTIONS:
            ts = entry.get("timestamp")
            if isinstance(ts, str) and ts:
                candidates.append(ts)
    if candidates:
        return max(candidates)
    return None


def _unabsorbed_user_notes(plan_dir: Path, state: PlanState) -> list[dict]:
    cutoff = _latest_revise_start_iso(plan_dir, state)
    notes = state.get("meta", {}).get("notes", [])
    user_notes = [
        n
        for n in notes
        if isinstance(n, dict)
        and n.get("source", "user") == "user"
        and isinstance(n.get("timestamp"), str)
    ]
    if cutoff is None:
        return user_notes
    return [n for n in user_notes if n["timestamp"] > cutoff]


def _override_add_note(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    note = args.note
    source = getattr(args, "source", None) or "user"
    note_entry: dict[str, Any] = {"timestamp": now_utc(), "note": note, "source": source}
    _append_to_meta(state, "notes", note_entry)
    _append_to_meta(state, "overrides", {"action": "add-note", "timestamp": now_utc(), "note": note, "source": source})
    # Merge so a phase that saves between our load and write doesn't clobber
    # this note (and so we don't clobber any concurrent-override appends).
    save_state_merge_meta(plan_dir, state)
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
    save_state_merge_meta(plan_dir, state)
    return {
        "success": True,
        "step": "override",
        "summary": "Plan aborted.",
        "next_step": None,
        "state": STATE_ABORTED,
    }

def _override_force_proceed(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    # Strict-notes invariants. Off by default; on for plans initialized with
    # --strict-notes (and auto-on for --mode metaplan/doc). Two checks:
    #   (1) Reject if any user-source note has been attached after the most
    #       recent absorption event (revise / structural-edit / replan).
    #   (2) If the last gate ESCALATEd, require explicit --user-approved.
    # Note: finalize is not an override path; strict-notes does not block it.
    if state["config"].get("strict_notes", False):
        unabsorbed = _unabsorbed_user_notes(plan_dir, state)
        if unabsorbed:
            raise CliError(
                "unabsorbed_notes_exist",
                (
                    f"strict_notes: {len(unabsorbed)} note(s) attached after the last "
                    "revise; run revise (or replan / step-edit) before force-proceed."
                ),
                extra={
                    "unabsorbed_note_timestamps": [
                        n["timestamp"] for n in unabsorbed
                    ]
                },
            )
        last_recommendation = (state.get("last_gate") or {}).get("recommendation")
        if last_recommendation == "ESCALATE" and not getattr(args, "user_approved", False):
            raise CliError(
                "escalate_requires_user_approval",
                (
                    "strict_notes: gate escalated and requires --user-approved "
                    "before force-proceed."
                ),
            )
    if state["current_state"] == STATE_EXECUTED:
        # Force-proceed from review loop: mark as done despite review issues
        _append_to_meta(state, "overrides", {"action": "force-proceed", "timestamp": now_utc(), "reason": args.reason})
        state["current_state"] = STATE_DONE
        save_state_merge_meta(plan_dir, state)
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
    save_state_merge_meta(plan_dir, state)
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
    allowed = {STATE_GATED, STATE_FINALIZED, STATE_CRITIQUED, STATE_FAILED}
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
    save_state_merge_meta(plan_dir, state)
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
    save_state_merge_meta(plan_dir, state)
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

def _override_set_profile(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    from megaplan.profiles import load_profiles, resolve_profile, profile_to_phase_models

    new_profile = getattr(args, "profile", None)
    if not new_profile:
        raise CliError("invalid_args", "override set-profile requires --profile NAME")
    if state["current_state"] in {STATE_DONE, STATE_ABORTED}:
        raise CliError(
            "invalid_transition",
            f"set-profile cannot be applied to a plan in terminal state '{state['current_state']}'",
        )
    project_dir = Path(state["config"].get("project_dir", str(root)))
    profiles = load_profiles(project_dir=project_dir)
    resolved = resolve_profile(new_profile, profiles)
    phase_models = profile_to_phase_models(resolved)

    previous_profile = state["config"].get("profile")
    state["config"]["profile"] = new_profile
    state["config"]["phase_model"] = phase_models
    _append_to_meta(
        state,
        "overrides",
        {
            "action": "set-profile",
            "timestamp": now_utc(),
            "from": previous_profile,
            "to": new_profile,
            "reason": args.reason,
        },
    )
    save_state_merge_meta(plan_dir, state)
    next_steps = infer_next_steps(state)
    summary = (
        f"Profile unchanged at '{new_profile}'."
        if previous_profile == new_profile
        else f"Profile changed from '{previous_profile}' to '{new_profile}'. Takes effect on the next phase."
    )
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": summary,
        "next_step": next_steps[0] if next_steps else None,
        "state": state["current_state"],
        "previous_profile": previous_profile,
        "profile": new_profile,
    }
    _attach_next_step_runtime(response)
    return response

_OVERRIDE_ACTIONS: dict[str, Callable[[Path, Path, PlanState, argparse.Namespace], StepResponse]] = {
    "add-note": _override_add_note,
    "abort": _override_abort,
    "force-proceed": _override_force_proceed,
    "replan": _override_replan,
    "set-robustness": _override_set_robustness,
    "set-profile": _override_set_profile,
}

def handle_override(root: Path, args: argparse.Namespace) -> StepResponse:
    plan_dir, state = load_plan(root, args.plan)
    action = args.override_action
    handler = _OVERRIDE_ACTIONS.get(action)
    if handler is None:
        raise CliError("invalid_override", f"Unknown override action: {action}")
    return handler(root, plan_dir, state, args)
