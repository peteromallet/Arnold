"""Pure runtime contracts for vendorable agent execution boundaries."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from arnold.pipelines.megaplan.types import AgentMode, AgentSpec, format_agent_spec, parse_agent_spec


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class CostUsage:
    cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class ResultProvenance:
    agent: str | None = None
    mode: str | None = None
    model: str | None = None
    resolved_model: str | None = None
    effort: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentRequest:
    agent: str
    mode: str
    model: str | None = None
    resolved_model: str | None = None
    effort: str | None = None
    spec: AgentSpec | None = None
    read_only: bool = True
    prompt: str | None = None
    system_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float | None = None
    provenance: ResultProvenance | None = None
    attestation: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentResult:
    payload: dict[str, Any]
    raw_output: str
    duration_ms: int
    cost_usd: float
    session_id: str | None = None
    trace_output: str | None = None
    rendered_prompt: str | None = None
    model_actual: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    shannon_plan: dict[str, Any] | None = None
    provenance: ResultProvenance | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens(self) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
        )

    @property
    def cost(self) -> CostUsage:
        return CostUsage(cost_usd=self.cost_usd)


@dataclass(frozen=True, slots=True)
class FanoutUnit:
    request: AgentRequest
    key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FanoutResult:
    results: tuple[AgentResult, ...]
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class _DispatchesAgentRequests(Protocol):
    def dispatch(self, request: AgentRequest) -> AgentResult: ...


def _fanout_result_from_results(results: list[AgentResult]) -> FanoutResult:
    return FanoutResult(
        results=tuple(results),
        cost_usd=sum(result.cost_usd for result in results),
        prompt_tokens=sum(result.prompt_tokens for result in results),
        completion_tokens=sum(result.completion_tokens for result in results),
        total_tokens=sum(result.total_tokens for result in results),
    )


def scatter_agent_units(
    *,
    units: list[FanoutUnit],
    dispatcher: _DispatchesAgentRequests,
    max_concurrent: int | None = None,
    on_unit_error: Callable[[int, FanoutUnit, Exception], AgentResult] | None = None,
) -> FanoutResult:
    """Dispatch read-only agent units through an injected local dispatcher.

    This generalizes the proven one-shot shape from the prep-vendor-agnostic branch:
    ``run_step_with_worker(read_only=True, output_path=<caller-owned>)``.
    Each unit's :class:`AgentRequest` carries the same semantics — agent, mode,
    model, output path, read_only flag, prompt, timeout, and parse hooks — so
    injected dispatchers and process fan-out speak the same contract.

    This is *worker fan-out* (thread-based, injected dispatcher).  For
    process-isolated fan-out over CLI workers, see
    :mod:`megaplan.agent_runtime.process_fanout` and
    :mod:`megaplan._core.worker_fanout`.
    """
    if not units:
        return FanoutResult(results=())
    if max_concurrent is not None and max_concurrent <= 0:
        raise ValueError("max_concurrent must be positive")

    concurrency = min(max_concurrent or len(units), len(units))
    results: list[AgentResult | None] = [None] * len(units)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_index: dict[Future[AgentResult], int] = {
            executor.submit(dispatcher.dispatch, unit.request): index
            for index, unit in enumerate(units)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
            except Exception as exc:
                if on_unit_error is None:
                    raise
                result = on_unit_error(index, units[index], exc)
            results[index] = result

    ordered_results: list[AgentResult] = []
    for result in results:
        if result is None:
            raise RuntimeError("agent fan-out did not return all unit results")
        ordered_results.append(result)
    return _fanout_result_from_results(ordered_results)


__all__ = [
    "AgentRequest",
    "AgentResult",
    "TokenUsage",
    "CostUsage",
    "ResultProvenance",
    "FanoutUnit",
    "FanoutResult",
    "scatter_agent_units",
    "AgentSpec",
    "AgentMode",
    "parse_agent_spec",
    "format_agent_spec",
]
