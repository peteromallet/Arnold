"""Focused Maintenance projection tests (M2, T13).

These tests prove the three independent projections
(``operational_custody``, ``verification``, ``efficiency_analysis``):

* independent advance with explicit sequence, source cursor/digest, output
  digest, lag, and freshness;
* occurrence dedupe versus causally linked verified recurrence;
* efficiency events can never alter custody or verification state;
* half-open watermarked windows (lateness/freshness) and append-only
  late-evidence corrections that never rewrite a prior result;
* retention of censoring, denominators, unknowns, coverage, classifier
  version, and digests;
* deterministic replay of the committed ``recurrence_replay.jsonl`` fixture.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.maintenance.events import (
    AuditFinding,
    AuditReport,
    ClassifierInfo,
    DetectionEvent,
    EfficiencyAnalysis,
    EventKind,
    MaintenanceEvent,
    OccurrenceBudget,
    RootCauseCluster,
    verified_recurrence,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EventWindow,
    Lateness,
    OwnerRef,
    UtcTime,
    Watermark,
    canonical_digest,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.projections import (
    ApplyDisposition,
    CorrectionKind,
    ProjectionConflictError,
    ProjectionEngine,
    ProjectionFreshness,
    ProjectionName,
    ProjectionResult,
    replay,
)

UTC = timezone.utc
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "maintenance"
REPLAY_FIXTURE = FIXTURE_DIR / "recurrence_replay.jsonl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _window(start_hour: int = 10, end_hour: int = 13) -> EventWindow:
    return EventWindow(
        start=UtcTime(f"2026-08-15T{start_hour:02d}:00:00+00:00"),
        end=UtcTime(f"2026-08-15T{end_hour:02d}:00:00+00:00"),
    )


def _detection(
    occurrence_id: str,
    event_id: str,
    *,
    event_time_hour: int,
    watermark_hour: int = 11,
    budget: OccurrenceBudget | None = None,
    cluster: RootCauseCluster | None = None,
) -> MaintenanceEvent:
    """Build an on-time or late detection event against an 11:30 watermark."""
    return MaintenanceEvent.build(
        event_id=event_id,
        occurrence_id=occurrence_id,
        observed_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        event_time=datetime(2026, 8, 15, event_time_hour, 30, tzinfo=UTC),
        window=_window(),
        watermark=Watermark(
            f"2026-08-15T{watermark_hour:02d}:30:00+00:00"
        ),
        classifier=ClassifierInfo(classifier_version="v1", confidence=0.9),
        cluster=cluster or RootCauseCluster(signature="sig-root", cluster_id="c-1"),
        budget=budget or OccurrenceBudget(max_attempts=3, attempts_used=1),
        payload=DetectionEvent(detection_kind="watchdog", subject="chain:session"),
        environment="production",
    )


def _efficiency(
    occurrence_id: str,
    event_id: str,
    *,
    event_time_hour: int = 11,
    product: str = "daily-efficiency",
    coverage_denominator: int | None = 100,
    covered_count: int | None = 87,
    censored_duration_seconds: float | None = 12.5,
) -> MaintenanceEvent:
    return MaintenanceEvent.build(
        event_id=event_id,
        occurrence_id=occurrence_id,
        observed_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        event_time=datetime(2026, 8, 15, event_time_hour, 50, tzinfo=UTC),
        window=_window(),
        watermark=Watermark("2026-08-15T11:30:00+00:00"),
        classifier=ClassifierInfo(classifier_version="v1", confidence=0.9),
        cluster=RootCauseCluster(signature="sig-eff", cluster_id="c-eff"),
        budget=OccurrenceBudget(max_attempts=1, attempts_used=1),
        payload=EfficiencyAnalysis(
            product=product,
            coverage_denominator=coverage_denominator,
            covered_count=covered_count,
            censored_duration_seconds=censored_duration_seconds,
        ),
        environment="production",
    )


def _load_replay_fixture() -> list[MaintenanceEvent]:
    events: list[MaintenanceEvent] = []
    for line in REPLAY_FIXTURE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(strict_loads(MaintenanceEvent, line))
    return events


# ---------------------------------------------------------------------------
# Independent advance: sequence, cursor, digests, lag, freshness
# ---------------------------------------------------------------------------


def test_projections_advance_independently() -> None:
    engine = ProjectionEngine()
    result = engine.apply(_detection("occ-1", "evt-1", event_time_hour=12))

    assert isinstance(result, ProjectionResult)
    assert result.disposition is ApplyDisposition.APPLIED
    # Detection advances custody and verification, but not efficiency.
    assert engine.custody.sequence == 1
    assert engine.verification.sequence == 1
    assert engine.efficiency.sequence == 0
    # Each projection exposes the full metadata surface.
    assert engine.custody.cursor == 1
    assert engine.custody.source_digest is not None
    assert engine.custody.output_digest is not None
    assert engine.custody.freshness is ProjectionFreshness.FRESH
    # Efficiency lags behind the global source cursor.
    assert engine.efficiency.lag == 1
    assert engine.custody.lag == 0
    # Coordinates bridge to the shared ProjectionCoordinates contract.
    coords = engine.custody.coordinates
    assert coords.projection == ProjectionName.OPERATIONAL_CUSTODY.value
    assert coords.sequence == 1
    assert coords.cursor == "seq:1"


def test_freshness_reflects_watermark_lateness() -> None:
    engine = ProjectionEngine()
    engine.apply(_detection("occ-on", "evt-on", event_time_hour=11))  # 11:30 > 11:30? no
    # 11:30 event_time vs 11:30 watermark -> late (closed boundary)
    assert engine.custody.freshness is ProjectionFreshness.STALE

    engine2 = ProjectionEngine()
    engine2.apply(_detection("occ-on", "evt-on", event_time_hour=12))  # 12:30 > 11:30
    assert engine2.custody.freshness is ProjectionFreshness.FRESH


# ---------------------------------------------------------------------------
# Occurrence dedupe vs. verified recurrence
# ---------------------------------------------------------------------------


def test_exact_duplicate_is_deduped_and_consumes_no_budget() -> None:
    engine = ProjectionEngine()
    event = _detection("occ-1", "evt-1", event_time_hour=12)
    engine.apply(event)

    again = engine.apply(event)

    assert again.disposition is ApplyDisposition.DEDUPED
    assert again.applied is False
    assert engine.custody.sequence == 1  # did not advance
    assert engine.custody.budget.attempts_used == 1  # budget not consumed again
    assert engine.custody.source_digest == engine.custody.source_digest
    assert len(engine.custody.corrections) == 0


def test_divergent_duplicate_raises_conflict() -> None:
    engine = ProjectionEngine()
    engine.apply(_detection("occ-1", "evt-1", event_time_hour=12))

    divergent = _detection("occ-1", "evt-1-different", event_time_hour=12)

    with pytest.raises(ProjectionConflictError, match="idempotency conflict"):
        engine.apply(divergent)

    # Nothing advanced on the conflicting event.
    assert engine.custody.sequence == 1
    assert engine.custody.event_id == "evt-1"


def test_verified_recurrence_creates_fresh_causally_linked_occurrence() -> None:
    engine = ProjectionEngine()
    predecessor = _detection(
        "occ-1", "evt-1", event_time_hour=12, cluster=RootCauseCluster(signature="sig-root", cluster_id="c-9")
    )
    engine.apply(predecessor)

    recurrence = verified_recurrence(
        predecessor=predecessor,
        new_event_id="evt-2",
        new_occurrence_id="occ-2",
        observed_at=datetime(2026, 8, 15, 12, 5, tzinfo=UTC),
        event_time=datetime(2026, 8, 15, 12, 10, tzinfo=UTC),
        window=_window(),
        watermark=Watermark("2026-08-15T11:30:00+00:00"),
        budget=OccurrenceBudget(max_attempts=3, attempts_used=0),
        payload=DetectionEvent(detection_kind="watchdog", subject="chain:session"),
        environment="production",
    )
    engine.apply(recurrence)

    # The recurrence is a NEW occurrence: it was applied, not deduped.
    assert engine.custody.sequence == 2
    assert engine.custody.occurrence_id == "occ-2"
    # Fresh occurrence-scoped budget.
    assert engine.custody.budget.attempts_used == 0
    # Causally linked and cluster grouping preserved.
    assert len(engine.custody.recurrences) == 1
    assert engine.custody.recurrences[0].predecessor_occurrence_id == "occ-1"
    assert engine.custody.recurrences[0].predecessor_event_id == "evt-1"
    assert engine.custody.cluster_signature == "sig-root"
    assert engine.custody.cluster_id == "c-9"


# ---------------------------------------------------------------------------
# Efficiency isolation
# ---------------------------------------------------------------------------


def test_efficiency_event_cannot_alter_custody_or_verification() -> None:
    engine = ProjectionEngine()
    engine.apply(_detection("occ-1", "evt-1", event_time_hour=12))
    custody_before = engine.custody
    verification_before = engine.verification

    engine.apply(_efficiency("occ-eff", "evt-eff", event_time_hour=12))

    # The only field an efficiency event may touch on custody/verification is
    # the global-cursor metadata (``lag``); the materialized output and every
    # other field are untouched.
    assert engine.custody.model_copy(update={"lag": custody_before.lag}) == custody_before
    assert (
        engine.verification.model_copy(update={"lag": verification_before.lag})
        == verification_before
    )
    assert engine.custody.output_digest == custody_before.output_digest
    assert engine.custody.sequence == custody_before.sequence
    # Efficiency advanced on its own.
    assert engine.efficiency.sequence == 1
    assert engine.efficiency.product == "daily-efficiency"


def test_reducer_level_isolation_for_efficiency() -> None:
    from arnold_pipelines.megaplan.maintenance.projections import (
        reduce_custody,
        reduce_verification,
    )

    engine = ProjectionEngine()
    eff = _efficiency("occ-eff", "evt-eff", event_time_hour=12)
    digest = canonical_digest(eff)

    # Forcing an efficiency event through custody/verification reducers is a no-op.
    assert reduce_custody(eff, engine.custody, cursor=9, event_digest=digest) == engine.custody
    assert reduce_verification(eff, engine.verification, cursor=9, event_digest=digest) == engine.verification


# ---------------------------------------------------------------------------
# Efficiency retention: censoring, denominators, unknowns, coverage, hashes
# ---------------------------------------------------------------------------


def test_efficiency_retains_censoring_denominators_coverage_and_window() -> None:
    engine = ProjectionEngine()
    engine.apply(_efficiency("occ-eff", "evt-eff", event_time_hour=12))

    state = engine.efficiency
    assert state.product == "daily-efficiency"
    assert state.coverage_denominator == 100
    assert state.covered_count == 87
    assert state.censored_duration_seconds == 12.5
    assert state.coverage == 0.87
    assert state.classifier_version == "v1"
    # Half-open window and watermark are retained (digest-visible).
    assert state.window_start == "2026-08-15T10:00:00+00:00"
    assert state.window_end == "2026-08-15T13:00:00+00:00"
    assert state.watermark == "2026-08-15T11:30:00+00:00"
    assert state.output_digest is not None


def test_efficiency_unknowns_stay_explicit() -> None:
    engine = ProjectionEngine()
    engine.apply(
        _efficiency(
            "occ-eff", "evt-eff", event_time_hour=12,
            coverage_denominator=None, covered_count=None, censored_duration_seconds=None,
        )
    )

    state = engine.efficiency
    assert state.coverage_denominator is None
    assert state.covered_count is None
    assert state.censored_duration_seconds is None
    assert state.coverage is None  # unknown, never zero


def test_half_open_window_excludes_end() -> None:
    window = _window(11, 12)  # [11:00, 12:00)
    assert window.contains(UtcTime("2026-08-15T11:00:00+00:00")) is True
    assert window.contains(UtcTime("2026-08-15T11:59:59+00:00")) is True
    assert window.contains(UtcTime("2026-08-15T12:00:00+00:00")) is False


# ---------------------------------------------------------------------------
# Append-only late-evidence corrections
# ---------------------------------------------------------------------------


def test_late_evidence_appends_correction_without_rewriting() -> None:
    engine = ProjectionEngine()
    engine.apply(_detection("occ-1", "evt-1", event_time_hour=12))
    prior = engine.custody
    assert len(prior.corrections) == 0

    # Late event: event_time 10:30 <= 11:30 watermark.
    engine.apply(_detection("occ-2", "evt-2", event_time_hour=10))

    state = engine.custody
    assert state.sequence == 2
    assert len(state.corrections) == 1
    correction = state.corrections[0]
    assert correction.kind is CorrectionKind.LATE_EVIDENCE
    assert correction.corrected_sequence == 1
    assert correction.sequence == 2
    # The prior result's identity is preserved in the correction, not overwritten.
    assert correction.prior_output_digest == prior.output_digest
    assert correction.event_id == "evt-2"
    assert correction.occurrence_id == "occ-2"
    # The late event is stale, and its correction changes the output digest.
    assert state.freshness is ProjectionFreshness.STALE
    assert state.output_digest != prior.output_digest


def test_replaying_late_event_does_not_append_a_second_correction() -> None:
    engine = ProjectionEngine()
    engine.apply(_detection("occ-1", "evt-1", event_time_hour=12))
    late = _detection("occ-2", "evt-2", event_time_hour=10)
    engine.apply(late)
    assert len(engine.custody.corrections) == 1

    engine.apply(late)  # duplicate

    assert engine.custody.sequence == 2
    assert len(engine.custody.corrections) == 1


def test_first_event_being_late_needs_no_correction() -> None:
    engine = ProjectionEngine()
    engine.apply(_detection("occ-1", "evt-1", event_time_hour=10))

    assert engine.custody.sequence == 1
    assert engine.custody.freshness is ProjectionFreshness.STALE
    assert len(engine.custody.corrections) == 0  # nothing prior to correct


# ---------------------------------------------------------------------------
# Audit reports feed verification (and never efficiency)
# ---------------------------------------------------------------------------


def test_audit_report_updates_verification_only() -> None:
    engine = ProjectionEngine()
    engine.apply(_detection("occ-1", "evt-1", event_time_hour=12))

    audit = MaintenanceEvent.build(
        event_id="evt-audit",
        occurrence_id="occ-audit",
        observed_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        event_time=datetime(2026, 8, 15, 12, 10, tzinfo=UTC),
        window=_window(),
        watermark=Watermark("2026-08-15T11:30:00+00:00"),
        classifier=ClassifierInfo(classifier_version="v1", confidence=0.9),
        cluster=RootCauseCluster(signature="sig-root", cluster_id="c-1"),
        budget=OccurrenceBudget(max_attempts=1, attempts_used=1),
        payload=AuditReport(
            report_type="efficiency-audit",
            verdict="pass",
            findings=(AuditFinding(finding_id="f-1", severity="info", message="ok"),),
        ),
        environment="production",
    )
    engine.apply(audit)

    assert engine.verification.sequence == 2
    assert engine.verification.audit_verdict == "pass"
    assert engine.verification.audit_report_type == "efficiency-audit"
    assert engine.custody.sequence == 1  # audit does not alter custody
    assert engine.efficiency.sequence == 0  # audit does not alter efficiency


# ---------------------------------------------------------------------------
# Determinism, order sensitivity, and the recurrence replay fixture
# ---------------------------------------------------------------------------


def test_replay_is_deterministic() -> None:
    engine_a = ProjectionEngine()
    engine_b = ProjectionEngine()
    for event in _load_replay_fixture():
        engine_a.apply(event)
    for event in _load_replay_fixture():
        engine_b.apply(event)

    assert engine_a.custody == engine_b.custody
    assert engine_a.verification == engine_b.verification
    assert engine_a.efficiency == engine_b.efficiency
    assert engine_a.custody.output_digest == engine_b.custody.output_digest


def test_replay_order_changes_source_digest() -> None:
    events = _load_replay_fixture()
    forward = replay(events)
    reversed_engine = replay(list(reversed(events)))

    assert forward.custody.source_digest != reversed_engine.custody.source_digest


def test_recurrence_replay_fixture_sequence() -> None:
    """Pin the committed recurrence replay fixture end-to-end."""
    events = _load_replay_fixture()
    assert len(events) == 4
    assert events[0].event_kind is EventKind.DETECTION
    assert events[1].event_kind is EventKind.DETECTION
    assert events[1].recurrence is not None
    assert events[2].event_kind is EventKind.EFFICIENCY_ANALYSIS
    assert events[3].lateness is Lateness.LATE

    engine = ProjectionEngine()
    for event in events:
        engine.apply(event)

    # detection 1 + recurrence + late detection -> custody/verification seq 3
    assert engine.custody.sequence == 3
    assert engine.verification.sequence == 3
    # efficiency advanced exactly once (the single efficiency event)
    assert engine.efficiency.sequence == 1
    # recurrence preserved, late event appended a correction
    assert engine.custody.recurrences[0].predecessor_occurrence_id == "occ-det-1"
    assert len(engine.custody.corrections) == 1
    assert engine.custody.corrections[0].kind is CorrectionKind.LATE_EVIDENCE
    # efficiency state is intact and never touched custody/verification
    assert engine.efficiency.coverage == 0.87


def test_engine_rejects_non_event_input() -> None:
    engine = ProjectionEngine()

    with pytest.raises(ValueError, match="MaintenanceEvent or a canonical dict"):
        engine.apply("not-an-event")  # type: ignore[arg-type]


def test_engine_accepts_canonical_dict() -> None:
    engine = ProjectionEngine()
    event = _detection("occ-1", "evt-1", event_time_hour=12)
    as_dict = json.loads(event.model_dump_json())

    engine.apply(as_dict)

    assert engine.custody.sequence == 1
    assert engine.custody.occurrence_id == "occ-1"
