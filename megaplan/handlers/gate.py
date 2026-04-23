from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from megaplan import handlers as _pkg
from megaplan.evaluation import build_gate_artifact, build_gate_signals, build_orchestrator_guidance, is_rubber_stamp, run_gate_checks
from megaplan.profiles import apply_profile_expansion
from megaplan.types import FLAG_BLOCKING_STATUSES, CliError, PlanState, STATE_CRITIQUED, STATE_GATED, StepResponse
from megaplan.workers import WorkerResult
from megaplan._core import (
    add_or_increment_debt,
    atomic_write_json,
    configured_robustness,
    extract_subsystem_tag,
    find_command,
    infer_next_steps,
    load_debt_registry,
    load_flag_registry,
    load_plan_locked,
    require_state,
    save_debt_registry,
    workflow_includes_step,
    workflow_next,
    workflow_transition,
)

from .critique import _validate_tiebreaker
from .shared import _append_to_meta, _build_gate_prompt_override, _finish_step, _run_worker, _write_json_artifact, log

def _build_gate_signals_artifact(
    plan_dir: Path,
    state: PlanState,
    *,
    iteration: int,
    root: Path,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    gate_signals = build_gate_signals(plan_dir, state, root=root)
    gate_checks = run_gate_checks(plan_dir, state, command_lookup=find_command)
    signals_artifact = {
        "robustness": gate_signals["robustness"],
        "signals": gate_signals["signals"],
        "warnings": gate_signals.get("warnings", []),
        "criteria_check": gate_checks["criteria_check"],
        "preflight_results": gate_checks["preflight_results"],
        "unresolved_flags": gate_checks["unresolved_flags"],
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

def _resolve_revise_transition(state: PlanState) -> tuple[bool, Any]:
    has_gate = workflow_includes_step(configured_robustness(state), "gate")
    if has_gate and state["last_gate"].get("recommendation") != "ITERATE":
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

def _gate_response_fields(state: PlanState, gate_summary: dict[str, Any], debt_entries_added: int) -> dict[str, Any]:
    return {
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
        "orchestrator_guidance": gate_summary["orchestrator_guidance"],
        "signals": gate_summary["signals"],
        "debt_entries_added": debt_entries_added,
    }

def _store_last_gate(state: PlanState, gate_summary: dict[str, Any]) -> None:
    state["last_gate"] = {
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

def _apply_gate_outcome(
    state: PlanState,
    gate_summary: dict[str, Any],
    *,
    robustness: str,
    plan_dir: Path,
) -> tuple[str, str, str, list[str]]:
    result = "success"
    summary = f"Gate recommendation {gate_summary['recommendation']}: {gate_summary['rationale']}"

    # Process explicit flag resolutions when the gate recommends PROCEED.
    if gate_summary["recommendation"] == "PROCEED":
        unresolved = gate_summary.get("unresolved_flags", [])
        resolutions = gate_summary.get("flag_resolutions", [])

        # Validate each explicit resolution
        valid_resolved_ids: set[str] = set()
        for res in resolutions:
            action = res.get("action", "")
            flag_id = res.get("flag_id", "")
            if action == "dispute":
                evidence = res.get("evidence", "").strip()
                if not evidence or is_rubber_stamp(evidence, strict=True):
                    continue  # invalid dispute — skip
            elif action == "accept_tradeoff":
                rationale = res.get("rationale", "").strip()
                if not rationale or is_rubber_stamp(rationale, strict=True):
                    continue  # invalid tradeoff acceptance — skip
            else:
                continue  # unknown action — skip
            valid_resolved_ids.add(flag_id)

        blocking_unresolved = [
            f for f in unresolved
            if f.get("severity") in ("significant", "likely-significant")
            and f.get("status") in FLAG_BLOCKING_STATUSES
            and f.get("id") not in valid_resolved_ids
        ]
        blocking_unresolved_ids = [f.get("id", "") for f in blocking_unresolved if f.get("id")]

        # Persist explicit resolutions
        if valid_resolved_ids:
            update_flags_after_gate(plan_dir, resolutions)

        if blocking_unresolved_ids:
            return "unresolved_flags", "gate", summary, blocking_unresolved_ids

    if gate_summary["recommendation"] == "PROCEED" and gate_summary["passed"]:
        state["current_state"] = STATE_GATED
        state["meta"].pop("user_approved_gate", None)
        return result, "finalize", summary, []
    state["current_state"] = STATE_CRITIQUED
    if gate_summary["recommendation"] == "PROCEED":
        result = "blocked"
        summary = "Gate recommended PROCEED, but preflight checks are still blocking execution."
        return result, "revise", summary, []
    if gate_summary["recommendation"] == "ITERATE":
        return result, "revise", summary, []
    if gate_summary["recommendation"] == "ESCALATE":
        return result, "override add-note", summary, []
    if gate_summary["recommendation"] == "TIEBREAKER":
        return "tiebreaker_recommended", "tiebreaker", summary, []
    result = "unknown_recommendation"
    summary = f"Gate returned unknown recommendation '{gate_summary['recommendation']}'; treating as escalation."
    return result, "override add-note", summary, []

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

def handle_gate(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="gate") as (plan_dir, state):
        require_state(state, "gate", {STATE_CRITIQUED})
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
        gate_payload = worker.payload
        guidance = build_orchestrator_guidance(
            gate_payload=gate_payload,
            signals=signals_artifact["signals"],
            preflight_passed=all(signals_artifact["preflight_results"].values()),
            preflight_results=signals_artifact["preflight_results"],
            robustness=signals_artifact.get("robustness", "standard"),
            plan_name=state["name"],
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
        result, next_step, summary, blocking_unresolved_ids = _apply_gate_outcome(
            state,
            gate_summary,
            robustness=gate_signals["robustness"],
            plan_dir=plan_dir,
        )
        if result == "tiebreaker_recommended":
            result, next_step, summary = _validate_tiebreaker(
                state, gate_summary, plan_dir, worker, args, agent,
                resolved, signals_artifact, gate_signals, root,
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
            worker = _merge_gate_worker_attempt(worker, retry_worker)
            gate_payload = worker.payload
            guidance = build_orchestrator_guidance(
                gate_payload=gate_payload,
                signals=signals_artifact["signals"],
                preflight_passed=all(signals_artifact["preflight_results"].values()),
                preflight_results=signals_artifact["preflight_results"],
                robustness=signals_artifact.get("robustness", "standard"),
                plan_name=state["name"],
            )
            gate_summary = build_gate_artifact(
                signals_artifact,
                gate_payload,
                override_forced=False,
                orchestrator_guidance=guidance,
            )
            gate_summary["reprompted"] = True
            result, next_step, summary, blocking_unresolved_ids = _apply_gate_outcome(
                state,
                gate_summary,
                robustness=gate_signals["robustness"],
                plan_dir=plan_dir,
            )
            if blocking_unresolved_ids:
                gate_summary["recommendation"] = "ITERATE"
                gate_summary["passed"] = False
                gate_summary["rationale"] = (
                    f"{gate_summary['rationale']} "
                    f"[Auto-downgraded from PROCEED: {len(blocking_unresolved_ids)} "
                    "blocking flag(s) not resolved after reprompt]"
                )
                gate_summary["orchestrator_guidance"] = (
                    "Gate auto-downgraded to ITERATE because blocking flags remained "
                    "unresolved after reprompt. Revise the plan."
                )
                result = "blocked"
                next_step = "revise"
                summary = f"Gate recommendation {gate_summary['recommendation']}: {gate_summary['rationale']}"
        _merge_resolution_tradeoffs_into_payload(gate_summary, worker.payload)
        gate_hash = _write_json_artifact(plan_dir, "gate.json", gate_summary)
        debt_entries_added = 0
        if gate_summary["recommendation"] == "PROCEED":
            debt_entries_added = _record_gate_debt_entries(root, state, gate_summary, worker.payload)
        # Store last_gate AFTER _apply_gate_outcome — the outcome may override
        # the recommendation (e.g. PROCEED → ITERATE when flags are unresolved).
        _store_last_gate(state, gate_summary)
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
            artifacts=[signals_filename, "gate.json"],
            output_file="gate.json",
            artifact_hash=gate_hash,
            result=result,
            success=gate_summary["recommendation"] != "PROCEED" or gate_summary["passed"],
            next_step=next_step,
            response_fields=_gate_response_fields(state, gate_summary, debt_entries_added),
            history_fields={"recommendation": gate_summary["recommendation"]},
        )


from megaplan.flags import update_flags_after_gate
