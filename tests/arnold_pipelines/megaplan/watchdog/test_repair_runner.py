from __future__ import annotations

import os
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root
from arnold_pipelines.megaplan.watchdog.repair_runner import RepairRunner


def test_argv_for_megaplan_subcommand_uses_safe_module_invocation(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd, path=None: None)

    runner = RepairRunner(python_bin="python3")

    argv, cwd, is_megaplan_subcommand = runner._argv_for_command("auto --plan demo")

    assert argv == [
        "python3",
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "auto",
        "--plan",
        "demo",
    ]
    assert cwd is None
    assert is_megaplan_subcommand is True


def test_run_anchors_megaplan_subcommand_to_editable_engine(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = dict(kwargs.get("env") or {})
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr("shutil.which", lambda cmd, path=None: None)
    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = RepairRunner(python_bin="python3")
    project_dir = tmp_path / "workflow"
    project_dir.mkdir()

    result = runner.run("resume --plan demo", project_dir=str(project_dir))

    assert result.status == "success"
    assert captured["argv"] == [
        "python3",
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
    assert env["MEGAPLAN_PROJECT_DIR"] == str(project_dir)
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(megaplan_engine_root())
