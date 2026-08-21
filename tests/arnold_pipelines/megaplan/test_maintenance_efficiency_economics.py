"""Focused proof tests for M5 route-mismatch and accepted-outcome economics
(Step 17 / T17).

Proves the pure economics module:

* route comparison per accepted outcome — expected vs resolved vs
  provider-actual — where a missing leg stays typed unknown, NEVER a
  mismatch, and provider aliases are equivalent ONLY where owner receipts
  declare them (SC18);
* time/tokens/authoritative cost and quality delta per accepted outcome,
  never raw totals: every economics claim is denominator-gated, competing
  cost sources are never merged, authoritative cost names a typed source
  with its exact coordinate, and missing pricing stays explicit unknown;
* conservative avoidable-impact estimates as bounded excess over an
  eligible cohort/SLO reference with explicit lower/upper/unknown bounds
  for censored or missing measures, excluding legitimate expensive
  high-depth outcomes;
* determinism — input order never changes finding IDs, references, or
  output ordering.

All findings are typed Step 3 contracts that strict-decode and hash
canonically.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from arnold_pipelines.megaplan.maintenance import efficiency_economics as ee
from arnold_pipelines.megaplan.maintenance import efficiency_contracts as ec
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _ref(owner: str, locator: str, identity: str | None = None) -> OwnerRef:
    return OwnerRef(owner=owner, locator=locator, identity=identity, digest="a" * 64)


def _outcome(
    outcome_id: str,
    *,
    expected_route: str | None = None,
    resolved_route: str | None = None,
    provider_actual_route: str | None = None,
    time_seconds: float | None = None,
    tokens: float | None = None,
    provider_reported_cost: float | None = None,
    work_ledger_cost: float | None = None,
    quality: float | None = None,
    expected_quality: float | None = None,
    robustness: ec.RobustnessKind | None = None,
    exploration: bool = False,
    censored: bool = False,
    lower_bound_seconds: float | None = None,
    excluded_reason: ee.OutcomeExclusionReason | None = None,
    deep_work: bool = False,
    configured_backoff: bool = False,
    human_gate: bool = False,
    productive: bool = False,
    coverage: ec.DenominatorCoverage | None = None,
    accepted_outcome_identity: str | None = None,
) -> ee.NormalizedAcceptedOutcome:
    accepted = accepted_outcome_identity or f"decision://{outcome_id}"
    refs = [_ref("wbc", f"wbc://{outcome_id}")]
    accepted_refs = [_ref("run_authority", accepted)]
    ledger_ref = (
        _ref("wbc", f"wbc://{outcome_id}/ledger") if work_ledger_cost is not None else None
    )
    provider_ref = (
        _ref("native_manifest", f"native_manifest://{outcome_id}/cost")
        if provider_reported_cost is not None
        else None
    )
    censoring_refs = (
        [_ref("wbc", f"wbc://{outcome_id}/censor")] if censored else []
    )
    return ee.NormalizedAcceptedOutcome(
        outcome_id=outcome_id,
        accepted_outcome_identity=accepted,
        stage="finalize",
        expected_route=expected_route,
        resolved_route=resolved_route,
        provider_actual_route=provider_actual_route,
        time_seconds=time_seconds,
        tokens=tokens,
        provider_reported_cost=provider_reported_cost,
        provider_reported_cost_ref=provider_ref,
        work_ledger_cost=work_ledger_cost,
        work_ledger_cost_ref=ledger_ref,
        quality=quality,
        expected_quality=expected_quality,
        robustness=robustness,
        exploration=exploration,
        censored=censored,
        lower_bound_seconds=lower_bound_seconds,
        excluded_reason=excluded_reason,
        deep_work=deep_work,
        configured_backoff=configured_backoff,
        human_gate=human_gate,
        productive=productive,
        coverage=coverage,
        refs=refs,
        accepted_resolution_refs=accepted_refs,
        censoring_refs=censoring_refs,
    )


# ---------------------------------------------------------------------------
# Contract discipline
# ---------------------------------------------------------------------------


def test_normalized_outcome_contract_discipline() -> None:
    # Outcomes require exact source refs.
    with pytest.raises(ValueError):
        ee.NormalizedAcceptedOutcome(
            outcome_id="o-1",
            accepted_outcome_identity="decision://o-1",
            stage="finalize",
            refs=[],
            accepted_resolution_refs=[_ref("run_authority", "decision://o-1")],
        )
    # Outcomes require exact accepted-resolution refs.
    with pytest.raises(ValueError):
        ee.NormalizedAcceptedOutcome(
            outcome_id="o-1",
            accepted_outcome_identity="decision://o-1",
            stage="finalize",
            refs=[_ref("wbc", "wbc://o-1")],
            accepted_resolution_refs=[],
        )
    # Censored outcomes cannot carry an exact time and require a lower bound.
    with pytest.raises(ValueError):
        _outcome("o-2", censored=True, time_seconds=10.0, lower_bound_seconds=5.0)
    with pytest.raises(ValueError):
        _outcome("o-3", censored=True)
    # Completed outcomes cannot carry a lower bound.
    with pytest.raises(ValueError):
        _outcome("o-4", time_seconds=10.0, lower_bound_seconds=5.0)
    # Cost claims pin their exact coordinates (authoritative cost refs).
    with pytest.raises(ValueError):
        ee.NormalizedAcceptedOutcome(
            outcome_id="o-5",
            accepted_outcome_identity="decision://o-5",
            stage="finalize",
            work_ledger_cost=1.0,
            refs=[_ref("wbc", "wbc://o-5")],
            accepted_resolution_refs=[_ref("run_authority", "decision://o-5")],
        )
    # The typed exclusion reason must accompany an exclusion flag (SC18).
    with pytest.raises(ValueError):
        _outcome("o-6", deep_work=True)
    with pytest.raises(ValueError):
        _outcome(
            "o-7",
            excluded_reason=ee.OutcomeExclusionReason.LEGITIMATE_DEPTH,
        )


# ---------------------------------------------------------------------------
# Route mismatch comparison (SC18)
# ---------------------------------------------------------------------------


def test_route_mismatch_named_legs_per_accepted_outcome() -> None:
    outcome = _outcome(
        "o-1",
        expected_route="model-a",
        resolved_route="model-b",
        provider_actual_route="model-a",
        time_seconds=100.0,
    )
    findings = ee.analyze_route_mismatches([outcome])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.family == "route_mismatch"
    assert finding.expected_route == "model-a"
    assert finding.resolved_route == "model-b"
    assert finding.provider_actual_route == "model-a"
    # Expected==actual so only the expected-vs-resolved and
    # resolved-vs-provider-actual legs are mismatches.
    assert finding.mismatch_legs == (
        ec.RouteMismatchLeg.EXPECTED_VS_RESOLVED,
        ec.RouteMismatchLeg.RESOLVED_VS_PROVIDER_ACTUAL,
    )
    assert finding.references.accepted_resolution_refs
    assert finding.references.source_refs
    assert finding.economics is not None
    assert finding.economics.time_seconds_per_accepted == 100.0


def test_route_mismatch_all_three_legs_when_all_differ() -> None:
    outcome = _outcome(
        "o-1",
        expected_route="model-a",
        resolved_route="model-b",
        provider_actual_route="model-c",
    )
    findings = ee.analyze_route_mismatches([outcome])
    assert len(findings) == 1
    assert findings[0].mismatch_legs == (
        ec.RouteMismatchLeg.EXPECTED_VS_PROVIDER_ACTUAL,
        ec.RouteMismatchLeg.EXPECTED_VS_RESOLVED,
        ec.RouteMismatchLeg.RESOLVED_VS_PROVIDER_ACTUAL,
    )


def test_missing_route_leg_is_unknown_never_mismatch() -> None:
    # Expected and resolved present, provider actual missing: the
    # resolved-vs-actual and expected-vs-actual legs stay unknown, never
    # named as mismatches; expected-vs-resolved still applies.
    outcome = _outcome(
        "o-1",
        expected_route="model-a",
        resolved_route="model-b",
    )
    findings = ee.analyze_route_mismatches([outcome])
    assert len(findings) == 1
    assert findings[0].mismatch_legs == (
        ec.RouteMismatchLeg.EXPECTED_VS_RESOLVED,
    )
    assert findings[0].provider_actual_route is None


def test_missing_all_but_one_leg_produces_no_finding() -> None:
    outcome = _outcome("o-1", resolved_route="model-b")
    assert ee.analyze_route_mismatches([outcome]) == ()


def test_consistent_routes_produce_no_finding() -> None:
    outcome = _outcome(
        "o-1",
        expected_route="model-a",
        resolved_route="model-a",
        provider_actual_route="model-a",
    )
    assert ee.analyze_route_mismatches([outcome]) == ()


def test_declared_aliases_resolve_equivalence_only_when_declared() -> None:
    aliases = [
        ee.DeclaredRouteAlias(canonical="model-a", aliases=("provider-model-a",)),
    ]
    # The provider reports a declared alias spelling -> equivalent, no
    # mismatch with the expected route.
    declared = _outcome(
        "o-1",
        expected_route="model-a",
        resolved_route="model-a",
        provider_actual_route="provider-model-a",
    )
    assert ee.analyze_route_mismatches([declared], declared_aliases=aliases) == ()
    # The SAME spelling WITHOUT the declared binding is a mismatch (aliases
    # are never inferred).
    undeclared = ee.analyze_route_mismatches([declared])
    assert len(undeclared) == 1
    assert undeclared[0].mismatch_legs == (
        ec.RouteMismatchLeg.EXPECTED_VS_PROVIDER_ACTUAL,
        ec.RouteMismatchLeg.RESOLVED_VS_PROVIDER_ACTUAL,
    )


def test_route_mismatch_finding_ids_are_deterministic() -> None:
    first = ee.derive_route_mismatch_finding_id(outcome_identity="decision://o-1")
    second = ee.derive_route_mismatch_finding_id(outcome_identity="decision://o-1")
    other = ee.derive_route_mismatch_finding_id(outcome_identity="decision://o-2")
    assert first == second
    assert first != other
    assert first.startswith("efficiency_route_mismatch|")


def test_route_mismatches_are_input_order_independent() -> None:
    outcomes = [
        _outcome("o-1", expected_route="a", resolved_route="b"),
        _outcome("o-2", expected_route="a", resolved_route="c"),
    ]
    forward = ee.analyze_route_mismatches(outcomes)
    backward = ee.analyze_route_mismatches(list(reversed(outcomes)))
    assert forward == backward
    assert [finding.finding_id for finding in forward] == sorted(
        finding.finding_id for finding in forward
    )


def test_route_mismatch_finding_roundtrip_and_hash_canonically() -> None:
    outcome = _outcome("o-1", expected_route="a", resolved_route="b")
    finding = ee.analyze_route_mismatches([outcome])[0]
    decoded = strict_loads(ec.RouteMismatchFinding, canonical_dumps(finding))
    assert decoded == finding
    assert canonical_digest(finding) == canonical_digest(decoded)


# ---------------------------------------------------------------------------
# Accepted-outcome economics (SC18)
# ---------------------------------------------------------------------------


def test_outcome_economics_per_accepted_denominator_gated() -> None:
    outcome = _outcome(
        "o-1",
        time_seconds=120.0,
        tokens=5000.0,
        work_ledger_cost=0.5,
        quality=0.9,
        expected_quality=0.8,
        robustness=ec.RobustnessKind.THOROUGH,
        coverage=ec.DenominatorCoverage(metric="accepted", numerator=1, denominator=1),
    )
    economics = ee.compute_outcome_economics(outcome)
    assert economics is not None
    # Exactly one accepted outcome is the denominator basis (never raw totals
    # without it).
    assert economics.accepted_outcome_count == 1
    assert economics.time_seconds_per_accepted == 120.0
    assert economics.tokens_per_accepted == 5000.0
    assert economics.cost_per_accepted == 0.5
    assert economics.raw_time_seconds_total == 120.0  # explicit context only
    assert economics.quality_delta == pytest.approx(0.1)
    # Authoritative cost names the typed source and pins the exact coordinate.
    assert economics.cost_source is ec.CostSourceKind.WBC_WORK_LEDGER
    assert economics.cost_source_ref is not None
    assert economics.cost_source_ref.locator == "wbc://o-1/ledger"


def test_authoritative_cost_precedence_work_ledger_wins_never_merged() -> None:
    outcome = _outcome(
        "o-1",
        provider_reported_cost=10.0,
        work_ledger_cost=2.0,
    )
    cost = ee.authoritative_cost(outcome)
    assert cost is not None
    value, source, ref = cost
    assert value == 2.0
    assert source is ec.CostSourceKind.WBC_WORK_LEDGER
    assert ref.locator == "wbc://o-1/ledger"
    # The provider-reported value is never merged into the claim.
    assert value != 10.0
    economics = ee.compute_outcome_economics(outcome)
    assert economics is not None
    assert economics.cost_per_accepted == 2.0
    assert economics.cost_source is ec.CostSourceKind.WBC_WORK_LEDGER


def test_authoritative_cost_falls_back_to_provider_reported() -> None:
    outcome = _outcome("o-1", provider_reported_cost=10.0)
    cost = ee.authoritative_cost(outcome)
    assert cost is not None
    value, source, ref = cost
    assert value == 10.0
    assert source is ec.CostSourceKind.PROVIDER_REPORTED
    assert ref.locator == "native_manifest://o-1/cost"


def test_missing_pricing_stays_explicit_unknown() -> None:
    outcome = _outcome("o-1", time_seconds=120.0)
    economics = ee.compute_outcome_economics(outcome)
    assert economics is not None
    assert economics.cost_per_accepted is None
    assert economics.cost_source is None
    assert economics.cost_source_ref is None


def test_quality_regression_is_negative_delta() -> None:
    outcome = _outcome(
        "o-1",
        time_seconds=120.0,
        quality=0.7,
        expected_quality=0.9,
    )
    economics = ee.compute_outcome_economics(outcome)
    assert economics is not None
    assert economics.quality_delta == pytest.approx(-0.2)


def test_zero_accepted_denominator_rejected_by_contract() -> None:
    # The T3 contract rejects economics claims without a positive
    # accepted-outcome denominator; T17 never fabricates one.
    with pytest.raises(ValueError):
        ec.AcceptedOutcomeEconomics(
            accepted_outcome_count=0,
            time_seconds_per_accepted=10.0,
        )
    with pytest.raises(ValueError):
        ec.AcceptedOutcomeEconomics(
            accepted_outcome_count=None,
            time_seconds_per_accepted=10.0,
        )


def test_censored_outcome_time_never_coerced() -> None:
    outcome = _outcome(
        "o-1",
        censored=True,
        lower_bound_seconds=300.0,
        tokens=100.0,
    )
    economics = ee.compute_outcome_economics(outcome)
    assert economics is not None
    # The censored outcome has no exact time claim — never coerced to
    # completion or zero.
    assert economics.time_seconds_per_accepted is None
    assert economics.raw_time_seconds_total is None
    assert economics.tokens_per_accepted == 100.0


def test_analyze_outcome_economics_retains_covariates() -> None:
    outcomes = [
        _outcome(
            "o-1",
            time_seconds=120.0,
            work_ledger_cost=0.5,
            robustness=ec.RobustnessKind.EXTREME,
            exploration=True,
            excluded_reason=ee.OutcomeExclusionReason.EXPLORATION,
            coverage=ec.DenominatorCoverage(
                metric="accepted", numerator=2, denominator=4
            ),
        ),
        _outcome("o-2", time_seconds=60.0),
    ]
    records = ee.analyze_outcome_economics(outcomes)
    assert len(records) == 2
    first = records[0]
    assert first.outcome_id == "o-1"
    assert first.robustness is ec.RobustnessKind.EXTREME
    assert first.exploration is True
    assert first.coverage == pytest.approx(0.5)
    assert first.economics.cost_source is ec.CostSourceKind.WBC_WORK_LEDGER


def test_analyze_outcome_economics_sorted_and_denominator_gated() -> None:
    outcomes = [
        _outcome("o-2", time_seconds=60.0),
        _outcome("o-1", time_seconds=120.0),
    ]
    records = ee.analyze_outcome_economics(outcomes)
    assert [record.outcome_id for record in records] == ["o-1", "o-2"]
    assert all(record.economics.accepted_outcome_count == 1 for record in records)


# ---------------------------------------------------------------------------
# Conservative avoidable-impact estimate (SC18)
# ---------------------------------------------------------------------------


def _p95_upper(value: float) -> ec.QuantileBounds:
    return ec.QuantileBounds(
        value=value - 10, lower_bound=value - 20, upper_bound=value
    )


def test_avoidable_impact_exact_excess_over_slo() -> None:
    outcomes = [
        _outcome("o-1", time_seconds=1200.0),
        _outcome("o-2", time_seconds=600.0),
    ]
    estimate = ee.estimate_avoidable_impact(outcomes, slo_seconds=900.0)
    assert estimate.eligible_bound_seconds == 900.0
    # Only the outcome above the SLO contributes excess: 1200 - 900 = 300.
    assert estimate.lower_bound_seconds == pytest.approx(300.0)
    assert estimate.upper_bound_seconds == pytest.approx(300.0)
    assert estimate.unknown_count == 0
    assert estimate.excluded_count == 0
    assert estimate.eligible_outcome_count == 2


def test_avoidable_impact_uses_p95_upper_when_no_slo() -> None:
    outcomes = [_outcome("o-1", time_seconds=400.0)]
    estimate = ee.estimate_avoidable_impact(outcomes, p95=_p95_upper(320.0))
    assert estimate.eligible_bound_seconds == 320.0
    assert estimate.lower_bound_seconds == pytest.approx(80.0)


def test_avoidable_impact_censored_lower_bound_floor_and_unknown_upper() -> None:
    outcomes = [
        _outcome("o-1", time_seconds=1200.0),
        _outcome("o-2", censored=True, lower_bound_seconds=1000.0),
    ]
    estimate = ee.estimate_avoidable_impact(outcomes, slo_seconds=900.0)
    # Exact excess 300 + censored known floor 100 -> 400 lower bound.
    assert estimate.lower_bound_seconds == pytest.approx(400.0)
    # The censored measure makes the finite upper bound unknown.
    assert estimate.upper_bound_seconds is None
    assert estimate.unknown_count == 1
    assert estimate.eligible_outcome_count == 2


def test_avoidable_impact_missing_time_is_unknown() -> None:
    outcomes = [
        _outcome("o-1", time_seconds=1200.0),
        _outcome("o-2", tokens=100.0),  # no time measure at all
    ]
    estimate = ee.estimate_avoidable_impact(outcomes, slo_seconds=900.0)
    assert estimate.lower_bound_seconds == pytest.approx(300.0)
    assert estimate.upper_bound_seconds is None
    assert estimate.unknown_count == 1


def test_avoidable_impact_excludes_legitimate_expensive_outcomes() -> None:
    outcomes = [
        _outcome("o-1", time_seconds=5000.0),
        _outcome(
            "o-2",
            time_seconds=5000.0,
            excluded_reason=ee.OutcomeExclusionReason.LEGITIMATE_DEPTH,
            deep_work=True,
        ),
        _outcome(
            "o-3",
            time_seconds=5000.0,
            excluded_reason=ee.OutcomeExclusionReason.EXPLORATION,
            exploration=True,
        ),
    ]
    estimate = ee.estimate_avoidable_impact(outcomes, slo_seconds=900.0)
    # Only the non-excluded outcome contributes excess.
    assert estimate.lower_bound_seconds == pytest.approx(4100.0)
    assert estimate.excluded_count == 2
    assert estimate.eligible_outcome_count == 1


def test_avoidable_impact_no_reference_is_all_unknown() -> None:
    outcomes = [
        _outcome("o-1", time_seconds=5000.0),
        _outcome("o-2", time_seconds=100.0),
    ]
    estimate = ee.estimate_avoidable_impact(outcomes)
    assert estimate.eligible_bound_seconds is None
    assert estimate.lower_bound_seconds == 0.0
    assert estimate.upper_bound_seconds is None
    assert estimate.unknown_count == 2
    assert estimate.eligible_outcome_count == 0