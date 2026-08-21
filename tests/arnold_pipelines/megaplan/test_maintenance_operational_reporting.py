"""Focused proof tests for M4 exact-window operational reports (T3).

Covers Plan Step 3: exact UTC half-open reports built from the last closed
Maintenance watermark, persisted immutable sorted input IDs and owner
references, versions, cohort and metric facts, allowed lateness, coverage,
censoring, and the canonical content hash — then the reuse of
:class:`MaintenanceLedger` and :class:`ProjectionEngine` for digest-linked
late corrections, absent-only replay, divergent-identity rejection, and
crash-safe idempotency.

Fail-closed invariants proven here:

* ``window.start`` equals the stored watermark exactly; ``window.end`` is
  exclusive (an instant equal to the end is NOT contained);
* input IDs and owner references are stored sorted and deduplicated; the
  same inputs reproduce the same canonical content hash and a different
  input set changes it;
* missing numerator/denominator stay explicit ``None`` and coverage returns
  ``None`` (never ``0``); unknown and censored counts are retained;
* strict decode rejects unknown fields, a tampered content hash, a window
  that does not open at the watermark, and unsorted inputs;
* the same report reproduces the same event bytes (deterministic replay and
  crash-safe idempotency without caller clocks);
* exact duplicates append at most once (``already_present``) and a divergent
  reuse of the occurrence identity is rejected (``conflict``) without writing;
* late evidence appends a digest-linked correction instead of rewriting the
  prior projection; and the canonical cadence is ``next_three_hour`` with
  ``six_hour_operational`` preserved as the legacy product label.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.maintenance import (
    CANONICAL_CADENCE,
    DEFAULT_ALLOWED_LATENESS_SECONDS,
    LEGACY_CADENCE_ALIAS,
    LEGACY_REPORT_TYPE,
    M4_API,
    MetricFacts,
    OperationalReport,
    REPORT_WINDOW_SECONDS,
    append_operational_report,
    build_operational_report,
    content_digest,
    last_closed_watermark,
    operational_report_to_event,
    read_committed_report_events,
    replay_absent_reports,
    replay_committed_reports,
)
from arnold_pipelines.megaplan.maintenance.events import EventKind
from arnold_pipelines.megaplan.maintenance.identity import (
    EventWindow,
    MaintenanceCodecError,
    OwnerRef,
    UtcTime,
    Watermark,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.ledger import MaintenanceLedger
from arnold_pipelines.megaplan.maintenance.operational_policy import CohortIdentity
from arnold_pipelines.megaplan.maintenance.projections import (
    CorrectionKind,
    ProjectionEngine,
)

UTC = timezone.utc

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FORBIDDEN_STATE_ROOTS = {
    _PROJECT_ROOT,
    Path("/Users/peteromalley/Documents/Arnold"),
    Path(
        "/Users/peteromalley/Documents/.megaplan-worktrees/"
        "runtime-convergence-execution"
    ),
    Path(
        "/Users/peteromalley/Documents/.megaplan-worktrees/"
        "runtime-convergence-r"
    ),
    Path("/workspace/runtime-candidates/arnold-4a830c6ac9"),
    Path("/workspace/runtime-candidates/arnold-4a830c6ac9a0"),
    Path("/workspace/runtime-candidates/astrid-first"),
    Path("/workspace/megaplan-maintenance/Arnold"),
    Path("/workspace/astrid-first-ce15b5a3/astrid"),
}


def _disposable_state_root(tmp_path: Path) -> Path:
    """Return and verify a test-only ledger root under pytest's temp dir."""
    root = tmp_path.resolve()
    assert root != _PROJECT_ROOT
    assert root not in {candidate.resolve() for candidate in _FORBIDDEN_STATE_ROOTS}
    assert root.is_relative_to(tmp_path.resolve())
    return root


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _mark(hour: int, minute: int = 0) -> Watermark:
    return Watermark(datetime(2026, 8, 18, hour, minute, tzinfo=UTC))


def _ref(owner: str, locator: str, digest: str | None = "a" * 64) -> OwnerRef:
    return OwnerRef(owner=owner, locator=locator, digest=digest)


def _report(**overrides: object) -> OperationalReport:
    base: dict[str, object] = {
        "report_id": "rep-1",
        "watermark": _mark(10),
        "input_ids": ["b", "a", "c"],
        "owner_refs": [_ref("wbc", "wbc/1"), _ref("run_authority", "ra/1", "b" * 64)],
        "policy_version": "policy-v1",
        "classifier_version": "cls-v1",
        "metrics": MetricFacts(
            numerator=3, denominator=5, unknown_count=1, censored_count=1
        ),
    }
    base.update(overrides)
    return build_operational_report(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Exact half-open UTC windows from the last closed watermark
# ---------------------------------------------------------------------------


def test_report_window_is_exact_half_open_from_last_closed_watermark() -> None:
    report = _report(watermark=_mark(10))
    assert report.window.start.root == report.watermark.root
    # Window size is the provisional fixed-rate three-hour horizon.
    assert report.window.end.root == _mark(10).root + timedelta(
        seconds=REPORT_WINDOW_SECONDS
    )
    # Half-open: start inclusive, end exclusive.
    assert report.window.contains(_mark(10).root) is True
    assert report.window.contains(_mark(10).root + timedelta(seconds=1)) is True
    assert report.window.contains(report.window.end.root) is False


def test_report_window_end_can_be_supplied_explicitly() -> None:
    report = _report(watermark=_mark(10), window_end=_mark(11))
    assert report.window.end.root == _mark(11).root
    assert report.window.contains(_mark(11).root) is False


def test_report_window_start_must_equal_watermark_at_strict_decode() -> None:
    data = _report().model_dump(mode="json", exclude_none=False)
    data["window"] = {
        "start": _mark(11).root.isoformat(),
        "end": _mark(14).root.isoformat(),
    }
    with pytest.raises(MaintenanceCodecError):
        strict_loads(OperationalReport, data)


# ---------------------------------------------------------------------------
# Immutable sorted inputs and canonical content hash
# ---------------------------------------------------------------------------


def test_input_ids_are_sorted_and_deduplicated() -> None:
    report = _report(input_ids=["b", "a", "c", "a"])
    assert report.input_ids == ("a", "b", "c")
    # The same report built from a different input order is identical.
    other = _report(input_ids=["c", "b", "a", "a"])
    assert report.model_dump(mode="json") == other.model_dump(mode="json")


def test_owner_refs_are_sorted_and_deduplicated() -> None:
    ref_b = _ref("wbc", "wbc/1", "b" * 64)
    ref_a = _ref("run_authority", "ra/1", "a" * 64)
    report = _report(owner_refs=[ref_b, ref_a, ref_b])
    assert report.owner_refs == (ref_a, ref_b)
    other = _report(owner_refs=[ref_a, ref_b, ref_a])
    assert report.model_dump(mode="json") == other.model_dump(mode="json")


def test_unsorted_input_ids_are_rejected_at_strict_decode() -> None:
    data = _report().model_dump(mode="json", exclude_none=False)
    data["input_ids"] = ["c", "a", "b"]
    with pytest.raises(MaintenanceCodecError):
        strict_loads(OperationalReport, data)


def test_content_hash_is_canonical_and_deterministic() -> None:
    assert len(_report().content_hash) == 64
    assert _report().content_hash == _report().content_hash
    # A different input set changes the hash.
    assert _report(input_ids=["x"]).content_hash != _report().content_hash
    assert _report(metrics=MetricFacts(numerator=1, denominator=2)).content_hash != (
        _report().content_hash
    )
    # The hash covers the materialized content, excluding only itself.
    assert content_digest(_report()) == _report().content_hash
    payload = _report().model_dump(mode="json", exclude_none=False)
    assert "content_hash" in payload
    assert payload["content_hash"] == _report().content_hash


def test_duplicate_owner_refs_are_rejected_at_strict_decode() -> None:
    data = _report().model_dump(mode="json", exclude_none=False)
    ref = _ref("wbc", "wbc/1", "a" * 64)
    data["owner_refs"] = [ref.model_dump(mode="json"), ref.model_dump(mode="json")]
    with pytest.raises(MaintenanceCodecError):
        strict_loads(OperationalReport, data)


def test_tampered_content_hash_is_rejected_at_strict_decode() -> None:
    data = _report().model_dump(mode="json", exclude_none=False)
    data["content_hash"] = "f" * 64
    with pytest.raises(MaintenanceCodecError):
        strict_loads(OperationalReport, data)


def test_unknown_fields_are_rejected_at_strict_decode() -> None:
    data = _report().model_dump(mode="json", exclude_none=False)
    data["invented_authority"] = True
    with pytest.raises(MaintenanceCodecError):
        strict_loads(OperationalReport, data)


def test_legacy_cadence_alias_normalizes_to_canonical_cadence() -> None:
    report = _report(cadence=LEGACY_CADENCE_ALIAS)
    assert report.cadence == CANONICAL_CADENCE
    assert report.report_type == LEGACY_REPORT_TYPE


def test_foreign_cadence_is_rejected() -> None:
    with pytest.raises(ValueError):
        _report(cadence="daily")


# ---------------------------------------------------------------------------
# Metric facts: explicit missing values, coverage, censoring
# ---------------------------------------------------------------------------


def test_missing_denominator_stays_explicit_never_green() -> None:
    report = _report(metrics=MetricFacts(numerator=3, denominator=None))
    assert report.metrics.missing_denominator is True
    assert report.metrics.coverage is None


def test_missing_numerator_stays_explicit_never_green() -> None:
    report = _report(metrics=MetricFacts(numerator=None, denominator=5))
    assert report.metrics.coverage is None


def test_zero_denominator_coverage_is_none_not_zero() -> None:
    report = _report(metrics=MetricFacts(numerator=0, denominator=0))
    assert report.metrics.coverage is None


def test_unknown_and_censored_counts_are_retained() -> None:
    report = _report(
        metrics=MetricFacts(
            numerator=3, denominator=8, unknown_count=2, censored_count=3
        )
    )
    assert report.metrics.unknown_count == 2
    assert report.metrics.censored_count == 3
    assert report.metrics.coverage == 3 / 8


def test_numerator_exceeding_denominator_is_rejected() -> None:
    with pytest.raises(ValueError):
        MetricFacts(numerator=9, denominator=5)


def test_allowed_lateness_is_recorded_and_report_only() -> None:
    assert _report().allowed_lateness_seconds == DEFAULT_ALLOWED_LATENESS_SECONDS
    assert _report(allowed_lateness_seconds=900).allowed_lateness_seconds == 900


def test_cohort_facts_round_trip() -> None:
    cohort = CohortIdentity(environment="production", stage="wbc_gate")
    report = _report(cohort=cohort)
    assert report.cohort == cohort
    decoded = strict_loads(
        OperationalReport, report.model_dump(mode="json", exclude_none=False)
    )
    assert decoded.cohort == cohort


# ---------------------------------------------------------------------------
# Report → strict event
# ---------------------------------------------------------------------------


def test_report_to_event_is_strict_efficiency_analysis_with_full_facts() -> None:
    report = _report()
    event = operational_report_to_event(report)
    assert event.event_kind is EventKind.EFFICIENCY_ANALYSIS
    assert event.occurrence_id == report.report_id
    assert event.idempotency_key == report.report_id
    assert event.window == report.window
    assert event.watermark == report.watermark
    assert event.payload.product == CANONICAL_CADENCE
    assert event.payload.coverage_denominator == 5
    assert event.payload.covered_count == 3
    # Full immutable facts ride in the extensions map (the only escape hatch).
    ext = event.extensions.root
    assert ext["report_id"] == "rep-1"
    assert ext["report_type"] == LEGACY_REPORT_TYPE
    assert ext["cadence"] == CANONICAL_CADENCE
    assert ext["input_ids"] == ["a", "b", "c"]
    assert ext["policy_version"] == "policy-v1"
    assert ext["classifier_version"] == "cls-v1"
    assert ext["allowed_lateness_seconds"] == DEFAULT_ALLOWED_LATENESS_SECONDS
    assert ext["metrics"]["unknown_count"] == 1
    assert ext["metrics"]["censored_count"] == 1
    assert ext["content_hash"] == report.content_hash
    # Owner references are embedded as immutable locator-only references.
    assert len(ext["owner_refs"]) == 2
    assert len(event.resolution_proof) == 2


def test_report_to_event_is_deterministic_without_caller_clocks() -> None:
    event = operational_report_to_event(_report())
    event_again = operational_report_to_event(_report())
    assert canonical_digest(event) == canonical_digest(event_again)
    # Default observation instant is the exact window close (on-time report).
    assert event.observed_at.root == _report().window.end.root
    assert event.lateness.value == "on_time"


def test_report_to_event_round_trips_through_strict_codec() -> None:
    event = operational_report_to_event(_report())
    decoded = strict_loads(
        type(event), json_payload := event.model_dump(mode="json", exclude_none=False)
    )
    assert canonical_digest(decoded) == canonical_digest(event)
    assert decoded.extensions.root == event.extensions.root


# ---------------------------------------------------------------------------
# Persistence through MaintenanceLedger + ProjectionEngine
# ---------------------------------------------------------------------------


def test_append_persists_report_and_advances_efficiency_projection(
    tmp_path: Path,
) -> None:
    ledger = MaintenanceLedger(_disposable_state_root(tmp_path))
    engine = ProjectionEngine()
    result = append_operational_report(ledger, _report(), engine=engine)
    assert result["append_status"] == "appended"
    assert len(result["event_digest"]) == 64
    assert result["projection"]["efficiency_sequence"] == 1
    assert result["projection"]["efficiency_watermark"] == _mark(10).root.isoformat()
    # The event is committed to the ledger and readable back.
    committed = read_committed_report_events(ledger)
    assert len(committed) == 1
    assert committed[0]["occurrence_id"] == "rep-1"
    assert committed[0]["payload"]["kind"] == "efficiency_analysis"
    assert engine.efficiency.window_start == _mark(10).root.isoformat()
    assert engine.efficiency.window_end == (
        _mark(10).root + timedelta(seconds=REPORT_WINDOW_SECONDS)
    ).isoformat()
    assert engine.efficiency.coverage == 3 / 5


def test_append_exact_duplicate_is_idempotent(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(_disposable_state_root(tmp_path))
    engine = ProjectionEngine()
    first = append_operational_report(ledger, _report(), engine=engine)
    second = append_operational_report(ledger, _report(), engine=engine)
    assert first["append_status"] == "appended"
    assert second["append_status"] == "already_present"
    assert first["event_digest"] == second["event_digest"]
    assert len(read_committed_report_events(ledger)) == 1
    assert engine.efficiency.sequence == 1


def test_append_divergent_identity_is_rejected_without_write(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(_disposable_state_root(tmp_path))
    assert append_operational_report(ledger, _report())["append_status"] == "appended"
    divergent = _report(
        report_id="rep-1", input_ids=["x"], metrics=MetricFacts(numerator=9, denominator=9)
    )
    result = append_operational_report(ledger, divergent)
    assert result["append_status"] == "conflict"
    # Nothing was written: the ledger still holds exactly one event.
    assert len(read_committed_report_events(ledger)) == 1


def test_last_closed_watermark_reads_the_ledger(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(_disposable_state_root(tmp_path))
    assert last_closed_watermark(ledger) is None
    append_operational_report(ledger, _report(watermark=_mark(10)))
    append_operational_report(ledger, _report(report_id="rep-2", watermark=_mark(13)))
    assert last_closed_watermark(ledger).root == _mark(13).root


def test_late_evidence_appends_digest_linked_correction(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(_disposable_state_root(tmp_path))
    engine = ProjectionEngine()
    first = append_operational_report(
        ledger, _report(report_id="rep-1", watermark=_mark(10)), engine=engine
    )
    assert first["projection"]["corrections"] == []
    prior_digest = engine.efficiency.output_digest
    # A late report for a LATER window arrives with observed_at before its
    # own watermark (late evidence) — it must amend, never rewrite.
    late = _report(report_id="rep-2", watermark=_mark(13))
    late_result = append_operational_report(
        ledger,
        late,
        engine=engine,
        observed_at=_mark(13).root - timedelta(seconds=1),
    )
    corrections = late_result["projection"]["corrections"]
    assert len(corrections) == 1
    assert corrections[0]["kind"] == CorrectionKind.LATE_EVIDENCE.value
    assert corrections[0]["corrected_sequence"] == 1
    assert corrections[0]["prior_output_digest"] == prior_digest
    # The prior result is linked to, not overwritten.
    assert engine.efficiency.corrections[0].prior_output_digest == prior_digest


def test_replay_absent_reports_appends_only_absent(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(_disposable_state_root(tmp_path))
    first = _report(report_id="rep-1", watermark=_mark(10))
    second = _report(report_id="rep-2", watermark=_mark(13))
    append_operational_report(ledger, first)
    replay = replay_absent_reports(ledger, [first, second])
    assert replay["appended_count"] == 1
    assert replay["already_present_count"] == 1
    assert replay["conflict_count"] == 0
    assert {outcome["outcome"] for outcome in replay["outcomes"]} == {
        "already_present",
        "appended",
    }


def test_replay_absent_reports_rejects_divergent_identity(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(_disposable_state_root(tmp_path))
    first = _report(report_id="rep-1", watermark=_mark(10))
    append_operational_report(ledger, first)
    divergent = _report(
        report_id="rep-1", watermark=_mark(10), metrics=MetricFacts(numerator=9, denominator=9)
    )
    replay = replay_absent_reports(ledger, [divergent])
    assert replay["conflict_count"] == 1
    assert replay["outcomes"][0]["outcome"] == "conflict"
    assert len(read_committed_report_events(ledger)) == 1


def test_crash_reopen_replays_at_most_once(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(_disposable_state_root(tmp_path))
    reports = [
        _report(report_id="rep-1", watermark=_mark(10)),
        _report(report_id="rep-2", watermark=_mark(13)),
    ]
    for report in reports:
        append_operational_report(ledger, report)
    # Simulate a crash + reopen with a fresh ledger instance on the same root.
    reopened = MaintenanceLedger(_disposable_state_root(tmp_path))
    replay = replay_absent_reports(reopened, reports)
    assert replay["already_present_count"] == 2
    assert replay["appended_count"] == 0
    # Deterministic rebuild from the committed stream reproduces the state.
    engine = replay_committed_reports(reopened)
    assert engine.efficiency.sequence == 2
    assert engine.efficiency.watermark == _mark(13).root.isoformat()


def test_replay_committed_reports_is_deterministic(tmp_path: Path) -> None:
    ledger = MaintenanceLedger(_disposable_state_root(tmp_path))
    append_operational_report(ledger, _report(report_id="rep-1", watermark=_mark(10)))
    append_operational_report(ledger, _report(report_id="rep-2", watermark=_mark(13)))
    first = replay_committed_reports(ledger)
    second = replay_committed_reports(ledger)
    assert first.efficiency.output_digest == second.efficiency.output_digest
    assert first.efficiency.sequence == second.efficiency.sequence == 2
    # The engine's digest-linked correction machinery stays available: a
    # second rebuild of the same stream reproduces identical digests.
    assert first.efficiency.corrections == second.efficiency.corrections


# ---------------------------------------------------------------------------
# Package export surface
# ---------------------------------------------------------------------------


def test_operational_reporting_names_resolve_through_m4_api() -> None:
    for name in (
        "CANONICAL_CADENCE",
        "MetricFacts",
        "OperationalReport",
        "append_operational_report",
        "build_operational_report",
        "content_digest",
        "last_closed_watermark",
        "operational_report_to_event",
        "read_committed_report_events",
        "replay_absent_reports",
        "replay_committed_reports",
    ):
        assert name in M4_API, name
        # Resolving through the lazy seam must yield the source object.
        from arnold_pipelines.megaplan import maintenance as maintenance_pkg

        assert getattr(maintenance_pkg, name) is getattr(
            __import__(
                "arnold_pipelines.megaplan.maintenance.operational_reporting",
                fromlist=[name],
            ),
            name,
        ), name


def test_reference_only_surface_never_imports_owner_stores() -> None:
    import ast

    source = Path(
        "arnold_pipelines/megaplan/maintenance/operational_reporting.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    for forbidden in (
        "repair_requests",
        "simple_fixer",
        "transition_writer",
        "repair_queue",
        "lease_store",
        "action_validator",
        "controlled_writers",
    ):
        assert not any(forbidden in name for name in imported), (
            f"operational_reporting must never import owner seam {forbidden!r}"
        )


# ---------------------------------------------------------------------------
# M4 (T13): golden replay timelines — every fixture runs twice and the two
# traces (included IDs, hashes, projections, corrections, metrics) must match
# ---------------------------------------------------------------------------


#: Ordered steps for each golden timeline.  "append" persists one report
#: through the ledger + projection engine; "reopen" simulates a crash by
#: re-instantiating the ledger over the same root; "replay_absent" re-runs
#: absent-only replay; "rebuild" deterministically rebuilds the projection.
GOLDEN_REPORT_TIMELINES: dict[str, list[dict[str, object]]] = {
    "exact_boundaries": [
        {
            "action": "append",
            "report": {"report_id": "gold-1", "watermark": _mark(10)},
            "expected_append_status": "appended",
            "expected_corrections": 0,
        },
        {
            # The next window opens EXACTLY at the last closed watermark.
            "action": "append",
            "report": {
                "report_id": "gold-2",
                "watermark": _mark(13),
                "window_end": _mark(16),
            },
            "expected_append_status": "appended",
            "expected_corrections": 0,
        },
        {"action": "rebuild"},
    ],
    "skew_and_lateness": [
        {
            "action": "append",
            "report": {"report_id": "gold-1", "watermark": _mark(10)},
            # Exact window close -> on-time evidence.
            "observed_at": _mark(13).root,
            "expected_append_status": "appended",
            "expected_corrections": 0,
        },
        {
            # Observation EXACTLY at the stored watermark is late evidence:
            # it appends a digest-linked correction, never a rewrite.
            "action": "append",
            "report": {
                "report_id": "gold-2",
                "watermark": _mark(13),
                "window_end": _mark(16),
            },
            "observed_at": _mark(13).root,
            "expected_append_status": "appended",
            "expected_corrections": 1,
        },
        {
            # One microsecond after the watermark is on-time evidence.
            "action": "append",
            "report": {
                "report_id": "gold-3",
                "watermark": _mark(16),
                "window_end": _mark(19),
            },
            "observed_at": _mark(16).root + timedelta(microseconds=1),
            "expected_append_status": "appended",
            # Cumulative projection corrections (gold-2's late evidence is
            # linked, never rewritten; gold-3 adds no new correction).
            "expected_corrections": 1,
        },
        {"action": "rebuild"},
    ],
    "late_out_of_order_duplicate": [
        {
            "action": "append",
            "report": {"report_id": "gold-1", "watermark": _mark(10)},
            "expected_append_status": "appended",
            "expected_corrections": 0,
        },
        {
            # Exact duplicate: at most once, nothing new is written.
            "action": "append",
            "report": {"report_id": "gold-1", "watermark": _mark(10)},
            "expected_append_status": "already_present",
            "expected_corrections": 0,
        },
        {
            # Late (observed at its own watermark) -> digest-linked correction.
            "action": "append",
            "report": {
                "report_id": "gold-2",
                "watermark": _mark(13),
                "window_end": _mark(16),
            },
            "observed_at": _mark(13).root,
            "expected_append_status": "appended",
            # Cumulative projection corrections (gold-2's late evidence is
            # linked; gold-3 appends no new correction).
            "expected_corrections": 1,
        },
        {
            # Out-of-order evidence arrival: the later window appends as its
            # own exact window (no history is rewritten).
            "action": "append",
            "report": {
                "report_id": "gold-3",
                "watermark": _mark(16),
                "window_end": _mark(19),
            },
            "expected_append_status": "appended",
            "expected_corrections": 1,
        },
        {
            "action": "replay_absent",
            "reports": [
                {"report_id": "gold-1", "watermark": _mark(10)},
                {
                    "report_id": "gold-2",
                    "watermark": _mark(13),
                    "window_end": _mark(16),
                },
                {
                    "report_id": "gold-3",
                    "watermark": _mark(16),
                    "window_end": _mark(19),
                },
            ],
            "expected_appended": 0,
            "expected_already_present": 2,
            # gold-2 was committed as LATE evidence; replayed with the default
            # on-time observation it is a divergent reuse (same identity,
            # different event bytes) -> conflict, never a rewrite.
            "expected_conflict": 1,
        },
        {
            # Divergent reuse of the same identity: rejected, nothing written.
            "action": "append",
            "report": {
                "report_id": "gold-2",
                "watermark": _mark(13),
                "window_end": _mark(16),
                "metrics": MetricFacts(numerator=9, denominator=9),
            },
            "expected_append_status": "conflict",
            "expected_corrections": 0,
            "engine": False,
        },
        {"action": "rebuild"},
    ],
    "censoring": [
        {
            "action": "append",
            "report": {
                "report_id": "gold-1",
                "watermark": _mark(10),
                "metrics": MetricFacts(
                    numerator=1, denominator=2, unknown_count=0, censored_count=1
                ),
            },
            "expected_append_status": "appended",
            "expected_corrections": 0,
        },
        {
            "action": "append",
            "report": {
                "report_id": "gold-2",
                "watermark": _mark(13),
                "window_end": _mark(16),
                "metrics": MetricFacts(
                    numerator=3, denominator=8, unknown_count=2, censored_count=3
                ),
            },
            "expected_append_status": "appended",
            "expected_corrections": 0,
        },
        {
            # A missing denominator stays explicit None; coverage is None,
            # never 0, and never a green signal.
            "action": "append",
            "report": {
                "report_id": "gold-3",
                "watermark": _mark(16),
                "window_end": _mark(19),
                "metrics": MetricFacts(
                    numerator=3, denominator=None, unknown_count=1, censored_count=0
                ),
            },
            "expected_append_status": "appended",
            "expected_corrections": 0,
        },
        {"action": "rebuild"},
    ],
    "crash_replay": [
        {
            "action": "append",
            "report": {"report_id": "gold-1", "watermark": _mark(10)},
            "expected_append_status": "appended",
            "expected_corrections": 0,
        },
        {
            "action": "append",
            "report": {"report_id": "gold-2", "watermark": _mark(13)},
            "expected_append_status": "appended",
            "expected_corrections": 0,
        },
        # Crash: a fresh ledger instance over the same root.
        {"action": "reopen"},
        {
            "action": "replay_absent",
            "reports": [
                {"report_id": "gold-1", "watermark": _mark(10)},
                {"report_id": "gold-2", "watermark": _mark(13)},
            ],
            "expected_appended": 0,
            "expected_already_present": 2,
            "expected_conflict": 0,
        },
        {"action": "rebuild"},
        # Rebuild again: the committed stream reproduces identical digests.
        {"action": "rebuild"},
    ],
}


def _run_golden_report_timeline(
    root: Path, steps: list[dict[str, object]]
) -> tuple[tuple[object, ...], ...]:
    """Execute one golden timeline over a fresh ledger and return a
    deterministic trace of every observable (included IDs, content hashes,
    append outcomes, event digests, projection state, corrections, metrics)."""
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    trace: list[tuple[object, ...]] = []
    for step in steps:
        action = step["action"]
        if action == "append":
            report = _report(**step["report"])  # type: ignore[arg-type]
            observed_at = step.get("observed_at")
            use_engine = step.get("engine", True)
            result = append_operational_report(
                ledger,
                report,
                engine=engine if use_engine else None,
                observed_at=observed_at,
            )
            status = result["append_status"]
            expected_status = step["expected_append_status"]
            assert status == expected_status, (
                f"{step['report'].get('report_id')}: expected "
                f"{expected_status!r}, got {status!r}"
            )
            projection = result.get("projection") or {}
            corrections = projection.get("corrections") or []
            expected_corrections = step.get("expected_corrections", 0)
            assert len(corrections) == expected_corrections, (
                f"{step['report'].get('report_id')}: expected "
                f"{expected_corrections} corrections, got {len(corrections)}"
            )
            trace.append(
                (
                    "append",
                    result["report_id"],
                    tuple(report.input_ids),
                    report.content_hash,
                    status,
                    result["event_digest"],
                    projection.get("efficiency_sequence"),
                    projection.get("efficiency_output_digest"),
                    projection.get("efficiency_watermark"),
                    tuple(
                        (
                            correction["kind"],
                            correction.get("prior_output_digest"),
                        )
                        for correction in corrections
                    ),
                    report.metrics.model_dump(mode="json"),
                )
            )
        elif action == "reopen":
            ledger = MaintenanceLedger(root)
            trace.append(("reopen",))
        elif action == "replay_absent":
            reports = [
                _report(**item) for item in step["reports"]  # type: ignore[arg-type]
            ]
            replay = replay_absent_reports(ledger, reports)
            assert replay["appended_count"] == step.get("expected_appended", 0)
            assert replay["already_present_count"] == step.get(
                "expected_already_present", 0
            )
            assert replay["conflict_count"] == step.get("expected_conflict", 0)
            trace.append(
                (
                    "replay_absent",
                    replay["appended_count"],
                    replay["already_present_count"],
                    replay["conflict_count"],
                )
            )
        elif action == "rebuild":
            rebuilt = replay_committed_reports(ledger)
            trace.append(
                (
                    "rebuild",
                    rebuilt.efficiency.sequence,
                    rebuilt.efficiency.watermark,
                    rebuilt.efficiency.output_digest,
                )
            )
        else:  # pragma: no cover - the table is closed
            raise AssertionError(f"unknown golden timeline action {action!r}")
    return tuple(trace)


@pytest.mark.parametrize("timeline_name", sorted(GOLDEN_REPORT_TIMELINES))
def test_golden_report_timeline_replays_identically(
    tmp_path: Path, timeline_name: str
) -> None:
    """Run each golden timeline twice in fresh roots and require identical
    traces: included IDs, content hashes, event digests, projection state,
    corrections, and retained metric facts are all deterministic."""
    steps = GOLDEN_REPORT_TIMELINES[timeline_name]
    first = _run_golden_report_timeline(tmp_path / f"{timeline_name}-a", steps)
    second = _run_golden_report_timeline(tmp_path / f"{timeline_name}-b", steps)
    assert first == second, (
        f"golden timeline {timeline_name!r} must replay to identical included "
        "IDs, hashes, projections, and events"
    )


def test_golden_exact_boundary_and_skew_edge_semantics() -> None:
    """The half-open window and the watermark lateness boundary are exact:
    an instant equal to the window end is NOT contained, and an observation
    exactly at the stored watermark is late while one microsecond later is on
    time (the skew edge that drives corrections)."""
    report = _report(watermark=_mark(10), window_end=_mark(13))
    assert report.window.contains(_mark(10).root) is True
    assert report.window.contains(_mark(13).root) is False

    def _lateness(observed_at: datetime) -> str:
        return operational_report_to_event(
            report, observed_at=observed_at
        ).lateness.value

    assert _lateness(_mark(13).root) == "on_time"
    assert _lateness(_mark(10).root) == "late"
    assert _lateness(_mark(10).root + timedelta(microseconds=1)) == "on_time"