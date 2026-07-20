from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import arnold

from arnold_pipelines.megaplan.runtime.process import (
    megaplan_engine_env,
    megaplan_engine_root,
)
from arnold_pipelines.megaplan.control import _resume_runner


def test_engine_root_is_anchored_to_megaplan_not_target_arnold(
    monkeypatch,
    tmp_path: Path,
) -> None:
    target_root = tmp_path / "target-checkout"
    target_package = target_root / "arnold"
    target_package.mkdir(parents=True)
    monkeypatch.setattr(arnold, "__file__", str(target_package / "__init__.py"))

    expected_root = Path(__file__).resolve().parents[3]
    assert megaplan_engine_root() == expected_root

    env = megaplan_engine_env({"PYTHONPATH": os.pathsep.join([str(target_root), "/other"])})
    assert env["PYTHONPATH"].split(os.pathsep) == [
        str(expected_root),
        str(target_root),
        "/other",
    ]


def test_resume_child_keeps_parent_megaplan_ahead_of_target_checkout(
    monkeypatch,
    tmp_path: Path,
) -> None:
    target_root = tmp_path / "target-checkout"
    target_package = target_root / "arnold"
    target_package.mkdir(parents=True)
    monkeypatch.setattr(arnold, "__file__", str(target_package / "__init__.py"))

    captured: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["env"] = dict(kwargs["env"])
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = _resume_runner(None)
    assert runner(["execute", "--plan", "demo"], cwd=target_root) == (0, "ok", "")

    assert captured["argv"][:4] == [
        sys.executable,
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
    ]
    child_env = captured["env"]
    assert isinstance(child_env, dict)
    assert child_env["PYTHONPATH"].split(os.pathsep)[0] == str(
        Path(__file__).resolve().parents[3]
    )
