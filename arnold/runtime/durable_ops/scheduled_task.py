"""Scheduled task contracts for durable operation orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Mapping

from .typed_resources import JSONValue, ensure_json_safe

__all__ = [
    "InvalidScheduledTaskTransition",
    "ScheduledTask",
    "ScheduledTaskState",
    "can_transition_scheduled_task",
    "ensure_scheduled_task_transition",
    "is_terminal_scheduled_task_state",
]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ScheduledTaskState(str, Enum):
    """Current lifecycle state for a durable scheduled task."""

    PENDING = "pending"
    LEASED = "leased"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_SCHEDULED_TASK_STATES: frozenset[ScheduledTaskState] = frozenset(
    {
        ScheduledTaskState.SUCCEEDED,
        ScheduledTaskState.FAILED,
        ScheduledTaskState.CANCELLED,
    }
)

ALLOWED_SCHEDULED_TASK_TRANSITIONS: Mapping[
    ScheduledTaskState, frozenset[ScheduledTaskState]
] = {
    ScheduledTaskState.PENDING: frozenset(
        {
            ScheduledTaskState.LEASED,
            ScheduledTaskState.FAILED,
            ScheduledTaskState.CANCELLED,
        }
    ),
    ScheduledTaskState.LEASED: frozenset(
        {
            ScheduledTaskState.PENDING,
            ScheduledTaskState.SUCCEEDED,
            ScheduledTaskState.FAILED,
            ScheduledTaskState.CANCELLED,
        }
    ),
    ScheduledTaskState.SUCCEEDED: frozenset(),
    ScheduledTaskState.FAILED: frozenset(),
    ScheduledTaskState.CANCELLED: frozenset(),
}


class InvalidScheduledTaskTransition(ValueError):
    """Raised when a scheduled task state transition violates the contract."""


def is_terminal_scheduled_task_state(state: ScheduledTaskState) -> bool:
    """Return whether ``state`` rejects all future transitions."""

    return state in TERMINAL_SCHEDULED_TASK_STATES


def can_transition_scheduled_task(
    current: ScheduledTaskState,
    target: ScheduledTaskState,
) -> bool:
    """Return whether ``current -> target`` is an allowed lifecycle transition."""

    return target in ALLOWED_SCHEDULED_TASK_TRANSITIONS[current]


def ensure_scheduled_task_transition(
    current: ScheduledTaskState,
    target: ScheduledTaskState,
) -> None:
    """Raise if ``current -> target`` is not allowed."""

    if is_terminal_scheduled_task_state(current):
        raise InvalidScheduledTaskTransition(
            f"scheduled task state {current.value!r} is terminal"
        )
    if not can_transition_scheduled_task(current, target):
        raise InvalidScheduledTaskTransition(
            f"scheduled task transition {current.value!r} -> {target.value!r} is not allowed"
        )


@dataclass(frozen=True)
class ScheduledTask:
    """Queryable current-state record for one durable scheduled task."""

    id: str
    task_type: str
    owner_id: str
    state: ScheduledTaskState = ScheduledTaskState.PENDING
    operation_id: str | None = None
    schedule: str | None = None
    recurring_interval_seconds: int | None = None
    retry_delay_seconds: int | None = None
    jitter_seconds: int = 0
    payload: Mapping[str, JSONValue] = field(default_factory=dict)
    next_run_at: datetime | None = field(default_factory=_utc_now)
    last_result: Mapping[str, JSONValue] | None = None
    failure_count: int = 0
    max_failures: int = 1
    lease_owner: str | None = None
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    idempotency_key: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    lock_version: int = 0

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        if not self.task_type:
            raise ValueError("task_type is required")
        if not self.owner_id:
            raise ValueError("owner_id is required")
        if not isinstance(self.state, ScheduledTaskState):
            object.__setattr__(self, "state", ScheduledTaskState(self.state))
        if (
            self.recurring_interval_seconds is not None
            and self.recurring_interval_seconds <= 0
        ):
            raise ValueError("recurring_interval_seconds must be positive")
        if self.retry_delay_seconds is not None and self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")
        if self.jitter_seconds < 0:
            raise ValueError("jitter_seconds must be non-negative")
        if self.failure_count < 0:
            raise ValueError("failure_count must be non-negative")
        if self.max_failures < 1:
            raise ValueError("max_failures must be at least 1")
        if self.failure_count > self.max_failures:
            raise ValueError("failure_count cannot exceed max_failures")
        if self.lock_version < 0:
            raise ValueError("lock_version must be non-negative")
        object.__setattr__(
            self,
            "payload",
            ensure_json_safe(dict(self.payload), field_name="payload"),
        )
        if self.last_result is not None:
            object.__setattr__(
                self,
                "last_result",
                ensure_json_safe(dict(self.last_result), field_name="last_result"),
            )

    @property
    def is_recurring(self) -> bool:
        """Return whether successful completion should schedule another run."""

        return self.recurring_interval_seconds is not None

    def has_active_lease(self, now: datetime | None = None) -> bool:
        """Return whether the current lease token is still valid."""

        if self.state is not ScheduledTaskState.LEASED or self.lease_expires_at is None:
            return False
        return self.lease_expires_at > (now or _utc_now())

    def is_claimable(self, now: datetime | None = None) -> bool:
        """Return whether the task can be claimed at ``now``."""

        timestamp = now or _utc_now()
        if is_terminal_scheduled_task_state(self.state):
            return False
        if self.state is ScheduledTaskState.LEASED and self.has_active_lease(timestamp):
            return False
        if self.next_run_at is None:
            return False
        return self.next_run_at <= timestamp

    def claim(
        self,
        *,
        lease_owner: str,
        lease_token: str,
        lease_expires_at: datetime,
        now: datetime | None = None,
    ) -> "ScheduledTask":
        """Return a copy claimed with a lease token after validating claimability."""

        if not lease_owner:
            raise ValueError("lease_owner is required")
        if not lease_token:
            raise ValueError("lease_token is required")
        timestamp = now or _utc_now()
        if lease_expires_at <= timestamp:
            raise ValueError("lease_expires_at must be in the future")
        if not self.is_claimable(timestamp):
            raise InvalidScheduledTaskTransition("scheduled task is not claimable")
        if self.state is not ScheduledTaskState.LEASED:
            ensure_scheduled_task_transition(self.state, ScheduledTaskState.LEASED)
        return replace(
            self,
            state=ScheduledTaskState.LEASED,
            lease_owner=lease_owner,
            lease_token=lease_token,
            lease_expires_at=lease_expires_at,
            updated_at=timestamp,
        )

    def complete(
        self,
        *,
        lease_token: str,
        result: Mapping[str, JSONValue] | None = None,
        now: datetime | None = None,
    ) -> "ScheduledTask":
        """Return a copy completed successfully for the matching lease token."""

        self._ensure_matching_lease_token(lease_token)
        timestamp = now or _utc_now()
        result_data = ensure_json_safe(dict(result or {}), field_name="result")
        if self.is_recurring:
            ensure_scheduled_task_transition(self.state, ScheduledTaskState.PENDING)
            next_run_at = timestamp + timedelta(
                seconds=self.recurring_interval_seconds or 0
            )
            target_state = ScheduledTaskState.PENDING
        else:
            ensure_scheduled_task_transition(self.state, ScheduledTaskState.SUCCEEDED)
            next_run_at = None
            target_state = ScheduledTaskState.SUCCEEDED
        return replace(
            self,
            state=target_state,
            next_run_at=next_run_at,
            last_result=result_data,
            failure_count=0,
            lease_owner=None,
            lease_token=None,
            lease_expires_at=None,
            updated_at=timestamp,
        )

    def fail(
        self,
        *,
        lease_token: str,
        result: Mapping[str, JSONValue],
        now: datetime | None = None,
    ) -> "ScheduledTask":
        """Return a copy failed for the matching lease token, retrying if allowed."""

        self._ensure_matching_lease_token(lease_token)
        timestamp = now or _utc_now()
        result_data = ensure_json_safe(dict(result), field_name="result")
        failure_count = self.failure_count + 1
        if failure_count >= self.max_failures:
            ensure_scheduled_task_transition(self.state, ScheduledTaskState.FAILED)
            target_state = ScheduledTaskState.FAILED
            next_run_at = None
        else:
            ensure_scheduled_task_transition(self.state, ScheduledTaskState.PENDING)
            target_state = ScheduledTaskState.PENDING
            next_run_at = timestamp + timedelta(seconds=self.retry_delay_seconds or 0)
        return replace(
            self,
            state=target_state,
            next_run_at=next_run_at,
            last_result=result_data,
            failure_count=failure_count,
            lease_owner=None,
            lease_token=None,
            lease_expires_at=None,
            updated_at=timestamp,
        )

    def cancel(self, *, now: datetime | None = None) -> "ScheduledTask":
        """Return a terminal cancelled copy."""

        timestamp = now or _utc_now()
        ensure_scheduled_task_transition(self.state, ScheduledTaskState.CANCELLED)
        return replace(
            self,
            state=ScheduledTaskState.CANCELLED,
            next_run_at=None,
            lease_owner=None,
            lease_token=None,
            lease_expires_at=None,
            updated_at=timestamp,
        )

    def _ensure_matching_lease_token(self, lease_token: str) -> None:
        if self.state is not ScheduledTaskState.LEASED:
            raise InvalidScheduledTaskTransition("scheduled task is not leased")
        if not lease_token or self.lease_token != lease_token:
            raise InvalidScheduledTaskTransition("lease_token does not match")
