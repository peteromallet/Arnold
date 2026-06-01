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
from typing import Any, Callable

from .hermes_fanout import GenericScatterResult, scatter_gather_processes
from megaplan.agent_runtime import AgentRequest, AgentSpec, ResultProvenance
from megaplan.types import AgentMode, PlanState


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

    extra: dict[str, Any] = field(default_factory=dict)
    """Opaque caller metadata forwarded to parse/reduce hooks."""


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
    step: str | None = None
    output_path: str | None = None
    read_only: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
    agent: str | None = None
    mode: str | None = None
    model: str | None = None
    resolved_model: str | None = None
    effort: str | None = None

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
            step=unit.step,
            output_path=str(unit.output_path),
            read_only=unit.read_only,
            extra=dict(unit.extra),
            agent=resolved.agent,
            mode=resolved.mode,
            model=resolved.model,
            resolved_model=resolved.resolved_model,
            effort=resolved.effort,
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
    spec = AgentSpec(
        agent=resolved.agent,
        model=resolved.model,
        effort=resolved.effort,
    )
    metadata = {
        "worker_unit": {
            "index": index,
            "step": unit.step,
            "output_path": str(unit.output_path),
            "read_only": unit.read_only,
            "extra": dict(unit.extra),
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
    provenance = ResultProvenance(
        agent=resolved.agent,
        mode=resolved.mode,
        model=resolved.model,
        resolved_model=resolved.resolved_model,
        effort=resolved.effort,
        metadata={
            "worker_step": unit.step,
            "output_path": str(unit.output_path),
            "read_only": unit.read_only,
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
        prompt=unit.prompt,
        metadata=metadata,
        timeout_seconds=timeout_seconds,
        provenance=provenance,
        attestation={
            "adapter": "megaplan._core.worker_fanout._worker_unit_to_agent_request",
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
    from megaplan.workers import run_step_with_worker

    worker_options = unit.extra.get("worker_options")
    if worker_options is not None and not isinstance(worker_options, dict):
        raise TypeError("WorkerUnit.extra['worker_options'] must be a dict when provided")

    worker, _agent, _mode, _refreshed = run_step_with_worker(
        unit.step,
        state,
        plan_dir,
        args,
        root=root,
        resolved=unit.resolved,
        prompt_override=unit.prompt,
        read_only=unit.read_only,
        output_path=unit.output_path,
        worker_options=dict(worker_options) if worker_options is not None else None,
        ledger_step_label=(
            unit.extra.get("ledger_step_label")
            or unit.extra.get("check_id")
            or unit.extra.get("area_id")
            or unit.step
        ),
        ledger_selected_spec=unit.extra.get("ledger_selected_spec"),
        ledger_tier=unit.extra.get("ledger_tier"),
        ledger_complexity=unit.extra.get("ledger_complexity"),
        ledger_tier_routing_active=bool(unit.extra.get("ledger_tier_routing_active", False)),
    )
    unit_result = WorkerUnitResult.from_worker_result(worker, unit)
    return (
        index,
        unit_result,
        unit_result.cost_usd,
        unit_result.prompt_tokens,
        unit_result.completion_tokens,
        unit_result.total_tokens,
    )


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
        extra=packed.get("extra", {}),
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
                "extra": u.extra,
                "state": state,
                "plan_dir": str(plan_dir),
                "root": str(root),
                "args": args,
            }
        )
    raw = scatter_gather_processes(
        units=packed_units,
        run_unit_fn=_scatter_worker_unit_from_packed,
        max_concurrent=max_concurrent,
        timeout_seconds=timeout_seconds,
        on_unit_error=on_unit_error,
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
