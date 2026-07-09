from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Mapping

from arnold.workflow.boundary_evidence import AuthorityRecord, BoundaryOutcome, BoundaryReceipt
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
from arnold_pipelines.megaplan.receipts.writer import write_boundary_receipt
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
    infer_next_steps,
    is_prose_mode,
    latest_plan_meta_path,
    load_plan_locked,
    read_json,
    save_state_merge_meta,
    set_active_step,
    workflow_includes_step,
)
from arnold_pipelines.megaplan.execute.policy import (
    ApprovalOutcome,
    ExecuteEntryRoute,
    NextExecuteTransition,
    NoReviewTerminalOutcome,
    evaluate_destructive_approval,
    evaluate_no_review_terminal,
    resolve_execute_entry_route,
    resolve_single_batch_next_step,
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

log = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Typed-policy → legacy-payload translators.
#
# Entry dispatch, approval gating, no-review terminal routing, and next_step
# payloads are decided by the typed constructs in
# :mod:`arnold_pipelines.megaplan.execute.policy`.  The handler only translates
# those typed outcomes into legacy ``CliError`` raises / response-field writes;
# persistence and command-adapter dispatch remain handler-owned.
# ---------------------------------------------------------------------------

#: Typed no-review terminal outcomes → canonical plan state.
_NO_REVIEW_TERMINAL_STATE: Mapping[NoReviewTerminalOutcome, str] = {
    NoReviewTerminalOutcome.TERMINATE_DONE: STATE_DONE,
    NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN: STATE_AWAITING_HUMAN_VERIFY,
}

#: Typed no-review terminal outcomes → legacy ``next_step`` (always terminal).
_NO_REVIEW_NEXT_STEP: Mapping[NoReviewTerminalOutcome, str | None] = {
    NoReviewTerminalOutcome.TERMINATE_DONE: None,
    NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN: None,
}

#: Typed single-batch transitions → legacy ``next_step`` value.
_LEGACY_NEXT_STEP: Mapping[NextExecuteTransition, str | None] = {
    NextExecuteTransition.EXECUTE: "execute",
    NextExecuteTransition.REVIEW: "review",
    NextExecuteTransition.BLOCKED: None,
    NextExecuteTransition.DONE: None,
    NextExecuteTransition.AWAITING_HUMAN: None,
}


# ---------------------------------------------------------------------------
# Evidence-only execute boundary receipt emission
# ---------------------------------------------------------------------------


def _emit_execute_boundary_receipt(
    *,
    boundary_id: str,
    plan_dir: Path,
    state: PlanState,
    outcome: BoundaryOutcome,
    artifact_refs: tuple[str, ...] = (),
    approval_scope: str | None = None,
    session_freshness: bool | None = None,
    authority_actor: str | None = None,
    authority_role: str | None = None,
    authority_decision: str | None = None,
    extra_details: dict[str, Any] | None = None,
) -> None:
    """Emit an evidence-only execute boundary receipt without raising.

    Receipts are strictly observational — they do not affect branch
    decisions, state transitions, or route authority.
    """
    try:
        from arnold_pipelines.megaplan.workflows.boundary_contracts import (
            BOUNDARY_CONTRACTS_BY_ID,
        )
        contract = BOUNDARY_CONTRACTS_BY_ID.get(boundary_id)
        if contract is None:
            return

        meta = state.get("meta") or {}
        invocation_id = meta.get("current_invocation_id")
        project_dir = Path(state["config"]["project_dir"])

        details: dict[str, Any] = {
            "current_state": state.get("current_state"),
            "iteration": state.get("iteration"),
        }
        if approval_scope is not None:
            details["approval_scope"] = approval_scope
        if session_freshness is not None:
            details["session_freshness"] = session_freshness
        if extra_details:
            details.update(extra_details)

        authority_records: tuple[AuthorityRecord, ...] = ()
        if authority_actor and authority_role:
            authority_records = (
                AuthorityRecord(
                    actor=authority_actor,
                    role=authority_role,
                    decision=authority_decision,
                    scope=contract.details.get("approval_scope") or boundary_id,
                    details={
                        "approval_scope": approval_scope,
                        "session_freshness": session_freshness,
                    },
                ),
            )

        receipt = BoundaryReceipt(
            boundary_id=contract.boundary_id,
            workflow_id=contract.workflow_id,
            row_id=contract.row_id,
            invocation_id=invocation_id,
            artifact_refs=artifact_refs,
            state_observation={
                "current_phase": "execute",
                "current_state": state.get("current_state"),
                "iteration": state.get("iteration"),
            },
            history_ref=contract.expected_history_entry,
            phase_result_ref="phase_result.json" if contract.phase_result_required else None,
            outcome=outcome,
            authority_records=authority_records,
            details=details,
        )
        write_boundary_receipt(plan_dir, receipt, project_dir=project_dir)
    except Exception:
        log.warning(
            "Execute boundary receipt emission failed for %s", boundary_id, exc_info=True
        )


def _enforce_entry_route(state: PlanState) -> None:
    """Translate the typed execute-entry decision into a legacy ``CliError``.

    The admissible entry states are declared by the policy; the handler raises
    the historical ``invalid_transition`` error only when the typed route is
    ``INVALID``.  ``PROCEED``/``BLOCKED``/``FAILED`` fall through to batch
    dispatch (mirroring ``require_state(state, "execute", ...)``).
    """
    decision = resolve_execute_entry_route(state["current_state"])
    if decision.route is ExecuteEntryRoute.INVALID:
        raise CliError(
            "invalid_transition",
            f"Cannot run 'execute' while current state is '{state['current_state']}'",
            valid_next=infer_next_steps(state),
            extra={"current_state": state["current_state"]},
        )


def _enforce_approval_gate(
    *,
    confirm_destructive: bool,
    auto_approve: bool,
    user_approved_gate: bool,
    is_prose: bool,
) -> ApprovalOutcome:
    """Translate the typed approval decision into legacy ``CliError`` raises.

    Returns the resolved outcome so callers keep the persisted
    ``user_approved_gate`` in lock-step with the typed decision (the gate is
    only written once the decision clears).
    """
    decision = evaluate_destructive_approval(
        confirm_destructive=confirm_destructive,
        auto_approve=auto_approve,
        user_approved_gate=user_approved_gate,
        is_prose_mode=is_prose,
    )
    if decision.outcome is ApprovalOutcome.DENIED_MISSING_CONFIRM:
        raise CliError("missing_confirmation", decision.reason)
    if decision.outcome is ApprovalOutcome.DENIED_MISSING_APPROVAL:
        raise CliError("missing_approval", decision.reason)
    return decision.outcome


def handle_execute(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="execute") as (plan_dir, state):
        # Entry dispatch and approval gating are decided by typed policy
        # outcomes; the handler only translates those outcomes into legacy
        # CliErrors / state mutations (see execute.policy).
        _enforce_entry_route(state)
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        # Loud operator warning if the resolved sandbox root is narrower than
        # the plan's stored project_dir. Silent divergence here cost entire
        # execute runs in the past (codex sandboxed to a subdirectory, writes
        # to sibling subrepos failed silently).
        warn_if_work_dir_differs_from_project_dir(state)
        auto_approve = bool(state["config"].get("auto_approve", False))
        # The operator-approval gate is authoritative only after the destructive
        # confirmation clears, so the persisted gate is not written until the
        # typed decision is APPROVED.  ``effective_gate`` folds in a freshly
        # supplied ``--user-approved`` without side-effecting state first.
        effective_gate = bool(state["meta"].get("user_approved_gate", False)) or bool(
            getattr(args, "user_approved", False)
        )
        is_prose = is_prose_mode(state)
        try:
            _enforce_approval_gate(
                confirm_destructive=bool(getattr(args, "confirm_destructive", False)),
                auto_approve=auto_approve,
                user_approved_gate=effective_gate,
                is_prose=is_prose,
            )
        except CliError:
            # Evidence-only denial receipt before the error propagates.
            denial_scope = "denied_missing_confirm" if not is_prose and not getattr(args, "confirm_destructive", False) else "denied_missing_approval"
            _emit_execute_boundary_receipt(
                boundary_id="execute_approval_denial",
                plan_dir=plan_dir,
                state=state,
                outcome=BoundaryOutcome.INCOMPLETE,
                approval_scope=denial_scope,
                authority_actor="execute_handler",
                authority_role="approval_gate",
                authority_decision="denied",
            )
            raise
        # Approval cleared — emit evidence-only approval receipt.
        approval_scope = "execute:approval-approved"
        _emit_execute_boundary_receipt(
            boundary_id="execute_approval",
            plan_dir=plan_dir,
            state=state,
            outcome=BoundaryOutcome.COMPLETE,
            approval_scope=approval_scope,
            authority_actor="execute_handler",
            authority_role="approval_gate",
            authority_decision="approved",
        )
        if getattr(args, "user_approved", False):
            state["meta"]["user_approved_gate"] = True
            save_state_merge_meta(plan_dir, state)
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
        force_fresh = not refreshed and (_is_rework_reexecution(state) or _is_blocked_retry(state))
        if force_fresh:
            refreshed = True
            _emit_execute_boundary_receipt(
                boundary_id="execute_resume_anchor",
                plan_dir=plan_dir,
                state=state,
                outcome=BoundaryOutcome.COMPLETE,
                session_freshness=True,
                authority_actor="execute_handler",
                authority_role="session_manager",
                authority_decision="fresh_session",
                extra_details={"fresh_session_reason": "rework_or_blocked_retry"},
            )
        if agent == "codex" and refreshed:
            # Key the session pop by the *resolved* model so it actually matches
            # the key ``run_codex_step`` writes (which uses resolved_model).
            state["sessions"].pop(
                worker_module.session_key_for("execute", "codex", model=resolved_model),
                None,
            )
        # Detect tier_models.execute from profile expansion. If present, pass
        # the tier map down so execute batches route by task complexity.
        # Explicit execute pins strip tier_models.execute during profile
        # expansion/override handling; a surviving tier map is therefore
        # authoritative even when config.phase_model also carries the profile's
        # fallback execute=... default.
        tier_map = _extract_execute_tier_map(getattr(args, "tier_models", None))
        if tier_map is None and _execute_phase_model_is_pinned(args, state):
            tier_map = None
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
            # Include the typed retry decision (from
            # ``evaluate_blocker_recovery_policy``) in the blocked-anchor
            # evidence so semantic-health checks can verify the policy
            # outcome without re-deriving it.
            _retry_decision = response.get("_blocked_retry_decision") or {}
            _extra: dict[str, Any] = {
                "blocked_task_ids": response.get("blocked_task_ids", []),
                "deviations": response.get("deviations", []),
            }
            if _retry_decision:
                _extra["blocked_retry_decision"] = _retry_decision
            _emit_execute_boundary_receipt(
                boundary_id="execute_blocked_anchor",
                plan_dir=plan_dir,
                state=state,
                outcome=BoundaryOutcome.PARTIAL,
                session_freshness=refreshed,
                authority_actor="***",
                authority_role="***",
                authority_decision="***",
                extra_details=_extra,
            )
            _record_execute_blocked(plan_dir, response)
            state = read_plan_state_cached(plan_dir, mode="authority")
            response["state"] = STATE_BLOCKED
            # next_step payload is translated from the typed BLOCKED transition;
            # ``blocked=True`` is dominant in resolve_single_batch_next_step, so
            # the legacy value is always None (halt → override recovery).
            blocked_transition = resolve_single_batch_next_step(
                is_final_batch=(int(response.get("batches_remaining") or 0) == 0),
                all_tracked=False,
                blocked=True,
            ).transition
            response["next_step"] = _LEGACY_NEXT_STEP[blocked_transition]
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
                # Target state + next_step payload come from the typed no-review
                # terminal policy, not an inline branch.
                terminal = evaluate_no_review_terminal(robustness="bare")
                next_state = _NO_REVIEW_TERMINAL_STATE[terminal.outcome]
                state["current_state"] = next_state
                save_state_merge_meta(plan_dir, state)
                response["state"] = next_state
                response["next_step"] = _NO_REVIEW_NEXT_STEP[terminal.outcome]
                response.pop("next_step_runtime", None)
                _emit_execute_boundary_receipt(
                    boundary_id="execute_no_review_terminal",
                    plan_dir=plan_dir,
                    state=state,
                    outcome=BoundaryOutcome.COMPLETE,
                    extra_details={
                        "robustness": robustness,
                        "terminal_outcome": str(terminal.outcome.value),
                    },
                )
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

            # Target state + next_step payload come from the typed no-review
            # terminal policy (the topology gate above already guaranteed a
            # bare/light robustness, for which the policy always terminates).
            terminal = evaluate_no_review_terminal(
                robustness=robustness, has_deferred_must=has_deferred_must
            )
            next_state = _NO_REVIEW_TERMINAL_STATE[terminal.outcome]

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
            response["next_step"] = _NO_REVIEW_NEXT_STEP[terminal.outcome]
            response.pop("next_step_runtime", None)
            _emit_execute_boundary_receipt(
                boundary_id="execute_no_review_terminal",
                plan_dir=plan_dir,
                state=state,
                outcome=BoundaryOutcome.COMPLETE,
                extra_details={
                    "robustness": robustness,
                    "terminal_outcome": str(terminal.outcome.value),
                    "has_deferred_must": has_deferred_must,
                },
            )
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
