from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from megaplan import auto
from megaplan.auto import drive


def _make_plan_dir(tmp_path: Path, plan: str) -> Path:
    plan_dir = tmp_path / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan, "current_state": "planned"}),
        encoding="utf-8",
    )
    return plan_dir


def _stale_active_step_status(plan: str, last_activity_at: str) -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": "planned",
        "iteration": 1,
        "summary": "Plan is in state 'planned'.",
        "next_step": "execute",
        "valid_next": ["execute"],
        "active_step": {
            "step": "execute",
            "agent": "shannon",
            "mode": "persistent",
            "started_at": last_activity_at,
            "last_activity_at": last_activity_at,
            "health": "healthy",
            "recommended_action": "wait",
            "recommended_action_reason": "The active step is within its expected runtime window.",
        },
    }


def test_auto_clears_active_step_when_last_activity_is_stale(
    tmp_path: Path,
) -> None:
    plan = "timestamp-staleness-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    old_activity = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()

    state_path = plan_dir / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    state_data["active_step"] = {
        "step": "execute",
        "agent": "shannon",
        "mode": "persistent",
        "started_at": old_activity,
        "last_activity_at": old_activity,
    }
    state_path.write_text(json.dumps(state_data), encoding="utf-8")

    poll_count = {"n": 0}
    run_calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            return _stale_active_step_status(plan_name, old_activity)
        return {
            "success": True,
            "step": "status",
            "plan": plan_name,
            "state": "done",
            "iteration": 1,
            "summary": "Plan is in state 'done'.",
            "next_step": None,
            "valid_next": [],
        }

    def fake_run(
        args,
        cwd=None,
        timeout=None,
        idle_timeout=None,
        progress_env=None,
        liveness_plan_dir=None,
    ):
        run_calls.append(list(args))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_iterations=3,
            stall_threshold=10,
            poll_sleep=0,
            phase_idle_timeout=1,
            writer=lambda _m: None,
        )

    assert outcome.status == "done"
    assert len(run_calls) == 1
    assert run_calls[0][0] == "execute"
    assert run_calls[0][-2:] == ["--plan", plan]
    assert json.loads(state_path.read_text(encoding="utf-8")).get("active_step") is None
    assert any(
        event.get("recommended_action") == "terminate_idle_step"
        for event in outcome.events
    )
