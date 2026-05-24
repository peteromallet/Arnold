"""Shared fan-out primitives for parallel Hermes critique and review."""

from __future__ import annotations

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
    """Run check futures (and optional side tasks) in a bounded thread pool.

    submit_check_fn(executor) must return a list of Future objects; each future
    must yield an 8-tuple: (index, check_payload, verified_ids, disputed_ids,
    cost_usd, prompt_tokens, completion_tokens, total_tokens).

    Each element of side_tasks is a callable (executor) -> Future; each future
    must yield a tuple whose first element is the side-task payload and whose
    remaining four elements are (cost_usd, prompt_tokens, completion_tokens,
    total_tokens).  Side costs ARE accumulated into the returned totals.

    max_concurrent=None is resolved to get_effective('orchestration',
    'max_critique_concurrency') inside this helper, before the min() cap.
    """
    effective_max = (
        max_concurrent
        if max_concurrent is not None
        else get_effective("orchestration", "max_critique_concurrency")
    )
    _side = side_tasks or []
    total_futures = num_checks + len(_side)
    concurrency = min(effective_max, total_futures)

    results: list[tuple[dict[str, Any], list[str], list[str]] | None] = [None] * num_checks
    side_results: list[Any] = [None] * len(_side)
    total_cost = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        check_futures = submit_check_fn(executor)
        side_futures = [task(executor) for task in _side]
        side_future_to_idx = {f: i for i, f in enumerate(side_futures)}
        all_futures = list(check_futures) + side_futures

        for future in as_completed(all_futures):
            result = future.result()
            if future in side_future_to_idx:
                idx = side_future_to_idx[future]
                side_results[idx] = result
                _payload, cost_usd, pt, ct, tt = result
            else:
                index, check_payload, verified_ids, disputed_ids, cost_usd, pt, ct, tt = result
                results[index] = (check_payload, verified_ids, disputed_ids)
            total_cost += cost_usd
            total_prompt_tokens += pt
            total_completion_tokens += ct
            total_tokens += tt

    ordered_checks: list[dict[str, Any]] = []
    verified_groups: list[list[str]] = []
    disputed_groups: list[list[str]] = []
    for item in results:
        if item is None:
            raise CliError("worker_error", "Parallel check did not return all check results")
        check_payload, verified_ids, disputed_ids = item
        ordered_checks.append(check_payload)
        verified_groups.append(verified_ids)
        disputed_groups.append(disputed_ids)

    disputed_flag_ids = _merge_unique(disputed_groups)
    disputed_set = set(disputed_flag_ids)
    verified_flag_ids = [flag_id for flag_id in _merge_unique(verified_groups) if flag_id not in disputed_set]

    return ScatterResult(
        ordered_checks=ordered_checks,
        verified_flag_ids=verified_flag_ids,
        disputed_flag_ids=disputed_flag_ids,
        total_cost=total_cost,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        side_results=side_results,
    )
