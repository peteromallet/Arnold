"""Focused proof tests for M5 root-cause clustering (Plan Step 18 / T18).

Proves the pure clustering module:

* clustering is input-order independent — shuffling evidence never changes
  fingerprints, recurrence counts, coverage, confidence, or output ordering;
* clustering is classifier-version separated — the same contract and feature
  set under different classifier versions NEVER merge;
* clustering is contract-specific — superficially similar evidence on
  different affected contracts NEVER merges;
* candidates are gated by the locked recurrence signal (2-in-7 OR 3-in-30
  over timestamped occurrences); below-signal groups and singletons stay
  typed context rows (report findings, never proposals);
* late occurrences re-derive the SAME root-cause fingerprint and candidate
  identity with advanced recurrence counts (deterministic correction basis);
* every candidate carries deterministic alternatives, an exact evidence
  coverage denominator, conservative confidence bounds (unknown ceiling under
  censoring), reference-only active custody, and denominator-gated
  avoidable-impact economics over the exact accepted-outcome count;
* candidates are strict Step 3 contracts that canonical-hash and strict-decode.

The module consumes pure :class:`ClusterEvidence` facts and never constructs
or mutates an owner store.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from arnold_pipelines.megaplan.maintenance import efficiency_clustering as cl
from arnold_pipelines.megaplan.maintenance import efficiency_contracts as ec
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    canonical_dumps,
    strict_loads,
)

UTC = timezone.utc

_BASE_DAY = datetime(2026, 8, 10, tzinfo=UTC)


def _ts(day_offset: int, hour: int = 12) -> datetime:
    return _BASE_DAY + timedelta(days=day_offset, hours=hour)


def _ref(owner: str, locator: str, identity: str | None = None) -> OwnerRef:
    return OwnerRef(owner=owner, locator=locator, identity=identity, digest="a" * 64)


def _evidence(
    evidence_id: str,
    *,
    affected_contract: str = "ac-1",
    classifier_version: str = "cls-v1",
    evidence_features: tuple[str, ...] = ("gate", "schema_failure"),
    occurred_at: datetime | None = None,
    accepted_outcome_id: str | None = None,
    time_seconds: float | None = None,
    censored: bool = False,
    custody: bool = False,
    **overrides: object,
) -> cl.ClusterEvidence:
    refs = [_ref("wbc", f"wbc://{evidence_id}")]
    accepted_refs = (
        [_ref("run_authority", f"decision://{accepted_outcome_id}")]
        if accepted_outcome_id is not None
        else []
    )
    custody_refs = [_ref("custody", f"custody://{evidence_id}")] if custody else []
    censoring_refs = [_ref("wbc", f"wbc://{evidence_id}/censor")] if censored else []
    base: dict[str, object] = {
        "evidence_id": evidence_id,
        "affected_contract": affected_contract,
        "classifier_version": classifier_version,
        "evidence_features": evidence_features,
        "occurred_at": occurred_at,
        "accepted_outcome_id": accepted_outcome_id,
        "time_seconds": time_seconds,
        "censored": censored,
        "refs": refs,
        "accepted_resolution_refs": accepted_refs,
        "active_custody_refs": custody_refs,
        "censoring_refs": censoring_refs,
    }
    base.update(overrides)
    return cl.ClusterEvidence(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ClusterEvidence contract discipline
# ---------------------------------------------------------------------------


def test_cluster_evidence_requires_source_refs() -> None:
    with pytest.raises(ValueError):
        cl.ClusterEvidence(
            evidence_id="ev-1",
            affected_contract="ac-1",
            classifier_version="cls-v1",
            refs=[],
        )


def test_cluster_evidence_attribution_requires_resolution_refs() -> None:
    with pytest.raises(ValueError):
        cl.ClusterEvidence(
            evidence_id="ev-1",
            affected_contract="ac-1",
            classifier_version="cls-v1",
            accepted_outcome_id="outcome-1",
            refs=[_ref("wbc", "wbc://ev-1")],
            accepted_resolution_refs=[],
        )


def test_cluster_evidence_features_are_sorted_and_deduped() -> None:
    item = cl.ClusterEvidence(
        evidence_id="ev-1",
        affected_contract="ac-1",
        classifier_version="cls-v1",
        evidence_features=("schema_failure", "gate", "gate"),
        refs=[_ref("wbc", "wbc://ev-1")],
    )
    assert item.evidence_features == ("gate", "schema_failure")


# ---------------------------------------------------------------------------
# Fingerprint / identity derivations
# ---------------------------------------------------------------------------


def test_root_cause_fingerprint_is_deterministic_and_feature_order_independent() -> None:
    features_a = ("gate", "schema_failure", "north_star_actions")
    features_b = ("north_star_actions", "gate", "schema_failure")
    fp_a = cl.derive_root_cause_fingerprint(
        affected_contract="ac-1", evidence_features=features_a, classifier_version="cls-v1"
    )
    fp_b = cl.derive_root_cause_fingerprint(
        affected_contract="ac-1", evidence_features=features_b, classifier_version="cls-v1"
    )
    assert fp_a == fp_b
    assert len(fp_a) == 64


def test_root_cause_fingerprint_separates_contract_and_classifier() -> None:
    base = dict(
        affected_contract="ac-1",
        evidence_features=("gate", "schema_failure"),
        classifier_version="cls-v1",
    )
    fp = cl.derive_root_cause_fingerprint(**base)  # type: ignore[arg-type]
    assert cl.derive_root_cause_fingerprint(
        affected_contract="ac-2",
        evidence_features=base["evidence_features"],  # type: ignore[arg-type]
        classifier_version=base["classifier_version"],  # type: ignore[arg-type]
    ) != fp
    assert cl.derive_root_cause_fingerprint(
        affected_contract=base["affected_contract"],  # type: ignore[arg-type]
        evidence_features=("other", "features"),
        classifier_version=base["classifier_version"],  # type: ignore[arg-type]
    ) != fp
    assert cl.derive_root_cause_fingerprint(
        affected_contract=base["affected_contract"],  # type: ignore[arg-type]
        evidence_features=base["evidence_features"],  # type: ignore[arg-type]
        classifier_version="cls-v2",
    ) != fp


def test_candidate_id_is_deterministic_and_prefixed() -> None:
    fp = cl.derive_root_cause_fingerprint(
        affected_contract="ac-1", evidence_features=("gate",), classifier_version="cls-v1"
    )
    candidate_id = cl.derive_candidate_id(fp)
    assert candidate_id == f"efficiency_root_cause|{fp}"
    assert candidate_id == cl.derive_candidate_id(fp)


# ---------------------------------------------------------------------------
# Recurrence signal (2-in-7 OR 3-in-30)
# ---------------------------------------------------------------------------


def test_recurrence_signal_2_in_7() -> None:
    assert cl.recurrence_signal_satisfied(recurrence_count_7d=2, recurrence_count_30d=2)
    assert cl.recurrence_signal_satisfied(recurrence_count_7d=2, recurrence_count_30d=1)


def test_recurrence_signal_3_in_30_without_2_in_7() -> None:
    # Three occurrences spread over 16 days (0, 8, 16): no 7-day window
    # holds two, but a 30-day window holds all three.
    evidence = [
        _evidence("ev-1", occurred_at=_ts(0)),
        _evidence("ev-2", occurred_at=_ts(8)),
        _evidence("ev-3", occurred_at=_ts(16)),
    ]
    result = cl.cluster_root_causes(evidence)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.recurrence_count_7d == 1
    assert candidate.recurrence_count_30d == 3
    assert cl.recurrence_signal_satisfied(
        recurrence_count_7d=candidate.recurrence_count_7d,
        recurrence_count_30d=candidate.recurrence_count_30d,
    )


def test_recurrence_signal_not_satisfied_for_sparse_pair() -> None:
    # Two occurrences 10 days apart satisfy neither 2-in-7 nor 3-in-30.
    evidence = [
        _evidence("ev-1", occurred_at=_ts(0)),
        _evidence("ev-2", occurred_at=_ts(10)),
    ]
    result = cl.cluster_root_causes(evidence)
    assert result.candidates == ()
    assert len(result.context) == 2
    assert all("recurrence signal" in entry.context_reason for entry in result.context)


def test_recurrence_signal_not_satisfied_for_three_over_40_days() -> None:
    evidence = [
        _evidence("ev-1", occurred_at=_ts(0)),
        _evidence("ev-2", occurred_at=_ts(20)),
        _evidence("ev-3", occurred_at=_ts(40)),
    ]
    result = cl.cluster_root_causes(evidence)
    assert result.candidates == ()
    assert len(result.context) == 3


def test_recurrence_counts_find_any_7_day_window() -> None:
    # 2-in-7 holds even though the latest occurrence is not inside the pair:
    # occurrences at days 0 and 6 form a 7-day window, the latest is day 20.
    evidence = [
        _evidence("ev-1", occurred_at=_ts(0)),
        _evidence("ev-2", occurred_at=_ts(6)),
        _evidence("ev-3", occurred_at=_ts(20)),
    ]
    result = cl.cluster_root_causes(evidence)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.recurrence_count_7d >= 2
    assert cl.recurrence_signal_satisfied(
        recurrence_count_7d=candidate.recurrence_count_7d,
        recurrence_count_30d=candidate.recurrence_count_30d,
    )


# ---------------------------------------------------------------------------
# Input-order independence
# ---------------------------------------------------------------------------


def test_clustering_is_input_order_independent() -> None:
    evidence = [
        _evidence("ev-1", affected_contract="ac-1", occurred_at=_ts(0),
                  accepted_outcome_id="outcome-1", time_seconds=120.0),
        _evidence("ev-2", affected_contract="ac-1", occurred_at=_ts(1),
                  accepted_outcome_id="outcome-1", time_seconds=90.0),
        _evidence("ev-3", affected_contract="ac-1", occurred_at=_ts(2),
                  accepted_outcome_id="outcome-2", time_seconds=200.0),
        _evidence("ev-4", affected_contract="ac-2", occurred_at=_ts(0),
                  accepted_outcome_id="outcome-3", time_seconds=50.0),
        _evidence("ev-5", affected_contract="ac-2", occurred_at=_ts(1),
                  accepted_outcome_id="outcome-3", time_seconds=60.0),
    ]
    shuffled = [
        evidence[3], evidence[0], evidence[4], evidence[2], evidence[1],
    ]
    first = cl.cluster_root_causes(evidence)
    second = cl.cluster_root_causes(shuffled)
    assert first == second
    assert [candidate.candidate_id for candidate in first.candidates] == [
        candidate.candidate_id for candidate in second.candidates
    ]
    # Reference groups inside candidates are canonical-sorted too.
    for candidate in first.candidates:
        assert candidate.occurrence_refs == tuple(
            sorted(
                candidate.occurrence_refs,
                key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
            )
        )


# ---------------------------------------------------------------------------
# Classifier-version separation and contract-specific non-merging
# ---------------------------------------------------------------------------


def test_classifier_versions_never_merge() -> None:
    evidence = [
        _evidence("ev-1", classifier_version="cls-v1", occurred_at=_ts(0)),
        _evidence("ev-2", classifier_version="cls-v1", occurred_at=_ts(1)),
        _evidence("ev-3", classifier_version="cls-v2", occurred_at=_ts(0)),
        _evidence("ev-4", classifier_version="cls-v2", occurred_at=_ts(1)),
    ]
    result = cl.cluster_root_causes(evidence)
    assert len(result.candidates) == 2
    fingerprints = {candidate.root_cause_fingerprint for candidate in result.candidates}
    assert len(fingerprints) == 2
    by_classifier = {
        candidate.classifier_version: candidate for candidate in result.candidates
    }
    assert set(by_classifier) == {"cls-v1", "cls-v2"}
    assert (
        by_classifier["cls-v1"].root_cause_fingerprint
        != by_classifier["cls-v2"].root_cause_fingerprint
    )


def test_contract_distinct_failures_never_merge() -> None:
    # Identical features on different contracts stay separate candidates.
    evidence = [
        _evidence("ev-1", affected_contract="ac-1", occurred_at=_ts(0)),
        _evidence("ev-2", affected_contract="ac-1", occurred_at=_ts(1)),
        _evidence("ev-3", affected_contract="ac-2", occurred_at=_ts(0)),
        _evidence("ev-4", affected_contract="ac-2", occurred_at=_ts(1)),
    ]
    result = cl.cluster_root_causes(evidence)
    assert len(result.candidates) == 2
    assert {candidate.affected_contract for candidate in result.candidates} == {"ac-1", "ac-2"}
    # And the superficially similar pair does NOT appear as a merged candidate.
    assert all(candidate.recurrence_count_7d == 2 for candidate in result.candidates)
    fp_a = next(c for c in result.candidates if c.affected_contract == "ac-1")
    fp_b = next(c for c in result.candidates if c.affected_contract == "ac-2")
    assert fp_a.root_cause_fingerprint != fp_b.root_cause_fingerprint


# ---------------------------------------------------------------------------
# Late-occurrence deterministic correction behavior
# ---------------------------------------------------------------------------


def test_late_occurrence_keeps_fingerprint_and_advances_counts() -> None:
    early = [
        _evidence("ev-1", occurred_at=_ts(0), accepted_outcome_id="outcome-1"),
        _evidence("ev-2", occurred_at=_ts(1), accepted_outcome_id="outcome-1"),
    ]
    result_early = cl.cluster_root_causes(early)
    assert len(result_early.candidates) == 1
    early_candidate = result_early.candidates[0]

    late = early + [
        _evidence("ev-3", occurred_at=_ts(2), accepted_outcome_id="outcome-2"),
    ]
    result_late = cl.cluster_root_causes(late)
    assert len(result_late.candidates) == 1
    late_candidate = result_late.candidates[0]

    # The root-cause identity NEVER changes when late evidence arrives.
    assert late_candidate.root_cause_fingerprint == early_candidate.root_cause_fingerprint
    assert late_candidate.candidate_id == early_candidate.candidate_id
    # Recurrence counts and the evidence basis advance deterministically.
    assert late_candidate.recurrence_count_30d >= early_candidate.recurrence_count_30d
    assert late_candidate.coverage.numerator > early_candidate.coverage.numerator
    assert late_candidate.avoidable_impact is not None
    assert late_candidate.avoidable_impact.accepted_outcome_count == 2


# ---------------------------------------------------------------------------
# Candidate payload semantics
# ---------------------------------------------------------------------------


def test_candidate_carries_alternatives_from_other_contract_signatures() -> None:
    evidence = [
        _evidence("ev-1", affected_contract="ac-1",
                  evidence_features=("gate", "schema_failure"), occurred_at=_ts(0)),
        _evidence("ev-2", affected_contract="ac-1",
                  evidence_features=("gate", "schema_failure"), occurred_at=_ts(1)),
        _evidence("ev-3", affected_contract="ac-1",
                  evidence_features=("gate", "timeout"), occurred_at=_ts(0)),
        _evidence("ev-4", affected_contract="ac-1",
                  evidence_features=("gate", "timeout"), occurred_at=_ts(1)),
    ]
    result = cl.cluster_root_causes(evidence)
    assert len(result.candidates) == 2
    for candidate in result.candidates:
        assert len(candidate.alternatives) == 1
        alternative = candidate.alternatives[0]
        assert alternative.alternative_id != f"root_cause_alt|{candidate.root_cause_fingerprint}"
        # The alternative is the OTHER signature on the same contract.
        other = next(c for c in result.candidates if c.candidate_id != candidate.candidate_id)
        assert alternative.alternative_id == f"root_cause_alt|{other.root_cause_fingerprint}"
        assert alternative.evidence_refs


def test_candidate_coverage_uses_contract_total_with_unknowns() -> None:
    evidence = [
        _evidence("ev-1", affected_contract="ac-1", occurred_at=_ts(0)),
        _evidence("ev-2", affected_contract="ac-1", occurred_at=_ts(1)),
        # Featureless evidence on the same contract stays unknown, never clustered.
        _evidence("ev-3", affected_contract="ac-1", evidence_features=(), occurred_at=_ts(2)),
    ]
    result = cl.cluster_root_causes(evidence)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.coverage.metric == "evidence_coverage"
    assert candidate.coverage.numerator == 2
    assert candidate.coverage.denominator == 3
    assert candidate.coverage.unknown_count == 1
    # The featureless evidence is retained as typed context.
    assert any(entry.evidence_id == "ev-3" for entry in result.context)


def test_candidate_confidence_is_conservative_under_censoring() -> None:
    supported = [
        _evidence("ev-1", occurred_at=_ts(0), accepted_outcome_id="outcome-1"),
        _evidence("ev-2", occurred_at=_ts(1), accepted_outcome_id="outcome-1"),
    ]
    result = cl.cluster_root_causes(supported)
    candidate = result.candidates[0]
    assert candidate.confidence.value == 1.0
    assert candidate.confidence.upper_bound == 1.0

    censored = [
        _evidence("ev-1", occurred_at=_ts(0), accepted_outcome_id="outcome-1"),
        _evidence("ev-2", occurred_at=_ts(1), accepted_outcome_id="outcome-1"),
        _evidence("ev-3", occurred_at=_ts(2), censored=True),
    ]
    result = cl.cluster_root_causes(censored)
    candidate = result.candidates[0]
    assert candidate.confidence.value == round(2 / 3, 6)
    assert candidate.confidence.lower_bound == candidate.confidence.value
    assert candidate.confidence.upper_bound is None  # unknown ceiling


def test_candidate_avoidable_impact_is_denominator_gated() -> None:
    # No exact accepted outcome -> no economics claim at all.
    unattributed = [
        _evidence("ev-1", occurred_at=_ts(0)),
        _evidence("ev-2", occurred_at=_ts(1)),
    ]
    result = cl.cluster_root_causes(unattributed)
    assert len(result.candidates) == 1
    assert result.candidates[0].avoidable_impact is None

    # Exact accepted outcomes -> per-accepted time over the exact denominator.
    attributed = [
        _evidence("ev-1", occurred_at=_ts(0), accepted_outcome_id="outcome-1",
                  time_seconds=120.0),
        _evidence("ev-2", occurred_at=_ts(1), accepted_outcome_id="outcome-1",
                  time_seconds=180.0),
        _evidence("ev-3", occurred_at=_ts(2), accepted_outcome_id="outcome-2",
                  time_seconds=300.0),
    ]
    result = cl.cluster_root_causes(attributed)
    assert len(result.candidates) == 1
    economics = result.candidates[0].avoidable_impact
    assert economics is not None
    assert economics.accepted_outcome_count == 2
    assert economics.time_seconds_per_accepted == round((120 + 180 + 300) / 2, 6)


def test_candidate_active_custody_is_reference_only() -> None:
    evidence = [
        _evidence("ev-1", occurred_at=_ts(0), custody=True),
        _evidence("ev-2", occurred_at=_ts(1), custody=True),
    ]
    result = cl.cluster_root_causes(evidence)
    candidate = result.candidates[0]
    assert candidate.active_custody_refs
    assert all(ref.owner == "custody" for ref in candidate.active_custody_refs)
    # Custody appears nowhere except the reference bundle.
    assert all(
        ref.owner != "custody" for ref in candidate.occurrence_refs + candidate.evidence_refs
    )


# ---------------------------------------------------------------------------
# Contract discipline of the emitted candidates
# ---------------------------------------------------------------------------


def test_candidates_strict_decode_and_hash_canonically() -> None:
    evidence = [
        _evidence("ev-1", occurred_at=_ts(0), accepted_outcome_id="outcome-1",
                  time_seconds=90.0),
        _evidence("ev-2", occurred_at=_ts(1), accepted_outcome_id="outcome-1",
                  time_seconds=110.0),
        _evidence("ev-3", affected_contract="ac-2", occurred_at=_ts(0)),
        _evidence("ev-4", affected_contract="ac-2", occurred_at=_ts(1)),
    ]
    result = cl.cluster_root_causes(evidence)
    assert len(result.candidates) == 2
    for candidate in result.candidates:
        decoded = strict_loads(ec.RootCauseCandidate, canonical_dumps(candidate))
        assert decoded == candidate
        assert canonical_dumps(decoded) == canonical_dumps(candidate)


def test_empty_evidence_yields_empty_result() -> None:
    result = cl.cluster_root_causes([])
    assert result.candidates == ()
    assert result.context == ()