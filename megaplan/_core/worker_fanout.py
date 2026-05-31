"""Reusable worker fan-out primitives.

Provides :class:`WorkerUnit` and :func:`scatter_worker_units` for dispatching
multiple :func:`~megaplan.workers.run_step_with_worker` calls through
process-isolated fan-out with token/cost aggregation, deterministic output
paths, caller-supplied parse/reduce hooks, and error propagation.

Mirrors the ``scatter_over_worker_step`` pattern in
:mod:`megaplan.orchestration.prep_research` but is generic — no prep-specific
assumptions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .hermes_fanout import GenericScatterResult, scatter_gather_processes
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

    worker, _agent, _mode, _refreshed = run_step_with_worker(
        unit.step,
        state,
        plan_dir,
        args,
        root=root,
        resolved=unit.resolved,
        prompt_override=unit.prompt,
        read_only=unit.read_only,
    )
    return (
        index,
        worker.payload,
        worker.cost_usd,
        worker.prompt_tokens,
        worker.completion_tokens,
        worker.total_tokens,
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
    state: PlanState,
    plan_dir: Path,
    root: Path,
    args: argparse.Namespace,
    parse_result: Callable[[int, Any, WorkerUnit], Any] | None = None,
    on_unit_error: (
        Callable[[int, Exception], tuple[Any, float, int, int, int]] | None
    ) = None,
    max_concurrent: int | None = None,
    timeout_seconds: float | None = None,
) -> GenericScatterResult:
    """Scatter multiple :class:`WorkerUnit` instances via process-isolated fan-out.

    Each unit is dispatched through :func:`run_step_with_worker` with its
    *resolved* mode, *prompt* override, *output_path*, and *read_only* flag.
    Token usage and cost are aggregated across all units.

    Parameters
    ----------
    units:
        Worker unit descriptions to dispatch.
    state:
        Plan state (shared across all units).
    plan_dir:
        Plan directory (determines where worker artefacts are written).
    root:
        Repository root passed through to the worker.
    args:
        ``argparse.Namespace`` for worker dispatch compatibility.
    parse_result:
        Optional post-processing hook ``(index, raw_payload, unit) -> parsed``.
        When supplied, each result in the returned
        :class:`~megaplan._core.hermes_fanout.GenericScatterResult` is the
        return value of this hook.
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
    if not units:
        return GenericScatterResult(
            ordered_results=[],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    packed_units: list[dict[str, Any]] = [
        {
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
        for u in units
    ]

    raw = scatter_gather_processes(
        units=packed_units,
        run_unit_fn=_scatter_worker_unit_from_packed,
        max_concurrent=max_concurrent,
        timeout_seconds=timeout_seconds,
        on_unit_error=on_unit_error,
    )

    if parse_result is not None:
        parsed: list[Any] = []
        for i, payload in enumerate(raw.ordered_results):
            parsed.append(parse_result(i, payload, units[i]))
        return GenericScatterResult(
            ordered_results=parsed,
            total_cost=raw.total_cost,
            total_prompt_tokens=raw.total_prompt_tokens,
            total_completion_tokens=raw.total_completion_tokens,
            total_tokens=raw.total_tokens,
            side_results=raw.side_results,
        )

    return raw
