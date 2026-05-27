"""Execute subpackage — execution, merge, timeout, and quality helpers.

This ``__init__`` re-exports every name historically imported from the
pre-refactor top-level modules (``megaplan.execution``,
``megaplan.execution_quality``, ``megaplan.execution_timeout``,
``megaplan.merge``) so that any lingering ``from megaplan.execute import X``
style callers keep working. The canonical import paths are now
``megaplan.execute.core``, ``megaplan.execute.quality``,
``megaplan.execute.timeout``, and ``megaplan.execute.merge``.
"""

from megaplan.execute.batch import (
    BatchResult,
    _active_sense_check_ids,
    _append_trace_output,
    _attach_next_step_runtime,
    _blocked_task_reason,
    _count_execute_tracking,
    _format_execute_tracking_note,
    _has_code_task_advisory_evidence,
    _positive_int_or_default,
    _resolve_max_tasks_per_batch,
    _resolve_tier_spec,
    _reset_blocked_tasks_to_pending,
    _run_and_merge_batch,
    build_blocking_reasons,
    build_monitor_hint,
    handle_execute_auto_loop,
    handle_execute_one_batch,
    worker_module,
)
from megaplan.execute.aggregation import (
    _build_aggregate_execution_payload,
    _compute_execute_scope_drift,
    _stable_unique_strings,
)
from megaplan.execute.quality import (
    _capture_git_status_snapshot,
    _check_done_task_evidence,
    _check_done_task_evidence_by_kind,
    _collect_execute_claimed_paths,
    _collect_quality_deviations,
    _normalize_execute_claimed_path,
    _observe_git_changes,
    _observed_batch_paths,
    _parse_git_status_paths,
    _repo_path_hash,
    run_quality_checks,
)
from megaplan.execute.timeout import (
    _merge_timeout_checkpoint,
    _recover_execute_timeout,
    _reset_timeout_invalid_tasks,
    _resolve_execute_approval_mode,
    _timeout_checkpoint_path,
)
from megaplan.execute.merge import (
    _FIELD_ALIASES,
    _VALUE_ALIASES,
    _append_execute_reconciliation_advisories,
    _merge_batch_results,
    _merge_validated_entries,
    _normalize_field_aliases,
    _snapshot_task_statuses,
    _validate_and_merge_batch,
    _validate_merge_inputs,
    reconcile_latest_execution_batch,
)

__all__ = [
    # core
    "BatchResult",
    "build_blocking_reasons",
    "build_monitor_hint",
    "handle_execute_auto_loop",
    "handle_execute_one_batch",
    "worker_module",
    # quality
    "run_quality_checks",
    # merge
    "_validate_and_merge_batch",
]
