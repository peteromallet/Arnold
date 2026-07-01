from __future__ import annotations

import asyncio
import subprocess as _subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident import subagent as subagent_module
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.subagent import launch_subagent_task


class _Completed:
    def __init__(self, *, stdout: str, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_builds_argv_and_reads_stdout(tmp_path, monkeypatch) -> None:
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["kwargs"] = kwargs
        qf = argv[argv.index("--query-file") + 1]
        captured["query"] = Path(qf).read_text()
        return _Completed(stdout="FINAL ANSWER\n", stderr="diag", returncode=0)

    monkeypatch.setattr(subagent_module.subprocess, "run", fake_run)

    config = ResidentConfig(
        subagent_model_name="deepseek:deepseek-v4-pro",
        special_requests_subagent_toolsets="file,web",
        special_requests_subagent_max_tokens=12345,
    )
    result = asyncio.run(
        launch_subagent_task(config, task="hello\nworld", project_dir=str(tmp_path))
    )

    assert result.ok is True
    assert result.final_text == "FINAL ANSWER"
    assert result.returncode == 0
    argv = captured["argv"]
    assert argv[1].endswith("launch_hermes_agent.py")
    assert "--model" in argv and "deepseek:deepseek-v4-pro" in argv
    assert "--toolsets" in argv and "file,web" in argv
    assert "--max-tokens" in argv and "12345" in argv
    assert "--project-dir" in argv and str(tmp_path) in argv
    assert "--query-file" in argv
    assert captured["query"] == "hello\nworld"
    # query file cleaned up after the run
    qf = argv[argv.index("--query-file") + 1]
    assert not Path(qf).exists()


def test_nonzero_exit_is_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        subagent_module.subprocess,
        "run",
        lambda argv, **kw: _Completed(stdout="", stderr="boom", returncode=6),
    )
    result = asyncio.run(launch_subagent_task(ResidentConfig(), task="x"))
    assert result.ok is False
    assert result.returncode == 6
    assert "exit 6" in (result.error or "")


def test_empty_stdout_is_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        subagent_module.subprocess,
        "run",
        lambda argv, **kw: _Completed(stdout="   \n", stderr="", returncode=0),
    )
    result = asyncio.run(launch_subagent_task(ResidentConfig(), task="x"))
    assert result.ok is False


def test_timeout_is_failure(monkeypatch) -> None:
    def raise_timeout(argv, **kw):
        raise _subprocess.TimeoutExpired(cmd=argv, timeout=0.01)

    monkeypatch.setattr(subagent_module.subprocess, "run", raise_timeout)
    result = asyncio.run(launch_subagent_task(ResidentConfig(), task="x"))
    assert result.ok is False
    assert "timed out" in (result.error or "")


def test_missing_launcher_raises(tmp_path) -> None:
    config = ResidentConfig()
    monkeypatch_path = tmp_path / "ghost.py"
    # Point the module's LAUNCHER_PATH at a non-existent file.
    original = subagent_module.LAUNCHER_PATH
    subagent_module.LAUNCHER_PATH = monkeypatch_path
    try:
        with pytest.raises(FileNotFoundError):
            asyncio.run(launch_subagent_task(config, task="x"))
    finally:
        subagent_module.LAUNCHER_PATH = original
