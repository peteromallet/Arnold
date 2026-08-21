"""Focused proof tests for the M4 operational policy and classifier (T1/T2).

Covers Plan Step 1 (typed stage policy, cohort identity, comparable-sample
facts, suppressors, observation facts, and decisions; strict decoding; the
29/30-sample and 4/5-plan cold-start boundaries; explicit
``action_policy_approved`` behavior; reference-only package exports) and Plan
Step 2 (expired-policy, no-live-call-or-lease, no-material-delta, and
second-coherent-observation predicates; repetition rules; stage and
no-progress handling; UNKNOWN/INCOHERENT outcomes; every locked suppressor;
censored metrics; and the WBC gate timeline fixture).

Fail-closed invariants proven here:

* strict decoding rejects unknown fields, missing required fields, and
  over-claimed dispatch/green state;
* cohort isolation is exact-match only — nothing is aliased or inferred;
* missing and censored denominators are preserved explicitly and never become
  zero or green;
* adaptive median/MAD/p95 values are report-only until 30 completed
  comparable samples from five plans AND explicit approval all hold;
* stale, torn, identity-mismatched, live-call, live-lease, improving-quality,
  long-phase, backoff, external-gate, and single-observation cases can never
  become dispatchable.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.maintenance import (
    M4_API,
    BlockKind,
    CLASSIFIER_VERSION,
    CohortIdentity,
    ComparableSampleFacts,
    DecisionOutcome,
    DeltaKind,
    MIN_ADAPTIVE_PLANS,
    MIN_ADAPTIVE_SAMPLES,
    ObservationFacts,
    OperationalDecision,
    ReportOnlyReason,
    StagePolicy,
    SuppressorReason,
    adaptive_action_eligible,
    adaptive_values_report_only,
    canonical_digest,
    canonical_dumps,
    classify_stall,
    cohort_matches,
    strict_loads,
    suppressors_for,
)
from arnold_pipelines.megaplan.maintenance.contracts import (
    CoherenceState,
    CompletenessState,
    FreshnessState,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    EventWindow,
    MaintenanceCodecError,
    ModelId,
    ProfileId,
    RunId,
    StageId,
    UtcTime,
)
from arnold_pipelines.megaplan.maintenance.operational_policy import (
    evidence_coherent,
    has_material_delta,
    no_progress_met,
    policy_is_expired,
    repetition_met,
    slo_expired,
)

UTC = timezone.utc

#: Owner stores / seams Maintenance domain modules must never import or
#: instantiate (mutation orchestration stays in the cloud adapter).
_FORBIDDEN_OWNER_IMPORTS = (
    "lease_store",
    "action_validator",
    "attempt_ledger_store",
    "repair_requests",
    "simple_fixer",
    "completion_engine",
    "transition_writer",
    "repair_queue",
    "controlled_writers",
)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _ts(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 18, hour, minute, tzinfo=UTC)


def _policy(
    *,
    approved: bool = False,
    expires_at: datetime | None = None,
    stage: str = "wbc_gate",
    version: str = "policy-v1",
    timeout_seconds: int = 3600,
    lateness_seconds: int = 300,
) -> StagePolicy:
    return StagePolicy(
        stage=StageId(stage),
        policy_version=version,
        declared_timeout_seconds=timeout_seconds,
        declared_slo_expires_at=UtcTime(expires_at if expires_at is not None else _ts(15, 30)),
        allowed_lateness_seconds=lateness_seconds,
        action_policy_approved=approved,
    )


def _facts(
    *,
    observed_at: datetime,
    coherence: CoherenceState = CoherenceState.COHERENT,
    completeness: CompletenessState = CompletenessState.COMPLETE,
    freshness: FreshnessState = FreshnessState.FRESH,
    block_kind: BlockKind = BlockKind.GATE_FINALIZE_REVIEW,
    fingerprint: str | None = "north_star_actions:repeated",
    equivalent_failures: int = 0,
    retry_revision_cycles: int = 0,
    same_fingerprint: bool = False,
    live_call: bool = False,
    live_lease: bool = False,
    material_deltas: tuple[DeltaKind, ...] = (),
    no_progress_cost_increasing: bool = False,
    cohort_agrees: bool = True,
    second_coherent_observation: bool = False,
    cross_environment: bool = False,
    identity_mismatch: bool = False,
    torn: bool = False,
    backoff_or_fallback: bool = False,
    unmatched_fresh_call_start: bool = False,
    declared_long_phase: bool = False,
    thorough_or_extreme_robustness: bool = False,
    external_pr_human_quota_gate: bool = False,
    improving_quality: bool = False,
    censored_metric_names: tuple[str, ...] = (),
    cohort: CohortIdentity | None = None,
    window: EventWindow | None = None,
) -> ObservationFacts:
    return ObservationFacts(
        observed_at=UtcTime(observed_at),
        window=window,
        cohort=cohort,
        block_kind=block_kind,
        coherence=coherence,
        completeness=completeness,
        freshness=freshness,
        cross_environment=cross_environment,
        identity_mismatch=identity_mismatch,
        torn=torn,
        fingerprint=fingerprint,
        equivalent_failures=equivalent_failures,
        retry_revision_cycles=retry_revision_cycles,
        same_fingerprint=same_fingerprint,
        live_call=live_call,
        live_lease=live_lease,
        material_deltas=material_deltas,
        no_progress_cost_increasing=no_progress_cost_increasing,
        cohort_agrees=cohort_agrees,
        second_coherent_observation=second_coherent_observation,
        backoff_or_fallback=backoff_or_fallback,
        unmatched_fresh_call_start=unmatched_fresh_call_start,
        declared_long_phase=declared_long_phase,
        thorough_or_extreme_robustness=thorough_or_extreme_robustness,
        external_pr_human_quota_gate=external_pr_human_quota_gate,
        improving_quality=improving_quality,
        censored_metric_names=censored_metric_names,
    )


def _samples(
    *,
    completed: int = 30,
    plans: int = 5,
    denominator: int | None = 30,
    censored: int = 0,
    unknown: int = 0,
) -> ComparableSampleFacts:
    return ComparableSampleFacts(
        completed_comparable_samples=completed,
        distinct_plans=plans,
        denominator=denominator,
        censored_samples=censored,
        unknown_samples=unknown,
        median_seconds=120.0,
        mad_seconds=8.0,
        p95_seconds=300.0,
    )


def _stall_shaped(
    *,
    observed_at: datetime,
    second_coherent_observation: bool = True,
    equivalent_failures: int = 3,
    **kwargs,
) -> ObservationFacts:
    """A coherent observation that would be a stall if not suppressed."""
    return _facts(
        observed_at=observed_at,
        second_coherent_observation=second_coherent_observation,
        equivalent_failures=equivalent_failures,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# T1 — Step 1 contracts: strict decoding and the reference/policy surface
# ---------------------------------------------------------------------------


def test_stage_policy_defaults_to_non_authorizing_and_round_trips() -> None:
    policy = _policy()
    # SD3: production action is default-off — approval must be explicit.
    assert policy.action_policy_approved is False
    assert policy.allowed_lateness_seconds == 300
    decoded = strict_loads(StagePolicy, canonical_dumps(policy))
    assert decoded == policy
    assert canonical_digest(decoded) == canonical_digest(policy)
    # An explicitly approved policy round-trips with approval preserved.
    approved = _policy(approved=True)
    assert approved.action_policy_approved is True
    assert strict_loads(StagePolicy, canonical_dumps(approved)) == approved


def test_stage_policy_strict_decode_rejects_unknown_and_missing_fields() -> None:
    payload = canonical_dumps(_policy())
    with pytest.raises(MaintenanceCodecError, match="strict decode failed"):
        strict_loads(StagePolicy, payload.replace('"policy_version"', '"bogus_field"'))
    with pytest.raises(MaintenanceCodecError, match="strict decode failed"):
        strict_loads(
            StagePolicy,
            '{"stage": "s1", "declared_timeout_seconds": 300, '
            '"declared_slo_expires_at": "2026-08-18T15:30:00Z"}',
        )


def test_cohort_identity_isolation_is_exact_match() -> None:
    base = CohortIdentity(
        run=RunId("run-1"),
        stage=StageId("stage-1"),
        profile=ProfileId("profile-1"),
        model=ModelId("model-1"),
        environment=EnvironmentId("production"),
    )
    assert cohort_matches(base, CohortIdentity(**base.model_dump())) is True
    # Every dimension is exact-match: a mismatch on any dimension isolates.
    assert cohort_matches(base, CohortIdentity(run=RunId("run-2"), stage=StageId("stage-1"))) is False
    assert cohort_matches(base, CohortIdentity(run=RunId("run-1"), stage=StageId("stage-2"))) is False
    assert (
        cohort_matches(
            base,
            CohortIdentity(
                run=RunId("run-1"),
                stage=StageId("stage-1"),
                profile=ProfileId("profile-2"),
            ),
        )
        is False
    )
    assert (
        cohort_matches(
            base,
            CohortIdentity(
                run=RunId("run-1"),
                stage=StageId("stage-1"),
                profile=ProfileId("profile-1"),
                model=ModelId("model-2"),
            ),
        )
        is False
    )
    assert (
        cohort_matches(
            base,
            CohortIdentity(
                run=RunId("run-1"),
                stage=StageId("stage-1"),
                profile=ProfileId("profile-1"),
                model=ModelId("model-1"),
                environment=EnvironmentId("staging"),
            ),
        )
        is False
    )
    # An absent dimension never matches a present one (nothing is inferred).
    assert cohort_matches(base, CohortIdentity(run=RunId("run-1"))) is False
    # A missing cohort never matches anything.
    assert cohort_matches(base, None) is False
    # Two explicitly empty cohorts match exactly.
    assert cohort_matches(CohortIdentity(), CohortIdentity()) is True


def test_comparable_sample_facts_preserve_missing_and_censored_denominators() -> None:
    missing = _samples(completed=10, denominator=None)
    # Missing denominator is explicit and round-trips as a preserved null.
    assert missing.missing_denominator is True
    assert missing.denominator is None
    decoded = strict_loads(ComparableSampleFacts, canonical_dumps(missing))
    assert decoded.denominator is None
    assert decoded.missing_denominator is True
    # Never inferred: a missing denominator yields an explicit None rate,
    # never a zero or green signal.
    assert decoded.completion_rate() is None
    # A zero denominator is also never a zero coverage rate.
    assert _samples(completed=0, denominator=0).completion_rate() is None
    # Censored and unknown samples are retained, never dropped or promoted.
    censored = _samples(completed=12, denominator=20, censored=5, unknown=3)
    assert censored.censored_samples == 5
    assert censored.unknown_samples == 3
    assert censored.completion_rate() == pytest.approx(0.6)
    round_tripped = strict_loads(ComparableSampleFacts, canonical_dumps(censored))
    assert round_tripped.censored_samples == 5
    assert round_tripped.unknown_samples == 3
    assert round_tripped.median_seconds == 120.0
    # Negative counts are rejected at construction and at strict decode.
    with pytest.raises(ValueError):
        ComparableSampleFacts(completed_comparable_samples=-1, distinct_plans=5)
    with pytest.raises(MaintenanceCodecError):
        strict_loads(
            ComparableSampleFacts,
            canonical_dumps(censored).replace('"censored_samples":5', '"censored_samples":-5'),
        )


def test_adaptive_boundaries_29_30_samples_and_4_5_plans() -> None:
    # 29 completed samples from 5 plans: report-only (SD2 cold start).
    below_samples = _samples(completed=29, plans=5)
    assert adaptive_action_eligible(below_samples) is False
    assert adaptive_values_report_only(below_samples) is True
    # 30 completed samples from 4 plans: report-only.
    below_plans = _samples(completed=30, plans=4)
    assert adaptive_action_eligible(below_plans) is False
    assert adaptive_values_report_only(below_plans) is True
    # 30 completed samples from 5 plans: eligible (approval still required).
    at_boundary = _samples(completed=30, plans=5)
    assert adaptive_action_eligible(at_boundary) is True
    assert adaptive_values_report_only(at_boundary) is False
    # Missing facts are never eligible (fail closed).
    assert adaptive_action_eligible(None) is False
    assert adaptive_values_report_only(None) is True
    assert MIN_ADAPTIVE_SAMPLES == 30
    assert MIN_ADAPTIVE_PLANS == 5


def test_action_policy_approved_is_explicit_and_gates_dispatch() -> None:
    observed = _stall_shaped(observed_at=_ts(15, 36))
    unapproved = classify_stall(policy=_policy(approved=False), facts=observed)
    # The stall is detected, but the explicit approval gate keeps it
    # report-only: provisional SLOs can generate shadow reports, never repair.
    assert unapproved.outcome is DecisionOutcome.STALL
    assert unapproved.action_policy_approved is False
    assert unapproved.dispatchable is False
    assert unapproved.green is False
    assert ReportOnlyReason.ACTION_POLICY_NOT_APPROVED in unapproved.report_only_reasons

    approved = classify_stall(policy=_policy(approved=True), facts=observed)
    assert approved.outcome is DecisionOutcome.STALL
    assert approved.action_policy_approved is True
    assert approved.dispatchable is True
    assert approved.green is True
    assert approved.report_only_reasons == ()
    assert approved.classifier_version == CLASSIFIER_VERSION


def test_operational_decision_rejects_overclaiming() -> None:
    # Only a STALL outcome with explicit approval, no suppressors, no
    # report-only reasons, and no censored metrics can be dispatchable.
    with pytest.raises(ValueError, match="only a STALL outcome"):
        OperationalDecision(
            policy_version="v1",
            outcome=DecisionOutcome.SUPPRESSED,
            action_policy_approved=True,
            dispatchable=True,
        )
    with pytest.raises(ValueError, match="explicit action_policy_approved"):
        OperationalDecision(
            policy_version="v1",
            outcome=DecisionOutcome.STALL,
            action_policy_approved=False,
            dispatchable=True,
        )
    with pytest.raises(ValueError, match="report-only"):
        OperationalDecision(
            policy_version="v1",
            outcome=DecisionOutcome.STALL,
            action_policy_approved=True,
            dispatchable=True,
            report_only_reasons=(ReportOnlyReason.ACTION_POLICY_NOT_APPROVED,),
        )
    with pytest.raises(ValueError, match="suppressed"):
        OperationalDecision(
            policy_version="v1",
            outcome=DecisionOutcome.STALL,
            action_policy_approved=True,
            dispatchable=True,
            suppressors=(SuppressorReason.ACTIVE_LEASE,),
        )
    with pytest.raises(ValueError, match="censored"):
        OperationalDecision(
            policy_version="v1",
            outcome=DecisionOutcome.STALL,
            action_policy_approved=True,
            dispatchable=True,
            censored_metrics=("gate_duration",),
        )
    # green requires dispatchable — suppressed observations are never green.
    with pytest.raises(ValueError, match="green requires dispatchable"):
        OperationalDecision(
            policy_version="v1",
            outcome=DecisionOutcome.SUPPRESSED,
            action_policy_approved=False,
            green=True,
        )


def test_all_policy_models_round_trip_strictly() -> None:
    models = (
        _policy(approved=True),
        CohortIdentity(
            run=RunId("run-1"),
            stage=StageId("stage-1"),
            profile=ProfileId("profile-1"),
            model=ModelId("model-1"),
            environment=EnvironmentId("production"),
        ),
        _samples(completed=30, plans=5, denominator=30, censored=2, unknown=1),
        _facts(observed_at=_ts(15, 36), second_coherent_observation=True),
        classify_stall(policy=_policy(approved=True), facts=_stall_shaped(observed_at=_ts(15, 36))),
    )
    for model in models:
        decoded = strict_loads(type(model), canonical_dumps(model))
        assert decoded == model
        assert canonical_digest(decoded) == canonical_digest(model)


def test_fail_closed_facts_reject_coherent_evidence_with_torn_or_mismatch_flags() -> None:
    # A COHERENT observation cannot smuggle torn, mismatched, or
    # cross-environment evidence; such evidence must be declared INCOHERENT.
    for kwargs in (
        {"torn": True},
        {"identity_mismatch": True},
        {"cross_environment": True},
    ):
        with pytest.raises(ValueError, match="INCOHERENT"):
            _facts(observed_at=_ts(15, 36), **kwargs)
    # A non-coherent observation can never be a second coherent observation.
    with pytest.raises(ValueError, match="second coherent"):
        _facts(
            observed_at=_ts(15, 36),
            coherence=CoherenceState.UNKNOWN,
            second_coherent_observation=True,
        )


def test_package_exports_only_reference_policy_types() -> None:
    # Every policy name is part of the frozen M4-facing API surface.
    for name in (
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
        "classify_stall",
        "cohort_matches",
        "suppressors_for",
    ):
        assert name in M4_API, name
    # The policy module never imports or constructs an owner authority store.
    root = Path(__file__).resolve().parents[3]
    source = (root / "arnold_pipelines/megaplan/maintenance/operational_policy.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    lowered = " ".join(imported).lower()
    for forbidden in _FORBIDDEN_OWNER_IMPORTS:
        assert forbidden not in lowered, (
            f"operational_policy.py imports an owner authority seam: {forbidden}"
        )


# ---------------------------------------------------------------------------
# T2 — Step 2: predicates, repetition, suppressors, and outcomes
# ---------------------------------------------------------------------------


def test_policy_expiry_is_computed_not_asserted() -> None:
    # The declared SLO horizon has NOT passed: no stall, whatever else holds.
    future_policy = _policy(approved=True, expires_at=_ts(16, 0))
    early = _stall_shaped(observed_at=_ts(15, 36))
    assert policy_is_expired(future_policy, early) is False
    decision = classify_stall(policy=future_policy, facts=early)
    assert decision.outcome is DecisionOutcome.NO_STALL
    assert decision.dispatchable is False
    # Once the declared horizon passes, expiry is computed from the policy.
    expired_policy = _policy(approved=True, expires_at=_ts(15, 30))
    assert policy_is_expired(expired_policy, early) is True
    assert slo_expired(expired_policy, early) is True
    assert classify_stall(policy=expired_policy, facts=early).outcome is DecisionOutcome.STALL


def test_live_call_or_lease_defeat_stall() -> None:
    policy = _policy(approved=True)
    # A valid in-flight call is work in progress: no stall.
    live_call = _stall_shaped(observed_at=_ts(15, 36), live_call=True)
    decision = classify_stall(policy=policy, facts=live_call)
    assert decision.outcome is DecisionOutcome.NO_STALL
    assert decision.dispatchable is False
    # An active lease is a locked suppressor: SUPPRESSED, never dispatchable.
    live_lease = _stall_shaped(observed_at=_ts(15, 36), live_lease=True)
    decision = classify_stall(policy=policy, facts=live_lease)
    assert decision.outcome is DecisionOutcome.SUPPRESSED
    assert SuppressorReason.ACTIVE_LEASE in decision.suppressors
    assert decision.dispatchable is False
    assert decision.green is False


def test_material_delta_defeats_stall() -> None:
    policy = _policy(approved=True)
    for delta in DeltaKind:
        decision = classify_stall(
            policy=policy,
            facts=_stall_shaped(
                observed_at=_ts(15, 36),
                material_deltas=(delta,),
            ),
        )
        assert has_material_delta(_facts(observed_at=_ts(15, 36), material_deltas=(delta,))) is True
        assert decision.outcome is DecisionOutcome.NO_STALL
        assert decision.dispatchable is False


def test_second_coherent_observation_required() -> None:
    policy = _policy(approved=True)
    # First coherent observation: everything else holds, but confirmation is
    # missing — explicitly report-only, never dispatchable.
    first = _stall_shaped(observed_at=_ts(15, 30), second_coherent_observation=False)
    decision = classify_stall(policy=policy, facts=first)
    assert decision.outcome is DecisionOutcome.NO_STALL
    assert ReportOnlyReason.SINGLE_OBSERVATION in decision.report_only_reasons
    assert decision.dispatchable is False
    # Second coherent observation confirms the stall.
    second = _stall_shaped(observed_at=_ts(15, 33), second_coherent_observation=True)
    decision = classify_stall(policy=policy, facts=second)
    assert decision.outcome is DecisionOutcome.STALL
    assert decision.dispatchable is True


def test_repetition_three_equivalent_failures() -> None:
    policy = _policy(approved=True)
    facts = _facts(
        observed_at=_ts(15, 36),
        block_kind=BlockKind.STAGE_REPETITION,
        equivalent_failures=3,
        second_coherent_observation=True,
    )
    assert repetition_met(facts) is True
    assert classify_stall(policy=policy, facts=facts).outcome is DecisionOutcome.STALL
    # Two equivalent failures are NOT yet actionable for stage repetition.
    two = facts.model_copy(update={"equivalent_failures": 2})
    assert repetition_met(two) is False
    decision = classify_stall(policy=policy, facts=two)
    assert decision.outcome is DecisionOutcome.NO_STALL
    assert decision.dispatchable is False


def test_repetition_two_retry_revision_cycles_same_fingerprint() -> None:
    policy = _policy(approved=True)
    base = dict(
        observed_at=_ts(15, 36),
        block_kind=BlockKind.STAGE_REPETITION,
        retry_revision_cycles=2,
        second_coherent_observation=True,
    )
    # Two retry/revision cycles with the same fingerprint and no material
    # delta are actionable.
    same = _facts(**base, same_fingerprint=True)
    assert repetition_met(same) is True
    assert classify_stall(policy=policy, facts=same).outcome is DecisionOutcome.STALL
    # A different fingerprint is NOT actionable: the repetition must share the
    # same input/error fingerprint.
    different = _facts(**base, same_fingerprint=False)
    assert repetition_met(different) is False
    assert classify_stall(policy=policy, facts=different).outcome is DecisionOutcome.NO_STALL
    # One cycle is never actionable.
    one = _facts(**{**base, "retry_revision_cycles": 1, "same_fingerprint": True})
    assert repetition_met(one) is False
    assert classify_stall(policy=policy, facts=one).outcome is DecisionOutcome.NO_STALL


def test_no_progress_requires_increasing_cost_without_improvement() -> None:
    policy = _policy(approved=True)
    base = dict(
        observed_at=_ts(15, 36),
        block_kind=BlockKind.NO_PROGRESS,
        second_coherent_observation=True,
    )
    # Increasing time/cost without any accepted improvement: actionable.
    increasing = _facts(**base, no_progress_cost_increasing=True)
    assert no_progress_met(increasing) is True
    assert classify_stall(policy=policy, facts=increasing).outcome is DecisionOutcome.STALL
    # Flat cost is not a no-progress stall.
    flat = _facts(**base, no_progress_cost_increasing=False)
    assert no_progress_met(flat) is False
    assert classify_stall(policy=policy, facts=flat).outcome is DecisionOutcome.NO_STALL
    # Increasing cost WITH an accepted improvement is progress, not a stall.
    improved = _facts(
        **base,
        no_progress_cost_increasing=True,
        material_deltas=(DeltaKind.EVIDENCE_COVERAGE,),
    )
    assert no_progress_met(improved) is False
    assert classify_stall(policy=policy, facts=improved).outcome is DecisionOutcome.NO_STALL


def test_gate_finalize_review_requires_slo_expiry_and_cohort_agreement() -> None:
    policy = _policy(approved=True)
    base = dict(
        observed_at=_ts(15, 36),
        block_kind=BlockKind.GATE_FINALIZE_REVIEW,
        second_coherent_observation=True,
        equivalent_failures=3,
    )
    # Declared SLO expired AND cohort evidence agrees: actionable.
    agreeing = _facts(**base, cohort_agrees=True)
    assert slo_expired(policy, agreeing) is True
    assert classify_stall(policy=policy, facts=agreeing).outcome is DecisionOutcome.STALL
    # Cohort evidence disagrees: a daily p95 outlier flag can never act.
    disagreeing = _facts(**base, cohort_agrees=False)
    assert slo_expired(policy, disagreeing) is False
    decision = classify_stall(policy=policy, facts=disagreeing)
    assert decision.outcome is DecisionOutcome.NO_STALL
    assert decision.dispatchable is False
    # Not-yet-expired SLO: no intervention even with cohort agreement.
    future_policy = _policy(approved=True, expires_at=_ts(16, 0))
    assert classify_stall(policy=future_policy, facts=agreeing).outcome is DecisionOutcome.NO_STALL


def test_unknown_and_incoherent_outcomes_never_dispatch() -> None:
    policy = _policy(approved=True)
    cases = [
        # (facts, expected outcome)
        (
            _facts(observed_at=_ts(15, 36), coherence=CoherenceState.INCOHERENT),
            DecisionOutcome.INCOHERENT,
        ),
        (
            _facts(
                observed_at=_ts(15, 36),
                coherence=CoherenceState.INCOHERENT,
                cross_environment=True,
            ),
            DecisionOutcome.INCOHERENT,
        ),
        (
            _facts(
                observed_at=_ts(15, 36),
                coherence=CoherenceState.UNKNOWN,
                torn=True,
            ),
            DecisionOutcome.INCOHERENT,
        ),
        (
            _facts(
                observed_at=_ts(15, 36),
                coherence=CoherenceState.UNKNOWN,
                identity_mismatch=True,
            ),
            DecisionOutcome.INCOHERENT,
        ),
        (
            _facts(observed_at=_ts(15, 36), coherence=CoherenceState.UNKNOWN),
            DecisionOutcome.UNKNOWN,
        ),
        (
            _facts(observed_at=_ts(15, 36), freshness=FreshnessState.STALE),
            DecisionOutcome.UNKNOWN,
        ),
        (
            _facts(observed_at=_ts(15, 36), completeness=CompletenessState.PARTIAL),
            DecisionOutcome.UNKNOWN,
        ),
    ]
    for facts, expected in cases:
        assert evidence_coherent(facts) is False
        decision = classify_stall(policy=policy, facts=facts)
        assert decision.outcome is expected
        assert decision.dispatchable is False
        assert decision.green is False
        # The explicit approval state is still carried on non-dispatchable
        # decisions so shadow reports never lose the authorization context.
        assert decision.action_policy_approved is True


_SUPPRESSOR_CASES = [
    ("backoff_or_fallback", SuppressorReason.BACKOFF_OR_FALLBACK),
    ("unmatched_fresh_call_start", SuppressorReason.UNMATCHED_FRESH_CALL_START),
    ("declared_long_phase", SuppressorReason.DECLARED_LONG_PHASE),
    ("thorough_or_extreme_robustness", SuppressorReason.THOROUGH_OR_EXTREME_ROBUSTNESS),
    ("live_lease", SuppressorReason.ACTIVE_LEASE),
    ("external_pr_human_quota_gate", SuppressorReason.EXTERNAL_PR_HUMAN_QUOTA_GATE),
    ("improving_quality", SuppressorReason.IMPROVING_QUALITY),
]


@pytest.mark.parametrize("flag,reason", _SUPPRESSOR_CASES)
def test_every_locked_suppressor_suppresses_and_retains_censored_metrics(
    flag: str, reason: SuppressorReason
) -> None:
    policy = _policy(approved=True)
    # The observation would otherwise be a confirmed stall: 3 equivalent
    # failures, expired policy, second coherent observation, no live work.
    facts = _stall_shaped(
        observed_at=_ts(15, 36),
        censored_metric_names=("gate_duration", "finalize_gap"),
        **{flag: True},
    )
    suppressors = suppressors_for(facts)
    assert reason in suppressors
    decision = classify_stall(policy=policy, facts=facts)
    assert decision.outcome is DecisionOutcome.SUPPRESSED
    assert reason in decision.suppressors
    assert decision.dispatchable is False
    assert decision.green is False
    # Suppressed observations retain their censored metrics — never dropped,
    # never promoted to zero or green.
    assert decision.censored_metrics == ("gate_duration", "finalize_gap")


def test_suppressed_observation_never_becomes_green_by_inference() -> None:
    policy = _policy(approved=True)
    facts = _stall_shaped(
        observed_at=_ts(15, 36),
        improving_quality=True,
        censored_metric_names=("stage_duration",),
    )
    decision = classify_stall(policy=policy, facts=facts)
    assert decision.outcome is DecisionOutcome.SUPPRESSED
    assert decision.dispatchable is False
    assert decision.green is False
    # The suppressed observation retains the censored metric name.
    assert decision.censored_metrics == ("stage_duration",)


def test_adaptive_values_report_only_until_30_samples_five_plans_and_approval() -> None:
    observed = _stall_shaped(observed_at=_ts(15, 36))
    # 30 samples / 5 plans AND explicit approval: adaptive values may act.
    decision = classify_stall(
        policy=_policy(approved=True),
        facts=observed,
        samples=_samples(completed=30, plans=5),
        uses_adaptive_slo=True,
    )
    assert decision.outcome is DecisionOutcome.STALL
    assert decision.dispatchable is True
    # 29 samples / 5 plans: adaptive values stay report-only (SD2).
    decision = classify_stall(
        policy=_policy(approved=True),
        facts=observed,
        samples=_samples(completed=29, plans=5),
        uses_adaptive_slo=True,
    )
    assert decision.outcome is DecisionOutcome.STALL
    assert decision.dispatchable is False
    assert ReportOnlyReason.COLD_START_ADAPTIVE_REPORT_ONLY in decision.report_only_reasons
    # 30 samples / 4 plans: still report-only.
    decision = classify_stall(
        policy=_policy(approved=True),
        facts=observed,
        samples=_samples(completed=30, plans=4),
        uses_adaptive_slo=True,
    )
    assert decision.dispatchable is False
    assert ReportOnlyReason.COLD_START_ADAPTIVE_REPORT_ONLY in decision.report_only_reasons
    # 30/5 but NO approval: report-only — both gates must hold together.
    decision = classify_stall(
        policy=_policy(approved=False),
        facts=observed,
        samples=_samples(completed=30, plans=5),
        uses_adaptive_slo=True,
    )
    assert decision.dispatchable is False
    assert ReportOnlyReason.ACTION_POLICY_NOT_APPROVED in decision.report_only_reasons
    # 29/5 AND no approval: both cold-start and approval gates are missing.
    decision = classify_stall(
        policy=_policy(approved=False),
        facts=observed,
        samples=_samples(completed=29, plans=5),
        uses_adaptive_slo=True,
    )
    assert decision.dispatchable is False
    assert ReportOnlyReason.COLD_START_ADAPTIVE_REPORT_ONLY in decision.report_only_reasons
    assert ReportOnlyReason.ACTION_POLICY_NOT_APPROVED in decision.report_only_reasons
    # Missing sample facts are never eligible (fail closed).
    decision = classify_stall(
        policy=_policy(approved=True),
        facts=observed,
        samples=None,
        uses_adaptive_slo=True,
    )
    assert decision.dispatchable is False
    assert ReportOnlyReason.COLD_START_ADAPTIVE_REPORT_ONLY in decision.report_only_reasons
    # Without an adaptive SLO, the declared static policy alone authorizes
    # action once approved (cold-start does not apply to static SLOs).
    decision = classify_stall(
        policy=_policy(approved=True),
        facts=observed,
        samples=_samples(completed=0, plans=0),
        uses_adaptive_slo=False,
    )
    assert decision.dispatchable is True


def test_wbc_gate_timeline_fixture() -> None:
    """The WBC gate timeline: repeated north_star_actions failures share one
    fingerprint and may propose ONE occurrence; the accepted artifact and the
    later frontier advancement suppress any new request.

    Timeline (brief ``WBC gate/finalize example``):
    * 15:30, 15:33, 15:36 — repeated `north_star_actions` schema failures on
      one fingerprint; no accepted artifact, no live call/lease.
    * 15:43 — a passing gate is accepted: material delta, no new request.
    * 15:45 — state/events advance: material delta, no new request.
    """
    policy = _policy(
        approved=True,
        expires_at=_ts(15, 30),
        stage="north_star_actions",
        version="wbc-gate-policy-v1",
    )
    fingerprint = "north_star_actions:repeated-15:30-15:36"

    def observe(at: datetime, **kwargs) -> OperationalDecision:
        return classify_stall(
            policy=policy,
            facts=_facts(
                observed_at=at,
                block_kind=BlockKind.GATE_FINALIZE_REVIEW,
                fingerprint=fingerprint,
                cohort_agrees=True,
                **kwargs,
            ),
        )

    # 15:30 — first coherent observation: confirmation missing, report-only.
    first = observe(_ts(15, 30), equivalent_failures=1, second_coherent_observation=False)
    assert first.outcome is DecisionOutcome.NO_STALL
    assert ReportOnlyReason.SINGLE_OBSERVATION in first.report_only_reasons
    assert first.dispatchable is False

    # 15:33 — second coherent observation confirms no progress: ONE occurrence
    # may be proposed for the repeated fingerprint.
    proposed = observe(_ts(15, 33), equivalent_failures=2, second_coherent_observation=True)
    assert proposed.outcome is DecisionOutcome.STALL
    assert proposed.dispatchable is True
    assert proposed.fingerprint == fingerprint

    # 15:36 — an identical re-observation of the same fingerprint produces the
    # identical decision (join/dedupe downstream, never a second proposal).
    repeated = observe(_ts(15, 36), equivalent_failures=3, second_coherent_observation=True)
    assert repeated == proposed
    assert canonical_digest(repeated) == canonical_digest(proposed)

    # 15:43 — a passing gate is accepted: the artifact delta suppresses any new
    # request even though the fingerprint is unchanged.
    accepted = observe(
        _ts(15, 43),
        equivalent_failures=3,
        second_coherent_observation=True,
        material_deltas=(DeltaKind.ARTIFACT_DIGEST,),
    )
    assert accepted.outcome is DecisionOutcome.NO_STALL
    assert accepted.dispatchable is False

    # 15:45 — state/events advance past the frontier: no new request.
    advanced = observe(
        _ts(15, 45),
        equivalent_failures=3,
        second_coherent_observation=True,
        material_deltas=(DeltaKind.TASK_FRONTIER, DeltaKind.PLAN_VERSION),
    )
    assert advanced.outcome is DecisionOutcome.NO_STALL
    assert advanced.dispatchable is False

    # Exactly ONE distinct dispatchable proposal exists across the whole
    # timeline: the 15:33 and 15:36 observations classify as the SAME
    # decision (identical digest), which is what lets the runtime join them
    # into a single occurrence/request instead of proposing twice.
    dispatchable = [d for d in (first, proposed, repeated, accepted, advanced) if d.dispatchable]
    assert len(dispatchable) == 2  # the two pre-artifact observations
    assert len({canonical_digest(d) for d in dispatchable}) == 1  # one proposal
    assert dispatchable[0] is proposed


def test_sc2_sweep_no_stale_torn_mismatched_live_or_single_observation_dispatchable() -> None:
    """Every SC2 hazard case stays non-dispatchable through the fail-closed
    decision path."""
    policy = _policy(approved=True)
    nondispatchable_cases = [
        # stale evidence
        _facts(observed_at=_ts(15, 36), freshness=FreshnessState.STALE),
        # torn evidence
        _facts(
            observed_at=_ts(15, 36),
            coherence=CoherenceState.UNKNOWN,
            torn=True,
        ),
        # identity-mismatched evidence
        _facts(
            observed_at=_ts(15, 36),
            coherence=CoherenceState.UNKNOWN,
            identity_mismatch=True,
        ),
        # cross-environment evidence
        _facts(
            observed_at=_ts(15, 36),
            coherence=CoherenceState.INCOHERENT,
            cross_environment=True,
        ),
        # live in-flight call
        _stall_shaped(observed_at=_ts(15, 36), live_call=True),
        # live lease (locked suppressor)
        _stall_shaped(observed_at=_ts(15, 36), live_lease=True),
        # improving quality (locked suppressor)
        _stall_shaped(observed_at=_ts(15, 36), improving_quality=True),
        # declared long phase (locked suppressor)
        _stall_shaped(observed_at=_ts(15, 36), declared_long_phase=True),
        # backoff/fallback (locked suppressor)
        _stall_shaped(observed_at=_ts(15, 36), backoff_or_fallback=True),
        # external PR/human/quota gate (locked suppressor)
        _stall_shaped(observed_at=_ts(15, 36), external_pr_human_quota_gate=True),
        # unmatched fresh call start (locked suppressor)
        _stall_shaped(observed_at=_ts(15, 36), unmatched_fresh_call_start=True),
        # single observation (no confirmation)
        _stall_shaped(observed_at=_ts(15, 36), second_coherent_observation=False),
        # accepted material delta
        _stall_shaped(
            observed_at=_ts(15, 36),
            material_deltas=(DeltaKind.ACCEPTED_DECISION,),
        ),
    ]
    unexpired_policy = _policy(approved=True, expires_at=_ts(16, 0))
    for facts in nondispatchable_cases:
        decision = classify_stall(policy=policy, facts=facts)
        assert decision.dispatchable is False, (
            f"hazard case became dispatchable: {facts.model_dump()}"
        )
        assert decision.green is False
    # policy not expired — the declared stage policy still has runway.
    decision = classify_stall(
        policy=unexpired_policy,
        facts=_stall_shaped(observed_at=_ts(15, 36)),
    )
    assert decision.outcome is DecisionOutcome.NO_STALL
    assert decision.dispatchable is False
