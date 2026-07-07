"""Canonical run-state model package.

Exports
-------
CanonicalState
    Enum of canonical resolver classifications (RUNNING, REPAIRING, …).
TypedHumanGate
    Enum of specific human-gate categories (EXPLICIT_APPROVAL, …).
CanonicalRunState
    Frozen dataclass holding the resolver's authoritative output.
NormalizedEvidence
    Frozen dataclass with structured accessors over current-target evidence
    and an optional BlockerVerdict.
normalize_evidence
    Factory function that constructs a NormalizedEvidence from raw evidence.
resolve_run_state
    Pure ordered classifier: maps evidence + optional BlockerVerdict to a
    single CanonicalRunState applying the North Star evidence priority.

This package is the shared classification contract. It MUST NOT import from
watchdog, status, repair-loop, feature_flags, or any other consumer.
"""

from arnold_pipelines.megaplan.run_state.evidence import (
    NormalizedEvidence,
    normalize_evidence,
)
from arnold_pipelines.megaplan.run_state.model import (
    CanonicalRunState,
    CanonicalState,
    TypedHumanGate,
)
from arnold_pipelines.megaplan.run_state.resolver import resolve_run_state

__all__ = [
    "CanonicalRunState",
    "CanonicalState",
    "NormalizedEvidence",
    "TypedHumanGate",
    "normalize_evidence",
    "resolve_run_state",
]
