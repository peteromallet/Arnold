"""M5 efficiency contracts: compatibility seam and strict observation family.

This module is the M5 contract foundation over the existing Maintenance
ledger.  It owns two responsibilities:

1. **Compatibility seam (Plan Step 1 / T1).**  A machine-checked registry
   maps every planned M5 payload onto the existing analytical contracts so
   M5 never creates a competing representation of an existing analytical
   fact:

   * ``EFFICIENCY_ANALYSIS`` (M4 operational per-window reports) are
     **consumed inputs** — M5 never re-emits them and
     :func:`~arnold_pipelines.megaplan.maintenance.operational_reporting.read_committed_report_events`
     remains the only operational report scan;
   * ``AUDIT_REPORT`` is an **intentionally parallel legacy lineage** with
     no conversion in either direction;
   * the envelope :class:`~arnold_pipelines.megaplan.maintenance.events.RootCauseCluster`
     is **reused verbatim** as the signature carrier on every M5 event —
     every M5 cluster event's envelope ``cluster.signature`` must equal its
     payload root-cause fingerprint;
   * :class:`~arnold_pipelines.megaplan.maintenance.projections.CorrectionRecord`
     projection semantics are **reused with explicit keyed targets**
     (``supersedes`` kind + window + digest, Step 6) instead of the
     automatic ``LATE_EVIDENCE`` correction.

   The four additive closed kinds ``DAILY_EFFICIENCY_REPORT``,
   ``DAILY_EFFICIENCY_CLUSTER``, ``DAILY_EFFICIENCY_PROPOSAL``, and
   ``DAILY_EFFICIENCY_CORRECTION`` are declared here with their
   ``daily_efficiency.v1`` payload identities.  They are strictly disjoint
   from the legacy vocabulary, so legacy event serialization is never
   widened and no M5 event can strict-decode as a legacy payload (or vice
   versa).  The full typed daily payloads land in later steps (T3/T4); the
   seam carrier :class:`DailyEfficiencyPayloadId` exists only to
   machine-check the boundary now.

2. **Observation and statistics family (Plan Step 2 / T2).**  Frozen,
   strict, versioned contracts for normalized cohort identity
   (:class:`EfficiencyCohortIdentity`), completed and right-censored
   duration observations (:class:`DurationObservation`), baseline snapshots
   with conservative quantile bounds (:class:`BaselineSnapshot` /
   :class:`QuantileBounds`), metric denominators and coverage
   (:class:`DenominatorCoverage`), and shadow-evaluation measures
   (:class:`ShadowMeasure`).  Missing numerators, denominators, costs,
   quality, and realized savings are encoded as explicit ``null`` /
   typed-unavailable states — never coerced to zero or to green.

3. **Finding, economics, and root-cause family (Plan Step 3 / T3).**
   Typed dwell, loop, mismatch, idle-handoff, and accepted-outcome
   economics payloads (:class:`DwellFinding`, :class:`LoopFinding`,
   :class:`IdleHandoffFinding`, :class:`RouteMismatchFinding`,
   :class:`AcceptedOutcomeEconomics`) plus root-cause candidates
   (:class:`RootCauseCandidate` / :class:`RootCauseAlternative`) with
   denominator-required coverage and exact reference bundles.

4. **Daily report, cluster, proposal, and correction contracts
   (Plan Step 4 / T4).**  The strict daily report (:class:`DailyEfficiencyReport`),
   inert proposal (:class:`DailyEfficiencyProposal`), and digest-linked
   correction (:class:`DailyEfficiencyCorrection`) payloads with exact
   half-open ``EventWindow`` boundaries, plus the LOCKED occurrence-ID
   derivations for reports, clusters, cross-window proposals, and
   corrections.  Proposal occurrence IDs are stable across windows
   (``daily_efficiency_proposal|{sha256(proposal_key)}`` over the locked
   proposal key — SD3), every payload validates its occurrence ID against
   the locked derivation (divergent identity reuse is rejected), and
   corrections carry validated keyed supersedes targets (kind + window +
   digest — SD4).

All models are frozen, forbid unknown fields, and round-trip through the
single canonical codec (``canonical_dumps`` / ``strict_loads``); references
are stored in canonical sorted order so hashing is input-order independent.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.maintenance.contracts import precedence_rank
from arnold_pipelines.megaplan.maintenance.events import (
    AuditReport,
    EfficiencyAnalysis,
    RootCauseCluster,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    EventWindow,
    ModelId,
    OwnerRef,
    ProfileId,
    StageId,
    UtcTime,
    canonical_digest,
    canonical_dumps,
    canonical_json,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.projections import CorrectionRecord

# ---------------------------------------------------------------------------
# Settled identity constants
# ---------------------------------------------------------------------------

#: Contract identity of every additive M5 payload (locked in the plan).
DAILY_EFFICIENCY_CONTRACT_ID: str = "daily_efficiency.v1"

#: Closed legacy Maintenance analytical kinds (M2/M4 vocabulary).  M5 daily
#: kinds are strictly disjoint from this set: legacy event serialization is
#: never widened with optional fields and no cross-decoding is possible.
LEGACY_MAINTENANCE_KINDS: frozenset[str] = frozenset(
    {"detection", "efficiency_analysis", "audit_report"}
)

#: The only kinds surfaced by ``read_committed_report_events`` (the single
#: operational report scan).  Daily kinds must never join this set.
OPERATIONAL_REPORT_SCAN_KINDS: frozenset[str] = frozenset({"efficiency_analysis"})

#: Existing analytical contracts referenced by the compatibility registry.
LEGACY_CONTRACT_NAMES: frozenset[str] = frozenset(
    {"EFFICIENCY_ANALYSIS", "AUDIT_REPORT", "RootCauseCluster", "CorrectionRecord"}
)


# ---------------------------------------------------------------------------
# T1: machine-checked compatibility registry
# ---------------------------------------------------------------------------


class CompatibilityRole(str, Enum):
    """How M5 relates to one existing analytical contract."""

    CONSUMED_INPUT = "consumed_input"
    PARALLEL_LEGACY = "parallel_legacy"
    REUSED = "reused"
    KEYED_EXTENSION = "keyed_extension"


class CompatibilityEntry(BaseModel):
    """One machine-checked compatibility binding to an existing contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract: StrictStr
    role: CompatibilityRole
    #: Machine-checkable binding description: the exact reuse rule that M5
    #: payloads must obey (never a free-form note).
    binding: StrictStr
    note: StrictStr | None = None

    @field_validator("contract", "binding")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("registry contract/binding must be non-empty strings")
        return value


#: The settled compatibility registry.  Exactly these four existing contracts
#: are referenced by M5; the invariant checker refuses additions, removals,
#: and role drift.
EFFICIENCY_COMPATIBILITY_REGISTRY: tuple[CompatibilityEntry, ...] = (
    CompatibilityEntry(
        contract="EFFICIENCY_ANALYSIS",
        role=CompatibilityRole.CONSUMED_INPUT,
        binding=(
            "M4 operational per-window reports are consumed inputs; M5 never "
            "re-emits them and read_committed_report_events remains the only "
            "operational report scan"
        ),
    ),
    CompatibilityEntry(
        contract="AUDIT_REPORT",
        role=CompatibilityRole.PARALLEL_LEGACY,
        binding=(
            "intentionally parallel legacy lineage with no conversion in "
            "either direction"
        ),
    ),
    CompatibilityEntry(
        contract="RootCauseCluster",
        role=CompatibilityRole.REUSED,
        binding=(
            "reused verbatim as the signature carrier on every M5 event; the "
            "envelope cluster.signature must equal the payload root-cause "
            "fingerprint"
        ),
    ),
    CompatibilityEntry(
        contract="CorrectionRecord",
        role=CompatibilityRole.KEYED_EXTENSION,
        binding=(
            "append-only projection semantics reused with explicit keyed "
            "supersedes targets (kind + window + digest, Step 6) instead of "
            "the automatic LATE_EVIDENCE correction"
        ),
    ),
)


class DailyEfficiencyKind(str, Enum):
    """The four additive closed M5 daily kinds (seam vocabulary).

    These kinds are declared here so the compatibility boundary is
    machine-checked before any event/schema routing lands (Step 5).  They
    are strictly disjoint from :data:`LEGACY_MAINTENANCE_KINDS`.
    """

    DAILY_EFFICIENCY_REPORT = "daily_efficiency_report"
    DAILY_EFFICIENCY_CLUSTER = "daily_efficiency_cluster"
    DAILY_EFFICIENCY_PROPOSAL = "daily_efficiency_proposal"
    DAILY_EFFICIENCY_CORRECTION = "daily_efficiency_correction"


#: Canonical string values of the four additive daily kinds.
DAILY_EFFICIENCY_KINDS: frozenset[str] = frozenset(
    kind.value for kind in DailyEfficiencyKind
)


class DailyEfficiencyPayloadId(BaseModel):
    """Strict seam carrier for the additive ``daily_efficiency.v1`` payloads.

    This is the *identity* carrier only — the full typed payload contracts
    (report, cluster, proposal, correction) land in Steps 3-4 (T3/T4).  It
    exists so the seam can be proven now: a daily payload can never
    strict-decode as a legacy payload and a legacy payload can never
    strict-decode as a daily payload.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: DailyEfficiencyKind
    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    root_cause_fingerprint: StrictStr

    @field_validator("root_cause_fingerprint")
    @classmethod
    def _validate_fingerprint(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "daily payload root_cause_fingerprint must be a non-empty string"
            )
        return value


def check_registry_invariants() -> tuple[str, ...]:
    """Machine-check the compatibility seam; return every violation found.

    An empty tuple means the seam is sound:

    * the registry covers exactly the four settled contracts with the
      settled roles;
    * every daily kind carries the ``daily_efficiency.v1`` identity;
    * daily kinds are disjoint from the legacy vocabulary (no cross-decoding,
      no widened legacy serialization);
    * daily kinds never appear in the operational report scan;
    * the reused :class:`CorrectionRecord` contract still exposes its
      keyed ``prior_output_digest`` semantics.
    """
    violations: list[str] = []

    by_contract = {
        entry.contract: entry for entry in EFFICIENCY_COMPATIBILITY_REGISTRY
    }
    if set(by_contract) != LEGACY_CONTRACT_NAMES:
        violations.append(
            "compatibility registry must reference exactly "
            f"{sorted(LEGACY_CONTRACT_NAMES)}; got {sorted(by_contract)}"
        )

    settled_roles: dict[str, CompatibilityRole] = {
        "EFFICIENCY_ANALYSIS": CompatibilityRole.CONSUMED_INPUT,
        "AUDIT_REPORT": CompatibilityRole.PARALLEL_LEGACY,
        "RootCauseCluster": CompatibilityRole.REUSED,
        "CorrectionRecord": CompatibilityRole.KEYED_EXTENSION,
    }
    for contract, role in settled_roles.items():
        entry = by_contract.get(contract)
        if entry is None:
            violations.append(f"registry missing compatibility entry for {contract}")
        elif entry.role is not role:
            violations.append(
                f"registry entry {contract} role is {entry.role.value!r}, "
                f"expected {role.value!r}"
            )

    if DAILY_EFFICIENCY_CONTRACT_ID != "daily_efficiency.v1":
        violations.append(
            f"daily contract id drifted to {DAILY_EFFICIENCY_CONTRACT_ID!r}; "
            "the settled identity is 'daily_efficiency.v1'"
        )
    if not DAILY_EFFICIENCY_KINDS.isdisjoint(LEGACY_MAINTENANCE_KINDS):
        violations.append(
            "daily kinds overlap the legacy vocabulary; cross-decoding would "
            "be possible and legacy serialization would be widened"
        )
    if not DAILY_EFFICIENCY_KINDS.isdisjoint(OPERATIONAL_REPORT_SCAN_KINDS):
        violations.append(
            "daily kinds overlap the operational report scan kinds; a daily "
            "event could surface in read_committed_report_events"
        )
    if "prior_output_digest" not in CorrectionRecord.model_fields:
        violations.append(
            "reused CorrectionRecord contract no longer exposes "
            "prior_output_digest keyed semantics"
        )
    return tuple(violations)


def is_legacy_kind(kind: str) -> bool:
    """Return ``True`` when *kind* belongs to the closed legacy vocabulary."""
    return kind in LEGACY_MAINTENANCE_KINDS


def is_daily_kind(kind: str) -> bool:
    """Return ``True`` when *kind* is one of the four additive daily kinds."""
    return kind in DAILY_EFFICIENCY_KINDS


def conversion_available(contract: str) -> bool:
    """Whether a conversion path exists from *contract* into M5 payloads.

    ``EFFICIENCY_ANALYSIS`` is consumed by decode-only reads
    (``read_committed_report_events``); ``AUDIT_REPORT`` is an intentionally
    parallel legacy lineage with **no** conversion in either direction
    (locked Step 1 rule).
    """
    if contract == "EFFICIENCY_ANALYSIS":
        return True
    if contract == "AUDIT_REPORT":
        return False
    raise ValueError(f"unknown analytical contract {contract!r}")


# ---------------------------------------------------------------------------
# T1: strict conversion / no-conversion helpers
# ---------------------------------------------------------------------------


def decode_legacy_analysis(data: str | bytes | dict[str, Any]) -> EfficiencyAnalysis:
    """Strict-decode *data* into a legacy ``efficiency_analysis`` payload."""
    return strict_loads(EfficiencyAnalysis, data)


def decode_legacy_audit(data: str | bytes | dict[str, Any]) -> AuditReport:
    """Strict-decode *data* into a legacy ``audit_report`` payload."""
    return strict_loads(AuditReport, data)


def legacy_analysis_roundtrip(payload: EfficiencyAnalysis) -> EfficiencyAnalysis:
    """Strict-decode the canonical bytes of *payload* byte-identically.

    The decoded payload equals the original and reproduces the identical
    canonical bytes — the consumed-input seam never rewrites legacy bytes.
    """
    return decode_legacy_analysis(canonical_dumps(payload))


def legacy_audit_roundtrip(payload: AuditReport) -> AuditReport:
    """Strict-decode the canonical bytes of *payload* byte-identically.

    The decoded payload equals the original and reproduces the identical
    canonical bytes — the parallel legacy lineage is never converted.
    """
    return decode_legacy_audit(canonical_dumps(payload))


# ---------------------------------------------------------------------------
# T1: reused RootCauseCluster signature binding
# ---------------------------------------------------------------------------


def bind_cluster_signature(root_cause_fingerprint: str) -> RootCauseCluster:
    """Build the reused envelope cluster whose signature IS the fingerprint.

    :class:`RootCauseCluster` is reused verbatim as the signature carrier on
    every M5 event (registry binding); the carrier's ``signature`` is set to
    the payload's root-cause fingerprint so the binding is exact.
    """
    return RootCauseCluster(signature=root_cause_fingerprint)


def cluster_for_daily_payload(payload: DailyEfficiencyPayloadId) -> RootCauseCluster:
    """Build the envelope cluster bound to a daily payload's fingerprint."""
    return bind_cluster_signature(payload.root_cause_fingerprint)


def require_cluster_signature_binding(
    cluster: RootCauseCluster,
    root_cause_fingerprint: str,
) -> None:
    """Raise unless *cluster*'s signature equals the payload fingerprint.

    Every M5 cluster event's envelope ``cluster.signature`` must equal its
    payload root-cause fingerprint; a drift is rejected explicitly rather
    than silently re-bound.
    """
    if cluster.signature != root_cause_fingerprint:
        raise ValueError(
            "cluster signature binding violated: envelope cluster.signature "
            f"{cluster.signature!r} != payload root-cause fingerprint "
            f"{root_cause_fingerprint!r}"
        )


# ---------------------------------------------------------------------------
# T2: shared reference ordering
# ---------------------------------------------------------------------------


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic reference order (SD1 rank, owner, locator, digest, cursor)."""
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
# T2: normalized cohort identity
# ---------------------------------------------------------------------------


class RobustnessKind(str, Enum):
    """Closed robustness vocabulary retained as a cohort covariate."""

    STANDARD = "standard"
    THOROUGH = "thorough"
    EXTREME = "extreme"


class EfficiencyCohortIdentity(BaseModel):
    """Normalized cohort identity for like-cohort comparisons.

    Cohort grouping uses stage/profile/model/robustness/environment and the
    classifier version (locked analytical policy).  Absent dimensions stay
    explicit ``None`` — never guessed or aliased.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    stage: StageId | None = None
    profile: ProfileId | None = None
    model: ModelId | None = None
    robustness: RobustnessKind | None = None
    environment: EnvironmentId | None = None
    classifier_version: StrictStr

    @field_validator("classifier_version")
    @classmethod
    def _validate_classifier(cls, value: str) -> str:
        if not value:
            raise ValueError("cohort classifier_version must be a non-empty string")
        return value


# ---------------------------------------------------------------------------
# T2: completed and right-censored duration observations
# ---------------------------------------------------------------------------


class ObservationStatus(str, Enum):
    """Closed observation status: completed or right-censored."""

    COMPLETED = "completed"
    RIGHT_CENSORED = "right_censored"


class DurationObservation(BaseModel):
    """One duration observation with an explicit censoring status.

    A **completed** observation carries its exact ``duration_seconds`` and no
    lower bound.  A **right-censored** observation carries no completion
    duration and an explicit ``lower_bound_seconds``: it contributes the
    conservative interval ``[lower_bound_seconds, +inf)`` to cohort
    quantiles — it is never coerced to completion or to zero.  References are
    stored in canonical sorted order so the canonical digest is independent
    of input order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    observation_id: StrictStr
    status: ObservationStatus
    #: Exact elapsed duration for completed observations; explicit ``None``
    #: for right-censored observations (unknown completion).
    duration_seconds: float | None = Field(default=None, ge=0)
    #: Explicit lower bound for right-censored observations; ``None`` for
    #: completed observations.
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    evidence_refs: tuple[OwnerRef, ...] = ()

    @field_validator("observation_id")
    @classmethod
    def _validate_observation_id(cls, value: str) -> str:
        if not value:
            raise ValueError("observation_id must be a non-empty string")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _sort_evidence(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @property
    def lower_bound(self) -> float | None:
        """Exact duration (completed) or explicit lower bound (censored)."""
        if self.status is ObservationStatus.COMPLETED:
            return self.duration_seconds
        return self.lower_bound_seconds

    @model_validator(mode="after")
    def _check_status_consistency(self) -> DurationObservation:
        if self.status is ObservationStatus.COMPLETED:
            if self.duration_seconds is None:
                raise ValueError(
                    "completed observations require an exact duration_seconds"
                )
            if self.lower_bound_seconds is not None:
                raise ValueError(
                    "completed observations cannot carry a lower_bound_seconds"
                )
        else:  # RIGHT_CENSORED
            if self.duration_seconds is not None:
                raise ValueError(
                    "right-censored observations cannot carry a completion "
                    "duration_seconds"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "right-censored observations require an explicit "
                    "lower_bound_seconds"
                )
        return self


# ---------------------------------------------------------------------------
# T2: baseline snapshots with conservative quantile bounds
# ---------------------------------------------------------------------------


class QuantileBounds(BaseModel):
    """One quantile estimate with conservative lower/upper bounds.

    Censored observations contribute ``[lower_bound, +inf)`` to the upper
    tail, so ``upper_bound`` may be ``None`` (unbounded) while ``value`` and
    ``lower_bound`` stay explicit.  Missing values remain explicit ``None`` —
    never fabricated.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: float | None = Field(default=None, ge=0)
    lower_bound: float | None = Field(default=None, ge=0)
    upper_bound: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_bounds(self) -> QuantileBounds:
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError(
                "quantile lower_bound cannot exceed upper_bound "
                f"({self.lower_bound} > {self.upper_bound})"
            )
        if self.value is not None:
            if self.lower_bound is not None and self.value < self.lower_bound:
                raise ValueError(
                    "quantile value cannot be below lower_bound "
                    f"({self.value} < {self.lower_bound})"
                )
            if self.upper_bound is not None and self.value > self.upper_bound:
                raise ValueError(
                    "quantile value cannot exceed upper_bound "
                    f"({self.value} > {self.upper_bound})"
                )
        return self


class BaselineSnapshot(BaseModel):
    """Rolling cohort baseline snapshot (median/MAD/p95/p99).

    Carries the normalized cohort, sample/plan/completed/censored counts, the
    four quantile estimates with conservative bounds, and the
    ``censoring_dominated`` flag that suppresses quantile-driven findings
    when censored mass dominates a cohort's tail (Step 12 rule; the flag is
    part of the contract so consumers can never lose it).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    cohort: EfficiencyCohortIdentity
    sample_count: int = Field(ge=0)
    plan_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    censored_count: int = Field(ge=0)
    median: QuantileBounds
    mad: QuantileBounds
    p95: QuantileBounds
    p99: QuantileBounds
    censoring_dominated: bool = False
    generated_at: UtcTime

    @model_validator(mode="after")
    def _check_counts(self) -> BaselineSnapshot:
        if self.completed_count + self.censored_count > self.sample_count:
            raise ValueError(
                "completed_count + censored_count cannot exceed sample_count "
                f"({self.completed_count} + {self.censored_count} > "
                f"{self.sample_count})"
            )
        if self.plan_count > self.sample_count:
            raise ValueError(
                "plan_count cannot exceed sample_count "
                f"({self.plan_count} > {self.sample_count})"
            )
        return self


# ---------------------------------------------------------------------------
# T2: metric denominators and coverage
# ---------------------------------------------------------------------------


class DenominatorCoverage(BaseModel):
    """Explicit metric denominator with coverage (never fabricated).

    A missing numerator or denominator stays explicit ``None``; ``coverage``
    returns ``None`` (never ``0``) when the numerator or denominator is
    missing or the denominator is zero.  Unknown and censored counts are
    retained, never dropped.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    metric: StrictStr
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    unknown_count: int = Field(default=0, ge=0)
    censored_count: int = Field(default=0, ge=0)

    @field_validator("metric")
    @classmethod
    def _validate_metric(cls, value: str) -> str:
        if not value:
            raise ValueError("metric identity must be a non-empty string")
        return value

    @property
    def missing_denominator(self) -> bool:
        """True when the denominator is missing (``None``), never inferred."""
        return self.denominator is None

    @property
    def coverage(self) -> float | None:
        """Derived coverage (numerator / denominator), or ``None`` when unknown.

        ``None`` covers every unknown case: a missing numerator, a missing
        denominator, or a zero denominator (never a division by zero).
        """
        if self.numerator is None or self.denominator is None:
            return None
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @model_validator(mode="after")
    def _check_bounds(self) -> DenominatorCoverage:
        if (
            self.numerator is not None
            and self.denominator is not None
            and self.numerator > self.denominator
        ):
            raise ValueError(
                f"metric numerator {self.numerator} exceeds "
                f"denominator {self.denominator}"
            )
        return self


# ---------------------------------------------------------------------------
# T2: shadow-evaluation measures
# ---------------------------------------------------------------------------


class ShadowMeasureKind(str, Enum):
    """Closed vocabulary of shadow-evaluation measures."""

    PRECISION = "precision"
    RECALL = "recall"
    ANALYST_OVERHEAD = "analyst_overhead"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    RECURRENCE_YIELD = "recurrence_yield"
    ACCEPTED_TICKET_RATE = "accepted_ticket_rate"
    ESTIMATED_SAVINGS = "estimated_savings"
    REALIZED_SAVINGS = "realized_savings"


class UnavailableReason(str, Enum):
    """Typed reason a shadow measure is unavailable (never guessed)."""

    MISSING_DENOMINATOR = "missing_denominator"
    MISSING_NUMERATOR = "missing_numerator"
    ZERO_DENOMINATOR = "zero_denominator"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


#: Shadow measures that are rates and must lie in ``[0, 1]`` when present.
_RATE_MEASURES: frozenset[ShadowMeasureKind] = frozenset(
    {
        ShadowMeasureKind.PRECISION,
        ShadowMeasureKind.RECALL,
        ShadowMeasureKind.FALSE_POSITIVE_RATE,
        ShadowMeasureKind.RECURRENCE_YIELD,
        ShadowMeasureKind.ACCEPTED_TICKET_RATE,
    }
)

#: Shadow measures that are non-negative magnitudes when present.
_NON_NEGATIVE_MEASURES: frozenset[ShadowMeasureKind] = frozenset(
    {
        ShadowMeasureKind.ANALYST_OVERHEAD,
        ShadowMeasureKind.ESTIMATED_SAVINGS,
        ShadowMeasureKind.REALIZED_SAVINGS,
    }
)


class ShadowMeasure(BaseModel):
    """One shadow-evaluation measure with explicit unavailable states.

    A measure with a value never carries an ``unavailable_reason``; a
    measure without a value keeps its numerator/denominator as explicit
    ``None`` and may name a typed :class:`UnavailableReason` (or stay an
    explicit null).  Rates are validated into ``[0, 1]`` when present.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    measure: ShadowMeasureKind
    value: float | None = None
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    unavailable_reason: UnavailableReason | None = None

    @model_validator(mode="after")
    def _check_value_consistency(self) -> ShadowMeasure:
        if self.value is None:
            return self
        if self.unavailable_reason is not None:
            raise ValueError(
                "a shadow measure with a value cannot carry an "
                "unavailable_reason"
            )
        if self.measure in _RATE_MEASURES and not 0.0 <= self.value <= 1.0:
            raise ValueError(
                f"{self.measure.value} is a rate and must be in [0, 1], "
                f"got {self.value}"
            )
        if self.measure in _NON_NEGATIVE_MEASURES and self.value < 0:
            raise ValueError(
                f"{self.measure.value} must be non-negative, got {self.value}"
            )
        return self


# ---------------------------------------------------------------------------
# T3: finding reference bundle (exact custody/source/gate/backoff/censoring)
# ---------------------------------------------------------------------------


class FindingReferences(BaseModel):
    """Exact reference bundle every M5 finding must carry (Step 3).

    Six categories are part of the contract: exact accepted resolution,
    active repair custody, source, gate/backoff, and censoring references.
    ``accepted_resolution_refs`` and ``source_refs`` are mandatory (a finding
    is always anchored to an exact accepted resolution and an exact source);
    custody, gate/backoff, and censoring references are exact-when-present
    and serialize as explicit empty lists when absent — absence is never
    inferred from the locator or from any other field.  All refs are stored
    in canonical sorted order so hashing is input-order independent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    #: Exact accepted resolution (accepted decision/claim/outcome) anchors.
    accepted_resolution_refs: tuple[OwnerRef, ...] = ()
    #: Active repair custody refs — reference/covariate only, never claimed.
    active_custody_refs: tuple[OwnerRef, ...] = ()
    #: Exact owner-source refs the finding was derived from.
    source_refs: tuple[OwnerRef, ...] = ()
    #: Exact configured gate/backoff references (human gates, backoff windows).
    gate_backoff_refs: tuple[OwnerRef, ...] = ()
    #: Exact censoring references (right-censored observation lower bounds).
    censoring_refs: tuple[OwnerRef, ...] = ()

    @field_validator(
        "accepted_resolution_refs",
        "active_custody_refs",
        "source_refs",
        "gate_backoff_refs",
        "censoring_refs",
    )
    @classmethod
    def _sort_reference_groups(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _require_anchor_refs(self) -> FindingReferences:
        if not self.accepted_resolution_refs:
            raise ValueError(
                "every finding requires at least one exact accepted_resolution_ref"
            )
        if not self.source_refs:
            raise ValueError("every finding requires at least one exact source_ref")
        return self


# ---------------------------------------------------------------------------
# T3: accepted-outcome economics (denominator-gated; never raw totals alone)
# ---------------------------------------------------------------------------


class CostSourceKind(str, Enum):
    """Closed authoritative-cost source vocabulary (never silently merged)."""

    PROVIDER_REPORTED = "provider_reported"
    WBC_WORK_LEDGER = "wbc_work_ledger"
    UNKNOWN = "unknown"


class AcceptedOutcomeEconomics(BaseModel):
    """Time/tokens/authoritative cost per accepted outcome plus quality delta.

    The accepted-outcome denominator (``accepted_outcome_count``) is
    mandatory whenever ANY economics claim is present: per-accepted values,
    quality delta, and raw totals are all rejected without an exact positive
    denominator (missing-denominator rejection, locked Step 3 rule).  Raw
    totals are carried only as explicit context alongside the denominator —
    they are never the primary claim.  Authoritative cost claims name a
    typed :class:`CostSourceKind` and, unless ``UNKNOWN``, pin the exact
    dispatch receipt / work-ledger coordinate with ``cost_source_ref``.
    Missing measures stay explicit ``None`` — never coerced to zero.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    #: Accepted-outcome denominator; required (> 0) for any economics claim.
    accepted_outcome_count: int | None = Field(default=None, ge=0)
    time_seconds_per_accepted: float | None = Field(default=None, ge=0)
    tokens_per_accepted: float | None = Field(default=None, ge=0)
    cost_per_accepted: float | None = Field(default=None, ge=0)
    #: Quality delta per accepted outcome (positive/negative/zero delta).
    quality_delta: float | None = None
    raw_time_seconds_total: float | None = Field(default=None, ge=0)
    raw_tokens_total: float | None = Field(default=None, ge=0)
    raw_cost_total: float | None = Field(default=None, ge=0)
    cost_source: CostSourceKind | None = None
    cost_source_ref: OwnerRef | None = None

    @model_validator(mode="after")
    def _require_denominator_for_claims(self) -> AcceptedOutcomeEconomics:
        claims = (
            self.time_seconds_per_accepted,
            self.tokens_per_accepted,
            self.cost_per_accepted,
            self.quality_delta,
            self.raw_time_seconds_total,
            self.raw_tokens_total,
            self.raw_cost_total,
        )
        if any(value is not None for value in claims):
            if self.accepted_outcome_count is None:
                raise ValueError(
                    "economics claims require an exact accepted-outcome "
                    "denominator (accepted_outcome_count); raw totals or "
                    "per-accepted values without a denominator are rejected"
                )
            if self.accepted_outcome_count <= 0:
                raise ValueError(
                    "accepted-outcome denominator must be positive when "
                    f"economics claims are present, got {self.accepted_outcome_count}"
                )
        if self.cost_per_accepted is not None or self.raw_cost_total is not None:
            if self.cost_source is None:
                raise ValueError(
                    "authoritative cost claims require a typed cost_source "
                    "(provider_reported or wbc_work_ledger); competing cost "
                    "sources are never silently merged"
                )
        if (
            self.cost_source is not None
            and self.cost_source is not CostSourceKind.UNKNOWN
            and self.cost_source_ref is None
        ):
            raise ValueError(
                "authoritative cost source requires an exact cost_source_ref "
                "pinning the dispatch receipt or work-ledger coordinate"
            )
        return self


# ---------------------------------------------------------------------------
# T3: typed dwell, loop, idle-handoff, and route-mismatch findings
# ---------------------------------------------------------------------------


class EfficiencyFinding(BaseModel):
    """Common frozen base for every M5 finding payload (Step 3).

    Every finding carries the exact :class:`FindingReferences` bundle and an
    optional :class:`AcceptedOutcomeEconomics` payload whose denominator
    gates any raw-total or per-accepted regression claim.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    finding_id: StrictStr
    references: FindingReferences
    economics: AcceptedOutcomeEconomics | None = None

    @field_validator("finding_id")
    @classmethod
    def _validate_finding_id(cls, value: str) -> str:
        if not value:
            raise ValueError("finding_id must be a non-empty string")
        return value


class DwellFindingKind(str, Enum):
    """Closed dwell-family vocabulary: gate / finalize-publication / review."""

    GATE = "gate"
    FINALIZE_PUBLICATION = "finalize_publication"
    REVIEW = "review"


class DwellFinding(EfficiencyFinding):
    """One gate/finalize-publication/review dwell observation.

    A **completed** dwell carries its exact ``duration_seconds``; a
    **censored** dwell carries no completion duration and an explicit
    ``lower_bound_seconds`` (it is never coerced to completion or zero).  The
    conservative predicate flags (``above_p95`` / ``above_2x_median`` /
    ``above_slo``) are part of the contract so consumers can never lose the
    conservative-bounds basis of a dwell flag.
    """

    family: Literal["dwell"] = "dwell"
    kind: DwellFindingKind
    duration_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    slo_seconds: float | None = Field(default=None, ge=0)
    above_p95: bool = False
    above_2x_median: bool = False
    above_slo: bool = False

    @model_validator(mode="after")
    def _check_duration_censoring(self) -> DwellFinding:
        if self.censored:
            if self.duration_seconds is not None:
                raise ValueError(
                    "censored dwell findings cannot carry a completion "
                    "duration_seconds"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "censored dwell findings require an explicit "
                    "lower_bound_seconds"
                )
        else:
            if self.duration_seconds is None:
                raise ValueError(
                    "completed dwell findings require an exact duration_seconds"
                )
            if self.lower_bound_seconds is not None:
                raise ValueError(
                    "completed dwell findings cannot carry a lower_bound_seconds"
                )
        if self.above_slo and self.slo_seconds is None:
            raise ValueError(
                "above_slo requires a declared slo_seconds (an SLO is never "
                "inferred)"
            )
        return self

    @property
    def lower_bound(self) -> float | None:
        """Exact duration (completed) or explicit lower bound (censored)."""
        if self.censored:
            return self.lower_bound_seconds
        return self.duration_seconds


class LoopFindingKind(str, Enum):
    """Closed loop-family vocabulary."""

    RETRY_LOOP = "retry_loop"
    REVISION_LOOP = "revision_loop"
    DUPLICATE_CALL = "duplicate_call"
    NO_PROGRESS = "no_progress"


class LoopFinding(EfficiencyFinding):
    """One retry/revision/duplicate/no-progress loop finding.

    ``attempt_count`` is the exact number of calls/attempts folded into the
    loop; retry/revision/duplicate loops require at least 2 attempts and
    no-progress findings require an explicit ``no_progress_delta_seconds``.
    A duplicated or no-progress call is counted only against an exact
    accepted-outcome denominator (via ``economics``).
    """

    family: Literal["loop"] = "loop"
    kind: LoopFindingKind
    repeated_stage: StrictStr
    attempt_count: int = Field(ge=1)
    loop_span_seconds: float | None = Field(default=None, ge=0)
    no_progress_delta_seconds: float | None = Field(default=None, ge=0)

    @field_validator("repeated_stage")
    @classmethod
    def _validate_stage(cls, value: str) -> str:
        if not value:
            raise ValueError("repeated_stage must be a non-empty string")
        return value

    @model_validator(mode="after")
    def _check_loop_bounds(self) -> LoopFinding:
        if (
            self.kind
            in (
                LoopFindingKind.RETRY_LOOP,
                LoopFindingKind.REVISION_LOOP,
                LoopFindingKind.DUPLICATE_CALL,
            )
            and self.attempt_count < 2
        ):
            raise ValueError(
                f"{self.kind.value} requires at least 2 attempts, "
                f"got {self.attempt_count}"
            )
        if self.kind is LoopFindingKind.NO_PROGRESS:
            if self.no_progress_delta_seconds is None:
                raise ValueError(
                    "no-progress findings require an explicit "
                    "no_progress_delta_seconds"
                )
        elif self.no_progress_delta_seconds is not None:
            raise ValueError(
                f"{self.kind.value} findings cannot carry "
                "no_progress_delta_seconds"
            )
        return self


class IdleHandoffFinding(EfficiencyFinding):
    """One idle handoff finding (stage A handed to stage B with no progress)."""

    family: Literal["idle_handoff"] = "idle_handoff"
    from_stage: StrictStr
    to_stage: StrictStr
    idle_seconds: float = Field(ge=0)
    handed_off_at: UtcTime | None = None

    @field_validator("from_stage", "to_stage")
    @classmethod
    def _validate_stages(cls, value: str) -> str:
        if not value:
            raise ValueError("handoff stages must be non-empty strings")
        return value

    @model_validator(mode="after")
    def _check_distinct_stages(self) -> IdleHandoffFinding:
        if self.from_stage == self.to_stage:
            raise ValueError(
                "idle handoff stages must differ "
                f"({self.from_stage!r} == {self.to_stage!r})"
            )
        return self


class RouteMismatchLeg(str, Enum):
    """Closed route-mismatch leg vocabulary."""

    EXPECTED_VS_RESOLVED = "expected_vs_resolved"
    RESOLVED_VS_PROVIDER_ACTUAL = "resolved_vs_provider_actual"
    EXPECTED_VS_PROVIDER_ACTUAL = "expected_vs_provider_actual"


class RouteMismatchFinding(EfficiencyFinding):
    """One route mismatch finding (expected/resolved/provider-actual routes).

    A missing route leg stays explicit ``None`` — typed unknown, NEVER a
    mismatch.  Every named :attr:`mismatch_legs` entry requires both of its
    routes present and different; legs are stored sorted for stable hashing.
    """

    family: Literal["route_mismatch"] = "route_mismatch"
    expected_route: StrictStr | None = None
    resolved_route: StrictStr | None = None
    provider_actual_route: StrictStr | None = None
    mismatch_legs: tuple[RouteMismatchLeg, ...] = ()

    @field_validator("expected_route", "resolved_route", "provider_actual_route")
    @classmethod
    def _validate_routes(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("route identities must be non-empty strings when present")
        return value

    @field_validator("mismatch_legs")
    @classmethod
    def _sort_legs(
        cls, value: Sequence[RouteMismatchLeg]
    ) -> tuple[RouteMismatchLeg, ...]:
        return tuple(sorted(value, key=lambda leg: leg.value))

    @model_validator(mode="after")
    def _check_mismatch_legs(self) -> RouteMismatchFinding:
        if not self.mismatch_legs:
            raise ValueError(
                "route mismatch findings require at least one named mismatch_leg"
            )
        pairs: dict[RouteMismatchLeg, tuple[str | None, str | None]] = {
            RouteMismatchLeg.EXPECTED_VS_RESOLVED: (
                self.expected_route,
                self.resolved_route,
            ),
            RouteMismatchLeg.RESOLVED_VS_PROVIDER_ACTUAL: (
                self.resolved_route,
                self.provider_actual_route,
            ),
            RouteMismatchLeg.EXPECTED_VS_PROVIDER_ACTUAL: (
                self.expected_route,
                self.provider_actual_route,
            ),
        }
        for leg in self.mismatch_legs:
            left, right = pairs[leg]
            if left is None or right is None:
                raise ValueError(
                    f"mismatch leg {leg.value} requires both routes present; "
                    "a missing leg is typed UNKNOWN, never a mismatch"
                )
            if left == right:
                raise ValueError(
                    f"mismatch leg {leg.value} named for equal routes "
                    f"{left!r} == {right!r}"
                )
        return self


# ---------------------------------------------------------------------------
# T3: root-cause candidates (alternatives, coverage, confidence bounds)
# ---------------------------------------------------------------------------


class RootCauseAlternative(BaseModel):
    """One alternative explanation for a root-cause candidate.

    ``confidence`` carries conservative lower/upper bounds; ``evidence_refs``
    are locator-only immutable references, never embedded payloads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    alternative_id: StrictStr
    summary: StrictStr
    confidence: QuantileBounds
    evidence_refs: tuple[OwnerRef, ...] = ()

    @field_validator("alternative_id", "summary")
    @classmethod
    def _validate_alternative(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "root-cause alternative id/summary must be non-empty strings"
            )
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _sort_evidence(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)


class RootCauseCandidate(BaseModel):
    """One root-cause candidate with alternatives, coverage, and confidence.

    ``root_cause_fingerprint`` is the canonical problem signature the reused
    envelope :class:`RootCauseCluster` signature binds to (Step 1 seam);
    operational occurrences are referenced (``occurrence_refs``), never
    embedded — problem fingerprints stay separate from operational
    occurrence identity.  ``coverage`` requires an exact denominator
    (missing-denominator rejection); confidence carries conservative bounds;
    ``avoidable_impact`` is denominator-gated economics; active repair
    custody appears only as reference/covariate refs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    candidate_id: StrictStr
    root_cause_fingerprint: StrictStr
    affected_contract: StrictStr
    classifier_version: StrictStr
    alternatives: tuple[RootCauseAlternative, ...] = ()
    coverage: DenominatorCoverage
    confidence: QuantileBounds
    recurrence_count_7d: int = Field(ge=0)
    recurrence_count_30d: int = Field(ge=0)
    occurrence_refs: tuple[OwnerRef, ...] = ()
    active_custody_refs: tuple[OwnerRef, ...] = ()
    evidence_refs: tuple[OwnerRef, ...] = ()
    avoidable_impact: AcceptedOutcomeEconomics | None = None

    @field_validator(
        "candidate_id",
        "root_cause_fingerprint",
        "affected_contract",
        "classifier_version",
    )
    @classmethod
    def _validate_identities(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "candidate identities/fingerprints must be non-empty strings"
            )
        return value

    @field_validator("alternatives")
    @classmethod
    def _sort_alternatives(
        cls, value: Sequence[RootCauseAlternative]
    ) -> tuple[RootCauseAlternative, ...]:
        return tuple(sorted(value, key=lambda alt: alt.alternative_id))

    @field_validator("occurrence_refs", "active_custody_refs", "evidence_refs")
    @classmethod
    def _sort_candidate_refs(
        cls, value: Sequence[OwnerRef]
    ) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_candidate(self) -> RootCauseCandidate:
        if self.coverage.denominator is None:
            raise ValueError(
                "root-cause candidate coverage requires an exact denominator; "
                "coverage is never fabricated from a missing denominator"
            )
        if self.recurrence_count_30d < self.recurrence_count_7d:
            raise ValueError(
                "recurrence_count_30d cannot be below recurrence_count_7d "
                f"({self.recurrence_count_30d} < {self.recurrence_count_7d})"
            )
        return self


# ---------------------------------------------------------------------------
# T4: locked occurrence-ID derivations (report / cluster / proposal / correction)
# ---------------------------------------------------------------------------


_SHA256_HEX: frozenset[str] = frozenset("0123456789abcdef")


def _sha256_hex(material: str) -> str:
    """Canonical sha256 hex digest of *material* (the locked identity basis)."""
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _require_sha256(value: str, *, what: str) -> str:
    """Validate a 64-character lowercase sha256 hex digest."""
    if len(value) != 64 or any(char not in _SHA256_HEX for char in value):
        raise ValueError(f"{what} must be a 64-character lowercase sha256 hex digest")
    return value


def _env_root(environment: EnvironmentId | str | None) -> str | None:
    """Normalize an environment coordinate to its canonical root (fail fast)."""
    if environment is None:
        return None
    if isinstance(environment, EnvironmentId):
        return environment.root
    return EnvironmentId(environment).root


def _window_material(window: EventWindow) -> str:
    """Canonical serialization of a half-open window (stable, replayable)."""
    return canonical_json(window.model_dump(mode="json"))


class ProposalKind(str, Enum):
    """Closed vocabulary of inert M5 proposal kinds (recommendation routing).

    A proposal is report-only: it may recommend a ticket or an initiative,
    but it never materializes either (``auto_materialization`` is locked to
    ``False`` on :class:`DailyEfficiencyProposal`).
    """

    TICKET = "ticket"
    INITIATIVE = "initiative"


#: Discriminated union of every M5 finding payload (dwell/loop/handoff/mismatch).
EfficiencyFindingUnion = Annotated[
    Union[
        DwellFinding,
        LoopFinding,
        IdleHandoffFinding,
        RouteMismatchFinding,
    ],
    Field(discriminator="family"),
]


def derive_report_occurrence_id(
    *,
    environment: EnvironmentId | str | None,
    window: EventWindow,
) -> str:
    """Locked daily-report occurrence ID.

    ``daily_efficiency_report|{sha256(environment|window)}`` over the exact
    half-open window boundaries.  Deterministic and replayable: the same
    environment and window always derive the same identity, and any window
    or environment change derives a different identity.
    """
    material = canonical_json(
        {
            "environment": _env_root(environment),
            "window": _window_material(window),
        }
    )
    return f"daily_efficiency_report|{_sha256_hex(material)}"


def derive_cluster_occurrence_id(
    *,
    environment: EnvironmentId | str | None,
    window: EventWindow,
    root_cause_fingerprint: str,
) -> str:
    """Locked daily cluster occurrence ID.

    ``daily_efficiency_cluster|{sha256(environment|window|fingerprint)}`` —
    one cluster identity per root-cause fingerprint per window; the cluster
    signature carrier binding stays exact (Step 1 seam).
    """
    if not root_cause_fingerprint:
        raise ValueError("root_cause_fingerprint must be a non-empty string")
    material = canonical_json(
        {
            "environment": _env_root(environment),
            "window": _window_material(window),
            "root_cause_fingerprint": root_cause_fingerprint,
        }
    )
    return f"daily_efficiency_cluster|{_sha256_hex(material)}"


def derive_proposal_key(
    *,
    proposal_kind: ProposalKind | str,
    root_cause_fingerprint: str,
    affected_contract: str,
    classifier_version: str,
    open_ticket_identity: str | None,
) -> str:
    """Locked cross-window proposal key (SD3).

    Canonical JSON over (proposal kind, root-cause fingerprint, affected
    contract, classifier version, open-ticket identity).  The key is
    intentionally WINDOW-FREE so the same proposal keeps one identity across
    windows; ``open_ticket_identity=None`` is the explicit no-match state
    (never guessed).
    """
    kind = proposal_kind.value if isinstance(proposal_kind, ProposalKind) else proposal_kind
    if not kind:
        raise ValueError("proposal_kind must be a non-empty string")
    if not root_cause_fingerprint or not affected_contract or not classifier_version:
        raise ValueError(
            "proposal key requires non-empty root-cause fingerprint, affected "
            "contract, and classifier version"
        )
    return canonical_json(
        {
            "proposal_kind": kind,
            "root_cause_fingerprint": root_cause_fingerprint,
            "affected_contract": affected_contract,
            "classifier_version": classifier_version,
            "open_ticket_identity": open_ticket_identity,
        }
    )


def derive_proposal_occurrence_id(
    *,
    proposal_kind: ProposalKind | str,
    root_cause_fingerprint: str,
    affected_contract: str,
    classifier_version: str,
    open_ticket_identity: str | None,
) -> str:
    """Locked cross-window proposal occurrence ID (SD3).

    ``daily_efficiency_proposal|{sha256(proposal_key)}`` over the locked
    proposal key.  Because the key carries no window, the same proposal
    derives the SAME occurrence ID in every window; a different key derives a
    different ID, so divergent identity reuse is rejected by construction
    (Step 19 prior-key lookup dedupes on this identity).
    """
    key = derive_proposal_key(
        proposal_kind=proposal_kind,
        root_cause_fingerprint=root_cause_fingerprint,
        affected_contract=affected_contract,
        classifier_version=classifier_version,
        open_ticket_identity=open_ticket_identity,
    )
    return f"daily_efficiency_proposal|{_sha256_hex(key)}"


def derive_correction_occurrence_id(
    *,
    supersedes_kind: DailyEfficiencyKind | str,
    supersedes_window: EventWindow,
    supersedes_digest: str,
) -> str:
    """Locked keyed-correction occurrence ID (SD4).

    ``daily_efficiency_correction|{sha256(supersedes_kind|window|digest)}``
    over the validated keyed supersedes target, so exactly one keyed
    correction exists per (kind, window, digest) target and a late-evidence
    digest advance derives a NEW correction identity instead of rewriting.
    """
    kind = (
        supersedes_kind.value
        if isinstance(supersedes_kind, DailyEfficiencyKind)
        else supersedes_kind
    )
    if not kind:
        raise ValueError("supersedes_kind must be a non-empty string")
    _require_sha256(supersedes_digest, what="supersedes_digest")
    material = canonical_json(
        {
            "supersedes_kind": kind,
            "supersedes_window": _window_material(supersedes_window),
            "supersedes_digest": supersedes_digest,
        }
    )
    return f"daily_efficiency_correction|{_sha256_hex(material)}"


def derive_input_fingerprint(input_refs: Sequence[OwnerRef]) -> str:
    """Canonical per-window input fingerprint over the exact owner refs.

    sha256 of the canonical sorted reference set (owner/locator/digest/cursor
    coordinates), so a late-evidence input advance changes the fingerprint
    deterministically (Step 22 correction-discovery basis).
    """
    refs = _sort_refs(input_refs)
    material = canonical_json([ref.model_dump(mode="json") for ref in refs])
    return _sha256_hex(material)


# ---------------------------------------------------------------------------
# T4: strict daily report contract (exact half-open boundaries)
# ---------------------------------------------------------------------------


class DailyEfficiencyReport(BaseModel):
    """Strict daily efficiency report over one exact half-open window.

    Carries the full observation/statistics/finding family for one
    ``[window.start, window.end)`` window, the locked ``report_id``
    (``daily_efficiency_report|{sha256(environment|window)}``), and the
    canonical per-window ``input_fingerprint`` over the exact owner refs.
    ``report_hash`` is the replayable canonical digest of the whole report;
    ``watermark`` is the window's exclusive end boundary.  Missing values
    stay explicit ``None`` — never fabricated.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    kind: Literal["daily_efficiency_report"] = DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT.value
    report_id: StrictStr
    environment: EnvironmentId | None = None
    window: EventWindow
    generated_at: UtcTime
    classifier_version: StrictStr
    policy_version: StrictStr
    observations: tuple[DurationObservation, ...] = ()
    baselines: tuple[BaselineSnapshot, ...] = ()
    findings: tuple[EfficiencyFindingUnion, ...] = ()
    denominators: tuple[DenominatorCoverage, ...] = ()
    shadow_measures: tuple[ShadowMeasure, ...] = ()
    input_refs: tuple[OwnerRef, ...] = ()
    input_fingerprint: StrictStr

    @field_validator("classifier_version", "policy_version")
    @classmethod
    def _validate_versions(cls, value: str) -> str:
        if not value:
            raise ValueError("report classifier/policy versions must be non-empty strings")
        return value

    @field_validator("observations")
    @classmethod
    def _sort_observations(
        cls, value: Sequence[DurationObservation]
    ) -> tuple[DurationObservation, ...]:
        return tuple(sorted(value, key=lambda obs: obs.observation_id))

    @field_validator("baselines")
    @classmethod
    def _sort_baselines(
        cls, value: Sequence[BaselineSnapshot]
    ) -> tuple[BaselineSnapshot, ...]:
        return tuple(sorted(value, key=lambda item: canonical_dumps(item)))

    @field_validator("findings")
    @classmethod
    def _sort_findings(cls, value: Sequence[EfficiencyFinding]) -> tuple[EfficiencyFinding, ...]:
        return tuple(sorted(value, key=lambda finding: finding.finding_id))

    @field_validator("denominators")
    @classmethod
    def _sort_denominators(
        cls, value: Sequence[DenominatorCoverage]
    ) -> tuple[DenominatorCoverage, ...]:
        return tuple(sorted(value, key=lambda item: item.metric))

    @field_validator("shadow_measures")
    @classmethod
    def _sort_shadow_measures(
        cls, value: Sequence[ShadowMeasure]
    ) -> tuple[ShadowMeasure, ...]:
        return tuple(sorted(value, key=lambda item: item.measure.value))

    @field_validator("input_refs")
    @classmethod
    def _sort_input_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @field_validator("input_fingerprint")
    @classmethod
    def _validate_fingerprint(cls, value: str) -> str:
        return _require_sha256(value, what="report input_fingerprint")

    @model_validator(mode="after")
    def _check_locked_identity(self) -> DailyEfficiencyReport:
        expected_id = derive_report_occurrence_id(
            environment=self.environment, window=self.window
        )
        if self.report_id != expected_id:
            raise ValueError(
                "report_id diverges from the locked derivation; divergent "
                f"identity reuse is rejected (expected {expected_id!r}, "
                f"got {self.report_id!r})"
            )
        expected_fingerprint = derive_input_fingerprint(self.input_refs)
        if self.input_fingerprint != expected_fingerprint:
            raise ValueError(
                "input_fingerprint diverges from the canonical input ref set "
                f"(expected {expected_fingerprint!r}, got {self.input_fingerprint!r})"
            )
        return self

    @property
    def report_hash(self) -> str:
        """Replayable canonical digest of the whole report payload."""
        return canonical_digest(self)

    @property
    def watermark(self) -> UtcTime:
        """The window's exclusive end boundary (the derived closure boundary)."""
        return self.window.end


# ---------------------------------------------------------------------------
# T4: strict daily cluster payload
# ---------------------------------------------------------------------------


class DailyEfficiencyCluster(BaseModel):
    """Strict daily root-cause cluster payload (Step 4).

    ``cluster_id`` is the locked derivation over (environment, window,
    root-cause fingerprint).  The embedded candidate's fingerprint must equal
    the cluster fingerprint so the reused envelope :class:`RootCauseCluster`
    signature binding (Step 1 seam) is exact; occurrences and evidence are
    referenced (never embedded).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    kind: Literal["daily_efficiency_cluster"] = DailyEfficiencyKind.DAILY_EFFICIENCY_CLUSTER.value
    cluster_id: StrictStr
    environment: EnvironmentId | None = None
    window: EventWindow
    root_cause_fingerprint: StrictStr
    candidate: RootCauseCandidate
    occurrence_refs: tuple[OwnerRef, ...] = ()
    evidence_refs: tuple[OwnerRef, ...] = ()
    generated_at: UtcTime

    @field_validator("root_cause_fingerprint")
    @classmethod
    def _validate_fingerprint(cls, value: str) -> str:
        if not value:
            raise ValueError("cluster root_cause_fingerprint must be a non-empty string")
        return value

    @field_validator("occurrence_refs", "evidence_refs")
    @classmethod
    def _sort_cluster_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_locked_identity(self) -> DailyEfficiencyCluster:
        expected_id = derive_cluster_occurrence_id(
            environment=self.environment,
            window=self.window,
            root_cause_fingerprint=self.root_cause_fingerprint,
        )
        if self.cluster_id != expected_id:
            raise ValueError(
                "cluster_id diverges from the locked derivation; divergent "
                f"identity reuse is rejected (expected {expected_id!r}, "
                f"got {self.cluster_id!r})"
            )
        if self.candidate.root_cause_fingerprint != self.root_cause_fingerprint:
            raise ValueError(
                "cluster candidate fingerprint diverges from the cluster "
                "root_cause_fingerprint; the envelope signature binding must "
                "stay exact"
            )
        return self


# ---------------------------------------------------------------------------
# T4: strict INERT daily proposal payload (cross-window identity)
# ---------------------------------------------------------------------------


class DailyEfficiencyProposal(BaseModel):
    """Strict INERT daily proposal payload (Step 4 / SD3).

    The proposal is a recommendation only: ``auto_materialization`` is locked
    to ``False`` (any attempt to construct it as ``True`` fails validation).
    ``proposal_id`` is the locked cross-window derivation
    ``daily_efficiency_proposal|{sha256(proposal_key)}`` over (proposal kind,
    root-cause fingerprint, affected contract, classifier version, open-ticket
    identity) — the key carries no window, so the same proposal keeps ONE
    identity across windows and divergent identity reuse is rejected by
    construction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    kind: Literal["daily_efficiency_proposal"] = DailyEfficiencyKind.DAILY_EFFICIENCY_PROPOSAL.value
    proposal_id: StrictStr
    proposal_kind: ProposalKind
    root_cause_fingerprint: StrictStr
    affected_contract: StrictStr
    classifier_version: StrictStr
    #: Explicit no-match state is ``None`` (never guessed); an actual matching
    #: open ticket carries its stable ticket identity.
    open_ticket_identity: StrictStr | None = None
    environment: EnvironmentId | None = None
    window: EventWindow
    #: Locator-only reference to the emitting cluster (never embedded).
    cluster_ref: OwnerRef
    candidate_refs: tuple[OwnerRef, ...] = ()
    evidence_refs: tuple[OwnerRef, ...] = ()
    active_custody_refs: tuple[OwnerRef, ...] = ()
    active_custody_present: bool = False
    auto_materialization: Literal[False] = False
    generated_at: UtcTime

    @field_validator("root_cause_fingerprint", "affected_contract", "classifier_version")
    @classmethod
    def _validate_identities(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "proposal identities/fingerprints must be non-empty strings"
            )
        return value

    @field_validator("candidate_refs", "evidence_refs", "active_custody_refs")
    @classmethod
    def _sort_proposal_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_locked_identity(self) -> DailyEfficiencyProposal:
        expected_id = derive_proposal_occurrence_id(
            proposal_kind=self.proposal_kind,
            root_cause_fingerprint=self.root_cause_fingerprint,
            affected_contract=self.affected_contract,
            classifier_version=self.classifier_version,
            open_ticket_identity=self.open_ticket_identity,
        )
        if self.proposal_id != expected_id:
            raise ValueError(
                "proposal_id diverges from the locked cross-window derivation; "
                "divergent identity reuse is rejected "
                f"(expected {expected_id!r}, got {self.proposal_id!r})"
            )
        return self

    @property
    def proposal_key(self) -> str:
        """Locked cross-window proposal key (canonical, window-free)."""
        return derive_proposal_key(
            proposal_kind=self.proposal_kind,
            root_cause_fingerprint=self.root_cause_fingerprint,
            affected_contract=self.affected_contract,
            classifier_version=self.classifier_version,
            open_ticket_identity=self.open_ticket_identity,
        )


# ---------------------------------------------------------------------------
# T4: strict digest-linked daily correction payload
# ---------------------------------------------------------------------------


class DailyEfficiencyCorrection(BaseModel):
    """Strict digest-linked daily correction payload (Step 4 / SD4).

    An explicit correction BYPASSES the automatic LATE_EVIDENCE
    CorrectionRecord and targets exactly one prior daily payload by its
    validated keyed supersedes target (kind + exact half-open window +
    sha256 digest).  ``correction_id`` is the locked derivation over that
    target, so the same target+digest derives ONE correction identity and a
    changed digest derives a different one (a late-evidence advance appends a
    NEW keyed correction rather than rewriting the prior report).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    kind: Literal["daily_efficiency_correction"] = DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION.value
    correction_id: StrictStr
    supersedes_kind: DailyEfficiencyKind
    supersedes_window: EventWindow
    supersedes_digest: StrictStr
    environment: EnvironmentId | None = None
    window: EventWindow
    reason: StrictStr | None = None
    generated_at: UtcTime

    @field_validator("supersedes_digest")
    @classmethod
    def _validate_supersedes_digest(cls, value: str) -> str:
        return _require_sha256(value, what="supersedes_digest")

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("correction reason must be a non-empty string when present")
        return value

    @model_validator(mode="after")
    def _check_locked_identity(self) -> DailyEfficiencyCorrection:
        expected_id = derive_correction_occurrence_id(
            supersedes_kind=self.supersedes_kind,
            supersedes_window=self.supersedes_window,
            supersedes_digest=self.supersedes_digest,
        )
        if self.correction_id != expected_id:
            raise ValueError(
                "correction_id diverges from the locked keyed derivation; "
                "divergent identity reuse is rejected "
                f"(expected {expected_id!r}, got {self.correction_id!r})"
            )
        return self


__all__ = [
    "AcceptedOutcomeEconomics",
    "BaselineSnapshot",
    "CompatibilityEntry",
    "CompatibilityRole",
    "CostSourceKind",
    "DAILY_EFFICIENCY_CONTRACT_ID",
    "DAILY_EFFICIENCY_KINDS",
    "DailyEfficiencyCluster",
    "DailyEfficiencyCorrection",
    "DailyEfficiencyKind",
    "DailyEfficiencyPayloadId",
    "DailyEfficiencyProposal",
    "DailyEfficiencyReport",
    "DenominatorCoverage",
    "DurationObservation",
    "DwellFinding",
    "DwellFindingKind",
    "EFFICIENCY_COMPATIBILITY_REGISTRY",
    "EfficiencyCohortIdentity",
    "EfficiencyFinding",
    "EfficiencyFindingUnion",
    "FindingReferences",
    "IdleHandoffFinding",
    "LEGACY_CONTRACT_NAMES",
    "LEGACY_MAINTENANCE_KINDS",
    "LoopFinding",
    "LoopFindingKind",
    "OPERATIONAL_REPORT_SCAN_KINDS",
    "ObservationStatus",
    "ProposalKind",
    "QuantileBounds",
    "RobustnessKind",
    "RootCauseAlternative",
    "RootCauseCandidate",
    "RouteMismatchFinding",
    "RouteMismatchLeg",
    "ShadowMeasure",
    "ShadowMeasureKind",
    "UnavailableReason",
    "bind_cluster_signature",
    "check_registry_invariants",
    "cluster_for_daily_payload",
    "conversion_available",
    "decode_legacy_analysis",
    "decode_legacy_audit",
    "derive_cluster_occurrence_id",
    "derive_correction_occurrence_id",
    "derive_input_fingerprint",
    "derive_proposal_key",
    "derive_proposal_occurrence_id",
    "derive_report_occurrence_id",
    "is_daily_kind",
    "is_legacy_kind",
    "legacy_analysis_roundtrip",
    "legacy_audit_roundtrip",
    "require_cluster_signature_binding",
]