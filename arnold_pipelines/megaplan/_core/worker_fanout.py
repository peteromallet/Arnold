"""Reusable worker fan-out primitives.

Provides :class:`WorkerUnit` and :func:`scatter_worker_units` for dispatching
multiple :func:`~megaplan.workers.run_step_with_worker` calls through
process-isolated fan-out with token/cost aggregation, deterministic output
paths, caller-supplied parse/reduce hooks, and error propagation.

This is *worker fan-out* — each unit dispatches through ``run_step_with_worker``,
the CLI-backed worker function that drives Claude (via Shannon interactive
tmux), Codex, and Hermes.  Each unit receives a caller-owned output path,
per-unit prompt, and resolved agent mode.  For process fan-out without the
worker dispatch layer, see :mod:`megaplan.agent_runtime.process_fanout`.  For
thread-based injected-dispatcher fan-out, see
:func:`megaplan.agent_runtime.scatter_agent_units`.

The proven one-shot shape that made vendor-agnostic fan-out work is
``run_step_with_worker(read_only=True, output_path=<caller-owned>)``; this
module's adapter (:func:`_worker_unit_to_agent_request`) generalizes that
pattern into the ``AgentRequest`` / ``AgentResult`` runtime contract.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from .hermes_fanout import GenericScatterResult, scatter_gather_processes
from arnold_pipelines.megaplan.agent_runtime import AgentRequest, AgentSpec, ResultProvenance
from arnold_pipelines.megaplan.fallback_chains import (
    ExecuteFallbackUnsafe,
    classify_retryability,
    is_retryable_classification,
    is_same_family_operational_classification,
    normalize_fallback_spec_list,
    provider_family,
)
from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan.model_seam import ModelBudgetError, ModelTier, render_step_message
from arnold_pipelines.megaplan.custody.worker_dispatch_wbc import build_worker_dispatch_spec
from arnold_pipelines.megaplan.types import (
    AgentMode,
    PlanState,
    format_agent_spec,
    parse_agent_spec,
    resolved_default_model_for_agent,
)


def _resolved_mode_spec(resolved: AgentMode) -> str:
    return format_agent_spec(
        AgentSpec(agent=resolved.agent, model=resolved.model, effort=resolved.effort)
    )


def _normalize_failed_attempt_reasons(
    value: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise TypeError("failed_attempt_reasons must be a list[str] or tuple[str, ...]")
    normalized: list[str] = []
    for index, reason in enumerate(value):
        if not isinstance(reason, str):
            raise TypeError(f"failed_attempt_reasons[{index}] must be a string")
        if not reason:
            raise ValueError(f"failed_attempt_reasons[{index}] must be a non-empty string")
        normalized.append(reason)
    return tuple(normalized)


def _normalize_fallback_trigger(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("fallback_trigger must be a string when provided")
    if not value:
        raise ValueError("fallback_trigger must be a non-empty string when provided")
    return value


@dataclass
class WorkerUnit:
    """One unit of work for the worker fan-out.

    Each unit is dispatched through :func:`run_step_with_worker` using its
    *resolved* agent mode, *prompt* override, *output_path*, and *read_only*
    flag.

    ``extra`` carries arbitrary caller metadata (e.g. check id, area label)
    that parse/reduce hooks can reference.
    """

    step: str
    """Step name passed to :func:`run_step_with_worker` (e.g. ``"critique"``)."""

    resolved: AgentMode
    """Resolved agent mode controlling which agent/model/effort is used."""

    prompt: str
    """Full prompt text (passed as ``prompt_override``)."""

    output_path: Path
    """Deterministic output path for the worker's template output."""

    read_only: bool = True
    """When *True* the worker cannot mutate the repository."""

    validation_step: str | None = None
    """Explicit schema-audit step name when it differs from ``step``."""

    schema: Mapping[str, Any] | None = None
    """Optional structured output schema to carry through dispatch metadata."""

    model: str | None = None
    """Optional normalized model label for dispatch/capture metadata."""

    tier: ModelTier | str | None = None
    """Optional seam tier override for dispatch/capture metadata."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Opaque caller metadata forwarded to parse/reduce hooks."""

    configured_specs: tuple[str, ...] = ()
    """Configured ordered fallback chain for this unit's selected route."""

    attempt_index: int = 0
    """0-based selected attempt inside ``configured_specs``."""

    attempted_specs: tuple[str, ...] = ()
    """Ordered specs already attempted for this worker unit."""

    failed_attempt_reasons: tuple[str, ...] = ()
    """Ordered machine-readable reasons aligned to failed attempted specs."""

    fallback_trigger: str | None = None
    """Machine-readable trigger that advanced to the current attempt."""

    def __post_init__(self) -> None:
        self.configured_specs = normalize_fallback_spec_list(
            self.configured_specs or (_resolved_mode_spec(self.resolved),),
            path="WorkerUnit.configured_specs",
        )
        self.attempted_specs = normalize_fallback_spec_list(
            self.attempted_specs or self.configured_specs[: self.attempt_index + 1],
            path="WorkerUnit.attempted_specs",
        )
        self.failed_attempt_reasons = _normalize_failed_attempt_reasons(
            self.failed_attempt_reasons
        )
        self.fallback_trigger = _normalize_fallback_trigger(self.fallback_trigger)
        if self.attempt_index < 0:
            raise ValueError("attempt_index must be non-negative")
        if self.attempt_index >= len(self.configured_specs):
            raise ValueError(
                f"attempt_index {self.attempt_index} is out of range for "
                f"{len(self.configured_specs)} configured_specs"
            )
        if len(self.failed_attempt_reasons) > len(self.attempted_specs):
            raise ValueError(
                "failed_attempt_reasons cannot exceed attempted_specs length"
            )


@dataclass
class WorkerUnitResult:
    """Rich, picklable worker result carried as the process fan-out payload."""

    payload: Any
    raw_output: str
    duration_ms: int
    cost_usd: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    session_id: str | None = None
    trace_output: str | None = None
    rendered_prompt: str | None = None
    model_actual: str | None = None
    shannon_plan: dict[str, Any] | None = None
    rate_limit: dict[str, Any] | None = None
    step: str | None = None
    output_path: str | None = None
    read_only: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
    agent: str | None = None
    mode: str | None = None
    model: str | None = None
    resolved_model: str | None = None
    effort: str | None = None
    configured_specs: tuple[str, ...] = ()
    attempt_index: int = 0
    attempted_specs: tuple[str, ...] = ()
    failed_attempt_reasons: tuple[str, ...] = ()
    fallback_trigger: str | None = None

    def __post_init__(self) -> None:
        selected_spec = AgentSpec(
            agent=self.agent or "unknown",
            model=self.model,
            effort=self.effort,
        )
        self.configured_specs = normalize_fallback_spec_list(
            self.configured_specs or (format_agent_spec(selected_spec),),
            path="WorkerUnitResult.configured_specs",
        )
        self.attempted_specs = normalize_fallback_spec_list(
            self.attempted_specs or self.configured_specs[: self.attempt_index + 1],
            path="WorkerUnitResult.attempted_specs",
        )
        self.failed_attempt_reasons = _normalize_failed_attempt_reasons(
            self.failed_attempt_reasons
        )
        self.fallback_trigger = _normalize_fallback_trigger(self.fallback_trigger)
        if self.attempt_index < 0:
            raise ValueError("attempt_index must be non-negative")
        if self.attempt_index >= len(self.configured_specs):
            raise ValueError(
                f"attempt_index {self.attempt_index} is out of range for "
                f"{len(self.configured_specs)} configured_specs"
            )
        if len(self.failed_attempt_reasons) > len(self.attempted_specs):
            raise ValueError(
                "failed_attempt_reasons cannot exceed attempted_specs length"
            )

    @classmethod
    def from_worker_result(cls, worker: Any, unit: WorkerUnit) -> WorkerUnitResult:
        resolved = unit.resolved
        return cls(
            payload=worker.payload,
            raw_output=worker.raw_output,
            duration_ms=worker.duration_ms,
            cost_usd=worker.cost_usd,
            prompt_tokens=worker.prompt_tokens,
            completion_tokens=worker.completion_tokens,
            total_tokens=worker.total_tokens,
            session_id=worker.session_id,
            trace_output=worker.trace_output,
            rendered_prompt=worker.rendered_prompt,
            model_actual=worker.model_actual,
            shannon_plan=worker.shannon_plan,
            rate_limit=worker.rate_limit,
            step=unit.step,
            output_path=str(unit.output_path),
            read_only=unit.read_only,
            extra=dict(unit.extra),
            agent=resolved.agent,
            mode=resolved.mode,
            model=resolved.model,
            resolved_model=resolved.resolved_model,
            effort=resolved.effort,
            configured_specs=unit.configured_specs,
            attempt_index=unit.attempt_index,
            attempted_specs=unit.attempted_specs,
            failed_attempt_reasons=unit.failed_attempt_reasons,
            fallback_trigger=unit.fallback_trigger,
        )


def _worker_unit_to_agent_request(
    unit: WorkerUnit,
    *,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    args: argparse.Namespace,
    index: int | None = None,
    parse_result: Callable[[int, Any, WorkerUnit], Any] | None = None,
    on_unit_error: (
        Callable[[int, Exception], tuple[Any, float, int, int, int]] | None
    ) = None,
    max_concurrent: int | None = None,
    timeout_seconds: float | None = None,
    isolation: str | None = None,
) -> AgentRequest:
    """Adapt a legacy :class:`WorkerUnit` into the runtime request contract."""
    resolved = unit.resolved
    validation_step = unit.validation_step or unit.step
    worker_options = unit.extra.get("worker_options")
    worker_options_model = worker_options.get("resolved_model") if isinstance(worker_options, dict) else None
    model_name = (
        unit.model
        or resolved.resolved_model
        or worker_options_model
        or resolved.model
        or _fallback_model_for_worker_unit(unit)
    )
    tier = unit.tier or _default_worker_unit_tier(unit)
    rendered = _render_unit_prompt(
        unit,
        worker=resolved.agent,
        model_name=model_name,
        validation_step=validation_step,
        tier=tier,
    )
    spec = AgentSpec(
        agent=resolved.agent,
        model=resolved.model,
        effort=resolved.effort,
    )
    metadata = {
        "worker_unit": {
            "index": index,
            "step": unit.step,
            "validation_step": validation_step,
            "output_path": str(unit.output_path),
            "read_only": unit.read_only,
            "schema": dict(unit.schema) if unit.schema is not None else None,
            "model": model_name,
            "tier": tier.value if isinstance(tier, ModelTier) else str(tier),
            "extra": dict(unit.extra),
            "configured_specs": list(unit.configured_specs),
            "attempt_index": unit.attempt_index,
            "attempted_specs": list(unit.attempted_specs),
            "failed_attempt_reasons": list(unit.failed_attempt_reasons),
            "fallback_trigger": unit.fallback_trigger,
        },
        "fanout": {
            "parse_result": parse_result,
            "on_unit_error": on_unit_error,
            "max_concurrent": max_concurrent,
            "timeout_seconds": timeout_seconds,
            "isolation": isolation,
        },
        "paths": {
            "plan_dir": str(plan_dir),
            "root": str(root),
        },
        "state": state,
        "args": args,
    }
    if rendered is not None:
        metadata["model_seam"] = rendered.to_json()
    provenance = ResultProvenance(
        agent=resolved.agent,
        mode=resolved.mode,
        model=resolved.model,
        resolved_model=resolved.resolved_model,
        effort=resolved.effort,
        metadata={
            "worker_step": unit.step,
            "validation_step": validation_step,
            "output_path": str(unit.output_path),
            "read_only": unit.read_only,
            "model": model_name,
            "tier": tier.value if isinstance(tier, ModelTier) else str(tier),
            "configured_specs": list(unit.configured_specs),
            "attempt_index": unit.attempt_index,
            "attempted_specs": list(unit.attempted_specs),
            "failed_attempt_reasons": list(unit.failed_attempt_reasons),
            "fallback_trigger": unit.fallback_trigger,
        },
    )
    return AgentRequest(
        agent=resolved.agent,
        mode=resolved.mode,
        model=resolved.model,
        resolved_model=resolved.resolved_model,
        effort=resolved.effort,
        spec=spec,
        read_only=unit.read_only,
        prompt=rendered.prompt if rendered is not None else unit.prompt,
        metadata=metadata,
        timeout_seconds=timeout_seconds,
        provenance=provenance,
        attestation={
            "adapter": "arnold_pipelines.megaplan._core.worker_fanout._worker_unit_to_agent_request",
            "legacy_worker_entrypoint": "scatter_worker_unit",
        },
    )


def scatter_worker_unit(
    index: int,
    unit: WorkerUnit,
    *,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    args: argparse.Namespace,
    isolation: str = "thread",
) -> tuple[int, Any, float, int, int, int]:
    """Execute one :class:`WorkerUnit` through :func:`run_step_with_worker`.

    Returns the standard 6-tuple expected by fan-out collectors:

    ``(index, payload, cost_usd, prompt_tokens, completion_tokens, total_tokens)``

    The *isolation* parameter is a guard — callers must declare the expected
    isolation level (``"thread"`` or ``"process"``).  It does not change
    behaviour inside this function.
    """
    if isolation not in {"thread", "process"}:
        raise ValueError(f"unsupported isolation: {isolation}")

    # Deferred import to avoid circular import (worker_fanout is in _core,
    # and megaplan.workers imports from _core).
    from arnold_pipelines.megaplan.workers import run_step_with_worker

    worker_options = unit.extra.get("worker_options")
    if worker_options is not None and not isinstance(worker_options, dict):
        raise TypeError("WorkerUnit.extra['worker_options'] must be a dict when provided")
    validation_step = unit.validation_step or unit.step
    worker_options_model = worker_options.get("resolved_model") if isinstance(worker_options, dict) else None
    model_name = (
        unit.model
        or unit.resolved.resolved_model
        or worker_options_model
        or unit.resolved.model
        or _fallback_model_for_worker_unit(unit)
    )
    tier = unit.tier or _default_worker_unit_tier(unit)
    rendered = _render_unit_prompt(
        unit,
        worker=unit.resolved.agent,
        model_name=model_name,
        validation_step=validation_step,
        tier=tier,
    )

    worker, dispatched_unit = _run_worker_unit_with_ordered_fallback(
        unit,
        state=state,
        plan_dir=plan_dir,
        root=root,
        args=args,
        run_step_with_worker=run_step_with_worker,
        prompt_override=rendered.prompt if rendered is not None else unit.prompt,
        worker_options=dict(worker_options) if worker_options is not None else None,
    )
    unit_result = WorkerUnitResult.from_worker_result(worker, dispatched_unit)
    return (
        index,
        unit_result,
        unit_result.cost_usd,
        unit_result.prompt_tokens,
        unit_result.completion_tokens,
        unit_result.total_tokens,
    )


def _agent_mode_for_fallback_spec(base: AgentMode, spec: str) -> AgentMode:
    parsed = parse_agent_spec(spec)
    resolved_model = parsed.model
    if resolved_model is None and parsed.agent in {"claude", "codex"}:
        resolved_model = resolved_default_model_for_agent(parsed.agent)
    return AgentMode(
        agent=parsed.agent,
        mode=base.mode,
        refreshed=base.refreshed,
        model=parsed.model,
        effort=parsed.effort,
        resolved_model=resolved_model,
    )


def _next_fallback_index(
    unit: WorkerUnit,
    failed_index: int,
    classification: str,
) -> int | None:
    candidate_index = failed_index + 1
    if candidate_index >= len(unit.configured_specs):
        return None
    same_family = provider_family(unit.configured_specs[candidate_index]) == provider_family(
        unit.configured_specs[failed_index]
    )
    if same_family:
        if not unit.read_only:
            return None
        return (
            candidate_index
            if is_same_family_operational_classification(classification)  # type: ignore[arg-type]
            else None
        )
    return (
        candidate_index
        if is_retryable_classification(classification)  # type: ignore[arg-type]
        else None
    )


def _run_worker_unit_with_ordered_fallback(
    unit: WorkerUnit,
    *,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    args: argparse.Namespace,
    run_step_with_worker: Callable[..., Any],
    prompt_override: str,
    worker_options: dict[str, Any] | None,
) -> tuple[Any, WorkerUnit]:
    if unit.step in {"execute", "loop_execute"}:
        if unit.attempt_index > 0:
            raise ExecuteFallbackUnsafe(
                phase=unit.step,
                configured_specs=unit.configured_specs,
                attempted_index=unit.attempt_index,
            )
        try:
            return (
                _dispatch_worker_unit_attempt(
                    unit,
                    state=state,
                    plan_dir=plan_dir,
                    root=root,
                    args=args,
                    run_step_with_worker=run_step_with_worker,
                    prompt_override=prompt_override,
                    worker_options=worker_options,
                ),
                unit,
            )
        except Exception as exc:
            classification = classify_retryability(exc)
            next_index = _next_fallback_index(unit, unit.attempt_index, classification)
            if next_index is None:
                raise
            raise ExecuteFallbackUnsafe(
                phase=unit.step,
                configured_specs=unit.configured_specs,
                attempted_index=next_index,
            ) from exc

    if len(unit.configured_specs) == 1:
        return (
            _dispatch_worker_unit_attempt(
                unit,
                state=state,
                plan_dir=plan_dir,
                root=root,
                args=args,
                run_step_with_worker=run_step_with_worker,
                prompt_override=prompt_override,
                worker_options=worker_options,
            ),
            unit,
        )

    current = unit
    while True:
        try:
            return (
                _dispatch_worker_unit_attempt(
                    current,
                    state=state,
                    plan_dir=plan_dir,
                    root=root,
                    args=args,
                    run_step_with_worker=run_step_with_worker,
                    prompt_override=prompt_override,
                    worker_options=worker_options,
                ),
                current,
            )
        except Exception as exc:
            classification = classify_retryability(exc)
            next_index = _next_fallback_index(current, current.attempt_index, classification)
            if next_index is None:
                raise
            next_spec = current.configured_specs[next_index]
            current = WorkerUnit(
                step=current.step,
                resolved=_agent_mode_for_fallback_spec(current.resolved, next_spec),
                prompt=current.prompt,
                output_path=current.output_path,
                read_only=current.read_only,
                validation_step=current.validation_step,
                schema=current.schema,
                model=current.model,
                tier=current.tier,
                extra=dict(current.extra),
                configured_specs=current.configured_specs,
                attempt_index=next_index,
                attempted_specs=(
                    *current.attempted_specs,
                    *current.configured_specs[current.attempt_index + 1 : next_index + 1],
                ),
                failed_attempt_reasons=(
                    *current.failed_attempt_reasons,
                    classification,
                ),
                fallback_trigger=classification,
            )


def _dispatch_worker_unit_attempt(
    unit: WorkerUnit,
    *,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    args: argparse.Namespace,
    run_step_with_worker: Callable[..., Any],
    prompt_override: str,
    worker_options: dict[str, Any] | None,
) -> Any:
    options = dict(worker_options or {})
    if len(unit.configured_specs) > 1:
        options["_suppress_ambient_agent_fallback"] = True
    wbc_dispatch = build_worker_dispatch_spec(
        plan_dir=plan_dir,
        state=state,
        step=unit.step,
        phase_step=state.get("active_step", {}).get("_phase_wbc", {}).get("step")
        if isinstance(state.get("active_step"), dict)
        else None,
        agent=unit.resolved.agent,
        selected_spec=unit.configured_specs[unit.attempt_index],
        route_kind="subprocess",
        attempt_index=unit.attempt_index,
        configured_specs=unit.configured_specs,
        attempted_specs=unit.attempted_specs,
        failed_attempt_reasons=unit.failed_attempt_reasons,
        fallback_trigger=unit.fallback_trigger,
    )
    worker, _agent, _mode, _refreshed = run_step_with_worker(
        unit.step,
        state,
        plan_dir,
        args,
        root=root,
        resolved=unit.resolved,
        prompt_override=prompt_override,
        read_only=unit.read_only,
        output_path=unit.output_path,
        worker_options=options or None,
        ledger_step_label=(
            unit.extra.get("ledger_step_label")
            or unit.extra.get("check_id")
            or unit.extra.get("area_id")
            or unit.step
        ),
        ledger_selected_spec=unit.extra.get("ledger_selected_spec")
        or unit.configured_specs[unit.attempt_index],
        ledger_tier=unit.extra.get("ledger_tier"),
        ledger_complexity=unit.extra.get("ledger_complexity"),
        ledger_tier_routing_active=bool(unit.extra.get("ledger_tier_routing_active", False)),
        ledger_configured_specs=unit.configured_specs,
        ledger_attempt_index=unit.attempt_index,
        ledger_attempted_specs=unit.attempted_specs,
        ledger_failed_attempt_reasons=unit.failed_attempt_reasons,
        ledger_fallback_trigger=unit.fallback_trigger,
        wbc_dispatch=wbc_dispatch,
    )
    return worker


def _scatter_worker_unit_from_packed(
    index: int,
    packed: dict[str, Any],
) -> tuple[int, Any, float, int, int, int]:
    """Process-safe entry point: unpack a dict and dispatch one WorkerUnit.

    This module-level function is picklable, so it can be passed as the
    ``run_unit_fn`` to :func:`scatter_gather_processes`.
    """
    unit = WorkerUnit(
        step=packed["step"],
        resolved=packed["resolved"],
        prompt=packed["prompt"],
        output_path=Path(packed["output_path"]),
        read_only=packed.get("read_only", True),
        validation_step=packed.get("validation_step"),
        schema=packed.get("schema"),
        model=packed.get("model"),
        tier=packed.get("tier"),
        extra=packed.get("extra", {}),
        configured_specs=tuple(packed.get("configured_specs", ())),
        attempt_index=packed.get("attempt_index", 0),
        attempted_specs=tuple(packed.get("attempted_specs", ())),
        failed_attempt_reasons=tuple(packed.get("failed_attempt_reasons", ())),
        fallback_trigger=packed.get("fallback_trigger"),
    )
    return scatter_worker_unit(
        index,
        unit,
        state=packed["state"],
        plan_dir=Path(packed["plan_dir"]),
        root=Path(packed["root"]),
        args=packed["args"],
        isolation="process",
    )


def scatter_worker_units(
    *,
    units: list[WorkerUnit],
    side_units: list[WorkerUnit] | None = None,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    args: argparse.Namespace,
    parse_result: Callable[[int, Any, WorkerUnit], Any] | None = None,
    parse_side_result: Callable[[int, Any, WorkerUnit], Any] | None = None,
    on_unit_error: (
        Callable[[int, Exception], tuple[Any, float, int, int, int]] | None
    ) = None,
    max_concurrent: int | None = None,
    timeout_seconds: float | None = None,
) -> GenericScatterResult:
    """Scatter multiple :class:`WorkerUnit` instances via process-isolated fan-out.

    Each unit is dispatched through :func:`run_step_with_worker` with its
    *resolved* mode, *prompt* override, *output_path*, and *read_only* flag.
    This is *worker fan-out* — it drives CLI backends (Claude via Shannon
    interactive tmux, Codex, Hermes) through the worker dispatch layer.
    Token usage and cost are aggregated across all units.

    This generalizes the proven one-shot shape from the prep-vendor-agnostic
    branch: ``run_step_with_worker(read_only=True, output_path=<caller-owned>)``.
    Each unit's :class:`~megaplan.agent_runtime.AgentRequest` carries the same
    contract semantics.

    Parameters
    ----------
    units:
        Worker unit descriptions to dispatch.
    side_units:
        Optional side-worker descriptions dispatched in the same process fan-out
        batch. Their parsed outputs are returned in ``side_results``.
    state:
        Plan state (shared across all units).
    plan_dir:
        Plan directory (determines where worker artefacts are written).
    root:
        Repository root passed through to the worker.
    args:
        ``argparse.Namespace`` for worker dispatch compatibility.
    parse_result:
        Optional post-processing hook ``(index, worker_unit_result, unit) -> parsed``.
        When supplied, each result in the returned
        :class:`~megaplan._core.hermes_fanout.GenericScatterResult` is the
        return value of this hook.
    parse_side_result:
        Optional side-result hook with the same signature as ``parse_result``.
        When omitted, side results use the same legacy payload unwrapping as
        main results.
    on_unit_error:
        Optional error handler ``(index, exception) -> (payload, cost, pt, ct, tt)``.
        When omitted, the first unit failure propagates immediately.
    max_concurrent:
        Maximum number of concurrent workers (resolved via effective config
        when *None*).
    timeout_seconds:
        Per-unit wall-clock timeout in seconds.  Timed-out units are killed
        and reported via *on_unit_error* (or propagate if no handler).

    Returns
    -------
    GenericScatterResult
        Ordered results, aggregated costs, and token counts.
    """
    _side_units = side_units or []
    if not units and not _side_units:
        return GenericScatterResult(
            ordered_results=[],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    flattened_units: list[tuple[str, int, WorkerUnit]] = [
        ("main", i, u) for i, u in enumerate(units)
    ] + [("side", i, u) for i, u in enumerate(_side_units)]

    packed_units: list[dict[str, Any]] = []
    for role, original_index, u in flattened_units:
        packed_units.append(
            {
                "role": role,
                "original_index": original_index,
                "step": u.step,
                "resolved": u.resolved,
                "prompt": u.prompt,
                "output_path": str(u.output_path),
                "read_only": u.read_only,
                "validation_step": u.validation_step,
                "schema": dict(u.schema) if u.schema is not None else None,
                "model": u.model,
                "tier": u.tier.value if isinstance(u.tier, ModelTier) else u.tier,
                "extra": u.extra,
                "configured_specs": list(u.configured_specs),
                "attempt_index": u.attempt_index,
                "attempted_specs": list(u.attempted_specs),
                "failed_attempt_reasons": list(u.failed_attempt_reasons),
                "fallback_trigger": u.fallback_trigger,
                "state": state,
                "plan_dir": str(plan_dir),
                "root": str(root),
                "args": args,
            }
        )
    def _worker_metadata(index: int, packed: dict[str, Any]) -> dict[str, Any]:
        """Enrich BatchUnit metadata with WorkerUnit fields."""
        resolved: Any = packed.get("resolved")
        mode_labels: dict[str, Any] = {}
        if resolved is not None:
            mode_labels = {
                "agent": getattr(resolved, "agent", None),
                "mode": getattr(resolved, "mode", None),
                "model": getattr(resolved, "model", None),
                "resolved_model": getattr(resolved, "resolved_model", None),
                "effort": getattr(resolved, "effort", None),
            }
        return {
            "step": packed.get("step"),
            "validation_step": packed.get("validation_step"),
            "read_only": packed.get("read_only"),
            "schema": packed.get("schema"),
            "model_seam_model": packed.get("model"),
            "tier": packed.get("tier"),
            "extra": packed.get("extra"),
            "configured_specs": packed.get("configured_specs"),
            "attempt_index": packed.get("attempt_index"),
            "attempted_specs": packed.get("attempted_specs"),
            "failed_attempt_reasons": packed.get("failed_attempt_reasons"),
            "fallback_trigger": packed.get("fallback_trigger"),
            "mode_labels": mode_labels,
            "role": packed.get("role"),
            "original_index": packed.get("original_index"),
        }

    raw = scatter_gather_processes(
        units=packed_units,
        run_unit_fn=_scatter_worker_unit_from_packed,
        max_concurrent=max_concurrent,
        timeout_seconds=timeout_seconds,
        on_unit_error=on_unit_error,
        metadata_fn=_worker_metadata,
    )

    def _default_parse(item: Any) -> Any:
        return item.payload if isinstance(item, WorkerUnitResult) else item

    ordered_results: list[Any] = [None] * len(units)
    side_results: list[Any] = [None] * len(_side_units)
    for flat_index, item in enumerate(raw.ordered_results):
        role, original_index, unit = flattened_units[flat_index]
        if role == "main":
            if parse_result is not None:
                ordered_results[original_index] = parse_result(original_index, item, unit)
            else:
                ordered_results[original_index] = _default_parse(item)
        else:
            if parse_side_result is not None:
                side_results[original_index] = parse_side_result(
                    original_index,
                    item,
                    unit,
                )
            else:
                side_results[original_index] = _default_parse(item)

    if parse_result is not None:
        return GenericScatterResult(
            ordered_results=ordered_results,
            total_cost=raw.total_cost,
            total_prompt_tokens=raw.total_prompt_tokens,
            total_completion_tokens=raw.total_completion_tokens,
            total_tokens=raw.total_tokens,
            side_results=side_results,
        )

    return GenericScatterResult(
        ordered_results=ordered_results,
        total_cost=raw.total_cost,
        total_prompt_tokens=raw.total_prompt_tokens,
        total_completion_tokens=raw.total_completion_tokens,
        total_tokens=raw.total_tokens,
        side_results=side_results,
    )


def _default_worker_unit_tier(unit: WorkerUnit) -> ModelTier:
    agent = unit.resolved.agent
    if agent in {"codex", "hermes"}:
        return ModelTier.ENFORCED
    return ModelTier.NON_ENFORCED


def _fallback_model_for_worker_unit(unit: WorkerUnit) -> str | None:
    agent = unit.resolved.agent
    if agent == "shannon":
        return resolved_default_model_for_agent("claude")
    return resolved_default_model_for_agent(agent)


def _render_unit_prompt(
    unit: WorkerUnit,
    *,
    worker: str,
    model_name: str | None,
    validation_step: str,
    tier: ModelTier | str,
):
    if model_name is None:
        return None
    try:
        return render_step_message(
            StepInvocation(
                kind="model",
                metadata={
                    "tier": tier.value if isinstance(tier, ModelTier) else str(tier),
                    "worker": worker,
                    "model": model_name,
                    "normalized_model": model_name,
                    "prompt": unit.prompt,
                    "validation_step": validation_step,
                    "schema": dict(unit.schema) if unit.schema is not None else None,
                    "output_path": str(unit.output_path),
                    "read_only": unit.read_only,
                },
            )
        )
    except ModelBudgetError:
        return None
