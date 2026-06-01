"""Planning reducer binding for the unified execute path (F4/F5).

This module owns the four-outcome classification vocabulary
(BatchOutcome), the named alias (BatchReduceResult), the classification
function (reduce_batch), and the state-transition helper
(apply_outcome_to_state).

Classification logic moved here from:
  - batch.py:600–670  (build_blocking_reasons / batch_blocked_ids logic)
  - merge.py:148–157  (deviation→blocked downgrade)
  - merge.py:102–121  (patch-corruption/syntax mutation)

Fidelity is preserved, not weakened.  When _classification_mode=='legacy'
the task_deviation_dict passed to reduce_batch is empty / None, so no
mutations are applied via the SD2 path.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

from megaplan._core.scheduler.types import Reduce
from megaplan.execute import _blocked_task_reason, build_blocking_reasons
from megaplan.execute.merge import _is_blocking_deviation
from megaplan.types import STATE_EXECUTED

if TYPE_CHECKING:
    from megaplan.execute.batch import BatchResult


class BatchOutcome(str, enum.Enum):
    SUCCESS = "success"
    BLOCKED_BY_QUALITY = "blocked_by_quality"
    BLOCKED_BY_PREREQ = "blocked_by_prereq"
    TIMEOUT = "timeout"


BatchReduceResult = Reduce[BatchOutcome]


def _append_executor_note_inline(task: dict[str, Any], note: str) -> None:
    """Inline replication of merge._append_executor_note semantics (SD3)."""
    existing = task.get("executor_notes")
    if isinstance(existing, str) and existing:
        task["executor_notes"] = f"{existing}\n{note}"
    else:
        task["executor_notes"] = note


def reduce_batch(
    batch_process_result: "BatchResult",
    *,
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
    task_deviation_dict: dict[str, list[str]] | None = None,
) -> BatchReduceResult:
    """Classify a BatchResult into one of four outcomes.

    Applies SD2 deviation-dict mutations to task dicts in finalize_data
    (patch-corruption and blocking-deviation downgrade) when
    task_deviation_dict is non-empty.  When _classification_mode=='legacy'
    pass an empty dict or None — no mutations are applied.

    Args:
        batch_process_result: BatchResult from the batch process step.
        finalize_data: Finalize payload carrying the task list.
        batch_task_ids: Task IDs assigned to the current batch.
        task_deviation_dict: SD2 5th-tuple from _merge_batch_results in
            reducer mode: task_id → ordered list of blocking deviation strings
            + patch-corruption errors.  Empty/None → legacy mode (no mutations).

    Returns:
        BatchReduceResult with the classified BatchOutcome.
    """
    result = batch_process_result

    # --- Apply SD2 deviation dict mutations (patch-corruption + downgrade) ---
    if task_deviation_dict:
        all_tasks_list: list[dict[str, Any]] = finalize_data.get("tasks", [])
        tasks_by_id: dict[str, dict[str, Any]] = {
            task.get("id"): task
            for task in all_tasks_list
            if isinstance(task.get("id"), str)
        }
        for task_id, deviation_strings in task_deviation_dict.items():
            task = tasks_by_id.get(task_id)
            if task is None:
                continue
            for deviation in deviation_strings:
                # Patch-corruption deviations (replicates merge.py:102-121)
                if deviation.startswith("patch_corruption:"):
                    task["status"] = "blocked"
                    _append_executor_note_inline(task, f"[harness] {deviation}")
                    continue
                # Blocking-deviation downgrade (replicates merge.py:148-157)
                if task.get("status") == "done":
                    matched = _is_blocking_deviation(deviation)
                    if matched is not None:
                        task["status"] = "blocked"
                        _append_executor_note_inline(
                            task,
                            f"[harness] status auto-downgraded: deviation contains {matched}",
                        )
                        break

    # --- Timeout check (highest priority, mirrors auto-loop line 1499) ------
    if result.payload.get("_phase_outcome") == "timeout":
        return BatchReduceResult(value=BatchOutcome.TIMEOUT)

    # --- Build blocking reasons (mirrors batch.py:613-644) ------------------
    blocking_reasons = build_blocking_reasons(
        tracked_tasks=result.merged_task_count,
        total_tasks=result.total_task_count,
        acknowledged_checks=result.acknowledged_sense_check_count,
        total_checks=result.total_sense_check_count,
        missing_task_evidence=result.missing_task_evidence,
    )

    all_tasks: list[dict[str, Any]] = finalize_data.get("tasks", [])
    tracked_tasks = [t for t in all_tasks if isinstance(t.get("id"), str)]
    batch_task_id_set = set(batch_task_ids)
    batch_blocked_ids = [
        t.get("id")
        for t in tracked_tasks
        if t.get("id") in batch_task_id_set and t.get("status") == "blocked"
    ]
    blocked_task_reason = _blocked_task_reason(batch_blocked_ids)
    if blocked_task_reason:
        blocking_reasons.append(blocked_task_reason)

    all_tracked = all(t.get("status") in {"done", "skipped"} for t in tracked_tasks)
    any_done = any(t.get("status") == "done" for t in tracked_tasks)
    if all_tracked and tracked_tasks and not any_done:
        blocking_reasons.append(
            "All tasks were skipped with none completed — execution produced no work."
        )
        all_tracked = False  # noqa: F841 — keeps symmetry with batch.py

    blocked = bool(blocking_reasons)

    if blocked and batch_blocked_ids:
        return BatchReduceResult(value=BatchOutcome.BLOCKED_BY_PREREQ)
    if blocked:
        return BatchReduceResult(value=BatchOutcome.BLOCKED_BY_QUALITY)
    return BatchReduceResult(value=BatchOutcome.SUCCESS)


def apply_outcome_to_state(state: dict[str, Any], outcome: BatchOutcome) -> None:
    """Write the phase_outcome marker and current_state transition into state.

    Mirrors the legacy one-batch handler path:
      - Sets state["_phase_outcome"] to the outcome string so
        handlers/execute.py:258 reads the correct ExitKind.
      - Sets state["current_state"] = STATE_EXECUTED for SUCCESS
        (mirrors batch.py:674).  Other outcomes leave current_state unchanged.
    """
    state["_phase_outcome"] = outcome.value
    if outcome == BatchOutcome.SUCCESS:
        state["current_state"] = STATE_EXECUTED
