"""Project lease contracts for supervisor-owned worker coordination.

This module defines the backend-neutral current-state record shared by future
file and Postgres lease stores.  The contract is scoped to project/worktree
ownership and deliberately avoids durable scheduled-task internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Mapping

from arnold.runtime.durable_ops.typed_resources import JSONValue, ensure_json_safe

__all__ = [
    "InvalidProjectLeaseTransition",
    "ProjectLease",
    "ProjectLeaseIdentity",
    "ProjectLeaseState",
    "can_transition_project_lease",
    "ensure_project_lease_transition",
    "is_terminal_project_lease_state",
]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _datetime_to_json(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _datetime_from_json(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("datetime value must be a non-empty ISO-8601 string")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class ProjectLeaseState(StrEnum):
    """Lifecycle state for one project/worktree lease record."""

    PENDING = "pending"
    LEASED = "leased"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    QUARANTINED = "quarantined"


TERMINAL_PROJECT_LEASE_STATES: frozenset[ProjectLeaseState] = frozenset(
    {
        ProjectLeaseState.SUCCEEDED,
        ProjectLeaseState.FAILED,
        ProjectLeaseState.CANCELLED,
        ProjectLeaseState.QUARANTINED,
    }
)

ALLOWED_PROJECT_LEASE_TRANSITIONS: Mapping[
    ProjectLeaseState, frozenset[ProjectLeaseState]
] = {
    ProjectLeaseState.PENDING: frozenset(
        {
            ProjectLeaseState.LEASED,
            ProjectLeaseState.FAILED,
            ProjectLeaseState.CANCELLED,
            ProjectLeaseState.QUARANTINED,
        }
    ),
    ProjectLeaseState.LEASED: frozenset(
        {
            ProjectLeaseState.PENDING,
            ProjectLeaseState.SUCCEEDED,
            ProjectLeaseState.FAILED,
            ProjectLeaseState.CANCELLED,
            ProjectLeaseState.QUARANTINED,
        }
    ),
    ProjectLeaseState.SUCCEEDED: frozenset(),
    ProjectLeaseState.FAILED: frozenset(),
    ProjectLeaseState.CANCELLED: frozenset(),
    ProjectLeaseState.QUARANTINED: frozenset(),
}


class InvalidProjectLeaseTransition(ValueError):
    """Raised when a project lease lifecycle transition violates the contract."""


def is_terminal_project_lease_state(state: ProjectLeaseState) -> bool:
    """Return whether ``state`` rejects all future transitions."""

    return state in TERMINAL_PROJECT_LEASE_STATES


def can_transition_project_lease(
    current: ProjectLeaseState,
    target: ProjectLeaseState,
) -> bool:
    """Return whether ``current -> target`` is an allowed lifecycle transition."""

    return target in ALLOWED_PROJECT_LEASE_TRANSITIONS[current]


def ensure_project_lease_transition(
    current: ProjectLeaseState,
    target: ProjectLeaseState,
) -> None:
    """Raise if ``current -> target`` is not an allowed lease transition."""

    if is_terminal_project_lease_state(current):
        raise InvalidProjectLeaseTransition(
            f"project lease state {current.value!r} is terminal"
        )
    if not can_transition_project_lease(current, target):
        raise InvalidProjectLeaseTransition(
            f"project lease transition {current.value!r} -> {target.value!r} is not allowed"
        )


@dataclass(frozen=True)
class ProjectLeaseIdentity:
    """Stable identity for one project/worktree run attempt."""

    project_id: str
    worktree_id: str
    run_id: str

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("project_id is required")
        if not self.worktree_id:
            raise ValueError("worktree_id is required")
        if not self.run_id:
            raise ValueError("run_id is required")

    @property
    def project_worktree_key(self) -> str:
        """Return the uniqueness key shared across competing run attempts."""

        return f"{self.project_id}:{self.worktree_id}"

    def to_json(self) -> dict[str, str]:
        """Serialize the stable project/worktree/run identity."""

        return {
            "project_id": self.project_id,
            "worktree_id": self.worktree_id,
            "run_id": self.run_id,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "ProjectLeaseIdentity":
        """Deserialize the stable project/worktree/run identity."""

        return cls(
            project_id=str(data["project_id"]),
            worktree_id=str(data["worktree_id"]),
            run_id=str(data["run_id"]),
        )


@dataclass(frozen=True)
class ProjectLease:
    """Current-state record for one supervisor-managed project lease."""

    identity: ProjectLeaseIdentity
    state: ProjectLeaseState = ProjectLeaseState.PENDING
    owner_id: str | None = None
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_progress_at: datetime | None = None
    retry_count: int = 0
    failure_count: int = 0
    max_failures: int | None = None
    last_failure_at: datetime | None = None
    next_retry_at: datetime | None = None
    last_failure_reason: str | None = None
    last_result: Mapping[str, JSONValue] | None = None
    quarantine_reason: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    lock_version: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ProjectLeaseIdentity):
            raise TypeError("identity must be a ProjectLeaseIdentity")
        if not isinstance(self.state, ProjectLeaseState):
            object.__setattr__(self, "state", ProjectLeaseState(self.state))
        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")
        if self.failure_count < 0:
            raise ValueError("failure_count must be non-negative")
        if self.max_failures is not None and self.max_failures < 1:
            raise ValueError("max_failures must be at least 1 when provided")
        if (
            self.max_failures is not None
            and self.failure_count > self.max_failures
        ):
            raise ValueError("failure_count cannot exceed max_failures")
        if self.lock_version < 0:
            raise ValueError("lock_version must be non-negative")
        if self.state is ProjectLeaseState.LEASED:
            if not self.owner_id:
                raise ValueError("owner_id is required while leased")
            if not self.lease_token:
                raise ValueError("lease_token is required while leased")
            if self.lease_expires_at is None:
                raise ValueError("lease_expires_at is required while leased")
        if self.state is ProjectLeaseState.QUARANTINED and not self.quarantine_reason:
            raise ValueError("quarantine_reason is required while quarantined")
        if self.last_result is not None:
            object.__setattr__(
                self,
                "last_result",
                ensure_json_safe(dict(self.last_result), field_name="last_result"),
            )

    @property
    def project_id(self) -> str:
        return self.identity.project_id

    @property
    def worktree_id(self) -> str:
        return self.identity.worktree_id

    @property
    def run_id(self) -> str:
        return self.identity.run_id

    @property
    def project_worktree_key(self) -> str:
        return self.identity.project_worktree_key

    def has_active_lease(self, now: datetime | None = None) -> bool:
        """Return whether the lease token is active at ``now``."""

        if self.state is not ProjectLeaseState.LEASED or self.lease_expires_at is None:
            return False
        return self.lease_expires_at > (now or _utc_now())

    def to_json(self) -> dict[str, Any]:
        """Serialize the lease as a JSON-safe mapping."""

        return {
            "identity": self.identity.to_json(),
            "state": self.state.value,
            "owner_id": self.owner_id,
            "lease_token": self.lease_token,
            "lease_expires_at": _datetime_to_json(self.lease_expires_at),
            "last_heartbeat_at": _datetime_to_json(self.last_heartbeat_at),
            "last_progress_at": _datetime_to_json(self.last_progress_at),
            "retry_count": self.retry_count,
            "failure_count": self.failure_count,
            "max_failures": self.max_failures,
            "last_failure_at": _datetime_to_json(self.last_failure_at),
            "next_retry_at": _datetime_to_json(self.next_retry_at),
            "last_failure_reason": self.last_failure_reason,
            "last_result": None if self.last_result is None else dict(self.last_result),
            "quarantine_reason": self.quarantine_reason,
            "created_at": _datetime_to_json(self.created_at),
            "updated_at": _datetime_to_json(self.updated_at),
            "lock_version": self.lock_version,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "ProjectLease":
        """Deserialize a JSON-safe project lease mapping."""

        identity_payload = data.get("identity")
        if not isinstance(identity_payload, Mapping):
            raise ValueError("identity is required")
        return cls(
            identity=ProjectLeaseIdentity.from_json(identity_payload),
            state=ProjectLeaseState(data.get("state", ProjectLeaseState.PENDING.value)),
            owner_id=_optional_str(data.get("owner_id")),
            lease_token=_optional_str(data.get("lease_token")),
            lease_expires_at=_datetime_from_json(data.get("lease_expires_at")),
            last_heartbeat_at=_datetime_from_json(data.get("last_heartbeat_at")),
            last_progress_at=_datetime_from_json(data.get("last_progress_at")),
            retry_count=int(data.get("retry_count", 0)),
            failure_count=int(data.get("failure_count", 0)),
            max_failures=_optional_int(data.get("max_failures")),
            last_failure_at=_datetime_from_json(data.get("last_failure_at")),
            next_retry_at=_datetime_from_json(data.get("next_retry_at")),
            last_failure_reason=_optional_str(data.get("last_failure_reason")),
            last_result=data.get("last_result"),
            quarantine_reason=_optional_str(data.get("quarantine_reason")),
            created_at=_datetime_from_json(data.get("created_at")) or _utc_now(),
            updated_at=_datetime_from_json(data.get("updated_at")) or _utc_now(),
            lock_version=int(data.get("lock_version", 0)),
        )


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
