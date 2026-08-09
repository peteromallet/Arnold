"""Critique Ledger (CL2) — domain schemas, persistence, replay, and import.

This package is partitioned into two disjoint responsibility classes:

**Pure read-only replay (side-effect-free).**
``schemas``, ``semantic_loop``, ``redaction``, and ``projections``
define frozen dataclasses, enums, hashing helpers, and deterministic
projection/replay logic.  ``ProjectionBuilder`` reads the persisted ledger
partition through the *read-only* store API and calls the pure
:func:`semantic_loop.replay_full`; it never mutates the store and never
mutates plan, gate, lifecycle, queue, Git/provider, delivery, or
external-effect state (see ``test_readonly_isolation``).

**The sole side-effecting CL2 write entry point.**
:class:`LedgerPersistenceService` is the *only* CL2 surface that appends CL2
ledger events to the underlying :class:`SqliteAttemptLedgerStore`.  Every CL2
domain record (occurrence / reconciliation / disposition) is carried as
``EXTERNAL_EFFECT_OUTCOME`` payload content tagged by a ``cl2_kind``
discriminator; the unchanged WBC store remains the authority for ordering,
idempotency, and terminal-state enforcement.

**No dual write.**
CL2 ledger events flow exclusively through ``LedgerPersistenceService`` ->
``SqliteAttemptLedgerStore``.  The non-ledger runtime event path
(``FileNativePersistenceBackend`` -> ``NdjsonEventJournal``) is a separate
surface that handles non-ledger runtime events only; it never carries CL2
critique-occurrence/reconciliation/disposition payloads, so there is no window
in which a CL2 record is written to two backends.

**Import (non-authoritative).**
:class:`OneTimeImporter` ingests legacy r5 NDJSON evidence as
``cl2_kind = legacy_historical`` historical context: persisted (all available
legacy evidence preserved) but excluded from the v1 replay partition and never
carrying positive authority.  ``FreshnessTracker`` is a read-only staleness
signal only.
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

# ── Sole CL2 ledger write entry point (side-effecting) ───────────────────────
from arnold.critique_ledger.persistence_service import (  # noqa: F401
    AttemptAlreadyTerminalError,
    LedgerEventContext,
    LedgerEventMapper,
    LedgerPersistenceService,
    LedgerReconciliationResult,
)

# ── Pure read-only replay / projection ───────────────────────────────────────
from arnold.critique_ledger.projections import (  # noqa: F401
    Contribution,
    CumulativeProjection,
    ProjectionBuilder,
    ProjectionResult,
    REPLAY_ADMITTED_KINDS,
    ReplayExclusion,
)

# ── Non-authoritative legacy import + read-only freshness ────────────────────
from arnold.critique_ledger.legacy_import import (  # noqa: F401
    ImportReport,
    OneTimeImporter,
)
from arnold.critique_ledger.freshness import (  # noqa: F401
    FreshnessTracker,
    FreshnessVector,
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
    # Semantic loop (pure)
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
    # Sole CL2 ledger write entry point (side-effecting)
    "AttemptAlreadyTerminalError",
    "LedgerEventContext",
    "LedgerEventMapper",
    "LedgerPersistenceService",
    "LedgerReconciliationResult",
    # Pure read-only replay / projection
    "Contribution",
    "CumulativeProjection",
    "ProjectionBuilder",
    "ProjectionResult",
    "REPLAY_ADMITTED_KINDS",
    "ReplayExclusion",
    # Non-authoritative import + read-only freshness
    "ImportReport",
    "OneTimeImporter",
    "FreshnessTracker",
    "FreshnessVector",
]
