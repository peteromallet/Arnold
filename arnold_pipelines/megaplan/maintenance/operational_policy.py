"""Closed fail-closed operational stage policy, cohort facts, and stall classifier.

This module is the M4 pure policy surface (Plan Steps 1 and 2): typed stage
policy, cohort identity, comparable-sample facts, suppressor reasons,
observation facts, and operational decisions, plus the blocker-specific
classification logic that decides whether a loss of forward progress is a
dispatchable stall or must stay report-only.

Locked decisions (frozen, do not re-litigate):

* SD2 cold-start rule — adaptive cohort outputs (median/MAD/p95) are
  action-eligible only after at least 30 completed comparable samples from at
  least five distinct plans; below that threshold they are report-only.
* Production action is default-off (SD3): an explicit ``action_policy_approved``
  state is carried on the policy and on every decision so provisional numeric
  SLOs and lateness values can generate shadow reports but can never authorize
  repair.
* A stall is blocker-specific, not a status label: it requires an expired
  declared/static stage policy, no valid in-flight call or lease, no accepted
  decision/artifact/plan-version/frontier/coverage delta, and confirmation in a
  second coherent observation.
* Gate/finalize/review intervention requires the declared SLO to expire and
  cohort evidence to agree; daily p95 outlier flags can never act alone.
* Stage repetition is actionable after three equivalent failures, or two
  retry/revision cycles with the same input/error fingerprint and no material
  delta.
* Known backoff/fallback, fresh heartbeat with unmatched call start, declared
  long phase, thorough/extreme robustness, active lease, external
  PR/human/quota gate, and improving quality suppress intervention while
  retaining censored metrics; suppressed observations never become green by
  inference.

Fail-closed ordering (SC2 invariant): evidence sanity first (torn, stale,
cross-environment, incomplete, identity-mismatched, or incoherent evidence is
UNKNOWN/INCOHERENT and never dispatchable), then locked suppressors, then the
stall predicates, then repetition/no-progress rules, then the cold-start and
approval gates.  A predicate-ordering error cannot dispatch an invalid repair
because every earlier gate fails closed.

All models are frozen, forbid unknown fields, and round-trip through the single
canonical codec (``canonical_dumps`` / ``strict_loads``).  This module is
reference-only: it never constructs an owner authority record and never imports
an owner store.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from arnold_pipelines.megaplan.maintenance.contracts import (
    CoherenceState,
    CompletenessState,
    FreshnessState,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    EventWindow,
    ModelId,
    ProfileId,
    RunId,
    StageId,
    UtcTime,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Version of the pure classifier decision path (Step 2).  Bump only when the
#: predicate ordering or outcome semantics change.
CLASSIFIER_VERSION: str = "m4-operational-policy-v1"

#: Cold-start minimums (SD2, locked): adaptive median/MAD/p95 values may affect
#: action only after at least this many completed comparable samples ...
MIN_ADAPTIVE_SAMPLES: int = 30
#: ... from at least this many distinct plans.
MIN_ADAPTIVE_PLANS: int = 5


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class BlockKind(str, Enum):
    """Closed blocker-specific kinds the classifier may classify.

    A stall is always blocker-specific: the same predicates are interpreted
    differently for a plain stage expiry, a gate/finalize/review SLO expiry, a
    no-progress call, and a stage-repetition fingerprint.
    """

    STAGE = "stage"
    GATE_FINALIZE_REVIEW = "gate_finalize_review"
    NO_PROGRESS = "no_progress"
    STAGE_REPETITION = "stage_repetition"


class DeltaKind(str, Enum):
    """Accepted material deltas that prove forward progress.

    Any accepted delta defeats a stall: the loop detects concrete loss of
    forward progress, and an accepted decision, artifact digest, plan version,
    task frontier, or evidence-coverage improvement IS progress.
    """

    ACCEPTED_DECISION = "accepted_decision"
    ARTIFACT_DIGEST = "artifact_digest"
    PLAN_VERSION = "plan_version"
    TASK_FRONTIER = "task_frontier"
    EVIDENCE_COVERAGE = "evidence_coverage"


class SuppressorReason(str, Enum):
    """Every locked suppressor (brief ``Locked detection policy``).

    A suppressed observation retains its censored metrics and never becomes
    green or dispatchable by inference.
    """

    BACKOFF_OR_FALLBACK = "backoff_or_fallback"
    UNMATCHED_FRESH_CALL_START = "unmatched_fresh_call_start"
    DECLARED_LONG_PHASE = "declared_long_phase"
    THOROUGH_OR_EXTREME_ROBUSTNESS = "thorough_or_extreme_robustness"
    ACTIVE_LEASE = "active_lease"
    EXTERNAL_PR_HUMAN_QUOTA_GATE = "external_pr_human_quota_gate"
    IMPROVING_QUALITY = "improving_quality"


class DecisionOutcome(str, Enum):
    """Closed decision outcomes of the operational classifier.

    ``STALL`` is the only outcome that can ever be dispatchable, and even it
    stays report-only until the approval and cold-start gates hold.
    """

    STALL = "stall"
    SUPPRESSED = "suppressed"
    NO_STALL = "no_stall"
    UNKNOWN = "unknown"
    INCOHERENT = "incoherent"


class ReportOnlyReason(str, Enum):
    """Typed reasons a decision is explicitly report-only (never action)."""

    ACTION_POLICY_NOT_APPROVED = "action_policy_not_approved"
    COLD_START_ADAPTIVE_REPORT_ONLY = "cold_start_adaptive_report_only"
    SINGLE_OBSERVATION = "single_observation"


# ---------------------------------------------------------------------------
# Policy and cohort contracts (Step 1)
# ---------------------------------------------------------------------------


class CohortIdentity(BaseModel):
    """Cohort identity: run/stage/profile/model/environment dimensions.

    Cohort isolation is exact-match only: two cohorts match when every present
    dimension is exactly equal, and an absent (``None``) dimension never
    matches a present one.  Nothing is aliased or inferred.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run: RunId | None = None
    stage: StageId | None = None
    profile: ProfileId | None = None
    model: ModelId | None = None
    environment: EnvironmentId | None = None


def cohort_matches(left: CohortIdentity | None, right: CohortIdentity | None) -> bool:
    """Return ``True`` only when both cohorts are present and exactly equal.

    A missing cohort never matches anything (fail closed): classification
    cannot silently assume cohort agreement without a cohort identity.
    """
    if left is None or right is None:
        return False
    return (
        left.run == right.run
        and left.stage == right.stage
        and left.profile == right.profile
        and left.model == right.model
        and left.environment == right.environment
    )


class StagePolicy(BaseModel):
    """Declared/static stage policy with an explicit approval gate.

    ``declared_timeout_seconds`` and ``allowed_lateness_seconds`` are
    provisional numeric values: they may seed shadow reports, but repair is
    authorized only when ``action_policy_approved`` is explicitly ``True``
    (SD3, default-off).  ``declared_slo_expires_at`` is the declared UTC
    instant after which the stage policy is expired; expiry is computed, never
    asserted by an observation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: StageId
    policy_version: StrictStr
    declared_timeout_seconds: int = Field(ge=1)
    declared_slo_expires_at: UtcTime
    allowed_lateness_seconds: int = Field(default=300, ge=0)
    action_policy_approved: bool = False

    @field_validator("policy_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not value:
            raise ValueError("policy_version must be a non-empty string")
        return value


class ComparableSampleFacts(BaseModel):
    """Completed comparable-sample facts for one cohort (SD2 cold start).

    ``denominator`` is the total eligible sample count for the cohort.  A
    missing (``None``) or censored denominator is preserved explicitly and is
    never inferred: :attr:`completion_rate` returns ``None`` (never ``0``)
    when the denominator is missing, and ``missing_denominator`` is ``True``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed_comparable_samples: int = Field(ge=0)
    distinct_plans: int = Field(ge=0)
    #: Total eligible cohort samples (the denominator).  ``None`` is an
    #: explicit missing denominator — never promoted to zero.
    denominator: int | None = Field(default=None, ge=0)
    #: Samples censored by a suppressor or gate; retained, never dropped.
    censored_samples: int = Field(default=0, ge=0)
    unknown_samples: int = Field(default=0, ge=0)
    #: Adaptive cohort outputs — report-only until the cold-start rule and
    #: explicit approval both hold (SD2).
    median_seconds: float | None = Field(default=None, ge=0)
    mad_seconds: float | None = Field(default=None, ge=0)
    p95_seconds: float | None = Field(default=None, ge=0)

    @property
    def missing_denominator(self) -> bool:
        """True when the denominator is missing (``None``), never inferred."""
        return self.denominator is None

    def completion_rate(self) -> float | None:
        """Return completed/denominator, or ``None`` for a missing denominator.

        A missing or zero denominator is never treated as zero coverage:
        ``None`` is returned so downstream consumers cannot mistake absence
        for a green signal.
        """
        if self.denominator is None or self.denominator == 0:
            return None
        return self.completed_comparable_samples / self.denominator


def adaptive_action_eligible(samples: ComparableSampleFacts | None) -> bool:
    """Return whether adaptive cohort outputs may affect action (SD2).

    Requires at least :data:`MIN_ADAPTIVE_SAMPLES` completed comparable
    samples from at least :data:`MIN_ADAPTIVE_PLANS` distinct plans.  A
    missing facts object is never eligible (fail closed).
    """
    if samples is None:
        return False
    return (
        samples.completed_comparable_samples >= MIN_ADAPTIVE_SAMPLES
        and samples.distinct_plans >= MIN_ADAPTIVE_PLANS
    )


def adaptive_values_report_only(samples: ComparableSampleFacts | None) -> bool:
    """Return whether adaptive values are report-only for *samples*."""
    return not adaptive_action_eligible(samples)


# ---------------------------------------------------------------------------
# Observation facts (Step 2 input)
# ---------------------------------------------------------------------------


class ObservationFacts(BaseModel):
    """Typed evidence facts one observation contributes to the classifier.

    Fail-closed data invariants (enforced at construction and strict decode):

    * A COHERENT observation can never carry ``cross_environment``,
      ``identity_mismatch``, or ``torn`` evidence — such evidence must be
      declared INCOHERENT instead of being smuggled onto a coherent envelope.
    * A non-coherent observation can never be a ``second_coherent_observation``
      — confirmation requires a genuinely coherent second capture.

    Suppressor flags mirror the locked suppressor vocabulary one-to-one, and
    ``censored_metric_names`` records which metrics were censored so a
    suppressed observation keeps its censored metrics instead of dropping
    them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    observed_at: UtcTime
    window: EventWindow | None = None
    cohort: CohortIdentity | None = None
    block_kind: BlockKind = BlockKind.STAGE

    # Evidence sanity dimensions.
    coherence: CoherenceState
    completeness: CompletenessState
    freshness: FreshnessState
    cross_environment: bool = False
    identity_mismatch: bool = False
    torn: bool = False  # version tear on a source read

    # Blocker fingerprint and repetition evidence.
    fingerprint: StrictStr | None = None
    equivalent_failures: int = Field(default=0, ge=0)
    retry_revision_cycles: int = Field(default=0, ge=0)
    same_fingerprint: bool = False

    # Liveness and progress predicates.
    live_call: bool = False
    live_lease: bool = False
    material_deltas: tuple[DeltaKind, ...] = ()
    no_progress_cost_increasing: bool = False

    # Gate/finalize/review cohort agreement (daily p95 flags can never act).
    cohort_agrees: bool = True

    # Confirmation: a stall requires a second coherent observation.
    second_coherent_observation: bool = False

    # Every locked suppressor (brief ``Locked detection policy``).
    backoff_or_fallback: bool = False
    unmatched_fresh_call_start: bool = False
    declared_long_phase: bool = False
    thorough_or_extreme_robustness: bool = False
    external_pr_human_quota_gate: bool = False
    improving_quality: bool = False

    # Censored metrics retained on suppressed observations.
    censored_metric_names: tuple[str, ...] = ()

    @field_validator("censored_metric_names")
    @classmethod
    def _validate_censored(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for name in value:
            if not name:
                raise ValueError("censored metric names must be non-empty strings")
        return value

    @field_validator("fingerprint")
    @classmethod
    def _validate_fingerprint(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("fingerprint must be a non-empty string when present")
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed_facts(self) -> ObservationFacts:
        if self.coherence is CoherenceState.COHERENT and (
            self.cross_environment or self.identity_mismatch or self.torn
        ):
            raise ValueError(
                "a coherent observation cannot carry cross_environment, "
                "identity_mismatch, or torn evidence; declare it INCOHERENT instead"
            )
        if self.coherence is not CoherenceState.COHERENT and self.second_coherent_observation:
            raise ValueError(
                f"coherence {self.coherence.value!r} cannot be a second coherent "
                "observation; confirmation requires a genuinely coherent capture"
            )
        return self


# ---------------------------------------------------------------------------
# Operational decision (Step 1 output contract)
# ---------------------------------------------------------------------------


class OperationalDecision(BaseModel):
    """Closed classifier decision with an explicit, fail-closed action gate.

    ``dispatchable`` may be ``True`` ONLY when the outcome is ``STALL``, the
    policy approval is explicitly ``True``, no report-only reason applies, no
    suppressor applies, and no metrics were censored.  ``green`` may be
    ``True`` only when ``dispatchable`` is ``True`` — a suppressed or
    report-only observation is never green by inference.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: StrictStr
    classifier_version: StrictStr = CLASSIFIER_VERSION
    block_kind: BlockKind | None = None
    fingerprint: StrictStr | None = None
    outcome: DecisionOutcome
    #: Explicit approval mirror of the governing StagePolicy (SD3, default-off).
    action_policy_approved: bool = False
    dispatchable: bool = False
    green: bool = False
    suppressors: tuple[SuppressorReason, ...] = ()
    report_only_reasons: tuple[ReportOnlyReason, ...] = ()
    censored_metrics: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    @field_validator("policy_version", "classifier_version")
    @classmethod
    def _validate_versions(cls, value: str) -> str:
        if not value:
            raise ValueError("version strings must be non-empty")
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed_decision(self) -> OperationalDecision:
        if self.green and not self.dispatchable:
            raise ValueError(
                "green requires dispatchable; a non-dispatchable decision is "
                "never green by inference"
            )
        if not self.dispatchable:
            return self
        if self.outcome is not DecisionOutcome.STALL:
            raise ValueError(
                f"only a STALL outcome can be dispatchable, got {self.outcome.value!r}"
            )
        if not self.action_policy_approved:
            raise ValueError("a dispatchable decision requires explicit action_policy_approved")
        if self.suppressors:
            raise ValueError(
                "a suppressed decision can never be dispatchable; "
                f"got suppressors {[s.value for s in self.suppressors]}"
            )
        if self.report_only_reasons:
            raise ValueError(
                "a report-only decision can never be dispatchable; "
                f"got reasons {[r.value for r in self.report_only_reasons]}"
            )
        if self.censored_metrics:
            raise ValueError(
                "a decision with censored metrics can never be dispatchable; "
                f"got {list(self.censored_metrics)}"
            )
        return self


# ---------------------------------------------------------------------------
# Predicates (Step 2) — every predicate is a pure function of typed facts
# ---------------------------------------------------------------------------


def policy_is_expired(policy: StagePolicy, facts: ObservationFacts) -> bool:
    """Return whether the declared/static stage policy is expired.

    Expiry is computed from the declared SLO horizon and the observation
    instant — an observation can never assert its own expiry.
    """
    return facts.observed_at.root >= policy.declared_slo_expires_at.root


def slo_expired(policy: StagePolicy, facts: ObservationFacts) -> bool:
    """Return whether the relevant SLO is expired for gate/finalize/review.

    Gate/finalize/review intervention requires the declared SLO to expire AND
    cohort evidence to agree; a daily p95 outlier flag (``cohort_agrees``
    False) can never act.  For every other blocker kind the declared policy
    expiry alone is the SLO gate.
    """
    if not policy_is_expired(policy, facts):
        return False
    if facts.block_kind is BlockKind.GATE_FINALIZE_REVIEW and not facts.cohort_agrees:
        return False
    return True


def evidence_coherent(facts: ObservationFacts) -> bool:
    """Return whether the observation is one version-coherent, fresh, complete,
    single-environment truth with matching identities."""
    return (
        facts.coherence is CoherenceState.COHERENT
        and facts.completeness is CompletenessState.COMPLETE
        and facts.freshness is FreshnessState.FRESH
        and not facts.cross_environment
        and not facts.identity_mismatch
        and not facts.torn
    )


def has_material_delta(facts: ObservationFacts) -> bool:
    """Return whether any accepted decision/artifact/plan/frontier/coverage
    delta proves forward progress."""
    return bool(facts.material_deltas)


def suppressors_for(facts: ObservationFacts) -> tuple[SuppressorReason, ...]:
    """Return every locked suppressor that applies to *facts*.

    The seven suppressors map one-to-one onto the brief's locked detection
    policy.  Order is deterministic (enum declaration order) so decisions are
    digest-stable.
    """
    reasons: list[SuppressorReason] = []
    if facts.backoff_or_fallback:
        reasons.append(SuppressorReason.BACKOFF_OR_FALLBACK)
    if facts.unmatched_fresh_call_start:
        reasons.append(SuppressorReason.UNMATCHED_FRESH_CALL_START)
    if facts.declared_long_phase:
        reasons.append(SuppressorReason.DECLARED_LONG_PHASE)
    if facts.thorough_or_extreme_robustness:
        reasons.append(SuppressorReason.THOROUGH_OR_EXTREME_ROBUSTNESS)
    if facts.live_lease:
        reasons.append(SuppressorReason.ACTIVE_LEASE)
    if facts.external_pr_human_quota_gate:
        reasons.append(SuppressorReason.EXTERNAL_PR_HUMAN_QUOTA_GATE)
    if facts.improving_quality:
        reasons.append(SuppressorReason.IMPROVING_QUALITY)
    return tuple(reasons)


def repetition_met(facts: ObservationFacts) -> bool:
    """Return whether the locked stage-repetition rule is satisfied.

    Actionable after three equivalent failures, OR two retry/revision cycles
    with the same input/error fingerprint and no material delta.
    """
    if facts.equivalent_failures >= 3:
        return True
    return (
        facts.retry_revision_cycles >= 2
        and facts.same_fingerprint
        and not has_material_delta(facts)
    )


def no_progress_met(facts: ObservationFacts) -> bool:
    """Return whether the locked no-progress rule is satisfied.

    No-progress calls require increasing time/cost without any accepted
    decision, artifact digest, plan version, task frontier, or
    evidence-coverage improvement.
    """
    return facts.no_progress_cost_increasing and not has_material_delta(facts)


# ---------------------------------------------------------------------------
# The classifier (Step 2) — one fail-closed decision path
# ---------------------------------------------------------------------------


def classify_stall(
    *,
    policy: StagePolicy,
    facts: ObservationFacts,
    samples: ComparableSampleFacts | None = None,
    uses_adaptive_slo: bool = False,
) -> OperationalDecision:
    """Classify one observation into an :class:`OperationalDecision`.

    Fail-closed ordering (a predicate-ordering error cannot dispatch an
    invalid repair):

    1. Evidence sanity — torn, identity-mismatched, cross-environment, or
       incoherent evidence is ``INCOHERENT``; stale, incomplete, or
       unknown-coherence evidence is ``UNKNOWN``.  Never dispatchable.
    2. Locked suppressors — any suppressor yields ``SUPPRESSED`` with the
       observation's censored metrics retained.  Never dispatchable, never
       green.
    3. SLO gate — gate/finalize/review requires declared SLO expiry AND cohort
       agreement; every blocker requires the declared stage policy to be
       expired.
    4. Liveness — a valid in-flight call or lease defeats a stall.
    5. Progress — any accepted material delta defeats a stall.
    6. Confirmation — a stall requires a second coherent observation.
    7. Block rules — stage repetition requires the locked repetition rule;
       no-progress requires increasing cost without accepted improvement.
    8. Authorization — a STALL becomes dispatchable only when
       ``action_policy_approved`` is explicitly True AND (when the effective
       SLO is adaptive) the cold-start rule holds (30 samples / 5 plans).
    """
    reasons: list[str] = []

    # 1. Evidence sanity (explicit UNKNOWN / INCOHERENT, never dispatchable).
    if facts.coherence is CoherenceState.INCOHERENT or facts.cross_environment:
        return OperationalDecision(
            policy_version=policy.policy_version,
            block_kind=facts.block_kind,
            fingerprint=facts.fingerprint,
            outcome=DecisionOutcome.INCOHERENT,
            action_policy_approved=policy.action_policy_approved,
            reasons=("incoherent or cross-environment evidence",),
        )
    if (
        facts.identity_mismatch
        or facts.torn
        or facts.coherence is CoherenceState.UNKNOWN
        or facts.completeness is not CompletenessState.COMPLETE
        or facts.freshness is not FreshnessState.FRESH
    ):
        outcome = (
            DecisionOutcome.INCOHERENT
            if (facts.identity_mismatch or facts.torn)
            else DecisionOutcome.UNKNOWN
        )
        return OperationalDecision(
            policy_version=policy.policy_version,
            block_kind=facts.block_kind,
            fingerprint=facts.fingerprint,
            outcome=outcome,
            action_policy_approved=policy.action_policy_approved,
            reasons=(
                "identity-mismatched or torn evidence"
                if outcome is DecisionOutcome.INCOHERENT
                else "stale, incomplete, or unknown-coherence evidence",
            ),
        )

    # 2. Locked suppressors — censored metrics retained, never green.
    suppressors = suppressors_for(facts)
    if suppressors:
        return OperationalDecision(
            policy_version=policy.policy_version,
            block_kind=facts.block_kind,
            fingerprint=facts.fingerprint,
            outcome=DecisionOutcome.SUPPRESSED,
            action_policy_approved=policy.action_policy_approved,
            suppressors=suppressors,
            censored_metrics=facts.censored_metric_names,
            reasons=("suppressed observation retains censored metrics",),
        )

    # 3. SLO gate: declared stage policy must be expired (and for
    #    gate/finalize/review, cohort evidence must agree).
    if not slo_expired(policy, facts):
        reasons.append("declared stage policy is not expired")
        if facts.block_kind is BlockKind.GATE_FINALIZE_REVIEW and not facts.cohort_agrees:
            reasons.append("cohort evidence does not agree; daily p95 flags cannot act")
        return OperationalDecision(
            policy_version=policy.policy_version,
            block_kind=facts.block_kind,
            fingerprint=facts.fingerprint,
            outcome=DecisionOutcome.NO_STALL,
            action_policy_approved=policy.action_policy_approved,
            reasons=tuple(reasons),
        )

    # 4. Liveness: a valid in-flight call or lease defeats a stall.
    if facts.live_call or facts.live_lease:
        return OperationalDecision(
            policy_version=policy.policy_version,
            block_kind=facts.block_kind,
            fingerprint=facts.fingerprint,
            outcome=DecisionOutcome.NO_STALL,
            action_policy_approved=policy.action_policy_approved,
            reasons=("valid in-flight call or lease",),
        )

    # 5. Progress: any accepted material delta defeats a stall.
    if has_material_delta(facts):
        return OperationalDecision(
            policy_version=policy.policy_version,
            block_kind=facts.block_kind,
            fingerprint=facts.fingerprint,
            outcome=DecisionOutcome.NO_STALL,
            action_policy_approved=policy.action_policy_approved,
            reasons=("accepted material delta proves forward progress",),
        )

    # 6. Confirmation: a stall requires a second coherent observation.
    if not facts.second_coherent_observation:
        return OperationalDecision(
            policy_version=policy.policy_version,
            block_kind=facts.block_kind,
            fingerprint=facts.fingerprint,
            outcome=DecisionOutcome.NO_STALL,
            action_policy_approved=policy.action_policy_approved,
            report_only_reasons=(ReportOnlyReason.SINGLE_OBSERVATION,),
            reasons=("single coherent observation; confirmation required",),
        )

    # 7. Block-specific rules.
    if facts.block_kind is BlockKind.STAGE_REPETITION and not repetition_met(facts):
        return OperationalDecision(
            policy_version=policy.policy_version,
            block_kind=facts.block_kind,
            fingerprint=facts.fingerprint,
            outcome=DecisionOutcome.NO_STALL,
            action_policy_approved=policy.action_policy_approved,
            reasons=("stage repetition rule not met",),
        )
    if facts.block_kind is BlockKind.NO_PROGRESS and not no_progress_met(facts):
        return OperationalDecision(
            policy_version=policy.policy_version,
            block_kind=facts.block_kind,
            fingerprint=facts.fingerprint,
            outcome=DecisionOutcome.NO_STALL,
            action_policy_approved=policy.action_policy_approved,
            reasons=(
                "no-progress rule not met: cost not increasing or "
                "accepted improvement present",
            ),
        )

    # 8. Authorization: explicit approval + cold-start rule when adaptive.
    report_only: list[ReportOnlyReason] = []
    dispatchable = policy.action_policy_approved
    if uses_adaptive_slo and not adaptive_action_eligible(samples):
        dispatchable = False
        report_only.append(ReportOnlyReason.COLD_START_ADAPTIVE_REPORT_ONLY)
    if not policy.action_policy_approved:
        dispatchable = False
        report_only.append(ReportOnlyReason.ACTION_POLICY_NOT_APPROVED)
    return OperationalDecision(
        policy_version=policy.policy_version,
        block_kind=facts.block_kind,
        fingerprint=facts.fingerprint,
        outcome=DecisionOutcome.STALL,
        action_policy_approved=policy.action_policy_approved,
        dispatchable=dispatchable,
        green=dispatchable,
        report_only_reasons=tuple(report_only),
        reasons=(
            "all locked stall predicates and confirmation hold"
            if dispatchable
            else "stall confirmed but action authorization does not hold",
        ),
    )


__all__ = [
    "CLASSIFIER_VERSION",
    "MIN_ADAPTIVE_PLANS",
    "MIN_ADAPTIVE_SAMPLES",
    "BlockKind",
    "CohortIdentity",
    "ComparableSampleFacts",
    "DecisionOutcome",
    "DeltaKind",
    "ObservationFacts",
    "OperationalDecision",
    "ReportOnlyReason",
    "StagePolicy",
    "SuppressorReason",
    "adaptive_action_eligible",
    "adaptive_values_report_only",
    "classify_stall",
    "cohort_matches",
    "evidence_coherent",
    "has_material_delta",
    "no_progress_met",
    "policy_is_expired",
    "repetition_met",
    "slo_expired",
    "suppressors_for",
]
