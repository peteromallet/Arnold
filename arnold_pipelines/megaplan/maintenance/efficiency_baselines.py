"""M5 censor-aware rolling cohort baseline bounds (Plan Step 12 / T12).

This pure module computes conservative cohort statistics over the strict
observation family from Step 2 (T2) without touching any owner store:

* **cohort grouping** — observations are grouped by their normalized
  :class:`~arnold_pipelines.megaplan.maintenance.efficiency_contracts.EfficiencyCohortIdentity`
  (the identity is carried by the normalized fact layer, T11; this module
  accepts an injected cohort resolver so grouping stays deterministic and
  store-free);
* **median / MAD / p95 / p99 lower and upper bounds** — right-censored
  observations contribute the conservative interval ``[lower_bound, +inf)``
  and are never coerced to completion or zero:
  * ``value``/``lower_bound`` use the nearest-rank statistic over every
    observation's known lower value (exact duration for completed, explicit
    lower bound for censored) — a valid lower bound because every true
    duration is at least its lower value;
  * ``upper_bound`` is the nearest-rank statistic over the completed
    durations only, or ``None`` (unbounded) when the censored mass can push
    the quantile beyond every completed value;
* **censoring-dominated suppression** — when the p95 upper bound is
  unbounded, or censored observations alone could fill the p95 tail
  (``censored_count >= ceil(0.05 * n)``), ``censoring_dominated`` is set and
  quantile-driven dwell classification is suppressed (SC13);
* **sample guards** — adaptive claims stay report-only below 30 completed
  samples from 5 plans, and p99/regression priority recommendations stay
  ineligible below 100 completed samples from 10 plans (locked analytical
  policy);
* **conservative dwell predicate with the unfinished lower-bound proof** —
  ``dwell`` requires being above the *conservative* p95 upper bound and
  either at least 2x the conservative median upper bound or above the
  declared SLO.  For an unfinished (right-censored) observation the
  predicate is evaluated on its known lower bound only: a finding is proven
  only when the lower bound already proves the predicate, otherwise the
  result stays ``dwell=False`` with a typed reason (never coerced to
  completion).

All outputs are frozen :class:`BaselineSnapshot` /
:class:`QuantileBounds` contracts from Step 2, so consumers can never lose
the conservative-bounds basis or the ``censoring_dominated`` flag.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, StrictStr

from arnold_pipelines.megaplan.maintenance.efficiency_contracts import (
    BaselineSnapshot,
    DurationObservation,
    EfficiencyCohortIdentity,
    ObservationStatus,
    QuantileBounds,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    UtcTime,
    canonical_dumps,
)

# ---------------------------------------------------------------------------
# Locked sample-guard thresholds (analytical policy)
# ---------------------------------------------------------------------------

#: Minimum completed samples for adaptive (quantile-driven) claims.
MIN_ADAPTIVE_COMPLETED: int = 30
#: Minimum distinct plans for adaptive (quantile-driven) claims.
MIN_ADAPTIVE_PLANS: int = 5
#: Minimum completed samples before p99/regression priority recommendations.
MIN_P99_PRIORITY_COMPLETED: int = 100
#: Minimum distinct plans before p99/regression priority recommendations.
MIN_P99_PRIORITY_PLANS: int = 10

#: The p95 tail is 5% of the cohort by construction.
_P95_TAIL_FRACTION: float = 0.05


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic (owner, locator, digest, cursor) reference order."""
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


def _nearest_rank_index(sample_count: int, quantile: float) -> int:
    """1-based nearest-rank index for *quantile* over *sample_count* items."""
    if sample_count <= 0:
        raise ValueError("nearest-rank index requires a positive sample count")
    if not 0.0 < quantile < 1.0:
        raise ValueError(f"quantile must be in (0, 1), got {quantile!r}")
    return max(1, math.ceil(quantile * sample_count))


def quantile_bounds(
    completed: Sequence[float],
    censored_lower_bounds: Sequence[float],
    quantile: float,
) -> QuantileBounds:
    """Conservative nearest-rank quantile bounds with right censoring.

    Every completed observation contributes its exact duration and every
    right-censored observation contributes the interval
    ``[lower_bound, +inf)``:

    * ``value``/``lower_bound`` are the nearest-rank statistic over all known
      lower values (a valid lower bound: every true duration is at least its
      lower value, so the r-th order statistic is at least the r-th smallest
      lower value);
    * ``upper_bound`` is the nearest-rank statistic over the completed
      durations only, or ``None`` (unbounded) when the censored mass can push
      the quantile past every completed value (``r > completed_count``).

    An empty cohort yields explicit ``None`` bounds — never fabricated
    zeros.
    """
    completed_values = [float(value) for value in completed]
    censored_values = [float(value) for value in censored_lower_bounds]
    sample_count = len(completed_values) + len(censored_values)
    if sample_count == 0:
        return QuantileBounds(value=None, lower_bound=None, upper_bound=None)
    rank = _nearest_rank_index(sample_count, quantile)
    all_lower = sorted(completed_values + censored_values)
    lower = all_lower[rank - 1]
    if rank <= len(completed_values):
        completed_sorted = sorted(completed_values)
        upper = completed_sorted[rank - 1]
    else:
        upper = None
    return QuantileBounds(value=lower, lower_bound=lower, upper_bound=upper)


def mad_bounds(
    completed: Sequence[float],
    censored_lower_bounds: Sequence[float],
    median_value: float | None,
) -> QuantileBounds:
    """Conservative median-absolute-deviation bounds with right censoring.

    Deviations are taken against the cohort's median ``value`` (or the exact
    median lower value when the median is itself unbounded).  A censored
    observation with lower bound ``L`` has deviation at least
    ``max(L - median, 0)`` (its true value is at least ``L``), which is used
    for the lower bound; the worst-case upper bound treats censored
    observations as infinitely far from the median (``None`` when the
    censored mass can push the MAD past every completed deviation).
    """
    if median_value is None:
        return QuantileBounds(value=None, lower_bound=None, upper_bound=None)
    completed_devs = [abs(float(value) - median_value) for value in completed]
    censored_devs = [
        max(float(value) - median_value, 0.0) for value in censored_lower_bounds
    ]
    sample_count = len(completed_devs) + len(censored_devs)
    if sample_count == 0:
        return QuantileBounds(value=None, lower_bound=None, upper_bound=None)
    rank = _nearest_rank_index(sample_count, 0.5)
    all_devs = sorted(completed_devs + censored_devs)
    lower = all_devs[rank - 1]
    if rank <= len(completed_devs):
        completed_sorted = sorted(completed_devs)
        upper = completed_sorted[rank - 1]
    else:
        upper = None
    return QuantileBounds(value=lower, lower_bound=lower, upper_bound=upper)


def is_censoring_dominated(
    *,
    completed_count: int,
    censored_count: int,
    p95_upper_bound: float | None,
) -> bool:
    """Whether censored mass dominates the p95 tail (SC13 suppression).

    Returns ``True`` (and quantile-driven dwell classification must be
    suppressed) when either:

    * the conservative p95 upper bound is unbounded (``None``) — the true
      p95 cannot be bounded from above, so no observation can be proven
      above it; or
    * censored observations alone could fill the entire p95 tail
      (``censored_count >= ceil(0.05 * sample_count)``) — even a finite
      upper bound would rest on tail mass that censoring can move.

    A cohort with no completed observations is always dominated (there is no
    completed quantile basis at all).
    """
    if p95_upper_bound is None:
        return True
    if censored_count <= 0:
        return False
    sample_count = completed_count + censored_count
    if sample_count <= 0 or completed_count <= 0:
        return True
    tail_capacity = max(1, math.ceil(_P95_TAIL_FRACTION * sample_count))
    return censored_count >= tail_capacity


def adaptive_claims_eligible(*, completed_count: int, plan_count: int) -> bool:
    """Sample guard: adaptive (quantile-driven) claims need 30 samples / 5 plans.

    Below this guard, adaptive claims remain report-only (locked policy).
    """
    return (
        completed_count >= MIN_ADAPTIVE_COMPLETED
        and plan_count >= MIN_ADAPTIVE_PLANS
    )


def p99_priority_eligible(*, completed_count: int, plan_count: int) -> bool:
    """Sample guard: p99/regression priority needs 100 samples / 10 plans.

    Below this guard, p99/regression-driven priority recommendations stay
    ineligible (locked policy).
    """
    return (
        completed_count >= MIN_P99_PRIORITY_COMPLETED
        and plan_count >= MIN_P99_PRIORITY_PLANS
    )


def eligible_for_adaptive_claims(snapshot: BaselineSnapshot) -> bool:
    """Convenience sample guard over a computed :class:`BaselineSnapshot`."""
    return adaptive_claims_eligible(
        completed_count=snapshot.completed_count, plan_count=snapshot.plan_count
    )


def eligible_for_p99_priority(snapshot: BaselineSnapshot) -> bool:
    """Convenience p99 guard over a computed :class:`BaselineSnapshot`."""
    return p99_priority_eligible(
        completed_count=snapshot.completed_count, plan_count=snapshot.plan_count
    )


# ---------------------------------------------------------------------------
# Cohort grouping and plan counting
# ---------------------------------------------------------------------------


def default_plan_key(observation: DurationObservation) -> str | None:
    """Primary plan coordinate of *observation* from its evidence refs.

    Plan refs are the owner references with ``owner == \"plan\"`` (the
    canonical owner kind for plan events/receipts).  The primary coordinate
    is the typed ``identity`` when present, otherwise the ``locator``;
    observations without any plan ref contribute no plan coordinate (explicit
    ``None`` — never guessed).  Refs are considered in canonical sorted
    order so the choice is input-order independent.
    """
    for ref in _sort_refs(observation.evidence_refs):
        if ref.owner == "plan":
            return ref.identity or ref.locator
    return None


def distinct_plan_count(
    observations: Sequence[DurationObservation],
    *,
    plan_key: Callable[[DurationObservation], str | None] | None = None,
) -> int:
    """Number of distinct plans among *observations* (never exceeding the count).

    One primary plan coordinate per observation (a duration observation
    belongs to exactly one plan); distinct coordinates are counted, so
    ``plan_count <= sample_count`` always holds for the snapshot contract.
    """
    resolver = plan_key or default_plan_key
    return len({key for key in (resolver(obs) for obs in observations) if key is not None})


def group_observations_by_cohort(
    observations: Sequence[DurationObservation],
    *,
    cohort_of: Callable[[DurationObservation], EfficiencyCohortIdentity],
) -> dict[EfficiencyCohortIdentity, tuple[DurationObservation, ...]]:
    """Group *observations* by their normalized cohort identity.

    The cohort resolver is injected because the strict
    :class:`DurationObservation` contract deliberately carries evidence refs
    rather than the cohort identity — the normalized fact layer (Step 11)
    resolves each observation's cohort.  Groups preserve deterministic order
    (sorted by ``observation_id``) so downstream digests are input-order
    independent.
    """
    groups: dict[EfficiencyCohortIdentity, list[DurationObservation]] = {}
    for observation in observations:
        groups.setdefault(cohort_of(observation), []).append(observation)
    return {
        cohort: tuple(sorted(items, key=lambda obs: obs.observation_id))
        for cohort, items in groups.items()
    }


def compute_baseline_snapshot(
    *,
    cohort: EfficiencyCohortIdentity,
    observations: Sequence[DurationObservation],
    generated_at: UtcTime,
    plan_key: Callable[[DurationObservation], str | None] | None = None,
) -> BaselineSnapshot:
    """Compute the rolling baseline snapshot for one cohort (Step 12 core).

    Counts completed/censored observations exactly, derives ``plan_count``
    from the observations' plan coordinates, computes conservative
    median/MAD/p95/p99 bounds under right censoring, and sets the
    ``censoring_dominated`` suppression flag.  Empty cohorts produce explicit
    ``None`` quantiles — never fabricated zeros.
    """
    completed = [
        observation.duration_seconds
        for observation in observations
        if observation.status is ObservationStatus.COMPLETED
    ]
    censored_lower = [
        observation.lower_bound_seconds
        for observation in observations
        if observation.status is ObservationStatus.RIGHT_CENSORED
    ]
    completed_count = len(completed)
    censored_count = len(censored_lower)
    sample_count = len(observations)
    plan_count = distinct_plan_count(observations, plan_key=plan_key)

    median = quantile_bounds(completed, censored_lower, 0.5)
    mad = mad_bounds(completed, censored_lower, median.value)
    p95 = quantile_bounds(completed, censored_lower, 0.95)
    p99 = quantile_bounds(completed, censored_lower, 0.99)
    censoring_dominated = is_censoring_dominated(
        completed_count=completed_count,
        censored_count=censored_count,
        p95_upper_bound=p95.upper_bound,
    )
    return BaselineSnapshot(
        cohort=cohort,
        sample_count=sample_count,
        plan_count=plan_count,
        completed_count=completed_count,
        censored_count=censored_count,
        median=median,
        mad=mad,
        p95=p95,
        p99=p99,
        censoring_dominated=censoring_dominated,
        generated_at=generated_at,
    )


def build_cohort_baselines(
    cohort_observations: Mapping[
        EfficiencyCohortIdentity, Sequence[DurationObservation]
    ],
    *,
    generated_at: UtcTime,
    plan_key: Callable[[DurationObservation], str | None] | None = None,
) -> tuple[BaselineSnapshot, ...]:
    """Compute one baseline snapshot per cohort, in canonical cohort order.

    Deterministic and input-order independent: cohorts are sorted by their
    canonical serialization so the emitted tuple is reproducible from the
    same observations regardless of map insertion order.
    """
    snapshots = [
        compute_baseline_snapshot(
            cohort=cohort,
            observations=observations,
            generated_at=generated_at,
            plan_key=plan_key,
        )
        for cohort, observations in cohort_observations.items()
    ]
    return tuple(sorted(snapshots, key=lambda item: canonical_dumps(item)))


# ---------------------------------------------------------------------------
# Conservative dwell predicate (including the unfinished lower-bound proof)
# ---------------------------------------------------------------------------


class DwellPredicateResult(BaseModel):
    """Outcome of the conservative dwell predicate (Step 12).

    ``dwell`` is the conservative classification: it is ``True`` only when
    the value is proven above the p95 *upper* bound AND either at least 2x
    the median *upper* bound or above the declared SLO.  For an unfinished
    (right-censored) observation the predicate is evaluated on the known
    lower bound only — ``dwell`` stays ``False`` (with a typed ``reason``)
    until the lower bound already proves the predicate.  A ``reason`` is
    ``None`` exactly when ``dwell`` is ``True``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    above_p95: bool = False
    above_2x_median: bool = False
    above_slo: bool = False
    dwell: bool = False
    reason: StrictStr | None = None


def conservative_dwell_predicate(
    value_seconds: float,
    *,
    censored: bool,
    p95: QuantileBounds,
    median: QuantileBounds,
    slo_seconds: float | None = None,
) -> DwellPredicateResult:
    """Conservative dwell predicate over the cohort bounds (locked rule).

    The locked predicate is ``above p95`` AND (``>= 2x median`` OR ``above
    the declared SLO``).  Every threshold is taken from the conservative
    **upper** bounds so a finding is only emitted when the observation is
    *proven* to exceed the plausible cohort threshold:

    * ``above_p95`` compares against ``p95.upper_bound``; an unbounded p95
      (``None``) can never be proven above, so the flag stays ``False``
      (censoring-dominated suppression);
    * ``above_2x_median`` compares against ``2 * median.upper_bound``
      (``False`` when the median upper bound is unbounded);
    * ``above_slo`` requires a declared ``slo_seconds`` and compares against
      it — an SLO is never inferred.

    For an unfinished observation, pass its known ``lower_bound_seconds`` as
    *value_seconds* (``censored=True``): the finding is proven only when the
    lower bound already proves the predicate, otherwise the result remains
    ``dwell=False`` with a typed reason.
    """
    reason_parts: list[str] = []

    p95_upper = p95.upper_bound
    if p95_upper is None:
        above_p95 = False
        reason_parts.append("p95 upper bound unbounded (censoring-dominated)")
    else:
        above_p95 = value_seconds > p95_upper
        if not above_p95:
            reason_parts.append(
                f"value {value_seconds:.3f}s not above conservative p95 upper "
                f"bound {p95_upper:.3f}s"
            )

    median_upper = median.upper_bound
    if median_upper is None:
        above_2x_median = False
        reason_parts.append("median upper bound unbounded")
    else:
        above_2x_median = value_seconds > 2.0 * median_upper
        if not above_2x_median:
            reason_parts.append(
                f"value {value_seconds:.3f}s not above 2x median upper bound "
                f"{2.0 * median_upper:.3f}s"
            )

    if slo_seconds is None:
        above_slo = False
        reason_parts.append("no declared SLO")
    else:
        above_slo = value_seconds > slo_seconds
        if not above_slo:
            reason_parts.append(
                f"value {value_seconds:.3f}s not above declared SLO "
                f"{slo_seconds:.3f}s"
            )

    dwell = above_p95 and (above_2x_median or above_slo)
    if not dwell and censored:
        reason_parts.append(
            "censored lower bound does not yet prove the dwell predicate"
        )
    return DwellPredicateResult(
        above_p95=above_p95,
        above_2x_median=above_2x_median,
        above_slo=above_slo,
        dwell=dwell,
        reason=None if dwell else "; ".join(reason_parts),
    )


def dwell_predicate_for_observation(
    observation: DurationObservation,
    *,
    p95: QuantileBounds,
    median: QuantileBounds,
    slo_seconds: float | None = None,
) -> DwellPredicateResult:
    """Conservative dwell predicate for one duration observation.

    A completed observation is evaluated on its exact ``duration_seconds``;
    an unfinished (right-censored) observation is evaluated on its known
    ``lower_bound_seconds`` only — the unfinished lower-bound proof.  The
    observation is never coerced to completion or to zero.
    """
    if observation.status is ObservationStatus.COMPLETED:
        return conservative_dwell_predicate(
            observation.duration_seconds,  # type: ignore[arg-type]
            censored=False,
            p95=p95,
            median=median,
            slo_seconds=slo_seconds,
        )
    return conservative_dwell_predicate(
        observation.lower_bound_seconds,  # type: ignore[arg-type]
        censored=True,
        p95=p95,
        median=median,
        slo_seconds=slo_seconds,
    )


__all__ = [
    "MIN_ADAPTIVE_COMPLETED",
    "MIN_ADAPTIVE_PLANS",
    "MIN_P99_PRIORITY_COMPLETED",
    "MIN_P99_PRIORITY_PLANS",
    "DwellPredicateResult",
    "adaptive_claims_eligible",
    "build_cohort_baselines",
    "compute_baseline_snapshot",
    "conservative_dwell_predicate",
    "default_plan_key",
    "distinct_plan_count",
    "dwell_predicate_for_observation",
    "eligible_for_adaptive_claims",
    "eligible_for_p99_priority",
    "group_observations_by_cohort",
    "is_censoring_dominated",
    "mad_bounds",
    "p99_priority_eligible",
    "quantile_bounds",
]
