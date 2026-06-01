"""Topological scheduler: thin facade over ``megaplan._core.io`` topo-sort helpers.

Exposes ``schedule_batches`` as the primary entry point for the F5
task-DAG scheduler.  This module MUST NOT import anything from the
execute or handlers subpackages.
"""

from __future__ import annotations

from typing import Any

from megaplan._core.io import compute_task_batches, split_oversized_batches


def schedule_batches(
    work_list: list[dict[str, Any]],
    *,
    max_batch_size: int,
    completed_ids: set[str] | None = None,
    default_max_size: int = 5,
) -> list[list[str]]:
    """Topologically sort *work_list* into sized batches.

    Each element of *work_list* must be a dict with at least ``"id"``
    (``str``) and ``"depends_on"`` (``list[str]``).  No ``complexity``,
    ``status``, or planning fields are required — only the DAG shape
    matters.

    Tasks whose IDs appear in *completed_ids* are excluded from the
    output (they are treated as dependency-satisfied).  This mirrors the
    auto-loop call shape where ``pending_tasks`` are pre-filtered.

    Args:
        work_list: Task dicts with ``id`` and ``depends_on`` keys.
        max_batch_size: Maximum tasks per batch (used by ``split_oversized_batches``).
        completed_ids: Already-completed task IDs to exclude from scheduling
            and treat as satisfied dependencies.
        default_max_size: Fallback when *max_batch_size* ≤ 0.

    Returns:
        A list of batches, each a list of task-ID strings (completed tasks excluded).

    Raises:
        ValueError: Unknown dependency ID or cycle detected (same semantics
            as ``compute_task_batches`` in ``megaplan/_core/io.py``).
    """
    # Thread completed_ids through for dependency satisfaction and
    # validation (unknown-dep / cycle checks run against the full set).
    # Filter completed tasks from the output so they are not re-scheduled.
    raw_batches = compute_task_batches(work_list, completed_ids=completed_ids)
    if completed_ids:
        raw_batches = [
            [tid for tid in batch if tid not in completed_ids]
            for batch in raw_batches
        ]
        # Drop any batches that became empty after filtering.
        raw_batches = [batch for batch in raw_batches if batch]
    return split_oversized_batches(
        raw_batches,
        max_batch_size,
        default_max_size=default_max_size,
    )
