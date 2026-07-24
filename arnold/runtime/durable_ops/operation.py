"""Durable operation run contracts.

This module models persisted long-running operation runs.  It is separate from
``arnold.runtime.operations``, which is the plugin dispatch surface rather than
durable run state.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Mapping

__all__ = [
    "InvalidOperationTransition",
    "OperationRun",
    "OperationState",
    "RetryMetadata",
    "can_transition_operation",
    "ensure_operation_transition",
    "is_terminal_operation_state",
]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class OperationState(str, Enum):
    """Current lifecycle state for a durable operation run."""

    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    SUSPENDED = "suspended"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_OPERATION_STATES: frozenset[OperationState] = frozenset(
    {
        OperationState.SUCCEEDED,
        OperationState.FAILED,
        OperationState.CANCELLED,
    }
)

ALLOWED_OPERATION_TRANSITIONS: Mapping[OperationState, frozenset[OperationState]] = {
    OperationState.PENDING: frozenset(
        {
            OperationState.AWAITING_APPROVAL,
            OperationState.RUNNING,
            OperationState.FAILED,
            OperationState.CANCELLED,
        }
    ),
    OperationState.AWAITING_APPROVAL: frozenset(
        {
            OperationState.RUNNING,
            OperationState.FAILED,
            OperationState.CANCELLED,
        }
    ),
    OperationState.RUNNING: frozenset(
        {
            OperationState.AWAITING_APPROVAL,
            OperationState.SUSPENDED,
            OperationState.SUCCEEDED,
            OperationState.FAILED,
            OperationState.CANCELLED,
        }
    ),
    OperationState.SUSPENDED: frozenset(
        {
            OperationState.RUNNING,
            OperationState.FAILED,
            OperationState.CANCELLED,
        }
    ),
    OperationState.SUCCEEDED: frozenset(),
    OperationState.FAILED: frozenset(),
    OperationState.CANCELLED: frozenset(),
}


class InvalidOperationTransition(ValueError):
    """Raised when an operation run state transition violates the contract."""


def is_terminal_operation_state(state: OperationState) -> bool:
    """Return whether ``state`` rejects all future transitions."""

    return state in TERMINAL_OPERATION_STATES


def can_transition_operation(current: OperationState, target: OperationState) -> bool:
    """Return whether ``current -> target`` is an allowed lifecycle transition."""

    return target in ALLOWED_OPERATION_TRANSITIONS[current]


def ensure_operation_transition(current: OperationState, target: OperationState) -> None:
    """Raise if ``current -> target`` is not allowed."""

    if is_terminal_operation_state(current):
        raise InvalidOperationTransition(
            f"operation state {current.value!r} is terminal"
        )
    if not can_transition_operation(current, target):
        raise InvalidOperationTransition(
            f"operation state transition {current.value!r} -> {target.value!r} is not allowed"
        )


@dataclass(frozen=True)
class RetryMetadata:
    """Retry counters and the last failure summary for an operation run."""

    attempt: int = 0
    max_attempts: int = 1
    last_error: str | None = None

    def __post_init__(self) -> None:
        if self.attempt < 0:
            raise ValueError("attempt must be non-negative")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.attempt > self.max_attempts:
            raise ValueError("attempt cannot exceed max_attempts")


@dataclass(frozen=True)
class OperationRun:
    """Queryable current-state record for one durable operation execution."""

    id: str
    operation_type: str
    state: OperationState = OperationState.PENDING
    parent_operation_id: str | None = None
    operation_dir: str | None = None
    retry: RetryMetadata = field(default_factory=RetryMetadata)
    idempotency_key: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    lock_version: int = 0

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        if not self.operation_type:
            raise ValueError("operation_type is required")
        if self.lock_version < 0:
            raise ValueError("lock_version must be non-negative")
        if not isinstance(self.state, OperationState):
            object.__setattr__(self, "state", OperationState(self.state))

    def transition_to(
        self,
        target: OperationState,
        *,
        now: datetime | None = None,
    ) -> "OperationRun":
        """Return a copy transitioned to ``target`` after validating the state machine."""

        target = OperationState(target)
        ensure_operation_transition(self.state, target)
        timestamp = now or _utc_now()
        started_at = self.started_at
        completed_at = self.completed_at
        if target is OperationState.RUNNING and started_at is None:
            started_at = timestamp
        if is_terminal_operation_state(target):
            completed_at = timestamp
        return replace(
            self,
            state=target,
            updated_at=timestamp,
            started_at=started_at,
            completed_at=completed_at,
        )
