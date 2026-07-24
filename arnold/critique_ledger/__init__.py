"""Critique Ledger — read-only observe domain for critique occurrence,
reconciliation, disposition, briefing, and manifest schemas.

This module is pure and side-effect-free: it defines frozen dataclasses,
enums, hashing helpers, and deterministic validation logic. It never
mutates lifecycle state, queues, Git, providers, or external effects.
"""

from arnold.critique_ledger.schemas import (  # noqa: F401
    # Enums
    Authority,
    CompatibilityProfile,
    ContextMode,
    DispositionFamily,
    EvidenceAvailability,
    FindingDispositionEvent,
    ParseStatus,
    Relationship,
    # Dataclasses
    CritiqueOccurrenceEnvelope,
    DomainBriefingEnvelope,
    FindingReconciliationEvent,
    LedgerRevisionManifest,
    # Helpers
    canonical_hash,
    freeze_for_hashing,
)

from arnold.critique_ledger.semantic_loop import (  # noqa: F401
    # Failure modes
    FailureMode,
    SemanticLoopError,
    # Pure functions
    apply_disposition_events,
    apply_reconciliation_events,
    build_briefing,
    construct_manifest,
    project_gate_input,
    project_reviser_input,
    replay_full,
    validate_occurrence_custody,
)

__all__ = [
    # Enums
    "Authority",
    "CompatibilityProfile",
    "ContextMode",
    "DispositionFamily",
    "EvidenceAvailability",
    "FindingDispositionEvent",
    "ParseStatus",
    "Relationship",
    # Dataclasses
    "CritiqueOccurrenceEnvelope",
    "DomainBriefingEnvelope",
    "FindingReconciliationEvent",
    "LedgerRevisionManifest",
    # Helpers
    "canonical_hash",
    "freeze_for_hashing",
    # Semantic loop
    "FailureMode",
    "SemanticLoopError",
    "apply_disposition_events",
    "apply_reconciliation_events",
    "build_briefing",
    "construct_manifest",
    "project_gate_input",
    "project_reviser_input",
    "replay_full",
    "validate_occurrence_custody",
]
