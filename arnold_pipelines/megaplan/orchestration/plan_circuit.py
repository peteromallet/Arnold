"""Plan-level failure circuit breaker — M8A T8.

Normalizes failure signatures across class, task/batch/attempt identity,
blocker digest, provider/ref metadata, and current fence so that repeated
equivalent failures open a circuit before consuming another blind retry.

The circuit is **plan-scoped**: it tracks normalized failure signatures
and opens when the same failure identity repeats.  Unrelated classes or
identities do not collide — only exact normalized equivalence triggers
the circuit.

Contract
--------
:func:`normalize_failure_signature` extracts a frozen
:class:`FailureSignature` from error/context shapes.

:class:`PlanCircuit` records occurrences and returns typed
:class:`CircuitDecision` values.  Callers (e.g. recovery policy) consult
the circuit before authorizing a retry.

Locked decision
~~~~~~~~~~~~~~~
Two equivalent normalized ``worker_budget_exhausted`` occurrences open a
plan circuit before a third blind retry, while exact task/attempt identity
remains preserved.  Budget-exhaustion checkpoints carry the same blocker
digest and fence so that equivalent failures collide correctly.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Final, Literal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CIRCUIT_THRESHOLD: Final[int] = 2
"""Number of equivalent occurrences before the circuit opens.

Two equivalent failures → circuit opens; the third retry is blocked.
"""

CircuitAction = Literal["allow_retry", "open_circuit", "circuit_open"]


# ---------------------------------------------------------------------------
# FailureSignature — normalized failure identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FailureSignature:
    """Normalized identity for a failure occurrence.

    Every field participates in equivalence checks — two signatures are
    equivalent only when all fields match.  This preserves exact task/attempt
    identity while still grouping equivalent failures at the plan level
    through the blocker digest and fence.
    """

    failure_class: str
    """Normalized failure class (e.g. ``worker_budget_exhausted``)."""

    task_id: str | None = None
    """Task identity when the failure is scoped to a specific task."""

    batch_id: str | None = None
    """Batch identity when the failure is scoped to a batch."""

    attempt_id: str | None = None
    """Attempt identity — preserved for exact tracking."""

    blocker_digest: str | None = None
    """SHA-256 digest of the blocker payload that caused the failure.

    Two failures with the same class but different blocker payloads
    (different underlying causes) are *not* equivalent.
    """

    provider: str | None = None
    """Provider identifier (e.g. model provider name)."""

    ref_metadata: str | None = None
    """Source/install revision metadata (e.g. git commit refs)."""

    fence: str | None = None
    """Current grant/authority fence identifier."""

    def to_key(self) -> tuple:
        """Return a hashable, order-stable key for dict lookups."""
        return (
            self.failure_class,
            self.task_id or "",
            self.batch_id or "",
            self.attempt_id or "",
            self.blocker_digest or "",
            self.provider or "",
            self.ref_metadata or "",
            self.fence or "",
        )

    def __hash__(self) -> int:
        return hash(self.to_key())


# ---------------------------------------------------------------------------
# CircuitDecision — typed outcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CircuitDecision:
    """Pure decision returned when recording a failure against the circuit."""

    action: CircuitAction
    """What the circuit decided:

    * ``allow_retry`` — under threshold; retry is permitted.
    * ``open_circuit`` — threshold reached on this occurrence; circuit opens NOW.
    * ``circuit_open`` — circuit was already open; no further retries.
    """

    signature: FailureSignature
    """The normalized signature that was evaluated."""

    occurrence_count: int
    """Total occurrences *after* recording this one (1-indexed)."""

    threshold: int = DEFAULT_CIRCUIT_THRESHOLD

    @property
    def is_open(self) -> bool:
        """True when the circuit is open (either newly or already)."""
        return self.action in ("open_circuit", "circuit_open")

    @property
    def may_retry(self) -> bool:
        """True when a retry is still permitted."""
        return self.action == "allow_retry"


# ---------------------------------------------------------------------------
# PlanCircuit — stateful circuit tracker
# ---------------------------------------------------------------------------


@dataclass
class PlanCircuit:
    """Tracks normalized failure signatures and opens circuits on repetition.

    Usage::

        circuit = PlanCircuit()
        sig = normalize_failure_signature(error, task_id="T7", ...)
        decision = circuit.record_failure(sig)
        if decision.is_open:
            raise CircuitOpenError(...)

    The circuit is plan-scoped — a new :class:`PlanCircuit` instance should
    be created for each plan execution.
    """

    threshold: int = DEFAULT_CIRCUIT_THRESHOLD
    _occurrences: dict[FailureSignature, int] = field(default_factory=dict)
    _open_circuits: set[FailureSignature] = field(default_factory=set)

    def record_failure(self, signature: FailureSignature) -> CircuitDecision:
        """Record a failure occurrence and return the circuit decision.

        If the circuit was already open for this signature, returns
        ``circuit_open`` without incrementing the count (the circuit
        stays open).

        If this occurrence reaches or exceeds the threshold, the circuit
        opens and the action is ``open_circuit``.

        Otherwise the action is ``allow_retry``.
        """
        # If already open, just report it — don't double-count.
        if signature in self._open_circuits:
            count = self._occurrences.get(signature, self.threshold)
            return CircuitDecision(
                action="circuit_open",
                signature=signature,
                occurrence_count=count,
                threshold=self.threshold,
            )

        # Increment occurrence count.
        current = self._occurrences.get(signature, 0) + 1
        self._occurrences[signature] = current

        if current >= self.threshold:
            self._open_circuits.add(signature)
            return CircuitDecision(
                action="open_circuit",
                signature=signature,
                occurrence_count=current,
                threshold=self.threshold,
            )

        return CircuitDecision(
            action="allow_retry",
            signature=signature,
            occurrence_count=current,
            threshold=self.threshold,
        )

    def is_circuit_open(self, signature: FailureSignature) -> bool:
        """Return ``True`` when the circuit is already open for *signature*."""
        return signature in self._open_circuits

    def occurrence_count(self, signature: FailureSignature) -> int:
        """Return the recorded occurrence count for *signature* (0 if unseen)."""
        return self._occurrences.get(signature, 0)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _compute_blocker_digest(blocker: Any) -> str | None:
    """Compute a stable SHA-256 digest for a blocker payload."""
    if blocker is None:
        return None
    if isinstance(blocker, dict):
        payload = _stable_json_dump(blocker)
    elif hasattr(blocker, "to_dict"):
        payload = _stable_json_dump(blocker.to_dict())
    else:
        payload = str(blocker)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_json_dump(obj: Any) -> str:
    """JSON-dump with sorted keys for deterministic hashing."""
    import json

    return json.dumps(obj, sort_keys=True, default=str)


def normalize_failure_signature(
    error: Any,
    *,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    blocker: Any = None,
    provider: str | None = None,
    ref_metadata: str | None = None,
    fence: str | None = None,
    failure_class: str | None = None,
) -> FailureSignature:
    """Build a normalized :class:`FailureSignature` from error/context shapes.

    Parameters
    ----------
    error:
        The error or PhaseResult-like object.  May carry ``exit_kind``,
        ``error_kind``, ``external_error``, ``halt_kind``, etc.
    task_id / batch_id / attempt_id:
        Scope identity carried by the caller.
    blocker:
        A blocker payload (dict, dataclass, or similar) whose content
        determines the blocker digest.
    provider:
        Provider identifier (e.g. model provider).
    ref_metadata:
        Source/install revision metadata.
    fence:
        Current grant/authority fence identifier.
    failure_class:
        Explicit failure class override.  When ``None`` the class is
        derived from the error shape.

    Returns
    -------
    FailureSignature
        A frozen, hashable normalized failure identity.
    """
    # Derive failure_class from error shape when not explicitly provided.
    if failure_class is None:
        failure_class = _derive_failure_class(error)

    blocker_digest = _compute_blocker_digest(blocker)

    # Extract provider from external_error sub-object when available.
    if provider is None:
        _ext = getattr(error, "external_error", None)
        if _ext is not None:
            provider = getattr(_ext, "provider", None) or provider

    return FailureSignature(
        failure_class=failure_class,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=attempt_id,
        blocker_digest=blocker_digest,
        provider=provider,
        ref_metadata=ref_metadata,
        fence=fence,
    )


def _derive_failure_class(error: Any) -> str:
    """Derive a normalized failure class from an error object.

    Priority order:
    1. Explicit ``halt_kind`` attribute (from RecoveryDecision).
    2. ``error_kind`` attribute (from external/provider errors).
    3. ``exit_kind`` attribute (from PhaseResult / ExitKind enum).
    4. ``code`` attribute (from CliError-style errors).
    5. ``__class__.__name__`` as fallback.
    """
    # halt_kind carries the most specific normalized class.
    halt_kind = getattr(error, "halt_kind", None)
    if halt_kind and isinstance(halt_kind, str) and halt_kind not in ("", "unclassified"):
        return halt_kind

    # error_kind from external/provider errors.
    error_kind = getattr(error, "error_kind", None)
    if error_kind and isinstance(error_kind, str) and error_kind not in ("", "unclassified"):
        return error_kind

    # exit_kind from PhaseResult / ExitKind.
    exit_kind = getattr(error, "exit_kind", None)
    if exit_kind is not None:
        ek_str = exit_kind.value if hasattr(exit_kind, "value") else str(exit_kind)
        if ek_str and ek_str != "unclassified":
            if ek_str == "context_exhausted":
                return "context_exhausted"
            if ek_str == "external_error":
                # Try to get more specific from external_error sub-object.
                _ext = getattr(error, "external_error", None)
                if _ext is not None:
                    ek = getattr(_ext, "error_kind", None)
                    if ek and isinstance(ek, str) and ek not in ("", "unclassified"):
                        return ek
                return "external_error"
            if ek_str == "blocked_by_quality":
                return "blocked_by_quality"
            if ek_str == "blocked_by_prereq":
                return "blocked_by_prereq"
            if ek_str == "timeout":
                return "timeout"
            if ek_str == "internal_error":
                return "internal_error"
            if ek_str == "malformed_model_output":
                return "malformed_model_output"
            return ek_str

    # CliError-style code.
    code = getattr(error, "code", None)
    if code and isinstance(code, str) and code not in ("", "unclassified"):
        return code

    # Fallback: class name — but only for meaningful exception/error classes.
    # Generic containers (SimpleNamespace, object, dict) fall through to "unclassified".
    cls = type(error)
    cls_name = cls.__name__
    if cls_name not in ("", "object", "SimpleNamespace", "dict", "list", "tuple"):
        return cls_name

    return "unclassified"


__all__ = [
    "CircuitAction",
    "CircuitDecision",
    "DEFAULT_CIRCUIT_THRESHOLD",
    "FailureSignature",
    "PlanCircuit",
    "normalize_failure_signature",
]
