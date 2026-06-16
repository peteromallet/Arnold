"""Tests for live_supervisor pipeline steps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline import StepContext
from arnold.pipelines.megaplan.pipelines.live_supervisor.model import (
    CheckFinding,
    HealthCategory,
    Incident,
    PlanEntry,
    RepairRecommendation,
    SignalBundle,
    Snapshot,
    Triage,
)
from arnold.pipelines.megaplan.pipelines.live_supervisor.repair_agent import FakeRepairAgent, HermesRepairAgent
from arnold.pipelines.megaplan.pipelines.live_supervisor.steps import (
    ClassifyStep,
    DiagnoseStep,
    RecheckEmitStep,
    RepairDecisionStep,
)


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


class TestClassifyStep:
    def test_writes_classifications_and_sets_state(self, tmp_path):
        ctx = _ctx(tmp_path, _snapshot())
        result = ClassifyStep().run(ctx)
        assert result.next == "diagnose"
        artifact = json.loads((tmp_path / "classify" / "classifications.json").read_text())
        assert artifact[0]["health_category"] == "plan_issue"
        assert result.state_patch["classifications"] == artifact

    def test_detects_false_stall(self, tmp_path):
        ctx = _ctx(tmp_path, _snapshot(HealthCategory.FALSE_STALL))
        result = ClassifyStep().run(ctx)
        artifact = json.loads((tmp_path / "classify" / "classifications.json").read_text())
        assert artifact[0]["health_category"] == "false_stall"


class TestDiagnoseStep:
    def test_writes_diagnoses(self, tmp_path):
        snapshot = _snapshot()
        ctx = _ctx(tmp_path, snapshot)
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
        assert "liveness=stalled" in artifact[0]["reasoning"]


class TestRepairDecisionStep:
    def test_degraded_mode_report_only_no_credentials(self, tmp_path):
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
        assert "no repair agent" in artifact[0]["verdict"]["reason"]

    def test_allows_safe_doctor_recommendation(self, tmp_path):
        snapshot = _snapshot()
        agent = FakeRepairAgent(
            {"p1": RepairRecommendation(command="doctor", context={"plan_name": "my-plan"})}
        )
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={
                "snapshot": snapshot.to_dict(),
                "classifications": [{"plan_id": "p1", "health_category": "plan_issue"}],
                "diagnoses": [{"health_category": "plan_issue", "findings": [], "reasoning": "test"}],
            },
        )
        result = RepairDecisionStep(agent=agent).run(ctx)
        artifact = json.loads((tmp_path / "repair_decision" / "repair_decisions.json").read_text())
        assert artifact[0]["verdict"]["allowed"] is True


    def test_recommends_auto_for_resumable_plan_issue(self, tmp_path):
        snapshot = _snapshot()
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={
                "snapshot": snapshot.to_dict(),
                "classifications": [{"plan_id": "p1", "health_category": "plan_issue"}],
                "diagnoses": [{"health_category": "plan_issue", "findings": [], "reasoning": "test"}],
            },
        )
        result = RepairDecisionStep().run(ctx)
        artifact = json.loads((tmp_path / "repair_decision" / "repair_decisions.json").read_text())
        assert artifact[0]["recommended_command"] == "auto"
        assert artifact[0]["verdict"]["allowed"] is True

    def test_recommends_clean_lock_for_terminal_stale_lock(self, tmp_path):
        entry = PlanEntry(
            plan_id="p1",
            plan_name="my-plan",
            plan_dir="/tmp/my-plan",
            repo_path="/tmp/repo",
            state={"current_state": "finalized"},
        )
        signals = SignalBundle(
            liveness="stalled",
            liveness_reason="no events",
            block_details={},
            doctor_findings=(CheckFinding("plan", "stale_lock", "fail", "lock is stale"),),
        )
        incident = Incident(plan_entry=entry, signals=signals, triage=Triage.STALE)
        snapshot = Snapshot.now(plans=(entry,), incidents=(incident,))
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={
                "snapshot": snapshot.to_dict(),
                "classifications": [{"plan_id": "p1", "health_category": "harness_issue"}],
                "diagnoses": [{"health_category": "harness_issue", "findings": [], "reasoning": "test"}],
            },
        )
        result = RepairDecisionStep().run(ctx)
        artifact = json.loads((tmp_path / "repair_decision" / "repair_decisions.json").read_text())
        assert artifact[0]["recommended_command"] == "rm /tmp/my-plan/.plan.lock"
        assert artifact[0]["verdict"]["allowed"] is True


class TestRecheckEmitStep:
    def test_five_minute_wait_emitted_not_blocked(self, tmp_path):
        import time

        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={"repair_decisions": []},
        )
        before = time.time()
        result = RecheckEmitStep().run(ctx)
        after = time.time()
        assert result.next == "halt"
        artifact = json.loads((tmp_path / "recheck_emit" / "recheck_emit.json").read_text())
        assert artifact["resumable"] is True
        assert before + 250 <= artifact["recheck_after"] <= after + 350
        assert (after - before) < 1.0, "step must not sleep"
