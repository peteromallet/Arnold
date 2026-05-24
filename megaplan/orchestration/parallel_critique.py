"""Parallel Hermes critique runner."""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from megaplan._core import get_effective, read_json, schemas_root, _merge_unique, with_429_openrouter_fallback, scatter_gather_checks
from megaplan.workers.hermes import (
    _streaming_run_kwargs,
    _toolsets_for_phase,
    _worker_db_path,
    clean_parsed_payload,
    parse_agent_output,
)
from megaplan.prompts.critique import single_check_critique_prompt, write_single_check_template
from megaplan.prompts.critique_joke import single_check_critique_joke_prompt
from megaplan.types import CliError, PlanState
from megaplan.workers import STEP_SCHEMA_FILENAMES, WorkerResult


from megaplan.runtime.key_pool import (
    _load_hermes_env,
    _get_api_credential,
    resolve_model as _resolve_model,
)


def _run_check(
    index: int,
    check: dict[str, Any],
    *,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    model: str | None,
    schema: dict[str, Any],
    project_dir: Path,
    output_stream: Any | None = None,
) -> tuple[int, dict[str, Any], list[str], list[str], float]:
    from megaplan.workers.hermes import _import_hermes_runtime

    AIAgent, SessionDB = _import_hermes_runtime()

    _critique_db_path = _worker_db_path(plan_dir, f"critique_{check['id']}")
    output_path = write_single_check_template(plan_dir, state, check, f"critique_check_{check['id']}.json")
    prompt_builder = (
        single_check_critique_joke_prompt
        if state.get("config", {}).get("mode", "code") == "joke"
        else single_check_critique_prompt
    )
    prompt = prompt_builder(state, plan_dir, root, check, output_path)
    resolved_model, agent_kwargs = _resolve_model(model)

    _model_lower = (resolved_model or "").lower()
    _reasoning_families = ("qwen/qwen3", "deepseek/deepseek-r1")
    _reasoning_off = (
        {"enabled": False}
        if any(_model_lower.startswith(prefix) for prefix in _reasoning_families)
        else None
    )

    # Cap output tokens to match the main-line hermes worker (Qwen repetition
    # mitigation). Drives the Fireworks streaming gate below.
    agent_max_tokens = 32768
    _stream = output_stream if output_stream is not None else sys.stderr

    def _make_agent(m: str, kw: dict) -> "AIAgent":
        a = AIAgent(
            model=m,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            enabled_toolsets=_toolsets_for_phase("critique"),
            session_id=str(uuid.uuid4()),
            session_db=SessionDB(db_path=_critique_db_path),
            max_tokens=agent_max_tokens,
            reasoning_config=_reasoning_off,
            **kw,
        )
        a._print_fn = lambda *args, **kwargs: print(*args, **kwargs, file=_stream)
        return a

    def _failure_reason(exc: Exception) -> str:
        if isinstance(exc, CliError):
            return exc.message
        return str(exc) or exc.__class__.__name__

    def _run_attempt(current_agent, current_output_path: Path, *, current_model: str | None = None) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str], float]:
        # Force streaming for providers that require it at this max_tokens
        # (Fireworks rejects max_tokens > 4096 unless stream=true).  The
        # streaming response is reassembled into the same shape non-streaming
        # would return — downstream code is unchanged.
        run_kwargs = _streaming_run_kwargs(current_model or model, agent_max_tokens)
        current_result = current_agent.run_conversation(
            user_message=prompt,
            **run_kwargs,
        )
        payload, raw_output = parse_agent_output(
            current_agent,
            current_result,
            output_path=current_output_path,
            schema=schema,
            step="critique",
            project_dir=project_dir,
            plan_dir=plan_dir,
            run_kwargs=run_kwargs,
        )
        clean_parsed_payload(payload, schema, "critique")
        payload_checks = payload.get("checks")
        if not isinstance(payload_checks, list) or len(payload_checks) != 1 or not isinstance(payload_checks[0], dict):
            raise CliError(
                "worker_parse_error",
                f"Parallel critique output for check '{check['id']}' did not contain exactly one check",
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
            log_prefix="[parallel-critique]",
            rebuild_template_fn=lambda: write_single_check_template(plan_dir, state, check, f"critique_check_{check['id']}.json"),
            make_agent_fn=lambda m, kw: _make_agent(m, kw),
            run_attempt_fn=lambda a, op: _run_attempt(a, op),
            on_fail_message=lambda primary_exc, fallback_exc: (
                f"Parallel critique failed for check '{check['id']}' "
                f"(both MiniMax and OpenRouter): primary={_failure_reason(primary_exc)}; "
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


def run_parallel_critique(
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    model: str | None,
    checks: tuple[dict[str, Any], ...],
    max_concurrent: int | None = None,
) -> WorkerResult:
    started = time.monotonic()
    if not checks:
        return WorkerResult(
            payload={"checks": [], "flags": [], "verified_flag_ids": [], "disputed_flag_ids": []},
            raw_output="parallel",
            duration_ms=0,
            cost_usd=0.0,
            session_id=None,
        )

    schema = read_json(schemas_root(root) / STEP_SCHEMA_FILENAMES["critique"])
    project_dir = Path(state["config"]["project_dir"])
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
                output_stream=output_stream,
            )
            for index, check in enumerate(checks)
        ]

    sr = scatter_gather_checks(
        num_checks=len(checks),
        submit_check_fn=_submit_checks,
        side_tasks=None,
        max_concurrent=max_concurrent,
    )
    ordered_checks = sr.ordered_checks
    verified_flag_ids = sr.verified_flag_ids
    disputed_flag_ids = sr.disputed_flag_ids
    total_cost = sr.total_cost
    total_prompt_tokens = sr.total_prompt_tokens
    total_completion_tokens = sr.total_completion_tokens
    total_tokens = sr.total_tokens
    return WorkerResult(
        payload={
            "checks": ordered_checks,
            "flags": [],
            "verified_flag_ids": verified_flag_ids,
            "disputed_flag_ids": disputed_flag_ids,
        },
        raw_output="parallel",
        duration_ms=int((time.monotonic() - started) * 1000),
        cost_usd=total_cost,
        session_id=None,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
    )
