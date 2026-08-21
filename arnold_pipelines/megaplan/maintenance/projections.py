"""Independent, deterministic Maintenance projections (M2/M3, T13/T5).

This module materializes three *independent* projections over the strict
Maintenance event stream — legacy :class:`MaintenanceEvent` rows AND M3
operational :class:`OperationalEvent` lifecycle rows:

* :class:`CustodyProjection` — ``operational_custody``: the active
  custody/lease/fence state for a detection occurrence (``custody_refs`` +
  ``fence_refs`` + occurrence-scoped budget + recurrence chain) extended with
  the M3 operational custody state: canonical occurrence/lease/Run Authority/
  WBC/policy/target references, request/effect state, the current checkpoint
  set, open/terminal status, recurrence links, and escalation references.
* :class:`VerificationProjection` — ``verification``: resolution-proof and
  audit-report state (``resolution_proof`` from detection events, ``verdict`` /
  ``report_type`` from audit reports) extended with the M3 independent
  verification state: verifier provenance, proof mode, negative-control
  result, resumed-progress evidence, checkpoint outcomes, terminal reason,
  and a typed coherence that can never be green on UNKNOWN/INCOHERENT.
* :class:`EfficiencyProjection` — ``efficiency_analysis``: censoring,
  denominators, unknowns, coverage, bucket counts, classifier version, and the
  half-open reporting window / watermark.  It advances independently and M3
  operational events never alter it.

Each projection advances independently with its own monotonic ``sequence``,
source ``cursor``, chained ``source_digest``, canonical ``output_digest``,
``lag`` (distance behind the global source cursor), and ``freshness``.
Replaying the same event order byte-for-byte reproduces the same sequences
and digests.

Locked semantics (SD2 + M3 Step 2/4 + the fail-closed correction rule):

* **Lifecycle-key dedupe vs. verified recurrence.**  The engine deduplicates
  by the canonical lifecycle idempotency key recorded at the journal boundary
  (:func:`lifecycle_idempotency_key`): legacy rows keep the occurrence-only
  key (exactly one record per occurrence, M2 compatible) while M3 operational
  rows derive the strict action key — so distinct request/source-change/
  installation/retrigger/progress/checkpoint/terminal/recurrence/escalation
  records for ONE occurrence coexist, an exact retry is deduped, and a
  divergent reuse of the same action key raises
  :class:`ProjectionConflictError` without advancing.  A *verified recurrence*
  always carries a fresh occurrence id, so it is a distinct, causally linked
  occurrence with a fresh occurrence-scoped budget; its root-cause cluster
  grouping is preserved.
* **Efficiency isolation.**  ``efficiency_analysis`` events are routed only to
  the efficiency projection.  They can never alter the custody or verification
  projections (the reducers return the prior state unchanged for any
  non-relevant event kind).
* **Half-open watermarked windows.**  Latency/freshness for legacy events is
  taken from the event's already-validated ``lateness``.  Operational events
  carry no watermark, so their freshness is explicitly ``unknown`` — never
  guessed green.
* **UNKNOWN/INCOHERENT never closes custody.**  Terminal verification is
  terminal only when a terminal event is observed with durable
  negative-control references AND the complete policy-required checkpoint set
  (immediate, five-minute, one-hour, next-three-hour).  A terminal event with
  an incomplete set or missing negative controls derives
  ``INCOHERENT``/open; absent terminal evidence is ``UNKNOWN``/open.
* **Append-only late-evidence corrections.**  A *late* legacy event never
  rewrites a prior projection result; the reducer appends a
  :class:`CorrectionRecord`` (``kind="late_evidence"``) that links the new
  sequence to the corrected sequence and preserves the corrected result's
  ``output_digest``.  Operational events have no watermark/lateness and never
  append corrections.

No module here performs any ledger, plan, or chain mutation: projections are
pure, deterministic reducers over strict events.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from arnold_pipelines.megaplan.incident.schema import lifecycle_idempotency_key
from arnold_pipelines.megaplan.maintenance.events import (
    CheckpointWindowKind,
    EventKind,
    MaintenanceEvent,
    OccurrenceBudget,
    OperationalActionKind,
    OperationalEvent,
    ProjectionCoordinates,
    RecurrenceLink,
    VerifierProvenance,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EventWindow,
    Lateness,
    MaintenanceCodecError,
    OwnerRef,
    canonical_digest,
    canonical_dumps,
    canonical_json,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.operations import EscalationReference

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
    """Closed correction vocabulary (append-only; never rewrites a result).

    ``LATE_EVIDENCE`` is the automatic M4 correction appended for a late
    legacy event.  ``KEYED`` is the explicit M5 daily correction (Plan Step 6
    / T6): a ``DAILY_EFFICIENCY_CORRECTION`` event bypasses the automatic
    record and appends exactly one keyed correction validated against its
    declared supersedes target (kind + exact half-open window + sha256
    digest) — never the immediately preceding stream digest.
    """

    LATE_EVIDENCE = "late_evidence"
    KEYED = "keyed"


#: The four additive M5 daily kinds (Plan Step 5 / T5A).  Daily events
#: advance ONLY the efficiency projection: they are strict no-ops for the
#: operational custody and verification projections — a proposal or favorable
#: analytical report never closes custody, turns verification green, or
#: becomes dispatchable (Plan Step 6 / T6).
DAILY_EVENT_KINDS: frozenset[EventKind] = frozenset(
    {
        EventKind.DAILY_EFFICIENCY_REPORT,
        EventKind.DAILY_EFFICIENCY_CLUSTER,
        EventKind.DAILY_EFFICIENCY_PROPOSAL,
        EventKind.DAILY_EFFICIENCY_CORRECTION,
    }
)


class VerificationCoherence(str, Enum):
    """Typed coherence of the independent verification projection (M3).

    * ``UNKNOWN`` — no terminal verification evidence has been observed;
    * ``INCOHERENT`` — terminal evidence exists but the required checkpoint
      set is incomplete or durable negative controls are missing
      (contradictory evidence);
    * ``COHERENT`` — terminal evidence with the complete policy-required
      checkpoint set and durable negative-control references.

    Only ``COHERENT`` may close custody; ``UNKNOWN`` and ``INCOHERENT``
    always leave it open.
    """

    UNKNOWN = "unknown"
    INCOHERENT = "incoherent"
    COHERENT = "coherent"


#: The complete policy-required checkpoint set.  Terminal verification is
#: eligible only when every canonical window has a checkpoint outcome.
REQUIRED_CHECKPOINT_WINDOWS: frozenset[CheckpointWindowKind] = frozenset(
    {
        CheckpointWindowKind.IMMEDIATE,
        CheckpointWindowKind.FIVE_MINUTE,
        CheckpointWindowKind.ONE_HOUR,
        CheckpointWindowKind.NEXT_THREE_HOUR,
    }
)


class CheckpointOutcome(BaseModel):
    """One durable checkpoint-verification outcome (M3 Step 4).

    Records the canonical checkpoint window, the checkpoint reference, the
    evidence references, and the event that produced it.  The projection
    derives the *current checkpoint set* from these outcomes; a terminal
    event only closes custody when every window in
    :data:`REQUIRED_CHECKPOINT_WINDOWS` is present.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    window: CheckpointWindowKind
    checkpoint_ref: OwnerRef | None = None
    evidence_refs: tuple[OwnerRef, ...] = ()
    event_id: str

    @field_validator("event_id")
    @classmethod
    def _validate_event_id(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "checkpoint outcome event_id must be a non-empty string"
            )
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _sort_evidence(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_owner_refs(value)


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
#: The M5 per-stream cursors are bookkeeping like the projection-wide
#: ``cursor``; the per-stream digests are materialized output and stay
#: included so a committed daily payload always changes the output digest.
_METADATA_FIELDS: frozenset[str] = frozenset(
    {
        "sequence",
        "cursor",
        "source_digest",
        "output_digest",
        "lag",
        "freshness",
        "report_cursor",
        "baseline_cursor",
        "cluster_cursor",
        "proposal_cursor",
        "correction_cursor",
        "coverage_cursor",
        "precision_cursor",
    }
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

    Fed by ``detection`` events and M3 operational lifecycle events.  Retains
    the active occurrence, its classifier version, root-cause cluster
    grouping, custody/fence references, occurrence-scoped budget, and any
    verified recurrence links, plus the M3 operational custody state: the
    canonical occurrence/lease/Run Authority/WBC/policy/target references,
    request/effect state, the current checkpoint set, open/terminal status,
    and escalation references.
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

    # ── M3 operational custody state (Plan Step 4) ─────────────────────
    occurrence_digest: str | None = None
    occurrence_ref: OwnerRef | None = None
    lease_id: str | None = None
    custody_epoch: int | None = None
    lease_digest: str | None = None
    lease_ref: OwnerRef | None = None
    run_id: str | None = None
    run_authority_satisfied: bool | None = None
    grant_ref: OwnerRef | None = None
    fence_ref: OwnerRef | None = None
    decision_ref: OwnerRef | None = None
    wbc_attempt_id: str | None = None
    attempt_ref: OwnerRef | None = None
    ledger_ref: OwnerRef | None = None
    policy_version: str | None = None
    policy_digest: str | None = None
    target: str | None = None
    target_type: str | None = None
    producer_principal: str | None = None
    producer_role: str | None = None
    request_id: str | None = None
    request_ref: OwnerRef | None = None
    source_change_ref: OwnerRef | None = None
    effect_source_digest: str | None = None
    install_ref: OwnerRef | None = None
    install_digest: str | None = None
    retrigger_ref: OwnerRef | None = None
    progress_refs: tuple[OwnerRef, ...] = ()
    checkpoints: tuple[CheckpointOutcome, ...] = ()
    terminal: bool = False
    terminal_reason: str | None = None
    escalated: bool = False
    escalations: tuple[EscalationReference, ...] = ()

    @property
    def open(self) -> bool:
        """``True`` while canonical custody is NOT terminal.

        Custody closes only on a terminal verification with the complete
        policy-required checkpoint set and durable negative controls;
        UNKNOWN or INCOHERENT evidence always leaves it open.
        """
        return not self.terminal


class VerificationProjection(_ProjectionState):
    """``verification``: resolution-proof and audit-report state.

    Fed by ``detection`` events (``resolution_proof``), ``audit_report``
    events (``verdict`` / ``report_type`` / finding evidence), and M3
    operational verification actions (progress observation, checkpoint
    verification, terminal verification).  Efficiency events and
    request/effect/recurrence/escalation actions never alter it.  The M3
    state carries verifier provenance, proof mode, negative-control result,
    resumed-progress evidence, checkpoint outcomes, terminal reason, and a
    typed coherence that can never be green on UNKNOWN/INCOHERENT.
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

    # ── M3 operational verification state (Plan Step 4) ────────────────
    occurrence_digest: str | None = None
    verifier_principal: str | None = None
    verifier_provenance: VerifierProvenance | None = None
    proof_mode: str | None = None
    negative_control_result: str | None = None
    resumed_progress: bool | None = None
    progress_refs: tuple[OwnerRef, ...] = ()
    checkpoint_outcomes: tuple[CheckpointOutcome, ...] = ()
    terminal_reason: str | None = None
    coherence: VerificationCoherence = VerificationCoherence.UNKNOWN
    terminal: bool = False


class EfficiencyProjection(_ProjectionState):
    """``efficiency_analysis``: censoring/denominators/unknowns/coverage.

    Fed by ``efficiency_analysis`` events only.  Retains the product, coverage
    denominator and covered count (coverage is derived), censored duration,
    bucket counts, classifier version, and the half-open reporting window
    ``[start, end)`` plus the watermark.  Missing values stay explicit
    ``None`` (unknown) — never coerced to zero or to green.

    Plan Step 6 (T6) extends the projection with the four additive M5 daily
    kinds.  Daily events advance ONLY this projection — they are no-ops for
    operational custody and verification (a proposal or favorable analytical
    report never closes custody, turns verification green, or becomes
    dispatchable).  Each daily stream advances on its OWN source cursor and
    exposes its own canonical digest, independent of the projection-wide
    metadata and of the other streams; the ``committed_daily`` registry maps
    every committed daily payload ``(kind, window)`` to its commit sequence
    and canonical digest so explicit corrections are validated against
    exactly the declared supersedes target.
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

    # ── M5 independent per-stream coordinates (Plan Step 6 / T6) ────────
    # A stream cursor advances exactly when a payload for that stream is
    # committed; the stream digest is the canonical digest of that stream's
    # materialized output (the embedded ``daily_efficiency.v1`` contract
    # instance, or the embedded baseline / coverage / precision collection —
    # never fabricated when the report carries none).
    report_cursor: int = 0
    report_digest: str | None = None
    baseline_cursor: int = 0
    baseline_digest: str | None = None
    cluster_cursor: int = 0
    cluster_digest: str | None = None
    proposal_cursor: int = 0
    proposal_digest: str | None = None
    correction_cursor: int = 0
    correction_digest: str | None = None
    coverage_cursor: int = 0
    coverage_digest: str | None = None
    precision_cursor: int = 0
    precision_digest: str | None = None

    #: Keyed supersedes registry: every committed daily payload maps
    #: ``f"{kind}|{window_start}|{window_end}"`` to
    #: ``(projection_sequence_at_commit, canonical_payload_digest)``.
    committed_daily: dict[str, tuple[int, str]] = Field(default_factory=dict)

    @field_validator(
        "report_cursor",
        "baseline_cursor",
        "cluster_cursor",
        "proposal_cursor",
        "correction_cursor",
        "coverage_cursor",
        "precision_cursor",
    )
    @classmethod
    def _validate_stream_cursors(cls, value: int) -> int:
        if value < 0:
            raise ValueError(
                f"projection stream cursor must be >= 0, got {value}"
            )
        return value

    @field_validator(
        "report_digest",
        "baseline_digest",
        "cluster_digest",
        "proposal_digest",
        "correction_digest",
        "coverage_digest",
        "precision_digest",
    )
    @classmethod
    def _validate_stream_digests(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(
                "projection stream digest must be a 64-character lowercase "
                "sha256 hex digest"
            )
        return value

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


def _sort_owner_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic (owner, locator, digest, cursor) reference order."""
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


def _freshness_for(event: MaintenanceEvent | OperationalEvent) -> ProjectionFreshness:
    """Projection freshness from an event's validated lateness.

    Operational lifecycle events carry no watermark/lateness, so their
    freshness is explicitly ``unknown`` — never guessed green.
    """
    if isinstance(event, OperationalEvent):
        return ProjectionFreshness.UNKNOWN
    if event.lateness is Lateness.ON_TIME:
        return ProjectionFreshness.FRESH
    return ProjectionFreshness.STALE


def _correction_for(
    state: _ProjectionState,
    *,
    event: MaintenanceEvent | OperationalEvent,
    sequence: int,
    prior_output_digest: str | None,
) -> CorrectionRecord | None:
    """Build an append-only correction for late evidence, if there is a prior result.

    Operational lifecycle events have no watermark/lateness and never append
    corrections; only late legacy events amend a prior result.
    """
    if isinstance(event, OperationalEvent):
        return None
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
    explicit_correction: CorrectionRecord | None = None,
) -> _ProjectionState:
    """Advance *state* by one consumed event and finalize its metadata.

    Appends a late-evidence correction (without rewriting the prior result)
    when the event is late and a prior result exists, then recomputes the
    order-sensitive source digest and the canonical output digest.  When
    *explicit_correction* is supplied (Plan Step 6 / T6), the automatic
    ``LATE_EVIDENCE`` correction is BYPASSED entirely and exactly that keyed
    record is appended instead — an explicit ``DAILY_EFFICIENCY_CORRECTION``
    event never produces a second, automatic correction even when it is
    itself classified LATE.
    """
    new_sequence = state.sequence + 1
    corrections = state.corrections
    if explicit_correction is not None:
        correction = explicit_correction
    else:
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


# ---------------------------------------------------------------------------
# M3 operational reducers (Plan Step 4)
# ---------------------------------------------------------------------------


def _required_checkpoint_windows_complete(
    outcomes: Sequence[CheckpointOutcome],
) -> bool:
    """Return whether every policy-required window has a checkpoint outcome."""
    return REQUIRED_CHECKPOINT_WINDOWS.issubset(
        {outcome.window for outcome in outcomes}
    )


def _append_checkpoint_outcome(
    state: _ProjectionState,
    event: OperationalEvent,
    *,
    field: str,
) -> tuple[CheckpointOutcome, ...]:
    """Append one checkpoint outcome (dedupe by canonical window).

    The current checkpoint set holds at most one outcome per canonical
    window; a second checkpoint verification for an already-recorded window
    is not appended (the engine already deduped the exact retry).
    """
    if event.action_kind is not OperationalActionKind.CHECKPOINT_VERIFICATION:
        return getattr(state, field)
    payload = event.payload
    existing = getattr(state, field)
    if any(outcome.window == payload.checkpoint for outcome in existing):
        return existing
    return existing + (
        CheckpointOutcome(
            window=payload.checkpoint,
            checkpoint_ref=payload.checkpoint_ref,
            evidence_refs=_sort_owner_refs(payload.evidence_refs),
            event_id=event.event_id,
        ),
    )


def _operational_recurrence_link(
    state: CustodyProjection, event: OperationalEvent
) -> tuple[RecurrenceLink, ...]:
    """Extend custody's recurrence chain from a verified-recurrence action."""
    if event.action_kind is not OperationalActionKind.RECURRENCE:
        return state.recurrences
    reference = event.payload.recurrence
    return state.recurrences + (
        RecurrenceLink(
            verified=True,
            predecessor_event_id=reference.predecessor_event_id,
            predecessor_occurrence_id=reference.predecessor_occurrence_id,
        ),
    )


def _append_escalation(
    state: CustodyProjection, event: OperationalEvent
) -> tuple[EscalationReference, ...]:
    """Append one immutable human-escalation reference (never a waiver)."""
    if event.action_kind is not OperationalActionKind.HUMAN_ESCALATION:
        return state.escalations
    return state.escalations + (event.payload.escalation,)


def _terminal_eligible(
    *,
    checkpoints: Sequence[CheckpointOutcome],
    negative_controls_present: bool,
) -> bool:
    """Terminal eligibility: complete required checkpoint set AND negative
    controls.  UNKNOWN/INCOHERENT evidence can never close custody."""
    return negative_controls_present and _required_checkpoint_windows_complete(
        checkpoints
    )


def _derive_coherence(
    *,
    terminal_seen: bool,
    negative_control_passed: bool,
    checkpoint_outcomes: Sequence[CheckpointOutcome],
) -> VerificationCoherence:
    """Derive verification coherence from durable evidence.

    * no terminal evidence → ``UNKNOWN`` (custody open);
    * terminal evidence WITH the complete required checkpoint set AND durable
      negative controls → ``COHERENT`` (may close custody);
    * terminal evidence with an incomplete set or missing negative controls →
      ``INCOHERENT`` (contradictory — custody stays open).
    """
    if not terminal_seen:
        return VerificationCoherence.UNKNOWN
    if negative_control_passed and _required_checkpoint_windows_complete(
        checkpoint_outcomes
    ):
        return VerificationCoherence.COHERENT
    return VerificationCoherence.INCOHERENT


def _operational_custody_updates(
    event: OperationalEvent, state: CustodyProjection
) -> dict[str, Any]:
    """Materialize the M3 operational custody updates for one lifecycle action."""
    occurrence = event.occurrence
    lease = event.lease
    run = event.run_authority
    wbc = event.wbc_attempt
    policy = event.policy
    target = event.target
    payload = event.payload
    checkpoints = _append_checkpoint_outcome(state, event, field="checkpoints")

    updates: dict[str, Any] = {
        "occurrence_id": occurrence.occurrence_id,
        "occurrence_digest": occurrence.canonical_digest,
        "occurrence_ref": occurrence.occurrence_ref,
        "event_id": event.event_id,
        "lease_id": lease.lease_id,
        "custody_epoch": lease.custody_epoch,
        "lease_digest": lease.lease_digest,
        "lease_ref": lease.lease_ref,
        "run_id": run.run_id,
        "run_authority_satisfied": run.satisfied,
        "grant_ref": run.grant_ref,
        "fence_ref": run.fence_ref,
        "decision_ref": run.decision_ref,
        "wbc_attempt_id": wbc.attempt_id if wbc is not None else None,
        "attempt_ref": wbc.attempt_ref if wbc is not None else None,
        "ledger_ref": wbc.ledger_ref if wbc is not None else None,
        "policy_version": policy.policy_version,
        "policy_digest": policy.policy_digest,
        "target": target.target,
        "target_type": target.target_type,
        "producer_principal": event.producer.principal,
        "producer_role": event.producer.role.value,
        "recurrences": _operational_recurrence_link(state, event),
        "escalations": _append_escalation(state, event),
        "escalated": state.escalated
        or event.action_kind is OperationalActionKind.HUMAN_ESCALATION,
        "checkpoints": checkpoints,
        "terminal": state.terminal,
        "terminal_reason": state.terminal_reason,
    }

    if event.action_kind is OperationalActionKind.REPAIR_REQUEST:
        updates["request_id"] = payload.request_id
        updates["request_ref"] = payload.request_ref
    elif event.action_kind is OperationalActionKind.SOURCE_CHANGE:
        updates["source_change_ref"] = payload.change_ref
        updates["effect_source_digest"] = payload.source_digest
    elif event.action_kind is OperationalActionKind.INSTALLATION:
        updates["install_ref"] = payload.install_ref
        updates["install_digest"] = payload.install_digest
    elif event.action_kind is OperationalActionKind.RETRIGGER:
        updates["retrigger_ref"] = payload.retrigger_ref
    elif event.action_kind is OperationalActionKind.PROGRESS_OBSERVATION:
        updates["progress_refs"] = _union_refs(
            state.progress_refs, payload.progress_refs
        )
    elif event.action_kind is OperationalActionKind.TERMINAL_VERIFICATION:
        updates["terminal_reason"] = payload.terminal_reason
        updates["terminal"] = state.terminal or _terminal_eligible(
            checkpoints=checkpoints,
            negative_controls_present=bool(payload.negative_control_refs),
        )
    return updates


def _operational_verification_updates(
    event: OperationalEvent, state: VerificationProjection
) -> dict[str, Any]:
    """Materialize the M3 verification updates for verification-relevant
    actions (progress observation, checkpoint verification, terminal
    verification).  Request/effect/recurrence/escalation actions add no
    verification evidence and return ``{}`` (a no-op)."""
    updates: dict[str, Any] = {
        "occurrence_id": event.occurrence.occurrence_id,
        "occurrence_digest": event.occurrence.canonical_digest,
        "event_id": event.event_id,
    }
    payload = event.payload

    if event.action_kind is OperationalActionKind.CHECKPOINT_VERIFICATION:
        outcomes = _append_checkpoint_outcome(
            state, event, field="checkpoint_outcomes"
        )
        updates["checkpoint_outcomes"] = outcomes
        terminal_seen = state.terminal_reason is not None
        negative_passed = state.negative_control_result == "passed"
        updates["coherence"] = _derive_coherence(
            terminal_seen=terminal_seen,
            negative_control_passed=negative_passed,
            checkpoint_outcomes=outcomes,
        )
        updates["terminal"] = (
            updates["coherence"] is VerificationCoherence.COHERENT
        )
    elif event.action_kind is OperationalActionKind.PROGRESS_OBSERVATION:
        updates["progress_refs"] = _union_refs(
            state.progress_refs, payload.progress_refs
        )
        updates["resumed_progress"] = state.resumed_progress or bool(
            payload.progress_refs
        )
    elif event.action_kind is OperationalActionKind.TERMINAL_VERIFICATION:
        negative_passed = bool(payload.negative_control_refs)
        updates["verifier_principal"] = payload.verifier.principal
        updates["verifier_provenance"] = payload.verifier
        updates["proof_mode"] = (
            "negative_control" if negative_passed else "unknown"
        )
        updates["negative_control_result"] = (
            "passed" if negative_passed else "unknown"
        )
        updates["terminal_reason"] = payload.terminal_reason
        updates["coherence"] = _derive_coherence(
            terminal_seen=True,
            negative_control_passed=negative_passed,
            checkpoint_outcomes=state.checkpoint_outcomes,
        )
        updates["terminal"] = (
            updates["coherence"] is VerificationCoherence.COHERENT
        )
    else:
        # Repair request / source change / installation / retrigger /
        # recurrence / escalation carry no verification evidence.
        return {}
    return updates


def reduce_custody(
    event: MaintenanceEvent | OperationalEvent,
    state: CustodyProjection,
    *,
    cursor: int,
    event_digest: str,
) -> CustodyProjection:
    """Reduce a detection or operational lifecycle event into custody.

    M3 operational lifecycle events advance the operational custody state
    (occurrence/authority references, request/effect state, checkpoint set,
    open/terminal status, recurrences, escalations).  Any non-``detection``
    legacy event kind — including ``efficiency_analysis`` — is a no-op and
    leaves the custody state untouched.
    """
    if isinstance(event, OperationalEvent):
        return _advance(
            state,
            event=event,
            event_digest=event_digest,
            cursor=cursor,
            updates=_operational_custody_updates(event, state),
        )
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
    event: MaintenanceEvent | OperationalEvent,
    state: VerificationProjection,
    *,
    cursor: int,
    event_digest: str,
) -> VerificationProjection:
    """Reduce a detection/audit/operational-verification event.

    M3 verification-relevant actions (progress observation, checkpoint
    verification, terminal verification) advance the verification state;
    request/effect/recurrence/escalation actions and ``efficiency_analysis``
    events are a no-op (they never alter verification).  ``UNKNOWN`` or
    ``INCOHERENT`` verification is never green and never closes custody.
    """
    if isinstance(event, OperationalEvent):
        updates = _operational_verification_updates(event, state)
        if not updates:
            return state
        return _advance(
            state,
            event=event,
            event_digest=event_digest,
            cursor=cursor,
            updates=updates,
        )
    if (
        event.event_kind is EventKind.EFFICIENCY_ANALYSIS
        or event.event_kind in DAILY_EVENT_KINDS
    ):
        # Efficiency events and the four additive M5 daily kinds never alter
        # verification: a proposal or favorable analytical report can never
        # turn verification green or close custody (Plan Step 6 / T6).
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


def daily_commit_key(kind: str, window: EventWindow) -> str:
    """Canonical ``(kind, window)`` registry key for a committed daily payload.

    The key binds the closed daily kind to the exact half-open window
    boundaries, so a correction can target exactly one committed payload and
    a one-second boundary shift derives a different target.
    """
    return f"{kind}|{window.start.root.isoformat()}|{window.end.root.isoformat()}"


def _stream_collection_digest(items: Sequence[BaseModel]) -> str:
    """Canonical sha256 over a sorted collection of embedded contracts.

    The embedded ``daily_efficiency.v1`` collections (baselines, denominators,
    shadow measures) are already sorted by their contract validators, so the
    digest is deterministic and input-order independent.
    """
    material = canonical_json([item.model_dump(mode="json") for item in items])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _daily_report_updates(
    event: MaintenanceEvent, state: EfficiencyProjection, *, cursor: int
) -> dict[str, Any]:
    """Materialize the M5 daily-report stream updates (Plan Step 6 / T6).

    The report advances the report stream plus the derived baseline, coverage,
    and precision streams when the report actually carries that content
    (never fabricated when absent), and registers the committed payload in
    the keyed supersedes registry.
    """
    payload = event.payload.report
    commit_key = daily_commit_key(payload.kind, payload.window)
    new_sequence = state.sequence + 1
    payload_digest = canonical_digest(payload)
    updates: dict[str, Any] = {
        "occurrence_id": event.occurrence_id,
        "event_id": event.event_id,
        "classifier_version": event.classifier.classifier_version,
        "report_cursor": cursor,
        "report_digest": payload_digest,
        "committed_daily": {
            **state.committed_daily,
            commit_key: (new_sequence, payload_digest),
        },
    }
    if payload.baselines:
        updates["baseline_cursor"] = cursor
        updates["baseline_digest"] = _stream_collection_digest(payload.baselines)
    if payload.denominators:
        updates["coverage_cursor"] = cursor
        updates["coverage_digest"] = _stream_collection_digest(payload.denominators)
    if payload.shadow_measures:
        updates["precision_cursor"] = cursor
        updates["precision_digest"] = _stream_collection_digest(payload.shadow_measures)
    return updates


def _daily_cluster_updates(
    event: MaintenanceEvent, state: EfficiencyProjection, *, cursor: int
) -> dict[str, Any]:
    """Materialize the M5 daily-cluster stream updates (Plan Step 6 / T6)."""
    payload = event.payload.cluster
    commit_key = daily_commit_key(payload.kind, payload.window)
    new_sequence = state.sequence + 1
    payload_digest = canonical_digest(payload)
    return {
        "occurrence_id": event.occurrence_id,
        "event_id": event.event_id,
        "classifier_version": event.classifier.classifier_version,
        "cluster_cursor": cursor,
        "cluster_digest": payload_digest,
        "committed_daily": {
            **state.committed_daily,
            commit_key: (new_sequence, payload_digest),
        },
    }


def _daily_proposal_updates(
    event: MaintenanceEvent, state: EfficiencyProjection, *, cursor: int
) -> dict[str, Any]:
    """Materialize the M5 daily-proposal stream updates (Plan Step 6 / T6).

    The proposal is INERT (``auto_materialization`` is locked ``False`` by the
    T4 contract): it advances only the efficiency proposal stream and never
    grants ticket/initiative/repair operational semantics.
    """
    payload = event.payload.proposal
    commit_key = daily_commit_key(payload.kind, payload.window)
    new_sequence = state.sequence + 1
    payload_digest = canonical_digest(payload)
    return {
        "occurrence_id": event.occurrence_id,
        "event_id": event.event_id,
        "classifier_version": event.classifier.classifier_version,
        "proposal_cursor": cursor,
        "proposal_digest": payload_digest,
        "committed_daily": {
            **state.committed_daily,
            commit_key: (new_sequence, payload_digest),
        },
    }


def _daily_correction_updates(
    event: MaintenanceEvent, state: EfficiencyProjection, *, cursor: int
) -> tuple[dict[str, Any], CorrectionRecord]:
    """Validate and materialize one explicit daily correction (Plan Step 6).

    The declared keyed supersedes target (kind + exact half-open window +
    sha256 digest) is validated against the committed outputs registry; an
    uncommitted target or a digest that diverges from the committed payload
    FAILS CLOSED (``ValueError``) and nothing advances.  On success exactly
    one ``KEYED`` :class:`CorrectionRecord` is produced, targeting the
    DECLARED digest — never the immediately preceding stream digest — and the
    automatic ``LATE_EVIDENCE`` record is bypassed.
    """
    payload = event.payload.correction
    target_key = daily_commit_key(
        payload.supersedes_kind.value, payload.supersedes_window
    )
    committed = state.committed_daily.get(target_key)
    if committed is None:
        raise ValueError(
            "daily correction supersedes an uncommitted target "
            f"{target_key!r}; nothing applied"
        )
    committed_sequence, committed_digest = committed
    if committed_digest != payload.supersedes_digest:
        raise ValueError(
            "daily correction supersedes digest does not match the committed "
            f"target {target_key!r}: declared {payload.supersedes_digest!r} "
            f"!= committed {committed_digest!r}; nothing applied"
        )
    commit_key = daily_commit_key(payload.kind, payload.window)
    new_sequence = state.sequence + 1
    payload_digest = canonical_digest(payload)
    explicit_correction = CorrectionRecord(
        kind=CorrectionKind.KEYED,
        sequence=new_sequence,
        corrected_sequence=committed_sequence,
        prior_output_digest=payload.supersedes_digest,
        event_id=event.event_id,
        occurrence_id=event.occurrence_id,
        reason=payload.reason,
    )
    updates: dict[str, Any] = {
        "occurrence_id": event.occurrence_id,
        "event_id": event.event_id,
        "classifier_version": event.classifier.classifier_version,
        "correction_cursor": cursor,
        "correction_digest": payload_digest,
        "committed_daily": {
            **state.committed_daily,
            commit_key: (new_sequence, payload_digest),
        },
    }
    return updates, explicit_correction


def reduce_efficiency(
    event: MaintenanceEvent | OperationalEvent,
    state: EfficiencyProjection,
    *,
    cursor: int,
    event_digest: str,
) -> EfficiencyProjection:
    """Reduce an efficiency event into the efficiency projection.

    ``efficiency_analysis`` events and the four additive M5 daily kinds
    (report / cluster / proposal / correction) advance the efficiency
    projection; detection, audit_report, and M3 operational lifecycle events
    are a no-op (they never alter the efficiency projection).  Daily events
    advance their own independent stream cursors/digests, and an explicit
    daily correction validates its keyed supersedes target against committed
    outputs before appending exactly one ``KEYED`` correction.
    """
    if isinstance(event, OperationalEvent):
        return state
    if event.event_kind is EventKind.EFFICIENCY_ANALYSIS:
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
    if event.event_kind in DAILY_EVENT_KINDS:
        if event.event_kind is EventKind.DAILY_EFFICIENCY_REPORT:
            updates = _daily_report_updates(event, state, cursor=cursor)
        elif event.event_kind is EventKind.DAILY_EFFICIENCY_CLUSTER:
            updates = _daily_cluster_updates(event, state, cursor=cursor)
        elif event.event_kind is EventKind.DAILY_EFFICIENCY_PROPOSAL:
            updates = _daily_proposal_updates(event, state, cursor=cursor)
        else:  # DAILY_EFFICIENCY_CORRECTION
            updates, explicit_correction = _daily_correction_updates(
                event, state, cursor=cursor
            )
            return _advance(
                state,
                event=event,
                event_digest=event_digest,
                cursor=cursor,
                updates=updates,
                explicit_correction=explicit_correction,
            )
        return _advance(
            state,
            event=event,
            event_digest=event_digest,
            cursor=cursor,
            updates=updates,
        )
    return state


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
        event: MaintenanceEvent | OperationalEvent | dict[str, Any],
        *,
        cursor: int | None = None,
    ) -> ProjectionResult:
        """Apply one strict event to the projections, deduplicating exact repeats.

        * ``cursor`` is the source ledger sequence; when omitted it
          auto-increments from the previous source cursor.
        * The engine deduplicates by the canonical lifecycle idempotency key
          (M3 Step 2/4): legacy rows keep the occurrence-only key, M3
          operational rows derive the strict action key — so DISTINCT actions
          for ONE occurrence coexist while an exact retry is deduped.
        * A divergent duplicate (same lifecycle key, different digest) raises
          :class:`ProjectionConflictError` — nothing advances.
        * A verified recurrence carries a fresh occurrence id (enforced by the
          event contract), so it is applied as a new, causally linked
          occurrence with a fresh budget.
        """
        model = self._coerce(event)
        digest = canonical_digest(model)
        payload = json.loads(canonical_dumps(model))
        lifecycle_key = lifecycle_idempotency_key(payload)
        occurrence_id = (
            model.occurrence_id
            if isinstance(model, MaintenanceEvent)
            else model.occurrence.occurrence_id
        )

        if lifecycle_key in self._seen:
            if self._seen[lifecycle_key] == digest:
                return ProjectionResult(
                    self._custody,
                    self._verification,
                    self._efficiency,
                    ApplyDisposition.DEDUPED,
                )
            raise ProjectionConflictError(
                f"projection idempotency conflict for lifecycle key "
                f"{lifecycle_key!r} (occurrence {occurrence_id!r}): stored "
                f"digest {self._seen[lifecycle_key]} != incoming digest "
                f"{digest}; nothing applied"
            )
        self._seen[lifecycle_key] = digest

        prior_source_cursor = self._source_cursor
        if cursor is None:
            self._source_cursor += 1
        else:
            self._source_cursor = max(self._source_cursor, int(cursor))

        source = self._source_cursor
        try:
            self._custody = reduce_custody(
                model, self._custody, cursor=source, event_digest=digest
            )
            self._verification = reduce_verification(
                model, self._verification, cursor=source, event_digest=digest
            )
            self._efficiency = reduce_efficiency(
                model, self._efficiency, cursor=source, event_digest=digest
            )
        except Exception:
            # Fail closed: a rejected event (e.g. an explicit daily
            # correction whose keyed supersedes target does not match a
            # committed output) leaves NO trace — the idempotency
            # registration and the source cursor are rolled back so a
            # corrected retry still replays deterministically and a repeated
            # invalid emission keeps surfacing the rejection instead of
            # being silently deduped.
            self._seen.pop(lifecycle_key, None)
            self._source_cursor = prior_source_cursor
            raise

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

    def _coerce(
        self, event: MaintenanceEvent | OperationalEvent | dict[str, Any]
    ) -> MaintenanceEvent | OperationalEvent:
        """Strict-decode *event* into a Maintenance model (no writes)."""
        if isinstance(event, (MaintenanceEvent, OperationalEvent)):
            return event
        if isinstance(event, dict):
            try:
                return strict_loads(MaintenanceEvent, event)
            except MaintenanceCodecError:
                try:
                    return strict_loads(OperationalEvent, event)
                except MaintenanceCodecError as exc:
                    raise ValueError(
                        f"maintenance event strict decode failed: {exc}"
                    ) from exc
        raise ValueError(
            "event must be a MaintenanceEvent, OperationalEvent, or a canonical dict"
        )


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
    "DAILY_EVENT_KINDS",
    "daily_commit_key",
    "CheckpointOutcome",
    "CorrectionRecord",
    "CustodyProjection",
    "EfficiencyProjection",
    "ProjectionConflictError",
    "ProjectionEngine",
    "ProjectionFreshness",
    "ProjectionName",
    "ProjectionResult",
    "REQUIRED_CHECKPOINT_WINDOWS",
    "VerificationCoherence",
    "VerificationProjection",
    "reduce_custody",
    "reduce_efficiency",
    "reduce_verification",
    "replay",
]
