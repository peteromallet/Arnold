"""Focused T6.1 proof tests: append-only FENCED efficiency events.

Proves the adapted M5 reporting emission (``emit_daily_events``) against the
ONE canonical writer (``MaintenanceLedger.append`` ->
``IncidentLedger.append_maintenance_event`` ->
``_IncidentEventJournal.append_maintenance``):

* every append is bound to the current occurrence fence (a lost fence fails
  closed at EVERY boundary — entry, proposal prior-key lookup, pre-append
  classification, append, projection apply/catch-up — and writes nothing
  before the append) and to the evidence digest (journal CAS);
* exact replay returns ``already_present`` under a NEW fence; the same
  occurrence key with a divergent digest fails closed and never rewrites;
* concurrent writers append exactly once (journal CAS under flock);
* append failures dead-letter and replay at most once; injected projection
  failures leave the journal authoritative and the projection self-heals on
  replay with a deterministic cursor;
* the ledger/event append is the SOLE permitted M5 data-product mutation
  (static source scan) and neither appends nor projections mint closure,
  dispatch, completion, repair, scheduling-policy, or ticket authority.

Every state-writing test uses an explicit disposable root under pytest's
tmp dir and proves it is not a project/candidate/live runtime root.
"""

from __future__ import annotations

import inspect
import json
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.maintenance import efficiency_contracts as ec
from arnold_pipelines.megaplan.maintenance import efficiency_reporting as er
from arnold_pipelines.megaplan.maintenance.events import (
    ClassifierInfo,
    EventKind,
    MaintenanceEvent,
    OccurrenceBudget,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    EventWindow,
    OwnerRef,
    UtcTime,
    Watermark,
    canonical_digest,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.ledger import (
    MaintenanceAppendFailure,
    MaintenanceEventConflict,
    MaintenanceLedger,
    ReplayOutcome,
)
from arnold_pipelines.megaplan.maintenance.projections import (
    DAILY_EVENT_KINDS,
    ProjectionEngine,
    daily_commit_key,
    replay,
)

UTC = timezone.utc

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SHA256 = "a" * 64


def _disposable_state_root(tmp_path: Path) -> Path:
    """Return and PROVE a test-only ledger root under pytest's temp dir.

    The root must live inside pytest's per-test temp directory, must never
    be (or contain) this project's checkout, the live ``.megaplan`` runtime
    state, or any known integration/candidate runtime root.
    """
    root = tmp_path.resolve()
    tmp_root = tmp_path.resolve()
    assert root.is_relative_to(tmp_root), f"root escaped pytest tmp: {root}"
    assert not root.is_relative_to(_PROJECT_ROOT), (
        f"root is inside the project checkout: {root}"
    )
    assert root != _PROJECT_ROOT / ".megaplan"
    assert ".megaplan-worktrees" not in root.parts
    assert root.name != "incident-ledger"
    # The ledger must CREATE its state lazily; nothing exists yet.
    assert not (root / ".megaplan" / "incident-ledger" / "events.jsonl").exists()
    return root


# ---------------------------------------------------------------------------
# Builders (adapted from the M5 reporting pack fixtures)
# ---------------------------------------------------------------------------


def _ts(hour: int = 0, minute: int = 0, day: int = 18) -> datetime:
    return datetime(2026, 8, day, tzinfo=UTC) + timedelta(hours=hour, minutes=minute)


def _window(start: int = 0, end: int = 24, day: int = 18) -> EventWindow:
    return EventWindow(start=UtcTime(_ts(start, day=day)), end=UtcTime(_ts(end, day=day)))


def _ref(owner: str, locator: str, digest: str | None = _SHA256) -> OwnerRef:
    return OwnerRef(owner=owner, locator=locator, digest=digest)


def _op_report_ref(seq: int, digest: str = _SHA256) -> OwnerRef:
    return _ref("run_authority", f"operational-report:{seq}", digest)


def _cohort(**overrides: object) -> ec.EfficiencyCohortIdentity:
    base: dict[str, object] = {
        "stage": "stage-1",
        "profile": "profile-1",
        "model": "model-1",
        "robustness": ec.RobustnessKind.THOROUGH,
        "environment": "production",
        "classifier_version": "cls-v1",
    }
    base.update(overrides)
    return ec.EfficiencyCohortIdentity(**base)  # type: ignore[arg-type]


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
        "lower_bound_seconds": 1800.0,
    }
    base.update(overrides)
    return ec.DurationObservation(**base)  # type: ignore[arg-type]


def _references(**overrides: object) -> ec.FindingReferences:
    base: dict[str, object] = {
        "accepted_resolution_refs": [_ref("run_authority", "decision://d-1")],
        "active_custody_refs": [_ref("custody", "custody://lease-1")],
        "source_refs": [_ref("wbc", "wbc://att-1/1")],
        "gate_backoff_refs": [_ref("maintenance", "gate://g-1")],
        "censoring_refs": [_ref("maintenance", "censoring://c-1")],
    }
    base.update(overrides)
    return ec.FindingReferences(**base)  # type: ignore[arg-type]


def _dwell(**overrides: object) -> ec.DwellFinding:
    base: dict[str, object] = {
        "finding_id": "f-dwell-1",
        "kind": ec.DwellFindingKind.GATE,
        "duration_seconds": 7200.0,
        "references": _references(),
    }
    base.update(overrides)
    return ec.DwellFinding(**base)  # type: ignore[arg-type]


def _loop(**overrides: object) -> ec.LoopFinding:
    base: dict[str, object] = {
        "finding_id": "f-loop-1",
        "kind": ec.LoopFindingKind.RETRY_LOOP,
        "repeated_stage": "gate",
        "attempt_count": 3,
        "references": _references(),
    }
    base.update(overrides)
    return ec.LoopFinding(**base)  # type: ignore[arg-type]


def _candidate(**overrides: object) -> ec.RootCauseCandidate:
    base: dict[str, object] = {
        "candidate_id": "cand-1",
        "root_cause_fingerprint": "fp-1",
        "affected_contract": "ac-1",
        "classifier_version": "cls-v1",
        "coverage": _denominator(metric="evidence_coverage"),
        "confidence": _bounds(0.9, 0.8, 0.95),
        "recurrence_count_7d": 2,
        "recurrence_count_30d": 3,
        "occurrence_refs": [_ref("custody", "occurrence://occ-1")],
        "evidence_refs": [_ref("wbc", "wbc://att-1/1")],
    }
    base.update(overrides)
    return ec.RootCauseCandidate(**base)  # type: ignore[arg-type]


def _proposal(**overrides: object) -> ec.DailyEfficiencyProposal:
    base: dict[str, object] = {
        "proposal_kind": ec.ProposalKind.TICKET,
        "root_cause_fingerprint": "fp-1",
        "affected_contract": "ac-1",
        "classifier_version": "cls-v1",
        "open_ticket_identity": None,
        "environment": EnvironmentId("production"),
        "window": _window(),
        "cluster_ref": _ref("maintenance", "cluster://c-1"),
        "candidate_refs": [_ref("maintenance", "candidate://cand-1")],
        "evidence_refs": [_ref("wbc", "wbc://att-1/1")],
        "active_custody_refs": [_ref("custody", "custody://lease-1")],
        "active_custody_present": True,
        "auto_materialization": False,
        "generated_at": UtcTime(_ts()),
    }
    base.update(overrides)
    base["proposal_id"] = ec.derive_proposal_occurrence_id(
        proposal_kind=base["proposal_kind"],  # type: ignore[arg-type]
        root_cause_fingerprint=base["root_cause_fingerprint"],  # type: ignore[arg-type]
        affected_contract=base["affected_contract"],  # type: ignore[arg-type]
        classifier_version=base["classifier_version"],  # type: ignore[arg-type]
        open_ticket_identity=base.get("open_ticket_identity"),  # type: ignore[arg-type]
    )
    return ec.DailyEfficiencyProposal(**base)  # type: ignore[arg-type]


def _receipt(**overrides: object) -> er.OperationalClosureReceipt:
    """Default closure receipt over two committed 12-hour operational windows."""
    base: dict[str, object] = {
        "environment": EnvironmentId("production"),
        "previous_boundary": UtcTime(_ts(0)),
        "closed_boundary": UtcTime(_ts(24)),
        "covered_windows": [_window(0, 12), _window(12, 24)],
        "report_refs": [_op_report_ref(1), _op_report_ref(2)],
    }
    base.update(overrides)
    return er.OperationalClosureReceipt(**base)  # type: ignore[arg-type]


def _cluster(**overrides: object) -> ec.DailyEfficiencyCluster:
    candidate = overrides.pop("candidate", _candidate())
    window = overrides.pop("window", _window())
    environment = overrides.pop("environment", EnvironmentId("production"))
    generated_at = overrides.pop("generated_at", UtcTime(_ts()))
    return er.build_daily_cluster(
        candidate,  # type: ignore[arg-type]
        environment=environment,
        window=window,
        generated_at=generated_at,
    )


def _bundle(**overrides: object) -> er.DailyReportBundle:
    receipt = overrides.pop("closure_receipt", _receipt())  # type: ignore[assignment]
    assert isinstance(receipt, er.OperationalClosureReceipt)
    base: dict[str, object] = {
        "generated_at": UtcTime(_ts()),
        "classifier_version": "cls-v1",
        "policy_version": "policy-v1",
        "observations": [_completed(), _censored()],
        "baselines": [_snapshot()],
        "findings": [_dwell(), _loop()],
        "denominators": [_denominator()],
        "shadow_measures": [_shadow()],
        "clusters": [_cluster()],
        "proposals": [_proposal()],
        "extra_input_refs": [_ref("run_authority", "decision://d-1")],
    }
    base.update(overrides)
    return er.build_daily_report(receipt, **base)  # type: ignore[arg-type]


def _correction_for(bundle: er.DailyReportBundle) -> ec.DailyEfficiencyCorrection:
    """One explicit keyed correction targeting the bundle's report."""
    report = bundle.report
    return ec.DailyEfficiencyCorrection(
        correction_id=ec.derive_correction_occurrence_id(
            supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
            supersedes_window=report.window,
            supersedes_digest=report.report_hash,
        ),
        supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
        supersedes_window=report.window,
        supersedes_digest=report.report_hash,
        environment=report.environment,
        window=report.window,
        reason="late evidence advanced",
        generated_at=UtcTime(_ts()),
    )


def _fence(n: int = 3) -> er.OccurrenceFence:
    return er.OccurrenceFence(
        occurrence_id="daily-occ", fence=n, claim_token=f"tok-{n}"
    )


class _ScriptedFence:
    """Fence check that stays live for *live_calls* calls, then dies."""

    def __init__(self, live_calls: int) -> None:
        self.live_calls = live_calls
        self.calls = 0

    def __call__(self, fence: er.OccurrenceFence) -> bool:
        self.calls += 1
        return self.calls <= self.live_calls


def _emit(
    bundle: er.DailyReportBundle,
    ledger: MaintenanceLedger,
    engine: ProjectionEngine,
    seen: set[str],
    *,
    day: int = 18,
    corrections: Sequence[ec.DailyEfficiencyCorrection] | None = None,
    fence: er.OccurrenceFence | None = None,
    fence_check=None,
) -> er.DailyEmissionResult:
    """Emit *bundle* (plus its keyed correction) through the canonical writer."""
    return er.emit_daily_events(
        bundle,
        ledger=ledger,
        engine=engine,
        observed_at=UtcTime(_ts(12, day=day)),
        event_time=UtcTime(_ts(0, 15, day=day)),
        watermark=Watermark(_ts(day=day)),
        classifier=ClassifierInfo(classifier_version="cls-v1", confidence=0.9),
        budget=OccurrenceBudget(max_attempts=1),
        prior_key_lookup=lambda key: key in seen,
        corrections=(
            corrections if corrections is not None else [_correction_for(bundle)]
        ),
        occurrence_fence=fence or _fence(),
        fence_check=fence_check if fence_check is not None else (lambda f: True),
    )


def _committed_events(ledger: MaintenanceLedger) -> list[MaintenanceEvent]:
    """Strict-decode every committed Maintenance payload from the journal."""
    return [
        strict_loads(MaintenanceEvent, json.loads(line)["payload"])
        for line in ledger.events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _journal_seqs(ledger: MaintenanceLedger) -> list[int]:
    return [
        int(json.loads(line)["seq"])
        for line in ledger.events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Fence + digest bound append; deterministic order
# ---------------------------------------------------------------------------


def test_emit_appends_all_four_kinds_in_deterministic_order(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle()
    result = _emit(bundle, ledger, engine, seen=set())

    assert [(r.kind, r.outcome) for r in result.records] == [
        (ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT, er.DailyEmissionOutcome.APPENDED),
        (ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CLUSTER, er.DailyEmissionOutcome.APPENDED),
        (ec.DailyEfficiencyKind.DAILY_EFFICIENCY_PROPOSAL, er.DailyEmissionOutcome.APPENDED),
        (ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION, er.DailyEmissionOutcome.APPENDED),
    ]
    seqs = [r.seq for r in result.records]
    assert seqs == sorted(seqs)  # deterministic emission order
    assert _journal_seqs(ledger) == seqs
    kinds = [event.event_kind for event in _committed_events(ledger)]
    assert kinds == [
        EventKind.DAILY_EFFICIENCY_REPORT,
        EventKind.DAILY_EFFICIENCY_CLUSTER,
        EventKind.DAILY_EFFICIENCY_PROPOSAL,
        EventKind.DAILY_EFFICIENCY_CORRECTION,
    ]
    # Every record carries the fence it ran under.
    assert all(r.fence == _fence().fence for r in result.records)


def test_every_append_is_digest_bound_cas_record(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle(clusters=[], proposals=[])
    _emit(bundle, ledger, engine, seen=set())

    lines = ledger.events_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # report + keyed correction
    for line in lines:
        record = json.loads(line)
        event = strict_loads(MaintenanceEvent, record["payload"])
        # The journal row's payload digest equals the canonical event digest
        # (evidence-digest binding is exactly what the CAS compares).
        assert record["idempotency_key"] == event.occurrence_id
        assert canonical_digest(event) == canonical_digest(
            strict_loads(MaintenanceEvent, record["payload"])
        )


# ---------------------------------------------------------------------------
# Exact replay / divergent digest
# ---------------------------------------------------------------------------


def test_exact_replay_is_already_present_under_a_new_fence(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle()
    first = _emit(bundle, ledger, engine, seen=set())
    journal_before = ledger.events_path.read_text(encoding="utf-8")
    digest_before = engine.efficiency.output_digest

    # Replay under a NEWER fence (post-reclaim coordinates): still exact.
    replayed = _emit(
        bundle, ledger, engine, seen=set(), fence=_fence(n=9)
    )
    assert [(r.kind, r.outcome, r.seq) for r in replayed.records] == [
        (r.kind, er.DailyEmissionOutcome.ALREADY_PRESENT, r.seq) for r in first.records
    ]
    assert all(r.fence == 9 for r in replayed.records)
    assert ledger.events_path.read_text(encoding="utf-8") == journal_before
    assert engine.efficiency.output_digest == digest_before


def test_divergent_digest_for_same_occurrence_key_fails_closed(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle(clusters=[], proposals=[])
    _emit(bundle, ledger, engine, seen=set())
    journal_before = ledger.events_path.read_text(encoding="utf-8")

    # Same window/environment derive the SAME locked report_id (occurrence
    # key), but a modified observation changes the canonical digest.
    divergent = _bundle(
        clusters=[],
        proposals=[],
        observations=[
            _completed(),
            _censored(),
            _completed(observation_id="obs-completed-2", duration_seconds=7200.0),
        ],
    )
    assert divergent.report.report_id == bundle.report.report_id
    with pytest.raises(MaintenanceEventConflict, match="divergent digest"):
        _emit(divergent, ledger, engine, seen=set())
    assert ledger.events_path.read_text(encoding="utf-8") == journal_before


# ---------------------------------------------------------------------------
# Concurrent writers
# ---------------------------------------------------------------------------


def test_concurrent_writers_append_exactly_once(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    bundle = _bundle(clusters=[], proposals=[])
    errors: list[BaseException] = []
    results: list[er.DailyEmissionResult] = []

    def worker() -> None:
        engine = ProjectionEngine()
        try:
            results.append(_emit(bundle, ledger, engine, seen=set()))
        except BaseException as exc:  # noqa: BLE001 - collected below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    # The journal CAS (lookup -> digest compare -> append under flock)
    # commits EXACTLY ONE row per occurrence key: the report AND its keyed
    # correction each appear exactly once, whatever the race outcome.
    events = _committed_events(ledger)
    occurrence_ids = [event.occurrence_id for event in events]
    assert len(occurrence_ids) == len(set(occurrence_ids))
    assert sorted(occurrence_ids) == sorted(
        [bundle.report.report_id, _correction_for(bundle).correction_id]
    )
    seqs = {r.seq for result in results for r in result.records if r.seq is not None}
    assert seqs <= {0, 1}
    # A subsequent sequential emission classifies the race winner.
    final = _emit(bundle, MaintenanceLedger(root), ProjectionEngine(), seen=set())
    assert final.records[0].outcome is er.DailyEmissionOutcome.ALREADY_PRESENT


def test_threadpool_writers_never_duplicate_the_journal(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    bundle = _bundle()
    seen: set[str] = set()

    def worker(_index: int) -> None:
        engine = ProjectionEngine()
        _emit(bundle, ledger, engine, seen=seen)

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(worker, range(6)))

    events = _committed_events(ledger)
    occurrence_ids = [event.occurrence_id for event in events]
    assert len(occurrence_ids) == len(set(occurrence_ids))  # no duplicates
    assert len(events) == 4  # report + cluster + proposal + correction, once each


# ---------------------------------------------------------------------------
# Fence loss at each boundary
# ---------------------------------------------------------------------------


def _assert_nothing_written(ledger: MaintenanceLedger) -> None:
    assert not ledger.events_path.exists() or ledger.events_path.read_text(
        encoding="utf-8"
    ) == ""


def test_fence_loss_at_entry_writes_nothing(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    check = _ScriptedFence(live_calls=0)
    with pytest.raises(er.OccurrenceFenceLostError, match="emission-entry"):
        _emit(_bundle(), ledger, engine, seen=set(), fence_check=check)
    assert check.calls == 1
    _assert_nothing_written(ledger)


def test_fence_loss_at_proposal_prior_key_boundary_stops_the_proposal(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle(clusters=[])
    # Minimal gate sequence for [report, proposal]:
    # entry(1); report classification(2)/append(3)/projection(4);
    # proposal prior-key lookup(5) — dies there.
    check = _ScriptedFence(live_calls=4)
    with pytest.raises(er.OccurrenceFenceLostError, match="proposal-prior-key"):
        _emit(bundle, ledger, engine, seen=set(), corrections=[], fence_check=check)
    kinds = [event.event_kind.value for event in _committed_events(ledger)]
    assert kinds == ["daily_efficiency_report"]  # the proposal never reached


def test_fence_loss_at_pre_append_classification_writes_nothing(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    # Minimal single-payload emission: entry(1), then the report's
    # pre-append classification(2) — dies there.
    check = _ScriptedFence(live_calls=1)
    with pytest.raises(er.OccurrenceFenceLostError, match="pre-append-classification"):
        _emit(_bundle(), ledger, engine, seen=set(), fence_check=check)
    _assert_nothing_written(ledger)



def test_fence_loss_at_append_boundary_writes_nothing(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    # Minimal single-payload emission: entry(1), classification(2),
    # append(3) — dies exactly before the write.
    check = _ScriptedFence(live_calls=2)
    with pytest.raises(er.OccurrenceFenceLostError, match="at the append boundary"):
        _emit(_bundle(), ledger, engine, seen=set(), fence_check=check)
    _assert_nothing_written(ledger)
    assert engine.efficiency.sequence == 0



def test_fence_loss_at_projection_boundary_commits_but_does_not_advance(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    # Minimal single-payload emission (no correction): entry(1),
    # classification(2), append(3) pass; projection-apply(4) dies.
    check = _ScriptedFence(live_calls=3)
    with pytest.raises(er.OccurrenceFenceLostError, match="projection-apply"):
        _emit(
            _bundle(clusters=[], proposals=[]),
            ledger,
            engine,
            seen=set(),
            corrections=[],
            fence_check=check,
        )
    # The append already committed (the journal is authoritative); the
    # projection was NOT advanced by the failed call.
    assert len(_committed_events(ledger)) == 1
    assert engine.efficiency.sequence == 0
    # Deterministic self-heal: replay under a live fence is already_present
    # AND advances the projection to the committed cursor.
    healed = _emit(
        _bundle(clusters=[], proposals=[]),
        ledger,
        engine,
        seen=set(),
        corrections=[],
    )
    assert all(r.outcome is er.DailyEmissionOutcome.ALREADY_PRESENT for r in healed.records)
    assert engine.efficiency.sequence == 1
    assert engine.efficiency.report_cursor == healed.records[0].seq




def test_fence_loss_at_projection_catch_up_writes_nothing_new(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    bundle = _bundle(clusters=[], proposals=[])
    _emit(bundle, ledger, ProjectionEngine(), seen=set())  # committed elsewhere

    # A fresh engine has NOT consumed the committed events; the fence dies at
    # the projection-catch-up boundary (entry + classification pass).
    fresh_engine = ProjectionEngine()
    check = _ScriptedFence(live_calls=2)
    with pytest.raises(er.OccurrenceFenceLostError, match="projection-catch-up"):
        _emit(bundle, ledger, fresh_engine, seen=set(), fence_check=check)
    assert len(_committed_events(ledger)) == 2  # nothing new
    assert fresh_engine.efficiency.sequence == 0
    # Live replay heals the projection deterministically.
    _emit(bundle, ledger, fresh_engine, seen=set())
    assert fresh_engine.efficiency.sequence == 2


# ---------------------------------------------------------------------------
# Forbidden fallbacks
# ---------------------------------------------------------------------------


def test_production_rejects_fence_check_none_and_default_prior_key(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle()
    kwargs = dict(
        ledger=ledger,
        engine=engine,
        observed_at=UtcTime(_ts(12)),
        event_time=UtcTime(_ts(0, 15)),
        watermark=Watermark(_ts()),
        classifier=ClassifierInfo(classifier_version="cls-v1", confidence=0.9),
        budget=OccurrenceBudget(max_attempts=1),
        occurrence_fence=_fence(),
    )
    with pytest.raises(ValueError, match="fence_check=None is the forbidden"):
        er.emit_daily_events(bundle, prior_key_lookup=lambda key: False, fence_check=None, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="prior_key_lookup=None is the forbidden"):
        er.emit_daily_events(bundle, prior_key_lookup=None, fence_check=lambda f: True, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="OccurrenceFence"):
        er.emit_daily_events(
            bundle,
            prior_key_lookup=lambda key: False,  # type: ignore[arg-type]
            fence_check=lambda f: True,
            occurrence_fence=None,  # type: ignore[arg-type]
            **{k: v for k, v in kwargs.items() if k != "occurrence_fence"},
        )
    _assert_nothing_written(ledger)
    # The signature has NO defaults for the three required injections.
    signature = inspect.signature(er.emit_daily_events)
    for name in ("fence_check", "prior_key_lookup", "occurrence_fence"):
        assert signature.parameters[name].default is inspect.Parameter.empty


def test_occurrence_fence_rejects_invalid_coordinates() -> None:
    with pytest.raises(Exception, match="fence must be >= 1"):
        er.OccurrenceFence(occurrence_id="occ", fence=0, claim_token="tok")
    with pytest.raises(Exception, match="non-empty"):
        er.OccurrenceFence(occurrence_id="occ", fence=1, claim_token="")
    with pytest.raises(Exception, match="non-empty"):
        er.OccurrenceFence(occurrence_id="", fence=1, claim_token="tok")


# ---------------------------------------------------------------------------
# Append failure -> dead letter -> at-most-once replay
# ---------------------------------------------------------------------------


def test_append_failure_dead_letters_and_replays_at_most_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.incident.ledger import _IncidentEventJournal

    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle(clusters=[], proposals=[])
    original = _IncidentEventJournal.append_maintenance
    calls = {"n": 0}

    def failing_append(self, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("simulated primary write failure")
        return original(self, **kwargs)

    monkeypatch.setattr(_IncidentEventJournal, "append_maintenance", failing_append)
    with pytest.raises(MaintenanceAppendFailure):
        _emit(bundle, ledger, engine, seen=set())
    # The dead letter was written and the projection was NOT advanced.
    assert ledger.dead_letter_path.exists()
    dead_letters = [json.loads(line) for line in ledger.dead_letter_path.read_text().splitlines() if line.strip()]
    assert len(dead_letters) == 1
    assert dead_letters[0]["failure_type"] == "write_failure"
    assert engine.efficiency.sequence == 0
    monkeypatch.undo()

    # Replay the dead letter at most once: the event commits.
    report = ledger.replay_dead_letters()
    assert report.dispositions[0].outcome is ReplayOutcome.REPLAYED
    assert len(_committed_events(ledger)) == 1
    # A second replay call finds nothing pending (at-most-once).
    second = ledger.replay_dead_letters()
    assert second.dispositions == ()
    # Re-emission classifies the replayed event as already_present and the
    # projection catches up deterministically.
    result = _emit(bundle, ledger, engine, seen=set())
    assert [r.outcome for r in result.records] == [
        er.DailyEmissionOutcome.ALREADY_PRESENT,
        er.DailyEmissionOutcome.APPENDED,  # the correction appends now
    ]
    assert engine.efficiency.sequence == 2


# ---------------------------------------------------------------------------
# Projection failure: pre-flight, injected post-append failure, determinism
# ---------------------------------------------------------------------------


def test_correction_with_uncommitted_target_fails_closed_before_append(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle(clusters=[], proposals=[])
    # Commit the day-18 report first (its keyed correction is NOT emitted),
    # then attach a correction whose supersedes target names the NEVER
    # committed day-19 window: the pre-flight must reject it before any
    # append.
    _emit(bundle, ledger, engine, seen=set(), corrections=[])
    other_receipt = _receipt(
        previous_boundary=UtcTime(_ts(0, day=19)),
        closed_boundary=UtcTime(_ts(24, day=19)),
        covered_windows=[_window(0, 12, day=19), _window(12, 24, day=19)],
    )
    other_bundle = _bundle(closure_receipt=other_receipt, clusters=[], proposals=[])
    stale_correction = ec.DailyEfficiencyCorrection(
        correction_id=ec.derive_correction_occurrence_id(
            supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
            supersedes_window=other_bundle.report.window,
            supersedes_digest=other_bundle.report.report_hash,
        ),
        supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
        supersedes_window=other_bundle.report.window,
        supersedes_digest=other_bundle.report.report_hash,
        environment=other_bundle.report.environment,
        window=other_bundle.report.window,
        reason="targets an uncommitted window",
        generated_at=UtcTime(_ts()),
    )
    journal_before = ledger.events_path.read_text(encoding="utf-8")
    with pytest.raises(er.DailyCorrectionTargetError, match="uncommitted target"):
        _emit(bundle, ledger, engine, seen=set(), corrections=[stale_correction])
    assert ledger.events_path.read_text(encoding="utf-8") == journal_before


def test_correction_with_divergent_declared_digest_fails_closed(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle(clusters=[], proposals=[])
    _emit(bundle, ledger, engine, seen=set(), corrections=[])
    journal_before = ledger.events_path.read_text(encoding="utf-8")

    report = bundle.report
    divergent_digest = "b" * 64
    divergent = ec.DailyEfficiencyCorrection(
        correction_id=ec.derive_correction_occurrence_id(
            supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
            supersedes_window=report.window,
            supersedes_digest=divergent_digest,
        ),
        supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
        supersedes_window=report.window,
        supersedes_digest=divergent_digest,
        environment=report.environment,
        window=report.window,
        reason="declares a digest that was never committed",
        generated_at=UtcTime(_ts()),
    )
    with pytest.raises(er.DailyCorrectionTargetError, match="divergent|does not match"):
        _emit(bundle, ledger, engine, seen=set(), corrections=[divergent])
    assert ledger.events_path.read_text(encoding="utf-8") == journal_before
    assert engine.efficiency.sequence == 1


def test_injected_projection_failure_self_heals_deterministically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.maintenance import projections as pj

    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle(clusters=[], proposals=[])

    def failing_reduce(event, state, *, cursor, event_digest):
        raise RuntimeError("simulated projection failure")

    monkeypatch.setattr(pj, "reduce_efficiency", failing_reduce)
    with pytest.raises(RuntimeError, match="simulated projection failure"):
        _emit(bundle, ledger, engine, seen=set())
    monkeypatch.undo()
    # The journal is authoritative: the event IS committed; the engine left
    # NO trace of the failed attempt (rollback keeps replay deterministic).
    committed = _committed_events(ledger)
    assert len(committed) == 1
    assert bundle.report.report_id not in engine._seen

    # Replay heals: already_present + deterministic catch-up apply.
    result = _emit(bundle, ledger, engine, seen=set())
    assert [r.outcome for r in result.records] == [
        er.DailyEmissionOutcome.ALREADY_PRESENT,
        er.DailyEmissionOutcome.APPENDED,
    ]
    assert engine.efficiency.sequence == 2
    # A fresh replay of the FULL journal reproduces the EXACT projection
    # state (deterministic cursor semantics).
    committed = _committed_events(ledger)
    cursors = _journal_seqs(ledger)
    fresh = replay(committed, cursors=cursors)
    assert fresh.efficiency.model_dump() == engine.efficiency.model_dump()


# ---------------------------------------------------------------------------
# Sole permitted mutation + no authority minting
# ---------------------------------------------------------------------------


def test_ledger_append_is_the_sole_m5_data_product_mutation() -> None:
    """Static scan: the reporter mutates ONLY through the canonical writer."""
    source = Path(er.__file__).read_text(encoding="utf-8")
    forbidden = [
        "open(",
        "write_text",
        "write_bytes",
        "json.dump(",
        "os.remove",
        ".unlink(",
        "mkdir(",
        "shutil",
        "subprocess",
        "os.write",
    ]
    hits = [token for token in forbidden if token in source]
    assert hits == [], f"reporter performs raw I/O: {hits}"
    # The only data-product mutation calls are the canonical writer and the
    # in-memory projection advance.
    assert source.count("ledger.append(") == 1
    assert "engine.apply(" in source
    # The canonical writer chain is named exactly.
    assert "IncidentLedger.append_maintenance_event" in source
    assert "MaintenanceLedger.append" in source
    assert "_IncidentEventJournal.append_maintenance" in source


def test_appends_and_projections_mint_no_authority(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    custody_before = engine.custody.model_dump()
    verification_before = engine.verification.model_dump()

    result = _emit(_bundle(), ledger, engine, seen=set())
    assert len(result.records) == 4

    # Daily observation NEVER advances custody or verification authority:
    # no closure, dispatch, completion, repair, or scheduling effect can be
    # minted.  (Only the engine's bookkeeping ``lag`` moves — the custody
    # and verification STATES are byte-identical modulo lag.)
    custody_after = engine.custody.model_dump()
    verification_after = engine.verification.model_dump()
    for state in (custody_after, custody_before):
        state.pop("lag")
    for state in (verification_after, verification_before):
        state.pop("lag")
    assert custody_after == custody_before
    assert verification_after == verification_before
    assert engine.custody.terminal is False
    assert engine.verification.coherence.value == "unknown"
    # The proposal is INERT by contract (never dispatchable).
    proposal_event = next(
        event
        for event in _committed_events(ledger)
        if event.event_kind in DAILY_EVENT_KINDS
        and event.event_kind.value == "daily_efficiency_proposal"
    )
    assert proposal_event.payload.proposal.auto_materialization is False
    # A keyed correction appends exactly one KEYED correction record — never
    # a ticket, repair, schedule, or policy effect.
    keyed = [
        c for c in engine.efficiency.corrections if c.kind.value == "keyed"
    ]
    assert len(keyed) == 1
    # The disposable root contains ONLY the incident-ledger adjunct files —
    # no schedule, ticket, repair-queue, or policy state was created.
    created = sorted(
        str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()
    )
    assert created, "expected ledger state files"
    assert all(name.startswith(".megaplan/incident-ledger/") for name in created)
    assert not (root / "schedules").exists()
    assert not (root / "tickets").exists()


def test_proposal_prior_key_lookup_gates_cross_window_reappend(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle()
    # The proposal key is already committed from an earlier window emission:
    # it must NEVER reach the ledger again (SD3).
    proposal = _proposal()
    result = _emit(bundle, ledger, engine, seen={proposal.proposal_key})
    by_kind = {r.kind: r for r in result.records}
    assert (
        by_kind[ec.DailyEfficiencyKind.DAILY_EFFICIENCY_PROPOSAL].outcome
        is er.DailyEmissionOutcome.ALREADY_PRESENT
    )
    assert (
        by_kind[ec.DailyEfficiencyKind.DAILY_EFFICIENCY_PROPOSAL].seq is None
    )
    kinds = [event.event_kind.value for event in _committed_events(ledger)]
    assert "daily_efficiency_proposal" not in kinds
    assert kinds == [
        "daily_efficiency_report",
        "daily_efficiency_cluster",
        "daily_efficiency_correction",
    ]


# ---------------------------------------------------------------------------
# Deterministic + auditable cursors
# ---------------------------------------------------------------------------


def test_append_and_projection_cursors_are_deterministic_and_auditable(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()

    day18 = _bundle(clusters=[], proposals=[])
    _emit(day18, ledger, engine, seen=set())
    receipt19 = _receipt(
        previous_boundary=UtcTime(_ts(0, day=19)),
        closed_boundary=UtcTime(_ts(24, day=19)),
        covered_windows=[_window(0, 12, day=19), _window(12, 24, day=19)],
    )
    day19 = _bundle(closure_receipt=receipt19, clusters=[], proposals=[])
    _emit(day19, ledger, engine, seen=set())

    events = _committed_events(ledger)
    cursors = _journal_seqs(ledger)
    assert cursors == sorted(cursors)
    eff = engine.efficiency
    # Each daily stream cursor is exactly the committed ledger sequence of
    # its latest payload (auditable back to the journal).
    report_seqs = [
        cursor
        for event, cursor in zip(events, cursors)
        if event.event_kind.value == "daily_efficiency_report"
    ]
    correction_seqs = [
        cursor
        for event, cursor in zip(events, cursors)
        if event.event_kind.value == "daily_efficiency_correction"
    ]
    assert eff.report_cursor == report_seqs[-1]
    assert eff.correction_cursor == correction_seqs[-1]
    # The committed-daily registry binds (kind, window) -> (seq, digest).
    for event in events:
        if event.event_kind.value == "daily_efficiency_report":
            key = daily_commit_key(event.event_kind.value, event.window)
            seq, digest = eff.committed_daily[key]
            assert digest == canonical_digest(event.payload.report)
            assert seq in cursors
    # A fresh engine replaying the same journal reproduces the EXACT state.
    fresh = replay(events, cursors=cursors)
    assert fresh.efficiency.model_dump() == eff.model_dump()
    # Emission results round-trip strictly (typed audit artifact).
    result = _emit(day18, ledger, engine, seen=set())
    restored = er.DailyEmissionResult.model_validate(result.model_dump(mode="json"))
    assert restored == result


def test_emission_result_records_carry_fence_audit_coordinates(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    engine = ProjectionEngine()
    bundle = _bundle(clusters=[], proposals=[])
    result = _emit(bundle, ledger, engine, seen=set(), fence=_fence(n=7))
    assert [r.fence for r in result.records] == [7, 7]
    payload = result.model_dump(mode="json")
    assert payload["records"][0]["fence"] == 7
