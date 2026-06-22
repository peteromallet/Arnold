"""Observability helpers for the manifest runner.

All signals are product-neutral and built on the stdlib logging package.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from arnold.kernel import EventEnvelope, GovernorBudget, GovernorState, fold_governor_state
from arnold.execution.routing import project_routing_state
from arnold.execution.state import RouteCoordinate, RoutingState


@dataclass(frozen=True)
class ProgressReport:
    """Point-in-time progress of a manifest run."""

    total_nodes: int
    completed: int
    failed: int
    pending: int
    suspended: int
    consumed_cost: float
    remaining_cost: float | None
    health_status: str


@dataclass(frozen=True)
class BudgetTelemetry:
    """Budget-derived health telemetry."""

    consumed_cost: float
    net_cost: float
    cost_limit: float | None
    healthy: bool


@dataclass(frozen=True)
class HealthSnapshot:
    """Combined health snapshot for operators."""

    status: str
    budget: BudgetTelemetry
    elapsed_seconds: float | None


class ExecutionSpan:
    """Context manager that logs span start/end/duration."""

    def __init__(self, logger: logging.Logger, name: str, run_id: str) -> None:
        self._logger = logger
        self._name = name
        self._run_id = run_id
        self._start: float | None = None

    def __enter__(self) -> "ExecutionSpan":
        self._start = time.monotonic()
        self._logger.info(
            "span_started",
            extra={
                "arnold_event_kind": "span_started",
                "run_id": self._run_id,
                "span_name": self._name,
            },
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        elapsed = (time.monotonic() - self._start) if self._start is not None else None
        self._logger.info(
            "span_ended",
            extra={
                "arnold_event_kind": "span_ended",
                "run_id": self._run_id,
                "span_name": self._name,
                "elapsed_seconds": elapsed,
            },
        )


class ExecutionLogger:
    """Structured logger for execution events.

    Events emitted mirror the lifecycle events already journaled by the runner:
    run_started, node_started, node_completed, node_failed, run_suspended,
    run_resumed, run_completed, run_failed, budget_reserved, budget_settled,
    budget_released, and checkpoint_saved.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("arnold.execution")

    def _log(
        self,
        level: int,
        message: str,
        *,
        event_kind: str,
        run_id: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        extra = {
            "arnold_event_kind": event_kind,
            "run_id": run_id,
        }
        if payload:
            extra["arnold_payload"] = dict(payload)
        self._logger.log(level, message, extra=extra)

    def log_event(
        self,
        event_kind: str,
        run_id: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        self._log(logging.INFO, event_kind, event_kind=event_kind, run_id=run_id, payload=payload)

    def log_warning(
        self,
        event_kind: str,
        run_id: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        self._log(logging.WARNING, event_kind, event_kind=event_kind, run_id=run_id, payload=payload)

    def span(self, name: str, run_id: str) -> ExecutionSpan:
        return ExecutionSpan(self._logger, name, run_id)


def build_budget_telemetry(
    governor_state: GovernorState,
    budget: GovernorBudget,
) -> BudgetTelemetry:
    """Derive budget health telemetry from folded governor state."""

    net = governor_state.net_cost
    cost_limit = budget.cost_limit
    healthy = cost_limit is None or net < cost_limit
    return BudgetTelemetry(
        consumed_cost=governor_state.consumed_cost,
        net_cost=net,
        cost_limit=cost_limit,
        healthy=healthy,
    )


def build_health_snapshot(
    status: str,
    routing_state: RoutingState,
    governor_state: GovernorState,
    budget: GovernorBudget,
    elapsed_seconds: float | None = None,
) -> HealthSnapshot:
    """Combine routing progress and budget health into a single snapshot."""

    return HealthSnapshot(
        status=status,
        budget=build_budget_telemetry(governor_state, budget),
        elapsed_seconds=elapsed_seconds,
    )


def snapshot_to_dict(snapshot: HealthSnapshot) -> dict[str, Any]:
    return {
        "status": snapshot.status,
        "budget": asdict(snapshot.budget),
        "elapsed_seconds": snapshot.elapsed_seconds,
    }


def build_progress_report(
    journal: tuple[EventEnvelope, ...],
    checkpoint: Any | None = None,
) -> ProgressReport:
    """Derive a progress report from a journal and optional checkpoint.

    The checkpoint is accepted for API compatibility but the report is computed
    from the journal (and the manifest carried on the first event).
    """

    del checkpoint  # reserved for future overlay merging
    if not journal:
        return ProgressReport(
            total_nodes=0,
            completed=0,
            failed=0,
            pending=0,
            suspended=0,
            consumed_cost=0.0,
            remaining_cost=None,
            health_status="unknown",
        )

    manifest_ref = journal[0].manifest
    # Reconstruct the manifest stub needed for routing projection.  The
    # projection only needs node ids and edges; kinds are not used by the
    # projection, so we fill them with a neutral placeholder.
    from arnold.manifest import WorkflowManifest, WorkflowNode, WorkflowEdge

    node_refs = sorted({e.payload.get("node_ref", "") for e in journal if e.payload.get("node_ref")})
    nodes = tuple(WorkflowNode(id=nref, kind="unknown") for nref in node_refs)
    edges = ()

    routing = project_routing_state(
        WorkflowManifest(
            id=manifest_ref.alias,
            nodes=nodes,
            edges=edges,
            manifest_hash=manifest_ref.manifest_hash,
        ),
        journal,
    )
    governor = fold_governor_state(journal)
    budget = GovernorBudget()  # neutral default; runtime can pass a real budget if known
    health = build_health_snapshot("running", routing, governor, budget)

    total = len(routing.manifest.nodes)
    completed = len(routing.completed)
    failed = len(routing.failed)
    suspended = len(routing.suspended)
    pending = total - completed - failed - suspended
    remaining = None
    if health.budget.cost_limit is not None:
        remaining = max(0.0, health.budget.cost_limit - health.budget.net_cost)

    return ProgressReport(
        total_nodes=total,
        completed=completed,
        failed=failed,
        pending=pending,
        suspended=suspended,
        consumed_cost=health.budget.consumed_cost,
        remaining_cost=remaining,
        health_status="healthy" if health.budget.healthy else "over_budget",
    )


def routing_snapshot(routing: RoutingState) -> dict[str, Any]:
    """Convert a routing state into a JSON-friendly snapshot."""

    def coord_dict(coord: RouteCoordinate) -> dict[str, Any]:
        return {
            "node_ref": coord.node_ref,
            "scope_stack": list(coord.scope_stack),
            "attempt": coord.attempt,
            "iteration": coord.iteration,
            "child_key": coord.child_key,
        }

    return {
        "completed": [coord_dict(c) for c in sorted(routing.completed)],
        "failed": [coord_dict(c) for c in sorted(routing.failed)],
        "suspended": [coord_dict(c) for c in sorted(routing.suspended)],
        "ready": [coord_dict(c) for c in routing.ready],
        "blocked": [coord_dict(c) for c in routing.blocked],
    }


__all__ = [
    "BudgetTelemetry",
    "ExecutionLogger",
    "ExecutionSpan",
    "HealthSnapshot",
    "ProgressReport",
    "build_budget_telemetry",
    "build_health_snapshot",
    "build_progress_report",
    "routing_snapshot",
    "snapshot_to_dict",
]
