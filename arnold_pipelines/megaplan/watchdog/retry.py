"""Retry-loop state machine for the live watchdog."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
            return RetryOutcome.RESOLVED, True
        if outcome is RetryOutcome.TERMINAL:
            return RetryOutcome.TERMINAL, True
        if self.attempt_count >= self.max_attempts:
            return RetryOutcome.UNRESOLVED, True
        return RetryOutcome.UNRESOLVED, False

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "attempt_count": self.attempt_count,
        }


__all__ = [
    "RetryLoop",
    "RetryOutcome",
    "RetryCapExceeded",
]
