"""Focused T6.2 proof tests: the closure-proven daily runner.

Proves :func:`run_daily_efficiency` — ONE entry point owning the whole
daily efficiency cycle against ONE ``(MaintenanceLedger, ProjectionEngine)``
pair:

* **Replay-first convergence** — the journal is replayed into a fresh
  engine BEFORE any emission, so a keyed correction whose supersedes target
  was committed by a DIFFERENT writer process applies instead of
  false-rejecting (the T6.1 residual);
* **Exactly-once per day-occurrence** — an exact rerun joins
  (``already_present``) with zero new writes; divergent input fails closed
  writing nothing;
* **Fence loss at each emission boundary** — every loss leaves
  journal-authoritative recoverable state and the next run converges
  deterministically;
* **Closure receipt** — the typed terminal proof: the day's committed
  kinds, journal-bound stream cursors, byte-identical fresh replay, and
  round-trippable coordinates (never prose);
* **Mutation spies** — the runner adds no second writer, no raw I/O, and
  no schedule/ticket/repair/policy authority; every state-writing test uses
  an explicit disposable root proven not to be a project/candidate/live
  runtime root, and the run creates ONLY incident-ledger state.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.maintenance import (
    MetricFacts,
    build_operational_report,
    operational_report_to_event,
)
from arnold_pipelines.megaplan.maintenance import daily_runner as dr
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
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.ledger import (
    MaintenanceEventConflict,
    MaintenanceLedger,
)
from arnold_pipelines.megaplan.maintenance.projections import ProjectionEngine

UTC = timezone.utc

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FORBIDDEN_STATE_ROOTS = {
    _PROJECT_ROOT,
    Path("/Users/peteromalley/Documents/Arnold"),
    Path(
        "/Users/peteromalley/Documents/.megaplan-worktrees/"
        "runtime-convergence-execution"
    ),
    Path("/workspace/runtime-candidates/arnold-4a830c6ac9a0"),
    Path("/workspace/runtime-candidates/astrid-first"),
    Path("/workspace/megaplan-maintenance/Arnold"),
}
_SHA256 = "a" * 64


def _disposable_state_root(tmp_path: Path) -> Path:
    """Return and PROVE a test-only ledger root under pytest's temp dir.

    The root must live inside pytest's per-test temp directory and must
    never be (or contain) this project's checkout, a live ``.megaplan``
    runtime state, or any known integration/candidate runtime root.
    """
    root = tmp_path.resolve()
    tmp_root = tmp_path.resolve()
    assert root.is_relative_to(tmp_root), f"root escaped pytest tmp: {root}"
    assert not root.is_relative_to(_PROJECT_ROOT), (
        f"root is inside the project checkout: {root}"
    )
    assert root not in _FORBIDDEN_STATE_ROOTS
    assert ".megaplan-worktrees" not in root.parts
    assert root.name != "incident-ledger"
    # The ledger must CREATE its state lazily; nothing exists yet.
    assert not (root / ".megaplan" / "incident-ledger" / "events.jsonl").exists()
    return root


# ---------------------------------------------------------------------------
# Builders: operational closure evidence (the committed M4 chain)
# ---------------------------------------------------------------------------


def _ts(hour: int = 0, minute: int = 0, day: int = 18) -> datetime:
    return datetime(2026, 8, day, tzinfo=UTC) + timedelta(hours=hour, minutes=minute)


def _window(start: int = 0, end: int = 24, day: int = 18) -> EventWindow:
    return EventWindow(
        start=UtcTime(_ts(start, day=day)), end=UtcTime(_ts(end, day=day))
    )


def _ref(owner: str, locator: str, digest: str | None = _SHA256) -> OwnerRef:
    return OwnerRef(owner=owner, locator=locator, digest=digest)


def _op_event(
    name: str,
    start: int,
    end: int,
    *,
    day: int = 18,
    environment: str = "production",
) -> MaintenanceEvent:
    """One committed M4 operational report event covering ``[start, end)``."""
    report = build_operational_report(
        report_id=name,
        watermark=_ts(start, day=day),
        window_end=_ts(end, day=day),
        input_ids=["b", "a"],
        owner_refs=[_ref("wbc", f"wbc://{name}")],
        policy_version="policy-v1",
        classifier_version="cls-v1",
        metrics=MetricFacts(numerator=3, denominator=5, unknown_count=1),
    )
    return operational_report_to_event(report, environment=environment)


def _seed_operational_chain(
    ledger: MaintenanceLedger,
    windows: list[tuple[int, int]],
    *,
    day: int = 18,
    environment: str = "production",
) -> None:
    for index, (start, end) in enumerate(windows, start=1):
        ledger.append(
            _op_event(
                f"op-{day}-{index}", start, end, day=day, environment=environment
            )
        )


# ---------------------------------------------------------------------------
# Builders: the day's analysis inputs (injected pure analysis stage)
# ---------------------------------------------------------------------------


def _cohort() -> ec.EfficiencyCohortIdentity:
    return ec.EfficiencyCohortIdentity(
        stage="stage-1",
        profile="profile-1",
        model="model-1",
        robustness=ec.RobustnessKind.THOROUGH,
        environment="production",
        classifier_version="cls-v1",
    )


def _bounds(value: float, lower: float | None = None, upper: float | None = None) -> ec.QuantileBounds:
    return ec.QuantileBounds(value=value, lower_bound=lower, upper_bound=upper)


def _snapshot(day: int = 18) -> ec.BaselineSnapshot:
    return ec.BaselineSnapshot(
        cohort=_cohort(),
        sample_count=40,
        plan_count=8,
        completed_count=30,
        censored_count=10,
        median=_bounds(1800.0, 1500.0, 2100.0),
        mad=_bounds(300.0, 250.0, 400.0),
        p95=_bounds(7200.0, 6600.0, 9000.0),
        p99=_bounds(10800.0, 9600.0, None),
        censoring_dominated=False,
        generated_at=UtcTime(_ts(day=day)),
    )


def _denominator() -> ec.DenominatorCoverage:
    return ec.DenominatorCoverage(
        metric="accepted_outcomes",
        numerator=3,
        denominator=5,
        unknown_count=1,
        censored_count=1,
    )


def _shadow() -> ec.ShadowMeasure:
    return ec.ShadowMeasure(
        measure=ec.ShadowMeasureKind.PRECISION, value=0.8, numerator=4, denominator=5
    )


def _completed(observation_id: str = "obs-completed-1", duration: float = 3600.0) -> ec.DurationObservation:
    return ec.DurationObservation(
        observation_id=observation_id,
        status=ec.ObservationStatus.COMPLETED,
        duration_seconds=duration,
    )


def _censored() -> ec.DurationObservation:
    return ec.DurationObservation(
        observation_id="obs-censored-1",
        status=ec.ObservationStatus.RIGHT_CENSORED,
        lower_bound_seconds=1800.0,
    )


def _references() -> ec.FindingReferences:
    return ec.FindingReferences(
        accepted_resolution_refs=[_ref("run_authority", "decision://d-1")],
        active_custody_refs=[_ref("custody", "custody://lease-1")],
        source_refs=[_ref("wbc", "wbc://att-1/1")],
        gate_backoff_refs=[_ref("maintenance", "gate://g-1")],
        censoring_refs=[_ref("maintenance", "censoring://c-1")],
    )


def _dwell() -> ec.DwellFinding:
    return ec.DwellFinding(
        finding_id="f-dwell-1",
        kind=ec.DwellFindingKind.GATE,
        duration_seconds=7200.0,
        references=_references(),
    )


def _loop() -> ec.LoopFinding:
    return ec.LoopFinding(
        finding_id="f-loop-1",
        kind=ec.LoopFindingKind.RETRY_LOOP,
        repeated_stage="gate",
        attempt_count=3,
        references=_references(),
    )


def _candidate() -> ec.RootCauseCandidate:
    return ec.RootCauseCandidate(
        candidate_id="cand-1",
        root_cause_fingerprint="fp-1",
        affected_contract="ac-1",
        classifier_version="cls-v1",
        coverage=ec.DenominatorCoverage(
            metric="evidence_coverage", numerator=4, denominator=5
        ),
        confidence=_bounds(0.9, 0.8, 0.95),
        recurrence_count_7d=2,
        recurrence_count_30d=3,
        occurrence_refs=[_ref("custody", "occurrence://occ-1")],
        evidence_refs=[_ref("wbc", "wbc://att-1/1")],
    )


def _proposal(window: EventWindow, generated_at: UtcTime) -> ec.DailyEfficiencyProposal:
    proposal_id = ec.derive_proposal_occurrence_id(
        proposal_kind=ec.ProposalKind.TICKET,
        root_cause_fingerprint="fp-1",
        affected_contract="ac-1",
        classifier_version="cls-v1",
        open_ticket_identity=None,
    )
    return ec.DailyEfficiencyProposal(
        proposal_id=proposal_id,
        proposal_kind=ec.ProposalKind.TICKET,
        root_cause_fingerprint="fp-1",
        affected_contract="ac-1",
        classifier_version="cls-v1",
        open_ticket_identity=None,
        environment=EnvironmentId("production"),
        window=window,
        cluster_ref=_ref("maintenance", "cluster://c-1"),
        candidate_refs=[_ref("maintenance", "candidate://cand-1")],
        evidence_refs=[_ref("wbc", "wbc://att-1/1")],
        active_custody_refs=[_ref("custody", "custody://lease-1")],
        active_custody_present=True,
        auto_materialization=False,
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# The day under test: shared deterministic inputs for caller and runner
# ---------------------------------------------------------------------------


class _Day:
    """Deterministic day inputs: the caller-side mirror of the runner flow.

    The correction is derived EXACTLY as the T6.2 contract prescribes for
    callers: prove the closure receipt from the committed operational
    evidence, synthesize the same bundle through the single synthesizer,
    and key the correction to the report's canonical digest.
    """

    def __init__(self, day: int = 18) -> None:
        self.day = day
        self.previous_boundary = UtcTime(_ts(0, day=day))
        self.candidate_boundary = UtcTime(_ts(24, day=day))
        self.environment = EnvironmentId("production")
        self.generated_at = UtcTime(_ts(12, day=day))
        self.analysis_output = dr.DailyAnalysisOutput(
            observations=(_completed(), _censored()),
            baselines=(_snapshot(day=day),),
            findings=(_dwell(), _loop()),
            denominators=(_denominator(),),
            shadow_measures=(_shadow(),),
            candidates=(_candidate(),),
            proposals=(_proposal(_window(0, 24, day=day), UtcTime(_ts(day=day))),),
            extra_input_refs=(_ref("run_authority", "decision://d-1"),),
        )

    @property
    def analysis_stage(self) -> dr.DailyAnalysisStage:
        return lambda receipt: self.analysis_output

    def _closure(self, ledger: MaintenanceLedger) -> dr.DailyClosureResult:
        return dr.derive_daily_closure(
            events=_committed_events(ledger),
            previous_boundary=self.previous_boundary,
            candidate_boundary=self.candidate_boundary,
            environment=self.environment,
        )

    def expected_report_digest(self, ledger: MaintenanceLedger) -> str:
        closure = self._closure(ledger)
        assert closure.closed and closure.receipt is not None
        bundle = dr.synthesize_daily_report(
            closure.receipt,
            self.analysis_output,
            generated_at=self.generated_at,
        )
        return bundle.report.report_hash

    def correction(self, ledger: MaintenanceLedger) -> ec.DailyEfficiencyCorrection:
        digest = self.expected_report_digest(ledger)
        window = _window(0, 24, day=self.day)
        return ec.DailyEfficiencyCorrection(
            correction_id=ec.derive_correction_occurrence_id(
                supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
                supersedes_window=window,
                supersedes_digest=digest,
            ),
            supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
            supersedes_window=window,
            supersedes_digest=digest,
            environment=self.environment,
            window=window,
            reason="late evidence advanced",
            generated_at=UtcTime(_ts(13, day=self.day)),
        )


def _run(
    ledger: MaintenanceLedger,
    day: _Day,
    *,
    corrections: list[ec.DailyEfficiencyCorrection] | None = None,
    fence: er.OccurrenceFence | None = None,
    fence_check=None,
    environment: EnvironmentId | None = None,
) -> dr.DailyEfficiencyRunResult:
    return dr.run_daily_efficiency(
        ledger=ledger,
        previous_boundary=day.previous_boundary,
        candidate_boundary=day.candidate_boundary,
        environment=environment or day.environment,
        generated_at=day.generated_at,
        occurrence_fence=fence or _fence(),
        fence_check=fence_check if fence_check is not None else (lambda f: True),
        analysis=day.analysis_stage,
        corrections=(
            corrections if corrections is not None else [day.correction(ledger)]
        ),
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


def _committed_events(ledger: MaintenanceLedger) -> list[MaintenanceEvent]:
    """Strict-decode every committed Maintenance payload from the journal."""
    return [
        strict_loads(MaintenanceEvent, json.loads(line)["payload"])
        for line in _journal_lines(ledger)
    ]


def _journal_lines(ledger: MaintenanceLedger) -> list[str]:
    if not ledger.events_path.exists():
        return []
    return [
        line
        for line in ledger.events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _journal_bytes(ledger: MaintenanceLedger) -> str:
    return ledger.events_path.read_text(encoding="utf-8") if _journal_lines(
        ledger
    ) else ""


def _journal_seqs(ledger: MaintenanceLedger) -> list[int]:
    return [
        int(json.loads(line)["seq"])
        for line in _journal_lines(ledger)
        if line.strip()
    ]


def _kinds(ledger: MaintenanceLedger) -> list[str]:
    return [
        event.event_kind.value
        for event in _committed_events(ledger)
        if isinstance(event, MaintenanceEvent)
    ]


# ---------------------------------------------------------------------------
# Replay-first convergence (the T6.1 residual: cross-process targets)
# ---------------------------------------------------------------------------


def _daily_kinds(ledger: MaintenanceLedger) -> list[str]:
    return [kind for kind in _kinds(ledger) if kind.startswith("daily_")]


def test_replay_first_resolves_cross_process_correction_target(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    _seed_operational_chain(ledger, [(0, 12), (12, 24)], day=19)
    day18 = _Day(day=18)
    day19 = _Day(day=19)
    # Day 19 carries a report-only input set (no clusters/proposals): the
    # scenario's subject is the chained correction, and a shared reduced
    # input set keeps the control and the runner byte-identical.
    day19.analysis_output = dr.DailyAnalysisOutput(
        observations=day19.analysis_output.observations,
    )
    # Process A: yesterday (day 18) ran to terminal closure through the
    # runner — the four kinds, INCLUDING its keyed correction, are
    # committed in the journal by a DIFFERENT writer process/engine.
    first = _run(ledger, day18)
    assert first.status is dr.DailyRunStatus.CLOSED_APPENDED
    assert first.receipt is not None
    correction18 = next(
        record
        for record in first.receipt.committed
        if record.kind is ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION
    )

    # Late evidence chains onto process A's committed correction: today's
    # (day 19) run carries a keyed correction whose supersedes TARGET is
    # that cross-process-committed day-18 correction.
    chained = ec.DailyEfficiencyCorrection(
        correction_id=ec.derive_correction_occurrence_id(
            supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION,
            supersedes_window=_window(0, 24),
            supersedes_digest=correction18.digest,
        ),
        supersedes_kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION,
        supersedes_window=_window(0, 24),
        supersedes_digest=correction18.digest,
        environment=day19.environment,
        window=_window(0, 24, day=19),
        reason="chained late evidence on the committed correction",
        generated_at=UtcTime(_ts(13, day=19)),
    )

    # Control: WITHOUT replay-first, the engine-scoped T6.1 pre-flight
    # FALSE-REJECTS — the target lives only in the journal, not in a bare
    # engine's committed_daily registry.  Nothing is written.
    closure19 = dr.derive_daily_closure(
        events=_committed_events(ledger),
        previous_boundary=day19.previous_boundary,
        candidate_boundary=day19.candidate_boundary,
        environment=day19.environment,
    )
    assert closure19.closed and closure19.receipt is not None
    bundle19 = dr.synthesize_daily_report(
        closure19.receipt,
        day19.analysis_output,
        generated_at=day19.generated_at,
    )
    with pytest.raises(er.DailyCorrectionTargetError, match="uncommitted target"):
        er.emit_daily_events(
            bundle19,
            ledger=ledger,
            engine=ProjectionEngine(),
            observed_at=day19.generated_at,
            event_time=day19.generated_at,
            watermark=Watermark(day19.candidate_boundary.root),
            classifier=ClassifierInfo(classifier_version="cls-v1", confidence=1.0),
            budget=OccurrenceBudget(max_attempts=1),
            prior_key_lookup=lambda key: False,
            corrections=[chained],
            occurrence_fence=_fence(2),
            fence_check=lambda f: True,
        )
    # The false-rejected control DID append its own new day-19 payloads
    # (they precede the correction in emission order) — but the CHAINED
    # CORRECTION itself never entered: that is the false rejection, and
    # exactly what replay-first resolves below.
    daily = _daily_kinds(ledger)
    assert len(daily) == 5  # 4 x day 18 + the control's own day-19 report
    assert daily.count("daily_efficiency_correction") == 1

    # The runner OWNS the replay: it rebuilds the projection from the
    # journal FIRST, so the cross-process-committed target is registered
    # and the same correction APPLIES instead of false-rejecting.
    result = dr.run_daily_efficiency(
        ledger=ledger,
        previous_boundary=day19.previous_boundary,
        candidate_boundary=day19.candidate_boundary,
        environment=day19.environment,
        generated_at=day19.generated_at,
        occurrence_fence=_fence(2),
        fence_check=lambda f: True,
        analysis=day19.analysis_stage,
        corrections=[chained],
    )
    assert result.status is dr.DailyRunStatus.CLOSED_APPENDED
    assert result.receipt is not None
    committed_kinds = [record.kind for record in result.receipt.committed]
    assert ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION in committed_kinds
    # The chained correction targets the DAY-18 window (cross-process).
    chained_record = next(
        record
        for record in result.receipt.committed
        if record.kind is ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION
    )
    assert chained_record.outcome is er.DailyEmissionOutcome.APPENDED
    assert result.receipt.replay_identical is True


# ---------------------------------------------------------------------------
# Exactly-once per day-occurrence: rerun joins, divergent fails closed
# ---------------------------------------------------------------------------


def test_rerun_same_day_joins_exactly_once_with_no_writes(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()

    first = _run(ledger, day)
    assert first.status is dr.DailyRunStatus.CLOSED_APPENDED
    journal_after_first = _journal_bytes(ledger)
    assert first.receipt is not None
    first_seqs = {r.kind: r.seq for r in first.receipt.committed}

    # Exact rerun (same day inputs, same envelope coordinates): every
    # payload joins as already_present; the journal is byte-identical.
    second = _run(ledger, day, fence=_fence(9))
    assert second.status is dr.DailyRunStatus.CLOSED_JOINED
    assert second.appended is False
    assert _journal_bytes(ledger) == journal_after_first
    assert second.receipt is not None
    assert [record.outcome for record in second.receipt.committed] == [
        er.DailyEmissionOutcome.ALREADY_PRESENT
    ] * len(second.receipt.committed)
    second_seqs = {r.kind: r.seq for r in second.receipt.committed}
    for kind, seq in first_seqs.items():
        if kind is ec.DailyEfficiencyKind.DAILY_EFFICIENCY_PROPOSAL:
            # The cross-window key short-circuits BEFORE the ledger on the
            # join: no sequence, no re-append (SD3).
            assert second_seqs[kind] is None
        else:
            assert second_seqs[kind] == seq
    # The join ran under the newer fence (audit coordinate moves, content
    # does not): every record carries the fence it decided under.
    assert second.receipt.fence == 9


def test_divergent_input_fails_closed_writing_nothing(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()
    first = _run(ledger, day)
    assert first.status is dr.DailyRunStatus.CLOSED_APPENDED
    journal_before = _journal_bytes(ledger)

    # Same locked report identity (same window/environment), divergent
    # content: an extra observation changes the canonical digest.
    divergent_day = _Day()
    divergent_day.analysis_output = dr.DailyAnalysisOutput(
        observations=(
            _completed(),
            _censored(),
            _completed("obs-completed-2", 7200.0),
        ),
        baselines=divergent_day.analysis_output.baselines,
        findings=divergent_day.analysis_output.findings,
        denominators=divergent_day.analysis_output.denominators,
        shadow_measures=divergent_day.analysis_output.shadow_measures,
        candidates=divergent_day.analysis_output.candidates,
        proposals=divergent_day.analysis_output.proposals,
        extra_input_refs=divergent_day.analysis_output.extra_input_refs,
    )
    with pytest.raises(MaintenanceEventConflict, match="divergent"):
        _run(ledger, divergent_day)
    # Fail closed: nothing was appended, nothing was rewritten.
    assert _journal_bytes(ledger) == journal_before


# ---------------------------------------------------------------------------
# Fence loss at each boundary + deterministic recovery
# ---------------------------------------------------------------------------


def test_fence_loss_at_emission_entry_writes_nothing_and_converges(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()
    check = _ScriptedFence(live_calls=0)
    result = _run(ledger, day, fence_check=check)
    assert check.calls == 1
    assert result.status is dr.DailyRunStatus.FENCE_LOST
    assert result.receipt is None
    assert result.fence_boundary == "emission-entry"
    # Nothing was written by the failed run: only the seeded op reports exist.
    assert len(_committed_events(ledger)) == 2
    assert _daily_kinds(ledger) == []
    # Next run under a live fence converges deterministically.
    recovered = _run(ledger, day)
    assert recovered.status is dr.DailyRunStatus.CLOSED_APPENDED
    assert recovered.receipt is not None and recovered.receipt.replay_identical


def test_fence_loss_at_append_boundary_writes_nothing_and_converges(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()
    # Boundary sequence for [report, cluster, proposal, correction]:
    # entry(1); report classification(2) — dies before the report append(3).
    check = _ScriptedFence(live_calls=2)
    result = _run(ledger, day, fence_check=check)
    assert result.status is dr.DailyRunStatus.FENCE_LOST
    assert result.fence_boundary == "append"
    assert _kinds(ledger) == ["efficiency_analysis", "efficiency_analysis"]
    recovered = _run(ledger, day)
    assert recovered.status is dr.DailyRunStatus.CLOSED_APPENDED
    assert _kinds(ledger) == [
        "efficiency_analysis",
        "efficiency_analysis",
        "daily_efficiency_report",
        "daily_efficiency_cluster",
        "daily_efficiency_proposal",
        "daily_efficiency_correction",
    ]
    assert recovered.receipt is not None and recovered.receipt.replay_identical


def test_fence_loss_at_projection_boundary_commits_then_self_heals(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()
    # entry(1), report classification(2), report append(3) pass; the report's
    # projection-apply(4) dies: the journal is authoritative, the projection
    # was NOT advanced by the failed run.
    check = _ScriptedFence(live_calls=3)
    result = _run(ledger, day, fence_check=check)
    assert result.status is dr.DailyRunStatus.FENCE_LOST
    assert result.fence_boundary == "projection-apply"
    assert _kinds(ledger)[-1] == "daily_efficiency_report"

    # Next run converges: the committed report joins already_present and the
    # remaining payloads append; the receipt proves byte-identical replay.
    recovered = _run(ledger, day)
    assert recovered.status is dr.DailyRunStatus.CLOSED_APPENDED
    assert recovered.receipt is not None
    by_kind = {r.kind: r for r in recovered.receipt.committed}
    assert (
        by_kind[ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT].outcome
        is er.DailyEmissionOutcome.ALREADY_PRESENT
    )
    assert recovered.receipt.replay_identical is True
    assert _kinds(ledger) == [
        "efficiency_analysis",
        "efficiency_analysis",
        "daily_efficiency_report",
        "daily_efficiency_cluster",
        "daily_efficiency_proposal",
        "daily_efficiency_correction",
    ]


def test_fence_loss_at_catch_up_on_rerun_leaves_recoverable_state(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()
    assert _run(ledger, day).status is dr.DailyRunStatus.CLOSED_APPENDED
    journal_full = _journal_bytes(ledger)

    # A fresh-process rerun dies at the FIRST already-present payload's
    # projection-catch-up boundary: entry(1), report classification(2) pass,
    # catch-up(3) dies.  Nothing new is written.
    check = _ScriptedFence(live_calls=2)
    result = _run(ledger, day, fence_check=check)
    assert result.status is dr.DailyRunStatus.FENCE_LOST
    assert result.fence_boundary == "projection-catch-up"
    assert _journal_bytes(ledger) == journal_full

    # The next live run joins deterministically with zero new writes.
    recovered = _run(ledger, day, fence=_fence(11))
    assert recovered.status is dr.DailyRunStatus.CLOSED_JOINED
    assert _journal_bytes(ledger) == journal_full
    assert recovered.receipt is not None and recovered.receipt.replay_identical


def test_fence_loss_at_proposal_prior_key_boundary_stops_and_converges(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()
    # entry(1); report class(2)/append(3)/proj(4); cluster
    # class(5)/append(6)/proj(7) — the proposal prior-key lookup(8) dies.
    check = _ScriptedFence(live_calls=7)
    result = _run(ledger, day, fence_check=check)
    assert result.status is dr.DailyRunStatus.FENCE_LOST
    assert result.fence_boundary == "proposal-prior-key-lookup"
    assert _kinds(ledger)[-2:] == [
        "daily_efficiency_report",
        "daily_efficiency_cluster",
    ]
    recovered = _run(ledger, day)
    assert recovered.status is dr.DailyRunStatus.CLOSED_APPENDED
    assert _kinds(ledger)[-2:] == [
        "daily_efficiency_proposal",
        "daily_efficiency_correction",
    ]
    assert recovered.receipt is not None and recovered.receipt.replay_identical


# ---------------------------------------------------------------------------
# Closure receipt: typed terminal proof (never prose)
# ---------------------------------------------------------------------------


def test_closure_receipt_contents_and_round_trip(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()
    result = _run(ledger, day, fence=_fence(5))
    assert result.status is dr.DailyRunStatus.CLOSED_APPENDED
    assert result.closed is True and result.appended is True
    assert result.reason is None and result.fence_boundary is None
    receipt = result.receipt
    assert receipt is not None

    # The window/environment are the closure-proven coordinates.
    assert receipt.window == _window(0, 24)
    assert receipt.environment == day.environment
    assert receipt.fence == 5
    assert receipt.replay_identical is True

    # The day's four kinds are committed exactly once each, in emission
    # order, with strictly increasing journal sequences.
    kinds = [record.kind for record in receipt.committed]
    assert kinds == [
        ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
        ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CLUSTER,
        ec.DailyEfficiencyKind.DAILY_EFFICIENCY_PROPOSAL,
        ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION,
    ]
    seqs = [record.seq for record in receipt.committed]
    assert all(seq is not None for seq in seqs)
    assert seqs == sorted(seqs)  # type: ignore[arg-type]
    assert all(
        record.outcome is er.DailyEmissionOutcome.APPENDED
        for record in receipt.committed
    )
    # Every committed sequence exists in the journal (journal-authoritative).
    journal_seqs = set(_journal_seqs(ledger))
    assert set(seqs) <= journal_seqs  # type: ignore[arg-type]
    assert receipt.journal_head_seq == max(journal_seqs)

    # Cursors ARE journal sequences: each daily stream cursor equals the
    # latest committed journal sequence of its kind.
    latest: dict[str, int] = {}
    for seq, event in zip(_journal_seqs(ledger), _committed_events(ledger)):
        if isinstance(event, MaintenanceEvent) and event.event_kind.value.startswith(
            "daily_"
        ):
            latest[event.event_kind.value] = seq
    assert receipt.report_cursor == latest["daily_efficiency_report"]
    assert receipt.cluster_cursor == latest["daily_efficiency_cluster"]
    assert receipt.proposal_cursor == latest["daily_efficiency_proposal"]
    assert receipt.correction_cursor == latest["daily_efficiency_correction"]

    # The receipt carries the byte-identity coordinates of all three
    # projections and round-trips strictly as a typed artifact.
    assert receipt.efficiency_output_digest is not None
    # Custody and verification consumed no authority-bearing events in
    # this scenario, so their output digests stay explicitly None (never
    # green); the efficiency digest is the materialized daily identity.
    assert receipt.custody_output_digest is None
    assert receipt.verification_output_digest is None
    restored = dr.DailyClosureReceipt.model_validate(
        receipt.model_dump(mode="json")
    )
    assert restored == receipt
    run_restored = dr.DailyEfficiencyRunResult.model_validate(
        result.model_dump(mode="json")
    )
    assert run_restored == result


def test_unverified_or_reportless_receipts_cannot_be_minted(tmp_path: Path) -> None:
    window = _window(0, 24)
    record = dr.CommittedDailyRecord(
        kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
        occurrence_id="report-1",
        event_id="daily-efficiency|report-1",
        outcome=er.DailyEmissionOutcome.APPENDED,
        seq=1,
        digest=_SHA256,
    )
    with pytest.raises(Exception, match="byte-identical"):
        dr.DailyClosureReceipt(
            environment=EnvironmentId("production"),
            window=window,
            fence=1,
            committed=(record,),
            journal_head_seq=1,
            report_cursor=1,
            cluster_cursor=0,
            proposal_cursor=0,
            correction_cursor=0,
            replay_identical=False,
        )
    cluster_record = dr.CommittedDailyRecord(
        kind=ec.DailyEfficiencyKind.DAILY_EFFICIENCY_CLUSTER,
        occurrence_id="cluster-1",
        event_id="daily-efficiency|cluster-1",
        outcome=er.DailyEmissionOutcome.APPENDED,
        seq=2,
        digest=_SHA256,
    )
    with pytest.raises(Exception, match="report record"):
        dr.DailyClosureReceipt(
            environment=EnvironmentId("production"),
            window=window,
            fence=1,
            committed=(cluster_record,),
            journal_head_seq=2,
            report_cursor=0,
            cluster_cursor=2,
            proposal_cursor=0,
            correction_cursor=0,
            replay_identical=True,
        )


# ---------------------------------------------------------------------------
# Typed NON-APPENDING closure outcomes (SD2)
# ---------------------------------------------------------------------------


def test_empty_chain_is_typed_non_appending(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    day = _Day()
    result = _run(ledger, day, corrections=[])
    assert result.status is dr.DailyRunStatus.NON_CLOSING
    assert result.receipt is None
    assert result.closure.outcome is dr.DailyClosureOutcome.EMPTY_CHAIN
    assert result.closure.reason is not None
    assert _journal_lines(ledger) == []


def test_nominal_window_without_committed_coverage_never_emits(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    # Only the morning window committed: a candidate boundary at hour 24 is
    # NOMINAL clock time, not closure evidence — coverage ends at hour 12.
    _seed_operational_chain(ledger, [(0, 12)])
    day = _Day()
    result = _run(ledger, day, corrections=[])
    assert result.status is dr.DailyRunStatus.NON_CLOSING
    assert result.receipt is None
    assert result.closure.outcome is dr.DailyClosureOutcome.COVERAGE_GAP
    assert "candidate boundary" in (result.closure.reason or "")
    assert _kinds(ledger) == ["efficiency_analysis"]


def test_gapped_chain_is_typed_non_appending(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    # A gap between the two committed windows is not closure proof.
    ledger.append(_op_event("op-a", 0, 6))
    ledger.append(_op_event("op-b", 12, 24))
    day = _Day()
    result = _run(ledger, day, corrections=[])
    assert result.status is dr.DailyRunStatus.NON_CLOSING
    assert result.closure.outcome is dr.DailyClosureOutcome.COVERAGE_GAP
    assert "contiguous" in (result.closure.reason or "")
    assert _kinds(ledger) == ["efficiency_analysis", "efficiency_analysis"]


def test_cross_environment_break_is_typed_non_appending(tmp_path: Path) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12)], environment="staging")
    day = _Day()
    result = _run(ledger, day, corrections=[])
    assert result.status is dr.DailyRunStatus.NON_CLOSING
    assert result.closure.outcome is dr.DailyClosureOutcome.CROSS_ENVIRONMENT_BREAK
    assert _journal_lines(ledger) and "daily_efficiency" not in _kinds(ledger)


def test_torn_maintenance_row_fails_closed_before_emission(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()
    # A record that CLAIMS Maintenance identity but does not strict-decode:
    # the runner must fail closed BEFORE emitting anything.
    torn = {
        "seq": max(_journal_seqs(ledger)) + 1,
        "schema_version": 1,
        "kind": "incident.daily_efficiency_report",
        "payload": {"event_kind": "daily_efficiency_report", "bogus": True},
        "idempotency_key": "torn-row",
    }
    with open(ledger.events_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(torn, sort_keys=True, separators=(",", ":")) + "\n")
    lines_before_run = len(_journal_lines(ledger))
    result = _run(ledger, day, corrections=[])
    assert result.status is dr.DailyRunStatus.NON_CLOSING
    assert result.receipt is None
    assert result.closure.outcome is dr.DailyClosureOutcome.INCOHERENT_READ
    assert "does not strict-decode" in (result.reason or "")
    # The torn row is untouched and no daily event was appended by the
    # failed run (raw-bytes check: the torn row itself would break the
    # strict-decoding helpers).
    assert len(_journal_lines(ledger)) == lines_before_run


# ---------------------------------------------------------------------------
# Mutation spies: sole writer, no authority, disposable-root discipline
# ---------------------------------------------------------------------------


def test_runner_module_adds_no_second_writer_or_raw_io() -> None:
    """Static scan: the runner delegates ALL writes to the T6.1 seam."""
    source = Path(dr.__file__).read_text(encoding="utf-8")
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
    assert hits == [], f"runner performs raw I/O: {hits}"
    # NO second writer: the runner never calls ledger.append itself — the
    # only append path is the delegated emit_daily_events canonical writer.
    assert source.count("ledger.append(") == 0
    assert "emit_daily_events(" in source
    # The SD3 prior-key lookup is DERIVED from the replayed journal (never
    # an always-never_seen fallback), and the fence seam is the T2.1 one.
    assert "committed_proposal_keys" in source
    assert "OccurrenceFence" in source
    # No schedule/ticket/repair/policy authority is imported or referenced.
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden_modules = [
        name
        for name in imported
        if any(
            part in name
            for part in ("resident", "repair", "ticket", "custody", "scheduler")
        )
    ]
    assert forbidden_modules == [], f"runner imports authority modules: {forbidden_modules}"
    # The canonical writer chain is still named exactly once across both
    # modules (T6.1 invariant preserved).
    reporter_source = Path(er.__file__).read_text(encoding="utf-8")
    assert reporter_source.count("ledger.append(") == 1


def test_run_writes_only_ledger_state_under_disposable_root(
    tmp_path: Path,
) -> None:
    root = _disposable_state_root(tmp_path)
    ledger = MaintenanceLedger(root)
    _seed_operational_chain(ledger, [(0, 12), (12, 24)])
    day = _Day()
    result = _run(ledger, day)
    assert result.status is dr.DailyRunStatus.CLOSED_APPENDED
    # The disposable root contains ONLY incident-ledger files: no schedule,
    # ticket, repair-queue, or policy state was created.
    created = sorted(
        str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()
    )
    assert created, "expected ledger state files"
    assert all(name.startswith(".megaplan/incident-ledger/") for name in created)
    assert not (root / "schedules").exists()
    assert not (root / "tickets").exists()
    # Daily observation never advances custody or verification authority.
    fresh = dr._scan_journal(ledger)
    engine = dr._replayed_engine(fresh)
    assert engine.custody.terminal is False
    assert engine.verification.coherence.value == "unknown"
    # The proposal is INERT by contract (never dispatchable).
    proposal_event = next(
        event
        for event in _committed_events(ledger)
        if isinstance(event, MaintenanceEvent)
        and event.event_kind is EventKind.DAILY_EFFICIENCY_PROPOSAL
    )
    assert proposal_event.payload.proposal.auto_materialization is False
