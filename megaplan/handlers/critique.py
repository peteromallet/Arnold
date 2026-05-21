from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from megaplan import handlers as _pkg
from megaplan.audits.robustness import validate_critique_checks
from megaplan.forms.provocations import select_active_checks
from megaplan.forms.directors_notes import update_directors_notes_at_aggregate
from megaplan.orchestration.evaluation import build_gate_artifact, build_orchestrator_guidance, compute_plan_delta_percent, compute_recurring_critiques
from megaplan.orchestration.parallel_critique import run_parallel_critique
from megaplan.profiles import apply_profile_expansion
from megaplan.types import (
    CliError,
    FLAG_BLOCKING_STATUSES,
    PlanState,
    STATE_CRITIQUED,
    STATE_GATED,
    STATE_PLANNED,
    STATE_TIEBREAKER_PENDING,
    StepResponse,
)
from megaplan.workers import WorkerResult, validate_payload
from megaplan._core import (
    atomic_write_json,
    configured_robustness,
    is_creative_mode,
    latest_plan_meta_path,
    latest_plan_path,
    load_plan_locked,
    now_utc,
    read_json,
    record_step_failure,
    require_state,
    clear_active_step,
    save_flag_registry,
    save_state_merge_meta,
    scope_creep_flags,
    sha256_file,
    set_active_step,
    workflow_includes_step,
)

from .plan import _build_verifiability_flags, _merge_imported_decision_criteria
from .shared import _append_to_meta, _finish_step, _raise_step_validation_error, _write_plan_version
from .tiebreaker import _build_tiebreaker_reprompt

def handle_critique(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="critique") as (plan_dir, state):
        require_state(state, "critique", {STATE_PLANNED})
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        iteration = state["iteration"]
        robustness = configured_robustness(state)
        state["last_gate"] = {}
        critique_filename = f"critique_v{iteration}.json"
        if robustness == "bare":
            raise CliError(
                "bare_skips_critique",
                "bare robustness skips critique entirely; the workflow routes plan -> finalize directly. "
                "Run `megaplan finalize` instead, or use --robustness light if you want a critique pass.",
            )
        active_checks = select_active_checks(state, robustness, plan_dir=plan_dir)
        expected_ids = [check["id"] for check in active_checks]
        resolved = _pkg.resolve_agent_mode("critique", args)
        agent_type, mode, refreshed, model = resolved.agent, resolved.mode, resolved.refreshed, resolved.model
        if len(active_checks) > 1 and agent_type == "hermes":
            run_id = set_active_step(state, step="critique", agent="hermes", mode="persistent", model=model)
            save_state_merge_meta(plan_dir, state)
            try:
                worker = run_parallel_critique(state, plan_dir, root=root, model=model, checks=active_checks)
                agent, mode, refreshed = "hermes", "persistent", True
            except Exception as exc:
                clear_active_step(state, run_id=run_id)
                save_state_merge_meta(plan_dir, state)
                print(f"[parallel-critique] Failed, falling back to sequential: {exc}", file=sys.stderr)
                worker, agent, mode, refreshed = _pkg._run_worker(
                    "critique",
                    state,
                    plan_dir,
                    args,
                    root=root,
                    resolved=(agent_type, mode, refreshed, model),
                )
            else:
                clear_active_step(state, run_id=run_id)
        else:
            worker, agent, mode, refreshed = _pkg._run_worker(
                "critique",
                state,
                plan_dir,
                args,
                root=root,
                resolved=(agent_type, mode, refreshed, model),
            )
        invalid_checks = validate_critique_checks(worker.payload, expected_ids=expected_ids)
        if invalid_checks:
            recovered_payload = _recover_valid_critique_output(plan_dir, expected_ids=expected_ids)
            if recovered_payload is None:
                _raise_step_validation_error(plan_dir=plan_dir, state=state, step="critique", iteration=iteration, worker=worker, code="invalid_critique", message="Critique output failed check validation: " + ", ".join(invalid_checks))
            worker = WorkerResult(
                payload=recovered_payload,
                raw_output=worker.raw_output + "\n[megaplan] recovered critique payload from critique_output.json",
                duration_ms=worker.duration_ms,
                cost_usd=worker.cost_usd,
                session_id=worker.session_id,
                trace_output=worker.trace_output,
                rendered_prompt=worker.rendered_prompt,
                model_actual=worker.model_actual,
                prompt_tokens=worker.prompt_tokens,
                completion_tokens=worker.completion_tokens,
                total_tokens=worker.total_tokens,
            )


        from megaplan.audits.capabilities import get_worker_capabilities
        from megaplan.audits.verifiability import audit_criteria, validate_requires

        plan_meta = read_json(latest_plan_meta_path(plan_dir, state))
        success_criteria = plan_meta.get("success_criteria", [])
        v_worker_caps = get_worker_capabilities(state)
        v_flags = _build_verifiability_flags(success_criteria, v_worker_caps)
        if v_flags:
            worker.payload.setdefault("flags", []).extend(v_flags)

        atomic_write_json(plan_dir / critique_filename, worker.payload)
        if is_creative_mode(state):
            fired = [
                check.get("provocation", {})
                for check in active_checks
                if isinstance(check, dict) and isinstance(check.get("provocation"), dict)
            ]
            voice = next(
                (
                    check.get("provocateur_voice")
                    for check in active_checks
                    if isinstance(check, dict) and check.get("provocateur_voice")
                ),
                None,
            )
            update_directors_notes_at_aggregate(
                plan_dir,
                state,
                {"task_updates": []},
                iteration=iteration,
                voice=voice,
                fired_provocations=fired,
            )
        registry = update_flags_after_critique(plan_dir, worker.payload, iteration=iteration)
        significant = len([flag for flag in registry["flags"] if flag.get("severity") == "significant" and flag["status"] in FLAG_BLOCKING_STATUSES])
        _append_to_meta(state, "significant_counts", significant)
        recurring = compute_recurring_critiques(plan_dir, iteration)
        _append_to_meta(state, "recurring_critiques", recurring)
        state["current_state"] = STATE_CRITIQUED
        skip_gate = not workflow_includes_step(robustness, "gate")
        if skip_gate:
            minimal_gate: dict[str, Any] = {
                "recommendation": "ITERATE",
                "rationale": "Light robustness: single revision pass to incorporate critique feedback.",
                "signals_assessment": "",
                "warnings": [],
                "settled_decisions": [],
            }
            atomic_write_json(plan_dir / "gate.json", minimal_gate)
            state["last_gate"] = {"recommendation": "ITERATE"}
        scope_flags_list = scope_creep_flags(registry, statuses=FLAG_BLOCKING_STATUSES)
        open_flags_detail = [
            {"id": flag["id"], "concern": flag["concern"], "category": flag["category"], "severity": flag.get("severity", "unknown")}
            for flag in registry["flags"]
            if flag["status"] == "open"
        ]
        response_fields: dict[str, Any] = {
            "iteration": iteration,
            "checks": worker.payload.get("checks", []),
            "verified_flags": worker.payload.get("verified_flag_ids", []),
            "open_flags": open_flags_detail,
            "scope_creep_flags": [flag["id"] for flag in scope_flags_list],
        }
        if scope_flags_list:
            response_fields["warnings"] = ["Scope creep detected in the plan. Surface this drift to the user while continuing the loop."]
        return _finish_step(
            plan_dir, state, args,
            step="critique",
            worker=worker, agent=agent, mode=mode, refreshed=refreshed,
            summary=f"Recorded {len(worker.payload.get('flags', []))} critique flags.",
            artifacts=[critique_filename, "faults.json"],
            output_file=critique_filename,
            artifact_hash=sha256_file(plan_dir / critique_filename),
            response_fields=response_fields,
            history_fields={"flags_count": len(worker.payload.get("flags", []))},
        )


def _recover_valid_critique_output(plan_dir: Path, *, expected_ids: list[str]) -> dict[str, Any] | None:
    output_path = plan_dir / "critique_output.json"
    if not output_path.exists():
        return None
    payload = read_json(output_path)
    invalid_checks = validate_critique_checks(payload, expected_ids=expected_ids)
    if invalid_checks:
        return None
    validate_payload("critique", payload)
    return payload


def handle_revise(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="revise") as (plan_dir, state):
        require_state(state, "revise", {STATE_CRITIQUED})
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        has_gate, revise_transition = _resolve_revise_transition(state)
        previous_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
        revise_start_iso = now_utc()
        notes_consumed = [
            n["timestamp"]
            for n in state["meta"].get("notes", [])
            if isinstance(n, dict) and "timestamp" in n
        ]
        worker, agent, mode, refreshed = _pkg._run_worker(
            "revise",
            state,
            plan_dir,
            args,
            root=root,
            iteration=state["iteration"] + 1,
        )
        # Record audit fields on the revise receipt: which notes existed at the
        # moment we ran revise (so a future force-proceed can tell if notes
        # arrived after the last revise) and when revise started.
        worker.receipt_metrics = {
            "start_timestamp_utc": revise_start_iso,
            "notes_consumed": notes_consumed,
            "notes_consumed_count": len(notes_consumed),
        }
        if worker.cost_usd > 5.0:
            error = CliError(
                "revise_cost_sanity_guard",
                "revise cost exceeded $5.00; aborting to avoid a possible session-cache loop. See ticket 01KRXNZZGRV17PHZRJ2Q56SPS3.",
                extra={
                    "step": "revise",
                    "cost_usd": worker.cost_usd,
                    "session_id": worker.session_id,
                    "prompt_tokens": worker.prompt_tokens,
                    "completion_tokens": worker.completion_tokens,
                    "ticket": "01KRXNZZGRV17PHZRJ2Q56SPS3",
                },
            )
            record_step_failure(
                plan_dir,
                state,
                step="revise",
                iteration=state["iteration"] + 1,
                error=error,
                duration_ms=worker.duration_ms,
            )
            raise error
        payload = worker.payload
        validate_payload("revise", payload)
        payload["success_criteria"] = _merge_imported_decision_criteria(
            state,
            payload.get("success_criteria", []),
        )
        version = state["iteration"] + 1
        plan_text = payload["plan"].rstrip() + "\n"
        delta = compute_plan_delta_percent(previous_plan, plan_text)
        try:
            plan_filename, meta_filename, meta = _write_plan_version(
                plan_dir=plan_dir, state=state, step="revise", version=version,
                worker=worker, plan_filename=f"plan_v{version}.md", plan_text=plan_text,
                meta_fields={
                    "changes_summary": payload["changes_summary"],
                    "flags_addressed": payload["flags_addressed"],
                    "questions": payload.get("questions", []),
                    "success_criteria": payload.get("success_criteria", []),
                    "assumptions": payload.get("assumptions", []),
                    "delta_from_previous_percent": delta,
                },
            )
        except CliError as error:
            if error.code == "cache_hit_suspected":
                record_step_failure(
                    plan_dir,
                    state,
                    step="revise",
                    iteration=version,
                    error=error,
                    duration_ms=worker.duration_ms,
                )
            raise
        state["iteration"], state["current_state"] = version, revise_transition.next_state
        state["meta"].pop("user_approved_gate", None)
        if has_gate:
            state["last_gate"] = {}
        state["plan_versions"].append({
            "version": version, "file": plan_filename,
            "hash": meta["hash"], "timestamp": meta["timestamp"],
        })
        _append_to_meta(state, "plan_deltas", delta)
        update_flags_after_revise(plan_dir, payload["flags_addressed"], plan_file=plan_filename, summary=payload["changes_summary"])
        next_step = _next_progress_step(state)
        remaining = _remaining_significant_flags(plan_dir)
        return _finish_step(
            plan_dir, state, args,
            step="revise",
            worker=worker, agent=agent, mode=mode, refreshed=refreshed,
            summary=f"Updated plan to v{version}; addressed {len(payload['flags_addressed'])} flags.",
            artifacts=[plan_filename, meta_filename, "faults.json"],
            output_file=plan_filename,
            artifact_hash=meta["hash"],
            next_step=next_step,
            response_fields={
                "iteration": version,
                "changes_summary": payload["changes_summary"],
                "flags_addressed": payload["flags_addressed"],
                "flags_remaining": remaining,
                "plan_delta_percent": delta,
            },
            history_fields={"flags_addressed": payload["flags_addressed"]},
        )

def _validate_tiebreaker(
    state: PlanState,
    gate_summary: dict[str, Any],
    plan_dir: Path,
    worker: WorkerResult,
    args: argparse.Namespace,
    agent: str,
    resolved: tuple,
    signals_artifact: dict[str, Any],
    gate_signals: dict[str, Any],
    root: Path,
) -> tuple[str, str, str]:
    """Validate a TIEBREAKER gate recommendation. Returns (result, next_step, summary)."""
    from megaplan.audits.iteration import compute_iteration_pressure, has_mechanical_recurrence

    config = state.get("config", {})
    summary_base = f"Gate recommendation TIEBREAKER: {gate_summary['rationale']}"

    if not config.get("allow_tiebreaker", True):
        gate_summary["recommendation"] = "ITERATE"
        gate_summary["rationale"] += " [Auto-downgraded: tiebreaker disabled for this plan]"
        state["current_state"] = STATE_CRITIQUED
        return "tiebreaker_rejected_disabled", "revise", summary_base

    tiebreaker_count = state["meta"].get("tiebreaker_count", 0)
    max_tiebreakers = config.get("max_tiebreakers_per_plan", 2)
    if tiebreaker_count >= max_tiebreakers:
        gate_summary["recommendation"] = "ESCALATE"
        gate_summary["rationale"] += " [Auto-downgraded to ESCALATE: tiebreaker budget exhausted]"
        state["current_state"] = STATE_CRITIQUED
        return "tiebreaker_rejected_budget", "override add-note", summary_base

    blocklist = config.get("tiebreaker_blocklist", [])
    tiebreaker_flag_ids = gate_summary.get("tiebreaker_flag_ids", [])
    if blocklist and tiebreaker_flag_ids:
        from megaplan._core import load_flag_registry as _load_flag_registry
        registry = _load_flag_registry(plan_dir)
        flag_by_id = {f["id"]: f for f in registry.get("flags", [])}
        for fid in tiebreaker_flag_ids:
            flag = flag_by_id.get(fid, {})
            if flag.get("category", "") in blocklist:
                gate_summary["recommendation"] = "ITERATE"
                gate_summary["rationale"] += f" [Auto-downgraded: flag {fid} category in tiebreaker blocklist]"
                state["current_state"] = STATE_CRITIQUED
                return "tiebreaker_rejected_blocklist", "revise", summary_base

    required_fields = ("tiebreaker_question", "tiebreaker_flag_ids", "tiebreaker_fuzzy_group_id")
    missing = [f for f in required_fields if not gate_summary.get(f)]
    if missing:
        gate_summary["recommendation"] = "ITERATE"
        gate_summary["rationale"] += f" [Auto-downgraded: missing required fields {missing}]"
        state["current_state"] = STATE_CRITIQUED
        return "tiebreaker_rejected_missing_fields", "revise", summary_base

    entries = compute_iteration_pressure(plan_dir, state)
    if not has_mechanical_recurrence(entries):
        reprompt_prompt = _build_tiebreaker_reprompt(agent, state, plan_dir, root=root)
        retry_worker, _, _, _ = _pkg._run_worker(
            "gate", state, plan_dir, args, root=root,
            resolved=resolved, prompt_override=reprompt_prompt,
        )
        worker = _merge_gate_worker_attempt(worker, retry_worker)
        retry_payload = worker.payload
        if retry_payload.get("recommendation") == "TIEBREAKER":
            entries_retry = compute_iteration_pressure(plan_dir, state)
            if not has_mechanical_recurrence(entries_retry):
                gate_summary["recommendation"] = "ITERATE"
                gate_summary["rationale"] += " [Auto-downgraded: no mechanical recurrence signal after reprompt]"
                state["current_state"] = STATE_CRITIQUED
                return "tiebreaker_rejected_no_signal", "revise", summary_base
        else:
            gate_summary["recommendation"] = retry_payload.get("recommendation", "ITERATE")
            gate_summary["rationale"] = retry_payload.get("rationale", gate_summary["rationale"])
            guidance = build_orchestrator_guidance(
                gate_payload=retry_payload,
                signals=signals_artifact["signals"],
                preflight_passed=all(signals_artifact["preflight_results"].values()),
                preflight_results=signals_artifact["preflight_results"],
                robustness=signals_artifact.get("robustness", "standard"),
                plan_name=state["name"],
                strict_notes=bool(state["config"].get("strict_notes", False)),
            )
            new_summary = build_gate_artifact(
                signals_artifact, retry_payload,
                override_forced=False, orchestrator_guidance=guidance,
            )
            gate_summary.update(new_summary)
            state["current_state"] = STATE_CRITIQUED
            if gate_summary["recommendation"] == "PROCEED" and gate_summary.get("passed"):
                state["current_state"] = STATE_GATED
                return "success", "finalize", f"Gate recommendation {gate_summary['recommendation']}: {gate_summary['rationale']}"
            return "success", "revise", f"Gate recommendation {gate_summary['recommendation']}: {gate_summary['rationale']}"

    state["current_state"] = STATE_TIEBREAKER_PENDING
    state["meta"]["tiebreaker_count"] = tiebreaker_count + 1
    return "tiebreaker_approved", "tiebreaker-run", summary_base


from .gate import _merge_gate_worker_attempt, _next_progress_step, _remaining_significant_flags, _resolve_revise_transition
from megaplan.flags import update_flags_after_critique, update_flags_after_revise
