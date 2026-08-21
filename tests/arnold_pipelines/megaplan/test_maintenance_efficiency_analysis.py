"""Focused proof tests for M5 loop-family analyzers (Step 14 / T14).

Proves the pure analysis module:

* equivalent-failure, retry-loop, duplicate-call, and no-progress analyzers;
* problem signatures are separate from occurrence IDs — finding IDs derive
  from the normalized problem signature (never from call IDs), so the same
  problem across different occurrences yields the same finding identity;
* exact accepted-outcome denominators (SC15) — duplicate and no-progress
  impacts are counted only against exact accepted outcomes, and findings
  without any exact attribution carry ``economics=None`` (a missing
  denominator is never inferred);
* every finding anchors to exact accepted-resolution and source references
  with exact-when-present gate/backoff, censoring, and active-custody refs;
* determinism — input order never changes finding IDs, reference unions, or
  output ordering.

All findings are typed Step 3 contracts that strict-decode and hash
canonically.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from arnold_pipelines.megaplan.maintenance import efficiency_analysis as ea
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


def _ts(hour: int = 12, minute: int = 0) -> datetime:
    return datetime(2026, 8, 18, hour, minute, tzinfo=UTC)


def _ref(owner: str, locator: str, identity: str | None = None) -> OwnerRef:
    return OwnerRef(owner=owner, locator=locator, identity=identity, digest="a" * 64)


def _call(
    call_id: str,
    *,
    stage: str = "finalize",
    outcome: ea.CallOutcome = ea.CallOutcome.FAILED,
    failure_signature: str | None = None,
    operation_key: str | None = None,
    duplicate_key: str | None = None,
    accepted_outcome_id: str | None = None,
    elapsed_seconds: float | None = None,
    no_progress_delta_seconds: float | None = None,
    censored: bool = False,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> ea.NormalizedCall:
    refs = [_ref("wbc", f"wbc://{call_id}")]
    accepted_refs = (
        [_ref("run_authority", f"decision://{accepted_outcome_id}")]
        if accepted_outcome_id is not None
        else []
    )
    censoring_refs = [_ref("wbc", f"wbc://{call_id}/censor")] if censored else []
    return ea.NormalizedCall(
        call_id=call_id,
        stage=stage,
        outcome=outcome,
        failure_signature=failure_signature,
        operation_key=operation_key,
        duplicate_key=duplicate_key,
        accepted_outcome_id=accepted_outcome_id,
        elapsed_seconds=elapsed_seconds,
        no_progress_delta_seconds=no_progress_delta_seconds,
        censored=censored,
        started_at=started_at,
        ended_at=ended_at,
        refs=refs,
        accepted_resolution_refs=accepted_refs,
        censoring_refs=censoring_refs,
    )


# ---------------------------------------------------------------------------
# NormalizedCall contract discipline
# ---------------------------------------------------------------------------


def test_normalized_call_requires_source_refs() -> None:
    with pytest.raises(ValueError):
        ea.NormalizedCall(
            call_id="call-1",
            stage="finalize",
            outcome=ea.CallOutcome.FAILED,
            refs=[],
        )


def test_normalized_call_attribution_requires_resolution_refs() -> None:
    with pytest.raises(ValueError):
        ea.NormalizedCall(
            call_id="call-1",
            stage="finalize",
            outcome=ea.CallOutcome.FAILED,
            accepted_outcome_id="outcome-1",
            refs=[_ref("wbc", "wbc://call-1")],
            accepted_resolution_refs=[],
        )


# ---------------------------------------------------------------------------
# Problem signatures separate from occurrence IDs
# ---------------------------------------------------------------------------


def test_loop_problem_id_is_signature_based_and_classifier_separated() -> None:
    first = ea.derive_loop_problem_id(
        ec.LoopFindingKind.REVISION_LOOP,
        stage="finalize",
        problem_signature="north_star_actions-schema",
    )
    again = ea.derive_loop_problem_id(
        ec.LoopFindingKind.REVISION_LOOP,
        stage="finalize",
        problem_signature="north_star_actions-schema",
    )
    assert first == again
    other_sig = ea.derive_loop_problem_id(
        ec.LoopFindingKind.REVISION_LOOP,
        stage="finalize",
        problem_signature="other-signature",
    )
    assert first != other_sig
    other_cls = ea.derive_loop_problem_id(
        ec.LoopFindingKind.REVISION_LOOP,
        stage="finalize",
        problem_signature="north_star_actions-schema",
        classifier_version="cls-v2",
    )
    assert first != other_cls


def test_same_problem_different_occurrences_yield_same_finding_id() -> None:
    calls = [
        _call("occ-1", failure_signature="schema-failure", accepted_outcome_id="out-1"),
        _call("occ-2", failure_signature="schema-failure", accepted_outcome_id="out-1"),
    ]
    findings = ea.analyze_equivalent_failures(calls)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ec.LoopFindingKind.REVISION_LOOP
    assert finding.attempt_count == 2
    assert "occ-1" not in finding.finding_id and "occ-2" not in finding.finding_id
    # Occurrences are attached as exact source references, not identity.
    locators = {ref.locator for ref in finding.references.source_refs}
    assert locators == {"wbc://occ-1", "wbc://occ-2"}


# ---------------------------------------------------------------------------
# Equivalent failures / retry loops
# ---------------------------------------------------------------------------


def test_equivalent_failures_require_two_matching_signatures() -> None:
    single = [_call("occ-1", failure_signature="schema-failure")]
    assert ea.analyze_equivalent_failures(single) == ()
    matched = [
        _call("occ-1", failure_signature="schema-failure", accepted_outcome_id="out-1"),
        _call("occ-2", failure_signature="schema-failure", accepted_outcome_id="out-1"),
    ]
    findings = ea.analyze_equivalent_failures(matched)
    assert len(findings) == 1
    assert findings[0].repeated_stage == "finalize"
    assert findings[0].attempt_count == 2
    # Exact accepted-outcome denominator: one outcome, two attempts.
    assert findings[0].economics is not None
    assert findings[0].economics.accepted_outcome_count == 1


def test_equivalent_failures_separate_signatures_stay_separate() -> None:
    calls = [
        _call("occ-1", stage="finalize", failure_signature="sig-a", accepted_outcome_id="out-1"),
        _call("occ-2", stage="finalize", failure_signature="sig-a", accepted_outcome_id="out-1"),
        _call("occ-3", stage="finalize", failure_signature="sig-b", accepted_outcome_id="out-2"),
        _call("occ-4", stage="finalize", failure_signature="sig-b", accepted_outcome_id="out-2"),
        _call("occ-5", stage="gate", failure_signature="sig-a", accepted_outcome_id="out-3"),
        _call("occ-6", stage="gate", failure_signature="sig-a", accepted_outcome_id="out-3"),
    ]
    findings = ea.analyze_equivalent_failures(calls)
    assert len(findings) == 3  # (finalize, sig-a), (finalize, sig-b), (gate, sig-a)
    assert {f.repeated_stage for f in findings} == {"finalize", "gate"}


def test_retry_loops_group_by_operation_key() -> None:
    calls = [
        _call("occ-1", operation_key="op-1", accepted_outcome_id="out-1"),
        _call("occ-2", operation_key="op-1", accepted_outcome_id="out-1"),
        _call("occ-3", operation_key="op-2"),
    ]
    findings = ea.analyze_retry_loops(calls)
    assert len(findings) == 1
    assert findings[0].kind is ec.LoopFindingKind.RETRY_LOOP
    assert findings[0].attempt_count == 2
    assert findings[0].repeated_stage == "finalize"


def test_retry_loops_ignore_single_attempts() -> None:
    calls = [_call("occ-1", operation_key="op-1")]
    assert ea.analyze_retry_loops(calls) == ()


# ---------------------------------------------------------------------------
# Duplicate calls and no-progress (SC15 denominator discipline)
# ---------------------------------------------------------------------------


def test_duplicate_calls_count_impacts_against_exact_accepted_outcomes() -> None:
    calls = [
        _call("occ-1", duplicate_key="dup-1", accepted_outcome_id="out-1", elapsed_seconds=600.0),
        _call("occ-2", duplicate_key="dup-1", accepted_outcome_id="out-1", elapsed_seconds=300.0),
        _call("occ-3", duplicate_key="dup-1", accepted_outcome_id="out-2", elapsed_seconds=900.0),
    ]
    findings = ea.analyze_duplicate_calls(calls)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ec.LoopFindingKind.DUPLICATE_CALL
    assert finding.attempt_count == 3
    # Exact denominator: two distinct accepted outcomes.
    assert finding.economics is not None
    assert finding.economics.accepted_outcome_count == 2
    assert finding.economics.time_seconds_per_accepted == (600.0 + 300.0 + 900.0) / 2


def test_duplicate_calls_without_accepted_outcome_anchor_yield_no_finding() -> None:
    # Every T3 finding anchors to an exact accepted resolution; duplicates
    # with no accepted-outcome attribution stay context (conservative, SC15).
    calls = [
        _call("occ-1", duplicate_key="dup-1"),
        _call("occ-2", duplicate_key="dup-1"),
    ]
    assert ea.analyze_duplicate_calls(calls) == ()


def test_duplicate_calls_mixed_attribution_counts_only_exact_outcomes() -> None:
    # One duplicated call is attributed to an exact accepted outcome; the
    # unattributed occurrence is evidence context but never an inferred
    # impact denominator.
    calls = [
        _call("occ-1", duplicate_key="dup-1", accepted_outcome_id="out-1",
              elapsed_seconds=600.0),
        _call("occ-2", duplicate_key="dup-1", elapsed_seconds=300.0),
    ]
    findings = ea.analyze_duplicate_calls(calls)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.attempt_count == 2
    assert finding.economics is not None
    assert finding.economics.accepted_outcome_count == 1
    assert finding.economics.time_seconds_per_accepted == 600.0
    # Both occurrences remain exact source references.
    source_locs = {ref.locator for ref in finding.references.source_refs}
    assert source_locs == {"wbc://occ-1", "wbc://occ-2"}


def test_no_progress_findings_require_exact_delta_and_threshold() -> None:
    calls = [
        _call("occ-1", failure_signature="stuck", accepted_outcome_id="out-1",
              no_progress_delta_seconds=900.0),
        _call("occ-2", failure_signature="stuck", accepted_outcome_id="out-1",
              no_progress_delta_seconds=300.0),
        _call("occ-3", failure_signature="slow", accepted_outcome_id="out-2",
              no_progress_delta_seconds=60.0),
    ]
    findings = ea.analyze_no_progress(calls, min_delta_seconds=120.0)
    # occ-3's 60s delta is at or below the threshold; the two "stuck" calls
    # group by problem signature with the explicit summed delta.
    assert len(findings) == 1
    stuck = findings[0]
    assert stuck.attempt_count == 2
    assert stuck.no_progress_delta_seconds == 1200.0


def test_no_progress_single_call_without_signature_is_own_group() -> None:
    calls = [_call("occ-1", accepted_outcome_id="out-1", no_progress_delta_seconds=900.0)]
    findings = ea.analyze_no_progress(calls)
    assert len(findings) == 1
    assert findings[0].kind is ec.LoopFindingKind.NO_PROGRESS
    assert findings[0].attempt_count == 1
    assert findings[0].no_progress_delta_seconds == 900.0


def test_no_progress_impacts_counted_only_against_exact_accepted_outcomes() -> None:
    calls = [
        _call("occ-1", failure_signature="stuck", accepted_outcome_id="out-1",
              no_progress_delta_seconds=900.0),
        _call("occ-2", failure_signature="stuck", no_progress_delta_seconds=300.0),
    ]
    findings = ea.analyze_no_progress(calls)
    assert len(findings) == 1
    economics = findings[0].economics
    # Only the attributed call contributes to the exact denominator; the
    # unattributed call's delta is context, never an inferred impact.
    assert economics is not None
    assert economics.accepted_outcome_count == 1
    assert economics.time_seconds_per_accepted == 900.0


# ---------------------------------------------------------------------------
# Reference bundles and censoring
# ---------------------------------------------------------------------------


def test_findings_union_exact_reference_bundles() -> None:
    calls = [
        _call("occ-1", failure_signature="sig-a", accepted_outcome_id="out-1",
              censored=True),
        _call("occ-2", failure_signature="sig-a", accepted_outcome_id="out-2"),
    ]
    findings = ea.analyze_equivalent_failures(calls)
    assert len(findings) == 1
    references = findings[0].references
    resolution_locs = {ref.locator for ref in references.accepted_resolution_refs}
    assert resolution_locs == {"decision://out-1", "decision://out-2"}
    source_locs = {ref.locator for ref in references.source_refs}
    assert source_locs == {"wbc://occ-1", "wbc://occ-2"}
    censor_locs = {ref.locator for ref in references.censoring_refs}
    assert censor_locs == {"wbc://occ-1/censor"}


def test_loop_span_uses_group_timestamps() -> None:
    calls = [
        _call("occ-1", operation_key="op-1", accepted_outcome_id="out-1",
              started_at=_ts(10), ended_at=_ts(11)),
        _call("occ-2", operation_key="op-1", accepted_outcome_id="out-1",
              started_at=_ts(12), ended_at=_ts(13)),
    ]
    findings = ea.analyze_retry_loops(calls)
    assert len(findings) == 1
    # max end (13:00) - min start (10:00) = 3 hours.
    assert findings[0].loop_span_seconds == 3 * 3600.0


# ---------------------------------------------------------------------------
# Combined analyzer and determinism
# ---------------------------------------------------------------------------


def test_analyze_loops_combines_families_sorted_by_finding_id() -> None:
    calls = [
        _call("occ-1", failure_signature="sig-a", accepted_outcome_id="out-1"),
        _call("occ-2", failure_signature="sig-a", accepted_outcome_id="out-1"),
        _call("occ-3", duplicate_key="dup-1", accepted_outcome_id="out-1"),
        _call("occ-4", duplicate_key="dup-1", accepted_outcome_id="out-1"),
        _call("occ-5", failure_signature="stuck", accepted_outcome_id="out-1",
              no_progress_delta_seconds=900.0),
    ]
    findings = ea.analyze_loops(calls)
    assert len(findings) == 3
    kinds = {finding.kind for finding in findings}
    assert kinds == {
        ec.LoopFindingKind.REVISION_LOOP,
        ec.LoopFindingKind.DUPLICATE_CALL,
        ec.LoopFindingKind.NO_PROGRESS,
    }
    ids = [finding.finding_id for finding in findings]
    assert ids == sorted(ids)


def test_analyzers_are_input_order_independent() -> None:
    forward = [
        _call("occ-1", failure_signature="sig-a", accepted_outcome_id="out-1"),
        _call("occ-2", failure_signature="sig-a", accepted_outcome_id="out-1"),
        _call("occ-3", duplicate_key="dup-1", accepted_outcome_id="out-2"),
        _call("occ-4", duplicate_key="dup-1", accepted_outcome_id="out-2"),
    ]
    reversed_calls = list(reversed(forward))
    a = ea.analyze_loops(forward)
    b = ea.analyze_loops(reversed_calls)
    assert [canonical_dumps(f) for f in a] == [canonical_dumps(f) for f in b]


def test_findings_roundtrip_and_hash_canonically() -> None:
    calls = [
        _call("occ-1", failure_signature="sig-a", accepted_outcome_id="out-1"),
        _call("occ-2", failure_signature="sig-a", accepted_outcome_id="out-1"),
    ]
    findings = ea.analyze_equivalent_failures(calls)
    assert len(findings) == 1
    finding = findings[0]
    decoded = strict_loads(ec.LoopFinding, canonical_dumps(finding))
    assert decoded == finding
    assert canonical_digest(decoded) == canonical_digest(finding)


def test_empty_call_set_yields_no_findings() -> None:
    assert ea.analyze_loops([]) == ()
    assert ea.analyze_equivalent_failures([]) == ()
    assert ea.analyze_no_progress([]) == ()


# ---------------------------------------------------------------------------
# Plan Step 13 / T13: dwell-family analyzers (gate / finalize-publication /
# review) with the shared exclusion model (SC14)
# ---------------------------------------------------------------------------


def _dwell_obs(
    observation_id: str,
    kind: ec.DwellFindingKind = ec.DwellFindingKind.GATE,
    *,
    stage: str = "finalize",
    elapsed_seconds: float | None = None,
    censored: bool = False,
    lower_bound_seconds: float | None = None,
    slo_seconds: float | None = None,
    excluded_reason: ea.DwellExclusionReason | None = None,
    deep_work: bool = False,
    exploration: bool = False,
    configured_backoff: bool = False,
    human_gate: bool = False,
    productive: bool = False,
    accepted_outcome_id: str | None = None,
    gate_backoff: bool = False,
    active_custody: bool = False,
) -> ea.NormalizedDwellObservation:
    refs = [_ref("wbc", f"wbc://{observation_id}")]
    accepted_refs = (
        [_ref("run_authority", f"decision://{accepted_outcome_id}")]
        if accepted_outcome_id is not None
        else []
    )
    censoring_refs = (
        [_ref("wbc", f"wbc://{observation_id}/censor")] if censored else []
    )
    gate_backoff_refs = (
        [_ref("plan", f"gate://{observation_id}")] if gate_backoff else []
    )
    custody_refs = (
        [_ref("repair_custody", f"custody://{observation_id}")] if active_custody else []
    )
    return ea.NormalizedDwellObservation(
        observation_id=observation_id,
        kind=kind,
        stage=stage,
        elapsed_seconds=elapsed_seconds,
        censored=censored,
        lower_bound_seconds=lower_bound_seconds,
        slo_seconds=slo_seconds,
        excluded_reason=excluded_reason,
        deep_work=deep_work,
        exploration=exploration,
        configured_backoff=configured_backoff,
        human_gate=human_gate,
        productive=productive,
        accepted_outcome_id=accepted_outcome_id,
        refs=refs,
        accepted_resolution_refs=accepted_refs,
        gate_backoff_refs=gate_backoff_refs,
        censoring_refs=censoring_refs,
        active_custody_refs=custody_refs,
    )


def _bounds(
    *, p95_upper: float, median_upper: float
) -> tuple[ec.QuantileBounds, ec.QuantileBounds]:
    p95 = ec.QuantileBounds(
        value=p95_upper - 10, lower_bound=p95_upper - 20, upper_bound=p95_upper
    )
    median = ec.QuantileBounds(
        value=median_upper - 10,
        lower_bound=median_upper - 20,
        upper_bound=median_upper,
    )
    return p95, median


def test_dwell_leg_contract_discipline() -> None:
    # Legs require at least one exact source ref.
    with pytest.raises(ValueError):
        ea.NormalizedDwellObservation(
            observation_id="gate-1",
            kind=ec.DwellFindingKind.GATE,
            stage="finalize",
            elapsed_seconds=10.0,
            refs=[],
        )
    # Completed legs require an exact elapsed duration.
    with pytest.raises(ValueError):
        _dwell_obs("gate-1", elapsed_seconds=None)
    # Censored legs cannot carry a completion duration and require a lower
    # bound (never coerced to completion or zero).
    with pytest.raises(ValueError):
        _dwell_obs("gate-2", censored=True, elapsed_seconds=10.0, lower_bound_seconds=5.0)
    with pytest.raises(ValueError):
        _dwell_obs("gate-3", censored=True)
    # The typed exclusion reason must accompany an exclusion flag (SC14).
    with pytest.raises(ValueError):
        _dwell_obs("gate-4", elapsed_seconds=10.0, deep_work=True)
    with pytest.raises(ValueError):
        _dwell_obs(
            "gate-5",
            elapsed_seconds=10.0,
            excluded_reason=ea.DwellExclusionReason.HUMAN_GATE,
        )
    # Attribution requires exact accepted-resolution refs.
    with pytest.raises(ValueError):
        ea.NormalizedDwellObservation(
            observation_id="gate-6",
            kind=ec.DwellFindingKind.GATE,
            stage="finalize",
            elapsed_seconds=10.0,
            accepted_outcome_id="outcome-1",
            refs=[_ref("wbc", "wbc://gate-6")],
            accepted_resolution_refs=[],
        )


def test_gate_dwell_flags_above_threshold_completed_legs() -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    leg = _dwell_obs(
        "gate-1",
        elapsed_seconds=600.0,
        accepted_outcome_id="outcome-1",
        gate_backoff=True,
        active_custody=True,
    )
    result = ea.analyze_gate_dwell(
        [leg], p95=p95, median=median, slo_seconds=900.0
    )
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.family == "dwell"
    assert finding.kind is ec.DwellFindingKind.GATE
    assert finding.duration_seconds == 600.0
    assert finding.censored is False
    assert finding.above_p95 is True
    assert finding.above_2x_median is True
    assert finding.above_slo is False
    assert finding.slo_seconds == 900.0
    # Avoidable impact is counted only against the exact accepted outcome.
    assert finding.economics is not None
    assert finding.economics.accepted_outcome_count == 1
    assert finding.economics.time_seconds_per_accepted == 600.0
    # Exact reference bundle: accepted resolution, source, gate/backoff,
    # censoring, and active-custody refs.
    assert finding.references.accepted_resolution_refs
    assert finding.references.source_refs
    assert finding.references.gate_backoff_refs
    assert finding.references.active_custody_refs
    assert finding.references.censoring_refs == ()
    # No excluded context for an avoidable leg.
    assert result.context == ()


def test_gate_dwell_below_threshold_is_context_flag_only() -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    leg = _dwell_obs("gate-fast", elapsed_seconds=60.0, accepted_outcome_id="outcome-1")
    result = ea.analyze_gate_dwell([leg], p95=p95, median=median)
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.above_p95 is False
    assert finding.above_2x_median is False
    assert finding.above_slo is False
    # No proven dwell => no avoidable-impact economics claim.
    assert finding.economics is None


def test_finalize_publication_gaps_covered_completed_and_censored() -> None:
    # The approximately 79/84/176-minute publication gaps: 79 min = 4740s.
    p95, median = _bounds(p95_upper=2400.0, median_upper=1200.0)
    completed_gap = _dwell_obs(
        "finalize-gap-79min",
        kind=ec.DwellFindingKind.FINALIZE_PUBLICATION,
        elapsed_seconds=4740.0,
        accepted_outcome_id="outcome-1",
    )
    censored_gap = _dwell_obs(
        "finalize-gap-176min",
        kind=ec.DwellFindingKind.FINALIZE_PUBLICATION,
        censored=True,
        lower_bound_seconds=10560.0,
        accepted_outcome_id="outcome-2",
    )
    result = ea.analyze_finalize_publication_dwell(
        [completed_gap, censored_gap], p95=p95, median=median
    )
    assert len(result.findings) == 2
    completed = next(
        finding
        for finding in result.findings
        if "finalize-gap-79min" in finding.references.source_refs[0].locator
    )
    # The completed gap is flagged above both conservative thresholds.
    assert completed.censored is False
    assert completed.duration_seconds == 4740.0
    assert completed.above_p95 is True
    assert completed.above_2x_median is True
    # The censored gap keeps its explicit lower bound — never coerced to a
    # completion duration or to zero — and is flagged because its lower
    # bound already proves the predicate (T12 unfinished lower-bound proof).
    censored = next(
        finding for finding in result.findings if finding is not completed
    )
    assert censored.censored is True
    assert censored.duration_seconds is None
    assert censored.lower_bound_seconds == 10560.0
    assert censored.above_p95 is True
    assert censored.above_2x_median is True
    assert censored.references.censoring_refs
    # The analyzer never suggests a WBC restart: findings stay pure dwell
    # observations with references only.
    assert all(
        ref.owner != "wbc" or "restart" not in (ref.record_type or "")
        for finding in result.findings
        for ref in finding.references.source_refs
    )


def test_censored_leg_unproven_lower_bound_is_not_flagged() -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    leg = _dwell_obs(
        "review-censored",
        kind=ec.DwellFindingKind.REVIEW,
        censored=True,
        lower_bound_seconds=100.0,
        accepted_outcome_id="outcome-1",
    )
    result = ea.analyze_review_dwell([leg], p95=p95, median=median)
    assert len(result.findings) == 1
    finding = result.findings[0]
    # The censored lower bound does NOT prove the predicate, so the leg is
    # recorded but never flagged and carries no avoidable-impact economics.
    assert finding.censored is True
    assert finding.lower_bound_seconds == 100.0
    assert finding.above_p95 is False
    assert finding.above_2x_median is False
    assert finding.above_slo is False
    assert finding.economics is None


@pytest.mark.parametrize(
    ("reason", "flag"),
    [
        (ea.DwellExclusionReason.LEGITIMATE_DEPTH, {"deep_work": True}),
        (ea.DwellExclusionReason.EXPLORATION, {"exploration": True}),
        (ea.DwellExclusionReason.CONFIGURED_BACKOFF, {"configured_backoff": True}),
        (ea.DwellExclusionReason.HUMAN_GATE, {"human_gate": True}),
        (ea.DwellExclusionReason.PRODUCTIVE, {"productive": True}),
    ],
    ids=["depth", "exploration", "backoff", "human_gate", "productive"],
)
def test_dwell_exclusions_never_enter_avoidable_findings(
    reason: ea.DwellExclusionReason, flag: dict[str, bool]
) -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    leg = _dwell_obs(
        f"excluded-{reason.value}",
        elapsed_seconds=5000.0,  # far above every threshold
        accepted_outcome_id="outcome-1",
        excluded_reason=reason,
        **flag,
    )
    result = ea.analyze_gate_dwell([leg], p95=p95, median=median)
    # SC14: the excluded leg never becomes a finding — it stays context.
    assert result.findings == ()
    assert len(result.context) == 1
    entry = result.context[0]
    assert entry.excluded_reason is reason
    assert entry.elapsed_seconds == 5000.0  # context is retained
    assert "excluded from avoidable-impact totals" in (entry.context_reason or "")


def test_dwell_unattributed_leg_is_context_not_finding() -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    leg = _dwell_obs("gate-unattributed", elapsed_seconds=5000.0)
    result = ea.analyze_gate_dwell([leg], p95=p95, median=median)
    assert result.findings == ()
    assert len(result.context) == 1
    assert result.context[0].context_reason == "no exact accepted-resolution anchor"
    assert result.context[0].elapsed_seconds == 5000.0


def test_dwell_without_baseline_bounds_is_context_only() -> None:
    leg = _dwell_obs("gate-nobounds", elapsed_seconds=5000.0, accepted_outcome_id="o-1")
    result = ea.analyze_gate_dwell([leg])
    assert len(result.findings) == 1
    finding = result.findings[0]
    # Without conservative bounds nothing can be proven above p95.
    assert finding.above_p95 is False
    assert finding.above_2x_median is False
    assert finding.above_slo is False
    assert finding.economics is None


def test_review_dwell_productive_review_excluded_context_retained() -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    productive = _dwell_obs(
        "review-productive",
        kind=ec.DwellFindingKind.REVIEW,
        elapsed_seconds=700.0,
        accepted_outcome_id="outcome-1",
        excluded_reason=ea.DwellExclusionReason.PRODUCTIVE,
        productive=True,
    )
    avoidable = _dwell_obs(
        "review-idle",
        kind=ec.DwellFindingKind.REVIEW,
        elapsed_seconds=700.0,
        accepted_outcome_id="outcome-2",
    )
    result = ea.analyze_review_dwell([productive, avoidable], p95=p95, median=median)
    assert len(result.findings) == 1
    assert result.findings[0].references.accepted_resolution_refs[0].locator == (
        "decision://outcome-2"
    )
    assert len(result.context) == 1
    assert result.context[0].excluded_reason is ea.DwellExclusionReason.PRODUCTIVE
    assert result.context[0].elapsed_seconds == 700.0


def test_analyze_dwell_combines_families_sorted() -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    legs = [
        _dwell_obs(
            "review-1",
            kind=ec.DwellFindingKind.REVIEW,
            elapsed_seconds=700.0,
            accepted_outcome_id="o-r",
        ),
        _dwell_obs(
            "finalize-1",
            kind=ec.DwellFindingKind.FINALIZE_PUBLICATION,
            elapsed_seconds=700.0,
            accepted_outcome_id="o-f",
        ),
        _dwell_obs(
            "gate-1",
            elapsed_seconds=700.0,
            accepted_outcome_id="o-g",
            excluded_reason=ea.DwellExclusionReason.HUMAN_GATE,
            human_gate=True,
        ),
    ]
    result = ea.analyze_dwell(legs, p95=p95, median=median)
    assert len(result.findings) == 2
    assert [finding.finding_id for finding in result.findings] == sorted(
        finding.finding_id for finding in result.findings
    )
    kinds = {finding.kind for finding in result.findings}
    assert kinds == {
        ec.DwellFindingKind.REVIEW,
        ec.DwellFindingKind.FINALIZE_PUBLICATION,
    }
    # The excluded gate leg stays in context, never in the finding stream.
    assert len(result.context) == 1
    assert result.context[0].excluded_reason is ea.DwellExclusionReason.HUMAN_GATE


def test_dwell_analyzers_are_input_order_independent() -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    legs = [
        _dwell_obs(
            "gate-1", elapsed_seconds=700.0, accepted_outcome_id="o-1"
        ),
        _dwell_obs(
            "gate-2",
            elapsed_seconds=60.0,
            accepted_outcome_id="o-2",
            excluded_reason=ea.DwellExclusionReason.CONFIGURED_BACKOFF,
            configured_backoff=True,
        ),
        _dwell_obs(
            "finalize-1",
            kind=ec.DwellFindingKind.FINALIZE_PUBLICATION,
            censored=True,
            lower_bound_seconds=700.0,
            accepted_outcome_id="o-3",
        ),
    ]
    forward = ea.analyze_dwell(legs, p95=p95, median=median)
    backward = ea.analyze_dwell(list(reversed(legs)), p95=p95, median=median)
    assert forward == backward
    assert forward.findings[0].finding_id == backward.findings[0].finding_id
    assert canonical_digest(forward) == canonical_digest(backward)


def test_dwell_findings_roundtrip_and_hash_canonically() -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    leg = _dwell_obs(
        "gate-1",
        elapsed_seconds=700.0,
        accepted_outcome_id="o-1",
        gate_backoff=True,
        active_custody=True,
    )
    result = ea.analyze_gate_dwell([leg], p95=p95, median=median, slo_seconds=600.0)
    finding = result.findings[0]
    assert finding.above_slo is True  # 700 > 600 declared SLO
    assert finding.slo_seconds == 600.0
    decoded = strict_loads(ec.DwellFinding, canonical_dumps(finding))
    assert decoded == finding
    assert decoded.finding_id == finding.finding_id
    assert canonical_digest(finding) == canonical_digest(decoded)


def test_empty_dwell_set_yields_no_findings() -> None:
    result = ea.analyze_dwell([])
    assert result.findings == ()


# ---------------------------------------------------------------------------
# Step 15 / T15: idle-handoff and repair-pattern analyzers + exclusion
# accounting (SC16)
# ---------------------------------------------------------------------------


def _handoff(
    observation_id: str,
    *,
    from_stage: str = "finalize",
    to_stage: str = "review",
    idle_seconds: float | None = None,
    censored: bool = False,
    lower_bound_seconds: float | None = None,
    accepted_outcome_id: str | None = None,
    excluded_reason: ea.DwellExclusionReason | None = None,
    deep_work: bool = False,
    exploration: bool = False,
    configured_backoff: bool = False,
    human_gate: bool = False,
    productive: bool = False,
    handed_off_at: datetime | None = None,
    active_custody: bool = False,
    gate_backoff: bool = False,
) -> ea.NormalizedHandoffObservation:
    refs = [_ref("wbc", f"wbc://{observation_id}")]
    accepted_refs = (
        [_ref("run_authority", f"decision://{accepted_outcome_id}")]
        if accepted_outcome_id is not None
        else []
    )
    censoring_refs = (
        [_ref("wbc", f"wbc://{observation_id}/censor")] if censored else []
    )
    gate_backoff_refs = (
        [_ref("plan", f"gate://{observation_id}")] if gate_backoff else []
    )
    custody_refs = (
        [_ref("repair_custody", f"custody://{observation_id}")] if active_custody else []
    )
    return ea.NormalizedHandoffObservation(
        observation_id=observation_id,
        from_stage=from_stage,
        to_stage=to_stage,
        handed_off_at=handed_off_at,
        idle_seconds=idle_seconds,
        censored=censored,
        lower_bound_seconds=lower_bound_seconds,
        excluded_reason=excluded_reason,
        deep_work=deep_work,
        exploration=exploration,
        configured_backoff=configured_backoff,
        human_gate=human_gate,
        productive=productive,
        accepted_outcome_id=accepted_outcome_id,
        refs=refs,
        accepted_resolution_refs=accepted_refs,
        gate_backoff_refs=gate_backoff_refs,
        censoring_refs=censoring_refs,
        active_custody_refs=custody_refs,
    )


def _repair_obs(
    observation_id: str,
    *,
    affected_contract: str = "north_star_actions",
    repair_signature: str = "gate-schema-failure",
    occurred_at: datetime | None = None,
    accepted_outcome_id: str | None = None,
    active_custody: bool = False,
) -> ea.NormalizedRepairPatternObservation:
    refs = [_ref("wbc", f"wbc://{observation_id}")]
    accepted_refs = (
        [_ref("run_authority", f"decision://{accepted_outcome_id}")]
        if accepted_outcome_id is not None
        else []
    )
    custody_refs = (
        [_ref("repair_custody", f"custody://{observation_id}")] if active_custody else []
    )
    return ea.NormalizedRepairPatternObservation(
        observation_id=observation_id,
        affected_contract=affected_contract,
        repair_signature=repair_signature,
        occurred_at=occurred_at,
        accepted_outcome_id=accepted_outcome_id,
        refs=refs,
        accepted_resolution_refs=accepted_refs,
        active_custody_refs=custody_refs,
    )


def test_handoff_observation_contract_discipline() -> None:
    # Handoffs require at least one exact source ref.
    with pytest.raises(ValueError):
        ea.NormalizedHandoffObservation(
            observation_id="h-1",
            from_stage="finalize",
            to_stage="review",
            idle_seconds=10.0,
            refs=[],
        )
    # Completed handoffs require an exact idle duration.
    with pytest.raises(ValueError):
        _handoff("h-2", idle_seconds=None)
    # Censored handoffs cannot carry an exact idle duration and require an
    # explicit lower bound (never coerced to completion or zero).
    with pytest.raises(ValueError):
        _handoff("h-3", censored=True, idle_seconds=10.0, lower_bound_seconds=5.0)
    with pytest.raises(ValueError):
        _handoff("h-4", censored=True)
    # Stages must differ.
    with pytest.raises(ValueError):
        _handoff("h-5", from_stage="finalize", to_stage="finalize", idle_seconds=10.0)
    # The typed exclusion reason must accompany an exclusion flag (SC14).
    with pytest.raises(ValueError):
        _handoff("h-6", idle_seconds=10.0, human_gate=True)
    with pytest.raises(ValueError):
        _handoff(
            "h-7",
            idle_seconds=10.0,
            excluded_reason=ea.DwellExclusionReason.HUMAN_GATE,
        )
    # Attribution requires exact accepted-resolution refs.
    with pytest.raises(ValueError):
        ea.NormalizedHandoffObservation(
            observation_id="h-8",
            from_stage="finalize",
            to_stage="review",
            idle_seconds=10.0,
            accepted_outcome_id="outcome-1",
            refs=[_ref("wbc", "wbc://h-8")],
            accepted_resolution_refs=[],
        )


def test_idle_handoffs_emit_claim_free_findings_with_references() -> None:
    handoff = _handoff(
        "h-1",
        idle_seconds=3600.0,
        accepted_outcome_id="outcome-1",
        active_custody=True,
        gate_backoff=True,
        handed_off_at=_ts(9),
    )
    result = ea.analyze_idle_handoffs([handoff])
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.family == "idle_handoff"
    assert finding.from_stage == "finalize"
    assert finding.to_stage == "review"
    assert finding.idle_seconds == 3600.0
    assert finding.handed_off_at is not None
    # SC16: custody is reference-only — the finding carries the exact
    # active-custody refs but never claims or alters custody.
    assert finding.references.active_custody_refs
    assert finding.references.active_custody_refs[0].owner == "repair_custody"
    assert finding.references.accepted_resolution_refs
    assert finding.references.source_refs
    assert finding.references.gate_backoff_refs
    # Impact economics are denominator-gated (single exact accepted outcome).
    assert finding.economics is not None
    assert finding.economics.accepted_outcome_count == 1
    assert finding.economics.time_seconds_per_accepted == 3600.0
    assert result.context == ()


def test_idle_handoff_exclusions_stay_context_never_findings() -> None:
    for reason, flag in [
        (ea.DwellExclusionReason.LEGITIMATE_DEPTH, {"deep_work": True}),
        (ea.DwellExclusionReason.EXPLORATION, {"exploration": True}),
        (ea.DwellExclusionReason.CONFIGURED_BACKOFF, {"configured_backoff": True}),
        (ea.DwellExclusionReason.HUMAN_GATE, {"human_gate": True}),
        (ea.DwellExclusionReason.PRODUCTIVE, {"productive": True}),
    ]:
        handoff = _handoff(
            f"h-excl-{reason.value}",
            idle_seconds=5000.0,
            accepted_outcome_id="outcome-1",
            excluded_reason=reason,
            **flag,
        )
        result = ea.analyze_idle_handoffs([handoff])
        assert result.findings == ()
        assert len(result.context) == 1
        entry = result.context[0]
        assert entry.excluded_reason is reason
        assert entry.idle_seconds == 5000.0  # context is retained
        assert "excluded from avoidable-impact totals" in (entry.context_reason or "")


def test_idle_handoff_unattributed_and_censored_stay_context() -> None:
    unattributed = _handoff("h-unattributed", idle_seconds=5000.0)
    censored = _handoff(
        "h-censored",
        censored=True,
        lower_bound_seconds=7200.0,
        accepted_outcome_id="outcome-2",
    )
    result = ea.analyze_idle_handoffs([unattributed, censored])
    assert result.findings == ()
    assert len(result.context) == 2
    reasons = {entry.context_reason for entry in result.context}
    assert any("no exact accepted-resolution anchor" in (r or "") for r in reasons)
    assert any("censored" in (r or "") for r in reasons)
    censored_entry = next(
        entry for entry in result.context if entry.observation_id == "h-censored"
    )
    assert censored_entry.censored is True
    assert censored_entry.lower_bound_seconds == 7200.0
    assert censored_entry.idle_seconds is None  # never coerced


def test_idle_handoff_finding_ids_are_deterministic_and_classifier_separated() -> None:
    first = ea.derive_handoff_finding_id(
        from_stage="finalize",
        to_stage="review",
        observation_identity="h-1",
    )
    second = ea.derive_handoff_finding_id(
        from_stage="finalize",
        to_stage="review",
        observation_identity="h-1",
    )
    other = ea.derive_handoff_finding_id(
        from_stage="finalize",
        to_stage="review",
        observation_identity="h-2",
    )
    other_classifier = ea.derive_handoff_finding_id(
        from_stage="finalize",
        to_stage="review",
        observation_identity="h-1",
        classifier_version="cls-v2",
    )
    assert first == second
    assert first != other
    assert first != other_classifier
    assert first.startswith("efficiency_handoff|")


def test_idle_handoffs_roundtrip_and_hash_canonically() -> None:
    handoff = _handoff(
        "h-1",
        idle_seconds=3600.0,
        accepted_outcome_id="outcome-1",
        active_custody=True,
    )
    result = ea.analyze_idle_handoffs([handoff])
    finding = result.findings[0]
    decoded = strict_loads(ec.IdleHandoffFinding, canonical_dumps(finding))
    assert decoded == finding
    assert canonical_digest(finding) == canonical_digest(decoded)


def test_repair_pattern_recurrence_reports_windows_without_claims() -> None:
    base = _ts(12)
    occurrences = [
        _repair_obs(
            "rep-1",
            occurred_at=_ts(12, 0),
            accepted_outcome_id="outcome-1",
            active_custody=True,
        ),
        _repair_obs(
            "rep-2",
            occurred_at=_ts(12, 15),
            accepted_outcome_id="outcome-2",
            active_custody=True,
        ),
        _repair_obs(
            "rep-3",
            occurred_at=_ts(12, 30),
            accepted_outcome_id="outcome-3",
        ),
    ]
    result = ea.analyze_repair_patterns(occurrences)
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.family == "repair_pattern"
    assert finding.affected_contract == "north_star_actions"
    assert finding.repair_signature == "gate-schema-failure"
    assert finding.recurrence_count == 3
    assert finding.recurrence_count_7d == 3
    assert finding.recurrence_count_30d == 3
    assert finding.recurrence_window_seconds == pytest.approx(1800.0)
    assert finding.first_occurred_at is not None
    assert finding.last_occurred_at is not None
    # SC16: recurrence is reported WITHOUT any avoidable-impact claim.
    assert finding.economics is None
    # SC16: active custody is reference-only.
    assert finding.references.active_custody_refs
    assert finding.references.active_custody_refs[0].owner == "repair_custody"
    assert len(finding.references.accepted_resolution_refs) == 3
    assert result.context == ()


def test_repair_pattern_singletons_and_unattributed_stay_context() -> None:
    singleton = _repair_obs(
        "rep-single",
        repair_signature="single-failure",
        occurred_at=_ts(12),
        accepted_outcome_id="outcome-1",
    )
    unattributed_group = [
        _repair_obs("rep-a1", occurred_at=_ts(11)),
        _repair_obs("rep-a2", occurred_at=_ts(12)),
    ]
    result = ea.analyze_repair_patterns([singleton, *unattributed_group])
    assert result.findings == ()
    assert len(result.context) == 3
    reasons = {entry.context_reason for entry in result.context}
    assert any("below recurrence threshold" in (r or "") for r in reasons)
    assert any("no exact accepted-resolution anchor" in (r or "") for r in reasons)


def test_repair_pattern_finding_ids_are_signature_based() -> None:
    first = ea.derive_repair_pattern_finding_id(
        affected_contract="north_star_actions",
        repair_signature="gate-schema-failure",
    )
    second = ea.derive_repair_pattern_finding_id(
        affected_contract="north_star_actions",
        repair_signature="gate-schema-failure",
    )
    other = ea.derive_repair_pattern_finding_id(
        affected_contract="north_star_actions",
        repair_signature="different-failure",
    )
    other_classifier = ea.derive_repair_pattern_finding_id(
        affected_contract="north_star_actions",
        repair_signature="gate-schema-failure",
        classifier_version="cls-v2",
    )
    assert first == second
    assert first != other
    assert first != other_classifier
    assert first.startswith("efficiency_repair_pattern|")


def test_repair_pattern_finding_never_carries_economics() -> None:
    # The contract forbids economics on repair-pattern findings (SC16).
    with pytest.raises(ValueError):
        ea.RepairPatternFinding(
            finding_id="efficiency_repair_pattern|" + "a" * 64,
            affected_contract="north_star_actions",
            repair_signature="gate-schema-failure",
            classifier_version="cls-v1",
            recurrence_count=2,
            recurrence_count_7d=2,
            recurrence_count_30d=2,
            references=ec.FindingReferences(
                accepted_resolution_refs=[_ref("run_authority", "decision://o")],
                source_refs=[_ref("wbc", "wbc://r")],
            ),
            economics=ec.AcceptedOutcomeEconomics(
                accepted_outcome_count=1,
                time_seconds_per_accepted=10.0,
            ),
        )


def test_repair_patterns_are_input_order_independent() -> None:
    occurrences = [
        _repair_obs("rep-1", occurred_at=_ts(11), accepted_outcome_id="o-1"),
        _repair_obs("rep-2", occurred_at=_ts(12), accepted_outcome_id="o-2"),
        _repair_obs("rep-3", occurred_at=_ts(13), accepted_outcome_id="o-3"),
        _repair_obs("rep-single", occurred_at=_ts(14), accepted_outcome_id="o-4"),
    ]
    forward = ea.analyze_repair_patterns(occurrences)
    backward = ea.analyze_repair_patterns(list(reversed(occurrences)))
    assert forward == backward
    assert canonical_digest(forward) == canonical_digest(backward)


def test_aggregate_exclusion_accounting_bounds_with_unknowns_and_exclusions() -> None:
    p95, median = _bounds(p95_upper=320.0, median_upper=140.0)
    dwell_avoidable = _dwell_obs(
        "gate-1",
        elapsed_seconds=600.0,
        accepted_outcome_id="outcome-1",
    )
    dwell_censored = _dwell_obs(
        "gate-2",
        censored=True,
        lower_bound_seconds=400.0,
        accepted_outcome_id="outcome-2",
    )
    dwell_excluded = _dwell_obs(
        "gate-3",
        elapsed_seconds=5000.0,
        accepted_outcome_id="outcome-3",
        excluded_reason=ea.DwellExclusionReason.HUMAN_GATE,
        human_gate=True,
    )
    dwell = ea.analyze_gate_dwell(
        [dwell_avoidable, dwell_censored, dwell_excluded], p95=p95, median=median
    )
    handoffs = ea.analyze_idle_handoffs(
        [
            _handoff("h-1", idle_seconds=3600.0, accepted_outcome_id="o-1"),
            _handoff(
                "h-2",
                idle_seconds=5000.0,
                accepted_outcome_id="o-2",
                excluded_reason=ea.DwellExclusionReason.PRODUCTIVE,
                productive=True,
            ),
        ]
    )
    bounds = ea.aggregate_exclusion_accounting(dwell=dwell, handoffs=handoffs)
    # Exact proven seconds (600 dwell + 3600 handoff) plus the censored
    # dwell leg's known floor (400) = 4600 lower bound.
    assert bounds.lower_bound_seconds == pytest.approx(4600.0)
    # The censored dwell leg marks the measure unknown: the finite upper
    # bound is unknown (never coerced).
    assert bounds.upper_bound_seconds is None
    assert bounds.unknown_count == 1
    # Typed exclusion accounting retains the excluded context (never in the
    # avoidable bounds).
    assert bounds.excluded_count == 2
    assert bounds.excluded_seconds == pytest.approx(10000.0)
    assert len(bounds.entries) == 2
    entry_map = {
        (entry.family, entry.reason.value): entry for entry in bounds.entries
    }
    assert entry_map[("dwell", "human_gate")].count == 1
    assert entry_map[("dwell", "human_gate")].retained_context_seconds == 5000.0
    assert entry_map[("idle_handoff", "productive")].count == 1
    assert entry_map[("idle_handoff", "productive")].retained_context_seconds == 5000.0


def test_aggregate_exclusion_accounting_exact_upper_when_no_unknowns() -> None:
    dwell = ea.analyze_gate_dwell(
        [
            _dwell_obs("gate-1", elapsed_seconds=600.0, accepted_outcome_id="o-1"),
        ],
        p95=ec.QuantileBounds(value=300.0, lower_bound=290.0, upper_bound=320.0),
        median=ec.QuantileBounds(value=120.0, lower_bound=110.0, upper_bound=140.0),
    )
    loops = ea.analyze_duplicate_calls(
        [
            _call(
                "call-1",
                duplicate_key="dup-key",
                accepted_outcome_id="o-1",
                elapsed_seconds=100.0,
            ),
            _call(
                "call-2",
                duplicate_key="dup-key",
                accepted_outcome_id="o-1",
                elapsed_seconds=100.0,
            ),
        ]
    )
    bounds = ea.aggregate_exclusion_accounting(dwell=dwell, loops=loops)
    assert bounds.lower_bound_seconds == pytest.approx(800.0)  # 600 + 200
    assert bounds.upper_bound_seconds == pytest.approx(800.0)
    assert bounds.unknown_count == 0
    assert bounds.excluded_count == 0
    assert bounds.entries == ()


def test_aggregate_exclusion_accounting_ignores_repair_pattern_claims() -> None:
    # Repair-pattern findings never carry economics, so they contribute
    # nothing to the avoidable-impact bounds.
    occurrences = [
        _repair_obs("rep-1", occurred_at=_ts(11), accepted_outcome_id="o-1"),
        _repair_obs("rep-2", occurred_at=_ts(12), accepted_outcome_id="o-2"),
    ]
    patterns = ea.analyze_repair_patterns(occurrences)
    bounds = ea.aggregate_exclusion_accounting(repair_patterns=patterns.findings)
    assert bounds.lower_bound_seconds == 0.0
    assert bounds.upper_bound_seconds == 0.0
    assert bounds.unknown_count == 0


def test_aggregate_exclusion_accounting_empty_inputs() -> None:
    bounds = ea.aggregate_exclusion_accounting()
    assert bounds.lower_bound_seconds == 0.0
    assert bounds.upper_bound_seconds == 0.0
    assert bounds.unknown_count == 0
    assert bounds.excluded_count == 0
    assert bounds.entries == ()

