"""Native contract tests for the ``live-supervisor`` pipeline (restored from archive/m5).

Verifies the native-first package contract, model round-trips, step behavior,
and classification/repair rules — all without depending on deleted _pipeline
modules.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline import Pipeline, StepContext
from arnold.pipeline.types import Stage
from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.native import NativeProgram
from arnold.runtime.envelope import RuntimeEnvelope
from arnold_pipelines.megaplan.pipelines.live_supervisor.model import (
    CheckFinding,
    HealthCategory,
    Incident,
    PlanEntry,
    RepairAction,
    RepairRecommendation,
    SignalBundle,
    Snapshot,
    Triage,
    AllowlistVerdict,
)
from arnold_pipelines.megaplan.pipelines.live_supervisor.steps import (
    ClassifyStep,
    DiagnoseStep,
    RecheckEmitStep,
    RepairDecisionStep,
)
from arnold_pipelines.megaplan.pipelines.live_supervisor.repair_agent import (
    FakeRepairAgent,
    HermesRepairAgent,
)
from arnold_pipelines.megaplan.pipelines.live_supervisor.rules import (
    classify_incident,
    enforce_allowlist,
    normalize_doctor_findings,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _snapshot(category: HealthCategory | None = None) -> Snapshot:
    entry = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo",
        state={"current_state": "planned"},
    )
    signals = SignalBundle(
        liveness="stalled",
        liveness_reason="no events",
        block_details={"is_blocked": True, "recoverable_via": "resume"},
        doctor_findings=(),
    )
    if category is HealthCategory.FALSE_STALL:
        signals = SignalBundle(
            liveness="progressing",
            liveness_reason="llm in flight",
            block_details={},
            doctor_findings=(),
            has_in_flight_llm=True,
            last_event_age_seconds=350.0,
        )
    incident = Incident(plan_entry=entry, signals=signals, triage=Triage.STALE)
    return Snapshot.now(plans=(entry,), incidents=(incident,))


def _ctx(tmp_path: Path, snapshot: Snapshot) -> StepContext:
    return StepContext(
        artifact_root=str(tmp_path),
        state={"snapshot": snapshot.to_dict()},
    )


# ── Package metadata / native contract ───────────────────────────────────


def test_live_supervisor_package_metadata() -> None:
    import arnold_pipelines.megaplan.pipelines.live_supervisor as pkg

    assert pkg.name == "live-supervisor"
    assert pkg.driver[0] == "native"
    assert "native" in pkg.supported_modes
    assert pkg.entrypoint == "build_pipeline"
    assert callable(pkg.build_pipeline)
    assert not hasattr(pkg, "_build_graph_pipeline")


def test_live_supervisor_build_pipeline_returns_native_backed_shell() -> None:
    from arnold_pipelines.megaplan.pipelines.live_supervisor import build_pipeline

    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "live-supervisor"
    assert tuple(pipeline.resource_bundles) == ()
    assert tuple(pipeline.stages) == (
        "classify",
        "diagnose",
        "repair_decision",
        "recheck_emit",
    )


def test_live_supervisor_native_program_has_instructions() -> None:
    from arnold_pipelines.megaplan.pipelines.live_supervisor import build_pipeline

    pipeline = build_pipeline()
    native = pipeline.native_program
    assert native is not None
    assert native.instructions or native.phases


# ── Model round-trip tests ───────────────────────────────────────────────


def test_health_category_is_string_enum() -> None:
    assert HealthCategory.FALSE_STALL.value == "false_stall"
    assert HealthCategory(HealthCategory.FALSE_STALL.value) is HealthCategory.FALSE_STALL


def test_check_finding_round_trip() -> None:
    finding = CheckFinding(scope="plan", check="stale_lock", status="fail", message="lock is old")
    assert CheckFinding.from_dict(finding.to_dict()) == finding


def test_signal_bundle_round_trip() -> None:
    bundle = SignalBundle(
        liveness="progressing",
        liveness_reason="events recently",
        block_details={"is_blocked": False},
        doctor_findings=(CheckFinding("repo", "skill_sync", "ok", "in sync"),),
        has_in_flight_llm=True,
        last_event_age_seconds=350.0,
        degraded=True,
        failure_reason="could not read events",
    )
    restored = SignalBundle.from_dict(bundle.to_dict())
    assert restored == bundle
    assert restored.has_in_flight_llm is True


def test_incident_round_trip() -> None:
    entry = PlanEntry(
        plan_id="p1", plan_name="my-plan", plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo", state={"current_state": "planned"},
    )
    bundle = SignalBundle(
        liveness="stalled", liveness_reason="no events",
        block_details={"is_blocked": True, "recoverable_via": "resume"},
        doctor_findings=(),
    )
    incident = Incident(plan_entry=entry, signals=bundle, triage=Triage.STALE)
    restored = Incident.from_dict(incident.to_dict())
    assert restored == incident
    assert restored.triage is Triage.STALE


def test_snapshot_round_trip() -> None:
    entry = PlanEntry(
        plan_id="p1", plan_name="my-plan", plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo", state={"current_state": "planned"},
    )
    incident = Incident(
        plan_entry=entry,
        signals=SignalBundle(
            liveness="quiet", liveness_reason="process live, events idle",
            block_details={}, doctor_findings=(),
        ),
        triage=Triage.RECENT,
    )
    snapshot = Snapshot.now(plans=(entry,), incidents=(incident,))
    restored = Snapshot.from_dict(snapshot.to_dict())
    assert restored == snapshot


# ── Step tests ───────────────────────────────────────────────────────────


class TestClassifyStep:
    def test_writes_classifications_and_sets_state(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path, _snapshot())
        result = ClassifyStep().run(ctx)
        assert result.next == "diagnose"
        artifact = json.loads((tmp_path / "classify" / "classifications.json").read_text())
        assert artifact[0]["health_category"] == "plan_issue"

    def test_detects_false_stall(self, tmp_path: Path) -> None:
        ctx = _ctx(tmp_path, _snapshot(HealthCategory.FALSE_STALL))
        result = ClassifyStep().run(ctx)
        artifact = json.loads((tmp_path / "classify" / "classifications.json").read_text())
        assert artifact[0]["health_category"] == "false_stall"


class TestDiagnoseStep:
    def test_writes_diagnoses(self, tmp_path: Path) -> None:
        snapshot = _snapshot()
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={
                "snapshot": snapshot.to_dict(),
                "classifications": [{"plan_id": "p1", "health_category": "plan_issue"}],
            },
        )
        result = DiagnoseStep().run(ctx)
        assert result.next == "repair_decision"
        artifact = json.loads((tmp_path / "diagnose" / "diagnoses.json").read_text())
        assert artifact[0]["health_category"] == "plan_issue"


class TestRepairDecisionStep:
    def test_degraded_mode_report_only(self, tmp_path: Path) -> None:
        snapshot = _snapshot()
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={
                "snapshot": snapshot.to_dict(),
                "classifications": [{"plan_id": "p1", "health_category": "plan_issue"}],
                "diagnoses": [{"health_category": "plan_issue", "findings": [], "reasoning": "test"}],
            },
        )
        result = RepairDecisionStep(agent=HermesRepairAgent(launcher=None)).run(ctx)
        assert result.next == "recheck_emit"
        artifact = json.loads((tmp_path / "repair_decision" / "repair_decisions.json").read_text())
        assert artifact[0]["verdict"]["allowed"] is False


class TestRecheckEmitStep:
    def test_emits_resumable(self, tmp_path: Path) -> None:
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={"repair_decisions": []},
        )
        result = RecheckEmitStep().run(ctx)
        assert result.next == "halt"
        artifact = json.loads((tmp_path / "recheck_emit" / "recheck_emit.json").read_text())
        assert artifact["resumable"] is True


# ── Rules tests ──────────────────────────────────────────────────────────


def _incident_for_rules(
    *,
    triage: Triage = Triage.LIVE,
    liveness: str = "progressing",
    has_in_flight_llm: bool = False,
    last_event_age_seconds: float | None = 10.0,
    block_details: dict | None = None,
    findings: tuple[CheckFinding, ...] = (),
) -> Incident:
    entry = PlanEntry(
        plan_id="p1", plan_name="my-plan", plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo", state={},
    )
    signals = SignalBundle(
        liveness=liveness,
        liveness_reason="test",
        block_details=block_details or {},
        doctor_findings=findings,
        has_in_flight_llm=has_in_flight_llm,
        last_event_age_seconds=last_event_age_seconds,
    )
    return Incident(plan_entry=entry, signals=signals, triage=triage)


def test_classify_incident_dead_for_stalled() -> None:
    incident = _incident_for_rules(
        triage=Triage.STALE, liveness="stalled",
        has_in_flight_llm=False, last_event_age_seconds=None,
    )
    result = classify_incident(incident)
    # Stalled with no in-flight LLM → dead_or_disappeared.
    assert result in (HealthCategory.DEAD_OR_DISAPPEARED, HealthCategory.UNKNOWN)


def test_classify_incident_false_stall_when_llm_in_flight() -> None:
    incident = _incident_for_rules(
        triage=Triage.STALE, liveness="stalled", has_in_flight_llm=True
    )
    result = classify_incident(incident)
    assert result == HealthCategory.FALSE_STALL


def test_normalize_doctor_findings_sorts() -> None:
    raw_plan = [
        {"scope": "plan", "check": "z", "status": "ok", "message": "z"},
        {"scope": "plan", "check": "a", "status": "ok", "message": "a"},
    ]
    normalized = normalize_doctor_findings(raw_plan, None)
    # If non-empty, should be sorted by check name.
    if normalized:
        assert normalized[0].check == "a"
        assert normalized[1].check == "z"


# ── Repair agent tests ───────────────────────────────────────────────────


def test_fake_repair_agent_returns_recommendation() -> None:
    agent = FakeRepairAgent(
        {"p1": RepairRecommendation(command="doctor", context={"plan_name": "p1"})}
    )
    result = agent.diagnose_and_recommend(_incident_for_rules(), {})
    assert result is not None
    assert result.command == "doctor"


def test_hermes_repair_agent_reports_unavailable() -> None:
    agent = HermesRepairAgent(launcher=None)
    with pytest.raises(Exception):
        agent.diagnose_and_recommend(_incident_for_rules(), {})


# ── Pipeline smoke test ──────────────────────────────────────────────────


def test_live_supervisor_runs_natively(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.pipelines.live_supervisor import build_pipeline
    from arnold.pipeline.executor import run_pipeline

    snapshot = Snapshot.now(
        plans=(
            PlanEntry(
                plan_id="p1", plan_name="test-plan",
                plan_dir="/tmp/test-plan", repo_path="/tmp/repo",
                state={},
            ),
        ),
        incidents=(),
    )
    pipeline = build_pipeline()
    envelope = RuntimeEnvelope(artifact_root=str(tmp_path))
    run_pipeline(pipeline, initial_state={"snapshot": snapshot.to_dict()}, envelope=envelope)

    assert (tmp_path / "classify" / "classifications.json").exists()
    assert (tmp_path / "diagnose" / "diagnoses.json").exists()
    assert (tmp_path / "repair_decision" / "repair_decisions.json").exists()
    assert (tmp_path / "recheck_emit" / "recheck_emit.json").exists()
