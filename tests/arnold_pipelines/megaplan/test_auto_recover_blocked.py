from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan import auto


def test_drive_stops_on_non_retryable_recover_blocked_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "blocked",
                "resume_cursor": {
                    "phase": "execute",
                    "retry_strategy": "manual_review",
                },
            }
        ),
        encoding="utf-8",
    )

    status_calls = 0
    run_calls = 0

    def fake_status(plan: str, **kwargs):
        nonlocal status_calls
        status_calls += 1
        assert plan == "demo"
        return {
            "state": "blocked",
            "next_step": "recover-blocked",
            "valid_next": ["recover-blocked"],
            "progress": {},
        }

    def fake_run_planning_phase(args, **kwargs):
        nonlocal run_calls
        run_calls += 1
        assert args == [
            "override",
            "recover-blocked",
            "--reason",
            "megaplan auto: recover blocked plan after blocker resolution",
            "--plan",
            "demo",
        ]
        return (
            1,
            "",
            json.dumps(
                {
                    "success": False,
                    "error": "blocked_recovery_not_resolved",
                    "message": (
                        "recover-blocked requires every current blocker "
                        "to be explicitly resolved as non-terminal"
                    ),
                }
            ),
        )

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive("demo", cwd=tmp_path)

    assert outcome.status == "blocked"
    assert outcome.final_state == "blocked"
    assert outcome.iterations == 1
    assert outcome.last_phase == "recover-blocked"
    assert outcome.blocking_reasons == ["blocked_recovery_not_resolved"]
    assert "explicitly resolved as non-terminal" in outcome.reason
    assert status_calls == 1
    assert run_calls == 1
