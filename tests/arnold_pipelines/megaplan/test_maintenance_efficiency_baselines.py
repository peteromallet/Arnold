"""Focused proof tests for M5 censor-aware cohort baseline bounds (Step 12 / T12).

Proves the pure baseline module:

* cohort grouping by normalized cohort identity with deterministic order;
* median / MAD / p95 / p99 lower and upper bounds under right censoring —
  censored observations contribute ``[lower_bound, +inf)`` and are never
  coerced to completion or zero; unbounded upper bounds stay explicit
  ``None``;
* censoring-dominated suppression (SC13) — unbounded p95 upper bounds and
  censored mass that alone could fill the p95 tail suppress quantile-driven
  findings;
* sample guards — 30 completed samples from 5 plans for adaptive claims and
  100 from 10 for p99/regression priority;
* the conservative dwell predicate — above the p95 upper bound AND either 2x
  the median upper bound or the declared SLO, with the unfinished
  lower-bound proof: a censored observation is flagged only when its known
  lower bound already proves the predicate.

All snapshots strict-decode, hash canonically, and are input-order
independent.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from arnold_pipelines.megaplan.maintenance import efficiency_baselines as eb
from arnold_pipelines.megaplan.maintenance import efficiency_contracts as ec
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    ModelId,
    OwnerRef,
    ProfileId,
    StageId,
    UtcTime,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _ts(hour: int = 12, minute: int = 0) -> datetime:
    return datetime(2026, 8, 18, hour, minute, tzinfo=UTC)


def _ref(owner: str, locator: str, identity: str | None = None) -> OwnerRef:
    return OwnerRef(owner=owner, locator=locator, identity=identity, digest="a" * 64)


def _cohort(**overrides: object) -> ec.EfficiencyCohortIdentity:
    base: dict[str, object] = {
        "stage": StageId("stage-1"),
        "profile": ProfileId("profile-1"),
        "model": ModelId("model-1"),
        "robustness": ec.RobustnessKind.THOROUGH,
        "environment": EnvironmentId("production"),
        "classifier_version": "cls-v1",
    }
    base.update(overrides)
    return ec.EfficiencyCohortIdentity(**base)  # type: ignore[arg-type]


def _completed(obs_id: str, duration: float, plan: str | None = "plan-1") -> ec.DurationObservation:
    refs = [] if plan is None else [_ref("plan", f"plan://{plan}", identity=plan)]
    return ec.DurationObservation(
        observation_id=obs_id,
        status=ec.ObservationStatus.COMPLETED,
        duration_seconds=duration,
        evidence_refs=refs,
    )


def _censored(obs_id: str, lower: float, plan: str | None = "plan-1") -> ec.DurationObservation:
    refs = [] if plan is None else [_ref("plan", f"plan://{plan}", identity=plan)]
    return ec.DurationObservation(
        observation_id=obs_id,
        status=ec.ObservationStatus.RIGHT_CENSORED,
        lower_bound_seconds=lower,
        evidence_refs=refs,
    )


def _snapshot(**overrides: object) -> ec.BaselineSnapshot:
    base: dict[str, object] = {
        "cohort": _cohort(),
        "sample_count": 40,
        "plan_count": 8,
        "completed_count": 30,
        "censored_count": 10,
        "median": ec.QuantileBounds(value=1800.0, lower_bound=1500.0, upper_bound=2100.0),
        "mad": ec.QuantileBounds(value=300.0, lower_bound=250.0, upper_bound=400.0),
        "p95": ec.QuantileBounds(value=7200.0, lower_bound=6600.0, upper_bound=9000.0),
        "p99": ec.QuantileBounds(value=10800.0, lower_bound=9600.0, upper_bound=None),
        "censoring_dominated": False,
        "generated_at": UtcTime(_ts()),
    }
    base.update(overrides)
    return ec.BaselineSnapshot(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Quantile bounds with right censoring
# ---------------------------------------------------------------------------


def test_quantile_bounds_all_completed_use_nearest_rank() -> None:
    bounds = eb.quantile_bounds([10.0, 20.0, 30.0, 40.0], [], 0.5)
    assert bounds == ec.QuantileBounds(value=20.0, lower_bound=20.0, upper_bound=20.0)
    p95 = eb.quantile_bounds([10.0, 20.0, 30.0, 40.0], [], 0.95)
    assert p95 == ec.QuantileBounds(value=40.0, lower_bound=40.0, upper_bound=40.0)


def test_quantile_bounds_empty_cohort_is_explicit_null() -> None:
    bounds = eb.quantile_bounds([], [], 0.95)
    assert bounds == ec.QuantileBounds(value=None, lower_bound=None, upper_bound=None)


def test_quantile_bounds_censored_contribute_lower_bound_and_unbounded_upper() -> None:
    # Censored observation [50, +inf) can push p95 past every completed value.
    bounds = eb.quantile_bounds([10.0, 20.0, 30.0, 40.0], [50.0], 0.95)
    assert bounds.value == 50.0
    assert bounds.lower_bound == 50.0
    assert bounds.upper_bound is None


def test_quantile_bounds_censored_never_raise_finite_upper_beyond_completed() -> None:
    # Small censored lower bound still leaves p95 unbounded: the censored
    # observation could be arbitrarily large.
    bounds = eb.quantile_bounds([10.0, 20.0, 30.0, 40.0], [15.0], 0.95)
    assert bounds.value == 40.0
    assert bounds.lower_bound == 40.0
    assert bounds.upper_bound is None


def test_quantile_bounds_median_with_censoring_keeps_finite_upper() -> None:
    bounds = eb.quantile_bounds([10.0, 20.0, 30.0, 40.0], [50.0], 0.5)
    assert bounds == ec.QuantileBounds(value=30.0, lower_bound=30.0, upper_bound=30.0)


def test_quantile_bounds_rejects_invalid_quantile() -> None:
    with pytest.raises(ValueError):
        eb.quantile_bounds([1.0], [], 1.0)


# ---------------------------------------------------------------------------
# MAD bounds with right censoring
# ---------------------------------------------------------------------------


def test_mad_bounds_completed_only() -> None:
    bounds = eb.mad_bounds([10.0, 20.0, 30.0, 40.0], [], 20.0)
    assert bounds == ec.QuantileBounds(value=10.0, lower_bound=10.0, upper_bound=10.0)


def test_mad_bounds_censored_deviation_is_clipped_lower_bound() -> None:
    # Censored observation at [50, +inf) deviates at least 30 from median 20.
    bounds = eb.mad_bounds([10.0, 20.0, 30.0, 40.0], [50.0], 20.0)
    assert bounds.value == 10.0
    assert bounds.lower_bound == 10.0
    assert bounds.upper_bound == 10.0


def test_mad_bounds_unbounded_upper_when_censored_mass_pushes_past_completed() -> None:
    bounds = eb.mad_bounds([10.0], [20.0, 30.0], 10.0)
    assert bounds.value == 10.0
    assert bounds.upper_bound is None


def test_mad_bounds_without_median_is_explicit_null() -> None:
    assert eb.mad_bounds([], [], None) == ec.QuantileBounds(
        value=None, lower_bound=None, upper_bound=None
    )


# ---------------------------------------------------------------------------
# Censoring-dominated suppression (SC13)
# ---------------------------------------------------------------------------


def test_censoring_dominated_when_p95_upper_unbounded() -> None:
    assert eb.is_censoring_dominated(
        completed_count=40, censored_count=1, p95_upper_bound=None
    )


def test_censoring_dominated_when_censored_mass_fills_p95_tail() -> None:
    # 3 censored of 40 is >= ceil(0.05 * 40) = 2: censored alone could fill
    # the p95 tail even though the upper bound happens to be finite.
    assert eb.is_censoring_dominated(
        completed_count=37, censored_count=3, p95_upper_bound=9000.0
    )


def test_not_censoring_dominated_without_censoring() -> None:
    assert not eb.is_censoring_dominated(
        completed_count=40, censored_count=0, p95_upper_bound=9000.0
    )


def test_not_censoring_dominated_with_small_censored_mass() -> None:
    assert not eb.is_censoring_dominated(
        completed_count=39, censored_count=1, p95_upper_bound=9000.0
    )


def test_censoring_dominated_without_completed_basis() -> None:
    assert eb.is_censoring_dominated(
        completed_count=0, censored_count=5, p95_upper_bound=None
    )


# ---------------------------------------------------------------------------
# Sample guards
# ---------------------------------------------------------------------------


def test_adaptive_claims_require_30_completed_from_5_plans() -> None:
    assert not eb.adaptive_claims_eligible(completed_count=29, plan_count=5)
    assert not eb.adaptive_claims_eligible(completed_count=30, plan_count=4)
    assert eb.adaptive_claims_eligible(completed_count=30, plan_count=5)
    assert eb.adaptive_claims_eligible(completed_count=31, plan_count=5)


def test_p99_priority_requires_100_completed_from_10_plans() -> None:
    assert not eb.p99_priority_eligible(completed_count=99, plan_count=10)
    assert not eb.p99_priority_eligible(completed_count=100, plan_count=9)
    assert eb.p99_priority_eligible(completed_count=100, plan_count=10)
    assert eb.p99_priority_eligible(completed_count=101, plan_count=10)


def test_snapshot_convenience_guards() -> None:
    eligible = _snapshot(completed_count=30, plan_count=5)
    assert eb.eligible_for_adaptive_claims(eligible)
    assert not eb.eligible_for_p99_priority(eligible)
    cold = _snapshot(completed_count=10, plan_count=2)
    assert not eb.eligible_for_adaptive_claims(cold)


# ---------------------------------------------------------------------------
# Cohort grouping, plan counting, and snapshot computation
# ---------------------------------------------------------------------------


def test_default_plan_key_uses_plan_ref_identity() -> None:
    obs = _completed("obs-1", 3600.0, plan="plan-7")
    assert eb.default_plan_key(obs) == "plan-7"
    assert eb.default_plan_key(_completed("obs-2", 3600.0, plan=None)) is None


def test_distinct_plan_count_never_exceeds_sample_count() -> None:
    observations = [
        _completed("obs-1", 3600.0, plan="plan-1"),
        _completed("obs-2", 5400.0, plan="plan-2"),
        _censored("obs-3", 7200.0, plan="plan-1"),
    ]
    assert eb.distinct_plan_count(observations) == 2
    assert eb.distinct_plan_count([_completed("obs-4", 100.0, plan=None)]) == 0


def test_group_observations_by_cohort_is_deterministic() -> None:
    cohort_a = _cohort(stage=StageId("stage-a"))
    cohort_b = _cohort(stage=StageId("stage-b"))
    observations = [
        _completed("obs-b2", 200.0),
        _completed("obs-a2", 300.0),
        _completed("obs-a1", 100.0),
    ]
    grouped = eb.group_observations_by_cohort(
        observations,
        cohort_of=lambda obs: cohort_a if obs.observation_id.startswith("obs-a") else cohort_b,
    )
    assert set(grouped) == {cohort_a, cohort_b}
    assert [obs.observation_id for obs in grouped[cohort_a]] == ["obs-a1", "obs-a2"]


def test_compute_baseline_snapshot_counts_and_bounds() -> None:
    observations = [
        _completed("obs-1", 3600.0, plan="plan-1"),
        _completed("obs-2", 5400.0, plan="plan-1"),
        _completed("obs-4", 1800.0, plan="plan-2"),
        _censored("obs-3", 7200.0, plan="plan-2"),
    ]
    snapshot = eb.compute_baseline_snapshot(
        cohort=_cohort(), observations=observations, generated_at=UtcTime(_ts())
    )
    assert snapshot.sample_count == 4
    assert snapshot.completed_count == 3
    assert snapshot.censored_count == 1
    assert snapshot.plan_count == 2
    # median over [1800, 3600, 5400, 7200] -> nearest rank 2 -> 3600.
    assert snapshot.median.value == 3600.0
    assert snapshot.median.upper_bound == 3600.0
    # p95 rank 4 -> 7200, but the censored observation can push it unbounded.
    assert snapshot.p95.value == 7200.0
    assert snapshot.p95.upper_bound is None
    assert snapshot.censoring_dominated is True
    assert snapshot.p99.upper_bound is None


def test_compute_baseline_snapshot_empty_cohort() -> None:
    snapshot = eb.compute_baseline_snapshot(
        cohort=_cohort(), observations=[], generated_at=UtcTime(_ts())
    )
    assert snapshot.sample_count == 0
    assert snapshot.completed_count == 0
    assert snapshot.censored_count == 0
    assert snapshot.plan_count == 0
    assert snapshot.median.value is None
    assert snapshot.p95.value is None


def test_build_cohort_baselines_is_input_order_independent() -> None:
    cohort_a = _cohort(stage=StageId("stage-a"))
    cohort_b = _cohort(stage=StageId("stage-b"))
    observations = {
        cohort_a: [_completed("obs-1", 3600.0)],
        cohort_b: [_completed("obs-2", 5400.0)],
    }
    forward = eb.build_cohort_baselines(observations, generated_at=UtcTime(_ts()))
    reversed_map = {cohort_b: observations[cohort_b], cohort_a: observations[cohort_a]}
    backward = eb.build_cohort_baselines(reversed_map, generated_at=UtcTime(_ts()))
    assert [canonical_dumps(item) for item in forward] == [
        canonical_dumps(item) for item in backward
    ]
    assert [item.cohort for item in forward] == sorted(
        [cohort_a, cohort_b], key=lambda item: canonical_dumps(item)
    )


def test_baseline_snapshot_roundtrips_and_hashes_canonically() -> None:
    observations = [
        _completed("obs-1", 3600.0, plan="plan-1"),
        _censored("obs-2", 7200.0, plan="plan-2"),
    ]
    snapshot = eb.compute_baseline_snapshot(
        cohort=_cohort(), observations=observations, generated_at=UtcTime(_ts())
    )
    decoded = strict_loads(ec.BaselineSnapshot, canonical_dumps(snapshot))
    assert decoded == snapshot
    assert canonical_digest(decoded) == canonical_digest(snapshot)


# ---------------------------------------------------------------------------
# Conservative dwell predicate (including unfinished lower-bound proof)
# ---------------------------------------------------------------------------


def _cohort_bounds() -> tuple[ec.QuantileBounds, ec.QuantileBounds]:
    p95 = ec.QuantileBounds(value=7200.0, lower_bound=6600.0, upper_bound=9000.0)
    median = ec.QuantileBounds(value=1800.0, lower_bound=1500.0, upper_bound=2100.0)
    return p95, median


def test_dwell_predicate_completed_above_p95_and_2x_median() -> None:
    p95, median = _cohort_bounds()
    result = eb.conservative_dwell_predicate(
        20000.0, censored=False, p95=p95, median=median, slo_seconds=3600.0
    )
    assert result.above_p95 is True
    assert result.above_2x_median is True
    assert result.above_slo is True
    assert result.dwell is True
    assert result.reason is None


def test_dwell_predicate_requires_above_p95_upper_bound() -> None:
    p95, median = _cohort_bounds()
    # 8500 is above the p95 VALUE but below the conservative upper bound.
    result = eb.conservative_dwell_predicate(
        8500.0, censored=False, p95=p95, median=median, slo_seconds=3600.0
    )
    assert result.above_p95 is False
    assert result.dwell is False
    assert result.reason is not None
    assert "p95 upper bound" in result.reason


def test_dwell_predicate_unbounded_p95_cannot_prove_above() -> None:
    p95 = ec.QuantileBounds(value=7200.0, lower_bound=6600.0, upper_bound=None)
    median = ec.QuantileBounds(value=1800.0, lower_bound=1500.0, upper_bound=2100.0)
    result = eb.conservative_dwell_predicate(
        50000.0, censored=False, p95=p95, median=median, slo_seconds=3600.0
    )
    assert result.above_p95 is False
    assert result.dwell is False
    assert "unbounded" in result.reason


def test_dwell_predicate_above_p95_via_declared_slo() -> None:
    p95, median = _cohort_bounds()
    # Above p95 upper (9000) and above the SLO (3600), but not 2x median upper.
    result = eb.conservative_dwell_predicate(
        12000.0, censored=False, p95=p95, median=median, slo_seconds=3600.0
    )
    assert result.above_p95 is True
    assert result.above_2x_median is True  # 12000 > 2*2100
    assert result.dwell is True
    # Use a median upper bound large enough that 2x is not exceeded.
    median_wide = ec.QuantileBounds(value=1800.0, lower_bound=1500.0, upper_bound=7000.0)
    result2 = eb.conservative_dwell_predicate(
        12000.0, censored=False, p95=p95, median=median_wide, slo_seconds=3600.0
    )
    assert result2.above_2x_median is False
    assert result2.above_slo is True
    assert result2.dwell is True


def test_dwell_predicate_without_slo_cannot_use_slo_leg() -> None:
    p95, median = _cohort_bounds()
    result = eb.conservative_dwell_predicate(
        12000.0, censored=False, p95=p95, median=median, slo_seconds=None
    )
    assert result.above_slo is False
    assert result.above_2x_median is True
    assert result.dwell is True
    # Below 2x median and no SLO declared -> not dwell.
    median_wide = ec.QuantileBounds(value=1800.0, lower_bound=1500.0, upper_bound=7000.0)
    result2 = eb.conservative_dwell_predicate(
        12000.0, censored=False, p95=p95, median=median_wide, slo_seconds=None
    )
    assert result2.dwell is False
    assert "no declared SLO" in result2.reason


def test_dwell_predicate_unfinished_lower_bound_proof() -> None:
    p95, median = _cohort_bounds()
    # Censored lower bound already proves the predicate -> flagged.
    proven = eb.conservative_dwell_predicate(
        30000.0, censored=True, p95=p95, median=median, slo_seconds=3600.0
    )
    assert proven.dwell is True
    # Censored lower bound does NOT yet prove it -> remains unknown.
    unproven = eb.conservative_dwell_predicate(
        5000.0, censored=True, p95=p95, median=median, slo_seconds=3600.0
    )
    assert unproven.dwell is False
    assert "censored lower bound" in unproven.reason


def test_dwell_predicate_for_observation_uses_exact_or_lower_bound() -> None:
    p95, median = _cohort_bounds()
    completed = _completed("obs-1", 30000.0)
    censored = _censored("obs-2", 30000.0)
    assert eb.dwell_predicate_for_observation(
        completed, p95=p95, median=median, slo_seconds=3600.0
    ).dwell is True
    assert eb.dwell_predicate_for_observation(
        censored, p95=p95, median=median, slo_seconds=3600.0
    ).dwell is True
    # A censored observation whose lower bound is modest stays unknown.
    censored_modest = _censored("obs-3", 3000.0)
    assert eb.dwell_predicate_for_observation(
        censored_modest, p95=p95, median=median, slo_seconds=3600.0
    ).dwell is False
