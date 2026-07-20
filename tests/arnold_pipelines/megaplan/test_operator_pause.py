from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.operator_pause import is_paused, pause_chain, resume_chain
from arnold_pipelines.megaplan.chain.spec import ChainState, load_chain_state, save_chain_state
from arnold_pipelines.megaplan.types import CliError


def _chain(tmp_path: Path, *, complete: bool = False) -> tuple[Path, Path]:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    brief = initiative / "brief.md"
    brief.write_text("# brief\n")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n  north_star: brief.md\n"
        "milestones:\n  - label: M1\n    idea: brief.md\n"
    )
    plan = tmp_path / ".megaplan" / "plans" / "demo-plan"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps(
            {
                "current_state": "blocked",
                "resume_cursor": {"phase": "execute", "retry_strategy": "rerun_phase"},
                "active_step": {"phase": "execute", "worker_pid": 999999},
                "meta": {"kept": True},
            }
        )
    )
    state = ChainState(
        current_milestone_index=1 if complete else 0,
        current_plan_name=None if complete else "demo-plan",
        last_state="blocked",
        completed=[{"label": "M1", "plan": "demo-plan", "status": "done"}] if complete else [],
    )
    save_chain_state(spec, state)
    return spec, plan


def test_pause_and_resume_preserve_cursor_workspace_and_artifacts(tmp_path: Path) -> None:
    spec, plan = _chain(tmp_path)
    artifact = plan / "result.md"
    artifact.write_text("keep me")
    before = json.loads((plan / "state.json").read_text())

    paused = pause_chain(spec, tmp_path, reason="capacity control")

    after = json.loads((plan / "state.json").read_text())
    chain_state = load_chain_state(spec)
    assert paused["changed"] is True
    assert is_paused(chain_state)
    assert chain_state.last_state == "paused"
    assert after["current_state"] == "paused"
    assert after["resume_cursor"] == before["resume_cursor"]
    assert after["active_step"] == before["active_step"]
    assert artifact.read_text() == "keep me"

    resumed = resume_chain(spec, tmp_path)

    restored = json.loads((plan / "state.json").read_text())
    assert resumed["restored_plan_state"] == "blocked"
    assert restored["current_state"] == "blocked"
    assert restored["resume_cursor"] == before["resume_cursor"]
    assert restored["active_step"] == before["active_step"]
    assert not is_paused(load_chain_state(spec))


def test_pause_is_idempotent_and_completed_chain_is_excluded(tmp_path: Path) -> None:
    spec, _ = _chain(tmp_path)
    pause_chain(spec, tmp_path, reason="first")
    second = pause_chain(spec, tmp_path, reason="second")
    assert second["changed"] is False
    assert second["authority"]["reason"] == "first"

    other = tmp_path / "complete"
    other.mkdir()
    complete_spec, _ = _chain(other, complete=True)
    with pytest.raises(CliError, match="completed chains cannot be paused"):
        pause_chain(complete_spec, other, reason="must refuse")


def test_cloud_session_pause_stops_only_owned_runner_and_repair(tmp_path: Path, monkeypatch) -> None:
    from arnold_pipelines.megaplan.cloud import operator_control

    spec, _ = _chain(tmp_path)
    marker = tmp_path / "markers" / "demo.json"
    marker.parent.mkdir()
    marker.write_text(json.dumps({"session": "demo", "relaunch_command": "safe command"}))
    calls = []

    class Completed:
        returncode = 0

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return Completed()

    monkeypatch.setattr(operator_control.subprocess, "run", fake_run)
    monkeypatch.setattr(operator_control, "_stop_owned_pidfile", lambda path, session: True)
    result = operator_control.pause_session(
        spec=spec,
        workspace=tmp_path,
        session="demo",
        marker_path=marker,
        reason="operator",
        actor="test",
    )
    assert calls == [["tmux", "kill-session", "-t", "demo"]]
    assert result["runner_stopped"] is True
    assert result["repair_stopped"] is True
    assert json.loads(marker.read_text())["should_run"] is False

    calls.clear()

    def resume_run(argv, **kwargs):
        calls.append(argv)
        result = Completed()
        if argv[:3] == ["tmux", "has-session", "-t"]:
            result.returncode = 1
        return result

    monkeypatch.setattr(operator_control.subprocess, "run", resume_run)
    resumed = operator_control.resume_session(
        spec=spec,
        workspace=tmp_path,
        session="demo",
        marker_path=marker,
        actor="test",
    )
    assert calls == [
        ["tmux", "has-session", "-t", "demo"],
        ["tmux", "new-session", "-d", "-s", "demo", "-c", str(tmp_path), "safe command"],
    ]
    assert resumed["runner_started"] is True
    assert json.loads(marker.read_text())["should_run"] is True
