"""Parallel Hermes review runner.

The preloaded-template-ID convention is the preferred way to get structured
output from focused review agents: write the exact slot shape first, then have
each agent fill that file instead of inventing IDs in free-form JSON.

This module intentionally mirrors `megaplan.orchestration.parallel_critique` so the two phase
runners remain easy to compare and later extract into a shared utility.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import Any

from megaplan._core import load_flag_registry, read_json, schemas_root, scatter_gather_checks, with_429_openrouter_fallback
from megaplan.workers.hermes import _toolsets_for_phase, clean_parsed_payload, parse_agent_output, _worker_db_path
from megaplan.prompts.review import (
    _filtered_prior_flags,
    _write_criteria_verdict_review_template,
    _write_single_check_review_template,
    parallel_criteria_review_prompt,
    single_check_review_prompt,
)
from megaplan.types import CliError, PlanState
from megaplan.workers import STEP_SCHEMA_FILENAMES, WorkerResult

from megaplan.runtime.key_pool import (
    resolve_model as _resolve_model,
)


def _clean_review_check_payload(payload: dict[str, Any]) -> None:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return
    for check in checks:
        if not isinstance(check, dict):
            continue
        check.pop("guidance", None)
        check.pop("prior_findings", None)


def _failure_reason(exc: Exception) -> str:
    if isinstance(exc, CliError):
        return exc.message
    return str(exc) or exc.__class__.__name__


def _run_check(
    index: int,
    check: Any,
    *,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    model: str | None,
    schema: dict[str, Any],
    project_dir: Path,
    pre_check_flags: list[dict[str, Any]],
    prior_flags: list[dict[str, Any]] | None = None,
    output_stream: Any | None = None,
) -> tuple[int, dict[str, Any], list[str], list[str], float, int, int, int]:
    from megaplan.workers.hermes import _import_hermes_runtime

    AIAgent, SessionDB = _import_hermes_runtime()

    check_id = check["id"] if isinstance(check, dict) else getattr(check, "id")
    _review_db_path = _worker_db_path(plan_dir, f"review_{check_id}")
    output_path = _write_single_check_review_template(plan_dir, state, check, f"review_check_{check_id}.json")
    prompt = single_check_review_prompt(state, plan_dir, root, check, output_path, pre_check_flags, prior_flags)
    resolved_model, agent_kwargs = _resolve_model(model)

    _model_lower = (resolved_model or "").lower()
    _reasoning_families = ("qwen/qwen3", "deepseek/deepseek-r1")
    _reasoning_off = (
        {"enabled": False}
        if any(_model_lower.startswith(prefix) for prefix in _reasoning_families)
        else None
    )

    _stream = output_stream if output_stream is not None else sys.stderr

    def _make_agent(m: str, kw: dict) -> "AIAgent":
        agent = AIAgent(
            model=m,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            enabled_toolsets=_toolsets_for_phase("review"),
            session_id=str(uuid.uuid4()),
            session_db=SessionDB(db_path=_review_db_path),
            max_tokens=32768,
            reasoning_config=_reasoning_off,
            **kw,
        )
        agent._print_fn = lambda *args, **kwargs: print(*args, **kwargs, file=_stream)
        return agent

    def _run_attempt(current_agent, current_output_path: Path) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str], float, int, int, int]:
        current_result = current_agent.run_conversation(user_message=prompt)
        payload, raw_output = parse_agent_output(
            current_agent,
            current_result,
            output_path=current_output_path,
            schema=schema,
            step="review",
            project_dir=project_dir,
            plan_dir=plan_dir,
        )
        clean_parsed_payload(payload, schema, "review")
        _clean_review_check_payload(payload)
        payload_checks = payload.get("checks")
        if not isinstance(payload_checks, list) or len(payload_checks) != 1 or not isinstance(payload_checks[0], dict):
            raise CliError(
                "worker_parse_error",
                f"Parallel review output for check '{check_id}' did not contain exactly one check",
                extra={"raw_output": raw_output},
            )
        verified = payload.get("verified_flag_ids", [])
        disputed = payload.get("disputed_flag_ids", [])
        return (
            current_result,
            payload_checks[0],
            verified if isinstance(verified, list) else [],
            disputed if isinstance(disputed, list) else [],
            float(current_result.get("estimated_cost_usd", 0.0) or 0.0),
            int(current_result.get("prompt_tokens", 0) or 0),
            int(current_result.get("completion_tokens", 0) or 0),
            int(current_result.get("total_tokens", 0) or 0),
        )

    agent = _make_agent(resolved_model, agent_kwargs)
    try:
        _result, check_payload, verified_ids, disputed_ids, cost_usd, pt, ct, tt = _run_attempt(agent, output_path)
    except Exception as exc:
        _result, check_payload, verified_ids, disputed_ids, cost_usd, pt, ct, tt = with_429_openrouter_fallback(
            model=model,
            agent_kwargs=agent_kwargs,
            exc=exc,
            log_prefix="[parallel-review]",
            rebuild_template_fn=lambda: _write_single_check_review_template(plan_dir, state, check, f"review_check_{check_id}.json"),
            make_agent_fn=_make_agent,
            run_attempt_fn=_run_attempt,
            on_fail_message=lambda exc, fallback_exc: (
                f"Parallel review failed for check '{check_id}' "
                f"(both MiniMax and OpenRouter): primary={_failure_reason(exc)}; "
                f"fallback={_failure_reason(fallback_exc)}"
            ),
            stream=_stream,
        )
    return (
        index,
        check_payload,
        verified_ids,
        disputed_ids,
        cost_usd,
        pt,
        ct,
        tt,
    )


def _run_criteria_verdict(
    *,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    model: str | None,
    schema: dict[str, Any],
    project_dir: Path,
    output_stream: Any | None = None,
) -> tuple[dict[str, Any], float, int, int, int]:
    from megaplan.workers.hermes import _import_hermes_runtime

    AIAgent, SessionDB = _import_hermes_runtime()

    _criteria_db_path = _worker_db_path(plan_dir, "review_criteria_verdict")
    output_path = _write_criteria_verdict_review_template(plan_dir, state, "review_criteria_verdict.json")
    prompt = parallel_criteria_review_prompt(state, plan_dir, root, output_path)
    resolved_model, agent_kwargs = _resolve_model(model)

    _model_lower = (resolved_model or "").lower()
    _reasoning_families = ("qwen/qwen3", "deepseek/deepseek-r1")
    _reasoning_off = (
        {"enabled": False}
        if any(_model_lower.startswith(prefix) for prefix in _reasoning_families)
        else None
    )

    _stream_cv = output_stream if output_stream is not None else sys.stderr

    def _make_agent(m: str, kw: dict) -> "AIAgent":
        agent = AIAgent(
            model=m,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            enabled_toolsets=_toolsets_for_phase("review"),
            session_id=str(uuid.uuid4()),
            session_db=SessionDB(db_path=_criteria_db_path),
            max_tokens=32768,
            reasoning_config=_reasoning_off,
            **kw,
        )
        agent._print_fn = lambda *args, **kwargs: print(*args, **kwargs, file=_stream_cv)
        return agent

    def _run_attempt(current_agent, current_output_path: Path) -> tuple[dict[str, Any], dict[str, Any], float, int, int, int]:
        current_result = current_agent.run_conversation(user_message=prompt)
        payload, _raw_output = parse_agent_output(
            current_agent,
            current_result,
            output_path=current_output_path,
            schema=schema,
            step="review",
            project_dir=project_dir,
            plan_dir=plan_dir,
        )
        clean_parsed_payload(payload, schema, "review")
        return (
            current_result,
            payload,
            float(current_result.get("estimated_cost_usd", 0.0) or 0.0),
            int(current_result.get("prompt_tokens", 0) or 0),
            int(current_result.get("completion_tokens", 0) or 0),
            int(current_result.get("total_tokens", 0) or 0),
        )

    agent = _make_agent(resolved_model, agent_kwargs)
    try:
        _result, payload, cost_usd, pt, ct, tt = _run_attempt(agent, output_path)
    except Exception as exc:
        _result, payload, cost_usd, pt, ct, tt = with_429_openrouter_fallback(
            model=model,
            agent_kwargs=agent_kwargs,
            exc=exc,
            log_prefix="[parallel-review]",
            rebuild_template_fn=lambda: _write_criteria_verdict_review_template(plan_dir, state, "review_criteria_verdict.json"),
            make_agent_fn=_make_agent,
            run_attempt_fn=_run_attempt,
            on_fail_message=lambda exc, fallback_exc: (
                "Parallel review criteria verdict failed "
                f"(both MiniMax and OpenRouter): primary={_failure_reason(exc)}; "
                f"fallback={_failure_reason(fallback_exc)}"
            ),
            stream=_stream_cv,
        )
    return payload, cost_usd, pt, ct, tt


def run_parallel_review(
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    model: str | None,
    checks: tuple[Any, ...],
    pre_check_flags: list[dict[str, Any]],
    max_concurrent: int | None = None,
) -> WorkerResult:
    started = time.monotonic()
    schema = read_json(schemas_root(root) / STEP_SCHEMA_FILENAMES["review"])
    project_dir = Path(state["config"]["project_dir"])
    prior_flags = load_flag_registry(plan_dir).get("flags", [])
    output_stream = sys.stderr

    def _submit_checks(executor):
        return [
            executor.submit(
                _run_check,
                index,
                check,
                state=state,
                plan_dir=plan_dir,
                root=root,
                model=model,
                schema=schema,
                project_dir=project_dir,
                pre_check_flags=pre_check_flags,
                prior_flags=_filtered_prior_flags(check, prior_flags),
                output_stream=output_stream,
            )
            for index, check in enumerate(checks)
        ]

    def _submit_criteria(executor):
        return executor.submit(
            _run_criteria_verdict,
            state=state,
            plan_dir=plan_dir,
            root=root,
            model=model,
            schema=schema,
            project_dir=project_dir,
            output_stream=output_stream,
        )

    sr = scatter_gather_checks(
        num_checks=len(checks),
        submit_check_fn=_submit_checks,
        side_tasks=[_submit_criteria],
        max_concurrent=max_concurrent,
    )

    criteria_payload, *_ = sr.side_results[0]
    if criteria_payload is None:
        raise CliError("worker_error", "Parallel review did not return a criteria verdict payload")

    return WorkerResult(
        payload={
            "checks": sr.ordered_checks,
            "verified_flag_ids": sr.verified_flag_ids,
            "disputed_flag_ids": sr.disputed_flag_ids,
            "criteria_payload": criteria_payload,
        },
        raw_output="parallel",
        duration_ms=int((time.monotonic() - started) * 1000),
        cost_usd=sr.total_cost,
        session_id=None,
        prompt_tokens=sr.total_prompt_tokens,
        completion_tokens=sr.total_completion_tokens,
        total_tokens=sr.total_tokens,
    )
