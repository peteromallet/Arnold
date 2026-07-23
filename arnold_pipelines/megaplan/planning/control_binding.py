"""Planning-owned binding hooks for the shared control interface.

M9 status: This module is a positive-control-path consumer.  It is not
cut over to the shared SourceCursorVector / WBC adapter seam in M9 (which
operates in shadow/view-only mode).  Every control-path decision made here
MUST reread live Run Authority grant/fence, Custody lease/epoch, and WBC
evidence before any positive dispatch.  Full cutover is deferred to M10.

Compatibility row: control_binding.py – non-authoritative in M9, expiry
gated by M10 control-path migration readiness.
"""

from __future__ import annotations

# M9: _non_authoritative marker at module level
# This module's control-path decisions are not yet backed by the shared
# SourceCursorVector contract.  Consumers must treat output as orientation
# only until M10 integrates the reread obligations.
_m9_non_authoritative = True

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import topology
from arnold_pipelines.megaplan._core.workflow import workflow_next
from arnold_pipelines.megaplan._core import (
    add_or_increment_debt,
    atomic_write_json,
    extract_subsystem_tag,
    find_command,
    load_debt_registry,
    load_flag_registry,
    latest_plan_path,
    now_utc,
    read_json,
    save_debt_registry,
    sha256_file,
    unresolved_significant_flags,
)
from arnold_pipelines.megaplan.state_delta import StateDelta
from arnold.control.interface import (
    CONTROL_TARGET_ABORT,
    CONTROL_TARGET_FORCE_ADVANCE,
    CONTROL_TARGET_RECOVER_FROM_STUCK,
    CONTROL_TARGET_REROUTE,
    ControlTargetRef,
    ControlTransition,
    ControlTransitionRequest,
    ControlTransitionResult,
    RunStateView,
)
from arnold.runtime.outcome import RunOutcome
from arnold_pipelines.megaplan.profiles import effective_premium_vendor
from arnold_pipelines.megaplan.profiles.policy import (
    DEFAULT_AGENT_ROUTING,
    ROBUSTNESS_ACCEPTED,
    _profile_has_premium_slots,
    _prep_flat_spec_from_profile,
    normalize_robustness,
    resolve_prep_models,
)
from arnold_pipelines.megaplan.replan_state import (
    REPLAN_STATE_KEYS_TO_CLEAR,
    reset_replan_loop_state,
)
from arnold_pipelines.megaplan.fallback_chains import decode_phase_model_value, select_fallback_spec
from arnold_pipelines.megaplan.types import (
    AgentSpec,
    CliError,
    _PREMIUM_EFFORT_TOKENS,
    _PREMIUM_VENDORS,
    format_agent_spec,
    is_premium_placeholder_spec,
    parse_agent_spec,
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
from arnold_pipelines.megaplan.orchestration.gate_checks import (
    build_gate_artifact,
    failed_preflight_checks,
    only_agent_availability_preflight_failed,
    run_gate_checks,
)
from arnold_pipelines.megaplan.orchestration.gate_signals import build_gate_signals
from arnold_pipelines.megaplan.blocker_recovery import (
    command_blocker_details,
    evaluate_blocker_recovery,
    recoverable_contract_failure_without_phase_result,
)
from arnold_pipelines.megaplan.control_interface import declared_override_policy_target
from arnold_pipelines.megaplan.orchestration.phase_result import read_phase_result


def _write_gate_json(plan_dir: Path, payload: dict[str, Any]) -> str:
    atomic_write_json(plan_dir / "gate.json", payload, _plan_dir=plan_dir)
    return sha256_file(plan_dir / "gate.json")


def _coerce_plan_state(raw_state: Mapping[str, object]) -> dict[str, object] | None:
    current_state = raw_state.get("current_state")
    config = raw_state.get("config")
    if not isinstance(current_state, str):
        return None
    state = dict(raw_state)
    if isinstance(config, dict):
        return state
    synthesized_config: dict[str, object] = {}
    for key in ("robustness", "mode", "profile_name", "creative", "with_feedback", "form"):
        value = raw_state.get(key)
        if value is not None:
            synthesized_config[key] = value
    if not synthesized_config:
        return None
    state["config"] = synthesized_config
    return state


def _project_run_outcome(state: Mapping[str, object]) -> RunOutcome | None:
    current_state = state.get("current_state")
    if not isinstance(current_state, str):
        return None
    if current_state == STATE_DONE:
        return RunOutcome.SUCCEEDED
    if current_state in {STATE_FAILED, STATE_ABORTED}:
        return RunOutcome.FAILED
    if current_state == STATE_BLOCKED:
        return RunOutcome.BLOCKED
    if current_state in {STATE_AWAITING_HUMAN, "clarifying"}:
        return RunOutcome.AWAITING_HUMAN
    return None


def planning_run_state_view(
    raw_state: Mapping[str, object],
    *,
    run_id: str | None = None,
    projection_surface: str = "legacy",
) -> RunStateView:
    state = _coerce_plan_state(raw_state) or dict(raw_state)
    resolved_run_id = run_id
    if resolved_run_id is None:
        name = state.get("name")
        resolved_run_id = name if isinstance(name, str) and name else "planning-run"
    outcome = _project_run_outcome(state)
    blocking_reason = None
    if outcome == RunOutcome.BLOCKED and state.get("current_state") == STATE_BLOCKED:
        latest_failure = state.get("latest_failure")
        if isinstance(latest_failure, Mapping):
            kind = latest_failure.get("kind")
            if isinstance(kind, str) and kind:
                blocking_reason = kind
    return RunStateView(
        run_id=resolved_run_id,
        outcome=outcome,
        cursor=state.get("current_state") if isinstance(state.get("current_state"), str) else None,
        metadata={
            "planning_state": state.get("current_state"),
            "blocking_reason": blocking_reason,
            "projection_surface": projection_surface,
        },
        raw_state=state,
    )


def planning_supervisor_run_state_view(
    raw_state: Mapping[str, object],
    *,
    run_id: str | None = None,
) -> RunStateView:
    """Build a planning run-state view for neutral supervisor-facing projections."""

    return planning_run_state_view(
        raw_state,
        run_id=run_id,
        projection_surface="supervisor",
    )


def _diagnostic(code: str, message: str, **metadata: object) -> ControlTargetRef:
    return ControlTargetRef(
        id=f"diagnostic:{code}",
        label=message,
        metadata={
            "kind": "diagnostic",
            "code": code,
            "message": message,
            "actionable": False,
            **metadata,
        },
    )


def _workflow_step_target(
    step: str,
    *,
    direction: str,
    target_state: str | None = None,
    source: str | None = None,
    operator_action: str | None = None,
) -> ControlTargetRef:
    metadata: dict[str, object] = {
        "kind": "workflow_step",
        "step": step,
        "direction": direction,
        "actionable": True,
    }
    if target_state is not None:
        metadata["target_state"] = target_state
    if source is not None:
        metadata["source"] = source
    if operator_action is not None:
        metadata["operator_action"] = operator_action
    return ControlTargetRef(id=step, label=step, metadata=metadata)


def _neutral_target(
    target_id: str,
    *,
    source_state: str,
    direction: str,
) -> ControlTargetRef:
    return ControlTargetRef(
        id=target_id,
        label=target_id,
        metadata={
            "kind": "control_target",
            "direction": direction,
            "actionable": True,
            "source_state": source_state,
            "surface": "supervisor",
        },
    )


def _string_from_path(raw_state: Mapping[str, object], path: tuple[str, ...]) -> str | None:
    value: object = raw_state
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value if isinstance(value, str) and value else None


def _recovery_phase(state: Mapping[str, object]) -> tuple[str | None, str | None]:
    helper_phases = {"recover-blocked", "resume-clarify", "status", "step"}
    candidates = (
        ("resume_cursor", "phase"),
        ("active_step", "name"),
        ("active_step", "phase"),
        ("active_step", "step"),
        ("phase_result", "phase"),
        ("latest_failure", "metadata", "phase_result", "phase"),
        ("latest_failure", "metadata", "phase"),
        ("latest_failure", "phase"),
    )
    for path in candidates:
        phase = _string_from_path(state, path)
        if phase is not None:
            if phase in helper_phases:
                continue
            return phase, ".".join(path)
    return None, None


def _blocked_phase_rerun_target(
    state: Mapping[str, object],
    *,
    phase: str,
    source: str | None,
) -> ControlTargetRef | None:
    blocked_rerunnable_phases = {"execute"}
    latest_failure = state.get("latest_failure")
    if not isinstance(latest_failure, Mapping):
        return None
    failure_kind = latest_failure.get("kind")
    stale_recover_blocked_failure = (
        failure_kind == "blocked_recovery_not_resolved"
        and _string_from_path(state, ("latest_failure", "phase")) == "recover-blocked"
        and source in {"resume_cursor.phase", "phase_result.phase"}
    )
    rerun_from_stale_recovery_helper = (
        failure_kind == "iteration_cap" and source == "phase_result.phase"
    )
    if (
        failure_kind != "authority_divergence"
        and not rerun_from_stale_recovery_helper
        and not stale_recover_blocked_failure
    ):
        return None
    if phase not in blocked_rerunnable_phases:
        return None
    return _workflow_step_target(
        phase,
        direction="recovery",
        source=source,
    )


def _awaiting_human_target(state: Mapping[str, object]) -> ControlTargetRef:
    clarification = state.get("clarification")
    source = clarification.get("source") if isinstance(clarification, Mapping) else None
    if source == "prep":
        return declared_override_policy_target(
            "resume-clarify",
            direction="operator",
            source="awaiting_human",
            target_state="prepped",
            operator_action="resume-clarify",
        )
    return _workflow_step_target(
        "verify-human",
        direction="operator",
        target_state="awaiting_human_verify",
        source="awaiting_human",
        operator_action="verify-human",
    )


def _has_prep_clarification(state: Mapping[str, object]) -> bool:
    clarification = state.get("clarification")
    return (
        isinstance(clarification, Mapping)
        and clarification.get("source") == "prep"
    )


def _state_version(state: Mapping[str, object], key: str) -> int:
    meta = state.get("_state_meta")
    if not isinstance(meta, Mapping):
        return 0
    versions = meta.get("versions")
    if not isinstance(versions, Mapping):
        return 0
    value = versions.get(key)
    return value if isinstance(value, int) else 0


def _meta_delta(state: Mapping[str, object], value: Mapping[str, Any], *, version_offset: int = 0) -> StateDelta:
    return StateDelta(
        op="accumulate",
        key="meta",
        value=value,
        version=_state_version(state, "meta") + version_offset,
    )


def _replace_delta(state: Mapping[str, object], key: str, value: object) -> StateDelta:
    return StateDelta(
        op="replace",
        key=key,
        value=value,
        version=_state_version(state, key),
    )


def _next_meta(
    state: Mapping[str, object],
    *,
    note_entry: Mapping[str, Any] | None = None,
    override_entry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current_meta = state.get("meta")
    meta = dict(current_meta) if isinstance(current_meta, Mapping) else {}
    if note_entry is not None:
        notes = list(meta.get("notes", []))
        notes.append(dict(note_entry))
        meta["notes"] = notes
    if override_entry is not None:
        overrides = list(meta.get("overrides", []))
        overrides.append(dict(override_entry))
        meta["overrides"] = overrides
    return meta


def _project_dir(state: Mapping[str, object]) -> Path:
    config = state.get("config")
    if isinstance(config, Mapping):
        raw = config.get("project_dir")
        if isinstance(raw, str) and raw:
            return Path(raw)
    return Path.cwd()


def _plan_dir(state: Mapping[str, object], transition: ControlTransition) -> Path:
    raw = transition.payload.get("plan_dir")
    if isinstance(raw, str) and raw:
        return Path(raw)
    metadata = state.get("metadata")
    if isinstance(metadata, Mapping):
        raw_meta = metadata.get("plan_dir")
        if isinstance(raw_meta, str) and raw_meta:
            return Path(raw_meta)
    return _project_dir(state)


def _root_dir(state: Mapping[str, object], transition: ControlTransition) -> Path:
    raw = transition.payload.get("root")
    if isinstance(raw, str) and raw:
        return Path(raw)
    return _project_dir(state)


_NEUTRAL_TO_INTERNAL_ACTIONS = {
    CONTROL_TARGET_FORCE_ADVANCE: "force-proceed",
    CONTROL_TARGET_REROUTE: "replan",
    CONTROL_TARGET_RECOVER_FROM_STUCK: "recover-blocked",
    CONTROL_TARGET_ABORT: "abort",
}


def _projection_surface(run_state: RunStateView) -> str:
    surface = run_state.metadata.get("projection_surface")
    return surface if isinstance(surface, str) and surface else "legacy"


def _supervisor_forward_targets(state: Mapping[str, object]) -> tuple[ControlTargetRef, ...]:
    current_state = state.get("current_state")
    if not isinstance(current_state, str):
        return ()
    if current_state == STATE_CRITIQUED:
        return (
            _neutral_target(
                CONTROL_TARGET_FORCE_ADVANCE,
                source_state=current_state,
                direction="forward",
            ),
            _neutral_target(
                CONTROL_TARGET_REROUTE,
                source_state=current_state,
                direction="forward",
            ),
            _neutral_target(
                CONTROL_TARGET_ABORT,
                source_state=current_state,
                direction="forward",
            ),
        )
    if current_state in {STATE_GATED, STATE_FINALIZED, STATE_FAILED}:
        return (
            _neutral_target(
                CONTROL_TARGET_REROUTE,
                source_state=current_state,
                direction="forward",
            ),
            _neutral_target(
                CONTROL_TARGET_ABORT,
                source_state=current_state,
                direction="forward",
            ),
        )
    if current_state == STATE_BLOCKED:
        targets = [
            _neutral_target(
                CONTROL_TARGET_RECOVER_FROM_STUCK,
                source_state=current_state,
                direction="recovery",
            ),
            _neutral_target(
                CONTROL_TARGET_ABORT,
                source_state=current_state,
                direction="forward",
            ),
        ]
        if _last_gate_is_agent_availability_preflight_block(state):
            targets.insert(
                1,
                _neutral_target(
                    CONTROL_TARGET_FORCE_ADVANCE,
                    source_state=current_state,
                    direction="forward",
                ),
            )
        return tuple(targets)
    return ()


def _supervisor_recover_targets(state: Mapping[str, object]) -> tuple[ControlTargetRef, ...]:
    current_state = state.get("current_state")
    if current_state == STATE_BLOCKED:
        return (
            _neutral_target(
                CONTROL_TARGET_RECOVER_FROM_STUCK,
                source_state=current_state,
                direction="recovery",
            ),
        )
    if current_state == STATE_FAILED:
        return (
            _neutral_target(
                CONTROL_TARGET_REROUTE,
                source_state=current_state,
                direction="recovery",
            ),
        )
    return ()


def _normalize_transition_action(
    transition: ControlTransition | ControlTransitionRequest,
) -> tuple[str | None, ControlTransition | ControlTransitionRequest]:
    action = transition.target_id
    if action is None:
        request_action = getattr(transition, "action", None)
        if isinstance(request_action, str) and request_action:
            action = request_action
    normalized_action = _NEUTRAL_TO_INTERNAL_ACTIONS.get(action, action)
    if normalized_action == action:
        return action, transition

    if isinstance(transition, ControlTransitionRequest):
        return normalized_action, ControlTransitionRequest(
            action=transition.action,
            target_id=normalized_action,
            params=dict(transition.params),
            actor=transition.actor,
            source=transition.source,
            reason=transition.reason,
            note=transition.note,
            metadata=dict(transition.metadata),
            expected_versions=dict(transition.expected_versions),
            idempotency_key=transition.idempotency_key,
        )

    return normalized_action, ControlTransition(
        op=transition.op,
        target_id=normalized_action,
        payload=dict(transition.payload),
        idempotency_key=transition.idempotency_key,
    )


_EXTERNAL_ERROR_RETRY_STRATEGIES = frozenset({"external_error", "provider_error", "wait_and_retry"})


def _external_error_requires_resume(
    state: Mapping[str, object],
    resume_cursor: Mapping[str, object],
    phase_result: Any | None,
) -> bool:
    latest_failure = state.get("latest_failure")
    if isinstance(latest_failure, Mapping) and latest_failure.get("kind") == "external_error":
        return True
    if getattr(phase_result, "exit_kind", None) == "external_error":
        return True
    return resume_cursor.get("retry_strategy") in _EXTERNAL_ERROR_RETRY_STRATEGIES


def _latest_revise_start_iso(plan_dir: Path, state: Mapping[str, object]) -> str | None:
    candidates: list[str] = []
    for receipt_path in plan_dir.glob("step_receipt_revise_v*.json"):
        try:
            import json as _json

            data = _json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        metrics = data.get("metrics") if isinstance(data, dict) else None
        ts = metrics.get("start_timestamp_utc") if isinstance(metrics, dict) else None
        if not isinstance(ts, str) or not ts:
            ts = data.get("timestamp_utc") if isinstance(data, dict) else None
        if isinstance(ts, str) and ts:
            candidates.append(ts)
    for entry in state.get("meta", {}).get("overrides", []):  # type: ignore[union-attr]
        if not isinstance(entry, dict):
            continue
        if entry.get("action") in {"step-add", "step-remove", "step-move", "replan"}:
            ts = entry.get("timestamp")
            if isinstance(ts, str) and ts:
                candidates.append(ts)
    return max(candidates) if candidates else None


def _unabsorbed_user_notes(plan_dir: Path, state: Mapping[str, object]) -> list[dict[str, object]]:
    cutoff = _latest_revise_start_iso(plan_dir, state)
    meta = state.get("meta")
    notes = meta.get("notes", []) if isinstance(meta, Mapping) else []
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


def _last_gate_is_agent_availability_preflight_block(state: Mapping[str, object]) -> bool:
    last_gate = state.get("last_gate") or {}
    if not isinstance(last_gate, Mapping):
        return False
    if last_gate.get("recommendation") != "PROCEED" or last_gate.get("passed", False):
        return False
    preflight_results = last_gate.get("preflight_results")
    return (
        isinstance(preflight_results, Mapping)
        and only_agent_availability_preflight_failed(preflight_results)
    )


def _strict_notes_guard(plan_dir: Path, state: Mapping[str, object], transition: ControlTransition) -> None:
    config = state.get("config")
    strict_notes = config.get("strict_notes", False) if isinstance(config, Mapping) else False
    if not strict_notes:
        return
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
    last_gate = state.get("last_gate")
    last_recommendation = last_gate.get("recommendation") if isinstance(last_gate, Mapping) else None
    if last_recommendation == "ESCALATE" and not transition.payload.get("user_approved", False):
        raise CliError(
            "escalate_requires_user_approval",
            (
                "strict_notes: gate escalated and requires --user-approved "
                "before force-proceed."
            ),
        )


def _force_proceed_gate_artifacts(
    state: Mapping[str, object],
    transition: ControlTransition,
) -> dict[str, object]:
    plan_dir = _plan_dir(state, transition)
    root = _root_dir(state, transition)
    gate_checks = run_gate_checks(plan_dir, state, command_lookup=find_command)  # type: ignore[arg-type]
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
    signals = build_gate_signals(plan_dir, state, root=root)  # type: ignore[arg-type]
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
            "rationale": transition.payload.get("reason") or "User forced execution past the gate.",
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
    flag_registry = load_flag_registry(plan_dir)
    return {
        "gate.json": gate,
        "unresolved_flags": unresolved_significant_flags(flag_registry),
    }


def _write_force_proceed_artifacts(
    state: Mapping[str, object],
    transition: ControlTransition,
    artifacts: Mapping[str, object],
) -> int:
    plan_dir = _plan_dir(state, transition)
    root = _root_dir(state, transition)
    gate = artifacts.get("gate.json")
    if isinstance(gate, Mapping):
        _write_gate_json(plan_dir, dict(gate))
    unresolved_flags = artifacts.get("unresolved_flags")
    flags = unresolved_flags if isinstance(unresolved_flags, list) else []
    debt_registry = load_debt_registry(root)
    for flag in flags:
        if not isinstance(flag, Mapping):
            continue
        concern = flag.get("concern")
        flag_id = flag.get("id")
        if not isinstance(concern, str) or not isinstance(flag_id, str):
            continue
        add_or_increment_debt(
            debt_registry,
            subsystem=extract_subsystem_tag(concern),
            concern=concern,
            flag_ids=[flag_id],
            plan_id=str(state.get("name") or ""),
        )
    save_debt_registry(root, debt_registry)
    return len(flags)


def _selected_profile_spec_value(spec_value: str | list[str], *, path: str) -> str:
    if isinstance(spec_value, str):
        return spec_value
    return select_fallback_spec(spec_value, 0, path=path)


def _load_resolved_profile(state: Mapping[str, object]) -> dict[str, str | list[str]] | None:
    config = state.get("config")
    profile_name = config.get("profile") if isinstance(config, Mapping) else None
    if not isinstance(profile_name, str) or not profile_name:
        return None
    from arnold_pipelines.megaplan.profiles import load_profiles, resolve_profile

    profiles = load_profiles(project_dir=_project_dir(state))
    return resolve_profile(profile_name, profiles)


def _infer_phase_agent(phase: str, state: Mapping[str, object]) -> str | None:
    config = state.get("config")
    phase_models = config.get("phase_model") if isinstance(config, Mapping) else None
    if isinstance(phase_models, list):
        for raw in phase_models:
            if isinstance(raw, str) and "=" in raw:
                pm_phase, chain = decode_phase_model_value(raw)
                if pm_phase == phase:
                    return parse_agent_spec(
                        _resolve_symbolic_phase_spec(chain.selected(), state)
                    ).agent
    try:
        resolved = _load_resolved_profile(state)
    except Exception:
        resolved = None
    if resolved and phase in resolved:
        return parse_agent_spec(
            _resolve_symbolic_phase_spec(
                _selected_profile_spec_value(resolved[phase], path=f"profile.{phase}"),
                state,
            )
        ).agent
    default_spec = DEFAULT_AGENT_ROUTING.get(phase, "")
    return parse_agent_spec(_resolve_symbolic_phase_spec(default_spec, state)).agent if default_spec else None


def _current_phase_spec(phase: str, state: Mapping[str, object]) -> str:
    config = state.get("config")
    phase_models = config.get("phase_model") if isinstance(config, Mapping) else None
    if isinstance(phase_models, list):
        for raw in phase_models:
            if isinstance(raw, str) and "=" in raw:
                pm_phase, chain = decode_phase_model_value(raw)
                if pm_phase == phase:
                    return _resolve_symbolic_phase_spec(chain.selected(), state)
    try:
        resolved = _load_resolved_profile(state)
    except Exception:
        resolved = None
    if resolved and phase in resolved:
        return _resolve_symbolic_phase_spec(
            _selected_profile_spec_value(resolved[phase], path=f"profile.{phase}"),
            state,
        )
    return _resolve_symbolic_phase_spec(DEFAULT_AGENT_ROUTING.get(phase, ""), state)


def _resolve_symbolic_phase_spec(spec: str, state: Mapping[str, object]) -> str:
    if not spec or not is_premium_placeholder_spec(spec):
        return spec
    config = state.get("config")
    vendor = effective_premium_vendor(config=config if isinstance(config, Mapping) else {})
    return format_agent_spec(resolve_premium_placeholder_spec(spec, vendor))


def _replace_phase_model(
    state: Mapping[str, object],
    *,
    phase: str,
    new_spec: str,
    default_previous_spec: str,
) -> tuple[dict[str, Any], str]:
    config = state.get("config")
    phase_models = list(config.get("phase_model") or []) if isinstance(config, Mapping) else []
    previous_spec = None
    found = False
    for i, raw in enumerate(phase_models):
        if isinstance(raw, str) and "=" in raw and raw.split("=", 1)[0] == phase:
            previous_spec = raw.split("=", 1)[1]
            phase_models[i] = f"{phase}={new_spec}"
            found = True
            break
    if not found:
        previous_spec = default_previous_spec
        phase_models.append(f"{phase}={new_spec}")
    next_config = dict(config) if isinstance(config, Mapping) else {}
    next_config["phase_model"] = phase_models
    tier_models = next_config.get("tier_models")
    if isinstance(tier_models, Mapping) and phase in tier_models:
        next_tier_models = dict(tier_models)
        next_tier_models.pop(phase, None)
        next_config["tier_models"] = next_tier_models
    return next_config, previous_spec


class PlanningControlBinding:
    """Planning implementation of the shared control-binding protocol.

    T6 establishes the import boundary and forward target projection. Recovery,
    transition mutation, and artifact synthesis stay as explicit placeholders
    until later routing tasks land on this package path.
    """

    def valid_targets(self, run_state: RunStateView) -> tuple[ControlTargetRef, ...]:
        state = _coerce_plan_state(run_state.raw_state)
        if state is None:
            return (
                _diagnostic(
                    "malformed_plan_state",
                    "planning target projection requires current_state and config",
                ),
            )
        if _projection_surface(run_state) == "supervisor":
            projected = _supervisor_forward_targets(state)
            if projected:
                return projected
        return tuple(
            _workflow_step_target(step, direction="forward")
            for step in workflow_next(state)
        )

    def recover_targets(self, run_state: RunStateView) -> tuple[ControlTargetRef, ...]:
        state = _coerce_plan_state(run_state.raw_state)
        if state is None:
            return (
                _diagnostic(
                    "malformed_plan_state",
                    "planning recovery projection requires current_state and config",
                ),
            )
        if _projection_surface(run_state) == "supervisor":
            projected = _supervisor_recover_targets(state)
            if projected:
                return projected
            return ()

        current_state = state["current_state"]
        if current_state == STATE_AWAITING_HUMAN or (
            current_state == STATE_BLOCKED and _has_prep_clarification(state)
        ):
            return (_awaiting_human_target(state),)

        phase, source = _recovery_phase(state)
        if phase is None:
            return (
                _diagnostic(
                    "missing_recovery_phase",
                    "planning recovery projection could not find a phase",
                    current_state=current_state,
                ),
            )

        if current_state == STATE_BLOCKED:
            rerun_target = _blocked_phase_rerun_target(
                state,
                phase=phase,
                source=source,
            )
            if rerun_target is not None:
                return (rerun_target,)
            return (
                declared_override_policy_target(
                    "recover-blocked",
                    direction="recovery",
                    source=source,
                    operator_action="recover-blocked",
                ),
            )

        recovered_state = topology.predecessors(phase, policy="recovery")
        if recovered_state is None:
            return (
                _diagnostic(
                    "unknown_recovery_phase",
                    f"planning recovery projection does not know phase {phase!r}",
                    current_state=current_state,
                    phase=phase,
                    source=source,
                ),
            )

        return (
            _workflow_step_target(
                phase,
                direction="recovery",
                target_state=recovered_state,
                source=source,
            ),
        )

    def apply_transition(
        self,
        run_state: RunStateView,
        transition: ControlTransition,
    ) -> ControlTransitionResult:
        state = _coerce_plan_state(run_state.raw_state)
        if state is None:
            return ControlTransitionResult(
                accepted=False,
                mutated=False,
                reason="malformed_plan_state",
            )

        action, transition = _normalize_transition_action(transition)
        if transition.op != "override" and action is None:
            return ControlTransitionResult(
                accepted=False,
                mutated=False,
                reason="planning_control_binding_transition_unimplemented",
            )
        if action == "add-note":
            note = transition.payload.get("note")
            if not isinstance(note, str) or not note:
                raise CliError("invalid_args", "override add-note requires --note")
            source = transition.payload.get("source")
            if not isinstance(source, str) or not source:
                source = "user"
            note_entry = {
                "timestamp": now_utc(),
                "note": note,
                "source": source,
            }
            override_entry = {
                "action": "add-note",
                "timestamp": now_utc(),
                "note": note,
                "source": source,
            }
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="add-note",
                state_deltas=(
                    _replace_delta(
                        state,
                        "meta",
                        _next_meta(
                            state,
                            note_entry=note_entry,
                            override_entry=override_entry,
                        ),
                    ),
                ),
            )

        if action == "abort":
            reason = transition.payload.get("reason")
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="abort",
                state_deltas=(
                    _replace_delta(state, "current_state", STATE_ABORTED),
                    _replace_delta(
                        state,
                        "meta",
                        _next_meta(
                            state,
                            override_entry={
                                "action": "abort",
                                "timestamp": now_utc(),
                                "reason": reason,
                            },
                        ),
                    ),
                ),
            )

        if action == "force-proceed":
            plan_dir = _plan_dir(state, transition)
            _strict_notes_guard(plan_dir, state, transition)
            current_state = state["current_state"]
            reason = transition.payload.get("reason")
            override_entry = {
                "action": "force-proceed",
                "timestamp": now_utc(),
                "reason": reason,
            }
            if current_state == STATE_EXECUTED:
                return ControlTransitionResult(
                    accepted=True,
                    mutated=True,
                    reason="force-proceed",
                    state_deltas=(
                        _replace_delta(state, "current_state", STATE_DONE),
                        _replace_delta(
                            state,
                            "meta",
                            _next_meta(state, override_entry=override_entry),
                        ),
                    ),
                )
            if current_state == STATE_BLOCKED:
                if not _last_gate_is_agent_availability_preflight_block(state):
                    raise CliError(
                        "invalid_transition",
                        "force-proceed from blocked is only supported for PROCEED gates blocked by agent availability preflight",
                    )
            elif current_state != STATE_CRITIQUED:
                raise CliError(
                    "invalid_transition",
                    "force-proceed is only supported from critiqued, executed, or recoverable blocked state",
                )

            artifacts = dict(self.synthesize_artifacts(run_state, transition))
            debt_entries_added = _write_force_proceed_artifacts(state, transition, artifacts)
            next_meta = _next_meta(state, override_entry=override_entry)
            next_meta.pop("user_approved_gate", None)
            gate = artifacts.get("gate.json")
            orchestrator_guidance = (
                gate.get("orchestrator_guidance")
                if isinstance(gate, Mapping)
                else "Force-proceed override applied. Proceed to finalize."
            )
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="force-proceed",
                artifacts={
                    **artifacts,
                    "orchestrator_guidance": orchestrator_guidance,
                    "debt_entries_added": debt_entries_added,
                },
                state_deltas=(
                    _replace_delta(state, "current_state", STATE_GATED),
                    _replace_delta(state, "last_gate", {}),
                    _replace_delta(state, "meta", next_meta),
                ),
            )

        if action == "recover-blocked":
            latest_failure = state.get("latest_failure")
            aborted_with_blocked_failure = (
                state["current_state"] == STATE_ABORTED
                and isinstance(latest_failure, Mapping)
                and latest_failure.get("state") == STATE_BLOCKED
            )
            if state["current_state"] != STATE_BLOCKED and not aborted_with_blocked_failure:
                raise CliError(
                    "invalid_transition",
                    f"recover-blocked requires state '{STATE_BLOCKED}', got '{state['current_state']}'",
                )
            reason = transition.payload.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise CliError("invalid_args", "override recover-blocked requires --reason")
            resume_cursor = state.get("resume_cursor")
            if not isinstance(resume_cursor, Mapping):
                raise CliError(
                    "missing_resume_cursor",
                    "recover-blocked requires a stored resume_cursor",
                )
            phase = resume_cursor.get("phase")
            if not isinstance(phase, str) or not phase:
                raise CliError(
                    "invalid_resume_cursor",
                    "recover-blocked requires resume_cursor.phase",
                    extra={"resume_cursor": dict(resume_cursor)},
                )
            recovered_state = topology.predecessors(phase, policy="recovery")
            if recovered_state is None:
                raise CliError(
                    "invalid_resume_cursor",
                    f"recover-blocked does not know how to resume phase {phase!r}",
                    extra={"resume_cursor": dict(resume_cursor)},
                )
            if isinstance(latest_failure, Mapping) and latest_failure.get("kind") == "authority_divergence":
                plan_name = state.get("name") or "plan"
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
                        "resume_cursor": dict(resume_cursor),
                        "latest_failure": dict(latest_failure),
                        "rerun_command": rerun_command,
                        "suggested_recovery_commands": [rerun_command],
                    },
                )

            plan_dir = _plan_dir(state, transition)
            finalize_path = plan_dir / "finalize.json"
            finalize_data = read_json(finalize_path) if finalize_path.exists() else {}
            phase_result = read_phase_result(plan_dir)
            if _external_error_requires_resume(state, resume_cursor, phase_result):
                plan_name = state.get("name") or plan_dir.name
                resume_command = f"megaplan resume --plan {plan_name}"
                raise CliError(
                    "external_error_resume_required",
                    (
                        "recover-blocked is for explicit task or quality blockers. "
                        "This blocked plan stopped on an external provider error; "
                        f"fix provider/profile settings if needed, then run `{resume_command}`."
                    ),
                    extra={
                        "resume_cursor": dict(resume_cursor),
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
            contract_failure_without_result = (
                phase_result is None
                and recoverable_contract_failure_without_phase_result(state, resume_cursor)
            )
            if phase_result is None and not contract_failure_without_result:
                raise CliError(
                    "missing_phase_result",
                    "recover-blocked requires phase_result.json with current blocker details",
                    extra={"resume_cursor": dict(resume_cursor)},
                )
            evaluation = evaluate_blocker_recovery(
                finalize_data,
                state,
                plan_dir=plan_dir,
                blocked_tasks=phase_result.blocked_tasks if phase_result is not None else (),
                deviations=phase_result.deviations if phase_result is not None else (),
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
                        "resume_cursor": dict(resume_cursor),
                        "phase_result_exit_kind": (
                            phase_result.exit_kind if phase_result is not None else None
                        ),
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
            override_entry = {
                "action": "recover-blocked",
                "timestamp": now_utc(),
                "reason": reason,
                "from_state": previous_state,
                "to_state": recovered_state,
                "resume_cursor": dict(resume_cursor),
                "blocker_ids": [blocker.blocker_id for blocker in evaluation.blockers],
            }
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="recover-blocked",
                artifacts={
                    "blockers": blocker_details,
                    "remove_state_keys": ("latest_failure", "active_step"),
                },
                state_deltas=(
                    _replace_delta(state, "current_state", recovered_state),
                    _replace_delta(
                        state,
                        "meta",
                        _next_meta(state, override_entry=override_entry),
                    ),
                ),
            )

        if action == "resume-clarify":
            clarification = state.get("clarification")
            source = clarification.get("source") if isinstance(clarification, Mapping) else None
            if state["current_state"] not in {STATE_AWAITING_HUMAN, STATE_BLOCKED}:
                raise CliError(
                    "invalid_transition",
                    f"resume-clarify requires state '{STATE_AWAITING_HUMAN}', got '{state['current_state']}'",
                )
            if source != "prep":
                raise CliError(
                    "invalid_transition",
                    "resume-clarify can only resume a prep-sourced clarification halt; "
                    "use verify-human for criteria-verification awaiting_human states",
                )
            meta = state.get("meta")
            notes = meta.get("notes") if isinstance(meta, Mapping) else []
            user_notes = [
                note
                for note in notes
                if isinstance(note, Mapping) and note.get("source", "user") == "user"
            ]
            warnings = []
            if not user_notes:
                warnings.append(
                    "No answers found in notes; consider adding answers via "
                    "'override add-note' before the plan phase."
                )
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="resume-clarify",
                artifacts={
                    "warnings": warnings,
                    "remove_state_keys": ("clarification",),
                },
                state_deltas=(
                    _replace_delta(state, "current_state", STATE_PREPPED),
                    _replace_delta(
                        state,
                        "meta",
                        _next_meta(
                            state,
                            override_entry={"action": "resume-clarify", "timestamp": now_utc()},
                        ),
                    ),
                ),
            )

        if action == "replan":
            allowed = {STATE_GATED, STATE_FINALIZED, STATE_CRITIQUED, STATE_FAILED}
            current_state = state["current_state"]
            if current_state not in allowed:
                raise CliError(
                    "invalid_transition",
                    f"replan requires state {', '.join(sorted(allowed))}, got '{current_state}'",
                )
            reason = transition.payload.get("reason") or transition.payload.get("note") or "Re-entering planning loop"
            note = transition.payload.get("note")
            plan_dir = _plan_dir(state, transition)
            plan_file = latest_plan_path(plan_dir, state)  # type: ignore[arg-type]
            timestamp = now_utc()
            override_entry = {
                "action": "replan",
                "timestamp": timestamp,
                "reason": reason,
                "from_state": current_state,
                "plan_file": plan_file.name,
            }
            note_entry = None
            if isinstance(note, str) and note:
                note_entry = {"timestamp": timestamp, "note": note}
            next_state = dict(state)
            next_state["meta"] = _next_meta(
                state,
                note_entry=note_entry,
                override_entry=override_entry,
            )
            reset_replan_loop_state(next_state, target_state=STATE_PLANNED)
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="replan",
                artifacts={
                    "plan_file": str(plan_file),
                    "remove_state_keys": REPLAN_STATE_KEYS_TO_CLEAR,
                },
                state_deltas=(
                    _replace_delta(state, "current_state", next_state["current_state"]),
                    _replace_delta(state, "last_gate", next_state["last_gate"]),
                    _replace_delta(state, "meta", next_state["meta"]),
                ),
            )

        if action == "set-robustness":
            raw_level = transition.payload.get("robustness")
            if raw_level not in ROBUSTNESS_ACCEPTED:
                raise CliError(
                    "invalid_args",
                    f"override set-robustness requires --robustness {'|'.join(ROBUSTNESS_ACCEPTED)}",
                )
            if state["current_state"] in {STATE_DONE, STATE_ABORTED}:
                raise CliError(
                    "invalid_transition",
                    "set-robustness cannot be applied to a plan in terminal state "
                    f"'{state['current_state']}'",
                )
            new_level = normalize_robustness(raw_level)
            previous_level = state["config"].get("robustness", "standard")
            next_config = dict(state["config"])
            next_config["robustness"] = new_level
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="set-robustness",
                state_deltas=(
                    _replace_delta(state, "config", next_config),
                    _replace_delta(
                        state,
                        "meta",
                        _next_meta(
                            state,
                            override_entry={
                                "action": "set-robustness",
                                "timestamp": now_utc(),
                                "from": previous_level,
                                "to": new_level,
                                "reason": transition.payload.get("reason"),
                            },
                        ),
                    ),
                ),
            )

        if action == "set-profile":
            new_profile = transition.payload.get("profile")
            if not isinstance(new_profile, str) or not new_profile:
                raise CliError("invalid_args", "override set-profile requires --profile NAME")
            if state["current_state"] in {STATE_DONE, STATE_ABORTED}:
                raise CliError(
                    "invalid_transition",
                    "set-profile cannot be applied to a plan in terminal state "
                    f"'{state['current_state']}'",
                )
            from arnold_pipelines.megaplan.profiles import (
                _resolve_prep_models_with_inheritance,
                load_profile_metadata,
                load_profiles,
                profile_to_phase_models,
                resolve_profile,
            )

            profiles = load_profiles(project_dir=_project_dir(state))
            metadata = load_profile_metadata(project_dir=_project_dir(state))
            resolved = resolve_profile(new_profile, profiles)
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
            previous_profile = state["config"].get("profile")
            next_config = dict(state["config"])
            next_config["profile"] = new_profile
            next_config["phase_model"] = profile_to_phase_models(resolved)
            if _profile_has_premium_slots(resolved):
                next_config["vendor"] = effective_premium_vendor(config=state.get("config", {}))
            else:
                next_config.pop("vendor", None)
            prep_models, prep_trace = resolve_prep_models(
                flat_prep_spec=_prep_flat_spec_from_profile(resolved),
                prep_models=inherited_prep_models,
            )
            if prep_models:
                next_config["prep_models"] = prep_models
                next_config["prep_model_resolver_trace"] = prep_trace
            else:
                next_config.pop("prep_models", None)
                next_config.pop("prep_model_resolver_trace", None)
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="set-profile",
                state_deltas=(
                    _replace_delta(state, "config", next_config),
                    _replace_delta(
                        state,
                        "meta",
                        _next_meta(
                            state,
                            override_entry={
                                "action": "set-profile",
                                "timestamp": now_utc(),
                                "from": previous_profile,
                                "to": new_profile,
                                "reason": transition.payload.get("reason"),
                            },
                        ),
                    ),
                ),
            )

        if action == "set-model":
            phase = transition.payload.get("phase")
            model_arg = transition.payload.get("model")
            effort = transition.payload.get("effort")
            if not isinstance(phase, str) or not phase:
                raise CliError("invalid_args", "override set-model requires --phase PHASE")
            if not isinstance(model_arg, str) or not model_arg:
                raise CliError("invalid_args", "override set-model requires --model MODEL")
            if phase not in DEFAULT_AGENT_ROUTING:
                raise CliError(
                    "invalid_args",
                    f"Unknown phase '{phase}'. Valid phases: {', '.join(sorted(DEFAULT_AGENT_ROUTING))}",
                )
            agent = _infer_phase_agent(phase, state) or DEFAULT_AGENT_ROUTING.get(phase, "")
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
            if target_model in _PREMIUM_EFFORT_TOKENS:
                raise CliError(
                    "invalid_args",
                    f"'{target_model}' is a reserved effort token and cannot be used as a model name. "
                    "Use --effort to set effort level.",
                )
            if target_effort is not None and target_effort not in _PREMIUM_EFFORT_TOKENS:
                raise CliError(
                    "invalid_args",
                    f"Unknown effort level '{target_effort}'. Valid: {', '.join(sorted(_PREMIUM_EFFORT_TOKENS))}",
                )
            new_spec = format_agent_spec(
                AgentSpec(target_agent, model=target_model, effort=target_effort)
            )
            next_config, previous_spec = _replace_phase_model(
                state,
                phase=phase,
                new_spec=new_spec,
                default_previous_spec=_current_phase_spec(phase, state),
            )
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="set-model",
                state_deltas=(
                    _replace_delta(state, "config", next_config),
                    _replace_delta(
                        state,
                        "meta",
                        _next_meta(
                            state,
                            override_entry={
                                "action": "set-model",
                                "phase": phase,
                                "previous_spec": previous_spec,
                                "new_spec": new_spec,
                                "timestamp": now_utc(),
                                "reason": transition.payload.get("reason", "") or "",
                            },
                        ),
                    ),
                ),
            )

        if action == "set-vendor":
            phase = transition.payload.get("phase")
            vendor = transition.payload.get("vendor")
            if not isinstance(phase, str) or not phase:
                raise CliError("invalid_args", "override set-vendor requires --phase PHASE")
            if not isinstance(vendor, str) or not vendor:
                raise CliError("invalid_args", "override set-vendor requires --vendor VENDOR")
            if phase not in DEFAULT_AGENT_ROUTING:
                raise CliError(
                    "invalid_args",
                    f"Unknown phase '{phase}'. Valid phases: {', '.join(sorted(DEFAULT_AGENT_ROUTING))}",
                )
            from arnold_pipelines.megaplan._core.user_config import VALID_VENDORS
            from arnold_pipelines.megaplan.profiles import _swap_premium_spec

            if vendor not in VALID_VENDORS:
                raise CliError(
                    "invalid_args",
                    f"set-vendor --vendor must be one of {', '.join(VALID_VENDORS)}; got {vendor!r}",
                )
            current_spec = _current_phase_spec(phase, state)
            parsed = parse_agent_spec(current_spec)
            if parsed.agent not in _PREMIUM_VENDORS:
                raise CliError(
                    "invalid_args",
                    f"set-vendor is only supported for claude/codex phases. "
                    f"Phase '{phase}' resolves to agent '{parsed.agent}' ({current_spec!r}).",
                )
            new_spec = format_agent_spec(parse_agent_spec(_swap_premium_spec(current_spec, vendor)))
            next_config, previous_spec = _replace_phase_model(
                state,
                phase=phase,
                new_spec=new_spec,
                default_previous_spec=current_spec or DEFAULT_AGENT_ROUTING.get(phase, ""),
            )
            return ControlTransitionResult(
                accepted=True,
                mutated=True,
                reason="set-vendor",
                state_deltas=(
                    _replace_delta(state, "config", next_config),
                    _replace_delta(
                        state,
                        "meta",
                        _next_meta(
                            state,
                            override_entry={
                                "action": "set-vendor",
                                "phase": phase,
                                "previous_spec": previous_spec,
                                "new_spec": new_spec,
                                "timestamp": now_utc(),
                                "reason": transition.payload.get("reason", "") or "",
                            },
                        ),
                    ),
                ),
            )

        return ControlTransitionResult(
            accepted=False,
            mutated=False,
            reason="planning_control_binding_transition_unimplemented",
        )

    def synthesize_artifacts(
        self,
        run_state: RunStateView,
        transition: ControlTransition,
    ) -> dict[str, object]:
        state = _coerce_plan_state(run_state.raw_state)
        if state is None:
            return {}
        if transition.op == "override" and transition.target_id == "force-proceed":
            return _force_proceed_gate_artifacts(state, transition)
        return {}


def planning_control_binding() -> PlanningControlBinding:
    """Return the planning binding instance for shared control-interface calls."""

    return PlanningControlBinding()


__all__ = ["PlanningControlBinding", "planning_control_binding"]
