"""Supervisor tier – worker-fleet supervision, leases, capacity, and cancellation.

This package provides backend-neutral project lease ownership, capacity gates,
progress classification, cancellation primitives, restart/quarantine decisions,
and a supervision loop that orchestrates them over native persistence.

Public API surface
------------------
Each sub-module defines its own ``__all__``.  The stable public import surface
re-exported here is organised by concern:

**Leases**
  :class:`ProjectLease`, :class:`ProjectLeaseIdentity`, :class:`ProjectLeaseState`,
  :func:`is_terminal_project_lease_state`, :func:`can_transition_project_lease`,
  :func:`ensure_project_lease_transition`, :class:`InvalidProjectLeaseTransition`

**Stores**
  :class:`ProjectLeaseStore` (protocol), :class:`FileProjectLeaseStore`,
  :class:`PostgresProjectLeaseStore`,
  :class:`ProjectLeaseAlreadyExists`, :class:`ProjectLeaseNotFound`,
  :class:`ProjectLeaseLockConflict`, :class:`ProjectLeaseConflict`,
  :class:`ProjectLeaseTokenMismatch`

**Capacity**
  :class:`CapacityGate`, :class:`CapacityPoolConfig`, :class:`CapacityPool`,
  :class:`CapacityGrant`, :class:`CapacityDecision`, :class:`CapacityStatus`

**Capacity context (call-site helpers)**
  :class:`CapacityContext`, :class:`CapacityGateRejected`,
  :func:`gate_capacity`, :func:`capacity_delay_metadata`,
  :func:`current_capacity_context`, :func:`set_capacity_context`

**Progress**
  :class:`ProgressSnapshot`, :class:`ProgressSignal`, :class:`ProgressUsage`,
  :class:`ProgressClassification`, :class:`ProgressWindows`,
  :func:`build_progress_snapshot`, :func:`build_progress_snapshot_for_artifact_root`

**Cancellation**
  :class:`CancellationRequested`, :func:`cancelled_contract_result`,
  :func:`cancellation_result_payload`

**Reconcile / takeover**
  :class:`ExpiredTakeoverDecision`, :func:`evaluate_expired_takeover`,
  :func:`reconcile_worktree_for_takeover`, :func:`claim_reconciled_project_lease`

**Restart / quarantine**
  :class:`RestartPolicy`, :class:`RestartDecision`, :class:`RestartDelay`,
  :func:`compute_restart_delay`, :func:`evaluate_automatic_restart`,
  :func:`record_restart_failure`, :func:`clear_quarantined_project_lease`

**Supervision loop**
  :class:`SupervisionLoop`, :class:`SupervisionLoopConfig`,
  :class:`LeaseSupervisionDecision`, :class:`SupervisionScanResult`

Design constraint – SD1
    The supervisor is a *consumer* of native trace, audit, and envelope data.
    It does **not** own workflow routing, loop exits, model routing, suspension,
    or execute / review decisions.  Public re-exports must not expose native
    runtime internals through supervisor module initialisation.
"""

from __future__ import annotations

# ── leases ────────────────────────────────────────────────────────────────────
from arnold.supervisor.leases import (
    InvalidProjectLeaseTransition,
    ProjectLease,
    ProjectLeaseIdentity,
    ProjectLeaseState,
    can_transition_project_lease,
    ensure_project_lease_transition,
    is_terminal_project_lease_state,
)

# ── stores ────────────────────────────────────────────────────────────────────
from arnold.supervisor.store import (
    FileProjectLeaseStore,
    PostgresProjectLeaseStore,
    ProjectLeaseAlreadyExists,
    ProjectLeaseConflict,
    ProjectLeaseLockConflict,
    ProjectLeaseNotFound,
    ProjectLeaseStore,
    ProjectLeaseTokenMismatch,
)

# ── capacity ──────────────────────────────────────────────────────────────────
from arnold.supervisor.capacity import (
    CapacityDecision,
    CapacityGate,
    CapacityGrant,
    CapacityPool,
    CapacityPoolConfig,
    CapacityStatus,
)

# ── capacity context (call-site helpers) ──────────────────────────────────────
from arnold.supervisor.capacity_context import (
    CapacityContext,
    CapacityGateRejected,
    capacity_delay_metadata,
    current_capacity_context,
    gate_capacity,
    set_capacity_context,
)

# ── progress ──────────────────────────────────────────────────────────────────
from arnold.supervisor.progress import (
    ProgressClassification,
    ProgressSignal,
    ProgressSnapshot,
    ProgressUsage,
    ProgressWindows,
    build_progress_snapshot,
    build_progress_snapshot_for_artifact_root,
)

# ── cancellation ──────────────────────────────────────────────────────────────
from arnold.supervisor.cancellation import (
    CancellationRequested,
    cancelled_contract_result,
    cancellation_result_payload,
)

# ── reconcile / takeover ──────────────────────────────────────────────────────
from arnold.supervisor.reconcile import (
    ExpiredTakeoverDecision,
    claim_reconciled_project_lease,
    evaluate_expired_takeover,
    reconcile_worktree_for_takeover,
)

# ── restart / quarantine ──────────────────────────────────────────────────────
from arnold.supervisor.restart import (
    RestartDecision,
    RestartDelay,
    RestartPolicy,
    clear_quarantined_project_lease,
    compute_restart_delay,
    evaluate_automatic_restart,
    record_restart_failure,
)

# ── supervision loop ──────────────────────────────────────────────────────────
from arnold.supervisor.loop import (
    LeaseSupervisionDecision,
    SupervisionLoop,
    SupervisionLoopConfig,
    SupervisionScanResult,
)

__all__ = [
    # leases
    "InvalidProjectLeaseTransition",
    "ProjectLease",
    "ProjectLeaseIdentity",
    "ProjectLeaseState",
    "can_transition_project_lease",
    "ensure_project_lease_transition",
    "is_terminal_project_lease_state",
    # stores
    "FileProjectLeaseStore",
    "PostgresProjectLeaseStore",
    "ProjectLeaseAlreadyExists",
    "ProjectLeaseConflict",
    "ProjectLeaseLockConflict",
    "ProjectLeaseNotFound",
    "ProjectLeaseStore",
    "ProjectLeaseTokenMismatch",
    # capacity
    "CapacityDecision",
    "CapacityGate",
    "CapacityGrant",
    "CapacityPool",
    "CapacityPoolConfig",
    "CapacityStatus",
    # capacity context
    "CapacityContext",
    "CapacityGateRejected",
    "capacity_delay_metadata",
    "current_capacity_context",
    "gate_capacity",
    "set_capacity_context",
    # progress
    "ProgressClassification",
    "ProgressSignal",
    "ProgressSnapshot",
    "ProgressUsage",
    "ProgressWindows",
    "build_progress_snapshot",
    "build_progress_snapshot_for_artifact_root",
    # cancellation
    "CancellationRequested",
    "cancelled_contract_result",
    "cancellation_result_payload",
    # reconcile / takeover
    "ExpiredTakeoverDecision",
    "claim_reconciled_project_lease",
    "evaluate_expired_takeover",
    "reconcile_worktree_for_takeover",
    # restart / quarantine
    "RestartDecision",
    "RestartDelay",
    "RestartPolicy",
    "clear_quarantined_project_lease",
    "compute_restart_delay",
    "evaluate_automatic_restart",
    "record_restart_failure",
    # supervision loop
    "LeaseSupervisionDecision",
    "SupervisionLoop",
    "SupervisionLoopConfig",
    "SupervisionScanResult",
]
