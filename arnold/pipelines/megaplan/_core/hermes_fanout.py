"""Shared fan-out primitives for parallel Hermes orchestration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, NamedTuple

from .io import get_effective
from arnold.pipelines.megaplan.types import CliError


class ScatterResult(NamedTuple):
    ordered_checks: list[dict[str, Any]]
    verified_flag_ids: list[str]
    disputed_flag_ids: list[str]
    total_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    side_results: list[Any]


class GenericScatterResult(NamedTuple):
    ordered_results: list[Any]
    total_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    side_results: list[Any]


class _ProcessUnitFailure(RuntimeError):
    pass


class _ProcessUnitTimeout(TimeoutError):
    pass


def _run_process_unit_child(
    run_unit_fn: Callable[[int, Any], tuple[int, Any, float, int, int, int]],
    index: int,
    unit: Any,
    out_queue: Any,
) -> None:
    try:
        out_queue.put(
            {
                "ok": True,
                "index": index,
                "result": run_unit_fn(index, unit),
            }
        )
    except BaseException as exc:
        out_queue.put(
            {
                "ok": False,
                "index": index,
                "exc_type": exc.__class__.__name__,
                "error": str(exc) or exc.__class__.__name__,
            }
        )


def _merge_unique(groups: list[list[str]]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


def _failure_reason(exc: Exception) -> str:
    if isinstance(exc, CliError):
        return exc.message
    return str(exc) or exc.__class__.__name__


def with_429_openrouter_fallback(
    *,
    model: str | None,
    agent_kwargs: dict[str, Any],
    exc: Exception,
    log_prefix: str,
    rebuild_template_fn: Callable[[], Any],
    make_agent_fn: Callable[[str, dict], Any],
    run_attempt_fn: Callable[[Any, Any], Any],
    on_fail_message: Callable[[Exception, Exception], str],
    stream: Any,
) -> Any:
    """Handle MiniMax 429 / bad-content by falling back to OpenRouter.

    Reports the 429 to the key pool (minimax 60s / zhipu 3600|120s cooldown),
    then retries via OpenRouter when available.  Re-raises the original exc
    unchanged when the model is not minimax: or no OpenRouter key is available.

    IMPORTANT: run_attempt_fn is called without the OpenRouter model so the
    streaming decision in the caller still uses the original minimax: model string.
    """
    from arnold.pipelines.megaplan.runtime.key_pool import acquire_key, report_429

    exc_str = str(exc)
    if "429" in exc_str:
        if model and model.startswith("minimax:"):
            report_429("minimax", agent_kwargs.get("api_key", ""), cooldown_secs=60)
        elif model and model.startswith("zhipu:"):
            cooldown = 3600 if "Limit Exhausted" in exc_str else 120
            report_429("zhipu", agent_kwargs.get("api_key", ""), cooldown_secs=cooldown)

    if model and model.startswith("minimax:"):
        or_key = acquire_key("openrouter")
        if or_key:
            from arnold.pipelines.megaplan.runtime.key_pool import minimax_openrouter_model

            fallback_model = minimax_openrouter_model(model[len("minimax:"):])
            fallback_kwargs = {"base_url": "https://openrouter.ai/api/v1", "api_key": or_key}
            if isinstance(exc, CliError):
                print(
                    f"{log_prefix} MiniMax returned bad content ({_failure_reason(exc)}), falling back to OpenRouter",
                    file=stream,
                )
            else:
                print(f"{log_prefix} Primary MiniMax failed ({exc}), falling back to OpenRouter", file=stream)
            output_path = rebuild_template_fn()
            agent = make_agent_fn(fallback_model, fallback_kwargs)
            try:
                return run_attempt_fn(agent, output_path)
            except Exception as fallback_exc:
                raise CliError(
                    "worker_error",
                    on_fail_message(exc, fallback_exc),
                ) from fallback_exc
        else:
            raise exc
    else:
        raise exc


def scatter_gather_checks(
    *,
    num_checks: int,
    submit_check_fn: Callable[[Any], list[Any]],
    side_tasks: list[Callable[[Any], Any]] | None = None,
    max_concurrent: int | None = None,
) -> ScatterResult:
    """Compatibility wrapper around :func:`scatter_gather`.

    Preserves the historical 8-tuple unit contract and the verified/disputed
    flag-union semantics used by critique/review callers.
    """
    def _unpack_check_result(
        result: Any,
    ) -> tuple[int, tuple[dict[str, Any], list[str], list[str]], float, int, int, int]:
        index, check_payload, verified_ids, disputed_ids, cost_usd, pt, ct, tt = result
        return index, (check_payload, verified_ids, disputed_ids), cost_usd, pt, ct, tt

    sr = scatter_gather(
        num_units=num_checks,
        submit_unit_fn=submit_check_fn,
        side_tasks=side_tasks,
        max_concurrent=max_concurrent,
        unpack_unit_result=_unpack_check_result,
    )

    ordered_checks: list[dict[str, Any]] = []
    verified_groups: list[list[str]] = []
    disputed_groups: list[list[str]] = []
    for item in sr.ordered_results:
        check_payload, verified_ids, disputed_ids = item
        ordered_checks.append(check_payload)
        verified_groups.append(verified_ids)
        disputed_groups.append(disputed_ids)

    disputed_flag_ids = _merge_unique(disputed_groups)
    disputed_set = set(disputed_flag_ids)
    verified_flag_ids = [
        flag_id for flag_id in _merge_unique(verified_groups) if flag_id not in disputed_set
    ]

    return ScatterResult(
        ordered_checks=ordered_checks,
        verified_flag_ids=verified_flag_ids,
        disputed_flag_ids=disputed_flag_ids,
        total_cost=sr.total_cost,
        total_prompt_tokens=sr.total_prompt_tokens,
        total_completion_tokens=sr.total_completion_tokens,
        total_tokens=sr.total_tokens,
        side_results=sr.side_results,
    )


def scatter_gather(
    *,
    num_units: int,
    submit_unit_fn: Callable[[Any], list[Any]],
    side_tasks: list[Callable[[Any], Any]] | None = None,
    max_concurrent: int | None = None,
    unpack_unit_result: Callable[[Any], tuple[int, Any, float, int, int, int]] | None = None,
    unpack_side_result: Callable[[Any], tuple[Any, float, int, int, int]] | None = None,
    on_unit_error: Callable[[int, Exception], tuple[Any, float, int, int, int]] | None = None,
) -> GenericScatterResult:
    """Run check futures (and optional side tasks) in a bounded thread pool.

    submit_unit_fn(executor) must return a list of Future objects. By default,
    each future must yield a 6-tuple:
    (index, payload, cost_usd, prompt_tokens, completion_tokens, total_tokens).
    ``unpack_unit_result`` may adapt richer result shapes.

    Each element of side_tasks is a callable (executor) -> Future; by default
    each future must yield (payload, cost_usd, prompt_tokens,
    completion_tokens, total_tokens). Side costs are accumulated into the
    returned totals.

    ``on_unit_error`` enables tolerant fan-out: it receives the unit index and
    exception and must return a sentinel payload plus zero-or-real cost/token
    metrics. When omitted, the first unit failure raises as before.

    max_concurrent=None is resolved to get_effective('orchestration',
    'max_critique_concurrency') inside this helper, before the min() cap.

    Internally delegates to :func:`arnold.runtime.batch.scatter_gather_threaded`
    after resolving Megaplan config at the boundary.
    """
    from arnold.runtime.batch import (
        BatchRuntimeSettings,
        BatchUnit,
        BatchUnitResult,
        scatter_gather_threaded,
    )

    if unpack_unit_result is None:
        unpack_unit_result = lambda result: result
    if unpack_side_result is None:
        unpack_side_result = lambda result: result

    effective_max = (
        max_concurrent
        if max_concurrent is not None
        else get_effective("orchestration", "max_critique_concurrency")
    )
    _side = side_tasks or []
    total_futures = num_units + len(_side)
    if total_futures == 0:
        return GenericScatterResult(
            ordered_results=[],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )
    concurrency = min(effective_max, total_futures)

    # Pre-submit all futures; scatter_gather_threaded resolves them.
    submit_executor = ThreadPoolExecutor(max_workers=concurrency)
    try:
        unit_futures = submit_unit_fn(submit_executor)
        side_futures = [task(submit_executor) for task in _side]

        side_future_to_idx = {f: i for i, f in enumerate(side_futures)}
        unit_future_map: dict[Any, int] = {}
        for future in unit_futures:
            try:
                idx = int(getattr(future, "_megaplan_unit_index"))
            except Exception:
                idx = len(unit_future_map)
            unit_future_map[future] = idx

        # Build BatchUnits: each resolves one pre-submitted future
        units: list[BatchUnit] = []
        for future in unit_futures:
            idx = unit_future_map[future]
            units.append(BatchUnit(
                unit_id="u{}".format(idx),
                payload=(future, "unit", idx),
                metadata={"kind": "unit", "index": idx},
            ))
        for future in side_futures:
            idx = side_future_to_idx[future]
            units.append(BatchUnit(
                unit_id="s{}".format(idx),
                payload=(future, "side", idx),
                metadata={"kind": "side", "index": idx},
            ))

        settings = BatchRuntimeSettings(max_workers=concurrency)

        # Shared state for cost/token aggregation and payload storage.
        _side_store: dict[str, tuple[float, int, int, int]] = {}
        _agg_cost = 0.0
        _agg_pt = 0
        _agg_ct = 0
        _agg_tt = 0

        def _run_unit(unit: BatchUnit, _settings: BatchRuntimeSettings) -> Any:
            future, _kind, _idx = unit.payload
            return future.result()

        def _parse_result(
            raw: Any, unit: BatchUnit, _settings: BatchRuntimeSettings,
        ) -> Any:
            nonlocal _agg_cost, _agg_pt, _agg_ct, _agg_tt
            kind = unit.metadata["kind"]
            if kind == "side":
                payload, cost_usd, pt, ct, tt = unpack_side_result(raw)
                _agg_cost += cost_usd
                _agg_pt += pt
                _agg_ct += ct
                _agg_tt += tt
                _side_store[unit.unit_id] = (cost_usd, pt, ct, tt)
                return raw
            _index, payload, cost_usd, pt, ct, tt = unpack_unit_result(raw)
            _agg_cost += cost_usd
            _agg_pt += pt
            _agg_ct += ct
            _agg_tt += tt
            _side_store[unit.unit_id] = (cost_usd, pt, ct, tt)
            return payload

        def _on_unit_error(
            unit: BatchUnit, exc: BaseException, _settings: BatchRuntimeSettings,
        ) -> BatchUnitResult:
            nonlocal _agg_cost, _agg_pt, _agg_ct, _agg_tt
            kind = unit.metadata["kind"]
            idx = unit.metadata["index"]
            if kind == "side":
                return BatchUnitResult(
                    unit_id=unit.unit_id,
                    error=str(exc),
                )
            if on_unit_error is None:
                raise exc
            payload, cost_usd, pt, ct, tt = on_unit_error(idx, Exception(str(exc)))
            _agg_cost += cost_usd
            _agg_pt += pt
            _agg_ct += ct
            _agg_tt += tt
            return BatchUnitResult(
                unit_id=unit.unit_id,
                result=payload,
                cost_usd=cost_usd,
                tokens=pt + ct,
            )

        batch_result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_run_unit,
            parse_result=_parse_result,
            on_unit_error=_on_unit_error if on_unit_error is not None else None,
            max_workers=concurrency,
        )
    finally:
        submit_executor.shutdown(wait=False)

    # Translate BatchRunResult -> GenericScatterResult
    ordered: list[Any] = [None] * num_units
    side_list: list[Any] = []
    total_cost = _agg_cost
    total_pt = _agg_pt
    total_ct = _agg_ct
    total_tt = _agg_tt

    for ur in batch_result.ordered_results:
        sid = ur.unit_id
        if sid.startswith("s"):
            if ur.result is not None:
                side_list.append(ur.result)
        else:
            try:
                idx = int(sid[1:])
            except (ValueError, IndexError):
                idx = len([x for x in ordered if x is not None])
            if idx < num_units:
                ordered[idx] = ur.result if ur.result is not None else ur.error

    for i in range(num_units):
        if ordered[i] is None:
            raise CliError("worker_error", "Parallel fan-out did not return all unit results")

    return GenericScatterResult(
        ordered_results=ordered,
        total_cost=total_cost,
        total_prompt_tokens=total_pt,
        total_completion_tokens=total_ct,
        total_tokens=total_tt,
        side_results=side_list,
    )


def scatter_gather_processes(
    *,
    units: list[Any],
    run_unit_fn: Callable[[int, Any], tuple[int, Any, float, int, int, int]],
    max_concurrent: int | None = None,
    on_unit_error: Callable[[int, Exception], tuple[Any, float, int, int, int]] | None = None,
    timeout_seconds: float | None = None,
    hard_kill_grace_seconds: float = 5.0,
    metadata_fn: Callable[[int, Any], dict[str, Any]] | None = None,
) -> GenericScatterResult:
    """Process-isolated scatter/gather for research units.

    The callable must be picklable. Results use the same six-field unit shape
    as ``scatter_gather`` and are returned in input order. When
    ``on_unit_error`` is supplied, failed children become ordered sentinels and
    sibling units continue.

    When ``timeout_seconds`` is supplied, each unit gets its own deadline. A
    child that exceeds the deadline is terminated, then killed if it is still
    alive after ``hard_kill_grace_seconds``.

    Internally delegates to ``arnold.runtime.batch.scatter_gather_processes``
    after resolving Megaplan config at the boundary.
    """
    from arnold.runtime.batch import (
        BatchRuntimeSettings,
        BatchUnit,
        BatchUnitResult,
        scatter_gather_processes as _arnold_scatter_gather,
    )

    # ------------------------------------------------------------------
    # Input validation (preserve legacy error behavior)
    # ------------------------------------------------------------------
    if not units:
        return GenericScatterResult([], 0.0, 0, 0, 0, [])
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if hard_kill_grace_seconds < 0:
        raise ValueError("hard_kill_grace_seconds must be non-negative")

    # ------------------------------------------------------------------
    # Resolve max_concurrent at Megaplan boundary
    # ------------------------------------------------------------------
    effective_max = (
        max_concurrent
        if max_concurrent is not None
        else get_effective("orchestration", "max_critique_concurrency")
    )
    concurrency = min(effective_max, len(units))
    if concurrency <= 0:
        raise ValueError("max_concurrent must be positive")

    # ------------------------------------------------------------------
    # Shared aggregation state (GIL-dependent, same pattern as scatter_gather)
    # ------------------------------------------------------------------
    _agg_cost = 0.0
    _agg_pt = 0
    _agg_ct = 0
    _agg_tt = 0

    # ------------------------------------------------------------------
    # Build BatchUnits and settings
    # ------------------------------------------------------------------
    settings = BatchRuntimeSettings(max_workers=concurrency)
    batch_units: list[BatchUnit] = []
    for i, unit in enumerate(units):
        meta: dict[str, Any] = {"index": i}
        if metadata_fn is not None:
            meta.update(metadata_fn(i, unit))
        batch_units.append(BatchUnit(unit_id=str(i), payload=unit, metadata=meta))

    # ------------------------------------------------------------------
    # Picklable run_unit adapter
    # ------------------------------------------------------------------
    _run_adapter = _ProcessRunUnitAdapter(run_unit_fn)

    # ------------------------------------------------------------------
    # Parse result: extract payload and aggregate cost/tokens
    # ------------------------------------------------------------------
    def _parse_result(raw: Any, _unit: BatchUnit, _settings: BatchRuntimeSettings) -> Any:
        nonlocal _agg_cost, _agg_pt, _agg_ct, _agg_tt
        _index, payload, cost_usd, pt, ct, tt = raw
        _agg_cost += cost_usd
        _agg_pt += pt
        _agg_ct += ct
        _agg_tt += tt
        return payload

    # ------------------------------------------------------------------
    # on_unit_error bridge
    # ------------------------------------------------------------------
    def _on_unit_error(
        batch_unit: BatchUnit, exc: BaseException, _settings: BatchRuntimeSettings,
    ) -> BatchUnitResult:
        nonlocal _agg_cost, _agg_pt, _agg_ct, _agg_tt
        if on_unit_error is None:
            raise exc
        idx = batch_unit.metadata["index"]
        payload, cost_usd, pt, ct, tt = on_unit_error(idx, Exception(str(exc)))
        _agg_cost += cost_usd
        _agg_pt += pt
        _agg_ct += ct
        _agg_tt += tt
        return BatchUnitResult(
            unit_id=batch_unit.unit_id,
            result=payload,
            cost_usd=cost_usd,
            tokens=pt + ct,
        )

    # ------------------------------------------------------------------
    # Delegate to Arnold
    # ------------------------------------------------------------------
    batch_result = _arnold_scatter_gather(
        units=batch_units,
        settings=settings,
        run_unit=_run_adapter,
        parse_result=_parse_result,
        on_unit_error=_on_unit_error if on_unit_error is not None else None,
        max_workers=concurrency,
        wall_timeout_s=timeout_seconds,
        hard_kill_grace_seconds=hard_kill_grace_seconds,
    )

    # ------------------------------------------------------------------
    # Translate BatchRunResult → GenericScatterResult
    # ------------------------------------------------------------------
    outcome = batch_result.outcome_kind

    if outcome in ("deadline_expired", "cancelled", "idle_unsupported", "heartbeat_unsupported"):
        # Arnold returned a neutral preflight outcome — no units were executed.
        if on_unit_error is not None:
            # Produce sentinel results for all units via on_unit_error.
            ordered: list[Any] = []
            for i, unit in enumerate(units):
                exc_msg = batch_result.errors[0] if batch_result.errors else outcome
                payload, cost_usd, pt, ct, tt = on_unit_error(
                    i, RuntimeError(str(exc_msg)),
                )
                ordered.append(payload)
                _agg_cost += cost_usd
                _agg_pt += pt
                _agg_ct += ct
                _agg_tt += tt
        else:
            raise CliError(
                "worker_error",
                f"Process fan-out: {outcome} — "
                f"{batch_result.errors[0] if batch_result.errors else 'unknown'}",
            )
    else:
        # completed / error: extract ordered results
        ordered = [ur.result for ur in batch_result.ordered_results]
        for i, item in enumerate(ordered):
            if item is None:
                raise CliError(
                    "worker_error",
                    "Process fan-out did not return all unit results",
                )

    return GenericScatterResult(
        ordered_results=ordered,
        total_cost=_agg_cost,
        total_prompt_tokens=_agg_pt,
        total_completion_tokens=_agg_ct,
        total_tokens=_agg_tt,
        side_results=[],
    )


class _ProcessRunUnitAdapter:
    """Picklable adapter from Megaplan ``run_unit_fn`` to Arnold ``RunUnitHook``.

    Defined at module level so ``multiprocessing`` spawn can pickle it.
    """

    __slots__ = ("_run_unit_fn",)

    def __init__(self, run_unit_fn: Callable) -> None:
        self._run_unit_fn = run_unit_fn

    def __call__(self, batch_unit: Any, _settings: Any) -> Any:
        idx = batch_unit.metadata["index"]
        unit = batch_unit.payload
        return self._run_unit_fn(idx, unit)
