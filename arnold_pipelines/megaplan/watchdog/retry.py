"""Retry-loop state machine for the live watchdog.

M9: Retry occurrences are classified by exact identity tuples
(session, plan, revision, attempt, failure_signature, fence) and
emit drift + evidence IDs on mismatch.  A stale occurrence cannot
bind to a different session or same-basename run.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RetryOutcome(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    TERMINAL = "terminal"


class RetryCapExceeded(Exception):
    """Raised when attempting a fourth retry."""


# ── M9: exact retry identity ──────────────────────────────────────────────


@dataclass(frozen=True)
class RetryIdentity:
    """Exact identity tuple for retry attempt classification.

    Each field narrows the binding so a retry cannot accidentally match
    a different session, plan, revision, or run.  A stale T7 occurrence
    cannot bind to T12 or a same-basename run.
    """

    session: str = ""
    """Canonical session name."""

    plan: str = ""
    """Plan name being retried."""

    plan_dir: str = ""
    """Absolute path to the plan directory."""

    revision: str = ""
    """Plan revision hash at the time the original attempt was admitted."""

    attempt: int = 0
    """Retry attempt number (1-indexed, where 1 = first retry after original failure)."""

    failure_signature: str = ""
    """Content hash of the failure that triggered this retry attempt."""

    fence: str = ""
    """Run Authority fence token at the time this retry was admitted."""

    def identity_digest(self) -> str:
        """Content-addressed evidence ID for this retry identity."""
        raw = (
            f"{self.session}\x00{self.plan}\x00{self.plan_dir}\x00"
            f"{self.revision}\x00{self.attempt}\x00"
            f"{self.failure_signature}\x00{self.fence}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session,
            "plan": self.plan,
            "plan_dir": self.plan_dir,
            "revision": self.revision,
            "attempt": self.attempt,
            "failure_signature": self.failure_signature,
            "fence": self.fence,
            "identity_digest": f"sha256:{self.identity_digest()}",
        }

    @classmethod
    def from_incident(
        cls,
        *,
        session: str = "",
        plan: str = "",
        plan_dir: str = "",
        revision: str = "",
        attempt: int = 0,
        failure_signature: str = "",
        fence: str = "",
    ) -> "RetryIdentity":
        return cls(
            session=session,
            plan=plan,
            plan_dir=plan_dir,
            revision=revision,
            attempt=attempt,
            failure_signature=failure_signature,
            fence=fence,
        )


@dataclass(frozen=True)
class RetryDrift:
    """Drift evidence when a retry identity does not match expectations.

    Emitted when the current binding target (session/plan/revision/fence)
    differs from the retry's recorded identity.  Drift is diagnostic
    evidence — it never authorizes repair or escalation.
    """

    field: str
    expected: str
    observed: str
    evidence_id: str = ""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raw = f"{self.field}\x00{self.expected}\x00{self.observed}"
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            object.__setattr__(self, "evidence_id", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "expected": self.expected,
            "observed": self.observed,
            "evidence_id": self.evidence_id,
            "_non_authoritative": self._non_authoritative,
        }


@dataclass
class RetryLoop:
    """Tracks up to three attempts per incident.

    M9: Each retry carries exact identity classification.  Drift is
    detected when the retry identity does not match the expected binding.

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

    # ── M9: exact identity fields ──
    identity: RetryIdentity = field(default_factory=RetryIdentity)
    """Exact identity tuple for this retry loop."""

    drift: tuple[RetryDrift, ...] = ()
    """Drift evidence when identity fields mismatch expectations."""

    evidence_id: str = ""
    """Content-addressed evidence ID for the entire retry loop."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raw = (
                f"{self.max_attempts}\x00{self.attempt_count}\x00"
                f"{self.identity.identity_digest()}"
            )
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            self.evidence_id = f"sha256:{digest}"

    def set_identity(
        self,
        identity: RetryIdentity,
        *,
        expected: RetryIdentity | None = None,
    ) -> tuple[RetryDrift, ...]:
        """Set the retry identity and detect drift against expected identity.

        Returns drift evidence when the identity does not match expectations.
        """
        self.identity = identity
        if expected is not None:
            self.drift = _detect_retry_drift(identity, expected)
        else:
            self.drift = ()
        return self.drift

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
            "identity": self.identity.to_dict(),
            "drift": [d.to_dict() for d in self.drift] if self.drift else [],
            "evidence_id": self.evidence_id,
            "_non_authoritative": self._non_authoritative,
        }


def _detect_retry_drift(
    observed: RetryIdentity,
    expected: RetryIdentity,
) -> tuple[RetryDrift, ...]:
    """Compare observed vs expected retry identity and emit drift on mismatch."""
    drift: list[RetryDrift] = []
    fields = [
        ("session", observed.session, expected.session),
        ("plan", observed.plan, expected.plan),
        ("plan_dir", observed.plan_dir, expected.plan_dir),
        ("revision", observed.revision, expected.revision),
        ("attempt", str(observed.attempt) if observed.attempt else "",
         str(expected.attempt) if expected.attempt else ""),
        ("failure_signature", observed.failure_signature, expected.failure_signature),
        ("fence", observed.fence, expected.fence),
    ]
    for field, obs_val, exp_val in fields:
        if not obs_val and not exp_val:
            continue
        if obs_val != exp_val:
            drift.append(RetryDrift(
                field=field,
                expected=exp_val or "",
                observed=obs_val or "",
            ))
    return tuple(drift)


def detect_retry_identity_drift(
    observed: RetryIdentity,
    expected: RetryIdentity,
) -> tuple[RetryDrift, ...]:
    """Public entry point for retry identity drift detection.

    Returns drift evidence for every mismatched identity field.
    """
    return _detect_retry_drift(observed, expected)


__all__ = [
    "RetryLoop",
    "RetryOutcome",
    "RetryCapExceeded",
    "RetryIdentity",
    "RetryDrift",
    "detect_retry_identity_drift",
]
