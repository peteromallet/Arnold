"""Tests for watchdog signal computation."""

from __future__ import annotations

import json
import time

import pytest

from arnold.pipelines.megaplan.watchdog.signals import compute_signal_bundle


def _write_state_and_events(plan_dir, *, events=None, state=None):
    plan_dir.mkdir(parents=True, exist_ok=True)
    if state is not None:
        (plan_dir / "state.json").write_text(json.dumps(state))
    if events is not None:
        (plan_dir / "events.ndjson").write_text(
            "".join(json.dumps(ev) + "\n" for ev in events)
        )


def test_progressing_no_events(tmp_path):
    plan_dir = tmp_path / "plan"
    _write_state_and_events(plan_dir, state={"current_state": "planned"}, events=[])
    bundle = compute_signal_bundle(plan_dir)
    assert bundle.liveness == "quiet"


def test_stalled_old_events(tmp_path):
    plan_dir = tmp_path / "plan"
    old_ts = "2026-06-14T00:00:00+00:00"
    _write_state_and_events(
        plan_dir,
        state={"current_state": "planned"},
        events=[{"ts_utc": old_ts, "kind": "llm_token_heartbeat"}],
    )
    bundle = compute_signal_bundle(plan_dir)
    assert bundle.liveness == "stalled"
    assert bundle.last_event_age_seconds is not None
    assert bundle.last_event_age_seconds > 0


def test_in_flight_llm_detection(tmp_path):
    plan_dir = tmp_path / "plan"
    now = time.time()
    from datetime import datetime, timezone

    ts = datetime.fromtimestamp(now - 10, timezone.utc).isoformat()
    _write_state_and_events(
        plan_dir,
        state={"current_state": "planned"},
        events=[
            {"ts_utc": ts, "kind": "llm_call_start", "payload": {"request_id": "r1"}},
        ],
    )
    bundle = compute_signal_bundle(plan_dir)
    assert bundle.has_in_flight_llm is True
    assert bundle.liveness == "progressing"


def test_block_details_from_gated_state(tmp_path):
    plan_dir = tmp_path / "plan"
    _write_state_and_events(plan_dir, state={"current_state": "gated"}, events=[])
    bundle = compute_signal_bundle(plan_dir)
    assert bundle.block_details["is_blocked"] is True
    assert "resume" in bundle.block_details["recoverable_via"]


def test_stale_lock_finding(tmp_path):
    plan_dir = tmp_path / "plan"
    _write_state_and_events(plan_dir, state={"current_state": "planned"}, events=[])
    lock = plan_dir / ".plan.lock"
    lock.write_text("")
    old = time.time() - 400
    import os

    os.utime(lock, (old, old))
    bundle = compute_signal_bundle(plan_dir)
    assert any(f.check == "stale_lock" for f in bundle.doctor_findings)


def test_degraded_on_signal_computation_failure(tmp_path, monkeypatch):
    plan_dir = tmp_path / "plan"
    _write_state_and_events(plan_dir, state={"current_state": "planned"}, events=[])

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.watchdog.signals._compute_liveness_and_reason",
        _boom,
    )
    bundle = compute_signal_bundle(plan_dir)
    assert bundle.degraded is True
    assert "simulated failure" in bundle.failure_reason
