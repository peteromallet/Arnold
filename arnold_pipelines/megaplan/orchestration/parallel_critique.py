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

from arnold_pipelines.megaplan._core import (
    _merge_unique,
    WorkerUnit,
    WorkerUnitResult,
    scatter_worker_units,
)
from arnold_pipelines.megaplan.orchestration.critique_status import (
    UNVERIFIABLE_STATUS,
    annotate_unverifiable_checks,
    unverifiable_detail,
)
from arnold_pipelines.megaplan.model_seam import ModelTier
from arnold_pipelines.megaplan.prompts.critique import single_check_critique_prompt, write_single_check_template
from arnold_pipelines.megaplan.pipelines.creative.prompts.critique_joke import single_check_critique_joke_prompt
from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.types import CliError, PlanState
from arnold_pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES, WorkerResult
from arnold_pipelines.megaplan.workers.result_metadata import aggregate_rate_limits


_CRITIQUE_WORKER_SHAPE_RETRIES = 2
_CRITIQUE_REPAIR_INSTRUCTION = (
    "Return a JSON object with a top-level `checks` array containing EXACTLY ONE "
    "check object for this single lens. Do not include multiple checks or wrap it differently."
)
_CRITIQUE_UNVERIFIABLE_SHAPE_REASON = (
    "parallel critique worker output did not contain a usable check object for "
    "this lens after retry; operator review may be needed"
)
_SANDBOX_NAMESPACE_REASON_MARKERS = (
    "bwrap",
    "bubblewrap",
    "sandbox namespace",
    "no permissions to create new namespace",
    "shell/file access is blocked in this environment",
)


class _RetryableCritiqueShapeError(Exception):
    """Internal signal for a critique worker payload that can be repaired by retry."""

    def __init__(self, check_id: str, check_count: int, raw_payload: Any) -> None:
        super().__init__(
            f"Parallel critique output for check '{check_id}' did not contain exactly one check"
        )
        self.check_id = check_id
        self.check_count = check_count
        self.raw_payload = raw_payload


def _critique_raw_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_raw.txt")


def _persist_critique_raw_output(output_path: Path, raw_output: object) -> None:
    text = "" if raw_output is None else str(raw_output)
    if not text:
        return
    try:
        _critique_raw_output_path(output_path).write_text(text, encoding="utf-8")
    except OSError:
        pass


def _unverifiable_check_payload(
    check_id: str,
    question: str,
    reason: str,
    *,
    cause: str | None = None,
    retryable: bool | None = None,
    error_kind: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": check_id,
        "question": question,
        "status": UNVERIFIABLE_STATUS,
        "unverifiable_reason": reason,
        "findings": [
            {"detail": unverifiable_detail(reason), "flagged": False},
        ],
    }
    if cause:
        payload["unverifiable_cause"] = cause
    if retryable is not None:
        payload["unverifiable_retryable"] = retryable
    if error_kind:
        payload["unverifiable_error_kind"] = error_kind
    return payload


def _sanitize_critique_check_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize benign model schema drift in a single critique check payload."""

    findings = payload.get("findings")
    if not isinstance(findings, list):
        return payload
    changed = False
    clean_findings: list[Any] = []
    for finding in findings:
        if not isinstance(finding, dict):
            clean_findings.append(finding)
            continue
        extra = set(finding) - {"detail", "flagged"}
        if not extra:
            clean_findings.append(finding)
            continue
        cleaned = {k: v for k, v in finding.items() if k not in extra}
        clean_findings.append(cleaned)
        changed = True
    if not changed:
        return payload
    cleaned_payload = dict(payload)
    cleaned_payload["findings"] = clean_findings
    return cleaned_payload


def _infer_unverifiable_cause(reason: str) -> tuple[str | None, bool | None, str | None]:
    normalized = str(reason or "").lower()
    if any(marker in normalized for marker in _SANDBOX_NAMESPACE_REASON_MARKERS):
        return "sandbox_namespace", False, "sandbox_namespace"
    if "rate limit" in normalized or "rate_limit" in normalized:
        return "provider_rate_limit", True, "rate_limit"
    if "capacity" in normalized or "quota" in normalized:
        return "provider_capacity", True, "rate_limit"
    return None, None, None


def _flags_only_unverifiable_payload(
    raw_payload: Any,
    *,
    check_id: str,
    question: str,
) -> dict[str, Any] | None:
    if not isinstance(raw_payload, dict):
        return None
    flags = raw_payload.get("flags")
    if not isinstance(flags, list) or not flags:
        return None
    dict_flags = [item for item in flags if isinstance(item, dict)]
    if not dict_flags:
        return None
    flag = dict_flags[0]
    category = str(flag.get("category", "")).strip().lower()
    concern = str(flag.get("concern", "")).strip()
    evidence = str(flag.get("evidence", "")).strip()
    reason = evidence or concern or "the worker could not verify this check"
    cause, retryable, error_kind = _infer_unverifiable_cause(reason)
    if category == "verifiability" and cause is not None:
        return _unverifiable_check_payload(
            check_id,
            question,
            reason,
            cause=cause,
            retryable=retryable,
            error_kind=error_kind,
        )
    # A valid flags-only critique is substantive evidence, not a parse
    # failure. Preserve every flag as a blocking finding instead of converting
    # it to a synthetic flagged:false unverifiable record.
    return {
        "id": check_id,
        "question": question,
        "status": "complete",
        "findings": [
            {
                "detail": str(item.get("evidence") or item.get("concern") or item.get("id") or "critique flag"),
                "flagged": True,
            }
            for item in dict_flags
        ],
    }


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

    from arnold_pipelines.megaplan._core import with_429_openrouter_fallback as _with_429_fallback
    from arnold_pipelines.megaplan.workers.hermes import (
        _import_hermes_runtime,
        _pre_dispatch_budget_check,
        _streaming_run_kwargs,
        _toolsets_for_phase,
        _worker_db_path,
        clean_parsed_payload,
        parse_agent_output,
    )
    from arnold_pipelines.megaplan.runtime.key_pool import resolve_model as _resolve_model

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
        # _pre_dispatch_budget_check sentinel: budget guard for dispatch
        _pre_dispatch_budget_check(
            current_agent,
            conversation_history=None,
            user_message=prompt,
            system=None,
            tool_manifest=None,
            schema=schema,
            step="critique",
            model_name=getattr(current_agent, "model", current_model or model),
            tier=ModelTier.NON_ENFORCED,
            worker="hermes",
        )
        current_result = current_agent.run_conversation(
            user_message=prompt,
            **run_kwargs,
        )
        try:
            payload, raw_output = parse_agent_output(
                current_agent,
                current_result,
                output_path=current_output_path,
                schema=schema,
                step="critique",
                project_dir=project_dir,
                plan_dir=plan_dir,
                run_kwargs=run_kwargs,
                check_id=str(check.get("id", "")) or None,
                question=str(check.get("question", "")) or None,
            )
        except CliError as exc:
            _persist_critique_raw_output(
                current_output_path,
                exc.extra.get("raw_output") or exc.message,
            )
            raise
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
    _schema = SCHEMAS[STEP_SCHEMA_FILENAMES["critique"]]

    # ------------------------------------------------------------------
    # Build one WorkerUnit per check
    # ------------------------------------------------------------------
    # Each unit runs in its OWN process and opens a hermes SessionDB. The
    # step+agent session_key collapses to a single shared db path
    # (state_hermes_critic.db), so without an override every concurrent worker
    # writes the SAME SQLite file → "database is locked". Give each check its
    # own session db (the legacy _run_check path did this); the override is
    # plumbed through WorkerUnit.extra["worker_options"]["session_db_path"]
    # (worker_fanout.py) → run_hermes_step db_override (hermes.py).
    from arnold_pipelines.megaplan.workers.hermes import _worker_db_path

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
        _seam_tier = (
            ModelTier.ENFORCED if _resolved.agent in {"codex", "hermes"} else ModelTier.NON_ENFORCED
        )

        units.append(
            WorkerUnit(
                step="critique",
                resolved=_resolved,
                prompt=_prompt,
                output_path=_output_path,
                read_only=True,
                validation_step="critique",
                schema=_schema,
                model=_resolved.resolved_model or _resolved.model,
                tier=_seam_tier,
                extra={
                    "check_id": _check["id"],
                    "question": _check.get("question", ""),
                    "index": _idx,
                    "ledger_step_label": _check["id"],
                    "ledger_selected_spec": _check.get("_routing_selected_spec"),
                    "ledger_tier": _check.get("_routing_tier"),
                    "ledger_complexity": _check.get("complexity"),
                    "ledger_tier_routing_active": bool(_check.get("_routing_tier_active", False)),
                    "worker_options": {
                        "session_db_path": str(_worker_db_path(plan_dir, f"critique_{_check['id']}")),
                        "check_id": str(_check["id"]),
                        "question": str(_check.get("question", "")),
                    },
                },
            )
        )

    # ------------------------------------------------------------------
    # Parse hook: extract exactly one check + verified/disputed per unit
    # ------------------------------------------------------------------
    def _parse_result(_index: int, raw_payload: Any, unit: WorkerUnit) -> tuple[dict[str, Any], list[str], list[str]]:
        _checks_list = raw_payload.get("checks") if isinstance(raw_payload, dict) else None
        _cid = unit.extra.get("check_id", "?")
        if isinstance(raw_payload, dict):
            _status = raw_payload.get("status") or raw_payload.get("result")
            _status_text = str(_status).strip().lower() if _status is not None else ""
            if _status_text == UNVERIFIABLE_STATUS or raw_payload.get(UNVERIFIABLE_STATUS) is True:
                _reason = (
                    raw_payload.get("reason")
                    or raw_payload.get("detail")
                    or raw_payload.get("message")
                    or "the worker could not verify this check"
                )
                return (
                    {
                        "id": _cid,
                        "question": unit.extra.get("question", ""),
                        "status": UNVERIFIABLE_STATUS,
                        "unverifiable_reason": str(_reason),
                        "findings": [
                            {"detail": unverifiable_detail(str(_reason)), "flagged": False}
                        ],
                    },
                    [],
                    [],
                )
            _flags_only = _flags_only_unverifiable_payload(
                raw_payload,
                check_id=str(_cid),
                question=str(unit.extra.get("question", "")),
            )
            if _flags_only is not None:
                _verified = raw_payload.get("verified_flag_ids", [])
                _disputed = raw_payload.get("disputed_flag_ids", [])
                return (
                    _flags_only,
                    _verified if isinstance(_verified, list) else [],
                    _disputed if isinstance(_disputed, list) else [],
                )
        if isinstance(_checks_list, list) and len(_checks_list) != 1:
            _matching = [
                item for item in _checks_list
                if isinstance(item, dict) and item.get("id") == _cid
            ]
            _dict_checks = [item for item in _checks_list if isinstance(item, dict)]
            _selected = _matching[0] if _matching else (_dict_checks[0] if _dict_checks else None)
            if _selected is not None:
                print(
                    f"[parallel-critique] worker '{_cid}' returned "
                    f"{len(_checks_list)} checks; using "
                    f"{'matching' if _matching else 'first'} check",
                    file=sys.stderr,
                )
                _checks_list = [_selected]
        if not isinstance(_checks_list, list) or len(_checks_list) != 1 or not isinstance(_checks_list[0], dict):
            _count = len(_checks_list) if isinstance(_checks_list, list) else 0
            raise _RetryableCritiqueShapeError(str(_cid), _count, raw_payload)
        _verified = raw_payload.get("verified_flag_ids", [])
        _disputed = raw_payload.get("disputed_flag_ids", [])
        _check_payload = _checks_list[0]
        if _check_payload.get("id") != _cid:
            _check_payload = dict(_check_payload)
            _check_payload["id"] = _cid
            print(
                f"[parallel-critique] worker '{_cid}' returned check id "
                f"'{_checks_list[0].get('id', '?')}'; normalizing to requested check",
                file=sys.stderr,
            )
        if (
            not isinstance(_check_payload.get("question"), str)
            or not _check_payload.get("question", "").strip()
        ):
            _check_payload = dict(_check_payload)
            _check_payload["question"] = unit.extra.get("question", "")
        _check_payload = _sanitize_critique_check_payload(_check_payload)
        annotate_unverifiable_checks({"checks": [_check_payload]})
        return (
            _check_payload,
            _verified if isinstance(_verified, list) else [],
            _disputed if isinstance(_disputed, list) else [],
        )

    def _repair_unit(unit: WorkerUnit) -> WorkerUnit:
        return WorkerUnit(
            step=unit.step,
            resolved=unit.resolved,
            prompt=f"{_CRITIQUE_REPAIR_INSTRUCTION}\n\n{unit.prompt}",
            output_path=unit.output_path,
            read_only=unit.read_only,
            validation_step=unit.validation_step,
            schema=unit.schema,
            model=unit.model,
            tier=unit.tier,
            extra=dict(unit.extra),
        )

    def _scatter_raw(current_units: list[WorkerUnit]) -> Any:
        def _on_unit_error(_index: int, exc: Exception) -> tuple[Any, float, int, int, int]:
            unit = current_units[_index]
            check_id = str(unit.extra.get("check_id", "?"))
            cause = None
            retryable = None
            error_kind = None
            if isinstance(exc, CliError):
                _persist_critique_raw_output(
                    unit.output_path,
                    exc.extra.get("raw_output") or exc.message,
                )
                cause = str(exc.extra.get("source") or "") or None
                retryable_raw = exc.extra.get("retryable")
                retryable = retryable_raw if isinstance(retryable_raw, bool) else None
                error_kind = str(exc.code or "") or None
            else:
                _persist_critique_raw_output(unit.output_path, str(exc))
            reason = f"parallel critique worker failed for check '{check_id}': {exc}"
            return (
                {
                    "checks": [
                        _unverifiable_check_payload(
                            check_id,
                            str(unit.extra.get("question", "")),
                            reason,
                            cause=cause,
                            retryable=retryable,
                            error_kind=error_kind,
                        )
                    ],
                    "flags": [],
                    "verified_flag_ids": [],
                    "disputed_flag_ids": [],
                },
                0.0,
                0,
                0,
                0,
            )

        return scatter_worker_units(
            units=current_units,
            state=state,
            plan_dir=plan_dir,
            root=root,
            args=_args,
            parse_result=lambda _idx, item, _unit: item,
            max_concurrent=max_concurrent,
            on_unit_error=_on_unit_error,
        )

    def _accumulate_scatter_totals(scatter_result: Any) -> None:
        nonlocal _total_cost, _total_prompt_tokens, _total_completion_tokens, _total_tokens
        _total_cost += scatter_result.total_cost
        _total_prompt_tokens += scatter_result.total_prompt_tokens
        _total_completion_tokens += scatter_result.total_completion_tokens
        _total_tokens += scatter_result.total_tokens

    # ------------------------------------------------------------------
    # Scatter + repair malformed worker shapes locally
    # ------------------------------------------------------------------
    _total_cost = 0.0
    _total_prompt_tokens = 0
    _total_completion_tokens = 0
    _total_tokens = 0
    _parsed_results: list[tuple[dict[str, Any], list[str], list[str]] | None] = [None] * len(units)
    _rate_limits: list[dict[str, Any] | None] = []

    _sr = _scatter_raw(units)
    _accumulate_scatter_totals(_sr)

    _failures: dict[int, _RetryableCritiqueShapeError] = {}
    for _idx, _item in enumerate(_sr.ordered_results):
        _payload = _item.payload if isinstance(_item, WorkerUnitResult) else _item
        _rate_limits.append(_item.rate_limit if isinstance(_item, WorkerUnitResult) else None)
        try:
            _parsed_results[_idx] = _parse_result(_idx, _payload, units[_idx])
        except _RetryableCritiqueShapeError as exc:
            if isinstance(_item, WorkerUnitResult):
                _persist_critique_raw_output(units[_idx].output_path, _item.raw_output)
            _failures[_idx] = exc

    _retry_units = units
    for _retry_number in range(1, _CRITIQUE_WORKER_SHAPE_RETRIES + 1):
        if not _failures:
            break
        _next_attempt = _retry_number + 1
        _total_attempts = _CRITIQUE_WORKER_SHAPE_RETRIES + 1
        _retry_indices = list(_failures)
        for _failure in _failures.values():
            print(
                f"[parallel-critique] worker '{_failure.check_id}' returned "
                f"{_failure.check_count} checks, retrying (attempt {_next_attempt}/{_total_attempts})",
                file=sys.stderr,
            )

        _subset_units = [_repair_unit(_retry_units[_idx]) for _idx in _retry_indices]
        _retry_units_by_index = dict(zip(_retry_indices, _subset_units, strict=True))
        _retry_sr = _scatter_raw(_subset_units)
        _accumulate_scatter_totals(_retry_sr)

        _next_failures: dict[int, _RetryableCritiqueShapeError] = {}
        for _subset_pos, _item in enumerate(_retry_sr.ordered_results):
            _original_idx = _retry_indices[_subset_pos]
            _unit = _retry_units_by_index[_original_idx]
            _payload = _item.payload if isinstance(_item, WorkerUnitResult) else _item
            _rate_limits.append(_item.rate_limit if isinstance(_item, WorkerUnitResult) else None)
            try:
                _parsed_results[_original_idx] = _parse_result(_original_idx, _payload, _unit)
            except _RetryableCritiqueShapeError as exc:
                if isinstance(_item, WorkerUnitResult):
                    _persist_critique_raw_output(_unit.output_path, _item.raw_output)
                _next_failures[_original_idx] = exc
        _failures = _next_failures
        for _idx, _unit in _retry_units_by_index.items():
            _retry_units[_idx] = _unit

    for _idx, _failure in _failures.items():
        _unit = _retry_units[_idx]
        print(
            f"[parallel-critique] worker '{_failure.check_id}' returned "
            f"{_failure.check_count} checks after retry budget; marking check unverifiable",
            file=sys.stderr,
        )
        _parsed_results[_idx] = (
            _unverifiable_check_payload(
                _failure.check_id,
                str(_unit.extra.get("question", "")),
                _CRITIQUE_UNVERIFIABLE_SHAPE_REASON,
            ),
            [],
            [],
        )

    # ------------------------------------------------------------------
    # Reduce: ordered checks + flag merge (disputed trumps verified)
    # ------------------------------------------------------------------
    ordered_checks: list[dict[str, Any]] = []
    verified_groups: list[list[str]] = []
    disputed_groups: list[list[str]] = []
    for _item in _parsed_results:
        if _item is None:
            raise CliError(
                "worker_parse_error",
                "Parallel critique worker result missing after retry processing",
            )
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
        cost_usd=_total_cost,
        session_id=None,
        prompt_tokens=_total_prompt_tokens,
        completion_tokens=_total_completion_tokens,
        total_tokens=_total_tokens,
        rate_limit=aggregate_rate_limits(_rate_limits),
    )
