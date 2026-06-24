"""Guardian v0 data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class GuardianOutcome(str, Enum):
    """High-level result of a Guardian inspection or action."""

    OK = "ok"
    NOOP = "noop"
    RETRY = "retry"
    ESCALATED = "escalated"
    FAILED = "failed"


class GuardianMaterialTransition(str, Enum):
    """Material operation state changes detected by Guardian."""

    NONE = "none"
    STARTED = "started"
    PROGRESSED = "progressed"
    STALLED = "stalled"
    RESUMED = "resumed"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass(frozen=True)
class GuardianRetryCounters:
    """Retry counters used by Guardian policy gates."""

    transient: int = 0
    resume_attempts: int = 0
    consecutive_inspection_failures: int = 0


@dataclass(frozen=True)
class GuardianInspectionResult:
    """Structured result emitted by a Guardian inspection handler."""

    operation_id: str | None
    outcome: GuardianOutcome
    material_transition: GuardianMaterialTransition = GuardianMaterialTransition.NONE
    summary: str = ""
    retry_counters: GuardianRetryCounters = field(default_factory=GuardianRetryCounters)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    inspected_at: datetime | None = None
