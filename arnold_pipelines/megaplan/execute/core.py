from __future__ import annotations

"""Canonical execute public facade."""

from arnold_pipelines.megaplan._core import load_config
from arnold_pipelines.megaplan.execute.aggregation import (
    _build_aggregate_execution_payload,
    _compute_execute_scope_drift,
)
from arnold_pipelines.megaplan.execute.batch import (
    BatchResult,
    _has_code_task_advisory_evidence,
    _resolve_tier_spec,
    _run_and_merge_batch,
    build_monitor_hint,
    handle_execute_auto_loop,
    handle_execute_one_batch,
)
from arnold_pipelines.megaplan.execute.merge import _merge_batch_results
from arnold_pipelines.megaplan.execute.wbc import (
    EXECUTE_DISPATCH_WBC_KEY,
    EXECUTE_TRANSITION_WBC_KEY,
)
from arnold_pipelines.megaplan.execute.quality import (
    _capture_git_status_snapshot,
    _capture_git_status_snapshot_recursive,
)

__all__ = [
    "_build_aggregate_execution_payload",
    "_merge_batch_results",
    "BatchResult",
    "handle_execute_auto_loop",
    "handle_execute_one_batch",
    "_has_code_task_advisory_evidence",
    "_capture_git_status_snapshot",
    "_capture_git_status_snapshot_recursive",
    "_compute_execute_scope_drift",
    "_resolve_tier_spec",
    "_run_and_merge_batch",
    "EXECUTE_DISPATCH_WBC_KEY",
    "EXECUTE_TRANSITION_WBC_KEY",
    "load_config",
    "build_monitor_hint",
]
