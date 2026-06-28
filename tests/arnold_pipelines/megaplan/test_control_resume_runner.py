from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from arnold_pipelines.megaplan.control import _resume_runner
from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root


def test_resume_runner_anchors_subprocess_to_editable_engine(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = dict(kwargs.get("env") or {})
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = _resume_runner({"MEGAPLAN_PROGRESS_TOKEN": "token-123"})
    project_dir = tmp_path / "workflow"
    project_dir.mkdir()

    rc, stdout, stderr = runner(["resume", "--plan", "demo"], cwd=project_dir)

    assert (rc, stdout, stderr) == (0, "ok", "")
    assert captured["argv"] == [
        sys.executable,
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "resume",
        "--plan",
        "demo",
    ]
    assert captured["cwd"] == str(project_dir)

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["MEGAPLAN_ENGINE_ROOT"] == str(megaplan_engine_root())
    assert env["PYTHONSAFEPATH"] == "1"
    assert env["MEGAPLAN_PROGRESS_TOKEN"] == "token-123"
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(megaplan_engine_root())
