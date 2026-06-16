"""Tests for watchdog NDJSON registry."""

from __future__ import annotations

import time

from arnold.pipelines.megaplan.watchdog.registry import (
    Observation,
    PlanStatus,
    WatchdogRegistry,
)


def test_registry_remembers_and_updates_seen_plans(tmp_path):
    path = tmp_path / "registry.ndjson"
    registry = WatchdogRegistry(path)

    class _Plan:
        pass

    p1 = _Plan()
    p1.plan_id = "p1"
    p1.state = {"current_state": "planned"}

    before = time.time()
    registry.update_seen([p1], now=before)
    registry.save()

    # Re-load and re-encounter the same plan.
    registry2 = WatchdogRegistry(path)
    after = before + 100
    p1.state = {"current_state": "executing"}
    registry2.update_seen([p1], now=after)
    entry = registry2.get("p1")
    assert entry is not None
    assert entry.first_seen == before
    assert entry.last_seen == after
    assert entry.last_state == "executing"


def test_registry_marks_disappeared_and_preserves_history(tmp_path):
    path = tmp_path / "registry.ndjson"
    registry = WatchdogRegistry(path)

    class _Plan:
        pass

    p1 = _Plan()
    p1.plan_id = "p1"
    p1.state = {"current_state": "planned"}

    registry.update_seen([p1], now=time.time())
    registry.mark_disappeared(["p1"], [])
    entry = registry.get("p1")
    assert entry.incident_count == 1
    registry.bump_retry("p1")
    assert entry.retry_count == 1


def test_registry_records_observations_and_detects_transitions(tmp_path):
    path = tmp_path / "registry.ndjson"
    registry = WatchdogRegistry(path)

    # First observation: plan is running.
    obs1 = Observation(
        ts=1000.0,
        state="finalized",
        triage="live",
        health_category="all_good",
        has_live_process=True,
    )
    registry.record_observation("p1", obs1, now=1000.0)

    # Second observation: plan finished.
    obs2 = Observation(
        ts=2000.0,
        state="done",
        triage="stale",
        health_category="all_good",
        has_live_process=False,
    )
    transitions = registry.compute_transitions({"p1": obs2}, now=2000.0)
    registry.record_observation("p1", obs2, now=2000.0)
    assert len(transitions) == 1
    assert transitions[0].plan_id == "p1"
    assert transitions[0].previous_status == PlanStatus.RUNNING
    assert transitions[0].current_status == PlanStatus.FINISHED
    assert transitions[0].previous_state == "finalized"
    assert transitions[0].current_state == "done"


def test_registry_detects_disappearance(tmp_path):
    path = tmp_path / "registry.ndjson"
    registry = WatchdogRegistry(path)

    obs = Observation(
        ts=1000.0,
        state="done",
        triage="stale",
        health_category="all_good",
        has_live_process=False,
    )
    registry.record_observation("p1", obs, now=1000.0)

    transitions = registry.compute_transitions({}, now=2000.0)
    registry.record_observation("p1", Observation(ts=2000.0, state=None, triage="disappeared", health_category="unknown", has_live_process=False), now=2000.0)
    assert len(transitions) == 1
    assert transitions[0].previous_status == PlanStatus.FINISHED
    assert transitions[0].current_status == PlanStatus.DISAPPEARED


def test_registry_detects_cancellation_and_failure(tmp_path):
    path = tmp_path / "registry.ndjson"
    registry = WatchdogRegistry(path)

    obs_run = Observation(ts=1000.0, state="executing", triage="live", health_category="all_good", has_live_process=True)
    obs_cancel = Observation(ts=2000.0, state="cancelled", triage="stale", health_category="plan_issue", has_live_process=False)
    obs_fail = Observation(ts=3000.0, state="failed", triage="stale", health_category="plan_issue", has_live_process=False)

    registry.record_observation("p1", obs_run, now=1000.0)
    transitions_cancel = registry.compute_transitions({"p1": obs_cancel}, now=2000.0)
    registry.record_observation("p1", obs_cancel, now=2000.0)
    transitions_fail = registry.compute_transitions({"p1": obs_fail}, now=3000.0)
    registry.record_observation("p1", obs_fail, now=3000.0)

    assert len(transitions_cancel) == 1
    assert transitions_cancel[0].previous_status == PlanStatus.RUNNING
    assert transitions_cancel[0].current_status == PlanStatus.CANCELLED
    assert len(transitions_fail) == 1
    assert transitions_fail[0].previous_status == PlanStatus.CANCELLED
    assert transitions_fail[0].current_status == PlanStatus.FAILED
