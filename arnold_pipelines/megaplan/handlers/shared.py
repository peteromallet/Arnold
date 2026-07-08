from __future__ import annotations

import argparse
import inspect
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import arnold_pipelines.megaplan.workers as worker_module
from arnold.workflow.boundary_evidence import AuthorityRecord, BoundaryOutcome, BoundaryReceipt
from arnold_pipelines.megaplan.execute.batch import build_monitor_hint
from arnold_pipelines.megaplan.fallback_chains import (
    configured_fallback_chain_for_phase,
    fallback_observability_fields,
)
from arnold_pipelines.megaplan.observability.routing_ledger import format_selected_spec
from arnold_pipelines.megaplan.profiles import apply_profile_expansion
from arnold_pipelines.megaplan.prompts import create_claude_prompt, create_codex_prompt, create_hermes_prompt
from arnold_pipelines.megaplan.receipts import build_receipt
from arnold_pipelines.megaplan.receipts.writer import write_boundary_receipt, write_receipt
from arnold_pipelines.megaplan.execute.step_edit import next_plan_artifact_name
from arnold_pipelines.megaplan.types import AgentMode, CliError, MOCK_ENV_VAR, PlanState, StepResponse
from arnold_pipelines.megaplan.orchestration.phase_result import (
    _emit_phase_result,
    phase_result_guard,
    BlockedTask,
    Deviation,
    ExitKind,
)
from arnold_pipelines.megaplan._core import (
    append_history,
    apply_session_update,
    atomic_write_json,
    atomic_write_text,
    build_next_step_runtime,
    clear_active_step,
    configured_robustness,
    get_effective,
    infer_next_steps,
    make_history_entry,
    now_utc,
    record_step_failure,
    save_state,
    save_state_merge_meta,
    set_active_step,
    sha256_file,
    sha256_text,
    workflow_next,
)
from arnold_pipelines.megaplan._core.phase_runtime import (
    DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    PHASE_RUNTIME_POLICY,
    format_duration_hint,
)
from arnold_pipelines.megaplan.orchestration.plan_structure import PLAN_STRUCTURE_REQUIRED_STEP_ISSUE, validate_plan_structure
from arnold_pipelines.megaplan.workflows.planning import resolve_lowered_route_target_for_signal
from arnold_pipelines.megaplan.workers import WorkerResult

log = logging.getLogger("megaplan")

_BOUNDARY_EXPECTED_NEXT_STEP_BY_ID = {
    "prep_to_plan": "plan",
    "plan_to_critique": "critique",
    "critique_to_gate": "gate",
    "gate_to_revise": "revise",
    "revise_to_critique": "critique",
}

_FRONT_HALF_BOUNDARY_ID_BY_PHASE = {
    "prep": "prep_to_plan",
    "plan": "plan_to_critique",
    "critique": "critique_to_gate",
    "gate": "gate_to_revise",
    "revise": "revise_to_critique",
}

_ROUTE_SIGNAL_AUTHORITY_STEP_ALIASES = {
    "tiebreaker_run": "tiebreaker_researcher",
    "tiebreaker_decide": "tiebreaker_decision",
}


def _agent_mode_parts(resolved: AgentMode | tuple[str, str, bool, str | None]) -> tuple[str, str, bool, str | None]:
    if isinstance(resolved, AgentMode):
        return resolved.agent, resolved.mode, resolved.refreshed, resolved.model
    return resolved


def _active_step_fallback_fields(
    step: str,
    args: argparse.Namespace,
    *,
    agent: str,
    model: str | None,
    effort: str | None = None,
) -> dict[str, Any]:
    configured = configured_fallback_chain_for_phase(getattr(args, "phase_model", None), step)
    selected_spec = format_selected_spec(agent, model, effort) or agent
    fields = fallback_observability_fields(configured.specs if configured is not None else selected_spec)
    return {
        "configured_specs": fields["configured_specs"],
        "attempt_index": fields["selected_spec_index"],
        "attempted_specs": fields["attempted_specs"],
        "failed_attempt_reasons": fields["failed_attempt_reasons"],
        "fallback_trigger": fields["fallback_trigger"],
    }


def _append_to_meta(state: PlanState, field: str, value: Any) -> None:
    state["meta"].setdefault(field, []).append(value)


def _merge_imported_decision_criteria(
    state: PlanState,
    criteria: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    imported_decisions = state["meta"].get("imported_decisions", [])
    if not imported_decisions:
        return criteria

    merged = list(criteria)
    referenced_ids = {
        decision_id
        for decision in imported_decisions
        for decision_id in [decision.get("id")]
        if isinstance(decision_id, str)
        and decision_id
        and any(
            decision_id in criterion_text
            for criterion in merged
            for criterion_text in [criterion.get("criterion")]
            if isinstance(criterion, dict) and isinstance(criterion_text, str)
        )
    }
    for decision in imported_decisions:
        decision_id = decision.get("id")
        if not isinstance(decision_id, str) or not decision_id or decision_id in referenced_ids:
            continue
        decision_text = decision.get("decision", "")
        if not isinstance(decision_text, str):
            decision_text = str(decision_text)
        load_bearing = bool(decision.get("load_bearing"))
        merged.append(
            {
                "criterion": f"Plan adheres to imported decision {decision_id}: {decision_text}",
                "priority": "must" if load_bearing else "info",
                "requires": ["subjective_judgment"] if load_bearing else [],
            }
        )
        referenced_ids.add(decision_id)
    return merged


def _validate_relative_path(project_dir: Path, raw: str, flag_name: str) -> str:
    candidate = Path(raw)
    if candidate.is_absolute():
        raise CliError(
            "invalid_args",
            f"{flag_name} must be a relative path inside the project directory",
        )
    if any(part == ".." for part in candidate.parts):
        raise CliError("invalid_args", f"{flag_name} must not contain '..' path traversal")
    resolved_path = (project_dir / candidate).resolve()
    try:
        return resolved_path.relative_to(project_dir).as_posix()
    except ValueError as exc:
        raise CliError(
            "invalid_args",
            f"{flag_name} must stay within the project directory",
        ) from exc


def attach_agent_fallback(response: StepResponse, args: argparse.Namespace) -> None:
    if hasattr(args, "_agent_fallback"):
        response["agent_fallback"] = args._agent_fallback


def _attach_next_step_runtime(response: StepResponse) -> None:
    runtime = build_next_step_runtime(
        response.get("next_step"),
        configured_timeout_seconds=int(get_effective("execution", "worker_timeout_seconds")),
    )
    if runtime is not None:
        response["next_step_runtime"] = runtime


def _warn_best_effort_emit_failure(
    token: str,
    *,
    action: str,
    plan_dir: Path | None = None,
    phase: str | None = None,
    event_kind: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    try:
        details: list[str] = [f"action={action}"]
        if event_kind:
            details.append(f"event_kind={event_kind}")
        if phase:
            details.append(f"phase={phase}")
        if plan_dir is not None:
            details.append(f"plan_dir={plan_dir}")
        if context:
            for key in sorted(context):
                details.append(f"{key}={context[key]!r}")
        log.warning(
            "%s best-effort observability emit failed (%s)",
            token,
            ", ".join(details),
            exc_info=True,
        )
    except Exception:
        pass


def _warn_read_fallback(
    token: str,
    *,
    path: Path | None = None,
    reason: str,
    context: dict[str, Any] | None = None,
) -> None:
    try:
        details: list[str] = [f"reason={reason}"]
        if path is not None:
            details.append(f"path={path}")
        if context:
            for key in sorted(context):
                details.append(f"{key}={context[key]!r}")
        log.warning("%s read fallback (%s)", token, ", ".join(details), exc_info=True)
    except Exception:
        pass


_AUTO_NEXT_STEP = object()


def _emit_phase_notice(step: str) -> None:
    if step not in PHASE_RUNTIME_POLICY:
        return
    duration_hint = format_duration_hint(
        step,
        configured_timeout_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    )
    log.info("[megaplan] Starting %s... %s", step, duration_hint)


def _run_worker(
    step: str,
    state: PlanState,
    plan_dir: Path,
    args: argparse.Namespace,
    *,
    root: Path,
    iteration: int | None = None,
    resolved: tuple[str, str, bool, str | None] | None = None,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
    read_only: bool = False,
) -> tuple[WorkerResult, str, str, bool]:
    failure_iteration = state["iteration"] if iteration is None else iteration
    from arnold_pipelines.megaplan import handlers as _handlers_pkg

    apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
    res = resolved or _handlers_pkg.resolve_agent_mode(step, args)
    agent = res.agent if isinstance(res, AgentMode) else res[0]
    mode = res.mode if isinstance(res, AgentMode) else res[1]
    refreshed = res.refreshed if isinstance(res, AgentMode) else res[2]
    model = res.resolved_model if isinstance(res, AgentMode) else res[3]
    effort = res.effort if isinstance(res, AgentMode) else None
    run_id = set_active_step(
        state,
        step=step,
        agent=agent,
        mode=mode,
        model=model,
        **_active_step_fallback_fields(step, args, agent=agent, model=model, effort=effort),
    )
    _emit_phase_notice(step)
    # Phases hold the lock for many minutes; merge meta to avoid clobbering
    # concurrent override appends to ``meta.notes`` / ``meta.overrides``.
    save_state_merge_meta(plan_dir, state)
    try:
        with phase_result_guard(plan_dir):
            run_step_kwargs: dict[str, Any] = {
                "root": root,
                "resolved": res,
                "prompt_override": prompt_override,
            }
            if prompt_kwargs is not None and _supports_prompt_kwargs(worker_module.run_step_with_worker):
                run_step_kwargs["prompt_kwargs"] = prompt_kwargs
            if read_only:
                run_step_kwargs["read_only"] = True
            return worker_module.run_step_with_worker(
                step,
                state,
                plan_dir,
                args,
                **run_step_kwargs,
            )
    except CliError as error:
        clear_active_step(state, run_id=run_id)
        record_step_failure(plan_dir, state, step=step, iteration=failure_iteration, error=error)
        raise
    except Exception:
        clear_active_step(state, run_id=run_id)
        save_state_merge_meta(plan_dir, state)
        raise


def _supports_prompt_kwargs(run_step: Callable[..., Any]) -> bool:
    params = inspect.signature(run_step).parameters.values()
    return any(param.name == "prompt_kwargs" for param in params) or any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in params
    )


def _build_gate_prompt_override(
    agent_type: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    missing_flag_ids: list[str],
) -> str:
    """Build a targeted gate reprompt that is scratch-file-aware.

    Does NOT rebuild the full base gate prompt (which would call
    ``_write_gate_template`` and overwrite the model's filled
    ``gate_output.json`` from the first attempt).  Instead, the reprompt
    references the **same** scratch path, instructs the model to read and
    **completely replace** its contents, and warns against writing to
    ``gate.json`` directly.
    """
    from arnold_pipelines.megaplan.prompts import _NESTED_HARNESS_GUARD

    scratch_path = plan_dir / "gate_output.json"
    missing_flags = ", ".join(missing_flag_ids)
    reprompt_body = (
        "GATE REPROMPT — SAME ITERATION, SAME SCRATCH FILE\n\n"
        "Your previous gate response recommended PROCEED but left blocking "
        "flags unresolved.  The scratch file at the path below still contains "
        "your prior attempt.\n\n"
        f"SCRATCH FILE: {scratch_path}\n\n"
        "WORKFLOW:\n"
        "1. Read the scratch file to see the template and your previous "
        "response.\n"
        "2. Produce a COMPLETE REPLACEMENT response — do NOT append or "
        "patch the existing content.  Every field must be filled fresh.\n"
        "3. Write the complete replacement JSON back to the SAME scratch "
        "file.\n\n"
        f"Missing blocking flag IDs that must be resolved: {missing_flags}\n\n"
        "REQUIREMENTS:\n"
        "- Return a complete gate response.  If you recommend PROCEED, you "
        "MUST include ``flag_resolutions`` entries for every blocking flag.\n"
        "- For addressed-but-unverified flags, the action MUST be "
        "``verify_fixed`` with concrete evidence from the revised plan; "
        "``dispute`` and ``accept_tradeoff`` do not clear addressed flags.\n"
        "- If you cannot resolve every blocking flag, return ITERATE or "
        "ESCALATE instead.\n"
        "- Write ONLY to the scratch file above.  Do NOT write to "
        "``gate.json`` or any other path — those are ignored by the "
        "harness.\n"
        "- If you cannot use file tools, return the populated JSON "
        "structure inline as your response instead."
    )
    return f"{_NESTED_HARNESS_GUARD}\n\n{reprompt_body}"


# ---------------------------------------------------------------------------
# Phase-result helpers for funneled handlers
# ---------------------------------------------------------------------------


def _derive_exit_kind_funneled(step: str, result: str, state: PlanState) -> str:
    """Derive ``exit_kind`` for the 6 funneled handlers.

    * ``step == "gate"`` and the result indicates a quality-gate block →
      ``blocked_by_quality``.
    * Everything else → ``success`` (funneled handlers don't have prereq
      blocks / timeouts — those come from execute).
    """
    if step == "gate" and result not in ("success",):
        return ExitKind.blocked_by_quality.value
    return ExitKind.success.value


def _extract_deviations_from_state(state: PlanState) -> tuple[Deviation, ...]:
    """Extract quality-gate deviation objects from *state*.

    Pulls from ``last_gate.warnings``; returns an empty tuple when there
    is nothing to report.
    """
    last_gate = state.get("last_gate")
    if not isinstance(last_gate, dict):
        return ()
    warnings = last_gate.get("warnings")
    if not isinstance(warnings, list) or not warnings:
        return ()
    return tuple(
        Deviation(kind="quality_gate", message=str(w), task_id=None)
        for w in warnings
    )


def _snapshot_cli_provenance(state: PlanState) -> dict[str, Any]:
    """Snapshot CLI-originated config keys so the driver can rehydrate them."""
    config = state.get("config", {})
    return {
        k: config.get(k)
        for k in (
            "phase_model",
            "profile",
            "auto_approve",
            "mode",
            "robustness",
            "max_execute_tier",
            "tier_models",
            "prep_models",
            "prep_model_resolver_trace",
        )
        if k in config
    }


# ---------------------------------------------------------------------------


def _emit_receipt(
    *,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
    worker: WorkerResult,
    agent: str,
    mode: str,
    phase: str,
    output_file: str,
    artifact_hash: str,
    verdict: Any = None,
) -> None:
    """Emit a receipt for *phase*, best-effort (warns on failure)."""
    try:
        project_dir = Path(state["config"]["project_dir"])
        receipt = build_receipt(
            phase=phase,
            state=state,
            plan_dir=plan_dir,
            args=args,
            worker=worker,
            agent=agent,
            mode=mode,
            output_file=output_file,
            artifact_hash=artifact_hash,
            verdict=verdict,
        )
        write_receipt(plan_dir, receipt, project_dir=project_dir)
    except Exception:
        log.warning("Receipt emission failed for step %s", phase, exc_info=True)


def _boundary_contract_by_phase(step: str):
    from arnold_pipelines.megaplan.workflows.boundary_contracts import BOUNDARY_CONTRACTS_BY_ID

    boundary_id = _FRONT_HALF_BOUNDARY_ID_BY_PHASE.get(step)
    if boundary_id is None:
        return None
    return BOUNDARY_CONTRACTS_BY_ID.get(boundary_id)


def _boundary_contract_for_response(
    step: str,
    response: StepResponse,
):
    contract = _boundary_contract_by_phase(step)
    if contract is None:
        return None
    expected_next_step = _BOUNDARY_EXPECTED_NEXT_STEP_BY_ID.get(contract.boundary_id)
    if expected_next_step is not None and response.get("next_step") != expected_next_step:
        return None
    return contract


def _boundary_history_snapshot(state: PlanState) -> dict[str, Any]:
    history = state.get("history")
    if not isinstance(history, list) or not history:
        return {}
    entry = history[-1]
    return dict(entry) if isinstance(entry, dict) else {}


def _boundary_session_snapshot(
    state: PlanState,
    *,
    session_id: str | None,
) -> dict[str, Any]:
    if not session_id:
        return {}
    sessions = state.get("sessions")
    if not isinstance(sessions, dict):
        return {}
    for session_key, session in sessions.items():
        if not isinstance(session, dict) or session.get("id") != session_id:
            continue
        snapshot = dict(session)
        snapshot["session_key"] = session_key
        return snapshot
    return {"id": session_id}


def _boundary_artifact_refs(
    *,
    plan_dir: Path,
    contract: Any,
    artifacts: list[str],
    output_file: str,
) -> tuple[str, ...]:
    refs: list[str] = []
    for ref in [*artifacts, output_file]:
        if isinstance(ref, str) and ref and ref not in refs:
            refs.append(ref)
    if contract.phase_result_required and "phase_result.json" not in refs:
        refs.append("phase_result.json")
    for required_artifact in contract.required_artifacts:
        if (
            isinstance(required_artifact, str)
            and required_artifact
            and (plan_dir / required_artifact).exists()
            and required_artifact not in refs
        ):
            refs.append(required_artifact)
    return tuple(refs)


def _boundary_authority_records(
    *,
    plan_dir: Path,
    contract: Any,
    worker: WorkerResult,
    agent: str,
    response: StepResponse,
) -> tuple[AuthorityRecord, ...]:
    if not contract.authority_required:
        return ()
    auth_metadata = worker.auth_metadata if isinstance(worker.auth_metadata, dict) else {}
    actor = str(auth_metadata.get("actor") or auth_metadata.get("authority_id") or worker.auth_channel or agent)
    role = str(auth_metadata.get("role") or auth_metadata.get("authority_role") or "boundary_observer")
    recommendation = response.get("recommendation")
    decision = str(recommendation) if isinstance(recommendation, str) and recommendation else None
    debt_payload = response.get("debt_payload")
    debt_entries_added = None
    if isinstance(debt_payload, dict):
        debt_entries_added = debt_payload.get("debt_entries_added")
    evidence_refs = tuple(
        ref
        for ref in ("gate.json", "gate_carry.json", "phase_result.json")
        if ref == "phase_result.json" or (plan_dir / ref).exists()
    )
    return (
        AuthorityRecord(
            actor=actor,
            role=role,
            decision=decision,
            scope=contract.boundary_id,
            evidence_refs=evidence_refs,
            details={
                "passed": response.get("passed"),
                "rationale": response.get("rationale"),
                "warnings": response.get("warnings"),
                "settled_decisions": response.get("settled_decisions"),
                "debt_entries_added": debt_entries_added,
                "auth_channel": worker.auth_channel,
                "auth_metadata": auth_metadata,
                "worker_channel": worker.worker_channel,
            },
        ),
    )


def _emit_boundary_receipt(
    *,
    plan_dir: Path,
    state: PlanState,
    step: str,
    worker: WorkerResult,
    agent: str,
    mode: str,
    artifacts: list[str],
    output_file: str,
    artifact_hash: str,
    response: StepResponse,
    run_id: str | None = None,
    gate_summary: dict[str, Any] | None = None,
) -> None:
    contract = _boundary_contract_for_response(step, response)
    if contract is None:
        return
    try:
        project_dir = Path(state["config"]["project_dir"])
        history_entry = _boundary_history_snapshot(state)
        session_entry = _boundary_session_snapshot(state, session_id=worker.session_id)
        details_dict: dict[str, Any] = {
            "artifact_hash": artifact_hash,
            "artifacts_written": list(artifacts),
            "history": {
                "step": history_entry.get("step"),
                "result": history_entry.get("result"),
                "timestamp": history_entry.get("timestamp"),
                "output_file": history_entry.get("output_file"),
            },
            "session": {
                "id": session_entry.get("id"),
                "session_key": session_entry.get("session_key"),
                "mode": mode,
                "worker_channel": session_entry.get("worker_channel") or worker.worker_channel,
                "auth_channel": session_entry.get("auth_channel") or worker.auth_channel,
            },
        }
        if run_id:
            details_dict["run_id"] = run_id
        # For gate_to_revise boundary, include gate_summary authority data
        # as receipt metadata so downstream consumers can cross-reference
        # gate decisions with boundary evidence without re-reading gate.json.
        if (
            gate_summary is not None
            and isinstance(gate_summary, dict)
            and contract.boundary_id == "gate_to_revise"
        ):
            details_dict["gate_authority"] = {
                "recommendation": gate_summary.get("recommendation"),
                "passed": gate_summary.get("passed"),
                "rationale": gate_summary.get("rationale"),
                "warnings": gate_summary.get("warnings"),
                "settled_decisions": gate_summary.get("settled_decisions"),
                "reprompted": gate_summary.get("reprompted"),
            }
        receipt = BoundaryReceipt(
            boundary_id=contract.boundary_id,
            workflow_id=contract.workflow_id,
            row_id=contract.row_id,
            invocation_id=(state.get("meta") or {}).get("current_invocation_id"),
            artifact_refs=_boundary_artifact_refs(
                plan_dir=plan_dir,
                contract=contract,
                artifacts=artifacts,
                output_file=output_file,
            ),
            state_observation={
                "current_phase": step,
                "current_state": state.get("current_state"),
                "iteration": state.get("iteration"),
                "next_step": response.get("next_step"),
            },
            history_ref=contract.expected_history_entry,
            phase_result_ref="phase_result.json" if contract.phase_result_required else None,
            outcome=BoundaryOutcome.COMPLETE,
            authority_records=_boundary_authority_records(
                plan_dir=plan_dir,
                contract=contract,
                worker=worker,
                agent=agent,
                response=response,
            ),
            details=details_dict,
        )
        write_boundary_receipt(plan_dir, receipt, project_dir=project_dir)
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_EMIT_BOUNDARY_RECEIPT",
            action="boundary-receipt",
            plan_dir=plan_dir,
            phase=step,
            context={"boundary_id": contract.boundary_id},
        )


def _finish_step(
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
    *,
    step: str,
    worker: WorkerResult,
    agent: str,
    mode: str,
    refreshed: bool,
    summary: str,
    artifacts: list[str],
    output_file: str,
    artifact_hash: str,
    result: str = "success",
    success: bool = True,
    next_step: object | str | None = _AUTO_NEXT_STEP,
    response_fields: dict[str, Any] | None = None,
    history_fields: dict[str, Any] | None = None,
    run_id: str | None = None,
    gate_summary: dict[str, Any] | None = None,
) -> StepResponse:
    # Capture run_id from state before clearing the active step.
    # Handlers that call _run_worker already have run_id stored in
    # state["active_step"]["run_id"]; extract it as a fallback so
    # boundary receipts carry the correct run_id for audit cross-
    # referencing without requiring every caller to plumb it explicitly.
    effective_run_id = run_id
    if effective_run_id is None:
        active = state.get("active_step")
        if isinstance(active, dict):
            effective_run_id = active.get("run_id")
    clear_active_step(state, run_id=run_id)
    if success and result == "success":
        state["latest_failure"] = None
        state.pop("resume_cursor", None)
    apply_session_update(
        state,
        step,
        agent,
        worker.session_id,
        mode=mode,
        refreshed=refreshed,
        worker_channel=worker.worker_channel,
        auth_channel=worker.auth_channel,
        auth_metadata=worker.auth_metadata,
    )
    append_history(
        state,
        make_history_entry(
            step,
            duration_ms=worker.duration_ms,
            cost_usd=worker.cost_usd,
            result=result,
            worker=worker,
            agent=agent,
            mode=mode,
            output_file=output_file,
            artifact_hash=artifact_hash,
            prompt_tokens=worker.prompt_tokens,
            completion_tokens=worker.completion_tokens,
            total_tokens=worker.total_tokens,
            **(history_fields or {}),
        ),
    )
    if step not in {"execute", "review"}:
        _emit_receipt(
            plan_dir=plan_dir,
            state=state,
            args=args,
            worker=worker,
            agent=agent,
            mode=mode,
            phase=step,
            output_file=output_file,
            artifact_hash=artifact_hash,
            verdict=(history_fields or {}).get("verdict"),
        )
    save_state_merge_meta(plan_dir, state)
    resolved_next = next_step
    if resolved_next is _AUTO_NEXT_STEP:
        next_steps = workflow_next(state)
        resolved_next = next_steps[0] if next_steps else None
    response: StepResponse = {
        "success": success,
        "step": step,
        "summary": summary,
        "artifacts": artifacts,
        "monitor_hint": build_monitor_hint(plan_dir),
        "next_step": resolved_next,
        "state": state["current_state"],
    }
    if response_fields:
        response.update(response_fields)
    route_signal = response.get("route_signal")
    route_target = None
    if isinstance(route_signal, str) and route_signal:
        authority_step = _ROUTE_SIGNAL_AUTHORITY_STEP_ALIASES.get(step, step)
        route_target = resolve_lowered_route_target_for_signal(authority_step, route_signal)
    if route_target is not None:
        response["next_step"] = route_target
    _attach_next_step_runtime(response)
    attach_agent_fallback(response, args)
    # Emit the canonical phase_result.json for the auto driver
    _emit_phase_result(
        phase=step,
        state=state,
        plan_dir=plan_dir,
        exit_kind=_derive_exit_kind_funneled(step, result, state),
        blocked_tasks=(),
        deviations=_extract_deviations_from_state(state),
        artifacts_written=tuple(artifacts),
        cli_provenance=_snapshot_cli_provenance(state),
    )
    _emit_boundary_receipt(
        plan_dir=plan_dir,
        state=state,
        step=step,
        worker=worker,
        agent=agent,
        mode=mode,
        artifacts=artifacts,
        output_file=output_file,
        artifact_hash=artifact_hash,
        response=response,
        run_id=effective_run_id,
        gate_summary=gate_summary,
    )
    return response


def _raise_step_validation_error(
    *,
    plan_dir: Path,
    state: PlanState,
    step: str,
    iteration: int,
    worker: WorkerResult,
    code: str,
    message: str,
) -> None:
    error = CliError(code, message, valid_next=infer_next_steps(state), extra={"raw_output": worker.raw_output})
    record_step_failure(plan_dir, state, step=step, iteration=iteration, error=error, duration_ms=worker.duration_ms)
    raise error


def _write_json_artifact(plan_dir: Path, filename: str, payload: dict[str, Any]) -> str:
    atomic_write_json(plan_dir / filename, payload, _plan_dir=plan_dir)
    return sha256_file(plan_dir / filename)


def _write_gate_json(plan_dir: Path, payload: dict[str, Any]) -> str:
    """Write gate.json through _write_json_artifact and return the hash."""
    return _write_json_artifact(plan_dir, "gate.json", payload)


def _normalize_plan_text(plan_text: str) -> str:
    """Decode escaped newlines some models emit inside JSON plan strings.

    When a model returns a JSON object whose ``plan`` field contains literal
    ``\\n`` (or ``\\r\\n``) characters instead of real newlines, the Markdown
    validator sees a single physical line and fails to find step headings.
    Detect that pattern and decode the escapes so the plan is valid Markdown.
    """
    # Fast path: already contains real newlines; leave it alone.
    if "\n" in plan_text:
        return plan_text
    # If the text contains literal \\n but no real newlines, decode them.
    if "\\n" in plan_text or "\\r" in plan_text:
        decoded = plan_text.encode("utf-8").decode("unicode_escape")
        # unicode_escape may turn actual Unicode into latin-1 approximations in
        # some Python versions; re-encode/decode via raw_unicode_escape to keep
        # the original code points. Fall back to the decoded string if that fails.
        try:
            decoded = decoded.encode("raw_unicode_escape").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        decoded = decoded.replace("\r\n", "\n").replace("\r", "\n")
        if "\n" in decoded:
            return decoded
    return plan_text


def _write_plan_version(
    *,
    plan_dir: Path,
    state: PlanState,
    step: str,
    version: int,
    worker: WorkerResult,
    plan_text: str,
    meta_fields: dict[str, Any],
    plan_filename: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    plan_text = _normalize_plan_text(plan_text)
    resolved_plan_filename = plan_filename or next_plan_artifact_name(plan_dir, version)
    meta_filename = (
        f"plan_v{version}.meta.json"
        if resolved_plan_filename == f"plan_v{version}.md"
        else resolved_plan_filename.replace(".md", ".meta.json")
    )
    structure_warnings = _validate_generated_plan_or_raise(
        plan_dir=plan_dir,
        state=state,
        step=step,
        iteration=version,
        worker=worker,
        plan_text=plan_text,
    )
    new_hash = sha256_text(plan_text)
    prior_version = (
        state.get("plan_versions", [])[-1]
        if state.get("plan_versions")
        else None
    )
    is_primary_plan_artifact = resolved_plan_filename == f"plan_v{version}.md"
    if (
        is_primary_plan_artifact
        and isinstance(prior_version, dict)
        and prior_version.get("hash") == new_hash
    ):
        raise CliError(
            "cache_hit_suspected",
            "revise produced byte-identical content to prior plan version - likely a session-cache replay. See ticket.",
            valid_next=infer_next_steps(state),
            extra={
                "step": step,
                "prior_version": prior_version.get("version"),
                "prior_hash": prior_version.get("hash"),
                "new_hash": new_hash,
                "session_id": worker.session_id,
                "duration_ms": worker.duration_ms,
                "prompt_tokens": worker.prompt_tokens,
                "completion_tokens": worker.completion_tokens,
                "ticket": "01KRXNZZGRV17PHZRJ2Q56SPS3",
                "message": "revise produced byte-identical content to prior plan version - likely a session-cache replay. See ticket.",
            },
        )
    atomic_write_text(plan_dir / resolved_plan_filename, plan_text, _plan_dir=plan_dir)
    meta = {
        "version": version,
        "timestamp": now_utc(),
        "hash": new_hash,
        **meta_fields,
        "structure_warnings": structure_warnings,
    }
    atomic_write_json(plan_dir / meta_filename, meta, _plan_dir=plan_dir)
    return resolved_plan_filename, meta_filename, meta


def _validate_generated_plan_or_raise(
    *,
    plan_dir: Path,
    state: PlanState,
    step: str,
    iteration: int,
    worker: WorkerResult,
    plan_text: str,
) -> list[str]:
    structure_warnings = validate_plan_structure(plan_text)
    if PLAN_STRUCTURE_REQUIRED_STEP_ISSUE in structure_warnings:
        retry_next = [step] if step in {"plan", "revise"} else infer_next_steps(state)
        error = CliError(
            "structure_error",
            f"{step.title()} output failed structural validation: {PLAN_STRUCTURE_REQUIRED_STEP_ISSUE}",
            valid_next=retry_next,
            extra={"raw_output": worker.raw_output},
        )
        record_step_failure(
            plan_dir,
            state,
            step=step,
            iteration=iteration,
            error=error,
            duration_ms=worker.duration_ms,
        )
        raise error
    return structure_warnings
