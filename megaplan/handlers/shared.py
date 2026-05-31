from __future__ import annotations

import argparse
import inspect
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import megaplan.workers as worker_module
from megaplan.execute.batch import build_monitor_hint
from megaplan.profiles import apply_profile_expansion
from megaplan.prompts import create_claude_prompt, create_codex_prompt, create_hermes_prompt
from megaplan.receipts import build_receipt
from megaplan.receipts.writer import write_receipt
from megaplan.execute.step_edit import next_plan_artifact_name
from megaplan.types import AgentMode, CliError, MOCK_ENV_VAR, PlanState, StepResponse
from megaplan.orchestration.phase_result import (
    _emit_phase_result,
    phase_result_guard,
    BlockedTask,
    Deviation,
    ExitKind,
)
from megaplan._core import (
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
from megaplan._core.phase_runtime import (
    DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    PHASE_RUNTIME_POLICY,
    format_duration_hint,
)
from megaplan.orchestration.evaluation import PLAN_STRUCTURE_REQUIRED_STEP_ISSUE, validate_plan_structure
from megaplan.workers import WorkerResult

log = logging.getLogger("megaplan")


def _agent_mode_parts(resolved: AgentMode | tuple[str, str, bool, str | None]) -> tuple[str, str, bool, str | None]:
    if isinstance(resolved, AgentMode):
        return resolved.agent, resolved.mode, resolved.refreshed, resolved.model
    return resolved


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
) -> tuple[WorkerResult, str, str, bool]:
    failure_iteration = state["iteration"] if iteration is None else iteration
    from megaplan import handlers as _handlers_pkg

    apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
    res = resolved or _handlers_pkg.resolve_agent_mode(step, args)
    agent = res.agent if isinstance(res, AgentMode) else res[0]
    mode = res.mode if isinstance(res, AgentMode) else res[1]
    refreshed = res.refreshed if isinstance(res, AgentMode) else res[2]
    model = res.resolved_model if isinstance(res, AgentMode) else res[3]
    run_id = set_active_step(state, step=step, agent=agent, mode=mode, model=model)
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
    if agent_type == "claude":
        base_prompt = create_claude_prompt("gate", state, plan_dir, root=root)
    elif agent_type == "hermes":
        base_prompt = create_hermes_prompt("gate", state, plan_dir, root=root)
    else:
        base_prompt = create_codex_prompt("gate", state, plan_dir, root=root)
    missing_flags = ", ".join(missing_flag_ids)
    addendum = (
        "Gate retry for the same iteration.\n"
        "Your previous response recommended PROCEED but left blocking flags unresolved.\n"
        f"Missing blocking flag IDs: {missing_flags}.\n"
        "Return a complete gate response. If you recommend PROCEED, you MUST include "
        "`flag_resolutions` entries for every blocking flag. For addressed-but-unverified "
        "flags, the action MUST be `verify_fixed` with concrete evidence from the revised "
        "plan; `dispute` and `accept_tradeoff` do not clear addressed flags. If you cannot "
        "resolve every blocking flag, return ITERATE or ESCALATE instead."
    )
    return f"{base_prompt}\n\n{addendum}"


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
) -> StepResponse:
    clear_active_step(state, run_id=run_id)
    apply_session_update(state, step, agent, worker.session_id, mode=mode, refreshed=refreshed)
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
        error = CliError(
            "structure_error",
            f"{step.title()} output failed structural validation: {PLAN_STRUCTURE_REQUIRED_STEP_ISSUE}",
            valid_next=infer_next_steps(state),
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
