from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.execute.batch import (
    handle_execute_auto_loop,
    handle_execute_one_batch,
    normalize_tier_map,
)
from arnold_pipelines.megaplan.fallback_chains import (
    configured_fallback_chain_for_phase,
    select_fallback_spec,
)
from arnold_pipelines.megaplan.profiles import apply_profile_expansion
from arnold_pipelines.megaplan.types import (
    CliError,
    PlanState,
    StepResponse,
)
from arnold_pipelines.megaplan.planning.state import (
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_BLOCKED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FAILED,
    STATE_FINALIZED,
)
from arnold.pipeline.step_io_contract import StepIOOperation
from arnold_pipelines.megaplan.runtime.schema_registry_adapter import create_step_io_contract_context
from arnold_pipelines.megaplan.store import PlanRepository, write_plan_artifact_json
from arnold_pipelines.megaplan.model_seam import audit_step_payload
from arnold_pipelines.megaplan._core import (
    clear_active_step,
    configured_robustness,
    is_prose_mode,
    latest_plan_meta_path,
    load_plan_locked,
    read_json,
    require_state,
    save_state_merge_meta,
    set_active_step,
    workflow_includes_step,
)
from arnold_pipelines.megaplan._core.io import read_plan_state_cached
from arnold_pipelines.megaplan.workers import warn_if_work_dir_differs_from_project_dir
from arnold_pipelines.megaplan.runtime.execution_environment import preflight_mutating_phase

from .shared import (
    _active_step_fallback_fields,
    _agent_mode_parts,
    _emit_phase_notice,
    attach_agent_fallback,
    worker_module,
)
from arnold_pipelines.megaplan.orchestration.phase_result import _emit_phase_result, phase_result_guard, BlockedTask, Deviation

# Canonical execute-phase defaults (rehomed from stages/execute.py during M3 T24).
EXECUTE_DEFAULTS: Mapping[str, Any] = {
    "user_approved": True,
    "confirm_destructive": True,
}


def _is_rework_reexecution(state: PlanState) -> bool:
    """Check if the last completed step was a review with needs_rework."""
    for entry in reversed(state.get("history", [])):
        if entry.get("step") == "review" and entry.get("result") == "needs_rework":
            return True
        if entry.get("step") == "execute":
            return False
    return False

def _is_blocked_retry(state: PlanState) -> bool:
    """Check if the last execute attempt was blocked (quality gate failure)."""
    for entry in reversed(state.get("history", [])):
        if entry.get("step") == "execute":
            return entry.get("result") == "blocked"
        if entry.get("step") in ("review", "finalize"):
            return False
    return False


def _record_execute_blocked(plan_dir: Path, response: StepResponse) -> None:
    repo = PlanRepository.from_plan_dir(plan_dir)
    artifact = repo.latest_execution_batch_artifact()
    repo.record_lifecycle_failure(
        kind="execution_blocked",
        message="execute returned result=blocked from quality gates",
        current_state=STATE_BLOCKED,
        phase="execute",
        resume_cursor={"phase": "execute", "batch_index": None, "retry_strategy": "fresh_session"},
        last_artifact=artifact.name if artifact is not None else None,
        suggested_action="Review blocking deviations and resume execute with a fresh worker session.",
        metadata={"response": dict(response)},
    )


def _extract_execute_tier_map(tier_models: object) -> dict[int, str] | None:
    """Return the execute tier map in the legacy int-keyed routing shape."""
    if not isinstance(tier_models, dict):
        return None
    execute_tiers = tier_models.get("execute")
    if not isinstance(execute_tiers, dict) or not execute_tiers:
        return None
    normalized: dict[int, str] = {}
    for raw_tier, raw_spec in execute_tiers.items():
        if isinstance(raw_tier, bool):
            continue
        selected_spec: str | None = None
        if isinstance(raw_spec, str) and raw_spec.strip():
            selected_spec = raw_spec
        elif isinstance(raw_spec, list):
            selected_spec = select_fallback_spec(
                raw_spec,
                0,
                path=f"tier_models.execute.{raw_tier}",
            )
        if not selected_spec:
            continue
        if isinstance(raw_tier, int):
            normalized[raw_tier] = selected_spec
            continue
        if isinstance(raw_tier, str) and raw_tier.isdigit():
            normalized[int(raw_tier)] = selected_spec
    return normalized or None


def _execute_phase_model_is_pinned(args: argparse.Namespace, state: PlanState) -> bool:
    """Return true when execute has an explicit phase-model override.

    A pinned execute model is authoritative for the whole execute phase,
    including per-batch routing. Chain resumes may carry the pin only in
    persisted state while profile expansion has already populated
    ``args.tier_models``; checking both sources prevents stale profile execute
    tiers from overriding the pin inside ``handle_execute_auto_loop``.
    """

    phase_models = list(getattr(args, "phase_model", None) or [])
    state_phase_models = (state.get("config") or {}).get("phase_model")
    if isinstance(state_phase_models, list):
        phase_models.extend(entry for entry in state_phase_models if isinstance(entry, str))
    return configured_fallback_chain_for_phase(phase_models, "execute") is not None


def _apply_execute_tier_cap(
    tier_map: dict[int, str] | None,
    max_execute_tier: object,
) -> dict[int, str] | None:
    if tier_map is None:
        return None
    if isinstance(max_execute_tier, bool):
        return tier_map
    try:
        cap = int(max_execute_tier)
    except (TypeError, ValueError):
        return tier_map
    if cap < 1:
        return tier_map
    cap_spec = tier_map.get(cap)
    if not cap_spec:
        return tier_map
    capped = dict(tier_map)
    for tier in list(capped):
        if tier > cap:
            capped[tier] = cap_spec
    return capped

def handle_execute(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="execute") as (plan_dir, state):
        require_state(state, "execute", {STATE_FINALIZED, STATE_BLOCKED, STATE_FAILED})
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        # Loud operator warning if the resolved sandbox root is narrower than
        # the plan's stored project_dir. Silent divergence here cost entire
        # execute runs in the past (codex sandboxed to a subdirectory, writes
        # to sibling subrepos failed silently).
        warn_if_work_dir_differs_from_project_dir(state)
        plan_mode = state["config"].get("mode", "code")
        if not is_prose_mode(state) and not args.confirm_destructive:
            raise CliError("missing_confirmation", "Execute requires --confirm-destructive")
        auto_approve = bool(state["config"].get("auto_approve", False))
        if getattr(args, "user_approved", False):
            state["meta"]["user_approved_gate"] = True
            save_state_merge_meta(plan_dir, state)
        if not auto_approve and not state["meta"].get("user_approved_gate", False):
            raise CliError(
                "missing_approval",
                "Execute requires explicit user approval (--user-approved) when auto-approve is not set. The orchestrator must confirm with the user at the gate checkpoint before proceeding.",
            )
        preflight_mutating_phase(root=root, state=state, phase="execute")
        save_state_merge_meta(plan_dir, state)
        am = worker_module.resolve_agent_mode("execute", args)
        agent, mode, refreshed, model = _agent_mode_parts(am)
        # Pull the resolved (default-applied) model + effort directly off the
        # AgentMode so they survive downstream. ``_agent_mode_parts`` returns the
        # *unresolved* ``model`` for backward compatibility, but the codex CLI
        # needs the resolved one (e.g. "gpt-5.5") to avoid hanging on a default
        # endpoint, and the session-key SHA must match what ``run_codex_step``
        # uses (which is keyed by resolved_model). See diagnostic
        # /tmp/codex_wedge_diagnostic.md.
        from arnold_pipelines.megaplan.types import AgentMode as _AgentMode  # local import to avoid cycle at module load
        if isinstance(am, _AgentMode):
            effort = am.effort
            resolved_model = am.resolved_model if am.resolved_model is not None else model
        else:
            effort = None
            resolved_model = model
        # Force fresh session after review kickback or blocked retry to avoid
        # prior-context bias (poisoned environment beliefs, stale task state).
        if not refreshed and (_is_rework_reexecution(state) or _is_blocked_retry(state)):
            refreshed = True
        if agent == "codex" and refreshed:
            # Key the session pop by the *resolved* model so it actually matches
            # the key ``run_codex_step`` writes (which uses resolved_model).
            state["sessions"].pop(
                worker_module.session_key_for("execute", "codex", model=resolved_model),
                None,
            )
        # Detect tier_models.execute from profile expansion.  If present,
        # pass the tier map down to the dispatchers so they can route
        # per-batch by task complexity.  apply_profile_expansion already
        # strips tier_models.execute when a CLI --phase-model execute=...
        # override is present, so no double-check is needed here.
        if _execute_phase_model_is_pinned(args, state):
            tier_map = None
        else:
            tier_map = _extract_execute_tier_map(getattr(args, "tier_models", None))
        tier_map = _apply_execute_tier_cap(
            tier_map,
            getattr(args, "max_execute_tier", None)
            if getattr(args, "max_execute_tier", None) is not None
            else state["config"].get("max_execute_tier"),
        )
        run_id = set_active_step(
            state,
            step="execute",
            agent=agent,
            mode=mode,
            model=model,
            **_active_step_fallback_fields("execute", args, agent=agent, model=model),
        )
        _emit_phase_notice("execute")
        save_state_merge_meta(plan_dir, state)
        response: StepResponse | None = None
        try:
            with phase_result_guard(plan_dir):
                if getattr(args, "batch", None) is not None:
                    response = handle_execute_one_batch(
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
                        effort=effort,
                        resolved_model=resolved_model,
                        tier_map=tier_map,
                    )
                else:
                    response = handle_execute_auto_loop(
                        root=root,
                        plan_dir=plan_dir,
                        state=state,
                        args=args,
                        auto_approve=auto_approve,
                        agent=agent,
                        mode=mode,
                        refreshed=refreshed,
                        model=model,
                        effort=effort,
                        resolved_model=resolved_model,
                        tier_map=tier_map,
                    )
        except CliError:
            clear_active_step(state, run_id=run_id)
            save_state_merge_meta(plan_dir, state)
            raise
        clear_active_step(state, run_id=run_id)
        if response.get("result") == "blocked":
            save_state_merge_meta(plan_dir, state)
            _record_execute_blocked(plan_dir, response)
            state = read_plan_state_cached(plan_dir, mode="authority")
            response["state"] = STATE_BLOCKED
            response["next_step"] = None
            response.pop("next_step_runtime", None)
        else:
            state["latest_failure"] = None
            state.pop("resume_cursor", None)
        if is_prose_mode(state) and response.get("state") == STATE_EXECUTED:
            from arnold_pipelines.megaplan.runtime.doc_assembly import assemble_doc
            output_path = Path(state["config"]["project_dir"]) / state["config"]["output_path"]
            finalize_data = read_json(plan_dir / "finalize.json")
            assemble_doc(plan_dir, output_path, finalize_data)
        robustness = configured_robustness(state)
        with_feedback = state.get("config", {}).get("with_feedback", False)
        if not workflow_includes_step(robustness, "review") and not workflow_includes_step(robustness, "feedback", with_feedback=with_feedback) and response.get("state") == STATE_EXECUTED:
            if robustness == "bare":
                # bare skips review entirely — no stub artifact, no deferred-must check.
                # If any success criteria need human verification, they'll surface
                # through the normal awaiting-human path on the next run.
                state["current_state"] = STATE_DONE
                save_state_merge_meta(plan_dir, state)
                response["state"] = STATE_DONE
                response["next_step"] = None
                response.pop("next_step_runtime", None)
                attach_agent_fallback(response, args)
                return response
            from arnold_pipelines.megaplan.audits.capabilities import get_worker_capabilities
            from arnold_pipelines.megaplan.orchestration.verifiability import classify_criteria

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

            next_state = STATE_AWAITING_HUMAN_VERIFY if has_deferred_must else STATE_DONE

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
            audit_step_payload("review", stub_review)
            write_plan_artifact_json(
                plan_dir, "review.json", stub_review,
                contract_context=create_step_io_contract_context(
                    operation=StepIOOperation.WRITE,
                    explicit_root=plan_dir,
                ),
            )
            artifacts = response.get("artifacts")
            if isinstance(artifacts, list) and "review.json" not in artifacts:
                artifacts.append("review.json")
            state["current_state"] = next_state
            save_state_merge_meta(plan_dir, state)
            response["state"] = next_state
            response["next_step"] = None
            response.pop("next_step_runtime", None)
        else:
            save_state_merge_meta(plan_dir, state)
        attach_agent_fallback(response, args)
        # Emit phase_result.json from the dispatcher's _phase_outcome marker
        if response is not None:
            outcome = response.get("_phase_outcome", "success")
            bt_ids: list[str] = list(response.get("blocked_task_ids", []))
            bt_notes: dict[str, str] = response.get("blocked_task_notes", {})
            if isinstance(bt_notes, dict):
                pass
            else:
                bt_notes = {}
            blocked = tuple(
                BlockedTask(task_id=tid, reason="blocked_by_prereq",
                            notes=bt_notes.get(tid, ""))
                for tid in bt_ids
            ) if outcome == "blocked_by_prereq" else ()

            dev_raw = response.get("deviations", [])
            if outcome == "blocked_by_quality" and dev_raw:
                devs: tuple[Deviation, ...] = tuple(
                    Deviation.from_string(d) if isinstance(d, str)
                    else Deviation(
                        kind=str(d.get("kind", "quality_gate")),
                        message=str(d.get("message", "")),
                        task_id=d.get("task_id"),
                        blocker_id=d.get("blocker_id"),
                        phase=d.get("phase"),
                    )
                    for d in dev_raw
                    if isinstance(d, (str, dict))
                )
            else:
                devs = ()

            _emit_phase_result(
                phase="execute",
                state=state,
                plan_dir=plan_dir,
                exit_kind=outcome,
                blocked_tasks=blocked,
                deviations=devs,
                artifacts_written=tuple(response.get("artifacts", [])),
            )
            response.pop("_phase_outcome", None)
            response.pop("blocked_task_notes", None)
        return response
