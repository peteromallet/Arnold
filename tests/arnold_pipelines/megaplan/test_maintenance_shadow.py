"""Focused Maintenance shadow-comparison tests (M2, T14).

These tests prove the deterministic read-only shadow comparison API:

* every comparison row occupies exactly ONE of the six closed buckets
  (match, explained_difference, unexplained_difference, missing_denominator,
  stale_projection, would_block) with explicit envelope/projection digests,
  coverage denominator, derived coverage, and legacy hash;
* every uncertain or mismatched input — UNKNOWN/PARTIAL/INCOHERENT envelope
  states, stale/unknown freshness, cross-environment evidence, a stale
  projection, a projection source-digest mismatch, or a missing required
  denominator — is non-green and non-dispatchable (fail-closed);
* only a match on an eligible, agreeing envelope can carry green/dispatchable/
  terminal;
* the comparator exposes no mutation or dispatch method and is a pure function
  (same inputs -> same row digest).
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from arnold_pipelines.megaplan.maintenance.contracts import (
    CoherenceReason,
    CoherenceState,
    CompletenessState,
    FreshnessState,
    ObservationEnvelope,
    SourceVersionVector,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    canonical_dumps,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.shadow import (
    LegacyResult,
    SHADOW_BUCKETS,
    ShadowBucket,
    ShadowComparison,
    compare_shadow,
)

UTC = timezone.utc


def _ts() -> datetime:
    return datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _vector(owner: str, env: str, version: str) -> SourceVersionVector:
    return SourceVersionVector(
        owner=owner,
        source=owner,
        environment=EnvironmentId(env),
        before=version,
        after=version,
    )


def _eligible_envelope(*, green: bool = True) -> ObservationEnvelope:
    """A coherent/complete/fresh single-environment envelope."""
    if green:
        return ObservationEnvelope.build(
            observed_at=_ts(),
            environment="production",
            version_vectors=[
                _vector("run_authority", "production", "a" * 64),
                _vector("wbc", "production", "b" * 64),
            ],
            completeness=CompletenessState.COMPLETE,
            freshness=FreshnessState.FRESH,
            coherence=CoherenceState.COHERENT,
        )
    # Eligible states but deliberately non-promoting flags: allowed by direct
    # construction (only over-claims are rejected by the envelope contract).
    return ObservationEnvelope(
        schema_version=1,
        observed_at=_ts(),
        environment=EnvironmentId("production"),
        version_vectors=[
            _vector("run_authority", "production", "a" * 64),
            _vector("wbc", "production", "b" * 64),
        ],
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.FRESH,
        coherence=CoherenceState.COHERENT,
        coherence_reasons=(),
        terminal=False,
        green=False,
        dispatchable=False,
    )


def _incoherent_envelope(
    *,
    reasons: tuple[CoherenceReason, ...] = (CoherenceReason.UNKNOWN,),
    completeness: CompletenessState = CompletenessState.UNKNOWN,
    freshness: FreshnessState = FreshnessState.FRESH,
    cross_env: bool = False,
) -> ObservationEnvelope:
    vectors = [_vector("run_authority", "production", "a" * 64)]
    if cross_env:
        vectors.append(_vector("wbc", "staging", "b" * 64))
    return ObservationEnvelope.build(
        observed_at=_ts(),
        environment="production",
        version_vectors=vectors,
        completeness=completeness,
        freshness=freshness,
        coherence=CoherenceState.INCOHERENT,
        coherence_reasons=reasons,
    )


def _stale_envelope() -> ObservationEnvelope:
    return ObservationEnvelope.build(
        observed_at=_ts(),
        environment="production",
        version_vectors=[_vector("run_authority", "production", "a" * 64)],
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.STALE,
        coherence=CoherenceState.COHERENT,
    )


def _projection(
    *,
    freshness: str = "fresh",
    source_digest: str | None = "a" * 64,
    output_digest: str | None = "b" * 64,
    denominator: int | None = 100,
    covered_count: int | None = 87,
) -> SimpleNamespace:
    return SimpleNamespace(
        projection="efficiency_analysis",
        freshness=freshness,
        source_digest=source_digest,
        output_digest=output_digest,
        coverage_denominator=denominator,
        covered_count=covered_count,
    )


def _legacy(
    *,
    green: bool = True,
    dispatchable: bool = True,
    terminal: bool = True,
) -> dict[str, bool]:
    return {"green": green, "dispatchable": dispatchable, "terminal": terminal}


# ---------------------------------------------------------------------------
# Exactly-one-bucket matrix and fail-closed interpretation
# ---------------------------------------------------------------------------


def test_match_bucket_for_eligible_agreeing_verdict() -> None:
    row = compare_shadow(_legacy(), _eligible_envelope())
    assert row.bucket is ShadowBucket.MATCH
    assert row.reasons == ()
    assert row.envelope_eligible is True
    assert row.green is True and row.dispatchable is True and row.terminal is True
    assert len(row.envelope_digest) == 64
    assert len(row.legacy_hash) == 64


def test_match_bucket_for_eligible_non_promoting_verdict() -> None:
    row = compare_shadow(
        _legacy(green=False, dispatchable=False, terminal=False),
        _eligible_envelope(green=False),
    )
    assert row.bucket is ShadowBucket.MATCH
    assert row.green is False and row.dispatchable is False and row.terminal is False


def test_would_block_when_legacy_promotes_but_envelope_not_eligible() -> None:
    row = compare_shadow(_legacy(), _incoherent_envelope())
    assert row.bucket is ShadowBucket.WOULD_BLOCK
    assert "would_block" in row.reasons
    assert CoherenceReason.UNKNOWN.value in row.reasons
    assert row.green is False and row.dispatchable is False and row.terminal is False


def test_explained_difference_when_legacy_also_non_promoting() -> None:
    row = compare_shadow(
        _legacy(green=False, dispatchable=False, terminal=False),
        _incoherent_envelope(reasons=(CoherenceReason.CURSOR_GAP,)),
    )
    assert row.bucket is ShadowBucket.EXPLAINED_DIFFERENCE
    assert CoherenceReason.CURSOR_GAP.value in row.reasons
    assert row.green is False and row.dispatchable is False


def test_known_conservative_legacy_non_promotion_is_explained() -> None:
    # REVIEW-CHECK_SHADOW_BUCKET-001: a known conservative legacy non-promotion
    # against an eligible green envelope is a deterministic, typed difference —
    # it lands in explained_difference (never unexplained_difference) with an
    # explicit reason and stays non-green/non-dispatchable/non-terminal.
    row = compare_shadow(
        _legacy(green=False, dispatchable=False, terminal=False),
        _eligible_envelope(),
    )
    assert row.bucket is ShadowBucket.EXPLAINED_DIFFERENCE
    assert "legacy_conservative_non_promotion" in row.reasons
    assert row.envelope_eligible is True
    assert row.envelope_green is True
    assert row.digest_mismatch is False and row.stale_projection is False
    assert row.green is False and row.dispatchable is False and row.terminal is False


def test_unexplained_difference_remains_for_legacy_promotion_against_non_promoting_envelope() -> None:
    # A legacy verdict that promotes while the envelope is eligible but
    # explicitly non-promoting has no typed explanation: it stays
    # unexplained_difference with the verdict_disagreement reason and is
    # never green (the shadow never authorizes a promotion it cannot explain).
    row = compare_shadow(_legacy(), _eligible_envelope(green=False))
    assert row.bucket is ShadowBucket.UNEXPLAINED_DIFFERENCE
    assert "verdict_disagreement" in row.reasons
    assert row.green is False and row.dispatchable is False and row.terminal is False


def test_stale_projection_is_never_green() -> None:
    row = compare_shadow(
        _legacy(),
        _eligible_envelope(),
        projection=_projection(freshness="stale"),
    )
    assert row.bucket is ShadowBucket.STALE_PROJECTION
    assert row.stale_projection is True
    assert "stale_projection" in row.reasons
    assert row.green is False and row.dispatchable is False and row.terminal is False


def test_unknown_projection_freshness_is_treated_as_stale() -> None:
    row = compare_shadow(
        _legacy(),
        _eligible_envelope(),
        projection=_projection(freshness="unknown"),
    )
    assert row.bucket is ShadowBucket.STALE_PROJECTION
    assert row.green is False


def test_missing_denominator_bucket() -> None:
    row = compare_shadow(
        _legacy(),
        _eligible_envelope(),
        projection=_projection(denominator=None, covered_count=None),
        require_denominator=True,
    )
    assert row.bucket is ShadowBucket.MISSING_DENOMINATOR
    assert row.missing_denominator is True
    assert row.denominator is None and row.coverage is None
    assert "missing_denominator" in row.reasons
    assert row.green is False and row.dispatchable is False


def test_projection_digest_mismatch_is_unexplained_and_non_green() -> None:
    row = compare_shadow(
        _legacy(),
        _eligible_envelope(),
        projection=_projection(source_digest="d" * 64),
        expected_source_digest="e" * 64,
    )
    assert row.bucket is ShadowBucket.UNEXPLAINED_DIFFERENCE
    assert row.digest_mismatch is True
    assert "digest_mismatch" in row.reasons
    assert row.green is False and row.dispatchable is False


def test_missing_projection_with_expected_digest_is_a_digest_mismatch() -> None:
    row = compare_shadow(
        _legacy(), _eligible_envelope(), expected_source_digest="e" * 64
    )
    assert row.bucket is ShadowBucket.UNEXPLAINED_DIFFERENCE
    assert row.digest_mismatch is True
    assert row.green is False


@pytest.mark.parametrize(
    "envelope",
    [
        _incoherent_envelope(reasons=(CoherenceReason.MISSING_REQUIRED_SOURCE,)),
        _incoherent_envelope(
            reasons=(CoherenceReason.CROSS_ENVIRONMENT,), cross_env=True
        ),
        _incoherent_envelope(
            reasons=(CoherenceReason.STALE_SOURCE,),
            completeness=CompletenessState.COMPLETE,
            freshness=FreshnessState.STALE,
        ),
        _incoherent_envelope(
            reasons=(CoherenceReason.VERSION_TEAR,),
            completeness=CompletenessState.PARTIAL,
        ),
    ],
)
def test_uncertain_envelopes_are_never_green_or_dispatchable(envelope: ObservationEnvelope) -> None:
    promoting = compare_shadow(_legacy(), envelope)
    assert promoting.bucket is ShadowBucket.WOULD_BLOCK
    assert promoting.green is False and promoting.dispatchable is False
    non_promoting = compare_shadow(
        _legacy(green=False, dispatchable=False, terminal=False), envelope
    )
    assert non_promoting.bucket is ShadowBucket.EXPLAINED_DIFFERENCE
    assert non_promoting.green is False and non_promoting.dispatchable is False


def test_partial_and_unknown_and_stale_and_cross_env_all_fail_closed() -> None:
    partial = _incoherent_envelope(
        reasons=(CoherenceReason.MISSING_OPTIONAL_SOURCE,),
        completeness=CompletenessState.PARTIAL,
    )
    assert not compare_shadow(_legacy(), partial).green

    unknown = _incoherent_envelope(reasons=(CoherenceReason.UNKNOWN,))
    assert not compare_shadow(_legacy(), unknown).green

    stale = _stale_envelope()
    assert not compare_shadow(_legacy(), stale).green

    cross_env = _incoherent_envelope(
        reasons=(CoherenceReason.CROSS_ENVIRONMENT,), cross_env=True
    )
    row = compare_shadow(_legacy(), cross_env)
    assert row.cross_environment is True
    assert not row.green and not row.dispatchable


def test_denominator_coverage_and_digests_are_reported() -> None:
    row = compare_shadow(
        _legacy(),
        _eligible_envelope(),
        projection=_projection(denominator=100, covered_count=87),
        expected_source_digest="a" * 64,
    )
    assert row.bucket is ShadowBucket.MATCH
    assert row.denominator == 100
    assert row.covered_count == 87
    assert row.coverage == pytest.approx(0.87)
    assert row.projection_source_digest == "a" * 64
    assert row.projection_output_digest == "b" * 64
    assert row.projection_name == "efficiency_analysis"
    assert row.green is True and row.dispatchable is True


def test_zero_denominator_coverage_is_explicit_none() -> None:
    row = compare_shadow(
        _legacy(),
        _eligible_envelope(),
        projection=_projection(denominator=0, covered_count=0),
    )
    assert row.denominator == 0
    assert row.coverage is None


def test_legacy_hash_is_stable_and_envelope_digest_is_stable() -> None:
    legacy = LegacyResult(green=True, dispatchable=True, terminal=True)
    first = compare_shadow(legacy, _eligible_envelope())
    second = compare_shadow(
        {"green": True, "dispatchable": True, "terminal": True},
        _eligible_envelope(),
    )
    assert first.legacy_hash == second.legacy_hash
    assert len(first.legacy_hash) == 64
    assert first.envelope_digest == second.envelope_digest
    assert first.digest == second.digest  # pure function: same inputs -> same row


def test_every_row_occupies_exactly_one_bucket() -> None:
    envelopes = [
        _eligible_envelope(),
        _eligible_envelope(green=False),
        _incoherent_envelope(),
        _stale_envelope(),
    ]
    verdicts = [
        _legacy(),
        _legacy(green=False, dispatchable=False, terminal=False),
    ]
    projections = [
        None,
        _projection(),
        _projection(freshness="stale"),
        _projection(denominator=None, covered_count=None),
    ]
    seen_buckets: set[str] = set()
    for envelope in envelopes:
        for verdict in verdicts:
            for projection in projections:
                for require_denominator in (False, True):
                    row = compare_shadow(
                        verdict,
                        envelope,
                        projection=projection,
                        expected_source_digest="a" * 64,
                        require_denominator=require_denominator,
                    )
                    assert row.bucket.value in SHADOW_BUCKETS
                    assert row.bucket.value not in (
                        "green",
                        "dispatchable",
                        "terminal",
                    )
                    seen_buckets.add(row.bucket.value)
                    if row.bucket is not ShadowBucket.MATCH:
                        assert row.green is False
                        assert row.dispatchable is False
                        assert row.terminal is False
    # Every one of the six buckets is reachable by the matrix.
    assert seen_buckets == set(SHADOW_BUCKETS)


# ---------------------------------------------------------------------------
# Strictness, round-trip, and the no-mutation/no-dispatch surface
# ---------------------------------------------------------------------------


def test_legacy_result_is_strict_and_non_coercing() -> None:
    with pytest.raises(ValueError):
        LegacyResult(green="yes", dispatchable=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        LegacyResult(green=True, dispatchable=True, unknown_field=1)  # type: ignore[call-arg]


def test_canonical_round_trip_of_comparison_row() -> None:
    row = compare_shadow(_legacy(), _eligible_envelope())
    decoded = strict_loads(ShadowComparison, canonical_dumps(row))
    assert decoded == row
    assert decoded.digest == row.digest


def test_unknown_field_on_comparison_row_is_rejected() -> None:
    with pytest.raises(Exception):
        strict_loads(ShadowComparison, {"bucket": "match", "unknown_key": 1})


def test_no_mutation_or_dispatch_surface() -> None:
    row = compare_shadow(_legacy(), _eligible_envelope())
    for name in ("apply", "dispatch", "append", "write", "mutate", "execute", "transition", "enqueue"):
        assert not hasattr(row, name)
        assert not hasattr(ShadowComparison, name)
        assert not hasattr(compare_shadow, name)
    import arnold_pipelines.megaplan.maintenance.shadow as shadow_module

    for name in ("dispatch", "apply", "write_plan_state", "save_chain_state", "TransitionWriter"):
        assert not hasattr(shadow_module, name)


def test_bucket_consistency_violations_are_rejected() -> None:
    # A stale projection forced out of its bucket must be rejected.
    stale = _projection(freshness="stale")
    row = compare_shadow(_legacy(), _eligible_envelope(), projection=stale)
    assert row.bucket is ShadowBucket.STALE_PROJECTION
    # A row claiming green while the envelope is not eligible must be rejected.
    with pytest.raises(ValueError):
        ShadowComparison(
            schema_version=1,
            bucket=ShadowBucket.MATCH,
            reasons=(),
            legacy_green=True,
            legacy_dispatchable=True,
            legacy_terminal=True,
            envelope_eligible=False,
            envelope_green=False,
            envelope_dispatchable=False,
            envelope_terminal=False,
            cross_environment=False,
            green=True,
            dispatchable=True,
            terminal=True,
            envelope_digest="a" * 64,
            legacy_hash="b" * 64,
        )
