"""Planning reducer binding for the unified execute path (F4/F5).

This module owns the four-outcome classification vocabulary
(BatchOutcome), the named alias (BatchReduceResult), the classification
function (reduce_batch), the state-transition helper
(apply_outcome_to_state), and the structured evidence surface
(ReducerEvidence / ReducerOutcome / compute_reducer_evidence /
reduce_batch_full).

Classification logic moved here from:
  - batch.py:600–670  (build_blocking_reasons / batch_blocked_ids logic)
  - merge.py:148–157  (deviation→blocked downgrade)
  - merge.py:102–121  (patch-corruption/syntax mutation)

Fidelity is preserved, not weakened.  When _classification_mode=='legacy'
the task_deviation_dict passed to reduce_batch is empty / None, so no
mutations are applied via the SD2 path.

Evidence surface (T5):
  ReducerEvidence captures the boundary between child work and parent
  state advancement: child outputs, aggregate canonical outputs,
  parent-state promotion points, side-effect refs, blocked/retry
  records, repair-domain separation, and non-atomic resume anchors.
  compute_reducer_evidence extracts this evidence from the same
  inputs that reduce_batch processes, staying read-only w.r.t. state.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from arnold_pipelines.megaplan._core.scheduler.types import Reduce
from arnold_pipelines.megaplan.execute import (
    _blocked_task_reason,
    _prerequisite_blocked_task_ids,
    build_blocking_reasons,
)
from arnold_pipelines.megaplan.execute.merge import _is_blocking_deviation
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    corroborated_completed_task_ids,
)
from arnold_pipelines.megaplan.planning.state import STATE_EXECUTED

if TYPE_CHECKING:
    from arnold_pipelines.megaplan.execute.batch import BatchResult


class BatchOutcome(str, enum.Enum):
    SUCCESS = "success"
    BLOCKED_BY_QUALITY = "blocked_by_quality"
    BLOCKED_BY_PREREQ = "blocked_by_prereq"
    TIMEOUT = "timeout"


BatchReduceResult = Reduce[BatchOutcome]


# ── Structured reducer evidence surface (T5) ──────────────────────────────


@dataclass(frozen=True, slots=True)
class ReducerEvidence:
    """Structured evidence produced at the reducer boundary.

    Captures the boundary between child work and parent state advancement.
    Frozen so downstream consumers (S4 repair/status/auditor) receive
    immutable facts.
    """

    # Per-child outputs keyed by task_id — preserves what each child produced.
    child_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Aggregate canonical outputs merged across all children (merged task
    # counts, sense-check acknowledgments, execution audit, etc.).
    aggregate_canonical_outputs: dict[str, Any] = field(default_factory=dict)

    # Ordered promotion points that should advance parent state (completed
    # task IDs, blocking reasons, phase-outcome marker, state transition).
    parent_promotion_points: list[dict[str, Any]] = field(default_factory=list)

    # Stable references to side effects produced by child work (file paths,
    # artifact refs, attribution records, routing degradations).
    side_effect_refs: list[str] = field(default_factory=list)

    # Blocked/retry records: which tasks are blocked, why, and whether they
    # are eligible for retry on the next scheduling pass.
    blocked_retry_records: list[dict[str, Any]] = field(default_factory=list)

    # Repair-domain separation: markers distinguishing repair-execution
    # evidence from ordinary-execution evidence so S4 consumers can route
    # verdicts correctly.
    repair_domain_separation: dict[str, Any] = field(default_factory=dict)

    # Non-atomic resume anchors: stable points that allow a subsequent run
    # to resume from partial completion.  Each anchor records which tasks
    # completed, which remain pending/blocked, and what state cursor the
    # next invocation should use.
    resume_anchors: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReducerOutcome:
    """Composite reducer result: classification outcome + structured evidence.

    The ``value`` property returns the ``BatchOutcome`` for backward
    compatibility with callers that expect ``BatchReduceResult`` semantics.
    """

    outcome: BatchOutcome
    evidence: ReducerEvidence = field(default_factory=ReducerEvidence)

    @property
    def value(self) -> BatchOutcome:
        """Backward-compatible accessor for BatchReduceResult semantics."""
        return self.outcome


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
    completed_task_ids: set[str] | None = None,
    plan_dir: Path | str | None = None,
    evidence_nucleus: Any = None,
    current_head: str | None = None,
    current_code_hash: str | None = None,
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
        completed_task_ids: Precomputed authority-corroborated completed IDs.
            When omitted, the reducer computes them with the shared authority
            adapter from ``finalize_data["tasks"]`` plus optional evidence inputs.
            Raw ``done``/``skipped`` labels are never success authority here.
        plan_dir/evidence_nucleus/current_head/current_code_hash: Optional
            authority adapter inputs used only when ``completed_task_ids`` is
            not supplied.

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
    if completed_task_ids is None:
        completed_task_ids = corroborated_completed_task_ids(
            tracked_tasks,
            plan_dir=plan_dir,
            evidence_nucleus=evidence_nucleus,
            current_head=current_head,
            current_code_hash=current_code_hash,
        )
    batch_task_id_set = set(batch_task_ids)
    batch_blocked_ids = sorted(
        _prerequisite_blocked_task_ids(
            tracked_tasks,
            active_task_ids=batch_task_id_set,
        )
    )
    blocked_task_reason = _blocked_task_reason(batch_blocked_ids)
    if blocked_task_reason:
        blocking_reasons.append(blocked_task_reason)

    tracked_task_ids = {
        task_id for task_id in (t.get("id") for t in tracked_tasks) if isinstance(task_id, str)
    }
    uncorroborated_tracked_ids = sorted(tracked_task_ids - completed_task_ids)
    raw_terminal_uncorroborated_ids = {
        task_id
        for task_id in uncorroborated_tracked_ids
        for task in tracked_tasks
        if task.get("id") == task_id and task.get("status") in {"done", "skipped"}
    }
    batch_uncorroborated_ids = [
        task_id
        for task_id in uncorroborated_tracked_ids
        if task_id in batch_task_id_set and task_id in raw_terminal_uncorroborated_ids
    ]
    if batch_uncorroborated_ids:
        blocking_reasons.append(
            "tracked task(s) lack authority-corroborated completion: "
            + ", ".join(batch_uncorroborated_ids)
        )

    all_tracked = bool(tracked_tasks) and not uncorroborated_tracked_ids
    any_done = any(t.get("id") in completed_task_ids for t in tracked_tasks)
    if all_tracked and tracked_tasks and not any_done:
        blocking_reasons.append(
            "All tasks were skipped with none completed — execution produced no work."
        )
        all_tracked = False  # noqa: F841 — keeps symmetry with batch.py

    blocked = bool(blocking_reasons)

    if blocked and (batch_blocked_ids or batch_uncorroborated_ids):
        return BatchReduceResult(value=BatchOutcome.BLOCKED_BY_PREREQ)
    if blocked:
        return BatchReduceResult(value=BatchOutcome.BLOCKED_BY_QUALITY)
    return BatchReduceResult(value=BatchOutcome.SUCCESS)


def apply_outcome_to_state(
    state: dict[str, Any],
    outcome: BatchOutcome,
    *,
    evidence: ReducerEvidence | None = None,
) -> None:
    """Write the phase_outcome marker and current_state transition into state.

    Mirrors the legacy one-batch handler path:
      - Sets state["_phase_outcome"] to the outcome string so
        handlers/execute.py:258 reads the correct ExitKind.
      - Sets state["current_state"] = STATE_EXECUTED for SUCCESS
        (mirrors batch.py:674).  Other outcomes leave current_state unchanged.

    When *evidence* is supplied (T5), also writes structured reducer
    evidence into state so downstream S4 consumers (repair, status,
    auditor) can consume the same findings.
    """
    state["_phase_outcome"] = outcome.value
    if outcome == BatchOutcome.SUCCESS:
        state["current_state"] = STATE_EXECUTED

    if evidence is not None:
        _write_reducer_evidence_to_state(state, evidence)


def _write_reducer_evidence_to_state(
    state: dict[str, Any], evidence: ReducerEvidence
) -> None:
    """Project structured reducer evidence into state keys (T5).

    Writes under stable, namespaced keys so S4 consumers can locate
    evidence without coupling to the ReducerEvidence dataclass shape.
    """
    state["_reducer_child_outputs"] = evidence.child_outputs
    state["_reducer_aggregate_canonical_outputs"] = evidence.aggregate_canonical_outputs
    state["_reducer_parent_promotion_points"] = evidence.parent_promotion_points
    state["_reducer_side_effect_refs"] = evidence.side_effect_refs
    state["_reducer_blocked_retry_records"] = evidence.blocked_retry_records
    state["_reducer_repair_domain_separation"] = evidence.repair_domain_separation
    state["_reducer_resume_anchors"] = evidence.resume_anchors


# ── Evidence extraction (T5) ──────────────────────────────────────────────


def compute_reducer_evidence(
    batch_process_result: "BatchResult",
    *,
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
    task_deviation_dict: dict[str, list[str]] | None = None,
    completed_task_ids: set[str] | None = None,
    blocking_reasons: list[str] | None = None,
    batch_blocked_ids: list[str] | None = None,
    uncorroborated_tracked_ids: list[str] | None = None,
    plan_dir: Path | str | None = None,
    evidence_nucleus: Any = None,
    current_head: str | None = None,
    current_code_hash: str | None = None,
) -> ReducerEvidence:
    """Extract structured evidence from batch-reducer inputs (T5).

    Reads the same inputs that ``reduce_batch`` processes but does not
    mutate state.  Returns an immutable ``ReducerEvidence`` that
    downstream S4 consumers (repair, status, auditor) can rely on.

    When intermediate values (*blocking_reasons*, *batch_blocked_ids*,
    *uncorroborated_tracked_ids*) are not supplied, this function
    recomputes them — callers that already computed them inside
    ``reduce_batch`` should pass them in to avoid duplicate work.
    """
    result = batch_process_result
    all_tasks: list[dict[str, Any]] = finalize_data.get("tasks", [])
    tracked_tasks = [t for t in all_tasks if isinstance(t.get("id"), str)]

    # ── child_outputs: per-child evidence ──────────────────────────────
    child_outputs: dict[str, dict[str, Any]] = {}
    for task in tracked_tasks:
        task_id = task.get("id")
        if isinstance(task_id, str):
            child_outputs[task_id] = {
                "status": task.get("status"),
                "files_changed": task.get("files_changed", []) or [],
                "commands_run": task.get("commands_run", []) or [],
                "executor_notes": task.get("executor_notes", ""),
            }

    # ── aggregate_canonical_outputs ────────────────────────────────────
    aggregate_canonical_outputs: dict[str, Any] = {
        "merged_task_count": result.merged_task_count,
        "total_task_count": result.total_task_count,
        "acknowledged_sense_check_count": result.acknowledged_sense_check_count,
        "total_sense_check_count": result.total_sense_check_count,
        "missing_task_evidence": list(result.missing_task_evidence),
        "execution_audit": dict(result.execution_audit) if result.execution_audit else {},
        "phase_outcome": result.payload.get("_phase_outcome"),
    }

    # ── completed / blocked / uncorroborated resolution ────────────────
    if completed_task_ids is None:
        completed_task_ids = corroborated_completed_task_ids(
            tracked_tasks,
            plan_dir=plan_dir,
            evidence_nucleus=evidence_nucleus,
            current_head=current_head,
            current_code_hash=current_code_hash,
        )

    batch_task_id_set = set(batch_task_ids)
    if batch_blocked_ids is None:
        batch_blocked_ids = sorted(
            _prerequisite_blocked_task_ids(
                tracked_tasks,
                active_task_ids=batch_task_id_set,
            )
        )

    tracked_task_ids_set = {
        tid for tid in (t.get("id") for t in tracked_tasks) if isinstance(tid, str)
    }
    if uncorroborated_tracked_ids is None:
        uncorroborated_tracked_ids = sorted(
            tracked_task_ids_set - completed_task_ids
        )

    if blocking_reasons is None:
        blocking_reasons = build_blocking_reasons(
            tracked_tasks=result.merged_task_count,
            total_tasks=result.total_task_count,
            acknowledged_checks=result.acknowledged_sense_check_count,
            total_checks=result.total_sense_check_count,
            missing_task_evidence=result.missing_task_evidence,
        )
        btr = _blocked_task_reason(batch_blocked_ids)
        if btr:
            blocking_reasons.append(btr)
        raw_terminal_uncorroborated_ids = {
            tid
            for tid in uncorroborated_tracked_ids
            for t in tracked_tasks
            if t.get("id") == tid and t.get("status") in {"done", "skipped"}
        }
        batch_uncorroborated_ids = [
            tid
            for tid in uncorroborated_tracked_ids
            if tid in batch_task_id_set and tid in raw_terminal_uncorroborated_ids
        ]
        if batch_uncorroborated_ids:
            blocking_reasons.append(
                "tracked task(s) lack authority-corroborated completion: "
                + ", ".join(batch_uncorroborated_ids)
            )

    blocked = bool(blocking_reasons)

    # ── parent_promotion_points ────────────────────────────────────────
    parent_promotion_points: list[dict[str, Any]] = [
        {
            "kind": "completed_task_ids",
            "task_ids": sorted(completed_task_ids),
        },
        {
            "kind": "blocking_reasons",
            "reasons": list(blocking_reasons),
            "blocked": blocked,
        },
        {
            "kind": "phase_outcome",
            "outcome": (
                result.payload.get("_phase_outcome")
                or ("blocked" if blocked else "success")
            ),
        },
        {
            "kind": "state_transition",
            "target_current_state": (
                STATE_EXECUTED if not blocked and result.payload.get("_phase_outcome") != "timeout"
                else None
            ),
        },
    ]

    # ── side_effect_refs ───────────────────────────────────────────────
    side_effect_refs: list[str] = []
    for record in getattr(result, "attribution_records", []) or []:
        if isinstance(record, dict):
            sp = record.get("source_path")
            if isinstance(sp, str):
                side_effect_refs.append(sp)
    for degradation in getattr(result, "routing_degradations", []) or []:
        if isinstance(degradation, str):
            side_effect_refs.append(f"routing_degradation:{degradation}")

    # Also include files_changed from child tasks as side-effect refs.
    seen_files: set[str] = set()
    for task in tracked_tasks:
        for fc in task.get("files_changed", []) or []:
            if isinstance(fc, str) and fc not in seen_files:
                seen_files.add(fc)
                side_effect_refs.append(fc)

    # ── blocked_retry_records ─────────────────────────────────────────
    blocked_retry_records: list[dict[str, Any]] = []
    for task in tracked_tasks:
        tid = task.get("id")
        if not isinstance(tid, str):
            continue
        status = task.get("status")
        if status == "blocked" or tid in batch_blocked_ids:
            harness_block = (
                isinstance(task.get("executor_notes"), str)
                and "[harness]" in task["executor_notes"]
            )
            blocked_retry_records.append(
                {
                    "task_id": tid,
                    "status": status,
                    "blocked": True,
                    "harness_generated": harness_block,
                    "retry_eligible": not harness_block,
                    "reason": task.get("executor_notes", ""),
                }
            )
        elif tid in uncorroborated_tracked_ids:
            blocked_retry_records.append(
                {
                    "task_id": tid,
                    "status": status,
                    "blocked": True,
                    "harness_generated": False,
                    "retry_eligible": True,
                    "reason": "uncorroborated completion — requires authority re-validation",
                }
            )

    # ── repair_domain_separation ───────────────────────────────────────
    repair_domain_separation: dict[str, Any] = {
        "is_repair_execution": bool(
            task_deviation_dict and len(task_deviation_dict) > 0
        ),
        "deviation_task_ids": (
            sorted(task_deviation_dict.keys())
            if task_deviation_dict
            else []
        ),
        "deviation_count": len(task_deviation_dict) if task_deviation_dict else 0,
        "repair_domain": (
            "repair" if (task_deviation_dict and len(task_deviation_dict) > 0)
            else "ordinary"
        ),
    }

    # ── resume_anchors ─────────────────────────────────────────────────
    resume_anchors: list[dict[str, Any]] = []
    if blocked or batch_blocked_ids or uncorroborated_tracked_ids:
        resume_anchors.append(
            {
                "anchor_kind": "partial_completion",
                "completed_task_ids": sorted(completed_task_ids),
                "blocked_task_ids": sorted(set(batch_blocked_ids or [])),
                "uncorroborated_task_ids": list(uncorroborated_tracked_ids or []),
                "pending_task_ids": sorted(
                    batch_task_id_set - completed_task_ids - set(batch_blocked_ids or [])
                ),
                "state_cursor": {
                    "merged_task_count": result.merged_task_count,
                    "batch_number": getattr(result, "batch_number", None),
                },
            }
        )
    else:
        resume_anchors.append(
            {
                "anchor_kind": "complete",
                "completed_task_ids": sorted(completed_task_ids),
                "blocked_task_ids": [],
                "uncorroborated_task_ids": [],
                "pending_task_ids": [],
                "state_cursor": {
                    "merged_task_count": result.merged_task_count,
                    "batch_number": getattr(result, "batch_number", None),
                },
            }
        )

    return ReducerEvidence(
        child_outputs=child_outputs,
        aggregate_canonical_outputs=aggregate_canonical_outputs,
        parent_promotion_points=parent_promotion_points,
        side_effect_refs=side_effect_refs,
        blocked_retry_records=blocked_retry_records,
        repair_domain_separation=repair_domain_separation,
        resume_anchors=resume_anchors,
    )


def reduce_batch_full(
    batch_process_result: "BatchResult",
    *,
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
    task_deviation_dict: dict[str, list[str]] | None = None,
    completed_task_ids: set[str] | None = None,
    plan_dir: Path | str | None = None,
    evidence_nucleus: Any = None,
    current_head: str | None = None,
    current_code_hash: str | None = None,
) -> ReducerOutcome:
    """Classify a batch and produce structured evidence (T5).

    Combines ``reduce_batch`` classification with ``compute_reducer_evidence``
    in a single call.  Returns a ``ReducerOutcome`` that carries both the
    ``BatchOutcome`` and the immutable ``ReducerEvidence``.

    All keyword arguments match ``reduce_batch``.
    """
    # Compute the classification first (may mutate finalize_data tasks).
    reduce_result = reduce_batch(
        batch_process_result,
        finalize_data=finalize_data,
        batch_task_ids=batch_task_ids,
        task_deviation_dict=task_deviation_dict,
        completed_task_ids=completed_task_ids,
        plan_dir=plan_dir,
        evidence_nucleus=evidence_nucleus,
        current_head=current_head,
        current_code_hash=current_code_hash,
    )

    # Recompute intermediates for evidence (classify already resolved them
    # but doesn't return them).  We recompute for clarity; the cost is low.
    result = batch_process_result
    all_tasks: list[dict[str, Any]] = finalize_data.get("tasks", [])
    tracked_tasks = [t for t in all_tasks if isinstance(t.get("id"), str)]

    if completed_task_ids is None:
        completed_task_ids = corroborated_completed_task_ids(
            tracked_tasks,
            plan_dir=plan_dir,
            evidence_nucleus=evidence_nucleus,
            current_head=current_head,
            current_code_hash=current_code_hash,
        )

    batch_task_id_set = set(batch_task_ids)
    batch_blocked_ids = sorted(
        _prerequisite_blocked_task_ids(
            tracked_tasks,
            active_task_ids=batch_task_id_set,
        )
    )

    tracked_task_ids_set = {
        tid for tid in (t.get("id") for t in tracked_tasks) if isinstance(tid, str)
    }
    uncorroborated_tracked_ids = sorted(
        tracked_task_ids_set - completed_task_ids
    )

    blocking_reasons = build_blocking_reasons(
        tracked_tasks=result.merged_task_count,
        total_tasks=result.total_task_count,
        acknowledged_checks=result.acknowledged_sense_check_count,
        total_checks=result.total_sense_check_count,
        missing_task_evidence=result.missing_task_evidence,
    )
    btr = _blocked_task_reason(batch_blocked_ids)
    if btr:
        blocking_reasons.append(btr)
    raw_terminal_uncorroborated_ids = {
        tid
        for tid in uncorroborated_tracked_ids
        for t in tracked_tasks
        if t.get("id") == tid and t.get("status") in {"done", "skipped"}
    }
    batch_uncorroborated_ids = [
        tid
        for tid in uncorroborated_tracked_ids
        if tid in batch_task_id_set and tid in raw_terminal_uncorroborated_ids
    ]
    if batch_uncorroborated_ids:
        blocking_reasons.append(
            "tracked task(s) lack authority-corroborated completion: "
            + ", ".join(batch_uncorroborated_ids)
        )

    evidence = compute_reducer_evidence(
        batch_process_result,
        finalize_data=finalize_data,
        batch_task_ids=batch_task_ids,
        task_deviation_dict=task_deviation_dict,
        completed_task_ids=completed_task_ids,
        blocking_reasons=blocking_reasons,
        batch_blocked_ids=batch_blocked_ids,
        uncorroborated_tracked_ids=uncorroborated_tracked_ids,
        plan_dir=plan_dir,
        evidence_nucleus=evidence_nucleus,
        current_head=current_head,
        current_code_hash=current_code_hash,
    )

    return ReducerOutcome(outcome=reduce_result.value, evidence=evidence)
