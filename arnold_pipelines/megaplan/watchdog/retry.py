"""Retry-loop state machine for the live watchdog."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from arnold_pipelines.megaplan.cloud.repair_contract import append_repair_event


class RetryOutcome(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    TERMINAL = "terminal"


class RetryCapExceeded(Exception):
    """Raised when attempting a fourth retry."""


@dataclass
class RetryLoop:
    """Tracks up to three attempts per incident.

    Usage::

        loop = RetryLoop()
        while True:
            outcome = run_repair()
            result, done = loop.attempt(outcome)
            if done:
                break
    """

    max_attempts: int = 3
    attempt_count: int = field(default=0, init=False)
    sidecar_dir: str = ""
    session_id: str = ""
    loop_id: str = ""

    def attempt(self, outcome: RetryOutcome) -> tuple[RetryOutcome, bool]:
        """Record one attempt and return (result, done).

        Returns done=True on success, terminal state, or after the third
        failure. Raises ``RetryCapExceeded`` if called after done=True was
        returned.
        """
        if self.attempt_count >= self.max_attempts:
            raise RetryCapExceeded(f"retry cap of {self.max_attempts} exceeded")

        self.attempt_count += 1

        if outcome is RetryOutcome.RESOLVED:
            result = (RetryOutcome.RESOLVED, True)
        elif outcome is RetryOutcome.TERMINAL:
            result = (RetryOutcome.TERMINAL, True)
        elif self.attempt_count >= self.max_attempts:
            result = (RetryOutcome.UNRESOLVED, True)
        else:
            result = (RetryOutcome.UNRESOLVED, False)
        self._append_evidence(outcome, result[1])
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "attempt_count": self.attempt_count,
        }

    def _append_evidence(self, outcome: RetryOutcome, done: bool) -> None:
        if not self.sidecar_dir:
            return
        append_repair_event(
            self.sidecar_dir,
            {
                "session_id": self.session_id,
                "attempt_id": self.loop_id or f"retry-loop:{id(self)}",
                "actor": "watchdog.retry",
                "attempt_number": self.attempt_count,
                "max_attempts": self.max_attempts,
                "outcome": outcome.value,
                "done": done,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )


__all__ = [
    "RetryLoop",
    "RetryOutcome",
    "RetryCapExceeded",
]
