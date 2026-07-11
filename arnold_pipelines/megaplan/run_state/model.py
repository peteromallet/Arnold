"""Canonical run-state model types for the pure resolver.

Defines the frozen :class:`CanonicalRunState` dataclass, the
:class:`CanonicalState` and :class:`TypedHumanGate` enums, and stable
serialization helpers.  This module MUST NOT import from watchdog, status,
repair-loop, or any other consumer — it is the shared contract layer consumed
by the resolver and all downstream observers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Mapping, Sequence


class CanonicalState(Enum):
    """Canonical run-state classifications determined by the resolver.

    These replace the legacy terminal-label projection (``blocked``, ``failed``,
    ``manual_review``, etc.) that multiple layers independently derived from
    overlapping artifacts.  Every consumer should use this enum instead of
    classifying raw evidence on its own.
    """

    RUNNING = auto()
    REPAIRING = auto()
    RETRYABLE_EXECUTION_BLOCK = auto()
    REAL_IMPLEMENTATION_BLOCK = auto()
    HUMAN_ACTION_REQUIRED = auto()
    COMPLETED = auto()
    STALE_DERIVED_STATE = auto()
    BROKEN_STATE_MACHINE = auto()
    UNKNOWN = auto()


class TypedHumanGate(Enum):
    """Specific categories of human-action-required gates.

    Only these explicit gate categories cause the resolver to classify a run
    as :attr:`CanonicalState.HUMAN_ACTION_REQUIRED`.  Machine-actionable
    implementation blockers (route-binding gaps, fixture refreshes, stale
    assertions, budget exhaustion) are *never* human gates.
    """

    EXPLICIT_APPROVAL = auto()       # User explicitly approved or rejected a gate.
    CREDENTIAL_ACCOUNT = auto()      # Missing external credential or account.
    QUOTA = auto()                   # Rate-limit or resource quota exhausted.
    VERIFICATION = auto()            # Human verification required (policy).
    POLICY = auto()                  # Policy decision pending human input.
    USER_ACTION = auto()             # Explicit user-action record pending.
    DESTRUCTIVE_ACTION = auto()      # Explicit consent for a destructive action.
    PRODUCT_DECISION = auto()        # Genuine product/requirements choice.


@dataclass(frozen=True)
class CanonicalRunState:
    """Frozen canonical run-state result produced by the resolver.

    This is the authoritative output that all consumers (watchdog, status,
    repair-loop, chain, auto, progress-auditor) should use instead of
    independently classifying raw artifacts.

    Fields
    ------
    canonical_state:
        The resolver's single classification for this run.
    confidence:
        ``"high"``, ``"medium"``, or ``"low"``.
    source_of_truth:
        Ordered list of evidence sources the resolver considered authoritative.
    stale_sources:
        Evidence sources the resolver found stale or contradictory.
    human_required:
        ``True`` only when *canonical_state* is ``HUMAN_ACTION_REQUIRED``.
    human_gate:
        The specific typed gate when *human_required* is ``True``, else ``None``.
    repairable:
        ``True`` when the repair loop should attempt automated repair.
    running:
        ``True`` when the run is actively executing (live worker).
    next_action:
        Suggested next action for the repair loop or operator.
    reason:
        Human-readable rationale for the classification.
    evidence:
        Supporting evidence items (each a dict with at least ``kind``,
        ``path``, and ``summary``).
    """

    canonical_state: CanonicalState
    confidence: str = "medium"
    source_of_truth: Sequence[str] = field(default_factory=tuple)
    stale_sources: Sequence[str] = field(default_factory=tuple)
    human_required: bool = False
    human_gate: TypedHumanGate | None = None
    repairable: bool = False
    running: bool = False
    next_action: str = ""
    reason: str = ""
    evidence: Sequence[Mapping[str, Any]] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Normalize mutable sequences to immutable tuples.

        The dataclass is frozen so we must use ``object.__setattr__``.
        """
        object.__setattr__(self, "source_of_truth", tuple(self.source_of_truth))
        object.__setattr__(self, "stale_sources", tuple(self.stale_sources))
        object.__setattr__(self, "evidence", tuple(self.evidence))

    # ------------------------------------------------------------------
    # stable serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a stable dict suitable for JSON persistence.

        Enum members are stored by name so the output survives re-ordering
        of enum definitions.  All sequences are materialized as lists.
        """
        return {
            "canonical_state": self.canonical_state.name,
            "confidence": self.confidence,
            "source_of_truth": list(self.source_of_truth),
            "stale_sources": list(self.stale_sources),
            "human_required": self.human_required,
            "human_gate": self.human_gate.name if self.human_gate is not None else None,
            "repairable": self.repairable,
            "running": self.running,
            "next_action": self.next_action,
            "reason": self.reason,
            "evidence": list(self.evidence),
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize to a stable JSON string.

        Keys are sorted so identical payloads produce identical strings.
        """
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CanonicalRunState:
        """Deserialize from a dict previously produced by :meth:`to_dict`."""
        human_gate_raw = data.get("human_gate")
        return cls(
            canonical_state=CanonicalState[data["canonical_state"]],
            confidence=data.get("confidence", "medium"),
            source_of_truth=tuple(data.get("source_of_truth", ())),
            stale_sources=tuple(data.get("stale_sources", ())),
            human_required=data.get("human_required", False),
            human_gate=TypedHumanGate[human_gate_raw] if human_gate_raw is not None else None,
            repairable=data.get("repairable", False),
            running=data.get("running", False),
            next_action=data.get("next_action", ""),
            reason=data.get("reason", ""),
            evidence=tuple(data.get("evidence", ())),
        )

    @classmethod
    def from_json(cls, text: str) -> CanonicalRunState:
        """Deserialize from a JSON string produced by :meth:`to_json`."""
        return cls.from_dict(json.loads(text))
