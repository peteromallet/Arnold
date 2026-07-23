from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import operator_control


def test_resume_injects_managed_repair_route_into_tmux_session(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    marker_dir = tmp_path / ".megaplan" / "cloud-sessions"
    marker_path = marker_dir / "demo.json"
    marker_dir.mkdir(parents=True)
    marker_path.write_text(
        json.dumps(
            {
                "session": "demo",
                "run_kind": "chain",
                "relaunch_command": "python -m demo",
                "operator_pause": {"active": True},
            }
        ),
        encoding="utf-8",
    )
    resume_calls: list[dict[str, object]] = []

    def fake_resume_chain(*args, **kwargs):
        resume_calls.append(dict(kwargs))
        return {"changed": True, "paused": False}

    monkeypatch.setattr(operator_control, "resume_chain", fake_resume_chain)
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if argv[1] == "new-session":
            launching = json.loads(marker_path.read_text(encoding="utf-8"))
            assert "operator_pause" not in launching
            assert launching["should_run"] is True
        return subprocess.CompletedProcess(argv, 1 if argv[1] == "has-session" else 0)

    monkeypatch.setattr(operator_control.subprocess, "run", fake_run)

    result = operator_control.resume_session(
        spec=tmp_path / "chain.yaml",
        workspace=workspace,
        session="demo",
        marker_path=marker_path,
        actor="test",
    )

    launch = calls[1]
    assert result["runner_started"] is True
    assert f"ARNOLD_REPAIR_QUEUE_ROOT={tmp_path / '.megaplan' / 'repair-queue'}" in launch
    assert f"ARNOLD_REPAIR_MARKER_DIR={marker_dir}" in launch
    assert "ARNOLD_REPAIR_SESSION=demo" in launch
    assert "ARNOLD_REPAIR_RUN_KIND=chain" in launch
    assert resume_calls == [{"actor": "test", "verify_execution_binding": True}]
    assert not any(item.startswith("MEGAPLAN_CHAIN_NO_PUSH=") for item in launch)
    assert launch[-1] == "python -m demo"
    updated = json.loads(marker_path.read_text(encoding="utf-8"))
    assert "operator_pause" not in updated
    assert updated["should_run"] is True


def test_resume_no_push_preserves_dirty_milestone_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    marker_dir = tmp_path / ".megaplan" / "cloud-sessions"
    marker_path = marker_dir / "demo.json"
    marker_dir.mkdir(parents=True)
    marker_path.write_text(
        json.dumps(
            {
                "session": "demo",
                "run_kind": "chain",
                "relaunch_command": "python -m demo",
                "operator_pause": {"active": True},
            }
        ),
        encoding="utf-8",
    )
    resume_calls: list[dict[str, object]] = []

    def fake_resume_chain(*args, **kwargs):
        resume_calls.append(dict(kwargs))
        return {"changed": True, "paused": False}

    monkeypatch.setattr(operator_control, "resume_chain", fake_resume_chain)
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 1 if argv[1] == "has-session" else 0)

    monkeypatch.setattr(operator_control.subprocess, "run", fake_run)

    result = operator_control.resume_session(
        spec=tmp_path / "chain.yaml",
        workspace=workspace,
        session="demo",
        marker_path=marker_path,
        actor="test",
        no_push=True,
    )

    launch = calls[1]
    assert result["runner_started"] is True
    assert result["no_push"] is True
    assert "MEGAPLAN_CHAIN_NO_PUSH=1" in launch
    assert launch[-1] == "python -m demo"


def test_resume_authority_only_does_not_start_runner(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    marker_path = tmp_path / ".megaplan" / "cloud-sessions" / "demo.json"
    marker_path.parent.mkdir(parents=True)
    marker_path.write_text(
        json.dumps(
            {
                "session": "demo",
                "operator_pause": {"active": True},
                "should_run": False,
            }
        ),
        encoding="utf-8",
    )
    resume_calls: list[dict[str, object]] = []

    def fake_resume_chain(*args, **kwargs):
        resume_calls.append(dict(kwargs))
        return {"changed": True, "paused": False}

    monkeypatch.setattr(operator_control, "resume_chain", fake_resume_chain)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        operator_control.subprocess,
        "run",
        lambda argv, **kwargs: calls.append(list(argv)),
    )

    result = operator_control.resume_session(
        spec=tmp_path / "chain.yaml",
        workspace=workspace,
        session="demo",
        marker_path=marker_path,
        actor="test",
        start_runner=False,
    )

    assert calls == []
    assert resume_calls == [
        {"actor": "test", "verify_execution_binding": False}
    ]
    assert result["runner_started"] is False
    assert result["authority_only"] is True
    updated = json.loads(marker_path.read_text(encoding="utf-8"))
    assert "operator_pause" not in updated
    assert updated["should_run"] is False


def test_resume_fails_closed_when_marker_changes_concurrently(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    marker_path = tmp_path / ".megaplan" / "cloud-sessions" / "demo.json"
    marker_path.parent.mkdir(parents=True)
    marker_path.write_text(
        json.dumps(
            {
                "session": "demo",
                "run_kind": "chain",
                "relaunch_command": "python -m demo",
                "operator_pause": {"active": True},
                "should_run": False,
            }
        ),
        encoding="utf-8",
    )

    def fake_resume_chain(*args, **kwargs):
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["runtime_binding"] = {
            "current_identity": {"source_revision": "c" * 40}
        }
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
        return {"changed": True, "paused": False}

    monkeypatch.setattr(operator_control, "resume_chain", fake_resume_chain)
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 1)

    monkeypatch.setattr(operator_control.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="session marker changed concurrently"):
        operator_control.resume_session(
            spec=tmp_path / "chain.yaml",
            workspace=workspace,
            session="demo",
            marker_path=marker_path,
            actor="test",
        )

    assert calls == [["tmux", "has-session", "-t", "demo"]]
