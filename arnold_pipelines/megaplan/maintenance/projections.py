"""Independent, deterministic Maintenance projections (M2, T13).

This module materializes three *independent* projections over the strict
:class:`~arnold_pipelines.megaplan.maintenance.events.MaintenanceEvent` stream:

* :class:`CustodyProjection` — ``operational_custody``: the active
  custody/lease/fence state for a detection occurrence (``custody_refs`` +
  ``fence_refs`` + occurrence-scoped budget + recurrence chain).
* :class:`VerificationProjection` — ``verification``: resolution-proof and
  audit-report state (``resolution_proof`` from detection events, ``verdict`` /
  ``report_type`` from audit reports).
* :class:`EfficiencyProjection` — ``efficiency_analysis``: censoring,
  denominators, unknowns, coverage, bucket counts, classifier version, and the
  half-open reporting window / watermark.

Each projection advances independently with its own monotonic ``sequence``,
source ``cursor``, chained ``source_digest``, canonical ``output_digest``,
``lag`` (distance behind the global source cursor), and ``freshness``
(``fresh``/``stale``/``unknown`` derived from the event's lateness against its
watermark).  Replaying the same event order byte-for-byte reproduces the same
sequences and digests.

Locked semantics (SD2 + the fail-closed correction rule):

* **Occurrence dedupe vs. verified recurrence.**  ``occurrence_id`` is the
  sole idempotency scope.  An exact duplicate (same occurrence + same
  canonical digest) is *deduped*: no projection advances, no budget is
  consumed, and no correction is appended.  A *verified recurrence* always
  carries a fresh ``occurrence_id`` (enforced by the event contract), so it is
  a distinct, causally linked occurrence with a fresh occurrence-scoped budget;
  its root-cause cluster grouping is preserved.
* **Efficiency isolation.**  ``efficiency_analysis`` events are routed only to
  the efficiency projection.  They can never alter the custody or verification
  projections (the reducers return the prior state unchanged for any
  non-relevant event kind).
* **Half-open watermarked windows.**  Latency/freshness is taken from the
  event's already-validated ``lateness`` (``classify_lateness(event_time,
  watermark)`` — half-open windows are enforced by the event contract).  The
  efficiency projection retains the half-open window ``[start, end)`` and the
  watermark so windowing is digest-visible and never inferred.
* **Append-only late-evidence corrections.**  A *late* event never rewrites a
  prior projection result.  When there is a prior result to amend, the reducer
  appends a :class:`CorrectionRecord` (``kind="late_evidence"``) that links the
  new sequence to the corrected sequence and preserves the corrected result's
  ``output_digest``.  The prior result is immutable.

No module here performs any ledger, plan, or chain mutation: projections are
pure, deterministic reducers over strict events.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from arnold_pipelines.megaplan.maintenance.events import (
    EventKind,
    MaintenanceEvent,
    OccurrenceBudget,
    ProjectionCoordinates,
    RecurrenceLink,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    Lateness,
    MaintenanceCodecError,
    OwnerRef,
    canonical_digest,
    canonical_json,
    strict_loads,
)

# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class ProjectionName(str, Enum):
    """The three independent Maintenance projections (closed vocabulary)."""

    OPERATIONAL_CUSTODY = "operational_custody"
    VERIFICATION = "verification"
    EFFICIENCY_ANALYSIS = "efficiency_analysis"


class ProjectionFreshness(str, Enum):
    """Freshness of a projection relative to the watermark it has consumed."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class CorrectionKind(str, Enum):
    """Closed correction vocabulary (append-only; never rewrites a result)."""

    LATE_EVIDENCE = "late_evidence"


class ApplyDisposition(str, Enum):
    """What an :meth:`ProjectionEngine.apply` call did with one event."""

    APPLIED = "applied"
    DEDUPED = "deduped"


class ProjectionConflictError(ValueError):
    """Raised when a divergent duplicate reuses an occurrence idempotency key.

    The conflicting event is NOT applied and no projection advances.  This
    mirrors the ledger's :class:`MaintenanceEventConflict` fail-closed rule so
    projections can never silently merge divergent truth for one occurrence.
    """


# ---------------------------------------------------------------------------
# Append-only correction record
# ---------------------------------------------------------------------------


class CorrectionRecord(BaseModel):
    """One append-only correction (never rewrites a prior projection result).

    ``prior_output_digest`` preserves the exact canonical digest of the result
    being corrected, so a consumer can prove the prior result was *linked to*,
    not overwritten.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: CorrectionKind
    #: Projection sequence assigned to the correcting result.
    sequence: int
    #: Sequence of the prior result this correction amends.
    corrected_sequence: int
    #: Canonical output digest of the corrected (prior) result.
    prior_output_digest: str | None
    event_id: str
    occurrence_id: str
    reason: str | None = None

    @field_validator("sequence", "corrected_sequence")
    @classmethod
    def _validate_sequences(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"correction sequence must be >= 0, got {value}")
        return value

    @field_validator("prior_output_digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(
                "prior_output_digest must be a 64-character lowercase sha256 hex digest"
            )
        return value


# ---------------------------------------------------------------------------
# Shared projection state machinery
# ---------------------------------------------------------------------------

#: Metadata fields excluded from ``output_digest`` (the digest is over the
#: projection's *materialized output*, never over its own bookkeeping).
_METADATA_FIELDS: frozenset[str] = frozenset(
    {"sequence", "cursor", "source_digest", "output_digest", "lag", "freshness"}
)


class _ProjectionState(BaseModel):
    """Common metadata for an independently advancing projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = 0
    #: Last source cursor (ledger sequence) consumed by this projection.
    cursor: int = 0
    #: Order-sensitive chained digest of the source events consumed so far.
    source_digest: str | None = None
    #: Canonical digest of this projection's materialized output.
    output_digest: str | None = None
    #: Distance behind the global source cursor (>= 0).
    lag: int = 0
    freshness: ProjectionFreshness = ProjectionFreshness.UNKNOWN

    @field_validator("sequence", "cursor", "lag")
    @classmethod
    def _validate_nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"projection sequence/cursor/lag must be >= 0, got {value}")
        return value

    @field_validator("source_digest", "output_digest")
    @classmethod
    def _validate_digests(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(
                "projection digest must be a 64-character lowercase sha256 hex digest"
            )
        return value

    @property
    def coordinates(self) -> ProjectionCoordinates:
        """Expose this projection's advance as :class:`ProjectionCoordinates`."""
        return ProjectionCoordinates(
            projection=str(getattr(self, "projection", "")),
            sequence=self.sequence,
            cursor=f"seq:{self.cursor}" if self.cursor else None,
            source_digest=self.source_digest,
            output_digest=self.output_digest,
        )


# ---------------------------------------------------------------------------
# The three independent projection states
# ---------------------------------------------------------------------------


class CustodyProjection(_ProjectionState):
    """``operational_custody``: active custody/lease/fence state.

    Fed by ``detection`` events only.  Retains the active occurrence, its
    classifier version, root-cause cluster grouping, custody/fence references,
    occurrence-scoped budget, and any verified recurrence links.
    """

    projection: Literal["operational_custody"] = "operational_custody"

    occurrence_id: str | None = None
    event_id: str | None = None
    classifier_version: str | None = None
    cluster_signature: str | None = None
    cluster_id: str | None = None
    custody_refs: tuple[OwnerRef, ...] = ()
    fence_refs: tuple[OwnerRef, ...] = ()
    budget: OccurrenceBudget | None = None
    recurrences: tuple[RecurrenceLink, ...] = ()
    corrections: tuple[CorrectionRecord, ...] = ()


class VerificationProjection(_ProjectionState):
    """``verification``: resolution-proof and audit-report state.

    Fed by ``detection`` events (``resolution_proof``) and ``audit_report``
    events (``verdict`` / ``report_type`` / finding evidence).  Efficiency
    events never alter it.
    """

    projection: Literal["verification"] = "verification"

    occurrence_id: str | None = None
    event_id: str | None = None
    classifier_version: str | None = None
    cluster_signature: str | None = None
    cluster_id: str | None = None
    resolution_proof: tuple[OwnerRef, ...] = ()
    audit_verdict: str | None = None
    audit_report_type: str | None = None
    recurrences: tuple[RecurrenceLink, ...] = ()
    corrections: tuple[CorrectionRecord, ...] = ()


class EfficiencyProjection(_ProjectionState):
    """``efficiency_analysis``: censoring/denominators/unknowns/coverage.

    Fed by ``efficiency_analysis`` events only.  Retains the product, coverage
    denominator and covered count (coverage is derived), censored duration,
    bucket counts, classifier version, and the half-open reporting window
    ``[start, end)`` plus the watermark.  Missing values stay explicit
    ``None`` (unknown) — never coerced to zero or to green.
    """

    projection: Literal["efficiency_analysis"] = "efficiency_analysis"

    occurrence_id: str | None = None
    event_id: str | None = None
    classifier_version: str | None = None
    product: str | None = None
    coverage_denominator: int | None = None
    covered_count: int | None = None
    censored_duration_seconds: float | None = None
    bucket_counts: dict[str, int] = Field(default_factory=dict)
    window_start: str | None = None
    window_end: str | None = None
    watermark: str | None = None
    corrections: tuple[CorrectionRecord, ...] = ()

    @property
    def coverage(self) -> float | None:
        """Derived coverage (covered / denominator), or ``None`` when unknown.

        ``None`` covers every unknown case: a missing numerator, a missing
        denominator, or a zero denominator (never a division by zero).
        """
        if self.coverage_denominator is not None and self.covered_count is not None:
            if self.coverage_denominator == 0:
                return None
            return self.covered_count / self.coverage_denominator
        return None


# ---------------------------------------------------------------------------
# Deterministic reducers
# ---------------------------------------------------------------------------


def _accumulate_source_digest(prior: str | None, event_digest: str) -> str:
    """Chain one event digest into the order-sensitive source digest."""
    material = canonical_json([prior if prior is not None else "", event_digest])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _output_digest(state: BaseModel) -> str:
    """Canonical digest of a projection's materialized output.

    Bookkeeping fields (sequence, cursor, digests, lag, freshness) are
    excluded so the digest changes exactly when the *output* changes.
    """
    data = state.model_dump(mode="json", exclude_none=False)
    payload = {key: value for key, value in data.items() if key not in _METADATA_FIELDS}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _freshness_for(event: MaintenanceEvent) -> ProjectionFreshness:
    """Projection freshness from an event's validated lateness."""
    if event.lateness is Lateness.ON_TIME:
        return ProjectionFreshness.FRESH
    return ProjectionFreshness.STALE


def _correction_for(
    state: _ProjectionState,
    *,
    event: MaintenanceEvent,
    sequence: int,
    prior_output_digest: str | None,
) -> CorrectionRecord | None:
    """Build an append-only correction for late evidence, if there is a prior result."""
    if event.lateness is Lateness.LATE and state.sequence >= 1:
        return CorrectionRecord(
            kind=CorrectionKind.LATE_EVIDENCE,
            sequence=sequence,
            corrected_sequence=state.sequence,
            prior_output_digest=prior_output_digest,
            event_id=event.event_id,
            occurrence_id=event.occurrence_id,
            reason=f"late evidence at event_time {event.event_time.root.isoformat()}",
        )
    return None


def _advance(
    state: _ProjectionState,
    *,
    event: MaintenanceEvent,
    event_digest: str,
    cursor: int,
    updates: dict[str, Any],
) -> _ProjectionState:
    """Advance *state* by one consumed event and finalize its metadata.

    Appends a late-evidence correction (without rewriting the prior result)
    when the event is late and a prior result exists, then recomputes the
    order-sensitive source digest and the canonical output digest.
    """
    new_sequence = state.sequence + 1
    corrections = state.corrections
    correction = _correction_for(
        state,
        event=event,
        sequence=new_sequence,
        prior_output_digest=state.output_digest,
    )
    if correction is not None:
        corrections = corrections + (correction,)

    merged: dict[str, Any] = dict(updates)
    merged.update(
        {
            "sequence": new_sequence,
            "cursor": cursor,
            "source_digest": _accumulate_source_digest(state.source_digest, event_digest),
            "output_digest": None,
            "freshness": _freshness_for(event),
            "corrections": corrections,
        }
    )
    provisional = state.model_copy(update=merged)
    return provisional.model_copy(update={"output_digest": _output_digest(provisional)})


def _union_refs(*groups: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Dedupe and deterministically order owner references."""
    seen: set[tuple[Any, ...]] = set()
    ordered: list[OwnerRef] = []
    for group in groups:
        for ref in group:
            key = (ref.owner, ref.locator, ref.digest, ref.cursor)
            if key not in seen:
                seen.add(key)
                ordered.append(ref)
    return tuple(
        sorted(
            ordered,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


def _append_recurrence(
    state: _ProjectionState, event: MaintenanceEvent
) -> tuple[RecurrenceLink, ...]:
    """Extend a projection's recurrence chain with a verified recurrence link."""
    existing: Sequence[RecurrenceLink] = getattr(state, "recurrences", ())
    if event.recurrence is None:
        return tuple(existing)
    return tuple(existing) + (event.recurrence,)


def reduce_custody(
    event: MaintenanceEvent,
    state: CustodyProjection,
    *,
    cursor: int,
    event_digest: str,
) -> CustodyProjection:
    """Reduce a detection event into the operational-custody projection.

    Any non-``detection`` event kind — including ``efficiency_analysis`` — is a
    no-op and leaves the custody state untouched.
    """
    if event.event_kind is not EventKind.DETECTION:
        return state
    return _advance(
        state,
        event=event,
        event_digest=event_digest,
        cursor=cursor,
        updates={
            "occurrence_id": event.occurrence_id,
            "event_id": event.event_id,
            "classifier_version": event.classifier.classifier_version,
            "cluster_signature": event.cluster.signature,
            "cluster_id": event.cluster.cluster_id,
            "custody_refs": event.custody_refs,
            "fence_refs": event.fence_refs,
            "budget": event.budget,
            "recurrences": _append_recurrence(state, event),
        },
    )


def reduce_verification(
    event: MaintenanceEvent,
    state: VerificationProjection,
    *,
    cursor: int,
    event_digest: str,
) -> VerificationProjection:
    """Reduce a detection or audit_report event into the verification projection.

    ``efficiency_analysis`` events are a no-op (they never alter verification).
    """
    if event.event_kind is EventKind.EFFICIENCY_ANALYSIS:
        return state

    updates: dict[str, Any] = {
        "occurrence_id": event.occurrence_id,
        "event_id": event.event_id,
        "classifier_version": event.classifier.classifier_version,
        "cluster_signature": event.cluster.signature,
        "cluster_id": event.cluster.cluster_id,
        "resolution_proof": _union_refs(state.resolution_proof, event.resolution_proof),
        "recurrences": _append_recurrence(state, event),
    }
    if event.event_kind is EventKind.AUDIT_REPORT:
        payload = event.payload
        finding_refs = tuple(
            ref for finding in payload.findings for ref in finding.evidence_refs
        )
        updates["audit_verdict"] = payload.verdict
        updates["audit_report_type"] = payload.report_type
        updates["resolution_proof"] = _union_refs(
            state.resolution_proof, event.resolution_proof, finding_refs
        )
    return _advance(
        state,
        event=event,
        event_digest=event_digest,
        cursor=cursor,
        updates=updates,
    )


def reduce_efficiency(
    event: MaintenanceEvent,
    state: EfficiencyProjection,
    *,
    cursor: int,
    event_digest: str,
) -> EfficiencyProjection:
    """Reduce an efficiency_analysis event into the efficiency projection.

    Detection and audit_report events are a no-op (they never alter the
    efficiency projection).
    """
    if event.event_kind is not EventKind.EFFICIENCY_ANALYSIS:
        return state
    payload = event.payload
    return _advance(
        state,
        event=event,
        event_digest=event_digest,
        cursor=cursor,
        updates={
            "occurrence_id": event.occurrence_id,
            "event_id": event.event_id,
            "classifier_version": event.classifier.classifier_version,
            "product": payload.product,
            "coverage_denominator": payload.coverage_denominator,
            "covered_count": payload.covered_count,
            "censored_duration_seconds": payload.censored_duration_seconds,
            "bucket_counts": payload.bucket_counts,
            "window_start": event.window.start.root.isoformat(),
            "window_end": event.window.end.root.isoformat(),
            "watermark": event.watermark.root.isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# The projection engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectionResult:
    """Snapshot of the three projections after one :meth:`ProjectionEngine.apply`."""

    custody: CustodyProjection
    verification: VerificationProjection
    efficiency: EfficiencyProjection
    disposition: ApplyDisposition

    @property
    def applied(self) -> bool:
        """``True`` when the event advanced at least one projection."""
        return self.disposition is ApplyDisposition.APPLIED


class ProjectionEngine:
    """Deterministic driver that routes strict events into three projections.

    The engine owns the occurrence idempotency registry (dedupe vs. verified
    recurrence) and the global source cursor.  It dispatches each new event to
    the independent reducers and recomputes each projection's ``lag``.
    """

    def __init__(self) -> None:
        self._custody = CustodyProjection()
        self._verification = VerificationProjection()
        self._efficiency = EfficiencyProjection()
        self._seen: dict[str, str] = {}
        self._source_cursor = 0

    # ── read-only state ─────────────────────────────────────────────────

    @property
    def custody(self) -> CustodyProjection:
        return self._custody

    @property
    def verification(self) -> VerificationProjection:
        return self._verification

    @property
    def efficiency(self) -> EfficiencyProjection:
        return self._efficiency

    def snapshot(self) -> ProjectionResult:
        """Return the current three projections without applying anything."""
        return ProjectionResult(
            self._custody, self._verification, self._efficiency, ApplyDisposition.APPLIED
        )

    # ── apply ───────────────────────────────────────────────────────────

    def apply(
        self,
        event: MaintenanceEvent | dict[str, Any],
        *,
        cursor: int | None = None,
    ) -> ProjectionResult:
        """Apply one strict event to the projections, deduplicating exact repeats.

        * ``cursor`` is the source ledger sequence; when omitted it
          auto-increments from the previous source cursor.
        * An exact duplicate (same occurrence + same digest) is deduped: no
          projection advances and no budget is consumed.
        * A divergent duplicate (same occurrence, different digest) raises
          :class:`ProjectionConflictError`.
        * A verified recurrence carries a fresh occurrence id (enforced by the
          event contract), so it is applied as a new, causally linked
          occurrence with a fresh budget.
        """
        model = self._coerce(event)
        digest = canonical_digest(model)
        occurrence_id = model.occurrence_id

        if occurrence_id in self._seen:
            if self._seen[occurrence_id] == digest:
                return ProjectionResult(
                    self._custody,
                    self._verification,
                    self._efficiency,
                    ApplyDisposition.DEDUPED,
                )
            raise ProjectionConflictError(
                f"projection idempotency conflict for occurrence "
                f"{occurrence_id!r}: stored digest {self._seen[occurrence_id]} "
                f"!= incoming digest {digest}; nothing applied"
            )
        self._seen[occurrence_id] = digest

        if cursor is None:
            self._source_cursor += 1
        else:
            self._source_cursor = max(self._source_cursor, int(cursor))

        source = self._source_cursor
        self._custody = reduce_custody(
            model, self._custody, cursor=source, event_digest=digest
        )
        self._verification = reduce_verification(
            model, self._verification, cursor=source, event_digest=digest
        )
        self._efficiency = reduce_efficiency(
            model, self._efficiency, cursor=source, event_digest=digest
        )

        self._custody = self._custody.model_copy(
            update={"lag": source - self._custody.cursor}
        )
        self._verification = self._verification.model_copy(
            update={"lag": source - self._verification.cursor}
        )
        self._efficiency = self._efficiency.model_copy(
            update={"lag": source - self._efficiency.cursor}
        )

        return ProjectionResult(
            self._custody,
            self._verification,
            self._efficiency,
            ApplyDisposition.APPLIED,
        )

    def _coerce(self, event: MaintenanceEvent | dict[str, Any]) -> MaintenanceEvent:
        """Strict-decode *event* into a :class:`MaintenanceEvent` (no writes)."""
        if isinstance(event, MaintenanceEvent):
            return event
        if isinstance(event, dict):
            try:
                return strict_loads(MaintenanceEvent, event)
            except MaintenanceCodecError as exc:
                raise ValueError(
                    f"maintenance event strict decode failed: {exc}"
                ) from exc
        raise ValueError("event must be a MaintenanceEvent or a canonical dict")


def replay(
    events: Sequence[MaintenanceEvent | dict[str, Any]],
    *,
    cursors: Sequence[int] | None = None,
) -> ProjectionEngine:
    """Replay a sequence of strict events through a fresh engine (in order).

    Deterministic: identical input (events + cursors) reproduces identical
    projection sequences and digests.
    """
    engine = ProjectionEngine()
    cursor_list = list(cursors) if cursors is not None else []
    for index, event in enumerate(events):
        cursor = cursor_list[index] if index < len(cursor_list) else None
        engine.apply(event, cursor=cursor)
    return engine


__all__ = [
    "ApplyDisposition",
    "CorrectionKind",
    "CorrectionRecord",
    "CustodyProjection",
    "EfficiencyProjection",
    "ProjectionConflictError",
    "ProjectionEngine",
    "ProjectionFreshness",
    "ProjectionName",
    "ProjectionResult",
    "VerificationProjection",
    "reduce_custody",
    "reduce_efficiency",
    "reduce_verification",
    "replay",
]
