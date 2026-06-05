from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from arnold.pipelines.megaplan._core import ensure_runtime_layout
from arnold.pipelines.megaplan.workers import CommandResult
from arnold.pipelines.megaplan.workers.shannon import run_shannon_step


def _make_state(tmp_path: Path) -> tuple[Path, dict]:
    ensure_runtime_layout(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "wall-clock-plan"
    plan_dir.mkdir(parents=True)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    state = {
        "name": "wall-clock-plan",
        "idea": "test shannon timeout plumbing",
        "current_state": "critiqued",
        "iteration": 1,
        "created_at": "2026-05-26T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "mode": "code",
            "robustness": "standard",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": 1,
                "file": "plan_v1.md",
                "hash": "sha256:test",
                "timestamp": "2026-05-26T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {},
        "last_gate": {},
    }
    (plan_dir / "plan_v1.md").write_text("# Plan\nDo it.\n", encoding="utf-8")
    return plan_dir, state


def test_main_shannon_run_command_has_wall_clock_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, state = _make_state(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_AUTO_PATCH", "0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_EXECUTE_TIMEOUT_SECONDS", "1234")
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    fake_result = CommandResult(
        command=["shannon"],
        cwd=tmp_path,
        returncode=0,
        stdout=json.dumps(
            {
                "structured_output": plan_payload,
                "session_id": "shannon-session",
                "total_cost_usd": 0.0,
            }
        ),
        stderr="",
        duration_ms=10,
    )

    with patch("arnold.pipelines.megaplan.workers.shannon.pane_pids", return_value=[]), \
         patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
        run_shannon_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="write a small plan",
        )

    assert run_command.call_count == 1
    assert run_command.call_args.kwargs["timeout"] == 1234
