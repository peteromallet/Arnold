"""Read-only projection/replay over the CL2 persistence ledger.

``ProjectionBuilder`` reconstructs the three CL1 domain lists from persisted
``EXTERNAL_EFFECT_OUTCOME`` events, applying the three conjunctive admission
conditions *before* reconstruction (exclude-then-reconstruct order), then calls
:func:`semantic_loop.replay_full` read-only.  It never mutates the store and
never fabricates custody evidence: ``wbc_receipt_chain`` is caller-supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from arnold.critique_ledger.persistence_service import (
    CL2_KIND_DISPOSITION,
    CL2_KIND_OCCURRENCE,
    CL2_KIND_RECONCILIATION,
)
from arnold.critique_ledger.schemas import (
    SCHEMA_VERSION,
    CritiqueOccurrenceEnvelope,
    DomainBriefingEnvelope,
    FindingDispositionEvent,
    FindingReconciliationEvent,
    LedgerRevisionManifest,
    canonical_hash,
)
from arnold.critique_ledger.semantic_loop import replay_full
from arnold.adapters.ledger_store_adapter import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AttemptEventType,
    LedgerEvent,
)

# ── Discriminators ──────────────────────────────────────────────────────────

#: Reserved payload discriminator for legacy r5 imports (OneTimeImporter).
#: Distinct from the replay-eligible kinds; excluded from replay by condition (i).
CL2_KIND_LEGACY_HISTORICAL = "legacy_historical"

#: The replay-eligible payload kinds — the condition-(i) admission set.
REPLAY_ADMITTED_KINDS = frozenset(
    {
        CL2_KIND_OCCURRENCE,
        CL2_KIND_RECONCILIATION,
        CL2_KIND_DISPOSITION,
    }
)

# ── Per-contribution authority scope ────────────────────────────────────────

AUTHORITY_SCOPE_AUTHORITATIVE = "authoritative"
AUTHORITY_SCOPE_NON_AUTHORITATIVE = "non_authoritative"

# ── Per-attempt authority rollup ────────────────────────────────────────────

ATTEMPT_AUTHORITY_MIXED = "mixed_authoritative"
ATTEMPT_AUTHORITY_AUTHORITATIVE = "authoritative"
ATTEMPT_AUTHORITY_NON_AUTHORITATIVE = "non_authoritative"
ATTEMPT_AUTHORITY_EMPTY = "empty"

# ── Replay-exclusion reasons ────────────────────────────────────────────────

EXCLUSION_REASON_LEGACY_DERIVED = "legacy_derived"
EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"

# Maps a replay-eligible cl2_kind to its reconstruction class + target list.
_KIND_RECONSTRUCTION = {
    CL2_KIND_OCCURRENCE: CritiqueOccurrenceEnvelope,
    CL2_KIND_RECONCILIATION: FindingReconciliationEvent,
    CL2_KIND_DISPOSITION: FindingDispositionEvent,
}


@dataclass(frozen=True)
class ReplayExclusion:
    """One persisted OUTCOME event excluded from the replay partition.

    Evidence only — never grants authority.  The ``reason`` discriminator is
    either :data:`EXCLUSION_REASON_LEGACY_DERIVED` or
    :data:`EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH`.
    """

    sequence: int
    cl2_kind: str
    reason: str


@dataclass(frozen=True)
class ProjectionResult:
    """The read-only replay projection for one attempt stream.

    Carries the three reconstructed CL1 domain lists (admitted partition), the
    deterministic ``manifest``/``briefing`` and their ``canonical_hash`` digests
    (stable across replays = byte-equivalence), the per-event ``replay_excluded``
    diagnostics, and the full :func:`replay_full` return dict for audit.
    """

    attempt_id: str
    occurrences: list[CritiqueOccurrenceEnvelope]
    reconciliations: list[FindingReconciliationEvent]
    dispositions: list[FindingDispositionEvent]
    manifest: LedgerRevisionManifest
    briefing: DomainBriefingEnvelope
    manifest_hash: str
    briefing_hash: str
    replay_excluded: list[ReplayExclusion]
    replay_result: dict[str, Any]


@dataclass(frozen=True)
class Contribution:
    """One persisted OUTCOME payload tagged with its per-contribution scope.

    Authority is per-contribution (per-OUTCOME payload), NOT per-attempt: an
    attempt stream may legitimately contain BOTH v1 and legacy_historical
    contributions under one ``attempt_id``.
    """

    attempt_id: str
    sequence: int
    cl2_kind: str
    authority_scope: Literal[
        AUTHORITY_SCOPE_AUTHORITATIVE, AUTHORITY_SCOPE_NON_AUTHORITATIVE
    ]


@dataclass(frozen=True)
class CumulativeProjection:
    """Aggregate of per-contribution authority across one or more attempts.

    ``contributions`` has one entry per persisted OUTCOME payload;
    ``attempt_authority_summary`` is the per-attempt rollup keyed by attempt_id.
    """

    contributions: list[Contribution]
    attempt_authority_summary: dict[str, str]


def _is_legacy_payload(payload: Any) -> bool:
    """True when a payload is legacy-derived (discriminator or metadata marker)."""
    if not isinstance(payload, dict):
        return False
    if payload.get("cl2_kind") == CL2_KIND_LEGACY_HISTORICAL:
        return True
    envelope = payload.get("envelope")
    if isinstance(envelope, dict):
        return envelope.get("metadata", {}).get("derived_from_legacy") is True
    return False


def _admission(payload: Any) -> tuple[bool, str | None]:
    """Evaluate the three conjunctive admission conditions (exclude-then-reconstruct).

    Returns ``(admitted, reason)``.  ``admitted`` is True only when ALL three
    conditions hold; otherwise ``reason`` is the exclusion discriminator with
    ``legacy_derived`` taking precedence over ``schema_version_mismatch``.  The
    filter runs before ``from_dict`` so excluded records never raise.
    """
    if not isinstance(payload, dict):
        return False, EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH

    cl2_kind = payload.get("cl2_kind")

    # Condition (i): cl2_kind in the admitted set.  A legacy discriminator (or
    # any non-admitted kind) is excluded here; legacy-derived records carry the
    # legacy reason.
    if cl2_kind not in REPLAY_ADMITTED_KINDS:
        if cl2_kind == CL2_KIND_LEGACY_HISTORICAL or _is_legacy_payload(payload):
            return False, EXCLUSION_REASON_LEGACY_DERIVED
        return False, EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH

    envelope = payload.get("envelope")
    if not isinstance(envelope, dict):
        return False, EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH

    # Condition (iii): derived_from_legacy marker (defense-in-depth).  Checked
    # before (ii) so the reason reads ``legacy_derived``.
    if envelope.get("metadata", {}).get("derived_from_legacy") is True:
        return False, EXCLUSION_REASON_LEGACY_DERIVED

    # Condition (ii): schema_version must be exactly cl.schema.v1.
    if envelope.get("schema_version") != SCHEMA_VERSION:
        return False, EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH

    return True, None


def _authority_scope_for(payload: Any) -> str:
    """Per-contribution authority scope: authoritative iff all three conditions hold."""
    admitted, _ = _admission(payload)
    return (
        AUTHORITY_SCOPE_AUTHORITATIVE
        if admitted
        else AUTHORITY_SCOPE_NON_AUTHORITATIVE
    )


def _rollup_authority(scopes: list[str]) -> str:
    """Per-attempt rollup from the list of per-contribution scopes."""
    if not scopes:
        return ATTEMPT_AUTHORITY_EMPTY
    has_auth = any(s == AUTHORITY_SCOPE_AUTHORITATIVE for s in scopes)
    has_nonauth = any(s == AUTHORITY_SCOPE_NON_AUTHORITATIVE for s in scopes)
    if has_auth and has_nonauth:
        return ATTEMPT_AUTHORITY_MIXED
    if has_auth:
        return ATTEMPT_AUTHORITY_AUTHORITATIVE
    return ATTEMPT_AUTHORITY_NON_AUTHORITATIVE


class ProjectionBuilder:
    """Read-only projection/replay surface over ``SqliteAttemptLedgerStore``."""

    def __init__(self, store: SqliteAttemptLedgerStore) -> None:
        self._store = store

    # ── replay ───────────────────────────────────────────────────────────

    def replay(
        self,
        attempt_id: str,
        *,
        wbc_receipt_chain: dict[str, Any] | None = None,
    ) -> ProjectionResult:
        """Reconstruct the CL1 domain lists and replay read-only.

        Filters the replay partition with the three conjunctive conditions
        (exclude-then-reconstruct), reconstructs the three ``replay_full``
        input lists, and calls :func:`semantic_loop.replay_full`.  No model
        calls, no external effects, no store mutations.  ``wbc_receipt_chain``
        is caller-supplied custody evidence (never fabricated).
        """
        events = self._store.read_events(attempt_id)

        occurrences: list[CritiqueOccurrenceEnvelope] = []
        reconciliations: list[FindingReconciliationEvent] = []
        dispositions: list[FindingDispositionEvent] = []
        excluded: list[ReplayExclusion] = []

        for event in events:
            if event.event_type != AttemptEventType.EXTERNAL_EFFECT_OUTCOME:
                # STARTED / INTENT / terminal are lifecycle context, not
                # replay inputs — never counted in replay_excluded.
                continue
            payload = event.payload
            admitted, reason = _admission(payload)
            if not admitted:
                excluded.append(
                    ReplayExclusion(
                        sequence=event.sequence,
                        cl2_kind=(
                            payload.get("cl2_kind")
                            if isinstance(payload, dict)
                            else ""
                        ),
                        reason=reason or EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH,
                    )
                )
                continue

            cl2_kind = payload["cl2_kind"]
            record_cls = _KIND_RECONSTRUCTION[cl2_kind]
            record = record_cls.from_dict(payload["envelope"])
            if cl2_kind == CL2_KIND_OCCURRENCE:
                occurrences.append(record)
            elif cl2_kind == CL2_KIND_RECONCILIATION:
                reconciliations.append(record)
            else:
                dispositions.append(record)

        replay_result = replay_full(
            occurrences,
            reconciliations,
            dispositions,
            wbc_receipt_chain=wbc_receipt_chain,
        )
        manifest = replay_result["manifest"]
        briefing = replay_result["briefing"]

        return ProjectionResult(
            attempt_id=attempt_id,
            occurrences=occurrences,
            reconciliations=reconciliations,
            dispositions=dispositions,
            manifest=manifest,
            briefing=briefing,
            manifest_hash=canonical_hash(manifest),
            briefing_hash=canonical_hash(briefing),
            replay_excluded=excluded,
            replay_result=replay_result,
        )

    # ── legacy context ───────────────────────────────────────────────────

    def read_legacy_context(self, attempt_id: str) -> list[LedgerEvent]:
        """Return all ``cl2_kind == legacy_historical`` events as full records.

        Queryable for audit/historical purposes but NEVER routed through
        :func:`replay_full` (excluded by the replay filter).
        """
        events = self._store.read_events(attempt_id)
        legacy: list[LedgerEvent] = []
        for event in events:
            if event.event_type != AttemptEventType.EXTERNAL_EFFECT_OUTCOME:
                continue
            payload = event.payload
            if (
                isinstance(payload, dict)
                and payload.get("cl2_kind") == CL2_KIND_LEGACY_HISTORICAL
            ):
                legacy.append(event)
        return legacy

    # ── byte-equivalence ─────────────────────────────────────────────────

    def verify_byte_equivalence(
        self,
        attempt_id: str,
        expected_manifest_hash: str,
        expected_briefing_hash: str,
        *,
        wbc_receipt_chain: dict[str, Any] | None = None,
    ) -> bool:
        """True iff replaying yields the expected manifest/briefing hashes.

        Byte-equivalence: replaying the same persisted partition is
        deterministic, so the hashes are identical across replays.
        """
        result = self.replay(
            attempt_id, wbc_receipt_chain=wbc_receipt_chain
        )
        return (
            result.manifest_hash == expected_manifest_hash
            and result.briefing_hash == expected_briefing_hash
        )

    # ── cumulative authority ─────────────────────────────────────────────

    def build_cumulative(
        self, attempt_ids: list[str]
    ) -> CumulativeProjection:
        """Aggregate per-contribution authority across attempts.

        Each persisted OUTCOME payload is one :class:`Contribution` with its own
        ``authority_scope``.  ``attempt_authority_summary`` rolls up per attempt:
        ``mixed_authoritative`` (both v1 + legacy), ``authoritative`` / non-,
        or ``empty``.
        """
        contributions: list[Contribution] = []
        summary: dict[str, str] = {}
        for attempt_id in attempt_ids:
            events = self._store.read_events(attempt_id)
            scopes: list[str] = []
            for event in events:
                if event.event_type != AttemptEventType.EXTERNAL_EFFECT_OUTCOME:
                    continue
                scope = _authority_scope_for(event.payload)
                scopes.append(scope)
                contributions.append(
                    Contribution(
                        attempt_id=attempt_id,
                        sequence=event.sequence,
                        cl2_kind=(
                            event.payload.get("cl2_kind")
                            if isinstance(event.payload, dict)
                            else ""
                        ),
                        authority_scope=scope,  # type: ignore[arg-type]
                    )
                )
            summary[attempt_id] = _rollup_authority(scopes)
        return CumulativeProjection(
            contributions=contributions,
            attempt_authority_summary=summary,
        )


__all__ = [
    "AUTHORITY_SCOPE_AUTHORITATIVE",
    "AUTHORITY_SCOPE_NON_AUTHORITATIVE",
    "ATTEMPT_AUTHORITY_AUTHORITATIVE",
    "ATTEMPT_AUTHORITY_EMPTY",
    "ATTEMPT_AUTHORITY_MIXED",
    "ATTEMPT_AUTHORITY_NON_AUTHORITATIVE",
    "CL2_KIND_LEGACY_HISTORICAL",
    "Contribution",
    "CumulativeProjection",
    "EXCLUSION_REASON_LEGACY_DERIVED",
    "EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH",
    "ProjectionBuilder",
    "ProjectionResult",
    "REPLAY_ADMITTED_KINDS",
    "ReplayExclusion",
]
