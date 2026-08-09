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

M9 dimensions
-------------
NormalizedFailureToken, FailureTokenKind
    Canonical failure-token normalization with preserved identity.
WbcEvidenceRef
    Lightweight reference to a WBC query envelope.
RunAuthorityRef
    Reference to a Run Authority grant and optional fence.
CustodyRef
    Reference to a Custody lease and/or epoch.
UncertaintyLevel
    Enum capturing resolver uncertainty (LOW, MEDIUM, HIGH).

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
    CustodyRef,
    FailureTokenKind,
    NormalizedFailureToken,
    RunAuthorityRef,
    TypedHumanGate,
    UncertaintyLevel,
    WbcEvidenceRef,
)
from arnold_pipelines.megaplan.run_state.resolver import resolve_run_state
from arnold_pipelines.megaplan.run_state.decision_contract import (
    is_machine_repairable_failure_kind,
    typed_human_gate,
)

__all__ = [
    "CanonicalRunState",
    "CanonicalState",
    "CustodyRef",
    "FailureTokenKind",
    "NormalizedEvidence",
    "NormalizedFailureToken",
    "RunAuthorityRef",
    "TypedHumanGate",
    "UncertaintyLevel",
    "WbcEvidenceRef",
    "normalize_evidence",
    "resolve_run_state",
    "is_machine_repairable_failure_kind",
    "typed_human_gate",
]
