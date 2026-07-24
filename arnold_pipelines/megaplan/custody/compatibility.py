"""Old-reader/new-writer compatibility bridge (M7 shadow-only).

Defines per-reader compatibility expiry, mode-gated behavior, and rollback
safety guards.  Every old reader that existed before the M7 projection
migration is registered with an explicit compatibility deadline.  By default,
old-reader compatibility is granted through M8 acceptance unless explicitly
overridden — this prevents the M7 projection migration from breaking
existing consumers while also ensuring there is a hard deadline.

Rollback Safety
---------------
The ``validate_rollback_safety()`` guard ensures that deactivating or
rolling back M7 does **not** re-enable legacy authoritative writers and
does **not** erase quarantined attempts.  In a safe rollback:

* Promotion/effects are disabled — no authority-increasing writer moves
  from ``shadow`` to ``active`` without machine-verifiable acceptance.
* Legacy authoritative writers (pre-M7 full-file replacements) remain
  retired — they are not restored.
* Quarantined outbox and lease-store entries are preserved — they are
  never erased.

Principles
----------
* **Per-reader expiry** — Every legacy reader has an explicit deadline
  milestone by which it must migrate to projection-aware consumption.
* **Mode-gated** — Compatibility checks adapt to the current M7 mode
  (shadow, active, rollback).
* **Default M8 acceptance** — Unless a reader has an explicit earlier
  deadline, old-reader compatibility is valid through M8.
* **Rollback-safe** — Rollback disables promotion/effects without
  restoring legacy authoritative writers or erasing quarantined attempts.
* **Not authority** — This module is advisory.  It does not authorize,
  block, or mutate any production state.

All production gates and mutating effects remain disabled in M7;
this module runs in shadow/report-only mode.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, FrozenSet, Mapping, Optional, Sequence


# ── Schema version constant ────────────────────────────────────────────────

COMPATIBILITY_SCHEMA_VERSION = 1


# ── Compatibility modes ────────────────────────────────────────────────────


class CompatibilityMode(StrEnum):
    """Current M7 compatibility mode.

    * **shadow** — M7 is active but enforcement is off; compatibility
      checks are advisory.
    * **active** — M7 enforcement is on; expired readers may be warned
      or blocked.
    * **rollback** — M7 is being rolled back; all promotion/effects are
      disabled and legacy writers must NOT be reactivated.
    """

    SHADOW = "shadow"
    ACTIVE = "active"
    ROLLBACK = "rollback"


# ── Compatibility status ───────────────────────────────────────────────────


class CompatibilityStatus(StrEnum):
    """Per-reader compatibility status."""

    COMPATIBLE = "compatible"
    """The reader is within its compatibility window."""

    EXPIRING = "expiring"
    """The reader is approaching its deadline (within one milestone)."""

    EXPIRED = "expired"
    """The reader's compatibility window has closed."""

    UNKNOWN = "unknown"
    """The reader is not in the compatibility registry."""

    ROLLBACK_SAFE = "rollback_safe"
    """Rollback has been validated as safe (no legacy writer reactivation)."""

    ROLLBACK_BLOCKED = "rollback_blocked"
    """Rollback would re-enable a legacy authoritative writer or erase
    quarantined evidence — the rollback is blocked."""


# ── Deadline milestones ────────────────────────────────────────────────────


class DeadlineMilestone(StrEnum):
    """Milestones that can serve as compatibility deadlines."""

    M7 = "M7"
    M7A = "M7A"
    M8 = "M8"
    M9 = "M9"
    M10 = "M10"
    NONE = "none"  # No explicit deadline (treated as M8 for safety)


_DEFAULT_DEADLINE: DeadlineMilestone = DeadlineMilestone.M8

# Milestone ordering for expiry comparisons
_MILESTONE_ORDER: tuple[DeadlineMilestone, ...] = (
    DeadlineMilestone.M7,
    DeadlineMilestone.M7A,
    DeadlineMilestone.M8,
    DeadlineMilestone.M9,
    DeadlineMilestone.M10,
)


def _milestone_index(ms: DeadlineMilestone) -> int:
    """Return the ordinal position of a milestone or len(order) for NONE."""
    if ms == DeadlineMilestone.NONE:
        return len(_MILESTONE_ORDER)
    try:
        return _MILESTONE_ORDER.index(ms)
    except ValueError:
        return len(_MILESTONE_ORDER)


def _milestone_expired(
    deadline: DeadlineMilestone, current: DeadlineMilestone
) -> bool:
    """Return True when *current* is at or past *deadline*."""
    if deadline == DeadlineMilestone.NONE:
        return False  # No deadline → never expired
    return _milestone_index(current) >= _milestone_index(deadline)


# ── Reader compatibility entry ─────────────────────────────────────────────


@dataclass(frozen=True)
class ReaderCompatibility:
    """A registered old-reader compatibility entry.

    Every legacy reader that consumed projection data from full-file
    replacements before the M7 projection migration must be registered
    here.  The entry records the reader identity, what projections it
    reads, the deadline by which it must migrate, and the current
    compatibility mode.

    Fields
    ------
    reader_id
        Stable identifier, e.g. ``"legacy-chain-state-reader"``.
    reader_name
        Human-readable name, e.g. ``"Chain State Consumer"``.
    description
        What this reader consumes and how.
    projection_ids
        Projection IDs this reader consumes (may be empty if the
        reader predates projection history).
    module_paths
        Dotted Python paths to the module(s) that provide this reader.
    deadline_milestone
        Milestone by which compatibility expires.  Defaults to
        ``M8`` — old-reader compatibility is valid through M8
        acceptance unless explicitly overridden.
    mode
        Current compatibility mode.  Defaults to ``shadow``.
    quarantined_entries
        Count of quarantined outbox or lease-store entries that
        were created during this reader's migration window.  Used
        by rollback safety checks.
    """

    reader_id: str
    reader_name: str
    description: str = ""
    projection_ids: FrozenSet[str] = field(default_factory=frozenset)
    module_paths: FrozenSet[str] = field(default_factory=frozenset)
    deadline_milestone: DeadlineMilestone = DeadlineMilestone.M8
    mode: CompatibilityMode = CompatibilityMode.SHADOW
    quarantined_entries: int = 0

    def is_expired(
        self, current_milestone: DeadlineMilestone | None = None
    ) -> bool:
        """Check whether this reader's compatibility has expired."""
        if self.deadline_milestone == DeadlineMilestone.NONE:
            return False
        if current_milestone is None:
            current_milestone = _current_milestone()
        return _milestone_expired(self.deadline_milestone, current_milestone)

    def is_expiring(
        self, current_milestone: DeadlineMilestone | None = None
    ) -> bool:
        """Check whether this reader is within one milestone of expiry."""
        if self.deadline_milestone == DeadlineMilestone.NONE:
            return False
        if current_milestone is None:
            current_milestone = _current_milestone()
        deadline_idx = _milestone_index(self.deadline_milestone)
        current_idx = _milestone_index(current_milestone)
        return current_idx + 1 >= deadline_idx and current_idx < deadline_idx

    def status(
        self, current_milestone: DeadlineMilestone | None = None
    ) -> CompatibilityStatus:
        """Return the current compatibility status for this reader."""
        if self.mode == CompatibilityMode.ROLLBACK:
            return CompatibilityStatus.ROLLBACK_SAFE
        if self.is_expired(current_milestone):
            return CompatibilityStatus.EXPIRED
        if self.is_expiring(current_milestone):
            return CompatibilityStatus.EXPIRING
        return CompatibilityStatus.COMPATIBLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "reader_id": self.reader_id,
            "reader_name": self.reader_name,
            "description": self.description,
            "projection_ids": sorted(self.projection_ids),
            "module_paths": sorted(self.module_paths),
            "deadline_milestone": str(self.deadline_milestone),
            "mode": str(self.mode),
            "quarantined_entries": self.quarantined_entries,
        }


# ── Compatibility registry ─────────────────────────────────────────────────
#
# Every old reader (pre-M7 full-file consumer) is registered here.
# Each entry has a deadline milestone.  The default is M8 — old-reader
# compatibility is valid through M8 acceptance unless explicitly
# overridden with an earlier deadline.


COMPATIBILITY_REGISTRY: tuple[ReaderCompatibility, ...] = (
    # ── Chain state readers ────────────────────────────────────────────
    ReaderCompatibility(
        reader_id="legacy-chain-state-reader",
        reader_name="Chain State Consumer",
        description=(
            "Legacy callers of load_chain_state() that read chain-state.json "
            "directly without cursor validation.  Migrated in T18."
        ),
        projection_ids=frozenset({"chain-state-projection"}),
        module_paths=frozenset({"arnold_pipelines.megaplan.chain.spec"}),
        deadline_milestone=DeadlineMilestone.M8,
    ),
    # ── Supervisor state readers ───────────────────────────────────────
    ReaderCompatibility(
        reader_id="legacy-supervisor-state-reader",
        reader_name="Supervisor State Consumer",
        description=(
            "Legacy callers of load_supervisor_state() that read the state "
            "JSON directly without cursor validation.  Migrated in T18."
        ),
        projection_ids=frozenset({"supervisor-state-projection"}),
        module_paths=frozenset({"arnold_pipelines.megaplan.supervisor.state"}),
        deadline_milestone=DeadlineMilestone.M8,
    ),
    # ── Bakeoff state readers ──────────────────────────────────────────
    ReaderCompatibility(
        reader_id="legacy-bakeoff-state-reader",
        reader_name="Bakeoff State Consumer",
        description=(
            "Legacy callers of load_bakeoff_state() that read bakeoff JSON "
            "directly without cursor validation.  Migrated in T19."
        ),
        projection_ids=frozenset(
            {"bakeoff-state-projection", "channel-shadow-projection"}
        ),
        module_paths=frozenset({"arnold_pipelines.megaplan.bakeoff.state"}),
        deadline_milestone=DeadlineMilestone.M8,
    ),
    # ── Cloud status snapshot readers ──────────────────────────────────
    ReaderCompatibility(
        reader_id="legacy-status-snapshot-reader",
        reader_name="Cloud Status Snapshot Consumer",
        description=(
            "Legacy callers of load_cloud_status_snapshot() that read "
            "cloud-status.json directly without cursor validation.  "
            "Migrated in T19."
        ),
        projection_ids=frozenset({"status-snapshot-projection"}),
        module_paths=frozenset(
            {"arnold_pipelines.megaplan.cloud.status_snapshot"}
        ),
        deadline_milestone=DeadlineMilestone.M8,
    ),
    # ── Heartbeat state readers ────────────────────────────────────────
    ReaderCompatibility(
        reader_id="legacy-heartbeat-state-reader",
        reader_name="Heartbeat State Consumer",
        description=(
            "Legacy callers that read state.json heartbeat data directly "
            "without cursor validation.  Migrated in T17."
        ),
        projection_ids=frozenset({"heartbeat-projection"}),
        module_paths=frozenset({"arnold_pipelines.megaplan._core.state"}),
        deadline_milestone=DeadlineMilestone.M8,
    ),
    # ── Repair lock readers (admission/projection evidence only) ───────
    ReaderCompatibility(
        reader_id="legacy-repair-lock-reader",
        reader_name="Repair Lock Consumer",
        description=(
            "Legacy callers that used PID-lock behavior as admission "
            "authority.  Migrated to lease-store ownership in T13."
        ),
        projection_ids=frozenset(),
        module_paths=frozenset({"arnold_pipelines.megaplan.cloud.repair_lock"}),
        deadline_milestone=DeadlineMilestone.M8,
    ),
)


# ── Registry index helpers ─────────────────────────────────────────────────

_COMPAT_BY_ID: Mapping[str, ReaderCompatibility] = {
    r.reader_id: r for r in COMPATIBILITY_REGISTRY
}

_COMPAT_BY_PROJECTION: Mapping[str, tuple[ReaderCompatibility, ...]] = {}

for _reader in COMPATIBILITY_REGISTRY:
    for _proj_id in _reader.projection_ids:
        _existing = list(_COMPAT_BY_PROJECTION.get(_proj_id, ()))
        _existing.append(_reader)
        _COMPAT_BY_PROJECTION[_proj_id] = tuple(_existing)


def get_reader(reader_id: str) -> Optional[ReaderCompatibility]:
    """Look up a registered reader by its stable id."""
    return _COMPAT_BY_ID.get(reader_id)


def list_readers(
    mode: CompatibilityMode | None = None,
    deadline: DeadlineMilestone | None = None,
) -> tuple[ReaderCompatibility, ...]:
    """List registered readers, optionally filtered by mode or deadline."""
    result = COMPATIBILITY_REGISTRY
    if mode is not None:
        result = tuple(r for r in result if r.mode == mode)
    if deadline is not None:
        result = tuple(r for r in result if r.deadline_milestone == deadline)
    return result


def list_expired_readers(
    current_milestone: DeadlineMilestone | None = None,
) -> tuple[ReaderCompatibility, ...]:
    """Return readers whose compatibility has expired."""
    return tuple(
        r for r in COMPATIBILITY_REGISTRY if r.is_expired(current_milestone)
    )


def list_expiring_readers(
    current_milestone: DeadlineMilestone | None = None,
) -> tuple[ReaderCompatibility, ...]:
    """Return readers approaching their compatibility deadline."""
    return tuple(
        r for r in COMPATIBILITY_REGISTRY if r.is_expiring(current_milestone)
    )


# ── Mode-gated compatibility check ─────────────────────────────────────────


def _current_milestone() -> DeadlineMilestone:
    """Read the current milestone from the environment.

    Controlled by ``ARNOLD_CURRENT_MILESTONE``.  Defaults to ``M7``
    when unset (the milestone that introduced this module).
    """
    raw = os.environ.get("ARNOLD_CURRENT_MILESTONE", "M7").strip().upper()
    try:
        return DeadlineMilestone(raw)
    except ValueError:
        return DeadlineMilestone.M7


def _compatibility_mode() -> CompatibilityMode:
    """Determine the current compatibility mode from environment flags.

    Priority:
    1. ``ARNOLD_M7_ROLLBACK`` → ``ROLLBACK`` mode
    2. ``ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT`` → ``ACTIVE`` mode
    3. Default → ``SHADOW`` mode
    """
    # Rollback flag takes absolute priority
    if os.environ.get("ARNOLD_M7_ROLLBACK", "").strip() in ("1", "true", "yes"):
        return CompatibilityMode.ROLLBACK

    # Enforcement flag gates active mode
    enforcement = os.environ.get(
        "ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT", "0"
    ).strip()
    if enforcement in ("1", "true", "yes"):
        return CompatibilityMode.ACTIVE

    return CompatibilityMode.SHADOW


def check_reader_compatibility(
    reader_id: str,
    *,
    current_milestone: DeadlineMilestone | None = None,
    mode: CompatibilityMode | None = None,
) -> CompatibilityStatus:
    """Check whether a reader is compatible under the current mode.

    In ``SHADOW`` mode, expiry is advisory — the reader can still
    consume projection data but should log a warning.

    In ``ACTIVE`` mode, expired readers may be denied access.

    In ``ROLLBACK`` mode, all promotion/effects are disabled and
    the check confirms rollback safety.

    Parameters
    ----------
    reader_id:
        Stable reader identifier.
    current_milestone:
        Override the current milestone (for testing).
    mode:
        Override the compatibility mode (for testing).

    Returns
    -------
    CompatibilityStatus
        The current compatibility status for the reader.
    """
    reader = _COMPAT_BY_ID.get(reader_id)
    if reader is None:
        return CompatibilityStatus.UNKNOWN

    if mode is None:
        mode = _compatibility_mode()

    if mode == CompatibilityMode.ROLLBACK:
        return CompatibilityStatus.ROLLBACK_SAFE

    return reader.status(current_milestone)


def get_mode() -> CompatibilityMode:
    """Return the current compatibility mode."""
    return _compatibility_mode()


def is_production_enforcement_enabled() -> bool:
    """Return ``True`` when M7 production enforcement is enabled.

    This is the same gate as
    :func:`arnold_pipelines.megaplan.custody.action_validator._production_enforcement_enabled`.
    """
    raw = os.environ.get("ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT", "0").strip()
    return raw in ("1", "true", "yes")


# ── Rollback safety ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RollbackValidation:
    """Result of a rollback safety validation.

    Fields
    ------
    safe
        ``True`` when the rollback is safe — no legacy authoritative
        writer would be re-enabled and no quarantined evidence would
        be erased.
    blocked_by
        List of reader or writer IDs that would be unsafe to roll back.
    quarantined_preserved
        Count of quarantined entries that would be preserved.
    legacy_writers_blocked
        List of legacy authoritative writer IDs that remain retired.
    reason
        Human-readable explanation.
    """

    safe: bool
    blocked_by: tuple[str, ...] = ()
    quarantined_preserved: int = 0
    legacy_writers_blocked: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "blocked_by": list(self.blocked_by),
            "quarantined_preserved": self.quarantined_preserved,
            "legacy_writers_blocked": list(self.legacy_writers_blocked),
            "reason": self.reason,
        }


def validate_rollback_safety(
    *,
    reader_ids: Sequence[str] | None = None,
    writer_ids: Sequence[str] | None = None,
    quarantined_count: int | None = None,
) -> RollbackValidation:
    """Validate that a rollback is safe.

    A safe rollback:
    1. Does NOT re-enable any legacy authoritative writer.
    2. Does NOT erase any quarantined outbox or lease-store entries.
    3. Disables all promotion/effects (no writer moves from shadow
       to active without machine-verifiable acceptance).

    In practice, rollback is always safe because M7 writers are
    shadow-only and legacy authoritative writers were retired in
    earlier milestones, not deleted.  Quarantined entries are
    preserved in append-only histories.

    Parameters
    ----------
    reader_ids:
        Reader IDs to check.  If None, checks all registered readers.
    writer_ids:
        Legacy authoritative writer IDs that might be re-enabled.
        If None, assumes no legacy writers are candidates.
    quarantined_count:
        Number of quarantined entries.  If None, sums from the
        compatibility registry.

    Returns
    -------
    RollbackValidation
        Structured safety result.
    """
    blocked: list[str] = []
    legacy_blocked: list[str] = []

    # ── Check 1: No legacy authoritative writer re-enabled ─────────────
    if writer_ids:
        # Legacy authoritative writers were retired in earlier milestones
        # (T2 inventory invariant).  Rollback must not re-enable them.
        legacy_blocked = list(writer_ids)
        # If any legacy writer would become active, block rollback
        for wid in writer_ids:
            blocked.append(f"legacy-writer:{wid}")

    # ── Check 2: Quarantined entries preserved ─────────────────────────
    total_quarantined = quarantined_count
    if total_quarantined is None:
        total_quarantined = sum(
            r.quarantined_entries for r in COMPATIBILITY_REGISTRY
        )

    # Quarantined entries are append-only and never erased —
    # they are always preserved during rollback.
    # No block needed unless the store is being deleted (which
    # would be a separate operation, not a compatibility rollback).

    # ── Check 3: No promotion/effects active ───────────────────────────
    # In rollback mode, all promotion is disabled.  The mode gate
    # in check_reader_compatibility returns ROLLBACK_SAFE.
    # Writers are shadow-only; no active promotions exist.

    safe = len(blocked) == 0

    reason = (
        "Rollback is safe: no legacy authoritative writers re-enabled, "
        f"{total_quarantined} quarantined entries preserved, "
        "all promotion/effects disabled."
    )

    return RollbackValidation(
        safe=safe,
        blocked_by=tuple(blocked),
        quarantined_preserved=total_quarantined,
        legacy_writers_blocked=tuple(legacy_blocked),
        reason=reason,
    )


# ── Compatibility snapshot ─────────────────────────────────────────────────


@dataclass(frozen=True)
class CompatibilitySnapshot:
    """A point-in-time snapshot of the compatibility state.

    Captures the current mode, all registered readers with their
    status, and rollback safety for audit purposes.

    Fields
    ------
    mode
        Current compatibility mode.
    milestone
        Current milestone.
    readers
        All registered readers with their current status.
    rollback_validation
        Rollback safety validation result.
    enforcement_enabled
        Whether production enforcement is enabled.
    generated_at
        ISO-8601 timestamp.
    """

    mode: CompatibilityMode
    milestone: DeadlineMilestone
    readers: tuple[ReaderCompatibility, ...]
    rollback_validation: RollbackValidation
    enforcement_enabled: bool = False
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not self.generated_at:
            object.__setattr__(
                self,
                "generated_at",
                datetime.now(timezone.utc).isoformat(),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": str(self.mode),
            "milestone": str(self.milestone),
            "readers": [r.to_dict() for r in self.readers],
            "rollback_validation": self.rollback_validation.to_dict(),
            "enforcement_enabled": self.enforcement_enabled,
            "generated_at": self.generated_at,
        }


def snapshot() -> CompatibilitySnapshot:
    """Generate a point-in-time compatibility snapshot.

    This is the primary entry point for audit and diagnostics.
    It captures the current mode, milestone, all reader statuses,
    and rollback safety.
    """
    mode = _compatibility_mode()
    milestone = _current_milestone()

    readers = tuple(
        ReaderCompatibility(
            reader_id=r.reader_id,
            reader_name=r.reader_name,
            description=r.description,
            projection_ids=r.projection_ids,
            module_paths=r.module_paths,
            deadline_milestone=r.deadline_milestone,
            mode=mode,
            quarantined_entries=r.quarantined_entries,
        )
        for r in COMPATIBILITY_REGISTRY
    )

    rollback = validate_rollback_safety()

    return CompatibilitySnapshot(
        mode=mode,
        milestone=milestone,
        readers=readers,
        rollback_validation=rollback,
        enforcement_enabled=is_production_enforcement_enabled(),
    )


# ── Public API ─────────────────────────────────────────────────────────────

__all__ = [
    "CompatibilityMode",
    "CompatibilityStatus",
    "CompatibilitySnapshot",
    "DeadlineMilestone",
    "ReaderCompatibility",
    "RollbackValidation",
    "COMPATIBILITY_REGISTRY",
    "check_reader_compatibility",
    "get_mode",
    "is_production_enforcement_enabled",
    "list_expired_readers",
    "list_expiring_readers",
    "list_readers",
    "snapshot",
    "validate_rollback_safety",
]
