"""Shared fan-out primitives for parallel Hermes orchestration."""

from __future__ import annotations

import multiprocessing as mp
import queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, NamedTuple

from .io import get_effective
from megaplan.types import CliError


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
    from megaplan.runtime.key_pool import acquire_key, report_429

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
            from megaplan.runtime.key_pool import minimax_openrouter_model

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
    """
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

    results: list[Any | None] = [None] * num_units
    side_results: list[Any] = [None] * len(_side)
    total_cost = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        unit_futures = submit_unit_fn(executor)
        side_futures = [task(executor) for task in _side]
        side_future_to_idx = {f: i for i, f in enumerate(side_futures)}
        unit_future_to_idx: dict[Any, int] = {}
        for future in unit_futures:
            try:
                idx = int(getattr(future, "_megaplan_unit_index"))
            except Exception:
                idx = len(unit_future_to_idx)
            unit_future_to_idx[future] = idx
        all_futures = list(unit_futures) + side_futures

        for future in as_completed(all_futures):
            if future in side_future_to_idx:
                result = future.result()
                idx = side_future_to_idx[future]
                payload, cost_usd, pt, ct, tt = unpack_side_result(result)
                side_results[idx] = result
            else:
                idx = unit_future_to_idx[future]
                try:
                    result = future.result()
                    index, payload, cost_usd, pt, ct, tt = unpack_unit_result(result)
                except Exception as exc:
                    if on_unit_error is None:
                        raise
                    payload, cost_usd, pt, ct, tt = on_unit_error(idx, exc)
                    index = idx
                results[index] = payload
            total_cost += cost_usd
            total_prompt_tokens += pt
            total_completion_tokens += ct
            total_tokens += tt

    ordered_results: list[Any] = []
    for item in results:
        if item is None:
            raise CliError("worker_error", "Parallel fan-out did not return all unit results")
        ordered_results.append(item)

    return GenericScatterResult(
        ordered_results=ordered_results,
        total_cost=total_cost,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        side_results=side_results,
    )


def scatter_gather_processes(
    *,
    units: list[Any],
    run_unit_fn: Callable[[int, Any], tuple[int, Any, float, int, int, int]],
    max_concurrent: int | None = None,
    on_unit_error: Callable[[int, Exception], tuple[Any, float, int, int, int]] | None = None,
    timeout_seconds: float | None = None,
    hard_kill_grace_seconds: float = 5.0,
) -> GenericScatterResult:
    """Process-isolated scatter/gather for research units.

    The callable must be picklable. Results use the same six-field unit shape
    as ``scatter_gather`` and are returned in input order. When
    ``on_unit_error`` is supplied, failed children become ordered sentinels and
    sibling units continue.

    When ``timeout_seconds`` is supplied, each unit gets its own deadline. A
    child that exceeds the deadline is terminated, then killed if it is still
    alive after ``hard_kill_grace_seconds``. This helper owns the child
    processes directly so a timed-out unit can be cleaned up without cancelling
    siblings or using a nested process pool.
    """
    if not units:
        return GenericScatterResult([], 0.0, 0, 0, 0, [])
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if hard_kill_grace_seconds < 0:
        raise ValueError("hard_kill_grace_seconds must be non-negative")
    effective_max = (
        max_concurrent
        if max_concurrent is not None
        else get_effective("orchestration", "max_critique_concurrency")
    )
    concurrency = min(effective_max, len(units))
    if concurrency <= 0:
        raise ValueError("max_concurrent must be positive")
    results: list[Any | None] = [None] * len(units)
    total_cost = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    ctx = mp.get_context("spawn")
    pending = list(enumerate(units))
    active: dict[int, dict[str, Any]] = {}

    def _launch_next() -> None:
        if not pending:
            return
        index, unit = pending.pop(0)
        out_queue: Any = ctx.Queue()
        proc = ctx.Process(
            target=_run_process_unit_child,
            args=(run_unit_fn, index, unit, out_queue),
        )
        proc.start()
        active[index] = {
            "process": proc,
            "queue": out_queue,
            "started_at": time.monotonic(),
            "terminating_since": None,
        }

    def _record(idx: int, payload: Any, cost_usd: float, pt: int, ct: int, tt: int) -> None:
        nonlocal total_cost, total_prompt_tokens, total_completion_tokens, total_tokens
        results[idx] = payload
        total_cost += cost_usd
        total_prompt_tokens += pt
        total_completion_tokens += ct
        total_tokens += tt

    def _sentinel(idx: int, exc: Exception) -> None:
        if on_unit_error is None:
            raise exc
        payload, cost_usd, pt, ct, tt = on_unit_error(idx, exc)
        _record(idx, payload, cost_usd, pt, ct, tt)

    def _cleanup_active() -> None:
        for item in active.values():
            proc = item["process"]
            if proc.is_alive():
                proc.terminate()
        for item in active.values():
            proc = item["process"]
            proc.join(hard_kill_grace_seconds)
            if proc.is_alive():
                proc.kill()
                proc.join()

    for _ in range(concurrency):
        _launch_next()

    try:
        while active:
            now = time.monotonic()
            completed: list[int] = []
            for idx, item in list(active.items()):
                proc = item["process"]
                out_queue = item["queue"]
                try:
                    message = out_queue.get_nowait()
                except queue.Empty:
                    message = None

                if message is not None:
                    proc.join()
                    if message.get("ok"):
                        index, payload, cost_usd, pt, ct, tt = message["result"]
                        _record(index, payload, cost_usd, pt, ct, tt)
                    else:
                        exc = _ProcessUnitFailure(str(message.get("error", "")))
                        _sentinel(idx, exc)
                    completed.append(idx)
                    continue

                if (
                    timeout_seconds is not None
                    and item["terminating_since"] is None
                    and now - item["started_at"] >= timeout_seconds
                ):
                    item["terminating_since"] = now
                    if proc.is_alive():
                        proc.terminate()

                terminating_since = item["terminating_since"]
                if terminating_since is not None:
                    if proc.is_alive() and now - terminating_since >= hard_kill_grace_seconds:
                        proc.kill()
                    proc.join(0)
                    if not proc.is_alive():
                        _sentinel(
                            idx,
                            _ProcessUnitTimeout(
                                f"process unit {idx} timed out after {timeout_seconds:.3f}s"
                            ),
                        )
                        completed.append(idx)
                    continue

                if not proc.is_alive():
                    proc.join()
                    _sentinel(
                        idx,
                        _ProcessUnitFailure(f"process unit {idx} exited without a result"),
                    )
                    completed.append(idx)

            for idx in completed:
                active.pop(idx, None)
                _launch_next()
            if active:
                time.sleep(0.01)
    except Exception:
        _cleanup_active()
        raise

    ordered_results: list[Any] = []
    for item in results:
        if item is None:
            raise CliError("worker_error", "Process fan-out did not return all unit results")
        ordered_results.append(item)
    return GenericScatterResult(
        ordered_results=ordered_results,
        total_cost=total_cost,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        side_results=[],
    )
