from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from megaplan.types import (
    AgentSpec,
    CliError,
    PlanState,
    STATE_ABORTED,
    STATE_AWAITING_HUMAN,
    STATE_BLOCKED,
    STATE_CRITIQUED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FAILED,
    STATE_FINALIZED,
    STATE_GATED,
    STATE_PLANNED,
    STATE_PREPPED,
    STATE_REVIEWED,
    StepResponse,
    DEFAULT_AGENT_ROUTING,
    _PREMIUM_EFFORT_TOKENS,
    _PREMIUM_VENDORS,
    parse_agent_spec,
    format_agent_spec,
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
    read_json,
    save_debt_registry,
    save_state_merge_meta,
    unresolved_significant_flags,
    workflow_next,
)
from megaplan.blocker_recovery import command_blocker_details, evaluate_blocker_recovery
from megaplan.orchestration.evaluation import (
    build_gate_artifact,
    build_gate_signals,
    failed_preflight_checks,
    only_agent_availability_preflight_failed,
    run_gate_checks,
)
from megaplan.orchestration.phase_result import read_phase_result

from .shared import _append_to_meta, _attach_next_step_runtime, _warn_best_effort_emit_failure, _write_gate_json


_REVISE_STRUCTURAL_OVERRIDE_ACTIONS = {"step-add", "step-remove", "step-move", "replan"}


def _last_gate_is_agent_availability_preflight_block(state: PlanState) -> bool:
    last_gate = state.get("last_gate") or {}
    if not isinstance(last_gate, dict):
        return False
    if last_gate.get("recommendation") != "PROCEED" or last_gate.get("passed", False):
        return False
    preflight_results = last_gate.get("preflight_results")
    return (
        isinstance(preflight_results, dict)
        and only_agent_availability_preflight_failed(preflight_results)
    )


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


def _override_add_note(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    note = args.note
    source = getattr(args, "source", None) or "user"
    note_entry: dict[str, Any] = {
        "timestamp": now_utc(),
        "note": note,
        "source": source,
    }
    _append_to_meta(state, "notes", note_entry)
    _append_to_meta(
        state,
        "overrides",
        {"action": "add-note", "timestamp": now_utc(), "note": note, "source": source},
    )
    # Merge so a phase that saves between our load and write doesn't clobber
    # this note (and so we don't clobber any concurrent-override appends).
    save_state_merge_meta(plan_dir, state)
    next_steps = infer_next_steps(state)
    # Emit observability events
    try:
        from megaplan.observability.events import emit, EventKind
        emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "add-note", "reason": note, "source": source})
        emit(EventKind.NOTE_ADDED, plan_dir=plan_dir, payload={"note": note, "source": source})
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_EMIT_OVERRIDE_ADD_NOTE",
            action="override-add-note",
            plan_dir=plan_dir,
            event_kind="override_applied,note_added",
            context={"source": source},
        )
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": "Attached note to the plan.",
        "next_step": next_steps[0] if next_steps else None,
        "state": state["current_state"],
    }
    _attach_next_step_runtime(response)
    return response


def _override_abort(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    state["current_state"] = STATE_ABORTED
    _append_to_meta(
        state,
        "overrides",
        {"action": "abort", "timestamp": now_utc(), "reason": args.reason},
    )
    save_state_merge_meta(plan_dir, state)
    try:
        from megaplan.observability.events import emit, EventKind
        emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "abort", "reason": args.reason})
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_EMIT_OVERRIDE_ABORT",
            action="override-abort",
            plan_dir=plan_dir,
            event_kind="override_applied",
        )
    return {
        "success": True,
        "step": "override",
        "summary": "Plan aborted.",
        "next_step": None,
        "state": STATE_ABORTED,
    }


def _override_force_proceed(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
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
                    "unabsorbed_note_timestamps": [n["timestamp"] for n in unabsorbed]
                },
            )
        last_recommendation = (state.get("last_gate") or {}).get("recommendation")
        if last_recommendation == "ESCALATE" and not getattr(
            args, "user_approved", False
        ):
            raise CliError(
                "escalate_requires_user_approval",
                (
                    "strict_notes: gate escalated and requires --user-approved "
                    "before force-proceed."
                ),
            )
    if state["current_state"] == STATE_EXECUTED:
        # Force-proceed from review loop: mark as done despite review issues
        _append_to_meta(
            state,
            "overrides",
            {"action": "force-proceed", "timestamp": now_utc(), "reason": args.reason},
        )
        state["current_state"] = STATE_DONE
        save_state_merge_meta(plan_dir, state)
        return {
            "success": True,
            "step": "override",
            "summary": "Force-proceeded past review into done state.",
            "next_step": None,
            "state": STATE_DONE,
        }
    if state["current_state"] == STATE_BLOCKED:
        if not _last_gate_is_agent_availability_preflight_block(state):
            raise CliError(
                "invalid_transition",
                "force-proceed from blocked is only supported for PROCEED gates blocked by agent availability preflight",
                valid_next=infer_next_steps(state),
            )
    elif state["current_state"] != STATE_CRITIQUED:
        raise CliError(
            "invalid_transition",
            "force-proceed is only supported from critiqued, executed, or recoverable blocked state",
            valid_next=infer_next_steps(state),
        )
    gate_checks = run_gate_checks(plan_dir, state, command_lookup=find_command)
    hard_failed = [
        name
        for name in failed_preflight_checks(gate_checks["preflight_results"])
        if name not in {"claude_available", "codex_available"}
    ]
    if hard_failed:
        labels = {
            "project_dir_exists": "project directory",
            "project_dir_writable": "project directory writable",
            "success_criteria_present": "success criteria",
        }
        readable = [labels.get(name, name) for name in hard_failed]
        raise CliError(
            "unsafe_override",
            "force-proceed cannot bypass hard preflight failures: " + ", ".join(readable),
        )
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
    _write_gate_json(plan_dir, gate)
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
    _append_to_meta(
        state,
        "overrides",
        {"action": "force-proceed", "timestamp": now_utc(), "reason": args.reason},
    )
    save_state_merge_meta(plan_dir, state)
    try:
        from megaplan.observability.events import emit, EventKind
        emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "force-proceed", "reason": args.reason})
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_EMIT_OVERRIDE_FORCE_PROCEED",
            action="override-force-proceed",
            plan_dir=plan_dir,
            event_kind="override_applied",
        )
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


def _override_replan(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
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
    _append_to_meta(
        state,
        "overrides",
        {"action": "replan", "timestamp": now_utc(), "reason": reason},
    )
    if args.note:
        _append_to_meta(state, "notes", {"timestamp": now_utc(), "note": args.note})
    save_state_merge_meta(plan_dir, state)
    try:
        from megaplan.observability.events import emit, EventKind
        emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "replan", "reason": reason})
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_EMIT_OVERRIDE_REPLAN",
            action="override-replan",
            plan_dir=plan_dir,
            event_kind="override_applied",
        )
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


_BLOCKED_RECOVERY_STATES: dict[str, str] = {
    "prep": "initialized",
    "plan": "initialized",
    "critique": STATE_PLANNED,
    "gate": STATE_CRITIQUED,
    "revise": STATE_CRITIQUED,
    "finalize": STATE_GATED,
    "execute": STATE_FINALIZED,
    "review": STATE_EXECUTED,
    "feedback": STATE_REVIEWED,
}


_EXTERNAL_ERROR_RETRY_STRATEGIES = {"wait_and_retry", "check_provider_and_retry"}


def _external_error_requires_resume(
    state: PlanState,
    resume_cursor: dict[str, Any],
    phase_result: Any | None,
) -> bool:
    latest_failure = state.get("latest_failure")
    if (
        isinstance(latest_failure, dict)
        and latest_failure.get("kind") == "external_error"
    ):
        return True
    if getattr(phase_result, "exit_kind", None) == "external_error":
        return True
    return resume_cursor.get("retry_strategy") in _EXTERNAL_ERROR_RETRY_STRATEGIES


def _override_recover_blocked(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    if state["current_state"] != STATE_BLOCKED:
        raise CliError(
            "invalid_transition",
            f"recover-blocked requires state '{STATE_BLOCKED}', got '{state['current_state']}'",
            valid_next=infer_next_steps(state),
        )
    reason = getattr(args, "reason", None)
    if not isinstance(reason, str) or not reason.strip():
        raise CliError("invalid_args", "override recover-blocked requires --reason")
    resume_cursor = state.get("resume_cursor")
    if not isinstance(resume_cursor, dict):
        raise CliError(
            "missing_resume_cursor",
            "recover-blocked requires a stored resume_cursor",
        )
    phase = resume_cursor.get("phase")
    if not isinstance(phase, str) or not phase:
        raise CliError(
            "invalid_resume_cursor",
            "recover-blocked requires resume_cursor.phase",
            extra={"resume_cursor": resume_cursor},
        )
    recovered_state = _BLOCKED_RECOVERY_STATES.get(phase)
    if recovered_state is None:
        raise CliError(
            "invalid_resume_cursor",
            f"recover-blocked does not know how to resume phase {phase!r}",
            extra={"resume_cursor": resume_cursor},
        )

    finalize_path = plan_dir / "finalize.json"
    finalize_data = read_json(finalize_path) if finalize_path.exists() else {}
    phase_result = read_phase_result(plan_dir)
    if _external_error_requires_resume(state, resume_cursor, phase_result):
        plan_name = state.get("name") or getattr(args, "plan", None) or plan_dir.name
        resume_command = f"megaplan resume --plan {plan_name}"
        raise CliError(
            "external_error_resume_required",
            (
                "recover-blocked is for explicit task or quality blockers. "
                "This blocked plan stopped on an external provider error; "
                f"fix provider/profile settings if needed, then run `{resume_command}`."
            ),
            extra={
                "resume_cursor": resume_cursor,
                "phase_result_exit_kind": (
                    getattr(phase_result, "exit_kind", None)
                    if phase_result is not None
                    else None
                ),
                "latest_failure": state.get("latest_failure"),
                "resume_command": resume_command,
                "suggested_recovery_commands": [resume_command],
            },
        )
    if phase_result is None:
        raise CliError(
            "missing_phase_result",
            "recover-blocked requires phase_result.json with current blocker details",
            extra={"resume_cursor": resume_cursor},
        )
    evaluation = evaluate_blocker_recovery(
        finalize_data,
        state,
        blocked_tasks=phase_result.blocked_tasks,
        deviations=phase_result.deviations,
    )
    blocker_details = command_blocker_details(evaluation)
    if not evaluation.can_continue:
        unresolved_blockers = [
            blocker
            for blocker in blocker_details
            if not blocker.get("is_non_terminal", False)
        ]
        raise CliError(
            "blocked_recovery_not_resolved",
            "recover-blocked requires every current blocker to be explicitly resolved as non-terminal",
            extra={
                "resume_cursor": resume_cursor,
                "phase_result_exit_kind": phase_result.exit_kind,
                "blocker_ids": [
                    blocker["blocker_id"] for blocker in unresolved_blockers
                ],
                "unresolved_blockers": unresolved_blockers,
                "blockers": blocker_details,
                "can_continue": evaluation.can_continue,
                "requires_rerun": evaluation.requires_rerun,
            },
        )

    previous_state = state["current_state"]
    state["current_state"] = recovered_state
    state.pop("latest_failure", None)
    state.pop("active_step", None)
    _append_to_meta(
        state,
        "overrides",
        {
            "action": "recover-blocked",
            "timestamp": now_utc(),
            "reason": reason,
            "from_state": previous_state,
            "to_state": recovered_state,
            "resume_cursor": dict(resume_cursor),
            "blocker_ids": [blocker.blocker_id for blocker in evaluation.blockers],
        },
    )
    save_state_merge_meta(plan_dir, state)
    next_steps = infer_next_steps(state)
    response: StepResponse = {
        "success": True,
        "step": "override",
        "action": "recover-blocked",
        "summary": (
            f"Recovered blocked plan to state '{recovered_state}' for phase "
            f"{phase!r}. Reason: {reason}"
        ),
        "state": recovered_state,
        "previous_state": previous_state,
        "phase": phase,
        "next_step": next_steps[0] if next_steps else None,
        "resume_cursor": resume_cursor,
        "blockers": blocker_details,
    }
    _attach_next_step_runtime(response)
    return response


def _override_set_robustness(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    from megaplan.types import ROBUSTNESS_ACCEPTED, normalize_robustness

    raw_level = getattr(args, "robustness", None)
    if raw_level not in ROBUSTNESS_ACCEPTED:
        raise CliError(
            "invalid_args",
            f"override set-robustness requires --robustness {'|'.join(ROBUSTNESS_ACCEPTED)}",
        )
    new_level = normalize_robustness(raw_level)
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
    try:
        from megaplan.observability.events import emit, EventKind
        emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "set-robustness", "from": previous_level, "to": new_level, "reason": args.reason})
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_EMIT_OVERRIDE_ROBUSTNESS",
            action="override-set-robustness",
            plan_dir=plan_dir,
            event_kind="override_applied",
            context={"from_level": previous_level, "to_level": new_level},
        )
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


def _override_set_profile(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    from megaplan.profiles import (
        load_profiles,
        resolve_profile,
        profile_to_phase_models,
    )

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
    try:
        from megaplan.observability.events import emit, EventKind
        emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "set-profile", "from": previous_profile, "to": new_profile, "reason": args.reason})
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_EMIT_OVERRIDE_PROFILE",
            action="override-set-profile",
            plan_dir=plan_dir,
            event_kind="override_applied",
            context={"from_profile": previous_profile, "to_profile": new_profile},
        )
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

def _override_set_model(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    """Override: change the model for a specific phase."""
    phase = getattr(args, "phase", None)
    model_arg = getattr(args, "model", None)
    effort = getattr(args, "effort", None)

    # Validate required args
    if not phase:
        raise CliError("invalid_args", "override set-model requires --phase PHASE")
    if not model_arg:
        raise CliError("invalid_args", "override set-model requires --model MODEL")

    # Validate known phase names
    if phase not in DEFAULT_AGENT_ROUTING:
        raise CliError(
            "invalid_args",
            f"Unknown phase '{phase}'. Valid phases: {', '.join(sorted(DEFAULT_AGENT_ROUTING))}",
        )

    # Infer the target agent for this phase
    # Priority: (1) persisted phase_model entry, (2) active profile, (3) DEFAULT_AGENT_ROUTING
    agent = _infer_phase_agent(phase, state, root)
    if agent is None:
        agent = DEFAULT_AGENT_ROUTING.get(phase, "")

    explicit_spec = parse_agent_spec(model_arg) if ":" in model_arg else None
    if explicit_spec is not None and explicit_spec.agent in _PREMIUM_VENDORS:
        target_agent = explicit_spec.agent
        target_model = explicit_spec.model
        target_effort = explicit_spec.effort
        if target_model is None:
            raise CliError(
                "invalid_args",
                f"'{model_arg}' does not name a model. "
                f"Use --model {target_agent}:MODEL or --model MODEL --effort {target_effort or 'EFFORT'}.",
            )
        if effort is not None and target_effort is not None:
            raise CliError(
                "invalid_args",
                "Effort was provided twice: once in --model and once via --effort.",
            )
        if effort is not None:
            target_effort = effort
    elif explicit_spec is not None:
        raise CliError(
            "invalid_args",
            f"set-model only supports claude/codex specs; got '{explicit_spec.agent}'. "
            "Use --phase-model on the phase command for hermes/shannon routing.",
        )
    else:
        # set-model only allowed for claude/codex
        if agent not in _PREMIUM_VENDORS:
            raise CliError(
                "invalid_args",
                f"set-model is only supported for claude/codex phases. "
                f"Phase '{phase}' resolves to agent '{agent}'.",
            )
        target_agent = agent
        target_model = model_arg
        target_effort = effort

    # Reject reserved effort tokens as --model values
    if target_model in _PREMIUM_EFFORT_TOKENS:
        raise CliError(
            "invalid_args",
            f"'{target_model}' is a reserved effort token and cannot be used as a model name. "
            f"Use --effort to set effort level.",
        )

    # Validate effort if provided
    if target_effort is not None and target_effort not in _PREMIUM_EFFORT_TOKENS:
        raise CliError(
            "invalid_args",
            f"Unknown effort level '{target_effort}'. Valid: {', '.join(sorted(_PREMIUM_EFFORT_TOKENS))}",
        )

    # Build the new spec string
    new_spec = format_agent_spec(AgentSpec(target_agent, model=target_model, effort=target_effort))

    # Find and update the phase_model entry
    phase_models = list(state["config"].get("phase_model") or [])
    previous_spec = None
    found = False
    for i, pm in enumerate(phase_models):
        if "=" in pm and pm.split("=", 1)[0] == phase:
            previous_spec = pm.split("=", 1)[1]
            phase_models[i] = f"{phase}={new_spec}"
            found = True
            break
    if not found:
        # No existing entry — append a new one
        previous_spec = DEFAULT_AGENT_ROUTING.get(phase, "")
        phase_models.append(f"{phase}={new_spec}")

    state["config"]["phase_model"] = phase_models

    # Append override meta entry
    _append_to_meta(
        state,
        "overrides",
        {
            "action": "set-model",
            "phase": phase,
            "previous_spec": previous_spec,
            "new_spec": new_spec,
            "timestamp": now_utc(),
            "reason": getattr(args, "reason", "") or "",
        },
    )
    save_state_merge_meta(plan_dir, state)

    next_steps = infer_next_steps(state)
    summary = (
        f"Model for phase '{phase}' changed from '{previous_spec}' to '{new_spec}'. "
        f"Takes effect on the next phase."
    )
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": summary,
        "next_step": next_steps[0] if next_steps else None,
        "state": state["current_state"],
        "phase": phase,
        "previous_spec": previous_spec,
        "new_spec": new_spec,
    }
    _attach_next_step_runtime(response)
    return response


def _current_phase_spec(phase: str, state: PlanState, root: Path) -> str:
    """Resolve the spec currently in force for *phase*.

    Priority mirrors :func:`_infer_phase_agent`: persisted ``phase_model``
    entry, then active profile, then ``DEFAULT_AGENT_ROUTING``.
    """
    phase_models = state.get("config", {}).get("phase_model") or []
    for pm in phase_models:
        if isinstance(pm, str) and "=" in pm:
            pm_phase, pm_spec = pm.split("=", 1)
            if pm_phase == phase:
                return pm_spec
    profile_name = state.get("config", {}).get("profile")
    if profile_name:
        try:
            from megaplan.profiles import load_profiles, resolve_profile

            project_dir = Path(state["config"].get("project_dir", str(root)))
            profiles = load_profiles(project_dir=project_dir)
            resolved = resolve_profile(profile_name, profiles)
            if phase in resolved:
                return resolved[phase]
        except Exception:
            pass
    return DEFAULT_AGENT_ROUTING.get(phase, "")


def _override_set_vendor(root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace) -> StepResponse:
    """Override: re-point a phase's premium vendor (claude <-> codex) cleanly.

    Mirrors ``set-model``'s clean construction: it resolves the spec currently
    in force for the phase and swaps only the vendor via the same
    ``_swap_premium_spec`` logic the ``--vendor`` profile rewrite uses, then
    re-formats through ``parse_agent_spec``/``format_agent_spec``. This removes
    the hand-edit vector that produced the malformed ``codex:claude:sonnet``
    pin (the original bug): an operator no longer needs to hand-write a spec.
    """
    phase = getattr(args, "phase", None)
    vendor = getattr(args, "vendor", None)

    if not phase:
        raise CliError("invalid_args", "override set-vendor requires --phase PHASE")
    if not vendor:
        raise CliError("invalid_args", "override set-vendor requires --vendor VENDOR")
    if phase not in DEFAULT_AGENT_ROUTING:
        raise CliError(
            "invalid_args",
            f"Unknown phase '{phase}'. Valid phases: {', '.join(sorted(DEFAULT_AGENT_ROUTING))}",
        )

    from megaplan.profiles import _swap_premium_spec
    from megaplan._core.user_config import VALID_VENDORS

    if vendor not in VALID_VENDORS:
        raise CliError(
            "invalid_args",
            f"set-vendor --vendor must be one of {', '.join(VALID_VENDORS)}; got {vendor!r}",
        )

    current_spec = _current_phase_spec(phase, state, root)
    parsed = parse_agent_spec(current_spec)
    if parsed.agent not in _PREMIUM_VENDORS:
        raise CliError(
            "invalid_args",
            f"set-vendor is only supported for claude/codex phases. "
            f"Phase '{phase}' resolves to agent '{parsed.agent}' ({current_spec!r}).",
        )

    # _swap_premium_spec raises vendor_swap_model_conflict on an explicit model
    # pin with no cross-vendor equivalent; re-format through the parser so the
    # persisted spec is always canonical (and re-validated).
    swapped = _swap_premium_spec(current_spec, vendor)
    new_spec = format_agent_spec(parse_agent_spec(swapped))

    phase_models = list(state["config"].get("phase_model") or [])
    previous_spec = None
    found = False
    for i, pm in enumerate(phase_models):
        if "=" in pm and pm.split("=", 1)[0] == phase:
            previous_spec = pm.split("=", 1)[1]
            phase_models[i] = f"{phase}={new_spec}"
            found = True
            break
    if not found:
        previous_spec = current_spec or DEFAULT_AGENT_ROUTING.get(phase, "")
        phase_models.append(f"{phase}={new_spec}")
    state["config"]["phase_model"] = phase_models

    _append_to_meta(
        state,
        "overrides",
        {
            "action": "set-vendor",
            "phase": phase,
            "previous_spec": previous_spec,
            "new_spec": new_spec,
            "timestamp": now_utc(),
            "reason": getattr(args, "reason", "") or "",
        },
    )
    save_state_merge_meta(plan_dir, state)

    next_steps = infer_next_steps(state)
    summary = (
        f"Vendor for phase '{phase}' changed from '{previous_spec}' to '{new_spec}'. "
        f"Takes effect on the next phase."
    )
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": summary,
        "next_step": next_steps[0] if next_steps else None,
        "state": state["current_state"],
        "phase": phase,
        "previous_spec": previous_spec,
        "new_spec": new_spec,
    }
    _attach_next_step_runtime(response)
    return response


def _infer_phase_agent(phase: str, state: PlanState, root: Path) -> str | None:
    """Infer the agent for a phase from persisted state or defaults."""
    # Check persisted phase_model for an explicit spec
    phase_models = state.get("config", {}).get("phase_model") or []
    for pm in phase_models:
        if isinstance(pm, str) and "=" in pm:
            pm_phase, pm_spec = pm.split("=", 1)
            if pm_phase == phase:
                parsed = parse_agent_spec(pm_spec)
                return parsed.agent

    # Check active profile
    profile_name = state.get("config", {}).get("profile")
    if profile_name:
        try:
            from megaplan.profiles import load_profiles, resolve_profile
            project_dir = Path(state["config"].get("project_dir", str(root)))
            profiles = load_profiles(project_dir=project_dir)
            resolved = resolve_profile(profile_name, profiles)
            if phase in resolved:
                parsed = parse_agent_spec(resolved[phase])
                return parsed.agent
        except Exception:
            pass

    # Fall back to DEFAULT_AGENT_ROUTING
    return DEFAULT_AGENT_ROUTING.get(phase)


def _override_resume_clarify(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    if state["current_state"] != STATE_AWAITING_HUMAN:
        raise CliError(
            "invalid_transition",
            f"resume-clarify requires state '{STATE_AWAITING_HUMAN}', got '{state['current_state']}'",
            valid_next=infer_next_steps(state),
        )
    if state.get("clarification", {}).get("source") != "prep":
        raise CliError(
            "invalid_transition",
            "resume-clarify can only resume a prep-sourced clarification halt; "
            "use verify-human for criteria-verification awaiting_human states",
            valid_next=infer_next_steps(state),
        )
    notes = state.get("meta", {}).get("notes") or []
    user_notes = [n for n in notes if isinstance(n, dict) and n.get("source", "user") == "user"]
    warnings: list[str] = []
    if not user_notes:
        warnings.append(
            "No answers found in notes; consider adding answers via "
            "'override add-note' before the plan phase."
        )
    state["current_state"] = STATE_PREPPED
    _append_to_meta(
        state,
        "overrides",
        {"action": "resume-clarify", "timestamp": now_utc()},
    )
    save_state_merge_meta(plan_dir, state)
    try:
        from megaplan.observability.events import emit, EventKind
        emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "resume-clarify"})
    except Exception:
        pass
    next_steps = infer_next_steps(state)
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": "Prep clarification resolved; plan phase is now ready to run.",
        "next_step": next_steps[0] if next_steps else None,
        "state": STATE_PREPPED,
    }
    if warnings:
        response["warnings"] = warnings
    _attach_next_step_runtime(response)
    return response


_OVERRIDE_ACTIONS: dict[
    str, Callable[[Path, Path, PlanState, argparse.Namespace], StepResponse]
] = {
    "add-note": _override_add_note,
    "abort": _override_abort,
    "force-proceed": _override_force_proceed,
    "replan": _override_replan,
    "recover-blocked": _override_recover_blocked,
    "resume-clarify": _override_resume_clarify,
    "set-robustness": _override_set_robustness,
    "set-profile": _override_set_profile,
    "set-model": _override_set_model,
    "set-vendor": _override_set_vendor,
}


def handle_override(root: Path, args: argparse.Namespace) -> StepResponse:
    plan_dir, state = load_plan(root, args.plan)
    action = args.override_action
    handler = _OVERRIDE_ACTIONS.get(action)
    if handler is None:
        raise CliError("invalid_override", f"Unknown override action: {action}")
    return handler(root, plan_dir, state, args)
