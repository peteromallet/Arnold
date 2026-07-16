from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.feature_flags import control_interface_routing_on
from arnold_pipelines.megaplan.profiles import (
    DEFAULT_AGENT_ROUTING,
    ROBUSTNESS_ACCEPTED,
    effective_premium_vendor,
    normalize_robustness,
)
from arnold_pipelines.megaplan.fallback_chains import decode_phase_model_value, select_fallback_spec
from arnold_pipelines.megaplan.types import (
    AgentSpec,
    CliError,
    PlanState,
    StepResponse,
    _PREMIUM_EFFORT_TOKENS,
    _PREMIUM_VENDORS,
    is_premium_placeholder_spec,
    parse_agent_spec,
    format_agent_spec,
    resolve_premium_placeholder_spec,
)
from arnold_pipelines.megaplan.planning.state import (
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
)
from arnold_pipelines.megaplan.runtime.execution_environment import (
    preflight_mutating_phase,
    preflight_phase,
)
from arnold_pipelines.megaplan._core import (
    add_or_increment_debt,
    append_history,
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
    sha256_file,
    unresolved_significant_flags,
    workflow_next,
)
from arnold_pipelines.megaplan._core import topology as _topology
from arnold.control.interface import ControlTransition, RunStateView
from arnold_pipelines.megaplan.control_interface import (
    apply_transition,
    emit_override_authority_receipt,
)
from arnold_pipelines.megaplan.blocker_recovery import (
    command_blocker_details,
    evaluate_blocker_recovery,
    validated_deterministic_phase_repair,
)
from arnold_pipelines.megaplan.orchestration.gate_checks import (
    build_gate_artifact,
    failed_preflight_checks,
    has_high_complexity_unverifiable_checks,
    is_operational_unverifiable_check,
    only_agent_availability_preflight_failed,
    run_gate_checks,
)
from arnold_pipelines.megaplan.orchestration.gate_signals import build_gate_signals
from arnold_pipelines.megaplan.orchestration.phase_result import (
    ExitKind,
    PhaseResult,
    atomic_write_phase_result,
    read_phase_result,
)
from arnold_pipelines.megaplan.replan_state import reset_replan_loop_state
from .shared import _append_to_meta, _attach_next_step_runtime, _warn_best_effort_emit_failure, _write_gate_json


_REVISE_STRUCTURAL_OVERRIDE_ACTIONS = {"step-add", "step-remove", "step-move", "replan"}
@dataclass(frozen=True)
class UnknownOverrideActionError(ValueError):
    action: str

    def __str__(self) -> str:
        return f"Unknown override action: {self.action}"


@dataclass(frozen=True)
class OverrideActionOutput:
    summary: str
    state: str
    route_signal: str | None = None
    next_step: str | None = None
    extras: tuple[tuple[str, Any], ...] = ()


def _override_action_entry(action: str):
    from arnold_pipelines.megaplan.workflows.override_matrix import get_entry

    return get_entry(action)


def _control_routed_override_actions() -> frozenset[str]:
    from arnold_pipelines.megaplan.workflows.override_matrix import CONTROL_ROUTED_ACTIONS

    return CONTROL_ROUTED_ACTIONS


def _route_signal_for_override_action(action: str) -> str | None:
    from arnold_pipelines.megaplan.workflows.override_matrix import ROUTE_SIGNAL_BY_ACTION

    return ROUTE_SIGNAL_BY_ACTION.get(action)


def _archive_stale_phase_result_for_resume(plan_dir: Path) -> str | None:
    """Move the terminal phase_result aside before resuming a blocked plan.

    ``recover-blocked`` changes ``state.current_state`` back to the predecessor
    phase. Keeping the old terminal ``phase_result.json`` in place makes status
    and blocker-recovery read contradictory evidence from the superseded blocked
    phase.
    """

    phase_result_path = plan_dir / "phase_result.json"
    if not phase_result_path.exists():
        return None
    stamp = (
        now_utc()
        .replace("-", "")
        .replace(":", "")
        .replace(".", "")
    )
    backup_path = plan_dir / f"phase_result.recovered-{stamp}.json"
    suffix = 1
    while backup_path.exists():
        backup_path = plan_dir / f"phase_result.recovered-{stamp}-{suffix}.json"
        suffix += 1
    phase_result_path.replace(backup_path)
    return backup_path.name


def _override_response_owns_next_step(action: str) -> bool:
    try:
        return _override_action_entry(action).family != "terminal_route"
    except KeyError:
        return action not in _control_routed_override_actions()


def _build_override_action_output(
    action: str,
    *,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
    artifacts: dict[str, Any] | None = None,
) -> OverrideActionOutput:
    next_steps = infer_next_steps(state)
    try:
        route_signal = _override_action_entry(action).route_signal
    except KeyError as error:
        raise UnknownOverrideActionError(action) from error
    if action == "add-note":
        return OverrideActionOutput(
            summary="Attached note to the plan.",
            state=state["current_state"],
            route_signal=route_signal,
            next_step=next_steps[0] if next_steps else None,
        )
    if action == "abort":
        return OverrideActionOutput(
            summary="Plan aborted.",
            state=STATE_ABORTED,
            route_signal=route_signal,
        )
    if action == "force-proceed":
        meta = state.get("meta")
        overrides = meta.get("overrides", []) if isinstance(meta, dict) else []
        latest_override = next(
            (
                entry
                for entry in reversed(overrides)
                if isinstance(entry, dict) and entry.get("action") == "force-proceed"
            ),
            {},
        )
        if state["current_state"] == STATE_DONE:
            return OverrideActionOutput(
                summary="Force-proceeded past review into done state.",
                state=STATE_DONE,
                route_signal=route_signal,
            )
        return OverrideActionOutput(
            summary="Force-proceeded past gate judgment into gated state.",
            state=STATE_GATED,
            route_signal=route_signal,
            next_step="finalize",
            extras=(
                (
                    "orchestrator_guidance",
                    (artifacts or {}).get(
                        "orchestrator_guidance",
                        "Force-proceed override applied. Proceed to finalize.",
                    ),
                ),
                (
                    "debt_entries_added",
                    (artifacts or {}).get(
                        "debt_entries_added",
                        latest_override.get("debt_entries_added", 0),
                    ),
                ),
            ),
        )
    if action == "set-robustness":
        previous_level = "standard"
        meta = state.get("meta")
        overrides = meta.get("overrides", []) if isinstance(meta, dict) else []
        for entry in reversed(overrides):
            if isinstance(entry, dict) and entry.get("action") == "set-robustness":
                previous_level = entry.get("from", "standard")
                break
        new_level = state["config"].get("robustness", "standard")
        summary = (
            f"Robustness unchanged at '{new_level}'."
            if previous_level == new_level
            else f"Robustness changed from '{previous_level}' to '{new_level}'. Takes effect on the next phase."
        )
        return OverrideActionOutput(
            summary=summary,
            state=state["current_state"],
            route_signal=route_signal,
            next_step=next_steps[0] if next_steps else None,
            extras=(("previous_robustness", previous_level), ("robustness", new_level)),
        )
    if action == "recover-blocked":
        meta = state.get("meta")
        overrides = meta.get("overrides", []) if isinstance(meta, dict) else []
        latest_override = next(
            entry
            for entry in reversed(overrides)
            if isinstance(entry, dict) and entry.get("action") == "recover-blocked"
        )
        resume_cursor = latest_override.get("resume_cursor")
        phase = (
            resume_cursor.get("phase")
            if isinstance(resume_cursor, dict)
            else latest_override.get("phase")
        )
        return OverrideActionOutput(
            summary=(
                f"Recovered blocked plan to state '{state['current_state']}' for phase "
                f"{phase!r}. Reason: {latest_override.get('reason')}"
            ),
            state=state["current_state"],
            route_signal=route_signal,
            next_step=next_steps[0] if next_steps else None,
            extras=(
                ("action", "recover-blocked"),
                ("previous_state", latest_override.get("from_state")),
                ("phase", phase),
                ("resume_cursor", resume_cursor),
                ("blockers", (artifacts or {}).get("blockers", [])),
            ),
        )
    if action == "resume-clarify":
        warnings = (artifacts or {}).get("warnings", [])
        extras: list[tuple[str, Any]] = []
        if warnings:
            extras.append(("warnings", warnings))
        return OverrideActionOutput(
            summary="Prep clarification resolved; plan phase is now ready to run.",
            state=STATE_PREPPED,
            route_signal=route_signal,
            next_step=next_steps[0] if next_steps else None,
            extras=tuple(extras),
        )
    if action == "replan":
        reason = getattr(args, "reason", None) or getattr(args, "note", None) or "Re-entering planning loop"
        plan_file_raw = (artifacts or {}).get("plan_file")
        plan_file = Path(plan_file_raw) if isinstance(plan_file_raw, str) and plan_file_raw else latest_plan_path(plan_dir, state)
        return OverrideActionOutput(
            summary=f"Re-entered planning loop at iteration {state['iteration']}. Reason: {reason}",
            state=STATE_PLANNED,
            route_signal=route_signal,
            extras=(
                ("plan_file", str(plan_file)),
                ("message", f"Edit {plan_file.name} to incorporate your changes, then run the next step."),
            ),
        )
    if action == "set-profile":
        previous_profile = None
        meta = state.get("meta")
        overrides = meta.get("overrides", []) if isinstance(meta, dict) else []
        for entry in reversed(overrides):
            if isinstance(entry, dict) and entry.get("action") == "set-profile":
                previous_profile = entry.get("from")
                break
        new_profile = state["config"].get("profile")
        summary = (
            f"Profile unchanged at '{new_profile}'."
            if previous_profile == new_profile
            else f"Profile changed from '{previous_profile}' to '{new_profile}'. Takes effect on the next phase."
        )
        return OverrideActionOutput(
            summary=summary,
            state=state["current_state"],
            route_signal=route_signal,
            next_step=next_steps[0] if next_steps else None,
            extras=(("previous_profile", previous_profile), ("profile", new_profile)),
        )
    if action in {"set-model", "set-vendor"}:
        meta = state.get("meta")
        overrides = meta.get("overrides", []) if isinstance(meta, dict) else []
        latest_override = next(
            entry
            for entry in reversed(overrides)
            if isinstance(entry, dict) and entry.get("action") == action
        )
        phase = latest_override.get("phase")
        previous_spec = latest_override.get("previous_spec")
        new_spec = latest_override.get("new_spec")
        summary = (
            f"{'Model' if action == 'set-model' else 'Vendor'} for phase '{phase}' "
            f"changed from '{previous_spec}' to '{new_spec}'. Takes effect on the next phase."
        )
        return OverrideActionOutput(
            summary=summary,
            state=state["current_state"],
            route_signal=route_signal,
            next_step=next_steps[0] if next_steps else None,
            extras=(("phase", phase), ("previous_spec", previous_spec), ("new_spec", new_spec)),
        )
    raise UnknownOverrideActionError(action)


def _routed_override_response(
    action: str,
    *,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
    artifacts: dict[str, Any] | None = None,
) -> StepResponse:
    try:
        action_output = _build_override_action_output(
            action,
            plan_dir=plan_dir,
            state=state,
            args=args,
            artifacts=artifacts,
        )
    except UnknownOverrideActionError as error:
        raise CliError("invalid_override", str(error)) from error
    response: StepResponse = {
        "success": True,
        "step": "override",
        "override_action": action,
        "summary": action_output.summary,
        "state": action_output.state,
    }
    if _override_response_owns_next_step(action) and action_output.next_step is not None:
        response["next_step"] = action_output.next_step
    if action_output.route_signal is not None:
        response["route_signal"] = action_output.route_signal
    for key, value in action_output.extras:
        response[key] = value
    if "next_step" in response:
        _attach_next_step_runtime(response)
    return response


def _emit_routed_override_events(
    action: str,
    *,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
) -> None:
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind, emit

        if action == "add-note":
            note = getattr(args, "note", None)
            source = getattr(args, "source", None) or "user"
            emit(
                EventKind.OVERRIDE_APPLIED,
                plan_dir=plan_dir,
                payload={"action": "add-note", "reason": note, "source": source},
            )
            emit(
                EventKind.NOTE_ADDED,
                plan_dir=plan_dir,
                payload={"note": note, "source": source},
            )
            return
        if action == "abort":
            emit(
                EventKind.OVERRIDE_APPLIED,
                plan_dir=plan_dir,
                payload={"action": "abort", "reason": args.reason},
            )
            return
        if action == "force-proceed":
            emit(
                EventKind.OVERRIDE_APPLIED,
                plan_dir=plan_dir,
                payload={"action": "force-proceed", "reason": args.reason},
            )
            return
        if action == "set-robustness":
            meta = state.get("meta")
            overrides = meta.get("overrides", []) if isinstance(meta, dict) else []
            latest_override = next(
                entry
                for entry in reversed(overrides)
                if isinstance(entry, dict) and entry.get("action") == "set-robustness"
            )
            emit(
                EventKind.OVERRIDE_APPLIED,
                plan_dir=plan_dir,
                payload={
                    "action": "set-robustness",
                    "from": latest_override.get("from"),
                    "to": latest_override.get("to"),
                    "reason": latest_override.get("reason"),
                },
            )
            return
        if action == "set-profile":
            meta = state.get("meta")
            overrides = meta.get("overrides", []) if isinstance(meta, dict) else []
            latest_override = next(
                entry
                for entry in reversed(overrides)
                if isinstance(entry, dict) and entry.get("action") == "set-profile"
            )
            emit(
                EventKind.OVERRIDE_APPLIED,
                plan_dir=plan_dir,
                payload={
                    "action": "set-profile",
                    "from": latest_override.get("from"),
                    "to": latest_override.get("to"),
                    "reason": latest_override.get("reason"),
                },
            )
            return
        if action == "recover-blocked":
            return
        if action == "resume-clarify":
            emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "resume-clarify"})
            return
        if action == "replan":
            reason = getattr(args, "reason", None) or getattr(args, "note", None) or "Re-entering planning loop"
            emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "replan", "reason": reason})
            return
        if action in {"set-model", "set-vendor"}:
            return
    except StopIteration:
        pass
    except Exception:
        if action == "add-note":
            _warn_best_effort_emit_failure(
                "M3A_WARN_EMIT_OVERRIDE_ADD_NOTE",
                action="override-add-note",
                plan_dir=plan_dir,
                event_kind="override_applied,note_added",
                context={"source": getattr(args, "source", None) or "user"},
            )
            return
        if action == "abort":
            _warn_best_effort_emit_failure(
                "M3A_WARN_EMIT_OVERRIDE_ABORT",
                action="override-abort",
                plan_dir=plan_dir,
                event_kind="override_applied",
            )
            return
        if action == "force-proceed":
            _warn_best_effort_emit_failure(
                "M3A_WARN_EMIT_OVERRIDE_FORCE_PROCEED",
                action="override-force-proceed",
                plan_dir=plan_dir,
                event_kind="override_applied",
            )
            return
        if action == "set-robustness":
            _warn_best_effort_emit_failure(
                "M3A_WARN_EMIT_OVERRIDE_ROBUSTNESS",
                action="override-set-robustness",
                plan_dir=plan_dir,
                event_kind="override_applied",
            )
            return
        if action == "set-profile":
            _warn_best_effort_emit_failure(
                "M3A_WARN_EMIT_OVERRIDE_PROFILE",
                action="override-set-profile",
                plan_dir=plan_dir,
                event_kind="override_applied",
            )
            return
        if action == "replan":
            _warn_best_effort_emit_failure(
                "M3A_WARN_EMIT_OVERRIDE_REPLAN",
                action="override-replan",
                plan_dir=plan_dir,
                event_kind="override_applied",
            )
            return


def _normalize_override_response(action: str, response: StepResponse) -> StepResponse:
    normalized = dict(response)
    normalized.setdefault("override_action", action)
    route_signal = _route_signal_for_override_action(action)
    if route_signal is not None:
        normalized.setdefault("route_signal", route_signal)
    if not _override_response_owns_next_step(action):
        normalized.pop("next_step", None)
        normalized.pop("next_step_runtime", None)
    return normalized


def _handle_routed_override(
    root: Path,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
) -> StepResponse:
    if args.override_action == "replan":
        from arnold_pipelines.megaplan.planning.source_binding import (
            reconcile_canonical_source_for_replan,
        )

        reason = (
            getattr(args, "reason", None)
            or getattr(args, "note", None)
            or "Re-entering planning loop"
        )
        reconcile_canonical_source_for_replan(plan_dir, state, reason=reason)
        save_state_merge_meta(plan_dir, state)
    transition = ControlTransition(
        op="override",
        target_id=args.override_action,
        payload={
            "note": getattr(args, "note", None),
            "reason": getattr(args, "reason", None),
            "repair_commit": getattr(args, "repair_commit", None),
            "failure_fingerprint": getattr(args, "failure_fingerprint", None),
            "source": getattr(args, "source", None),
            "robustness": getattr(args, "robustness", None),
            "profile": getattr(args, "profile", None),
            "phase": getattr(args, "phase", None),
            "model": getattr(args, "model", None),
            "effort": getattr(args, "effort", None),
            "vendor": getattr(args, "vendor", None),
            "user_approved": getattr(args, "user_approved", False),
            "root": str(root),
            "plan_dir": str(plan_dir),
        },
    )
    run_state = RunStateView(
        run_id=state.get("name", plan_dir.name),
        cursor=state.get("current_state"),
        raw_state=state,
    )
    result = apply_transition(
        run_state,
        transition,
        "megaplan",
        plan_dir=plan_dir,
    )
    if not result.accepted:
        if result.reason == "control_transition_conflict":
            raise CliError(
                "invalid_transition",
                result.reason,
                extra={"conflict": result.artifacts.get("conflict")},
            )
        raise CliError("invalid_transition", result.reason or "routed override rejected")
    persisted_state = load_plan(root, args.plan)[1]
    _emit_routed_override_events(args.override_action, plan_dir=plan_dir, state=persisted_state, args=args)
    return _routed_override_response(
        args.override_action,
        plan_dir=plan_dir,
        state=persisted_state,
        args=args,
        artifacts=dict(result.artifacts),
    )


def _resolved_default_phase_spec(phase: str, state: PlanState, root: Path) -> str:
    """Return the concrete default routing spec for *phase*."""
    from arnold_pipelines.megaplan.profiles import effective_premium_vendor

    raw_spec = DEFAULT_AGENT_ROUTING.get(phase, "")
    if not raw_spec:
        return raw_spec
    project_dir = Path(state.get("config", {}).get("project_dir", str(root)))
    config = dict(state.get("config", {}))
    config.setdefault("project_dir", str(project_dir))
    resolved = resolve_premium_placeholder_spec(
        raw_spec,
        effective_premium_vendor(config=config),
    )
    return format_agent_spec(resolved)


def _resolved_default_phase_agent(phase: str, state: PlanState, root: Path) -> str:
    """Return the concrete default routing agent for *phase*."""
    default_spec = _resolved_default_phase_spec(phase, state, root)
    return parse_agent_spec(default_spec).agent if default_spec else ""


def _resolved_profile_phase_spec(phase: str, state: PlanState, root: Path) -> str:
    """Return the concrete expanded profile spec for *phase*, if any."""
    from arnold_pipelines.megaplan.profiles import apply_profile_expansion

    profile_name = state.get("config", {}).get("profile")
    if not profile_name:
        return ""

    project_dir = Path(state.get("config", {}).get("project_dir", str(root)))
    args = argparse.Namespace(
        profile=profile_name,
        phase_model=[],
        vendor=state.get("config", {}).get("vendor"),
        critic=state.get("config", {}).get("critic"),
        depth=state.get("config", {}).get("depth"),
        deepseek_provider=state.get("config", {}).get("deepseek_provider"),
        agent=None,
        hermes=None,
        _profile_applied=False,
    )
    try:
        apply_profile_expansion(args, project_dir, state=state)
    except Exception:
        return ""

    for pm in args.phase_model or []:
        if isinstance(pm, str) and "=" in pm:
            pm_phase, pm_spec = pm.split("=", 1)
            if pm_phase == phase:
                return pm_spec
    return ""


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
    save_state_merge_meta(plan_dir, state, preserve_disk_non_meta=True)
    next_steps = infer_next_steps(state)
    # Emit observability events
    try:
        from arnold_pipelines.megaplan.observability.events import emit, EventKind
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
        from arnold_pipelines.megaplan.observability.events import emit, EventKind
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
        "state": STATE_ABORTED,
    }


def _execution_adoption_summary(plan_dir: Path) -> dict[str, Any]:
    execution_path = plan_dir / "execution.json"
    finalize_path = plan_dir / "finalize.json"
    if not execution_path.exists():
        raise CliError(
            "incomplete_execution_artifact",
            "adopt-execution requires execution.json to exist",
            extra={"missing": ["execution.json"]},
        )
    if not finalize_path.exists():
        raise CliError(
            "incomplete_execution_artifact",
            "adopt-execution requires finalize.json to exist",
            extra={"missing": ["finalize.json"]},
        )

    execution = read_json(execution_path)
    finalize = read_json(finalize_path)
    if not isinstance(execution, dict) or not isinstance(finalize, dict):
        raise CliError(
            "incomplete_execution_artifact",
            "adopt-execution requires object execution.json and finalize.json payloads",
        )

    finalize_tasks = [task for task in finalize.get("tasks", []) if isinstance(task, dict)]
    task_ids = {
        str(task.get("id"))
        for task in finalize_tasks
        if isinstance(task.get("id"), str) and task.get("id")
    }
    updates = [
        update
        for update in execution.get("task_updates", [])
        if isinstance(update, dict)
    ]
    updates_by_id: dict[str, dict[str, Any]] = {}
    blocked_task_ids: set[str] = set()
    for update in updates:
        task_id = update.get("task_id") or update.get("id")
        if not isinstance(task_id, str) or not task_id:
            continue
        updates_by_id[task_id] = update
        if update.get("status") == "blocked":
            blocked_task_ids.add(task_id)

    missing_task_updates = sorted(task_ids - set(updates_by_id))
    incomplete_task_updates = sorted(
        task_id
        for task_id in task_ids & set(updates_by_id)
        if updates_by_id[task_id].get("status") != "done"
    )
    incomplete_finalize_tasks = sorted(
        str(task.get("id"))
        for task in finalize_tasks
        if isinstance(task.get("id"), str) and task.get("status") != "done"
    )
    blocked_task_ids.update(
        str(task.get("id"))
        for task in finalize_tasks
        if isinstance(task.get("id"), str) and task.get("status") == "blocked"
    )

    finalize_checks = [
        check for check in finalize.get("sense_checks", []) if isinstance(check, dict)
    ]
    sense_check_ids = {
        str(check.get("id"))
        for check in finalize_checks
        if isinstance(check.get("id"), str) and check.get("id")
    }
    ack_ids: set[str] = set()
    for ack in execution.get("sense_check_acknowledgments", []):
        if not isinstance(ack, dict):
            continue
        check_id = ack.get("sense_check_id") or ack.get("id")
        if isinstance(check_id, str) and check_id:
            ack_ids.add(check_id)
    missing_sense_check_acknowledgments = sorted(sense_check_ids - ack_ids)

    failures = {
        "missing_task_updates": missing_task_updates,
        "incomplete_task_updates": incomplete_task_updates,
        "incomplete_finalize_tasks": incomplete_finalize_tasks,
        "blocked_task_ids": sorted(blocked_task_ids),
        "missing_sense_check_acknowledgments": missing_sense_check_acknowledgments,
    }
    failures = {key: value for key, value in failures.items() if value}
    if failures:
        raise CliError(
            "incomplete_execution_artifact",
            "adopt-execution refused because execution.json is not complete",
            extra=failures,
        )

    return {
        "task_count": len(task_ids),
        "sense_check_count": len(sense_check_ids),
        "execution_hash": sha256_file(execution_path),
        "finalize_hash": sha256_file(finalize_path),
    }


def _override_adopt_execution(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    previous_state = state["current_state"]
    summary = _execution_adoption_summary(plan_dir)
    reason = args.reason or "Adopted complete execution artifact after post-worker recovery."
    timestamp = now_utc()

    state["current_state"] = STATE_EXECUTED
    state.pop("resume_cursor", None)
    state.pop("active_step", None)
    adoption_record = {
        "action": "adopt-execution",
        "timestamp": timestamp,
        "reason": reason,
        "from_state": previous_state,
        "to_state": STATE_EXECUTED,
        **summary,
    }
    _append_to_meta(state, "overrides", adoption_record)
    append_history(
        state,
        {
            "step": "execute",
            "timestamp": timestamp,
            "duration_ms": 0,
            "cost_usd": 0.0,
            "result": "success",
            "output_file": "execution.json",
            "artifact_hash": summary["execution_hash"],
            "finalize_hash": summary["finalize_hash"],
            "message": f"adopted complete execution artifact via override: {reason}",
        },
    )
    save_state_merge_meta(plan_dir, state)

    existing_phase_result = read_phase_result(plan_dir)
    invocation_id = (
        existing_phase_result.invocation_id
        if existing_phase_result is not None and existing_phase_result.phase == "execute"
        else f"adopt-execution:{timestamp}"
    )
    artifacts = ["execution.json", "finalize.json"]
    for optional_name in ("execution_audit.json", "final.md"):
        if (plan_dir / optional_name).exists():
            artifacts.append(optional_name)
    atomic_write_phase_result(
        plan_dir,
        PhaseResult(
            phase="execute",
            invocation_id=invocation_id,
            exit_kind=ExitKind.success.value,
            artifacts_written=tuple(artifacts),
            cli_provenance={
                "command": "override adopt-execution",
                "reason": reason,
                "previous_state": previous_state,
                "adopted": True,
                **summary,
            },
        ),
    )

    response: StepResponse = {
        "success": True,
        "step": "override",
        "action": "adopt-execution",
        "summary": (
            "Adopted complete execution.json and promoted plan state to executed "
            f"({summary['task_count']} tasks, {summary['sense_check_count']} sense checks)."
        ),
        "state": STATE_EXECUTED,
        "previous_state": previous_state,
    }
    return response


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
            "state": STATE_DONE,
        }
    if state["current_state"] == STATE_BLOCKED:
        if not (
            _last_gate_is_agent_availability_preflight_block(state)
            or _blocked_plan_has_operational_unverifiable_evidence(plan_dir, state)
            or getattr(args, "user_approved", False)
        ):
            raise CliError(
                "invalid_transition",
                "force-proceed from blocked is only supported for recoverable gate blocks (pass --user-approved to override)",
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
            "settled_decisions": [],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
            "north_star_actions": [],
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
        from arnold_pipelines.megaplan.observability.events import emit, EventKind
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
        "state": STATE_GATED,
        "orchestrator_guidance": gate["orchestrator_guidance"],
        "debt_entries_added": len(unresolved_flags),
    }
    return response


def _override_replan(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    allowed = {STATE_GATED, STATE_FINALIZED, STATE_CRITIQUED, STATE_FAILED}
    previous_state = state["current_state"]
    if previous_state not in allowed:
        raise CliError(
            "invalid_transition",
            f"replan requires state {', '.join(sorted(allowed))}, got '{previous_state}'",
            valid_next=infer_next_steps(state),
        )
    reason = args.reason or args.note or "Re-entering planning loop"
    plan_file = latest_plan_path(plan_dir, state)
    timestamp = now_utc()
    _append_to_meta(
        state,
        "overrides",
        {
            "action": "replan",
            "timestamp": timestamp,
            "reason": reason,
            "from_state": previous_state,
            "plan_file": plan_file.name,
        },
    )
    if args.note:
        _append_to_meta(state, "notes", {"timestamp": timestamp, "note": args.note})
    from arnold_pipelines.megaplan.planning.source_binding import (
        reconcile_canonical_source_for_replan,
    )

    source_reconciliation = reconcile_canonical_source_for_replan(
        plan_dir,
        state,
        reason=reason,
    )
    reset_replan_loop_state(state, target_state=STATE_PLANNED)
    save_state_merge_meta(plan_dir, state)
    try:
        from arnold_pipelines.megaplan.observability.events import emit, EventKind
        emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "replan", "reason": reason})
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_EMIT_OVERRIDE_REPLAN",
            action="override-replan",
            plan_dir=plan_dir,
            event_kind="override_applied",
        )
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": f"Re-entered planning loop at iteration {state['iteration']}. Reason: {reason}",
        "state": STATE_PLANNED,
        "plan_file": str(plan_file),
        "message": f"Edit {plan_file.name} to incorporate your changes, then run the next step.",
    }
    if source_reconciliation is not None:
        response["canonical_source_binding"] = source_reconciliation
    return response


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


def _last_gate_is_operational_unverifiable_block(state: PlanState) -> bool:
    last_gate = state.get("last_gate")
    if not isinstance(last_gate, dict):
        return False
    if last_gate.get("recommendation") != "ITERATE" or last_gate.get("passed") is not False:
        return False

    signals = last_gate.get("signals")
    if not isinstance(signals, dict):
        history = state.get("meta", {}).get("critique_unverifiable_checks", [])
        if isinstance(history, list) and history:
            latest = history[-1]
            if isinstance(latest, dict):
                signals = {"unverifiable_checks": latest.get("checks", [])}
    if not isinstance(signals, dict):
        return False

    checks = signals.get("unverifiable_checks", [])
    if not isinstance(checks, list):
        return False
    high_complexity = [
        check
        for check in checks
        if isinstance(check, dict)
        and check.get("attention") == "high_complexity_unverifiable"
    ]
    return bool(high_complexity) and (
        not has_high_complexity_unverifiable_checks(signals)
        and all(is_operational_unverifiable_check(check) for check in high_complexity)
    )


def _blocked_plan_has_operational_unverifiable_evidence(
    plan_dir: Path, state: PlanState
) -> bool:
    if _last_gate_is_operational_unverifiable_block(state):
        return True

    history = state.get("meta", {}).get("critique_unverifiable_checks", [])
    if not isinstance(history, list) or not history:
        return False
    latest = history[-1]
    if not isinstance(latest, dict):
        return False
    checks = latest.get("checks", [])
    if not isinstance(checks, list):
        return False

    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("attention") != "high_complexity_unverifiable":
            continue
        check_id = str(check.get("id", "")).strip()
        if not check_id:
            continue
        raw_path = plan_dir / f"critique_check_{check_id}_raw.txt"
        if not raw_path.exists():
            continue
        try:
            raw_text = raw_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if is_operational_unverifiable_check({"reason": raw_text}):
            return True
    return False


def _override_recover_blocked(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    latest_failure = state.get("latest_failure")
    aborted_with_blocked_failure = (
        state["current_state"] == STATE_ABORTED
        and isinstance(latest_failure, dict)
        and latest_failure.get("state") == STATE_BLOCKED
    )
    if state["current_state"] != STATE_BLOCKED and not aborted_with_blocked_failure:
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
    recovered_state = _topology.predecessors(phase, policy="recovery")
    if recovered_state is None:
        raise CliError(
            "invalid_resume_cursor",
            f"recover-blocked does not know how to resume phase {phase!r}",
            extra={"resume_cursor": resume_cursor},
        )
    if isinstance(latest_failure, dict) and latest_failure.get("kind") == "authority_divergence":
        plan_name = state.get("name") or getattr(args, "plan", None) or plan_dir.name
        rerun_command = f"megaplan {phase} --plan {plan_name}"
        if phase == "execute":
            rerun_command += " --confirm-destructive --user-approved"
        raise CliError(
            "rerun_phase_required",
            (
                "recover-blocked is only for explicit task or quality blockers. "
                "This blocked plan needs a fresh phase rerun to regenerate "
                "authority evidence; do not use recover-blocked here."
            ),
            extra={
                "resume_cursor": resume_cursor,
                "latest_failure": dict(latest_failure),
                "rerun_command": rerun_command,
                "suggested_recovery_commands": [rerun_command],
            },
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
    phase_repair_evidence: dict[str, str] | None = None
    if phase_result is None:
        phase_repair_evidence = validated_deterministic_phase_repair(
            root,
            state,
            resume_cursor,
            getattr(args, "repair_commit", None),
            getattr(args, "failure_fingerprint", None),
        )
        if phase_repair_evidence is None:
            raise CliError(
                "missing_phase_result",
                "recover-blocked requires phase_result.json with current blocker details",
                extra={"resume_cursor": resume_cursor},
            )
        blocker_details: list[dict[str, Any]] = []
        blocker_ids: list[str] = []
    else:
        evaluation = evaluate_blocker_recovery(
            finalize_data,
            state,
            plan_dir=plan_dir,
            blocked_tasks=phase_result.blocked_tasks,
            deviations=phase_result.deviations,
        )
        blocker_details = command_blocker_details(evaluation)
        blocker_ids = [blocker.blocker_id for blocker in evaluation.blockers]
    if phase_result is not None and not evaluation.can_continue:
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
    archived_phase_result = _archive_stale_phase_result_for_resume(plan_dir)
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
            "blocker_ids": blocker_ids,
            "archived_phase_result": archived_phase_result,
            **(
                {"phase_contract_repair": phase_repair_evidence}
                if phase_repair_evidence is not None
                else {}
            ),
        },
    )
    save_state_merge_meta(plan_dir, state)
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
        "resume_cursor": resume_cursor,
        "blockers": blocker_details,
    }
    if phase_repair_evidence is not None:
        response["phase_contract_repair"] = phase_repair_evidence
    if archived_phase_result is not None:
        response["archived_phase_result"] = archived_phase_result
    return response


def _override_set_robustness(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    from arnold_pipelines.megaplan.profiles import ROBUSTNESS_ACCEPTED, normalize_robustness

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
        from arnold_pipelines.megaplan.observability.events import emit, EventKind
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
    from arnold_pipelines.megaplan.profiles import (
        _canonicalize_tier_models_for_json,
        _resolve_prep_models_with_inheritance,
        _resolve_tier_models_with_inheritance,
        _prep_flat_spec_from_profile,
        apply_depth_rewrite,
        apply_vendor_rewrite,
        load_profile_metadata,
        load_profiles,
        resolve_prep_models,
        resolve_profile,
        profile_to_phase_models,
    )
    from arnold_pipelines.megaplan.profiles.policy import _profile_has_premium_slots

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
    metadata = load_profile_metadata(project_dir=project_dir)
    resolved = resolve_profile(new_profile, profiles)
    try:
        tier_models = _resolve_tier_models_with_inheritance(
            new_profile,
            system_profiles=profiles,
            system_metadata=metadata,
            pipeline_local_profiles={},
            pipeline_local_metadata={},
        )
    except CliError:
        tier_models = {}
    try:
        inherited_prep_models = _resolve_prep_models_with_inheritance(
            new_profile,
            system_profiles=profiles,
            system_metadata=metadata,
            pipeline_local_profiles={},
            pipeline_local_metadata={},
        )
    except CliError:
        inherited_prep_models = {}
    vendor = effective_premium_vendor(config=state.get("config", {}))
    if _profile_has_premium_slots(resolved) or inherited_prep_models:
        resolved = apply_vendor_rewrite(
            resolved,
            vendor,
            prep_models=inherited_prep_models,
        )
    depth = state["config"].get("depth")
    if depth is not None:
        resolved = apply_depth_rewrite(resolved, depth)
    phase_models = profile_to_phase_models(resolved)
    prep_models, prep_trace = resolve_prep_models(
        flat_prep_spec=_prep_flat_spec_from_profile(resolved),
        prep_models=inherited_prep_models,
    )

    previous_profile = state["config"].get("profile")
    state["config"]["profile"] = new_profile
    state["config"]["phase_model"] = phase_models
    if _profile_has_premium_slots(resolved):
        state["config"]["vendor"] = vendor
    else:
        state["config"].pop("vendor", None)
    if tier_models:
        state["config"]["tier_models"] = _canonicalize_tier_models_for_json(tier_models)
    else:
        state["config"].pop("tier_models", None)
    if prep_models:
        state["config"]["prep_models"] = prep_models
        state["config"]["prep_model_resolver_trace"] = prep_trace
    else:
        state["config"].pop("prep_models", None)
        state["config"].pop("prep_model_resolver_trace", None)
    exec_spec = next(
        (phase_model.split("=", 1)[1] for phase_model in phase_models if phase_model.startswith("execute=")),
        "",
    )
    if exec_spec:
        _phase, exec_chain = decode_phase_model_value(f"execute={exec_spec}")
        exec_spec = exec_chain.selected()
    exec_spec = exec_spec.lower()
    exec_family = None
    if exec_spec.startswith("claude"):
        exec_family = "claude"
    elif exec_spec.startswith("codex") or "gpt-5" in exec_spec:
        exec_family = "codex"
    if exec_family is not None and state["config"].get("vendor") != exec_family:
        state["config"]["vendor"] = exec_family
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
        from arnold_pipelines.megaplan.observability.events import emit, EventKind
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
    if model_arg in _PREMIUM_VENDORS:
        raise CliError(
            "invalid_args",
            f"override set-model --model {model_arg!r} names an agent, not a model. "
            f"Use `override set-vendor --vendor {model_arg}` to switch vendors, "
            "or pass an actual model name/spec.",
        )

    # Validate known phase names
    if phase not in DEFAULT_AGENT_ROUTING:
        raise CliError(
            "invalid_args",
            f"Unknown phase '{phase}'. Valid phases: {', '.join(sorted(DEFAULT_AGENT_ROUTING))}",
        )

    # Infer the target agent for this phase
    # Priority: (1) persisted phase_model entry, (2) active profile, (3) DEFAULT_AGENT_ROUTING
    current_phase_spec = _current_phase_spec(phase, state, root)
    agent = parse_agent_spec(current_phase_spec).agent

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
        # Bare model strings normally keep the phase's current premium vendor.
        # If the current phase is non-premium, allow an unambiguous vendor-prefixed
        # premium model name to move the phase onto that vendor.
        inferred_agent = None
        if str(model_arg).startswith("claude-"):
            inferred_agent = "claude"
        elif str(model_arg).startswith(("gpt-", "o1", "o3", "o4")):
            inferred_agent = "codex"
        if agent == "shannon":
            inferred_agent = None
        if agent not in _PREMIUM_VENDORS and inferred_agent is None:
            raise CliError(
                "invalid_args",
                f"set-model is only supported for claude/codex phases. "
                f"Phase '{phase}' resolves to agent '{agent}'.",
            )
        target_agent = inferred_agent or agent
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
        previous_spec = current_phase_spec
        phase_models.append(f"{phase}={new_spec}")

    state["config"]["phase_model"] = phase_models
    tier_models = state["config"].get("tier_models")
    if isinstance(tier_models, dict) and phase in tier_models:
        next_tier_models = dict(tier_models)
        next_tier_models.pop(phase, None)
        state["config"]["tier_models"] = next_tier_models

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
            pm_phase, chain = decode_phase_model_value(pm)
            if pm_phase == phase:
                return _resolve_symbolic_phase_spec(chain.selected(), state)
    profile_name = state.get("config", {}).get("profile")
    if profile_name:
        try:
            from arnold_pipelines.megaplan.profiles import load_profiles, resolve_profile

            project_dir = Path(state["config"].get("project_dir", str(root)))
            profiles = load_profiles(project_dir=project_dir)
            resolved = resolve_profile(profile_name, profiles)
            if phase in resolved:
                resolved_spec = resolved[phase]
                if isinstance(resolved_spec, list):
                    resolved_spec = select_fallback_spec(resolved_spec, 0, path=f"profile.{phase}")
                return _resolve_symbolic_phase_spec(resolved_spec, state)
        except Exception:
            pass
    return _resolve_symbolic_phase_spec(DEFAULT_AGENT_ROUTING.get(phase, ""), state)


def _resolve_symbolic_phase_spec(spec: str, state: PlanState) -> str:
    if not spec or not is_premium_placeholder_spec(spec):
        return spec
    vendor = effective_premium_vendor(config=state.get("config", {}))
    return format_agent_spec(resolve_premium_placeholder_spec(spec, vendor))


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

    from arnold_pipelines.megaplan.profiles import _swap_premium_spec
    from arnold_pipelines.megaplan._core.user_config import VALID_VENDORS

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
        previous_spec = current_spec or _resolved_default_phase_spec(phase, state, root)
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
            pm_phase, chain = decode_phase_model_value(pm)
            if pm_phase == phase:
                parsed = parse_agent_spec(chain.selected())
                return parsed.agent

    # Check active profile
    profile_name = state.get("config", {}).get("profile")
    if profile_name:
        try:
            from arnold_pipelines.megaplan.profiles import load_profiles, resolve_profile
            project_dir = Path(state["config"].get("project_dir", str(root)))
            profiles = load_profiles(project_dir=project_dir)
            resolved = resolve_profile(profile_name, profiles)
            if phase in resolved:
                resolved_spec = resolved[phase]
                if isinstance(resolved_spec, list):
                    resolved_spec = select_fallback_spec(resolved_spec, 0, path=f"profile.{phase}")
                parsed = parse_agent_spec(_resolve_symbolic_phase_spec(resolved_spec, state))
                return parsed.agent
        except Exception:
            pass

    # Fall back to DEFAULT_AGENT_ROUTING
    default = DEFAULT_AGENT_ROUTING.get(phase)
    if default is None:
        return None
    return parse_agent_spec(_resolve_symbolic_phase_spec(default, state)).agent


def _override_resume_clarify(
    root: Path, plan_dir: Path, state: PlanState, args: argparse.Namespace
) -> StepResponse:
    clarification = state.get("clarification")
    has_prep_clarification = (
        isinstance(clarification, dict)
        and clarification.get("source") == "prep"
    )
    if state["current_state"] not in {STATE_AWAITING_HUMAN, STATE_BLOCKED}:
        raise CliError(
            "invalid_transition",
            f"resume-clarify requires state '{STATE_AWAITING_HUMAN}', got '{state['current_state']}'",
            valid_next=infer_next_steps(state),
        )
    if not has_prep_clarification:
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
    state.pop("clarification", None)
    _append_to_meta(
        state,
        "overrides",
        {"action": "resume-clarify", "timestamp": now_utc()},
    )
    save_state_merge_meta(plan_dir, state)
    try:
        from arnold_pipelines.megaplan.observability.events import emit, EventKind
        emit(EventKind.OVERRIDE_APPLIED, plan_dir=plan_dir, payload={"action": "resume-clarify"})
    except Exception:
        pass
    response: StepResponse = {
        "success": True,
        "step": "override",
        "summary": "Prep clarification resolved; plan phase is now ready to run.",
        "state": STATE_PREPPED,
    }
    if warnings:
        response["warnings"] = warnings
    return response


_OVERRIDE_ACTIONS: dict[
    str, Callable[[Path, Path, PlanState, argparse.Namespace], StepResponse]
] = {
    "add-note": _override_add_note,
    "abort": _override_abort,
    "adopt-execution": _override_adopt_execution,
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
    if action in {"adopt-execution"}:
        pass
    elif action in {"force-proceed", "recover-blocked", "resume-clarify"}:
        preflight_mutating_phase(root=root, state=state, phase=f"override:{action}")
    else:
        preflight_phase(root=root, state=state, phase=f"override:{action}")
    save_state_merge_meta(plan_dir, state)
    if control_interface_routing_on() and action in _control_routed_override_actions():
        return _handle_routed_override(root, plan_dir, state, args)
    handler = _OVERRIDE_ACTIONS.get(action)
    if handler is None:
        raise CliError("invalid_override", f"Unknown override action: {action}")
    response = _normalize_override_response(action, handler(root, plan_dir, state, args))
    emit_override_authority_receipt(plan_dir, state, action)
    return response
