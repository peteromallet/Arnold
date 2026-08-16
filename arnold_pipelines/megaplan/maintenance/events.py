"""Closed Maintenance event contracts with occurrence-scoped recurrence.

This module freezes the common :class:`MaintenanceEvent` envelope and the
closed discriminated :class:`DetectionEvent`, :class:`EfficiencyAnalysis`,
and :class:`AuditReport` payloads consumed by the incident-ledger append
(T10), the projections (T11), and every M2 shadow consumer.  It builds
exclusively on the T1 foundation (strict identities, locator-only immutable
owner references, validated UTC times, half-open windows, watermarks,
lateness, and the single canonical codec) and on the T2 fail-closed
vocabulary (SD1 evidence precedence).

Locked decision SD2 — occurrence identity is the idempotency, lease, and
budget scope (frozen, do not re-litigate)::

    * :attr:`MaintenanceEvent.occurrence_id` — not the signature and not
      the cluster — is the sole idempotency scope.  Repeated events for one
      occurrence deduplicate on ``occurrence_id`` plus canonical digest.
    * A *verified recurrence* creates a deterministically linked NEW
      occurrence: it requires a fresh ``occurrence_id`` (and a fresh
      ``event_id``), records a causal :class:`RecurrenceLink` to the
      predecessor event/occurrence, and carries a fresh
      :class:`OccurrenceBudget` scoped to the new occurrence.
    * The signature / root-cause cluster (:class:`RootCauseCluster`) is
      analytical grouping only: it is preserved across recurrences but
      never participates in idempotency, lease, or budget scope.

The envelope preserves classifier version / confidence / impact,
signatures and clusters, occurrence identity, custody/lease/fence
references, causality, recurrence, resolution-proof references, and
projection coordinates.  All models are frozen, forbid unknown fields
(except the explicit ``extensions`` map), and round-trip through the single
canonical codec (``canonical_dumps`` / ``strict_loads``).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.maintenance.contracts import precedence_rank
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    AttemptId,
    ChainId,
    EnvironmentId,
    EventWindow,
    Extensions,
    Lateness,
    ModelId,
    OwnerRef,
    PlanId,
    ProfileId,
    RunId,
    StageId,
    TenantId,
    UtcTime,
    Watermark,
    canonical_digest,
    classify_lateness,
)

_SHA256_HEX = frozenset("0123456789abcdef")


def _validate_sha256_hex(value: str | None, *, what: str) -> str | None:
    """Reject malformed sha256 hex coordinates (None stays explicit null)."""
    if value is None:
        return None
    if len(value) != 64 or any(char not in _SHA256_HEX for char in value):
        raise ValueError(f"{what} must be a 64-character lowercase sha256 hex digest")
    return value


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic reference order (SD1 rank, owner, locator, digest, cursor).

    References inside one category (custody, fences, resolution proof) are
    ordered by precedence rank first so events encode SD1 evidence precedence
    and never treat mutable status projections as authority.
    """
    return tuple(
        sorted(
            refs,
            key=lambda ref: (
                precedence_rank(ref.owner) if precedence_rank(ref.owner) is not None else 0,
                ref.owner,
                ref.locator,
                ref.digest or "",
                ref.cursor or "",
            ),
        )
    )


# ---------------------------------------------------------------------------
# Event kinds (closed vocabulary)
# ---------------------------------------------------------------------------


class EventKind(str, Enum):
    """Closed discriminated Maintenance event kinds."""

    DETECTION = "detection"
    EFFICIENCY_ANALYSIS = "efficiency_analysis"
    AUDIT_REPORT = "audit_report"


# ---------------------------------------------------------------------------
# Shared classifier / grouping / recurrence primitives
# ---------------------------------------------------------------------------


class ClassifierInfo(BaseModel):
    """Classifier version, confidence, and impact preserved on every event.

    Missing values stay explicit ``None`` (never guessed or defaulted).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    classifier_version: StrictStr
    confidence: float | None = None
    impact: StrictStr | None = None

    @field_validator("classifier_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not value:
            raise ValueError("classifier_version must be a non-empty string")
        return value

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"classifier confidence must be in [0, 1], got {value}")
        return value

    @field_validator("impact")
    @classmethod
    def _validate_impact(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("impact must be a non-empty string when present")
        return value


class RootCauseCluster(BaseModel):
    """Signature / root-cause cluster grouping.

    Analytical grouping only: it groups recurrences for analysis but is
    never the idempotency, lease, or budget scope (SD2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    signature: StrictStr
    cluster_id: StrictStr | None = None

    @field_validator("signature")
    @classmethod
    def _validate_signature(cls, value: str) -> str:
        if not value:
            raise ValueError("signature must be a non-empty string")
        return value

    @field_validator("cluster_id")
    @classmethod
    def _validate_cluster(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("cluster_id must be a non-empty string when present")
        return value


class RecurrenceLink(BaseModel):
    """Causal link from a verified recurrence to its predecessor.

    A verified recurrence always points at a DIFFERENT occurrence and a
    DIFFERENT event than the one carrying the link: fresh occurrence
    identity is required (SD2).  The link is validated against the
    enclosing event in :class:`MaintenanceEvent`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verified: bool
    predecessor_event_id: StrictStr
    predecessor_occurrence_id: StrictStr

    @field_validator("predecessor_event_id", "predecessor_occurrence_id")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "recurrence predecessor identities must be non-empty strings"
            )
        return value


class OccurrenceBudget(BaseModel):
    """Occurrence-scoped bounded budget (SD2).

    The budget is scoped to exactly one occurrence: a verified recurrence
    constructs a fresh :class:`OccurrenceBudget` for the new occurrence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_attempts: int
    attempts_used: int = 0

    @field_validator("max_attempts")
    @classmethod
    def _validate_max(cls, value: int) -> int:
        if value < 1:
            raise ValueError(f"occurrence budget max_attempts must be >= 1, got {value}")
        return value

    @field_validator("attempts_used")
    @classmethod
    def _validate_used(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"occurrence budget attempts_used must be >= 0, got {value}")
        return value

    @model_validator(mode="after")
    def _check_within_budget(self) -> OccurrenceBudget:
        if self.attempts_used > self.max_attempts:
            raise ValueError(
                f"occurrence budget exhausted: attempts_used={self.attempts_used} "
                f"> max_attempts={self.max_attempts}"
            )
        return self


class ProjectionCoordinates(BaseModel):
    """Projection sequence/cursor/digest coordinates attached to an event.

    ``source_digest`` and ``output_digest`` are optional sha256 hex digests;
    absent digests stay explicit ``None`` (never guessed or zeroed).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    projection: StrictStr
    sequence: int
    cursor: StrictStr | None = None
    source_digest: StrictStr | None = None
    output_digest: StrictStr | None = None

    @field_validator("projection")
    @classmethod
    def _validate_projection(cls, value: str) -> str:
        if not value:
            raise ValueError("projection identity must be a non-empty string")
        return value

    @field_validator("sequence")
    @classmethod
    def _validate_sequence(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"projection sequence must be >= 0, got {value}")
        return value

    @field_validator("cursor")
    @classmethod
    def _validate_cursor(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("projection cursor must be a non-empty string when present")
        return value

    @field_validator("source_digest", "output_digest")
    @classmethod
    def _validate_digests(cls, value: str | None) -> str | None:
        return _validate_sha256_hex(value, what="projection digest")


# ---------------------------------------------------------------------------
# Closed discriminated payloads
# ---------------------------------------------------------------------------


class DetectionEvent(BaseModel):
    """Closed payload for a maintenance detection observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["detection"] = "detection"
    detection_kind: StrictStr
    subject: StrictStr | None = None
    severity: StrictStr | None = None
    description: StrictStr | None = None
    evidence_refs: tuple[OwnerRef, ...] = ()

    @field_validator("detection_kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        if not value:
            raise ValueError("detection_kind must be a non-empty string")
        return value

    @field_validator("subject", "severity", "description")
    @classmethod
    def _validate_optional(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("detection fields must be non-empty strings when present")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _sort_evidence(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)


class EfficiencyAnalysis(BaseModel):
    """Closed payload for an efficiency analysis report.

    Missing denominators stay explicit ``None`` — never coerced to zero or
    to green.  Censored durations and bucket counts are surfaced without
    inventing baselines.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["efficiency_analysis"] = "efficiency_analysis"
    product: StrictStr
    coverage_denominator: int | None = None
    covered_count: int | None = None
    censored_duration_seconds: float | None = None
    bucket_counts: dict[str, int] = Field(default_factory=dict)

    @field_validator("product")
    @classmethod
    def _validate_product(cls, value: str) -> str:
        if not value:
            raise ValueError("efficiency analysis product must be a non-empty string")
        return value

    @field_validator("coverage_denominator", "covered_count")
    @classmethod
    def _validate_counts(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 0:
            raise ValueError(f"efficiency counts must be >= 0, got {value}")
        return value

    @field_validator("censored_duration_seconds")
    @classmethod
    def _validate_censored(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if value < 0:
            raise ValueError(
                f"censored_duration_seconds must be >= 0, got {value}"
            )
        return value

    @model_validator(mode="after")
    def _check_coverage(self) -> EfficiencyAnalysis:
        if (
            self.coverage_denominator is not None
            and self.covered_count is not None
            and self.covered_count > self.coverage_denominator
        ):
            raise ValueError(
                f"covered_count={self.covered_count} exceeds "
                f"coverage_denominator={self.coverage_denominator}"
            )
        return self


class AuditFinding(BaseModel):
    """One typed finding inside an :class:`AuditReport`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: StrictStr
    severity: StrictStr | None = None
    message: StrictStr
    evidence_refs: tuple[OwnerRef, ...] = ()

    @field_validator("finding_id", "message")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("audit finding id/message must be non-empty strings")
        return value

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("audit finding severity must be non-empty when present")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _sort_evidence(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)


class AuditReport(BaseModel):
    """Closed payload for an audit report."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["audit_report"] = "audit_report"
    report_type: StrictStr
    verdict: StrictStr | None = None
    summary: StrictStr | None = None
    findings: tuple[AuditFinding, ...] = ()

    @field_validator("report_type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        if not value:
            raise ValueError("audit report_type must be a non-empty string")
        return value

    @field_validator("verdict", "summary")
    @classmethod
    def _validate_optional(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("audit fields must be non-empty strings when present")
        return value


MaintenancePayload = Annotated[
    DetectionEvent | EfficiencyAnalysis | AuditReport,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# The common MaintenanceEvent envelope
# ---------------------------------------------------------------------------


class MaintenanceEvent(BaseModel):
    """Closed, strict common Maintenance event envelope.

    Carries the occurrence identity (sole idempotency/lease/budget scope,
    SD2), signature/cluster grouping, causality/recurrence, custody/lease/
    fence references, resolution proof, projection coordinates, and the
    closed discriminated payload.  ``event_kind`` must match the payload's
    ``kind`` exactly; a recurrence must name a different predecessor
    occurrence and event; ``lateness`` must equal the watermark
    classification of ``event_time``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)

    #: Unique identity of this event (fresh per occurrence; never reused).
    event_id: StrictStr

    #: Occurrence identity — the SOLE idempotency, lease, and budget scope
    #: (SD2).  A verified recurrence requires a fresh value.
    occurrence_id: StrictStr

    event_kind: EventKind

    #: Validated UTC instant at which the event was recorded.
    observed_at: UtcTime

    #: Validated UTC instant at which the event occurred.
    event_time: UtcTime

    #: Half-open reporting window ``[start, end)``.
    window: EventWindow

    #: Watermark against which lateness is classified (closed boundary).
    watermark: Watermark

    #: Derived lateness; validated to equal ``classify_lateness(event_time,
    #: watermark)``.
    lateness: Lateness

    # Typed source identities (explicit null when unknown — never guessed).
    environment: EnvironmentId | None = None
    tenant: TenantId | None = None
    run: RunId | None = None
    chain: ChainId | None = None
    plan: PlanId | None = None
    stage: StageId | None = None
    model: ModelId | None = None
    profile: ProfileId | None = None
    attempt: AttemptId | None = None

    classifier: ClassifierInfo
    cluster: RootCauseCluster
    recurrence: RecurrenceLink | None = None

    #: Custody/lease references (locator-only immutable references).
    custody_refs: tuple[OwnerRef, ...] = ()
    #: Fence references (locator-only immutable references).
    fence_refs: tuple[OwnerRef, ...] = ()
    #: Resolution-proof references (locator-only immutable references).
    resolution_proof: tuple[OwnerRef, ...] = ()

    projection: ProjectionCoordinates | None = None
    budget: OccurrenceBudget

    payload: MaintenancePayload

    #: The only place unknown keys are allowed.
    extensions: Extensions | None = None

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("event_id", "occurrence_id")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        if not value:
            raise ValueError("event_id/occurrence_id must be non-empty strings")
        return value

    @field_validator("custody_refs", "fence_refs", "resolution_proof")
    @classmethod
    def _sort_ref_lists(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @property
    def idempotency_key(self) -> str:
        """Occurrence identity is the sole idempotency scope (SD2)."""
        return self.occurrence_id

    @model_validator(mode="after")
    def _enforce_event_invariants(self) -> MaintenanceEvent:
        # 1. Discriminated payload kind must match the envelope kind.
        if self.payload.kind != self.event_kind.value:
            raise ValueError(
                f"event_kind {self.event_kind.value!r} does not match payload "
                f"kind {self.payload.kind!r}"
            )

        # 2. Lateness must equal the watermark classification (deterministic).
        expected_lateness = classify_lateness(self.event_time, self.watermark)
        if self.lateness != expected_lateness:
            raise ValueError(
                f"lateness {self.lateness!r} does not match watermark "
                f"classification {expected_lateness!r} for event_time "
                f"{self.event_time.root.isoformat()}"
            )

        # 3. A recurrence must point at a DIFFERENT occurrence and event:
        #    verified recurrence requires fresh occurrence identity (SD2).
        if self.recurrence is not None:
            if self.recurrence.predecessor_occurrence_id == self.occurrence_id:
                raise ValueError(
                    "a verified recurrence requires a fresh occurrence id; "
                    f"predecessor_occurrence_id {self.recurrence.predecessor_occurrence_id!r} "
                    "equals the enclosing occurrence_id"
                )
            if self.recurrence.predecessor_event_id == self.event_id:
                raise ValueError(
                    "a verified recurrence requires a fresh event id; "
                    f"predecessor_event_id {self.recurrence.predecessor_event_id!r} "
                    "equals the enclosing event_id"
                )
            if not self.recurrence.verified:
                raise ValueError(
                    "an unverified recurrence link is not supported; "
                    "recurrence must be deterministically verified"
                )
        return self

    @classmethod
    def build(
        cls,
        *,
        event_id: str,
        occurrence_id: str,
        observed_at: UtcTime | datetime,
        event_time: UtcTime | datetime,
        window: EventWindow,
        watermark: Watermark,
        classifier: ClassifierInfo,
        cluster: RootCauseCluster,
        budget: OccurrenceBudget,
        payload: DetectionEvent | EfficiencyAnalysis | AuditReport,
        environment: EnvironmentId | str | None = None,
        tenant: TenantId | str | None = None,
        run: RunId | str | None = None,
        chain: ChainId | str | None = None,
        plan: PlanId | str | None = None,
        stage: StageId | str | None = None,
        model: ModelId | str | None = None,
        profile: ProfileId | str | None = None,
        attempt: AttemptId | str | None = None,
        recurrence: RecurrenceLink | None = None,
        custody_refs: Sequence[OwnerRef] = (),
        fence_refs: Sequence[OwnerRef] = (),
        resolution_proof: Sequence[OwnerRef] = (),
        projection: ProjectionCoordinates | None = None,
        extensions: Extensions | None = None,
    ) -> MaintenanceEvent:
        """Construct an event with ``lateness`` derived from the watermark.

        Callers cannot supply a lateness value through this entry point; it
        is always derived as ``classify_lateness(event_time, watermark)``
        and validated by the model validator.
        """
        return cls(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            event_id=event_id,
            occurrence_id=occurrence_id,
            event_kind=EventKind(payload.kind),
            observed_at=observed_at,
            event_time=event_time,
            window=window,
            watermark=watermark,
            lateness=classify_lateness(event_time, watermark),
            environment=environment,
            tenant=tenant,
            run=run,
            chain=chain,
            plan=plan,
            stage=stage,
            model=model,
            profile=profile,
            attempt=attempt,
            classifier=classifier,
            cluster=cluster,
            recurrence=recurrence,
            custody_refs=tuple(custody_refs),
            fence_refs=tuple(fence_refs),
            resolution_proof=tuple(resolution_proof),
            projection=projection,
            budget=budget,
            payload=payload,
            extensions=extensions,
        )


def verified_recurrence(
    *,
    predecessor: MaintenanceEvent,
    new_event_id: str,
    new_occurrence_id: str,
    observed_at: UtcTime | datetime,
    event_time: UtcTime | datetime,
    window: EventWindow,
    watermark: Watermark,
    budget: OccurrenceBudget,
    payload: DetectionEvent | EfficiencyAnalysis | AuditReport,
    environment: EnvironmentId | str | None = None,
    tenant: TenantId | str | None = None,
    run: RunId | str | None = None,
    chain: ChainId | str | None = None,
    plan: PlanId | str | None = None,
    stage: StageId | str | None = None,
    model: ModelId | str | None = None,
    profile: ProfileId | str | None = None,
    attempt: AttemptId | str | None = None,
    classifier: ClassifierInfo | None = None,
    custody_refs: Sequence[OwnerRef] = (),
    fence_refs: Sequence[OwnerRef] = (),
    resolution_proof: Sequence[OwnerRef] = (),
    projection: ProjectionCoordinates | None = None,
    extensions: Extensions | None = None,
) -> MaintenanceEvent:
    """Deterministically construct a VERIFIED recurrence (SD2).

    A verified recurrence REQUIRES a fresh ``new_occurrence_id`` (and a
    fresh ``new_event_id``), links causally to *predecessor* via a
    :class:`RecurrenceLink`, preserves the predecessor's signature /
    root-cause-cluster grouping (analytical grouping only), and carries a
    fresh occurrence-scoped *budget*.  The event idempotency key is the new
    occurrence id — repeated recurrence construction for the same
    occurrence deduplicates, while a second recurrence with a different
    occurrence id remains causally linked.

    Raises:
        ValueError: if ``new_occurrence_id`` equals the predecessor's
            occurrence id, if ``new_event_id`` equals the predecessor's
            event id, or if the classifier/cluster/budget are invalid.
    """
    if new_occurrence_id == predecessor.occurrence_id:
        raise ValueError(
            "a verified recurrence requires a fresh occurrence id; "
            f"{new_occurrence_id!r} is already used by the predecessor"
        )
    if new_event_id == predecessor.event_id:
        raise ValueError(
            "a verified recurrence requires a fresh event id; "
            f"{new_event_id!r} is already used by the predecessor"
        )
    return MaintenanceEvent.build(
        event_id=new_event_id,
        occurrence_id=new_occurrence_id,
        observed_at=observed_at,
        event_time=event_time,
        window=window,
        watermark=watermark,
        classifier=classifier if classifier is not None else predecessor.classifier,
        cluster=predecessor.cluster,
        budget=budget,
        payload=payload,
        environment=environment,
        tenant=tenant,
        run=run,
        chain=chain,
        plan=plan,
        stage=stage,
        model=model,
        profile=profile,
        attempt=attempt,
        recurrence=RecurrenceLink(
            verified=True,
            predecessor_event_id=predecessor.event_id,
            predecessor_occurrence_id=predecessor.occurrence_id,
        ),
        custody_refs=custody_refs,
        fence_refs=fence_refs,
        resolution_proof=resolution_proof,
        projection=projection,
        extensions=extensions,
    )


def occurrence_idempotency_key(event: MaintenanceEvent) -> str:
    """Return the occurrence-scoped idempotency key for *event* (SD2).

    The occurrence identity — not the signature and not the cluster — is the
    sole idempotency, lease, and budget scope.
    """
    return event.occurrence_id


def event_digest(event: MaintenanceEvent) -> str:
    """Return the canonical content digest of *event*."""
    return canonical_digest(event)


__all__ = [
    "AuditFinding",
    "AuditReport",
    "ClassifierInfo",
    "DetectionEvent",
    "EfficiencyAnalysis",
    "EventKind",
    "MaintenanceEvent",
    "MaintenancePayload",
    "OccurrenceBudget",
    "ProjectionCoordinates",
    "RecurrenceLink",
    "RootCauseCluster",
    "event_digest",
    "occurrence_idempotency_key",
    "verified_recurrence",
]
