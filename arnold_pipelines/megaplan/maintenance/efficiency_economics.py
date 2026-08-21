"""M5 route-mismatch and accepted-outcome economics (Plan Step 17 / T17).

This module implements the deterministic, store-free economics and route
comparison over normalized accepted task/milestone outcomes (Step 11
normalized facts, consumed as pure inputs — never owner stores):

* :func:`analyze_route_mismatches` — compares the expected route, the
  resolved route, and the provider-reported actual model from immutable
  dispatch/routing receipts.  A missing leg stays typed ``None``/unknown —
  NEVER a mismatch (SC18); provider aliases are treated as equivalent ONLY
  where owner receipts declare them (:class:`DeclaredRouteAlias`), never
  inferred;
* :func:`compute_outcome_economics` — time, tokens, authoritative cost, and
  quality delta per accepted task/milestone outcome, NEVER raw totals:
  every economics payload is denominator-gated (the exact accepted-outcome
  count), competing cost sources are never silently merged, authoritative
  cost claims name a typed :class:`CostSourceKind` and pin the exact
  dispatch receipt / work-ledger coordinate (T3 contract), and missing
  measures stay explicit ``None`` — never coerced to zero (SC18);
* :func:`estimate_avoidable_impact` — conservative avoidable-impact
  estimate as a bounded excess over an eligible cohort/SLO reference with
  explicit lower/upper/unknown bounds for censored or missing measures;
  legitimate expensive high-depth outcomes (exploration / deep work /
  backoff / human gates / productive work) are excluded from avoidable
  impact entirely and retained as covariates only.

Design rules (locked Step 17 policy):

* **Per accepted outcome, never raw totals.**  Each
  :class:`NormalizedAcceptedOutcome` binds one exact accepted outcome
  (``accepted_outcome_identity``); every economics claim carries that exact
  denominator (1 per outcome) and per-accepted values.  Raw totals are
  carried only as explicit context inside :class:`AcceptedOutcomeEconomics`
  alongside the denominator — never as the primary claim.
* **Authoritative cost precedence.**  When both a provider-reported cost
  and a WBC work-ledger cost are available for the same outcome, the WBC
  work ledger is the authoritative source (it records the committed
  dispatch); the two sources are NEVER merged.  The claim names the typed
  authoritative source and pins its exact receipt/ledger coordinate.
* **Aliases only where declared.**  Route equality applies the declared
  alias bindings from owner receipts (:class:`DeclaredRouteAlias`) — an
  undeclared provider model spelling is a mismatch, never silently aliased.
* **Quality delta.**  ``quality_delta`` is the exact difference between the
  outcome's provider-reported quality and its cohort expected quality when
  both are present; a negative delta is a quality regression (never
  coerced, never inferred from missing quality).
* **Censoring and missing measures stay explicit.**  A censored outcome
  carries no exact time and an explicit ``lower_bound_seconds`` (never
  coerced to completion or zero); missing time/tokens/cost/quality stay
  ``None``.  Avoidable-impact bounds are conservative: exact proven excess
  contributes to the lower bound, censored known floors contribute to the
  lower bound as floors, and any censored/missing measure makes the finite
  upper bound ``None`` (unknown).
* **Determinism.**  All comparison, reference unions, and output ordering
  are input-order independent; findings are sorted by finding ID.

Inputs are pure :class:`NormalizedAcceptedOutcome` facts; this module never
constructs or mutates an owner store.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from arnold_pipelines.megaplan.maintenance.efficiency_contracts import (
    DAILY_EFFICIENCY_CONTRACT_ID,
    AcceptedOutcomeEconomics,
    CostSourceKind,
    DenominatorCoverage,
    FindingReferences,
    QuantileBounds,
    RobustnessKind,
    RouteMismatchFinding,
    RouteMismatchLeg,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    UtcTime,
    canonical_json,
)

#: Default classifier version used for finding-ID derivation when the caller
#: does not pin one (classifier-version separation is part of the signature).
DEFAULT_CLASSIFIER_VERSION: str = "cls-v1"


def _sha256_hex(material: str) -> str:
    """Canonical sha256 hex digest of *material*."""
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic (owner, locator, digest, cursor) reference order."""
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


class OutcomeExclusionReason(str, Enum):
    """Typed reasons an outcome is excluded from avoidable impact (SC18).

    Legitimate expensive high-depth work, deliberate exploration, configured
    backoff, known human gates, and productive work are NEVER counted as
    avoidable excess; their context is retained as covariates instead.
    """

    LEGITIMATE_DEPTH = "legitimate_depth"
    EXPLORATION = "exploration"
    CONFIGURED_BACKOFF = "configured_backoff"
    HUMAN_GATE = "human_gate"
    PRODUCTIVE = "productive"


class DeclaredRouteAlias(BaseModel):
    """One declared provider-alias binding from an owner receipt.

    ``canonical`` is the canonical route/model identity and ``aliases`` are
    the provider-reported spellings that owner receipts declare equivalent.
    Route comparison applies ONLY these declared bindings — an undeclared
    spelling is a mismatch, never silently aliased (SC18).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    canonical: StrictStr
    aliases: tuple[StrictStr, ...] = ()

    @field_validator("canonical")
    @classmethod
    def _validate_canonical(cls, value: str) -> str:
        if not value:
            raise ValueError("declared alias canonical identity must be non-empty")
        return value

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, value: Sequence[str]) -> tuple[str, ...]:
        cleaned = tuple(sorted({alias for alias in value if alias}))
        return cleaned


class NormalizedAcceptedOutcome(BaseModel):
    """One normalized accepted task/milestone outcome (Step 17 input).

    Binds the exact accepted-outcome identity (the impact denominator basis:
    every economics claim is per this exact accepted outcome), the expected /
    resolved / provider-actual route legs, exact time/tokens/cost/quality
    measures (explicit ``None`` when missing — never coerced to zero), the
    typed authoritative cost source, and the retained robustness,
    exploration, censoring, and coverage covariates.  A **censored** outcome
    carries no exact time and an explicit ``lower_bound_seconds`` (never
    coerced to completion or zero).  Active repair custody appears only as
    reference/covariate refs — never claimed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    outcome_id: StrictStr
    #: Exact accepted outcome identity (``run_id@run_revision``) — the
    #: denominator basis of every economics claim.
    accepted_outcome_identity: StrictStr
    stage: StrictStr
    expected_route: StrictStr | None = None
    resolved_route: StrictStr | None = None
    provider_actual_route: StrictStr | None = None
    time_seconds: float | None = Field(default=None, ge=0)
    tokens: float | None = Field(default=None, ge=0)
    #: Provider-reported cost (lower precedence; never merged with ledger).
    provider_reported_cost: float | None = Field(default=None, ge=0)
    provider_reported_cost_ref: OwnerRef | None = None
    #: WBC work-ledger cost (authoritative precedence; never merged).
    work_ledger_cost: float | None = Field(default=None, ge=0)
    work_ledger_cost_ref: OwnerRef | None = None
    #: Provider-reported quality score and cohort expected quality covariate.
    quality: float | None = None
    expected_quality: float | None = None
    robustness: RobustnessKind | None = None
    exploration: bool = False
    censored: bool = False
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    #: Typed exclusion reason (SC18); present exactly when an exclusion flag
    #: (deep_work/exploration/configured_backoff/human_gate/productive) is set.
    excluded_reason: OutcomeExclusionReason | None = None
    deep_work: bool = False
    configured_backoff: bool = False
    human_gate: bool = False
    productive: bool = False
    #: Explicit metric denominator/coverage covariate (never fabricated).
    coverage: DenominatorCoverage | None = None
    #: Exact source evidence refs for this outcome (mandatory).
    refs: tuple[OwnerRef, ...] = ()
    accepted_resolution_refs: tuple[OwnerRef, ...] = ()
    gate_backoff_refs: tuple[OwnerRef, ...] = ()
    censoring_refs: tuple[OwnerRef, ...] = ()
    active_custody_refs: tuple[OwnerRef, ...] = ()

    @field_validator("outcome_id", "accepted_outcome_identity", "stage")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("outcome identities/stage must be non-empty strings")
        return value

    @field_validator("expected_route", "resolved_route", "provider_actual_route")
    @classmethod
    def _validate_routes(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("route identities must be non-empty strings when present")
        return value

    @field_validator("refs", "accepted_resolution_refs", "gate_backoff_refs",
                     "censoring_refs", "active_custody_refs")
    @classmethod
    def _sort_reference_groups(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_outcome(self) -> NormalizedAcceptedOutcome:
        if not self.refs:
            raise ValueError(
                "normalized outcomes require at least one exact source ref"
            )
        if not self.accepted_resolution_refs:
            raise ValueError(
                "normalized outcomes require exact accepted_resolution_refs "
                "(every economics/mismatch claim anchors to the accepted "
                "resolution)"
            )
        if self.censored:
            if self.time_seconds is not None:
                raise ValueError(
                    "censored outcomes cannot carry an exact time_seconds"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "censored outcomes require an explicit lower_bound_seconds"
                )
        else:
            if self.lower_bound_seconds is not None:
                raise ValueError(
                    "completed outcomes cannot carry a lower_bound_seconds"
                )
        if self.work_ledger_cost is not None and self.work_ledger_cost_ref is None:
            raise ValueError(
                "work-ledger cost requires an exact work_ledger_cost_ref "
                "pinning the ledger coordinate"
            )
        if self.provider_reported_cost is not None and self.provider_reported_cost_ref is None:
            raise ValueError(
                "provider-reported cost requires an exact "
                "provider_reported_cost_ref pinning the dispatch receipt"
            )
        flags = (
            self.deep_work,
            self.exploration,
            self.configured_backoff,
            self.human_gate,
            self.productive,
        )
        if any(flags) != (self.excluded_reason is not None):
            raise ValueError(
                "excluded_reason must be present exactly when an exclusion "
                "flag (deep_work/exploration/configured_backoff/human_gate/"
                "productive) is set"
            )
        return self

    @property
    def time_lower_bound(self) -> float | None:
        """Exact time (completed) or explicit lower bound (censored)."""
        if self.censored:
            return self.lower_bound_seconds
        return self.time_seconds


def authoritative_cost(
    outcome: NormalizedAcceptedOutcome,
) -> tuple[float, CostSourceKind, OwnerRef] | None:
    """Resolve the authoritative cost of one outcome (never merged).

    The WBC work ledger is the authoritative source when present; otherwise
    the provider-reported cost applies.  Competing sources are NEVER
    merged — exactly one source is named with its exact coordinate.
    Returns ``None`` when no cost is available (explicit unknown).
    """
    if outcome.work_ledger_cost is not None:
        return (
            float(outcome.work_ledger_cost),
            CostSourceKind.WBC_WORK_LEDGER,
            outcome.work_ledger_cost_ref,  # type: ignore[arg-type]
        )
    if outcome.provider_reported_cost is not None:
        return (
            float(outcome.provider_reported_cost),
            CostSourceKind.PROVIDER_REPORTED,
            outcome.provider_reported_cost_ref,  # type: ignore[arg-type]
        )
    return None


def derive_route_mismatch_finding_id(
    *,
    outcome_identity: str,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> str:
    """Deterministic route-mismatch finding ID from the outcome identity.

    ``efficiency_route_mismatch|{sha256(outcome_identity|classifier_version)}``
    — one finding per normalized accepted outcome (never over raw owner
    occurrence coordinates).
    """
    if not outcome_identity:
        raise ValueError("route-mismatch finding IDs require an outcome identity")
    material = canonical_json(
        {
            "family": "route_mismatch",
            "outcome_identity": outcome_identity,
            "classifier_version": classifier_version,
        }
    )
    return f"efficiency_route_mismatch|{_sha256_hex(material)}"


def _canonical_route(
    route: str | None,
    aliases: Sequence[DeclaredRouteAlias],
) -> str | None:
    """Resolve *route* through the DECLARED alias bindings (SC18).

    A route matching a declared alias resolves to its canonical identity;
    an undeclared spelling stays as-is (never silently aliased).  Missing
    legs stay ``None`` — typed unknown, never a mismatch.
    """
    if route is None:
        return None
    for binding in aliases:
        if route in binding.aliases:
            return binding.canonical
    return route


def _mismatch_legs(
    expected: str | None,
    resolved: str | None,
    actual: str | None,
) -> tuple[RouteMismatchLeg, ...]:
    """Named mismatch legs over the canonical routes (missing = never mismatch)."""
    legs: list[RouteMismatchLeg] = []
    pairs: tuple[tuple[RouteMismatchLeg, str | None, str | None], ...] = (
        (RouteMismatchLeg.EXPECTED_VS_RESOLVED, expected, resolved),
        (RouteMismatchLeg.RESOLVED_VS_PROVIDER_ACTUAL, resolved, actual),
        (RouteMismatchLeg.EXPECTED_VS_PROVIDER_ACTUAL, expected, actual),
    )
    for leg, left, right in pairs:
        if left is None or right is None:
            continue
        if left != right:
            legs.append(leg)
    return tuple(sorted(legs, key=lambda leg: leg.value))


def analyze_route_mismatches(
    outcomes: Sequence[NormalizedAcceptedOutcome],
    *,
    declared_aliases: Sequence[DeclaredRouteAlias] = (),
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> tuple[RouteMismatchFinding, ...]:
    """Route-mismatch analyzer: expected vs resolved vs provider actual.

    Compares the three route legs per accepted outcome after applying ONLY
    the declared alias bindings (SC18).  A missing leg stays ``None`` —
    typed unknown, NEVER a mismatch.  Outcomes with no differing leg
    produce no finding (routes are consistent); each finding carries the
    exact reference bundle and denominator-gated economics.
    """
    findings: list[RouteMismatchFinding] = []
    for outcome in outcomes:
        expected = _canonical_route(outcome.expected_route, declared_aliases)
        resolved = _canonical_route(outcome.resolved_route, declared_aliases)
        actual = _canonical_route(outcome.provider_actual_route, declared_aliases)
        legs = _mismatch_legs(expected, resolved, actual)
        if not legs:
            continue
        findings.append(
            RouteMismatchFinding(
                finding_id=derive_route_mismatch_finding_id(
                    outcome_identity=outcome.accepted_outcome_identity,
                    classifier_version=classifier_version,
                ),
                references=FindingReferences(
                    accepted_resolution_refs=outcome.accepted_resolution_refs,
                    active_custody_refs=outcome.active_custody_refs,
                    source_refs=outcome.refs,
                    gate_backoff_refs=outcome.gate_backoff_refs,
                    censoring_refs=outcome.censoring_refs,
                ),
                economics=compute_outcome_economics(outcome),
                expected_route=outcome.expected_route,
                resolved_route=outcome.resolved_route,
                provider_actual_route=outcome.provider_actual_route,
                mismatch_legs=legs,
            )
        )
    return tuple(sorted(findings, key=lambda finding: finding.finding_id))


class OutcomeEconomicsRecord(BaseModel):
    """One accepted outcome's denominator-gated economics with covariates.

    Wraps the strict :class:`AcceptedOutcomeEconomics` payload (never raw
    totals without the exact accepted-outcome denominator) together with the
    retained robustness, exploration, censoring, and coverage covariates
    (SC18).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    outcome_id: StrictStr
    economics: AcceptedOutcomeEconomics
    robustness: RobustnessKind | None = None
    exploration: bool = False
    censored: bool = False
    coverage: float | None = None


def compute_outcome_economics(
    outcome: NormalizedAcceptedOutcome,
) -> AcceptedOutcomeEconomics | None:
    """Time/tokens/authoritative cost/quality delta per exact accepted outcome.

    The denominator is the exact accepted-outcome count (1 per normalized
    outcome); per-accepted values are the outcome's exact measures — missing
    measures stay explicit ``None``, never coerced to zero.  Authoritative
    cost applies :func:`authoritative_cost` precedence (WBC work ledger >
    provider reported; never merged) and names the typed source with its
    exact coordinate (T3 contract).  ``quality_delta`` is actual minus
    expected quality when both are present.

    Returns ``None`` when the outcome carries no economics-relevant measure
    at all (a denominator-only payload with no claims is not emitted).
    """
    cost = authoritative_cost(outcome)
    cost_value = cost[0] if cost is not None else None
    cost_source = cost[1] if cost is not None else None
    cost_source_ref = cost[2] if cost is not None else None
    quality_delta: float | None = None
    if outcome.quality is not None and outcome.expected_quality is not None:
        quality_delta = round(outcome.quality - outcome.expected_quality, 6)

    claims = {
        "time_seconds_per_accepted": (
            None if outcome.censored else outcome.time_seconds
        ),
        "tokens_per_accepted": outcome.tokens,
        "cost_per_accepted": cost_value,
        "quality_delta": quality_delta,
    }
    if all(value is None for value in claims.values()):
        return None
    return AcceptedOutcomeEconomics(
        accepted_outcome_count=1,
        time_seconds_per_accepted=claims["time_seconds_per_accepted"],
        tokens_per_accepted=claims["tokens_per_accepted"],
        cost_per_accepted=claims["cost_per_accepted"],
        quality_delta=claims["quality_delta"],
        raw_time_seconds_total=(
            None if outcome.censored else outcome.time_seconds
        ),
        raw_tokens_total=outcome.tokens,
        raw_cost_total=cost_value,
        cost_source=cost_source,
        cost_source_ref=cost_source_ref,
    )


def analyze_outcome_economics(
    outcomes: Sequence[NormalizedAcceptedOutcome],
) -> tuple[OutcomeEconomicsRecord, ...]:
    """Per-accepted-outcome economics with retained covariates (SC18)."""
    records: list[OutcomeEconomicsRecord] = []
    for outcome in outcomes:
        economics = compute_outcome_economics(outcome)
        if economics is None:
            continue
        records.append(
            OutcomeEconomicsRecord(
                outcome_id=outcome.outcome_id,
                economics=economics,
                robustness=outcome.robustness,
                exploration=outcome.exploration,
                censored=outcome.censored,
                coverage=(
                    outcome.coverage.coverage
                    if outcome.coverage is not None
                    else None
                ),
            )
        )
    return tuple(
        sorted(records, key=lambda record: record.outcome_id)
    )


class AvoidableImpactEstimate(BaseModel):
    """Conservative avoidable-impact estimate (bounded excess over a reference).

    ``eligible_bound_seconds`` is the declared SLO or the conservative p95
    upper bound used as the excess reference (never inferred when absent).
    ``lower_bound_seconds`` is the sum of exact proven excess plus the
    explicit censored known floors; ``upper_bound_seconds`` is ``None``
    (unknown) whenever any avoidable-eligible measure is censored or
    missing — a finite upper bound is only claimed when every contributing
    measure is exact.  Excluded legitimate high-depth/exploration/backoff/
    human-gate/productive outcomes never enter the bounds (SC18).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    eligible_bound_seconds: float | None = Field(default=None, ge=0)
    lower_bound_seconds: float = Field(ge=0)
    upper_bound_seconds: float | None = Field(default=None, ge=0)
    unknown_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    eligible_outcome_count: int = Field(ge=0)


def estimate_avoidable_impact(
    outcomes: Sequence[NormalizedAcceptedOutcome],
    *,
    p95: QuantileBounds | None = None,
    slo_seconds: float | None = None,
) -> AvoidableImpactEstimate:
    """Conservative avoidable-impact estimate over an eligible cohort/SLO.

    The eligible reference bound is the declared ``slo_seconds`` when
    present, otherwise the conservative ``p95.upper_bound``; with neither, no
    excess can be proven and every avoidable-eligible outcome is unknown
    (a reference is never inferred).

    For each avoidable-eligible outcome (not excluded):

    * completed with an exact time above the bound contributes its exact
      excess to the lower bound;
    * censored outcomes contribute their known lower-bound excess as a
      floor and mark the measure unknown — the finite upper bound becomes
      ``None``;
    * missing time (no exact measure and no lower bound) marks the measure
      unknown — the finite upper bound becomes ``None``.

    Excluded outcomes (legitimate expensive high-depth / exploration /
    backoff / human gate / productive) never enter the bounds and are
    counted in ``excluded_count`` (their context is retained via the
    covariates on :class:`NormalizedAcceptedOutcome`).
    """
    bound = slo_seconds if slo_seconds is not None else (
        p95.upper_bound if p95 is not None else None
    )
    if bound is None:
        eligible = [
            outcome for outcome in outcomes if outcome.excluded_reason is None
        ]
        return AvoidableImpactEstimate(
            eligible_bound_seconds=None,
            lower_bound_seconds=0.0,
            upper_bound_seconds=None,
            unknown_count=len(eligible),
            excluded_count=len(outcomes) - len(eligible),
            eligible_outcome_count=0,
        )

    lower_bound = 0.0
    unknown_count = 0
    censored_or_missing = False
    excluded_count = 0
    eligible_outcome_count = 0
    for outcome in outcomes:
        if outcome.excluded_reason is not None:
            excluded_count += 1
            continue
        eligible_outcome_count += 1
        if outcome.censored:
            floor = outcome.lower_bound_seconds
            if floor is None:
                unknown_count += 1
                censored_or_missing = True
                continue
            excess = max(0.0, float(floor) - bound)
            lower_bound = round(lower_bound + excess, 6)
            unknown_count += 1
            censored_or_missing = True
            continue
        if outcome.time_seconds is None:
            unknown_count += 1
            censored_or_missing = True
            continue
        excess = max(0.0, outcome.time_seconds - bound)
        lower_bound = round(lower_bound + excess, 6)

    return AvoidableImpactEstimate(
        eligible_bound_seconds=round(bound, 6),
        lower_bound_seconds=round(lower_bound, 6),
        upper_bound_seconds=None if censored_or_missing else round(lower_bound, 6),
        unknown_count=unknown_count,
        excluded_count=excluded_count,
        eligible_outcome_count=eligible_outcome_count,
    )


__all__ = [
    "AvoidableImpactEstimate",
    "DEFAULT_CLASSIFIER_VERSION",
    "DeclaredRouteAlias",
    "NormalizedAcceptedOutcome",
    "OutcomeEconomicsRecord",
    "OutcomeExclusionReason",
    "analyze_outcome_economics",
    "analyze_route_mismatches",
    "authoritative_cost",
    "compute_outcome_economics",
    "derive_route_mismatch_finding_id",
    "estimate_avoidable_impact",
]
