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
from megaplan.execute.core import build_monitor_hint
from megaplan.profiles import apply_profile_expansion
from megaplan.prompts import create_claude_prompt, create_codex_prompt, create_hermes_prompt
from megaplan.step_edit import next_plan_artifact_name
from megaplan.types import CliError, MOCK_ENV_VAR, PlanState, StepResponse
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
from megaplan.evaluation import PLAN_STRUCTURE_REQUIRED_STEP_ISSUE, validate_plan_structure
from megaplan.workers import WorkerResult

log = logging.getLogger("megaplan")


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


_AUTO_NEXT_STEP = object()


def _emit_phase_notice(step: str) -> None:
    if step not in PHASE_RUNTIME_POLICY:
        return
    duration_hint = format_duration_hint(
        step,
        configured_timeout_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    )
    print(f"[megaplan] Starting {step}... {duration_hint}", file=sys.stderr)


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
    agent, mode, refreshed, model = resolved or _handlers_pkg.resolve_agent_mode(step, args)
    run_id = set_active_step(state, step=step, agent=agent, mode=mode, model=model)
    _emit_phase_notice(step)
    save_state(plan_dir, state)
    try:
        run_step_kwargs: dict[str, Any] = {
            "root": root,
            "resolved": (agent, mode, refreshed, model),
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
        save_state(plan_dir, state)
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
        "`flag_resolutions` entries for every blocking flag. If you cannot resolve every "
        "blocking flag, return ITERATE or ESCALATE instead."
    )
    return f"{base_prompt}\n\n{addendum}"


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
    save_state(plan_dir, state)
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
    atomic_write_json(plan_dir / filename, payload)
    return sha256_file(plan_dir / filename)


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
    atomic_write_text(plan_dir / resolved_plan_filename, plan_text)
    meta = {
        "version": version,
        "timestamp": now_utc(),
        "hash": sha256_text(plan_text),
        **meta_fields,
        "structure_warnings": structure_warnings,
    }
    atomic_write_json(plan_dir / meta_filename, meta)
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
