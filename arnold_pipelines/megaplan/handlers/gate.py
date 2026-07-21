from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan import handlers as _pkg
from arnold_pipelines.megaplan.outcomes import GateOutcome
from arnold_pipelines.megaplan.orchestration.gate_checks import (
    build_gate_artifact,
    build_orchestrator_guidance,
    only_agent_availability_preflight_failed,
    run_gate_checks,
)
from arnold_pipelines.megaplan.orchestration.gate_signals import build_gate_signals
from arnold_pipelines.megaplan.orchestration.rubber_stamp import is_rubber_stamp
from arnold_pipelines.megaplan.orchestration.critique_custody import (
    CritiqueCustodyError,
    validate_gate_input_custody,
)
from arnold_pipelines.megaplan.profiles import apply_profile_expansion
from arnold_pipelines.megaplan.model_seam import ModelStructuralAuditError, audit_step_payload
from arnold_pipelines.megaplan.schema_projection import (
    project_schema_owned_fields,
    require_schema_fields,
    schema_property_names,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.types import FLAG_BLOCKING_STATUSES, CliError, PlanState, StepResponse
from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED, STATE_CRITIQUED, STATE_GATED, STATE_PLANNED
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.workers.result_metadata import prefer_retry_rate_limit
from arnold_pipelines.megaplan._core import (
    add_or_increment_debt,
    atomic_write_json,
    configured_robustness,
    extract_subsystem_tag,
    find_command,
    get_effective,
    infer_next_steps,
    load_debt_registry,
    load_flag_registry,
    load_plan_locked,
    now_utc,
    read_json,
    require_state,
    save_debt_registry,
    workflow_includes_step,
    workflow_next,
    workflow_transition,
)

from .critique import _validate_tiebreaker
from .shared import (
    _append_to_meta,
    _build_gate_prompt_override,
    _finish_step,
    _raise_step_validation_error,
    _run_worker,
    _warn_best_effort_emit_failure,
    _warn_read_fallback,
    _write_gate_json,
    log,
)


def _gate_debt_visibility_policy() -> dict[str, Any]:
    from arnold_pipelines.megaplan.workflows.components import GATE_DEBT_VISIBILITY_POLICY

    return GATE_DEBT_VISIBILITY_POLICY


def _gate_reprompt_policy() -> dict[str, Any]:
    from arnold_pipelines.megaplan.workflows.components import GATE_REPROMPT_POLICY

    return GATE_REPROMPT_POLICY


def _revise_loop_termination_policy() -> dict[str, Any]:
    from arnold_pipelines.megaplan.workflows.components import REVISE_LOOP_TERMINATION_POLICY

    return REVISE_LOOP_TERMINATION_POLICY

def _build_gate_signals_artifact(
    plan_dir: Path,
    state: PlanState,
    *,
    iteration: int,
    root: Path,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    try:
        critique_custody = validate_gate_input_custody(plan_dir, state)
    except CritiqueCustodyError as error:
        raise CliError(
            error.code,
            str(error),
            valid_next=["critique"],
            extra={"issues": list(error.issues)},
        ) from error
    gate_signals = build_gate_signals(plan_dir, state, root=root)
    gate_signals.setdefault("signals", {})["critique_custody"] = critique_custody
    gate_checks = run_gate_checks(plan_dir, state, command_lookup=find_command)
    signals_artifact = {
        "robustness": gate_signals["robustness"],
        "signals": gate_signals["signals"],
        "warnings": gate_signals.get("warnings", []),
        "criteria_check": gate_checks["criteria_check"],
        "preflight_results": gate_checks["preflight_results"],
        "unresolved_flags": gate_checks["unresolved_flags"],
        "critique_custody": critique_custody,
    }
    signals_filename = f"gate_signals_v{iteration}.json"
    atomic_write_json(plan_dir / signals_filename, signals_artifact)
    return gate_signals, signals_filename, signals_artifact

def _record_gate_debt_entries(
    root: Path,
    state: PlanState,
    gate_summary: dict[str, Any],
    worker_payload: dict[str, Any],
) -> int:
    if gate_summary["recommendation"] != "PROCEED":
        return 0

    raw_tradeoffs = worker_payload.get("accepted_tradeoffs", [])
    accepted_tradeoffs = [
        item
        for item in raw_tradeoffs
        if isinstance(item, dict)
        and isinstance(item.get("flag_id"), str)
        and isinstance(item.get("concern"), str)
    ] if isinstance(raw_tradeoffs, list) else []
    has_explicit_resolutions = any(
        isinstance(item, dict) for item in gate_summary.get("flag_resolutions", [])
    )
    debt_registry = load_debt_registry(root)
    debt_entries_added = 0
    if accepted_tradeoffs:
        for tradeoff in accepted_tradeoffs:
            subsystem_value = tradeoff.get("subsystem")
            subsystem = (
                subsystem_value
                if isinstance(subsystem_value, str) and subsystem_value.strip()
                else extract_subsystem_tag(tradeoff["concern"])
            )
            add_or_increment_debt(
                debt_registry,
                subsystem=subsystem,
                concern=tradeoff["concern"],
                flag_ids=[tradeoff["flag_id"]],
                plan_id=state["name"],
            )
            debt_entries_added += 1
    elif not has_explicit_resolutions:
        for flag in gate_summary["unresolved_flags"]:
            if not isinstance(flag, dict):
                continue
            flag_id = flag.get("id")
            concern = flag.get("concern")
            if not isinstance(flag_id, str) or not isinstance(concern, str):
                continue
            add_or_increment_debt(
                debt_registry,
                subsystem=extract_subsystem_tag(concern),
                concern=concern,
                flag_ids=[flag_id],
                plan_id=state["name"],
            )
            debt_entries_added += 1
    if debt_entries_added:
        save_debt_registry(root, debt_registry)
    return debt_entries_added

def _gate_summary_for_transition(plan_dir: Path, state: PlanState) -> dict[str, Any]:
    carry_path = plan_dir / "gate_carry.json"
    if carry_path.exists():
        carry = read_json(carry_path)
        if isinstance(carry, dict):
            require_schema_fields(
                carry,
                SCHEMAS["gate.json"],
                contract="gate transition carry consumption",
            )
            normalized = dict(carry)
            recommendation = normalized.get("recommendation") or normalized.get("verdict")
            if recommendation is not None:
                normalized["recommendation"] = recommendation
            return normalized
    gate_path = plan_dir / "gate.json"
    if gate_path.exists():
        gate = read_json(gate_path)
        if isinstance(gate, dict):
            require_schema_fields(
                gate,
                SCHEMAS["gate.json"],
                contract="gate transition artifact consumption",
            )
            return gate
    legacy = state.get("last_gate", {})
    return legacy if isinstance(legacy, dict) else {}


def _resolve_revise_transition(state: PlanState, plan_dir: Path) -> tuple[bool, Any]:
    has_gate = workflow_includes_step(configured_robustness(state), "gate")
    gate_summary = _gate_summary_for_transition(plan_dir, state)
    recommendation = gate_summary.get("recommendation") or gate_summary.get("verdict")
    if has_gate and recommendation != "ITERATE":
        raise CliError("invalid_transition", "Revise requires a gate recommendation of ITERATE", valid_next=infer_next_steps(state))
    revise_transition = workflow_transition(state, "revise")
    if revise_transition is None:
        raise CliError("invalid_transition", "Revise is not available from the current workflow state", valid_next=infer_next_steps(state))
    return has_gate, revise_transition

def _next_progress_step(state: PlanState) -> str | None:
    next_steps = workflow_next(state)
    return next((step for step in next_steps if step not in {"plan", "step"}), next_steps[0] if next_steps else None)

def _remaining_significant_flags(plan_dir: Path) -> list[dict[str, str]]:
    return [
        {"id": flag["id"], "concern": flag["concern"], "category": flag["category"]}
        for flag in load_flag_registry(plan_dir)["flags"]
        if flag["status"] in FLAG_BLOCKING_STATUSES and flag.get("severity") == "significant"
    ]

def _post_revise_gate_allowed(state: PlanState, plan_dir: Path) -> bool:
    if state.get("current_state") != STATE_PLANNED or int(state.get("iteration", 0) or 0) < 2:
        return False
    try:
        latest_meta = read_json(plan_dir / f"plan_v{state['iteration']}.meta.json")
    except (FileNotFoundError, OSError, ValueError):
        return False
    flags_addressed = latest_meta.get("flags_addressed")
    if not isinstance(flags_addressed, list) or not flags_addressed:
        return False
    history = state.get("history", [])
    return bool(history and isinstance(history[-1], dict) and history[-1].get("step") == "revise")

def _gate_response_fields(state: PlanState, gate_summary: dict[str, Any], debt_entries_added: int) -> dict[str, Any]:
    require_schema_fields(
        gate_summary,
        SCHEMAS["gate.json"],
        contract="gate response projection",
    )
    return {
        **project_schema_owned_fields(
            gate_summary,
            SCHEMAS["gate.json"],
            contract="gate response projection",
        ),
        "auto_approve": bool(state["config"].get("auto_approve", False)),
        "robustness": configured_robustness(state),
        "recommendation": gate_summary["recommendation"],
        "reprompted": bool(gate_summary.get("reprompted", False)),
        "rationale": gate_summary["rationale"],
        "signals_assessment": gate_summary["signals_assessment"],
        "warnings": gate_summary["warnings"],
        "passed": gate_summary["passed"],
        "criteria_check": gate_summary["criteria_check"],
        "preflight_results": gate_summary["preflight_results"],
        "unresolved_flags": gate_summary["unresolved_flags"],
        "addressed_flags": gate_summary.get("addressed_flags", []),
        "orchestrator_guidance": gate_summary["orchestrator_guidance"],
        "signals": gate_summary["signals"],
        "debt_entries_added": debt_entries_added,
    }


def _gate_debt_payload(gate_summary: dict[str, Any], debt_entries_added: int) -> dict[str, Any]:
    debt_visibility_policy = _gate_debt_visibility_policy()
    return {
        "recommendation": gate_summary["recommendation"],
        "entries_added": debt_entries_added,
        "accepted_tradeoffs": sum(
            1
            for item in gate_summary.get("flag_resolutions", [])
            if isinstance(item, dict) and item.get("action") == "accept_tradeoff"
        ),
        "visibility_effect": debt_visibility_policy["effect"],
        "payload_fields": debt_visibility_policy["payload_fields"],
    }

def _brief_text(value: object, *, sentences: int = 3, max_chars: int = 600) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    brief = " ".join(part for part in parts[:sentences] if part).strip()
    if len(brief) <= max_chars:
        return brief
    return brief[: max_chars - 1].rstrip() + "..."


def _normalize_settled_decisions(gate_summary: dict[str, Any]) -> list[dict[str, str]]:
    raw_decisions = gate_summary.get("settled_decisions", [])
    if not isinstance(raw_decisions, list):
        log.warning("gate settled_decisions was not a list; dropping invalid value")
        gate_summary["settled_decisions"] = []
        return []

    normalized: list[dict[str, str]] = []
    promoted_strings = 0
    for index, item in enumerate(raw_decisions, start=1):
        fallback_id = f"SD{index}"
        if isinstance(item, str):
            decision = item.strip()
            if not decision:
                continue
            normalized.append({"id": fallback_id, "decision": decision, "rationale": ""})
            promoted_strings += 1
            continue
        if not isinstance(item, dict):
            log.warning("gate settled_decisions item %s had invalid type; dropping", index)
            continue
        decision = str(item.get("decision", "")).strip()
        if not decision:
            log.warning("gate settled_decisions item %s had no decision; dropping", index)
            continue
        decision_id = str(item.get("id") or fallback_id).strip() or fallback_id
        rationale = str(item.get("rationale", "")).strip()
        normalized.append({"id": decision_id, "decision": decision, "rationale": rationale})

    if promoted_strings:
        log.warning(
            "auto-promoted %s legacy string settled_decisions entr%s to typed objects",
            promoted_strings,
            "y" if promoted_strings == 1 else "ies",
        )
    gate_summary["settled_decisions"] = normalized
    return normalized


def _build_gate_carry(gate_summary: dict[str, Any], *, iteration: int) -> dict[str, Any]:
    require_schema_fields(
        gate_summary,
        SCHEMAS["gate.json"],
        contract="gate carry persistence",
    )
    unresolved_by_id = {
        item.get("id"): item
        for item in gate_summary.get("unresolved_flags", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    carried_flags: list[dict[str, str]] = []
    for resolution in gate_summary.get("flag_resolutions", []):
        if not isinstance(resolution, dict) or resolution.get("action") != "accept_tradeoff":
            continue
        flag_id = resolution.get("flag_id")
        if not isinstance(flag_id, str) or not flag_id:
            continue
        flag = unresolved_by_id.get(flag_id, {})
        concern = flag.get("concern", "") if isinstance(flag, dict) else ""
        carried_flags.append(
            {
                "flag_id": flag_id,
                "concern_brief": _brief_text(concern, sentences=1, max_chars=240),
                "rationale_brief": _brief_text(resolution.get("rationale", ""), sentences=2, max_chars=360),
            }
        )
    recommendation = str(gate_summary.get("recommendation", "PROCEED"))
    return {
        **project_schema_owned_fields(
            gate_summary,
            SCHEMAS["gate.json"],
            contract="gate carry persistence",
        ),
        "version": 1,
        "recommendation": recommendation,
        "passed": bool(gate_summary.get("passed", False)),
        "rationale_brief": _brief_text(gate_summary.get("rationale", ""), sentences=3),
        "settled_decisions": _normalize_settled_decisions(gate_summary),
        "warnings": list(gate_summary.get("warnings", [])) if isinstance(gate_summary.get("warnings"), list) else [],
        "orchestrator_guidance": str(gate_summary.get("orchestrator_guidance", "")),
        "carried_flags": carried_flags,
        "iteration": iteration,
        "produced_at": now_utc(),
    }


def _write_gate_carry(plan_dir: Path, gate_summary: dict[str, Any], *, iteration: int) -> None:
    atomic_write_json(plan_dir / "gate_carry.json", _build_gate_carry(gate_summary, iteration=iteration))


def _sync_legacy_last_gate_for_workflow(state: PlanState, gate_summary: dict[str, Any]) -> None:
    require_schema_fields(
        gate_summary,
        SCHEMAS["gate.json"],
        contract="legacy last_gate persistence",
    )
    state["last_gate"] = {
        **project_schema_owned_fields(
            gate_summary,
            SCHEMAS["gate.json"],
            contract="legacy last_gate persistence",
        ),
        "recommendation": gate_summary["recommendation"],
        "rationale": gate_summary["rationale"],
        "reprompted": bool(gate_summary.get("reprompted", False)),
        "signals_assessment": gate_summary["signals_assessment"],
        "warnings": gate_summary["warnings"],
        "settled_decisions": gate_summary.get("settled_decisions", []),
        "passed": gate_summary["passed"],
        "preflight_results": gate_summary["preflight_results"],
        "orchestrator_guidance": gate_summary["orchestrator_guidance"],
    }


def _critique_cap_key(robustness: str) -> str:
    """Select the robustness-scoped critique-iteration cap key.

    Mirrors the review-loop cap selection (review.py): thorough/extreme pick
    up the higher robust cap, everything else the default cap.
    """
    termination_policy = _revise_loop_termination_policy()
    return (
        termination_policy["iteration_caps"]["robust_config_key"]
        if robustness in {"thorough", "extreme"}
        else termination_policy["iteration_caps"]["default_config_key"]
    )


def _effective_critique_cap(robustness: str) -> int:
    """Resolve the effective ITERATE-round cap for ``robustness``.

    Reads the robustness-scoped DEFAULTS/config key, then applies the light
    override (light caps at 2, below the full default of 4). bare never reaches
    the cap because it has no revise edge.
    """
    cap = int(get_effective("execution", _critique_cap_key(robustness)))
    termination_policy = _revise_loop_termination_policy()
    override = termination_policy["iteration_caps"]["robustness_overrides"].get(robustness)
    if isinstance(override, dict) and "max_value" in override:
        return min(cap, int(override["max_value"]))
    return cap


def _prior_iterate_rounds(state: PlanState) -> int:
    """Count completed critique→gate→revise ITERATE rounds in history.

    The current gate pass is not yet recorded in history when
    ``_build_gate_route_signal`` runs, so this counts only *prior* rounds — the
    same convention as ``prior_rework_count`` in the review handler.
    """
    return sum(
        1
        for entry in state.get("history", [])
        if entry.get("step") == "gate" and entry.get("recommendation") == "ITERATE"
    )


def _is_cap_blocking_flag(flag: dict[str, Any]) -> bool:
    """Whether ``flag`` must force ESCALATE (not force-proceed) at the cap.

    Broader than the PROCEED-path predicate ON PURPOSE and scoped to the
    cap-termination decision only (P2): a blocking flag escalates if it is
    severity-significant OR it is a correctness/security-category flag at any
    severity that is not explicitly cosmetic. So a blocking *moderate*
    correctness flag escalates rather than being shipped as "cosmetic".
    """
    if flag.get("status") not in FLAG_BLOCKING_STATUSES:
        return False
    severity = flag.get("severity")
    severity_policy = _revise_loop_termination_policy()["severity_policy"]
    if severity in severity_policy["significant_severities"]:
        return True
    if severity in severity_policy["cosmetic_severities"]:
        return False
    # Non-cosmetic, non-significant (e.g. "moderate"/"uncertain"/unset):
    # escalate when the flag is correctness/security in nature.
    return flag.get("category") in severity_policy["critical_categories"]


def _open_blocking_flags(gate_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Open flags that must force ESCALATE at the critique cap/stall.

    See ``_is_cap_blocking_flag``: significant-or-worse, or any blocking
    correctness/security flag at a non-cosmetic severity. Scoped to the
    cap-termination switch only; the PROCEED-path predicate is unchanged.
    """
    return [
        f
        for f in gate_summary.get("unresolved_flags", [])
        if isinstance(f, dict) and _is_cap_blocking_flag(f)
    ]


def _critique_no_progress_streak(
    state: PlanState,
    gate_summary: dict[str, Any],
    plan_dir: Path,
) -> int:
    """Update and return the consecutive no-net-progress round streak.

    A round counts as "no progress" when ``resolved_delta == 0`` (no prior
    blocking flag closed this round) AND ``new_blocking >= 1`` (at least one
    fresh blocking flag appeared) — the loop is treading water. The streak is
    persisted on ``state['meta']`` so two consecutive stalled rounds can trip
    the same severity-gated branch as the hard cap (mirrors the advisory
    plateau hint in build_orchestrator_guidance, now enforced).

    P4 — replay/resume consistency. ``_prior_iterate_rounds`` is history-based
    (one entry per completed gate→revise round) while this streak is computed
    from the per-iteration ``gate_signals`` files. To keep the two counters
    from diverging when ``_build_gate_route_signal`` runs more than once for the same
    ``state['iteration']`` (the reprompt path calls it twice; a resumed gate
    re-runs the whole handler), the streak is updated AT MOST ONCE per
    iteration. We stamp ``critique_no_progress_iteration`` with the iteration we
    last counted; a repeat call at the same iteration returns the already-stored
    streak without re-incrementing. Each real round bumps ``state['iteration']``
    (a new revise/critique pass), so genuine rounds still advance the streak.
    """
    iteration = int(state.get("iteration", 0) or 0)
    meta = state.setdefault("meta", {})
    streak = int(meta.get("critique_no_progress_streak", 0) or 0)
    # Idempotent per iteration: do not re-count a round we have already scored.
    if int(meta.get("critique_no_progress_iteration", -1) or -1) == iteration:
        return streak
    # "Blocking" for the progress metric is the full open-flag set the gate
    # tracks (gate_summary["unresolved_flags"], i.e. open significant flags),
    # symmetric with the prior round read from gate_signals_v{n-1}.json. The
    # narrower correctness/security predicate is only the termination *switch*.
    new_blocking_ids = {
        f.get("id")
        for f in gate_summary.get("unresolved_flags", [])
        if isinstance(f, dict) and f.get("id") and f.get("status") in FLAG_BLOCKING_STATUSES
    }
    prior_ids = _prior_unresolved_flag_ids(plan_dir, iteration)
    resolved_delta = len(prior_ids - new_blocking_ids)
    new_blocking = len(new_blocking_ids - prior_ids)
    if resolved_delta == 0 and new_blocking >= 1:
        streak += 1
    else:
        streak = 0
    meta["critique_no_progress_streak"] = streak
    meta["critique_no_progress_iteration"] = iteration
    return streak


def _critique_terminate_branch(
    state: PlanState,
    gate_summary: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Severity-gated termination shared by the hard cap and the stall stop.

    The auto/chain loop is STATUS-DRIVEN: ``auto.drive`` re-derives the next
    step from STATE via ``workflow_next``, IGNORING this handler's returned
    ``next_step``. So termination MUST be expressed in state, not just the
    return tuple, or the loop re-derives ``revise`` and spins forever (P0).

    - Open correctness/security flag → set ``current_state = STATE_BLOCKED``.
      STATE_BLOCKED has no WORKFLOW transitions, so ``workflow_next`` yields []
      (no "revise"), it is a TERMINAL/AUTOMATION_TERMINAL state, and the chain
      treats a "blocked" outcome under ``on_failure`` (default stop_chain) — NOT
      ``on_escalate``'s force-proceed default — so a blocked plan halts for the
      human (P1). This also sidesteps the soft-escalate-then-force-proceed gap.
    - Cosmetic-only open flags → set ``current_state = STATE_GATED`` so
      ``workflow_next`` yields "finalize" (mirrors the review-loop force-proceed
      at review.py:248-252). VERIFIED via workflow_data.py STATE_GATED→finalize.
    """
    open_critical = _open_blocking_flags(gate_summary)
    termination_policy = _revise_loop_termination_policy()
    if open_critical:
        state["current_state"] = STATE_BLOCKED
        outcome = termination_policy["cap_outcomes"]["critical_or_security_blockers"]
        summary = (
            f"{reason} with {len(open_critical)} unresolved correctness/security "
            "flag(s). Plan BLOCKED for human review — the critique loop will not "
            "ship an unresolved correctness/security concern."
        )
        return {
            "result": "blocked",
            "route_signal": outcome,
            "summary": summary,
            "blocking_unresolved_ids": [],
            "fallback_payload": {
                "kind": "critique_cap",
                "reason": "correctness_or_security_flags",
            },
        }
    state["current_state"] = STATE_GATED
    outcome = termination_policy["cap_outcomes"]["cosmetic_only"]
    summary = (
        f"{reason}. Force-proceeding to finalize despite remaining cosmetic flags "
        "(deferred and recorded for audit)."
    )
    return {
        "result": "blocked",
        "route_signal": outcome,
        "summary": summary,
        "blocking_unresolved_ids": [],
        "fallback_payload": {
            "kind": "critique_cap",
            "reason": "cosmetic_flags_only",
        },
    }


def _build_gate_route_signal(
    state: PlanState,
    gate_summary: dict[str, Any],
    *,
    robustness: str,
    plan_dir: Path,
) -> dict[str, Any]:
    result = "success"
    summary = f"Gate recommendation {gate_summary['recommendation']}: {gate_summary['rationale']}"
    route_signal = str(gate_summary["recommendation"]).lower()
    fallback_payload: dict[str, Any] | None = None

    # Process explicit flag resolutions when the gate recommends PROCEED.
    if gate_summary["recommendation"] == "PROCEED":
        unresolved = gate_summary.get("unresolved_flags", [])
        addressed = [
            flag for flag in gate_summary.get("addressed_flags", [])
            if isinstance(flag, dict)
            and flag.get("severity") in ("significant", "likely-significant")
        ]
        resolutions = gate_summary.get("flag_resolutions", [])

        # Validate each explicit resolution
        addressed_ids = {f.get("id") for f in addressed if f.get("id")}
        valid_resolved_ids: set[str] = set()
        valid_resolutions: list[dict[str, Any]] = []
        for res in resolutions:
            action = res.get("action", "")
            flag_id = res.get("flag_id", "")
            if action == "verify_fixed":
                evidence = res.get("evidence", "").strip()
                if not evidence or is_rubber_stamp(evidence, strict=True):
                    continue
                if flag_id not in addressed_ids:
                    continue
            elif action == "dispute":
                evidence = res.get("evidence", "").strip()
                if not evidence or is_rubber_stamp(evidence, strict=True):
                    continue  # invalid dispute — skip
                if flag_id in addressed_ids:
                    continue
            elif action == "accept_tradeoff":
                rationale = res.get("rationale", "").strip()
                if not rationale or is_rubber_stamp(rationale, strict=True):
                    continue  # invalid tradeoff acceptance — skip
                if flag_id in addressed_ids:
                    continue
            else:
                continue  # unknown action — skip
            valid_resolved_ids.add(flag_id)
            valid_resolutions.append(res)

        blocking_by_id: dict[str, dict[str, Any]] = {}
        for flag in [
            f for f in unresolved
            if f.get("severity") in ("significant", "likely-significant")
            and f.get("status") in FLAG_BLOCKING_STATUSES
            and f.get("id") not in valid_resolved_ids
        ]:
            flag_id = flag.get("id")
            if flag_id:
                blocking_by_id[str(flag_id)] = flag
        for flag in [
            f for f in addressed
            if f.get("id") not in valid_resolved_ids
        ]:
            flag_id = flag.get("id")
            if flag_id:
                blocking_by_id[str(flag_id)] = flag
        blocking_unresolved_ids = list(blocking_by_id)

        # Persist explicit resolutions
        if valid_resolutions:
            update_flags_after_gate(plan_dir, valid_resolutions)

        if blocking_unresolved_ids:
            state["current_state"] = STATE_CRITIQUED
            return {
                "result": "unresolved_flags",
                "route_signal": GateOutcome.RETRY_GATE,
                "summary": summary,
                "blocking_unresolved_ids": blocking_unresolved_ids,
                "fallback_payload": {
                    "kind": "blocking_flag_reprompt",
                    "blocking_unresolved_ids": list(blocking_unresolved_ids),
                },
            }

    if gate_summary["recommendation"] == "PROCEED" and gate_summary["passed"]:
        state["current_state"] = STATE_GATED
        state["meta"].pop("user_approved_gate", None)
        return {
            "result": result,
            "route_signal": route_signal,
            "summary": summary,
            "blocking_unresolved_ids": [],
            "fallback_payload": None,
        }
    state["current_state"] = STATE_CRITIQUED
    if gate_summary["recommendation"] == "PROCEED":
        result = "blocked"
        preflight_results = gate_summary.get("preflight_results", {})
        if (
            isinstance(preflight_results, dict)
            and only_agent_availability_preflight_failed(preflight_results)
        ):
            summary = (
                "Gate recommended PROCEED, but agent availability preflight failed. "
                "Repair the command PATH and rerun gate, or use force-proceed."
            )
            fallback_payload = {
                "kind": "preflight_failed",
                "reason": "agent_availability_only",
                "allow_force_proceed": True,
            }
            return {
                "result": result,
                "route_signal": "blocked_preflight",
                "summary": summary,
                "blocking_unresolved_ids": [],
                "fallback_payload": fallback_payload,
            }
        summary = "Gate recommended PROCEED, but preflight checks are still blocking execution."
        return {
            "result": result,
            "route_signal": "blocked_preflight",
            "summary": summary,
            "blocking_unresolved_ids": [],
            "fallback_payload": {
                "kind": "preflight_failed",
                "reason": "blocking_checks",
                "allow_force_proceed": False,
            },
        }
    if gate_summary["recommendation"] == "ITERATE":
        # Layer 0 backstop: bound the critique loop. Mirror the execute-review
        # rework cap (review.py:238-254). Count prior ITERATE rounds; at the
        # cap, terminate via the severity-gated branch (escalate on an open
        # correctness/security flag, else force-proceed-with-note).
        no_progress_streak = _critique_no_progress_streak(state, gate_summary, plan_dir)
        prior_rounds = _prior_iterate_rounds(state)
        max_iter = _effective_critique_cap(robustness)
        no_progress_cap = _revise_loop_termination_policy()["no_progress_cap"]
        max_no_progress = get_effective(
            str(no_progress_cap["config_scope"]),
            str(no_progress_cap["config_key"]),
        )
        if prior_rounds >= max_iter:
            return _critique_terminate_branch(
                state,
                gate_summary,
                f"Max critique iterations ({max_iter}) reached",
            )
        if no_progress_streak >= max_no_progress:
            return _critique_terminate_branch(
                state,
                gate_summary,
                f"Critique loop made no net progress for {no_progress_streak} consecutive rounds",
            )
        return {
            "result": result,
            "route_signal": route_signal,
            "summary": summary,
            "blocking_unresolved_ids": [],
            "fallback_payload": None,
        }
    if gate_summary["recommendation"] == "ESCALATE":
        return {
            "result": result,
            "route_signal": route_signal,
            "summary": summary,
            "blocking_unresolved_ids": [],
            "fallback_payload": None,
        }
    if gate_summary["recommendation"] == "TIEBREAKER":
        return {
            "result": "tiebreaker_recommended",
            "route_signal": route_signal,
            "summary": summary,
            "blocking_unresolved_ids": [],
            "fallback_payload": None,
        }
    result = "unknown_recommendation"
    summary = f"Gate returned unknown recommendation '{gate_summary['recommendation']}'; treating as escalation."
    return {
        "result": result,
        "route_signal": "escalate",
        "summary": summary,
        "blocking_unresolved_ids": [],
        "fallback_payload": {
            "kind": "unknown_recommendation",
            "recommendation": gate_summary["recommendation"],
        },
    }

def _merge_gate_worker_attempt(base: WorkerResult, retry: WorkerResult) -> WorkerResult:
    base.payload = retry.payload
    base.raw_output = "\n\n".join(part for part in [base.raw_output, retry.raw_output] if part)
    if base.trace_output or retry.trace_output:
        base.trace_output = "\n\n".join(part for part in [base.trace_output, retry.trace_output] if part)
    base.duration_ms += retry.duration_ms
    base.cost_usd += retry.cost_usd
    base.session_id = retry.session_id or base.session_id
    base.prompt_tokens += retry.prompt_tokens
    base.completion_tokens += retry.completion_tokens
    base.total_tokens += retry.total_tokens
    base.rate_limit = prefer_retry_rate_limit(base.rate_limit, retry.rate_limit)
    return base

def _merge_resolution_tradeoffs_into_payload(gate_summary: dict[str, Any], worker_payload: dict[str, Any]) -> None:
    raw_tradeoffs = worker_payload.get("accepted_tradeoffs", [])
    merged_tradeoffs = list(raw_tradeoffs) if isinstance(raw_tradeoffs, list) else []
    existing_ids = {
        item.get("flag_id")
        for item in merged_tradeoffs
        if isinstance(item, dict) and isinstance(item.get("flag_id"), str)
    }
    unresolved_by_id = {
        flag.get("id"): flag
        for flag in gate_summary.get("unresolved_flags", [])
        if isinstance(flag, dict) and isinstance(flag.get("id"), str)
    }
    for resolution in gate_summary.get("flag_resolutions", []):
        if not isinstance(resolution, dict) or resolution.get("action") != "accept_tradeoff":
            continue
        flag_id = resolution.get("flag_id")
        if not isinstance(flag_id, str) or flag_id in existing_ids:
            continue
        flag = unresolved_by_id.get(flag_id)
        if not isinstance(flag, dict):
            continue
        concern = flag.get("concern")
        if not isinstance(concern, str):
            continue
        tradeoff = {"flag_id": flag_id, "concern": concern}
        subsystem = flag.get("subsystem")
        if isinstance(subsystem, str) and subsystem.strip():
            tradeoff["subsystem"] = subsystem
        merged_tradeoffs.append(tradeoff)
        existing_ids.add(flag_id)
    worker_payload["accepted_tradeoffs"] = merged_tradeoffs

def _prior_unresolved_flag_ids(plan_dir: Path, current_iteration: int) -> set[str]:
    """Return flag IDs from the prior gate pass (iteration-1)."""
    if current_iteration <= 1:
        return set()
    prev_path = plan_dir / f"gate_signals_v{current_iteration - 1}.json"
    try:
        import json as _json
        data = _json.loads(prev_path.read_text(encoding="utf-8"))
        return {
            f.get("id") for f in data.get("unresolved_flags", [])
            if isinstance(f, dict) and f.get("id")
        }
    except FileNotFoundError:
        return set()
    except _json.JSONDecodeError:
        _warn_read_fallback(
            "M3A_WARN_CORRUPT_PRIOR_FLAGS",
            path=prev_path,
            reason="corrupt_json",
            context={"iteration": current_iteration - 1},
        )
        return set()
    except (OSError, UnicodeDecodeError):
        _warn_read_fallback(
            "M3A_WARN_CORRUPT_PRIOR_FLAGS",
            path=prev_path,
            reason="unreadable",
            context={"iteration": current_iteration - 1},
        )
        return set()


def _normalize_gate_payload(
    gate_payload: dict[str, Any],
    _signals_artifact: dict[str, Any],
) -> dict[str, Any]:
    """Normalize values without synthesizing required contract fields."""
    recommendation = str(gate_payload.get("recommendation", "")).strip().upper()
    if recommendation:
        gate_payload["recommendation"] = recommendation
    return gate_payload


def _build_reprompt_downgrade_route(
    gate_summary: dict[str, Any],
    blocking_unresolved_ids: list[str],
) -> tuple[dict[str, Any], str]:
    downgrade_policy = _gate_reprompt_policy()["downgrade_on_unresolved_blockers"]
    gate_summary["recommendation"] = str(downgrade_policy["recommendation"])
    gate_summary["passed"] = bool(downgrade_policy["passed"])
    gate_summary["rationale"] = (
        f"{gate_summary['rationale']} "
        f"[Auto-downgraded from PROCEED: {len(blocking_unresolved_ids)} "
        "blocking flag(s) not resolved after reprompt]"
    )
    gate_summary["orchestrator_guidance"] = (
        "Gate auto-downgraded to ITERATE because blocking flags remained "
        "unresolved after reprompt. Revise the plan."
    )
    summary = f"Gate recommendation {gate_summary['recommendation']}: {gate_summary['rationale']}"
    return (
        {
            "result": "blocked",
            "route_signal": GateOutcome(str(downgrade_policy["route_signal"])),
            "summary": summary,
            "blocking_unresolved_ids": [],
            "fallback_payload": {
                "kind": downgrade_policy["fallback_kind"],
                "blocking_unresolved_ids": list(blocking_unresolved_ids),
            },
        },
        summary,
    )


def handle_gate(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="gate") as (plan_dir, state):
        post_revise_gate = _post_revise_gate_allowed(state, plan_dir)
        if not post_revise_gate:
            require_state(state, "gate", {STATE_CRITIQUED})
        else:
            _append_to_meta(state, "post_revise_gate_iterations", state["iteration"])
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        iteration = state["iteration"]
        gate_signals, signals_filename, signals_artifact = _build_gate_signals_artifact(plan_dir, state, iteration=iteration, root=root)
        resolved = _pkg.resolve_agent_mode("gate", args)
        worker, agent, mode, refreshed = _run_worker(
            "gate",
            state,
            plan_dir,
            args,
            root=root,
            resolved=resolved,
        )

        # ── T10: Scratch promotion (first attempt) ──────────────────
        # Prefer valid filled gate_output.json over worker.payload;
        # fall back to worker.payload when scratch is missing/unmodified;
        # fail hard on modified invalid scratch when file-fill was
        # instructed (hermes agent).
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
            promote_scratch,
            require_scratch_filename_for_phase,
        )

        _scratch_filename = require_scratch_filename_for_phase("gate")
        _seed_path = plan_dir / _scratch_filename
        _seed_json: str | None = None
        if _seed_path.exists():
            try:
                _seed_json = _seed_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                _seed_json = None

        _file_fill_instructed = agent == "hermes"

        _scratch_status, _promoted = promote_scratch(
            plan_dir,
            _scratch_filename,
            schema_property_names(
                SCHEMAS["gate.json"],
                contract="gate scratch promotion",
            ),
            worker,
            seed_json=_seed_json,
            file_fill_instructed=_file_fill_instructed,
        )
        worker.payload = _promoted

        # ── T9: Structured promotion evidence (first attempt) ─────
        _promotion_evidence = build_promotion_evidence(
            plan_dir,
            _scratch_status,
            phase_identity="gate",
            scratch_filename=_scratch_filename,
            worker_payload_used=_scratch_status in ("missing", "unmodified"),
        )
        if _promotion_evidence:
            log.debug(
                "gate promotion evidence: %s",
                [e["promotion_state"] for e in _promotion_evidence],
            )
        # ───────────────────────────────────────────────────────────
        # ────────────────────────────────────────────────────────────

        gate_payload = _normalize_gate_payload(worker.payload, signals_artifact)
        worker.payload = gate_payload
        try:
            audit_step_payload("gate", gate_payload)
        except ModelStructuralAuditError as error:
            _raise_step_validation_error(
                plan_dir=plan_dir,
                state=state,
                step="gate",
                iteration=iteration,
                worker=worker,
                code="invalid_gate",
                message=f"Gate output failed schema audit: {error.details}",
            )
        strict_notes_flag = bool(state["config"].get("strict_notes", False))
        guidance = build_orchestrator_guidance(
            gate_payload=gate_payload,
            signals=signals_artifact["signals"],
            preflight_passed=all(signals_artifact["preflight_results"].values()),
            preflight_results=signals_artifact["preflight_results"],
            robustness=signals_artifact.get("robustness", "standard"),
            plan_name=state["name"],
            strict_notes=strict_notes_flag,
        )
        gate_summary = build_gate_artifact(
            signals_artifact,
            gate_payload,
            override_forced=False,
            orchestrator_guidance=guidance,
        )
        gate_summary["reprompted"] = False

        if len(state["meta"].get("weighted_scores", [])) < iteration:
            _append_to_meta(state, "weighted_scores", gate_signals["signals"]["weighted_score"])
        route_signal = _build_gate_route_signal(
            state,
            gate_summary,
            robustness=gate_signals["robustness"],
            plan_dir=plan_dir,
        )
        result = route_signal["result"]
        summary = route_signal["summary"]
        blocking_unresolved_ids = list(route_signal["blocking_unresolved_ids"])
        if result == "tiebreaker_recommended":
            result, next_step, summary = _validate_tiebreaker(
                state, gate_summary, plan_dir, worker, args, agent,
                resolved, signals_artifact, gate_signals, root,
            )
            route_signal["result"] = result
            route_signal["summary"] = summary
            route_signal["route_signal"] = (
                "proceed" if next_step == "finalize"
                else "iterate" if next_step == "revise"
                else "escalate"
            )
        if blocking_unresolved_ids:
            reprompt_prompt = _build_gate_prompt_override(
                agent,
                state,
                plan_dir,
                root=root,
                missing_flag_ids=blocking_unresolved_ids,
            )
            retry_worker, _, _, _ = _run_worker(
                "gate",
                state,
                plan_dir,
                args,
                root=root,
                resolved=resolved,
                prompt_override=reprompt_prompt,
            )

            # ── T10: Scratch promotion (reprompt) ───────────────────
            # Same promotion semantics as the first attempt: prefer
            # filled gate_output.json, fall back to worker.payload when
            # missing/unmodified, fail hard on modified invalid scratch
            # under file-fill instruction.
            _retry_seed_path = plan_dir / _scratch_filename
            _retry_seed_json: str | None = None
            if _retry_seed_path.exists():
                try:
                    _retry_seed_json = _retry_seed_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    _retry_seed_json = None

            _retry_scratch_status, _retry_promoted = promote_scratch(
                plan_dir,
                _scratch_filename,
                schema_property_names(
                    SCHEMAS["gate.json"],
                    contract="gate scratch reprompt promotion",
                ),
                retry_worker,
                seed_json=_retry_seed_json,
                file_fill_instructed=_file_fill_instructed,
            )
            retry_worker.payload = _retry_promoted

            # ── T9: Structured promotion evidence (reprompt) ─────
            _retry_promotion_evidence = build_promotion_evidence(
                plan_dir,
                _retry_scratch_status,
                phase_identity="gate",
                scratch_filename=_scratch_filename,
                worker_payload_used=_retry_scratch_status in ("missing", "unmodified"),
            )
            if _retry_promotion_evidence:
                log.debug(
                    "gate reprompt promotion evidence: %s",
                    [e["promotion_state"] for e in _retry_promotion_evidence],
                )
            # ────────────────────────────────────────────────────────
            # ────────────────────────────────────────────────────────

            worker = _merge_gate_worker_attempt(worker, retry_worker)
            gate_payload = _normalize_gate_payload(worker.payload, signals_artifact)
            worker.payload = gate_payload
            try:
                audit_step_payload("gate", gate_payload)
            except ModelStructuralAuditError as error:
                _raise_step_validation_error(
                    plan_dir=plan_dir,
                    state=state,
                    step="gate",
                    iteration=iteration,
                    worker=worker,
                    code="invalid_gate",
                    message=f"Gate output failed schema audit: {error.details}",
                )
            guidance = build_orchestrator_guidance(
                gate_payload=gate_payload,
                signals=signals_artifact["signals"],
                preflight_passed=all(signals_artifact["preflight_results"].values()),
                preflight_results=signals_artifact["preflight_results"],
                robustness=signals_artifact.get("robustness", "standard"),
                plan_name=state["name"],
                strict_notes=strict_notes_flag,
            )
            gate_summary = build_gate_artifact(
                signals_artifact,
                gate_payload,
                override_forced=False,
                orchestrator_guidance=guidance,
            )
            gate_summary["reprompted"] = True
            route_signal = _build_gate_route_signal(
                state,
                gate_summary,
                robustness=gate_signals["robustness"],
                plan_dir=plan_dir,
            )
            result = route_signal["result"]
            summary = route_signal["summary"]
            blocking_unresolved_ids = list(route_signal["blocking_unresolved_ids"])
            if blocking_unresolved_ids:
                route_signal, summary = _build_reprompt_downgrade_route(
                    gate_summary,
                    blocking_unresolved_ids,
                )
                result = route_signal["result"]
        _normalize_settled_decisions(gate_summary)
        _merge_resolution_tradeoffs_into_payload(gate_summary, worker.payload)
        _write_gate_carry(plan_dir, gate_summary, iteration=iteration)
        gate_hash = _write_gate_json(plan_dir, gate_summary)
        try:
            from arnold_pipelines.megaplan.observability.work_ledger import (
                WorkClass,
                emit_transition_activity,
                emit_worker_inference,
            )

            emit_worker_inference(
                plan_dir,
                phase="gate",
                worker=worker,
                work_class=WorkClass.REVIEW_PROOF,
                attempt_id=state.get("meta", {}).get("current_invocation_id"),
                agent=agent,
                model_calls=2 if gate_summary.get("reprompted") else 1,
                metadata={
                    "recommendation": gate_summary.get("recommendation"),
                    "route_signal": route_signal.get("route_signal"),
                    "boundary": "gate_worker",
                    "reprompted": bool(gate_summary.get("reprompted")),
                },
            )
            emit_transition_activity(
                plan_dir,
                phase="gate",
                transition="gate_route_signal",
                from_state=STATE_CRITIQUED,
                to_state=STATE_GATED if gate_summary.get("recommendation") == "PROCEED" else STATE_PLANNED,
                metadata={
                    "recommendation": gate_summary.get("recommendation"),
                    "route_signal": route_signal.get("route_signal"),
                },
            )
        except Exception:
            log.debug("Work ledger gate event emission skipped", exc_info=True)

        # Emit flag_raised / flag_resolved based on delta vs prior gate pass
        raised: set[str] = set()
        resolved: set[str] = set()
        try:
            from arnold_pipelines.megaplan.observability.events import emit, EventKind
            new_flag_ids = {
                f.get("id") for f in gate_summary.get("unresolved_flags", [])
                if isinstance(f, dict) and f.get("id")
            }
            old_flag_ids = _prior_unresolved_flag_ids(plan_dir, iteration)
            raised = new_flag_ids - old_flag_ids
            resolved = old_flag_ids - new_flag_ids
            for fid in raised:
                emit(EventKind.FLAG_RAISED, plan_dir=plan_dir, phase="gate", payload={"flag_id": fid})
            for fid in resolved:
                emit(EventKind.FLAG_RESOLVED, plan_dir=plan_dir, phase="gate", payload={"flag_id": fid})
        except Exception:
            _warn_best_effort_emit_failure(
                "M3A_WARN_EMIT_FLAG_EVENT",
                action="gate-flag-delta",
                plan_dir=plan_dir,
                phase="gate",
                context={"raised": len(raised), "resolved": len(resolved)},
            )

        debt_entries_added = 0
        if gate_summary["recommendation"] == "PROCEED":
            debt_entries_added = _record_gate_debt_entries(root, state, gate_summary, worker.payload)
        _sync_legacy_last_gate_for_workflow(state, gate_summary)
        emitter = getattr(args, "progress_emitter", None)
        if emitter is not None and gate_summary["recommendation"] in {"ESCALATE", "TIEBREAKER"}:
            emitter.gate_pending(
                f"{state['name']}:gate:{iteration}",
                summary=summary,
                recommendation=gate_summary["recommendation"],
                rationale=gate_summary["rationale"],
                next_step=response_next_step if (response_next_step := route_signal.get("route_signal")) else None,
                state=state["current_state"],
            )
        return _finish_step(
            plan_dir,
            state,
            args,
            step="gate",
            worker=worker,
            agent=agent,
            mode=mode,
            refreshed=refreshed,
            summary=summary,
            artifacts=[signals_filename, "gate.json", "gate_carry.json"],
            output_file="gate.json",
            artifact_hash=gate_hash,
            result=result,
            success=gate_summary["recommendation"] != "PROCEED" or gate_summary["passed"],
            gate_summary=gate_summary,
            response_fields={
                **_gate_response_fields(state, gate_summary, debt_entries_added),
                "route_signal": route_signal.get("route_signal"),
                "gate_signal": {
                    "recommendation": gate_summary["recommendation"],
                    "route_signal": route_signal.get("route_signal"),
                    "result": result,
                },
                "debt_payload": _gate_debt_payload(gate_summary, debt_entries_added),
                "fallback_payload": route_signal.get("fallback_payload") or {},
            },
            history_fields={"recommendation": gate_summary["recommendation"]},
        )


from arnold_pipelines.megaplan.flags import update_flags_after_gate
