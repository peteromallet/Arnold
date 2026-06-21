"""Generic suspension contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from arnold.kernel.capabilities import DispatchKey
from arnold.kernel.ids import ReentryId


class SuspensionState(StrEnum):
    """Lifecycle labels for a suspended run."""

    PENDING = "pending"
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class SuspendCapabilityRoute:
    """Route used to suspend and later re-enter a workflow."""

    route_id: str
    dispatch_key: DispatchKey
    reentry_id: ReentryId
    payload_schema_hash: str | None = None


@dataclass(frozen=True)
class SuspensionRecord:
    """Serializable state for a suspended run."""

    run_id: str
    manifest_hash: str
    node_ref: str
    route: SuspendCapabilityRoute
    state: SuspensionState = SuspensionState.PENDING
