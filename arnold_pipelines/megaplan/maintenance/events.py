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
from arnold_pipelines.megaplan.maintenance.operations import (
    ActionTarget,
    EscalationReference,
    LeaseCoordinates,
    OccurrenceCoordinates,
    OwnerReceipts,
    PolicyVersionCoordinates,
    ProducerPrincipal,
    ProducerRole,
    RecurrenceReference,
    RunAuthorityCoordinates,
    WbcAttemptCoordinates,
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


# ---------------------------------------------------------------------------
# M3 Step 2: closed operational lifecycle vocabulary and occurrence-bound
# operational event (reference-only contracts; see maintenance.operations)
# ---------------------------------------------------------------------------
# The operational lifecycle is a CLOSED vocabulary: repair request, source
# change, installation, retrigger, progress observation, checkpoint
# verification, terminal verification, recurrence, and human escalation are
# DISTINCT actions that can never be collapsed into a generic success
# receipt (locked decision).  Every owner coordinate is an immutable
# reference from maintenance.operations; Maintenance never constructs an
# owner authority record.


class OperationalActionKind(str, Enum):
    """Closed operational lifecycle actions (M3 Step 2).

    Source change, installation, retrigger, progress observation,
    checkpoint verification, and terminal verification are separate events
    for one occurrence; there is deliberately NO generic success action.
    """

    REPAIR_REQUEST = "repair_request"
    SOURCE_CHANGE = "source_change"
    INSTALLATION = "installation"
    RETRIGGER = "retrigger"
    PROGRESS_OBSERVATION = "progress_observation"
    CHECKPOINT_VERIFICATION = "checkpoint_verification"
    TERMINAL_VERIFICATION = "terminal_verification"
    RECURRENCE = "recurrence"
    HUMAN_ESCALATION = "human_escalation"


class CheckpointWindowKind(str, Enum):
    """Canonical checkpoint windows (M3 Step 6 vocabulary).

    ``next_three_hour`` is the canonical horizon; legacy ``six_hour`` naming
    maps to it as a read-only compatibility alias (see
    :func:`canonical_checkpoint_window`) and never schedules a separate
    six-hour authority window.
    """

    IMMEDIATE = "immediate"
    FIVE_MINUTE = "five_minute"
    ONE_HOUR = "one_hour"
    NEXT_THREE_HOUR = "next_three_hour"


#: Legacy six-hour naming — a compatibility alias for NEXT_THREE_HOUR only.
SIX_HOUR_ALIAS: str = "six_hour"


def canonical_checkpoint_window(name: str) -> CheckpointWindowKind:
    """Resolve *name* to the canonical checkpoint window.

    ``six_hour`` maps to :attr:`CheckpointWindowKind.NEXT_THREE_HOUR` (read
    alias only); any other unknown name is rejected — a window is never
    guessed.
    """
    if name == SIX_HOUR_ALIAS:
        return CheckpointWindowKind.NEXT_THREE_HOUR
    try:
        return CheckpointWindowKind(name)
    except ValueError as exc:
        raise ValueError(
            f"unknown checkpoint window {name!r}; expected one of "
            f"{sorted(window.value for window in CheckpointWindowKind)} "
            f"or the alias {SIX_HOUR_ALIAS!r}"
        ) from exc


class VerifierProvenance(BaseModel):
    """Durable provenance of the distinct independent verifier principal.

    A verifier is distinct from the repair producer and carries durable
    provenance: the exact principal, the runtime/source digests it ran
    under, a locator reference to its credential/runtime envelope, the UTC
    observation instant, and direct owner-source read references.  A label,
    a separate PID, or liveness alone is never sufficient provenance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    principal: StrictStr
    runtime_digest: StrictStr
    source_digest: StrictStr
    credential_envelope_ref: OwnerRef | None = None
    observed_at: UtcTime
    direct_read_refs: tuple[OwnerRef, ...] = ()

    @field_validator("principal")
    @classmethod
    def _validate_principal(cls, value: str) -> str:
        if not value:
            raise ValueError("verifier principal must be a non-empty string")
        return value

    @field_validator("runtime_digest", "source_digest")
    @classmethod
    def _validate_digests(cls, value: str) -> str:
        return _validate_sha256_hex(value, what="verifier digest")

    @field_validator("direct_read_refs")
    @classmethod
    def _sort_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)


class RepairRequestPayload(BaseModel):
    """Closed payload for a canonical repair-request action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["repair_request"] = "repair_request"
    request_id: StrictStr
    request_ref: OwnerRef | None = None

    @field_validator("request_id")
    @classmethod
    def _validate_request(cls, value: str) -> str:
        if not value:
            raise ValueError("request_id must be a non-empty string")
        return value


class SourceChangePayload(BaseModel):
    """Closed payload for a source-change action (distinct from install)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["source_change"] = "source_change"
    change_ref: OwnerRef | None = None
    source_digest: StrictStr | None = None

    @field_validator("source_digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        return _validate_sha256_hex(value, what="source-change digest")


class InstallationPayload(BaseModel):
    """Closed payload for an installation action (distinct from retrigger)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["installation"] = "installation"
    install_ref: OwnerRef | None = None
    install_digest: StrictStr | None = None

    @field_validator("install_digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        return _validate_sha256_hex(value, what="installation digest")


class RetriggerPayload(BaseModel):
    """Closed payload for a retrigger action (distinct from install)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["retrigger"] = "retrigger"
    retrigger_ref: OwnerRef | None = None
    reason: StrictStr | None = None

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("retrigger reason must be a non-empty string when present")
        return value


class ProgressObservationPayload(BaseModel):
    """Closed payload for a progress-observation action.

    Progress is durable authoritative evidence only when independently
    verified; observation references never close custody by themselves.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["progress_observation"] = "progress_observation"
    progress_refs: tuple[OwnerRef, ...] = ()
    observation_ref: OwnerRef | None = None

    @field_validator("progress_refs")
    @classmethod
    def _sort_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)


class CheckpointVerificationPayload(BaseModel):
    """Closed payload for one checkpoint-verification action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["checkpoint_verification"] = "checkpoint_verification"
    checkpoint: CheckpointWindowKind
    checkpoint_ref: OwnerRef | None = None
    evidence_refs: tuple[OwnerRef, ...] = ()

    @field_validator("evidence_refs")
    @classmethod
    def _sort_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)


class TerminalVerificationPayload(BaseModel):
    """Closed payload for the terminal-verification action.

    Only a durable distinct verifier with direct owner-source reads and
    accepted blocker-specific negative controls may author terminal
    verification (epic invariant); the repair producer can never carry this
    payload.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["terminal_verification"] = "terminal_verification"
    verifier: VerifierProvenance
    terminal_reason: StrictStr
    negative_control_refs: tuple[OwnerRef, ...] = ()
    verification_ref: OwnerRef | None = None

    @field_validator("terminal_reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        if not value:
            raise ValueError("terminal_reason must be a non-empty string")
        return value

    @field_validator("negative_control_refs")
    @classmethod
    def _sort_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)


class RecurrencePayload(BaseModel):
    """Closed payload for a verified-recurrence action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["recurrence"] = "recurrence"
    recurrence: RecurrenceReference


class HumanEscalationPayload(BaseModel):
    """Closed payload for a human-escalation action (never a waiver)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["human_escalation"] = "human_escalation"
    escalation: EscalationReference


OperationalPayload = Annotated[
    RepairRequestPayload
    | SourceChangePayload
    | InstallationPayload
    | RetriggerPayload
    | ProgressObservationPayload
    | CheckpointVerificationPayload
    | TerminalVerificationPayload
    | RecurrencePayload
    | HumanEscalationPayload,
    Field(discriminator="kind"),
]


class OperationalEvent(BaseModel):
    """Closed occurrence-bound operational lifecycle event (reference-only).

    Binds the canonical M7 occurrence and lease coordinates, Run Authority
    grant/fence, M6A WBC attempt, policy version, action target, producer
    principal, and owner receipts to exactly one closed action kind and its
    discriminated payload.  ``action_kind`` must match the payload's
    ``kind`` exactly — a generic success receipt does not exist, and every
    distinct action (source change, installation, retrigger, progress,
    checkpoint verification, terminal verification, recurrence, escalation)
    remains a separate event for one occurrence.  A recurrence payload must
    name a DIFFERENT predecessor occurrence.  All models are frozen, forbid
    unknown fields, and round-trip through the single canonical codec.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    event_id: StrictStr
    action_kind: OperationalActionKind
    occurrence: OccurrenceCoordinates
    lease: LeaseCoordinates
    run_authority: RunAuthorityCoordinates
    wbc_attempt: WbcAttemptCoordinates | None = None
    policy: PolicyVersionCoordinates
    target: ActionTarget
    producer: ProducerPrincipal
    owner_receipts: OwnerReceipts = Field(default_factory=OwnerReceipts)
    observed_at: UtcTime
    payload: OperationalPayload
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

    @field_validator("event_id")
    @classmethod
    def _validate_event_id(cls, value: str) -> str:
        if not value:
            raise ValueError("operational event_id must be a non-empty string")
        return value

    @model_validator(mode="after")
    def _enforce_operational_invariants(self) -> OperationalEvent:
        # 1. The discriminated payload kind must match the action kind: a
        #    generic success receipt does not exist and action kinds can
        #    never be collapsed.
        if self.payload.kind != self.action_kind.value:
            raise ValueError(
                f"action_kind {self.action_kind.value!r} does not match payload "
                f"kind {self.payload.kind!r}"
            )
        # 2. A recurrence must create a FRESH canonical occurrence: the
        #    predecessor occurrence must differ from the enclosing one.
        if (
            self.action_kind is OperationalActionKind.RECURRENCE
            and self.payload.kind == "recurrence"
            and self.payload.recurrence.predecessor_occurrence_id
            == self.occurrence.occurrence_id
        ):
            raise ValueError(
                "a verified recurrence requires a fresh canonical occurrence; "
                "predecessor_occurrence_id equals the enclosing occurrence_id"
            )
        # 3. Terminal verification can never be authored by the repair
        #    producer (epic invariant: a repair actor cannot verify itself).
        if (
            self.action_kind is OperationalActionKind.TERMINAL_VERIFICATION
            and self.producer.role is ProducerRole.REPAIR_PRODUCER
        ):
            raise ValueError(
                "terminal verification cannot be authored by a repair producer; "
                "a distinct verifier principal is required"
            )
        return self

    @classmethod
    def build(
        cls,
        *,
        event_id: str,
        occurrence: OccurrenceCoordinates,
        lease: LeaseCoordinates,
        run_authority: RunAuthorityCoordinates,
        policy: PolicyVersionCoordinates,
        target: ActionTarget,
        producer: ProducerPrincipal,
        payload: OperationalPayload,
        observed_at: UtcTime | datetime,
        wbc_attempt: WbcAttemptCoordinates | None = None,
        owner_receipts: OwnerReceipts | None = None,
        extensions: Extensions | None = None,
    ) -> OperationalEvent:
        """Construct an operational event with the action kind derived.

        ``action_kind`` is derived from the payload's ``kind`` so callers
        can never mismatch them; all invariants are enforced by the model
        validator.
        """
        return cls(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            event_id=event_id,
            action_kind=OperationalActionKind(payload.kind),
            occurrence=occurrence,
            lease=lease,
            run_authority=run_authority,
            wbc_attempt=wbc_attempt,
            policy=policy,
            target=target,
            producer=producer,
            owner_receipts=owner_receipts if owner_receipts is not None else OwnerReceipts(),
            observed_at=observed_at,
            payload=payload,
            extensions=extensions,
        )


def operational_event_digest(event: OperationalEvent) -> str:
    """Return the canonical content digest of *event*."""
    return canonical_digest(event)


__all__ = [
    "AuditFinding",
    "AuditReport",
    "CheckpointVerificationPayload",
    "CheckpointWindowKind",
    "ClassifierInfo",
    "DetectionEvent",
    "EfficiencyAnalysis",
    "EscalationReference",
    "EventKind",
    "HumanEscalationPayload",
    "InstallationPayload",
    "MaintenanceEvent",
    "MaintenancePayload",
    "OccurrenceBudget",
    "OperationalActionKind",
    "OperationalEvent",
    "OperationalPayload",
    "ProgressObservationPayload",
    "ProjectionCoordinates",
    "RecurrenceLink",
    "RecurrencePayload",
    "RepairRequestPayload",
    "RetriggerPayload",
    "RootCauseCluster",
    "SIX_HOUR_ALIAS",
    "SourceChangePayload",
    "TerminalVerificationPayload",
    "VerifierProvenance",
    "canonical_checkpoint_window",
    "event_digest",
    "occurrence_idempotency_key",
    "operational_event_digest",
    "verified_recurrence",
]
