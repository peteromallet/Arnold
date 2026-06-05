"""Task-DAG scheduler: scatter → batch → process → reduce loop.

The scheduler owns batching, ordering, invoking ``process_driver``, and
threading ``reduce`` — and NOTHING about classification or tier routing.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from arnold.pipelines.megaplan._core.scheduler.topo import schedule_batches
from arnold.pipelines.megaplan._core.scheduler.types import Reduce

T = TypeVar("T")


# ---------------------------------------------------------------------------
# M3 process-driver Protocol (inline until M3's public protocol lands)
# ---------------------------------------------------------------------------
# TODO: import from megaplan._pipeline once M3 exports a stable ProcessDriver
#       Protocol / ABC.  The inline definition below is the minimal contract
#       the scheduler needs.


class ProcessDriver(Protocol):
    """Minimal process-driver contract for the scheduler.

    M3 (or any process driver) must satisfy this protocol: a single
    ``process`` method that accepts a batch (list of task-ID strings)
    and returns an arbitrary result object.
    """

    def process(self, batch: list[str]) -> Any:
        """Execute *batch* (task IDs) and return a driver-specific result."""
        ...


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


def run_scheduler(
    *,
    produce: Any,
    process_driver: ProcessDriver,
    reduce: Any,
    max_batch_size: int,
    completed_ids: set[str] | None = None,
) -> list[Reduce[Any]]:
    """Run the full scatter → batch → process → reduce loop.

    Args:
        produce: Callable ``() -> list[dict]`` that returns the full work-list.
            Each dict must have at least ``"id"`` and ``"depends_on"`` keys.
        process_driver: A :class:`ProcessDriver` whose ``process(batch)``
            method executes one batch and returns a driver-specific result.
        reduce: Callable ``(batch_result, *, batch, batch_index) -> Reduce[T]``
            that reduces a per-batch process result into a typed ``Reduce``.
        max_batch_size: Maximum tasks per batch (passed to ``schedule_batches``).
        completed_ids: Already-completed task IDs to exclude from scheduling.

    Returns:
        A list of ``Reduce[T]`` items — one per batch, in batch order.
    """
    work_list = produce()
    batches = schedule_batches(
        work_list, max_batch_size=max_batch_size, completed_ids=completed_ids
    )

    results: list[Reduce[Any]] = []

    # Scatter (produce) → batch (schedule_batches) → for each batch:
    #   process (process_driver.process) → reduce (reduce callable)
    # Depth = 3: work_list ← produce(); batches ← schedule_batches;
    #            foreach batch → result ← reduce(process(batch))
    for batch_index, batch in enumerate(batches):
        batch_result = process_driver.process(batch)
        reduced = reduce(batch_result, batch=batch, batch_index=batch_index)
        results.append(reduced)

    return results
