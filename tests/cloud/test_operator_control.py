from __future__ import annotations

import json
import subprocess
from pathlib import Path

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
    monkeypatch.setattr(
        operator_control,
        "resume_chain",
        lambda *args, **kwargs: {"changed": True, "paused": False},
    )
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
    )

    launch = calls[1]
    assert result["runner_started"] is True
    assert f"ARNOLD_REPAIR_QUEUE_ROOT={tmp_path / '.megaplan' / 'repair-queue'}" in launch
    assert f"ARNOLD_REPAIR_MARKER_DIR={marker_dir}" in launch
    assert "ARNOLD_REPAIR_SESSION=demo" in launch
    assert "ARNOLD_REPAIR_RUN_KIND=chain" in launch
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
    monkeypatch.setattr(
        operator_control,
        "resume_chain",
        lambda *args, **kwargs: {"changed": True, "paused": False},
    )
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
