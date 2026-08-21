"""Focused proof tests for the M5 observation/statistics contracts (Step 2 / T2).

Proves the frozen, strict, versioned family:

* normalized cohort identity (stage/profile/model/robustness/environment/
  classifier version) with explicit nulls for absent dimensions;
* completed and right-censored duration observations with explicit lower
  bounds — censored observations contribute ``[lower_bound, +inf)`` and are
  never coerced to completion or zero;
* baseline snapshots (median/MAD/p95/p99) with conservative lower/upper
  quantile bounds and the ``censoring_dominated`` flag;
* metric denominators and coverage — missing numerators/denominators stay
  explicit ``None`` and coverage is never ``0`` when unknown;
* shadow-evaluation measures with typed unavailable states and rate bounds.

Every contract is versioned (``daily_efficiency.v1``), forbids unknown
fields, strict-decodes through the shared codec, and hashes canonically with
sorted references so the digest is independent of input order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.maintenance import efficiency_contracts as ec
from arnold_pipelines.megaplan.maintenance import efficiency_routing as er
from arnold_pipelines.megaplan.maintenance import efficiency_sources as es
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    EventWindow,
    MaintenanceCodecError,
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


def _ref(owner: str, locator: str, digest: str | None = "a" * 64) -> OwnerRef:
    return OwnerRef(owner=owner, locator=locator, digest=digest)


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


def _completed(**overrides: object) -> ec.DurationObservation:
    base: dict[str, object] = {
        "observation_id": "obs-completed-1",
        "status": ec.ObservationStatus.COMPLETED,
        "duration_seconds": 3600.0,
    }
    base.update(overrides)
    return ec.DurationObservation(**base)  # type: ignore[arg-type]


def _censored(**overrides: object) -> ec.DurationObservation:
    base: dict[str, object] = {
        "observation_id": "obs-censored-1",
        "status": ec.ObservationStatus.RIGHT_CENSORED,
        "lower_bound_seconds": 5400.0,
    }
    base.update(overrides)
    return ec.DurationObservation(**base)  # type: ignore[arg-type]


def _bounds(value: float, lower: float | None = None, upper: float | None = None) -> ec.QuantileBounds:
    return ec.QuantileBounds(value=value, lower_bound=lower, upper_bound=upper)


def _snapshot(**overrides: object) -> ec.BaselineSnapshot:
    base: dict[str, object] = {
        "cohort": _cohort(),
        "sample_count": 40,
        "plan_count": 8,
        "completed_count": 30,
        "censored_count": 10,
        "median": _bounds(1800.0, 1500.0, 2100.0),
        "mad": _bounds(300.0, 250.0, 400.0),
        "p95": _bounds(7200.0, 6600.0, 9000.0),
        "p99": _bounds(10800.0, 9600.0, None),
        "censoring_dominated": False,
        "generated_at": UtcTime(_ts()),
    }
    base.update(overrides)
    return ec.BaselineSnapshot(**base)  # type: ignore[arg-type]


def _denominator(**overrides: object) -> ec.DenominatorCoverage:
    base: dict[str, object] = {
        "metric": "accepted_outcomes",
        "numerator": 3,
        "denominator": 5,
        "unknown_count": 1,
        "censored_count": 1,
    }
    base.update(overrides)
    return ec.DenominatorCoverage(**base)  # type: ignore[arg-type]


def _shadow(**overrides: object) -> ec.ShadowMeasure:
    base: dict[str, object] = {
        "measure": ec.ShadowMeasureKind.PRECISION,
        "value": 0.8,
        "numerator": 4,
        "denominator": 5,
    }
    base.update(overrides)
    return ec.ShadowMeasure(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Versioned family identity
# ---------------------------------------------------------------------------


def test_every_family_contract_carries_the_versioned_identity() -> None:
    instances = (
        _cohort(),
        _completed(),
        _censored(),
        _snapshot(),
        _denominator(),
        _shadow(),
    )
    for instance in instances:
        assert instance.contract_id == "daily_efficiency.v1"
        assert instance.contract_id == ec.DAILY_EFFICIENCY_CONTRACT_ID


# ---------------------------------------------------------------------------
# Cohort identity: strict decoding and explicit nulls
# ---------------------------------------------------------------------------


def test_cohort_identity_round_trip_and_stable_digest() -> None:
    cohort = _cohort()
    decoded = strict_loads(ec.EfficiencyCohortIdentity, canonical_dumps(cohort))
    assert decoded == cohort
    assert canonical_digest(decoded) == canonical_digest(cohort)


def test_cohort_identity_preserves_explicit_nulls() -> None:
    cohort = _cohort(stage=None, model=None, robustness=None, environment=None)
    dumped = canonical_dumps(cohort)
    assert '"stage":null' in dumped
    assert '"environment":null' in dumped
    decoded = strict_loads(ec.EfficiencyCohortIdentity, dumped)
    assert decoded.stage is None
    assert decoded.environment is None


def test_cohort_identity_rejects_unknown_fields() -> None:
    data = _cohort().model_dump(mode="json", exclude_none=False)
    data["invented_dimension"] = "x"
    with pytest.raises(MaintenanceCodecError):
        strict_loads(ec.EfficiencyCohortIdentity, data)


def test_cohort_identity_rejects_bad_environment_and_empty_classifier() -> None:
    with pytest.raises(ValueError):
        _cohort(environment=EnvironmentId("prod"))  # alias rejected
    with pytest.raises(ValueError):
        _cohort(classifier_version="")


# ---------------------------------------------------------------------------
# Completed and right-censored observations
# ---------------------------------------------------------------------------


def test_completed_observation_round_trip() -> None:
    obs = _completed(duration_seconds=3600.0)
    assert obs.lower_bound == 3600.0
    decoded = strict_loads(ec.DurationObservation, canonical_dumps(obs))
    assert decoded == obs
    assert canonical_digest(decoded) == canonical_digest(obs)


def test_right_censored_observation_carries_explicit_lower_bound() -> None:
    obs = _censored(lower_bound_seconds=5400.0)
    assert obs.duration_seconds is None
    assert obs.lower_bound == 5400.0
    dumped = canonical_dumps(obs)
    assert '"duration_seconds":null' in dumped
    assert '"lower_bound_seconds":5400.0' in dumped
    decoded = strict_loads(ec.DurationObservation, dumped)
    assert decoded.status is ec.ObservationStatus.RIGHT_CENSORED
    assert decoded.lower_bound == 5400.0


def test_completed_observation_rejects_lower_bound() -> None:
    with pytest.raises(ValueError):
        _completed(lower_bound_seconds=100.0)


def test_completed_observation_requires_exact_duration() -> None:
    with pytest.raises(ValueError):
        _completed(duration_seconds=None)


def test_censored_observation_requires_lower_bound() -> None:
    with pytest.raises(ValueError):
        _censored(lower_bound_seconds=None)


def test_censored_observation_rejects_completion_duration() -> None:
    with pytest.raises(ValueError):
        _censored(duration_seconds=5400.0)


def test_negative_durations_are_rejected() -> None:
    with pytest.raises(ValueError):
        _completed(duration_seconds=-1.0)
    with pytest.raises(ValueError):
        _censored(lower_bound_seconds=-1.0)


def test_observation_evidence_refs_are_sorted_and_digest_stable() -> None:
    low = _ref("status_projection", "status://s", "c" * 64)
    high = _ref("run_authority", "grant://g", "b" * 64)
    forward = _completed(evidence_refs=[low, high])
    reversed_obs = _completed(evidence_refs=[high, low])
    assert forward.evidence_refs == (high, low)
    assert forward.evidence_refs == reversed_obs.evidence_refs
    assert canonical_digest(forward) == canonical_digest(reversed_obs)


def test_observation_nullable_evidence_and_refs_round_trip() -> None:
    obs = _completed(evidence_refs=[])
    dumped = canonical_dumps(obs)
    decoded = strict_loads(ec.DurationObservation, dumped)
    assert decoded.evidence_refs == ()
    ref = _ref("wbc", "wbc/1", None)
    obs_ref = _completed(evidence_refs=[ref])
    assert '"digest":null' in canonical_dumps(obs_ref)


def test_observation_rejects_unknown_fields() -> None:
    data = _completed().model_dump(mode="json", exclude_none=False)
    data["invented"] = True
    with pytest.raises(MaintenanceCodecError):
        strict_loads(ec.DurationObservation, data)


# ---------------------------------------------------------------------------
# Baseline snapshots with conservative quantile bounds
# ---------------------------------------------------------------------------


def test_baseline_snapshot_round_trip_and_canonical_hash() -> None:
    snapshot = _snapshot()
    decoded = strict_loads(ec.BaselineSnapshot, canonical_dumps(snapshot))
    assert decoded == snapshot
    assert canonical_digest(decoded) == canonical_digest(snapshot)
    # The censoring flag is part of the materialized contract.
    dominated = _snapshot(censoring_dominated=True)
    assert dominated.censoring_dominated is True
    assert strict_loads(
        ec.BaselineSnapshot, canonical_dumps(dominated)
    ).censoring_dominated is True


def test_baseline_counts_must_be_consistent() -> None:
    with pytest.raises(ValueError):
        _snapshot(completed_count=30, censored_count=15, sample_count=40)
    with pytest.raises(ValueError):
        _snapshot(plan_count=41, sample_count=40)


def test_quantile_bounds_are_conservative_and_validated() -> None:
    # Value inside [lower, upper] is accepted.
    _bounds(5.0, 4.0, 6.0)
    # Censored upper tails stay explicitly unbounded (upper None).
    _bounds(10.0, 8.0, None)
    with pytest.raises(ValueError):
        _bounds(5.0, 4.0, 4.5)  # value above upper
    with pytest.raises(ValueError):
        _bounds(5.0, 6.0, 7.0)  # value below lower
    with pytest.raises(ValueError):
        _bounds(5.0, 7.0, 6.0)  # lower above upper
    with pytest.raises(ValueError):
        ec.QuantileBounds(value=-1.0)  # negative value


def test_quantile_bounds_strict_decode_round_trip() -> None:
    bounds = _bounds(5.0, 4.0, None)
    decoded = strict_loads(ec.QuantileBounds, canonical_dumps(bounds))
    assert decoded == bounds
    assert decoded.upper_bound is None


# ---------------------------------------------------------------------------
# Denominator / coverage facts
# ---------------------------------------------------------------------------


def test_denominator_coverage_derived_values() -> None:
    facts = _denominator()
    assert facts.coverage == 3 / 5
    assert facts.missing_denominator is False
    assert strict_loads(ec.DenominatorCoverage, canonical_dumps(facts)) == facts


def test_missing_denominator_stays_explicit_never_green() -> None:
    facts = _denominator(denominator=None)
    assert facts.missing_denominator is True
    assert facts.coverage is None
    assert '"denominator":null' in canonical_dumps(facts)


def test_missing_numerator_stays_explicit_never_green() -> None:
    facts = _denominator(numerator=None)
    assert facts.coverage is None


def test_zero_denominator_coverage_is_none_not_zero() -> None:
    facts = _denominator(numerator=0, denominator=0)
    assert facts.coverage is None


def test_denominator_rejects_numerator_exceeding_denominator() -> None:
    with pytest.raises(ValueError):
        _denominator(numerator=6, denominator=5)


def test_denominator_retains_unknown_and_censored_counts() -> None:
    facts = _denominator(unknown_count=2, censored_count=3)
    assert facts.unknown_count == 2
    assert facts.censored_count == 3
    assert facts.coverage == 3 / 5


def test_denominator_rejects_unknown_fields() -> None:
    data = _denominator().model_dump(mode="json", exclude_none=False)
    data["invented"] = True
    with pytest.raises(MaintenanceCodecError):
        strict_loads(ec.DenominatorCoverage, data)


# ---------------------------------------------------------------------------
# Shadow-evaluation measures with explicit unavailable states
# ---------------------------------------------------------------------------


def test_shadow_measure_round_trip_and_stable_digest() -> None:
    measure = _shadow()
    decoded = strict_loads(ec.ShadowMeasure, canonical_dumps(measure))
    assert decoded == measure
    assert canonical_digest(decoded) == canonical_digest(measure)


def test_shadow_measure_rate_bounds_are_validated() -> None:
    _shadow(value=0.0)
    _shadow(value=1.0)
    with pytest.raises(ValueError):
        _shadow(value=1.5)  # precision is a rate
    with pytest.raises(ValueError):
        _shadow(value=-0.1)
    with pytest.raises(ValueError):
        _shadow(measure=ec.ShadowMeasureKind.ANALYST_OVERHEAD, value=-1.0)
    # Non-negative magnitudes accept values above 1.
    _shadow(measure=ec.ShadowMeasureKind.ESTIMATED_SAVINGS, value=123.0)


def test_shadow_measure_explicit_unavailable_state() -> None:
    unavailable = _shadow(
        value=None,
        numerator=None,
        denominator=None,
        unavailable_reason=ec.UnavailableReason.MISSING_DENOMINATOR,
    )
    dumped = canonical_dumps(unavailable)
    assert '"value":null' in dumped
    assert '"denominator":null' in dumped
    decoded = strict_loads(ec.ShadowMeasure, dumped)
    assert decoded.value is None
    assert decoded.unavailable_reason is ec.UnavailableReason.MISSING_DENOMINATOR
    assert canonical_digest(decoded) == canonical_digest(unavailable)


def test_shadow_measure_value_conflicts_with_unavailable_reason() -> None:
    with pytest.raises(ValueError):
        _shadow(value=0.8, unavailable_reason=ec.UnavailableReason.UNKNOWN)


def test_shadow_measure_rejects_unknown_fields() -> None:
    data = _shadow().model_dump(mode="json", exclude_none=False)
    data["invented"] = True
    with pytest.raises(MaintenanceCodecError):
        strict_loads(ec.ShadowMeasure, data)


# ---------------------------------------------------------------------------
# Cross-family canonical hashing and strict decoding
# ---------------------------------------------------------------------------


def test_family_digests_change_when_content_changes() -> None:
    assert canonical_digest(_completed(duration_seconds=3600.0)) != canonical_digest(
        _completed(duration_seconds=7200.0)
    )
    assert canonical_digest(_snapshot(median=_bounds(1900.0))) != canonical_digest(
        _snapshot()
    )
    assert canonical_digest(_denominator(numerator=2)) != canonical_digest(
        _denominator()
    )
    assert canonical_digest(_shadow(value=0.5)) != canonical_digest(_shadow())


def test_family_contracts_reject_unknown_fields_at_strict_decode() -> None:
    samples: tuple[tuple[type, object], ...] = (
        (ec.EfficiencyCohortIdentity, _cohort()),
        (ec.DurationObservation, _completed()),
        (ec.QuantileBounds, _bounds(1.0)),
        (ec.BaselineSnapshot, _snapshot()),
        (ec.DenominatorCoverage, _denominator()),
        (ec.ShadowMeasure, _shadow()),
    )
    for model_cls, sample in samples:
        data = sample.model_dump(mode="json", exclude_none=False)  # type: ignore[attr-defined]
        data["invented_authority"] = True
        with pytest.raises(MaintenanceCodecError):
            strict_loads(model_cls, data)  # type: ignore[arg-type]


def test_routing_emits_inert_deterministic_no_match_proposal() -> None:
    candidate = ec.RootCauseCandidate(
        candidate_id="candidate-1",
        root_cause_fingerprint="fingerprint-1",
        affected_contract="contract-1",
        classifier_version="classifier-1",
        coverage=_denominator(
            numerator=4,
            denominator=5,
            unknown_count=0,
            censored_count=1,
        ),
        confidence=_bounds(0.9, 0.9, 0.9),
        recurrence_count_7d=2,
        recurrence_count_30d=2,
        evidence_refs=(_ref("wbc", "wbc://occurrence-1"),),
    )
    ticket_read = es.OpenTicketLookupAdapter(
        lambda: SimpleNamespace(
            stable=True,
            ticket_id=None,
            row_count=0,
            content_digest=None,
            file_stats_before=(),
            file_stats_after=(),
        ),
        environment="production",
    ).read()
    prior_keys: list[str] = []
    result = er.route_recommendations(
        candidates=[candidate],
        ticket_read=ticket_read,
        policy=er.DEFAULT_ROUTING_POLICY,
        environment=EnvironmentId("production"),
        window=EventWindow(start=UtcTime(_ts(12)), end=UtcTime(_ts(13))),
        generated_at=UtcTime(_ts(12)),
        cluster_refs={"candidate-1": _ref("maintenance", "cluster://candidate-1")},
        prior_key_lookup=lambda key: prior_keys.append(key) or False,
    )

    assert len(result.decisions) == 1
    decision = result.decisions[0]
    assert decision.recommendation_kind is er.RecommendationKind.NEW_TICKET_PROPOSAL
    assert decision.state is er.RecommendationState.NEW
    assert decision.open_ticket_identity == es.NO_MATCH_TICKET_IDENTITY
    assert decision.acceptance_state == "pending_human_acceptance"
    assert decision.proposal is not None
    assert decision.proposal.auto_materialization is False
    # The proposal preserves explicit no-match as None; the routing decision
    # carries the stable no-match identity used for matching/deduplication.
    assert decision.proposal.open_ticket_identity is None
    assert decision.proposal.evidence_refs == candidate.evidence_refs
    assert decision.proposal.cluster_ref.locator == "cluster://candidate-1"
    assert decision.proposal.proposal_key == decision.proposal_key
    assert len(prior_keys) == 1

    decoded = strict_loads(ec.DailyEfficiencyProposal, canonical_dumps(decision.proposal))
    assert decoded == decision.proposal
    with pytest.raises(Exception):
        decision.proposal.auto_materialization = True  # type: ignore[misc]
