from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from megaplan.execute.core import (
    handle_execute_auto_loop as dispatch_execute_auto_loop,
    handle_execute_one_batch as dispatch_execute_one_batch,
)
from megaplan.profiles import apply_profile_expansion
from megaplan.types import (
    CliError,
    PlanState,
    STATE_AWAITING_HUMAN,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FINALIZED,
    StepResponse,
)
from megaplan._core import (
    atomic_write_json,
    clear_active_step,
    configured_robustness,
    latest_plan_meta_path,
    load_plan_locked,
    read_json,
    require_state,
    save_state,
    set_active_step,
    workflow_includes_step,
)
from megaplan.workers import validate_payload

from .shared import _emit_phase_notice, attach_agent_fallback, worker_module

def _is_rework_reexecution(state: PlanState) -> bool:
    """Check if the last completed step was a review with needs_rework."""
    for entry in reversed(state.get("history", [])):
        if entry.get("step") == "review" and entry.get("result") == "needs_rework":
            return True
        if entry.get("step") == "execute":
            return False
    return False

def handle_execute(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="execute") as (plan_dir, state):
        require_state(state, "execute", {STATE_FINALIZED})
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        plan_mode = state["config"].get("mode", "code")
        if plan_mode not in {"doc", "joke"} and not args.confirm_destructive:
            raise CliError("missing_confirmation", "Execute requires --confirm-destructive")
        auto_approve = bool(state["config"].get("auto_approve", False))
        if getattr(args, "user_approved", False):
            state["meta"]["user_approved_gate"] = True
            save_state(plan_dir, state)
        if not auto_approve and not state["meta"].get("user_approved_gate", False):
            raise CliError(
                "missing_approval",
                "Execute requires explicit user approval (--user-approved) when auto-approve is not set. The orchestrator must confirm with the user at the gate checkpoint before proceeding.",
            )
        agent, mode, refreshed, model = worker_module.resolve_agent_mode("execute", args)
        # Force fresh session after review kickback to avoid prior-context bias
        if not refreshed and _is_rework_reexecution(state):
            refreshed = True
        run_id = set_active_step(state, step="execute", agent=agent, mode=mode, model=model)
        _emit_phase_notice("execute")
        save_state(plan_dir, state)
        try:
            if getattr(args, "batch", None) is not None:
                response = dispatch_execute_one_batch(
                    root=root,
                    plan_dir=plan_dir,
                    state=state,
                    args=args,
                    batch_number=args.batch,
                    auto_approve=auto_approve,
                    agent=agent,
                    mode=mode,
                    refreshed=refreshed,
                    model=model,
                )
            else:
                response = dispatch_execute_auto_loop(
                    root=root,
                    plan_dir=plan_dir,
                    state=state,
                    args=args,
                    auto_approve=auto_approve,
                    agent=agent,
                    mode=mode,
                    refreshed=refreshed,
                    model=model,
                )
        except CliError:
            clear_active_step(state, run_id=run_id)
            save_state(plan_dir, state)
            raise
        clear_active_step(state, run_id=run_id)
        if plan_mode in {"doc", "joke"} and response.get("state") == STATE_EXECUTED:
            from megaplan.doc_assembly import assemble_doc
            output_path = Path(state["config"]["project_dir"]) / state["config"]["output_path"]
            finalize_data = read_json(plan_dir / "finalize.json")
            assemble_doc(plan_dir, output_path, finalize_data)
        robustness = configured_robustness(state)
        if not workflow_includes_step(robustness, "review") and response.get("state") == STATE_EXECUTED:
            from megaplan.audits.capabilities import get_worker_capabilities
            from megaplan.audits.verifiability import classify_criteria

            plan_meta = read_json(latest_plan_meta_path(plan_dir, state))
            success_criteria = plan_meta.get("success_criteria", [])
            worker_caps = get_worker_capabilities(state)
            _, human_deferred = classify_criteria(success_criteria, worker_caps)

            stub_criteria = []
            has_deferred_must = False
            for sc in success_criteria:
                entry: dict[str, Any] = {
                    "name": sc.get("criterion", ""),
                    "priority": sc.get("priority", "info"),
                }
                if sc in human_deferred:
                    entry["pass"] = "deferred_human"
                    entry["evidence"] = "Requires human verification capabilities."
                    if sc.get("priority") == "must":
                        has_deferred_must = True
                else:
                    entry["pass"] = "pass"
                    entry["evidence"] = f"{robustness.title()} robustness: auto-approved."
                stub_criteria.append(entry)

            next_state = STATE_AWAITING_HUMAN if has_deferred_must else STATE_DONE

            stub_review = {
                "review_verdict": "approved",
                "checks": [],
                "pre_check_flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
                "criteria": stub_criteria,
                "issues": [],
                "rework_items": [],
                "summary": f"{robustness.title()} robustness: review skipped; stub written for artifact parity.",
                "task_verdicts": [],
                "sense_check_verdicts": [],
            }
            validate_payload("review", stub_review)
            atomic_write_json(plan_dir / "review.json", stub_review)
            artifacts = response.get("artifacts")
            if isinstance(artifacts, list) and "review.json" not in artifacts:
                artifacts.append("review.json")
            state["current_state"] = next_state
            save_state(plan_dir, state)
            response["state"] = next_state
            response["next_step"] = None
            response.pop("next_step_runtime", None)
        else:
            save_state(plan_dir, state)
        attach_agent_fallback(response, args)
        return response
