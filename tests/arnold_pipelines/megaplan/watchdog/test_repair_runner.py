from __future__ import annotations

import os
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud.repair_contract import read_jsonl_records
from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root
from arnold_pipelines.megaplan.watchdog.repair_runner import RepairRunner
from arnold_pipelines.megaplan.watchdog.retry import RetryLoop, RetryOutcome


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


def test_argv_for_megaplan_subcommand_ignores_console_script_on_path(monkeypatch) -> None:
    def fake_which(cmd: str, path=None) -> str | None:
        if cmd == "megaplan":
            return "/tmp/fake-megaplan"
        return None

    monkeypatch.setattr("shutil.which", fake_which)

    runner = RepairRunner(python_bin="python3")

    argv, cwd, is_megaplan_subcommand = runner._argv_for_command("chain start --spec demo")

    assert argv == [
        "python3",
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "chain",
        "start",
        "--spec",
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


def test_run_appends_attempt_evidence_when_sidecar_configured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd, path=None: None)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout="ok", stderr=""),
    )

    sidecar_dir = tmp_path / "repair-data.d"
    runner = RepairRunner(
        python_bin="python3",
        evidence_sidecar_dir=str(sidecar_dir),
        evidence_session="repair-session",
    )
    project_dir = tmp_path / "workflow"
    project_dir.mkdir()

    result = runner.run("doctor --plan demo", project_dir=str(project_dir))

    assert result.status == "success"
    rows = read_jsonl_records(sidecar_dir / "attempts" / "attempts.jsonl")
    assert rows[-1]["session_id"] == "repair-session"
    assert rows[-1]["actor"] == "watchdog.repair_runner"
    assert rows[-1]["outcome"] == "success"
    assert rows[-1]["state"] == "succeeded"
    assert rows[-1]["project_dir"] == str(project_dir)


def test_retry_loop_appends_event_evidence(tmp_path: Path) -> None:
    sidecar_dir = tmp_path / "repair-data.d"
    loop = RetryLoop(
        sidecar_dir=str(sidecar_dir),
        session_id="repair-session",
        loop_id="retry-loop-1",
    )

    outcome, done = loop.attempt(RetryOutcome.UNRESOLVED)

    assert outcome is RetryOutcome.UNRESOLVED
    assert done is False
    rows = read_jsonl_records(sidecar_dir / "events" / "events.jsonl")
    assert rows[-1]["session_id"] == "repair-session"
    assert rows[-1]["attempt_id"] == "retry-loop-1"
    assert rows[-1]["actor"] == "watchdog.retry"
    assert rows[-1]["outcome"] == "unresolved"
