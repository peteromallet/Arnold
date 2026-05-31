"""Parallel critique runner — dispatches one read-only worker per check via
the generic worker fan-out primitives in :mod:`megaplan._core.worker_fanout`.

Each check carries a resolved :class:`~megaplan.types.AgentMode` (attached by
the critique handler per gate decision SD1).  The runner builds one
:class:`~megaplan._core.WorkerUnit` per check, scatters them through
:func:`~megaplan._core.scatter_worker_units`, and reduces the ordered results
while preserving the verified/disputed flag-merge semantics.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from megaplan._core import (
    read_json,
    schemas_root,
    _merge_unique,
    WorkerUnit,
    scatter_worker_units,
)
from megaplan.prompts.critique import single_check_critique_prompt, write_single_check_template
from megaplan.pipelines.creative.prompts.critique_joke import single_check_critique_joke_prompt
from megaplan.types import CliError, PlanState
from megaplan.workers import STEP_SCHEMA_FILENAMES, WorkerResult


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
) -> tuple[int, dict[str, Any], list[str], list[str], float, int, int, int]:
    """Legacy Hermes-specific check runner — kept for test compatibility.

    .. deprecated::
        :func:`run_parallel_critique` now dispatches through
        :func:`~megaplan._core.scatter_worker_units` instead.  This
        function is retained only so existing tests that import it
        continue to compile.
    """
    import uuid as _uuid

    from megaplan._core import with_429_openrouter_fallback as _with_429_fallback
    from megaplan.workers.hermes import (
        _import_hermes_runtime,
        _streaming_run_kwargs,
        _toolsets_for_phase,
        _worker_db_path,
        clean_parsed_payload,
        parse_agent_output,
    )
    from megaplan.runtime.key_pool import resolve_model as _resolve_model

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
            session_id=str(_uuid.uuid4()),
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

    def _run_attempt(current_agent, current_output_path: Path, *, current_model: str | None = None) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str], float, int, int, int]:
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
        _result, check_payload, verified_ids, disputed_ids, cost_usd, pt, ct, tt = _with_429_fallback(
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
    effort: str | None = None,
    max_concurrent: int | None = None,
) -> WorkerResult:
    """Run one single-check critique per *check* in parallel via worker fan-out.

    Each check MUST carry a ``_resolved_agent_mode`` key (an
    :class:`~megaplan.types.AgentMode` attached by the critique handler per
    gate decision SD1).  A :class:`~megaplan._core.WorkerUnit` is built per
    check with a unique output path, the single-check critique prompt, and
    ``read_only=True``.  Units are dispatched through
    :func:`~megaplan._core.scatter_worker_units`; results are reduced in
    input order while preserving the verified/disputed flag-merge semantics
    (disputed flags override verified).

    No session state is mutated — every unit is dispatched read-only.
    """
    started = time.monotonic()
    if not checks:
        return WorkerResult(
            payload={"checks": [], "flags": [], "verified_flag_ids": [], "disputed_flag_ids": []},
            raw_output="parallel",
            duration_ms=0,
            cost_usd=0.0,
            session_id=None,
        )

    # Minimal args namespace for worker dispatch — the real args are not
    # available at this layer and the downstream uses of args (explicit-agent
    # detection, phase-model overrides) are handled by the caller.
    _args = argparse.Namespace(
        hermes=None,
        agent=None,
        phase_model=[],
    )

    _mode = state.get("config", {}).get("mode", "code")
    _prompt_builder = (
        single_check_critique_joke_prompt
        if _mode == "joke"
        else single_check_critique_prompt
    )

    # ------------------------------------------------------------------
    # Build one WorkerUnit per check
    # ------------------------------------------------------------------
    units: list[WorkerUnit] = []
    for _idx, _check in enumerate(checks):
        _resolved = _check.get("_resolved_agent_mode")
        if _resolved is None:
            raise CliError(
                "invariant_error",
                f"No _resolved_agent_mode metadata on check '{_check.get('id', '?')}' — "
                "the critique handler must attach a resolved AgentMode per SD1",
            )

        _output_path = write_single_check_template(
            plan_dir, state, _check, f"critique_check_{_check['id']}.json",
        )
        _prompt = _prompt_builder(state, plan_dir, root, _check, _output_path)

        units.append(
            WorkerUnit(
                step="critique",
                resolved=_resolved,
                prompt=_prompt,
                output_path=_output_path,
                read_only=True,
                extra={"check_id": _check["id"], "index": _idx},
            )
        )

    # ------------------------------------------------------------------
    # Parse hook: extract exactly one check + verified/disputed per unit
    # ------------------------------------------------------------------
    def _parse_result(_index: int, raw_payload: Any, unit: WorkerUnit) -> tuple[dict[str, Any], list[str], list[str]]:
        _checks_list = raw_payload.get("checks") if isinstance(raw_payload, dict) else []
        _cid = unit.extra.get("check_id", "?")
        if isinstance(_checks_list, list) and len(_checks_list) != 1:
            _matching = [
                item for item in _checks_list
                if isinstance(item, dict) and item.get("id") == _cid
            ]
            if len(_matching) == 1:
                _checks_list = _matching
        if not isinstance(_checks_list, list) or len(_checks_list) != 1 or not isinstance(_checks_list[0], dict):
            raise CliError(
                "worker_parse_error",
                f"Parallel critique output for check '{_cid}' did not contain exactly one check",
                extra={"raw_output": str(raw_payload)},
            )
        _verified = raw_payload.get("verified_flag_ids", [])
        _disputed = raw_payload.get("disputed_flag_ids", [])
        return (
            _checks_list[0],
            _verified if isinstance(_verified, list) else [],
            _disputed if isinstance(_disputed, list) else [],
        )

    # ------------------------------------------------------------------
    # Scatter
    # ------------------------------------------------------------------
    sr = scatter_worker_units(
        units=units,
        state=state,
        plan_dir=plan_dir,
        root=root,
        args=_args,
        parse_result=_parse_result,
        max_concurrent=max_concurrent,
    )

    # ------------------------------------------------------------------
    # Reduce: ordered checks + flag merge (disputed trumps verified)
    # ------------------------------------------------------------------
    ordered_checks: list[dict[str, Any]] = []
    verified_groups: list[list[str]] = []
    disputed_groups: list[list[str]] = []
    for _item in sr.ordered_results:
        _check_payload, _v_ids, _d_ids = _item
        ordered_checks.append(_check_payload)
        verified_groups.append(_v_ids)
        disputed_groups.append(_d_ids)

    _disputed_flag_ids = _merge_unique(disputed_groups)
    _disputed_set = set(_disputed_flag_ids)
    _verified_flag_ids = [
        flag_id for flag_id in _merge_unique(verified_groups) if flag_id not in _disputed_set
    ]

    return WorkerResult(
        payload={
            "checks": ordered_checks,
            "flags": [],
            "verified_flag_ids": _verified_flag_ids,
            "disputed_flag_ids": _disputed_flag_ids,
        },
        raw_output="parallel",
        duration_ms=int((time.monotonic() - started) * 1000),
        cost_usd=sr.total_cost,
        session_id=None,
        prompt_tokens=sr.total_prompt_tokens,
        completion_tokens=sr.total_completion_tokens,
        total_tokens=sr.total_tokens,
    )
