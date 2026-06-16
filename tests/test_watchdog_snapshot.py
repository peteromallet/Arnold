"""Tests for watchdog snapshot construction."""

from __future__ import annotations

import json

from arnold.pipelines.megaplan.pipelines.live_supervisor.model import (
    PlanEntry,
    SignalBundle,
    Triage,
)
from arnold.pipelines.megaplan.watchdog.snapshot import build_incidents, build_snapshot


def test_build_snapshot_discovers_plans(tmp_path):
    plan_dir = tmp_path / "repo" / ".megaplan" / "plans" / "my-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(json.dumps({"current_state": "planned", "name": "my-plan"}))

    snapshot = build_snapshot(roots=(str(tmp_path / "repo"),), process_scanner=lambda: ())
    assert len(snapshot.plans) == 1
    assert snapshot.plans[0].plan_name == "my-plan"
    assert len(snapshot.incidents) == 1


def test_build_incidents_assigns_triage():
    plan = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo",
        state={"current_state": "planned"},
    )
    signals = SignalBundle(
        liveness="stalled",
        liveness_reason="test",
        block_details={},
        doctor_findings=(),
        last_event_age_seconds=4000.0,
    )
    incidents = build_incidents((plan,), {"p1": signals}, set())
    assert incidents[0].triage is Triage.STALE

    incidents_live = build_incidents((plan,), {"p1": signals}, {"p1"})
    assert incidents_live[0].triage is Triage.LIVE


def test_build_snapshot_filters_by_max_age_hours(tmp_path):
    # Old plan: state.json mtime is set far in the past.
    old_plan_dir = tmp_path / "repo" / ".megaplan" / "plans" / "old-plan"
    old_plan_dir.mkdir(parents=True)
    (old_plan_dir / "state.json").write_text(json.dumps({"current_state": "planned", "name": "old-plan"}))
    import os
    os.utime(old_plan_dir / "state.json", (1000, 1000))

    # Recent plan: state.json mtime is now.
    recent_plan_dir = tmp_path / "repo" / ".megaplan" / "plans" / "recent-plan"
    recent_plan_dir.mkdir(parents=True)
    (recent_plan_dir / "state.json").write_text(json.dumps({"current_state": "planned", "name": "recent-plan"}))

    snapshot = build_snapshot(roots=(str(tmp_path / "repo"),), max_age_hours=1.0, process_scanner=lambda: ())
    plan_names = {p.plan_name for p in snapshot.plans}
    assert "recent-plan" in plan_names
    assert "old-plan" not in plan_names
