"""Round-trip tests for live_supervisor models."""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.pipelines.live_supervisor.model import (
    AllowlistVerdict,
    CheckFinding,
    Diagnosis,
    HealthCategory,
    Incident,
    PlanEntry,
    RepairAction,
    RepairRecommendation,
    SignalBundle,
    Snapshot,
    Triage,
)


def test_health_category_is_string_enum():
    assert HealthCategory.FALSE_STALL.value == "false_stall"
    assert HealthCategory(HealthCategory.FALSE_STALL.value) is HealthCategory.FALSE_STALL


def test_check_finding_round_trip():
    finding = CheckFinding(scope="plan", check="stale_lock", status="fail", message="lock is old")
    assert CheckFinding.from_dict(finding.to_dict()) == finding


def test_signal_bundle_defaults_and_degraded_round_trip():
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
    assert restored.last_event_age_seconds == 350.0


def test_incident_round_trip():
    entry = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo",
        state={"current_state": "planned"},
    )
    bundle = SignalBundle(
        liveness="stalled",
        liveness_reason="no events",
        block_details={"is_blocked": True, "recoverable_via": "resume"},
        doctor_findings=(),
    )
    incident = Incident(plan_entry=entry, signals=bundle, triage=Triage.STALE)
    restored = Incident.from_dict(incident.to_dict())
    assert restored == incident
    assert restored.triage is Triage.STALE


def test_allowlist_verdict_with_action_round_trip():
    action = RepairAction(command="doctor", context={"plan_name": "my-plan"})
    verdict = AllowlistVerdict(allowed=True, reason="safe read-only", action=action)
    restored = AllowlistVerdict.from_dict(verdict.to_dict())
    assert restored == verdict
    assert restored.action is not None


def test_snapshot_round_trip():
    entry = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo",
        state={"current_state": "planned"},
    )
    incident = Incident(
        plan_entry=entry,
        signals=SignalBundle(
            liveness="quiet",
            liveness_reason="process live, events idle",
            block_details={},
            doctor_findings=(),
        ),
        triage=Triage.RECENT,
    )
    snapshot = Snapshot.now(plans=(entry,), incidents=(incident,))
    restored = Snapshot.from_dict(snapshot.to_dict())
    assert restored == snapshot


def test_plan_entry_chain_spec_optional():
    entry = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo",
        state={},
    )
    assert entry.chain_spec_path is None
    assert PlanEntry.from_dict(entry.to_dict()).chain_spec_path is None
