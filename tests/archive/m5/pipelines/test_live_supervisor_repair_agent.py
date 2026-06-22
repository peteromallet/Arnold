"""Tests for live_supervisor repair agents."""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.pipelines.live_supervisor.model import (
    Incident,
    PlanEntry,
    RepairRecommendation,
    SignalBundle,
    Triage,
)
from arnold.pipelines.megaplan.pipelines.live_supervisor.repair_agent import (
    FakeRepairAgent,
    HermesRepairAgent,
    RepairUnavailable,
)


def _incident(plan_id: str = "p1") -> Incident:
    return Incident(
        plan_entry=PlanEntry(
            plan_id=plan_id,
            plan_name=f"plan-{plan_id}",
            plan_dir=f"/tmp/{plan_id}",
            repo_path="/tmp/repo",
            state={},
        ),
        signals=SignalBundle(liveness="stalled", liveness_reason="test", block_details={}, doctor_findings=()),
        triage=Triage.STALE,
    )


def test_fake_repair_agent_returns_mapped_recommendation():
    agent = FakeRepairAgent({"p1": RepairRecommendation(command="doctor", context={"plan_name": "plan-p1"})})
    rec = agent.diagnose_and_recommend(_incident("p1"), {})
    assert rec.command == "doctor"
    assert rec.context["plan_name"] == "plan-p1"


def test_fake_repair_agent_returns_default():
    agent = FakeRepairAgent(None, default=RepairRecommendation(command="trace"))
    rec = agent.diagnose_and_recommend(_incident("p2"), {})
    assert rec.command == "trace"


def test_fake_repair_agent_fallback_to_doctor():
    agent = FakeRepairAgent(None)
    rec = agent.diagnose_and_recommend(_incident("p3"), {})
    assert rec.command == "doctor"


def test_hermes_repair_agent_without_launcher_raises_repair_unavailable():
    agent = HermesRepairAgent(launcher=None)
    with pytest.raises(RepairUnavailable):
        agent.diagnose_and_recommend(_incident(), {})
