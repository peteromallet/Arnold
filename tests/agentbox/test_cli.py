from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from arnold.runtime.durable_ops import OperationState, ResourceType, TypedResource

from agentbox.cli import main
from agentbox.config import AGENTBOX_CONFIG_ENV, AgentBoxConfig
from agentbox.operations import create_agentbox_operation, open_operation_store, update_agentbox_operation
from agentbox.run_dirs import append_stderr, append_stdout, ensure_run_dir, record_log_resources
from agentbox.tmux import SessionStatus, session_name


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_status_json_reports_local_operation_and_session_state(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command=("sleep", "10"), repo_names=["app"])
    update_agentbox_operation(
        config,
        "op-1",
        metadata={"session_name": session_name("op-1")},
        launch_state="running",
        state=OperationState.RUNNING,
    )
    monkeypatch.setattr(
        "agentbox.cli.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    assert main(["status", "op-1", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["operation_id"] == "op-1"
    assert payload["operation_state"] == "running"
    assert payload["launch_state"] == "running"
    assert payload["repo_names"] == ["app"]
    assert payload["session"]["state"] == "running"


def test_logs_are_bounded_and_json_capable(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command="echo hi")
    paths = ensure_run_dir(config, "op-1")
    record_log_resources(config, "op-1")
    append_stdout(paths, "one\n")
    append_stdout(paths, "two\n")
    append_stdout(paths, "three\n")
    append_stderr(paths, "err-one\nerr-two\n")

    assert main(["logs", "op-1", "--lines", "2", "--stream", "stdout", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["operation_id"] == "op-1"
    assert payload["lines"] == 2
    assert payload["logs"] == [
        {
            "stream": "stdout",
            "path": str(paths.stdout_path),
            "exists": True,
            "text": "two\nthree\n",
        }
    ]


def test_logs_tmux_capture_fallback_requires_recorded_live_session(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command="echo hi")
    ensure_run_dir(config, "op-1")

    assert main(["logs", "op-1", "--stream", "stdout", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["logs"][0]["text"] == ""

    resource = TypedResource(
        id="op-1:process-session",
        operation_id="op-1",
        resource_type=ResourceType.PROCESS_SESSION,
        name=session_name("op-1"),
        details={"provider": "tmux", "session_name": session_name("op-1")},
    )
    open_operation_store(config).create_typed_resource(resource)
    monkeypatch.setattr(
        "agentbox.cli.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    monkeypatch.setattr(
        "agentbox.cli.capture_pane",
        lambda name, *, lines: f"captured {name} {lines}\n",
    )

    assert main(["logs", "op-1", "--lines", "5", "--stream", "stdout", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["logs"][0]["stream"] == "tmux"
    assert payload["logs"][0]["text"] == f"captured {session_name('op-1')} 5\n"


def test_attach_reports_missing_and_stale_process_session_resources(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command="sleep 10")

    assert main(["attach", "op-1"]) == 1
    missing_err = capsys.readouterr().err
    assert "no recorded process-session resource" in missing_err
    assert "agentbox reconcile" in missing_err

    open_operation_store(config).create_typed_resource(
        TypedResource(
            id="op-1:process-session",
            operation_id="op-1",
            resource_type=ResourceType.PROCESS_SESSION,
            name=session_name("op-1"),
            details={"provider": "tmux", "session_name": session_name("op-1")},
        )
    )
    monkeypatch.setattr(
        "agentbox.cli.inspect_session",
        lambda name: SessionStatus(name, "missing", False, "can't find session"),
    )

    assert main(["attach", "op-1"]) == 1
    stale_err = capsys.readouterr().err
    assert "is missing" in stale_err
    assert "agentbox reconcile" in stale_err


def test_attach_invokes_tmux_attach_for_live_recorded_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command="sleep 10")
    open_operation_store(config).create_typed_resource(
        TypedResource(
            id="op-1:process-session",
            operation_id="op-1",
            resource_type=ResourceType.PROCESS_SESSION,
            name=session_name("op-1"),
            details={"provider": "tmux", "session_name": session_name("op-1")},
        )
    )
    monkeypatch.setattr(
        "agentbox.cli.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    captured: dict[str, object] = {}

    def fake_run(argv, *, check):
        captured["argv"] = argv
        captured["check"] = check
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert main(["attach", "op-1"]) == 0
    assert captured == {
        "argv": ["tmux", "attach-session", "-t", session_name("op-1")],
        "check": False,
    }


def test_reconcile_json_exposes_report_only_snapshot(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command="echo hi")
    orphan = config.runs_root / "orphan"
    orphan.mkdir(parents=True)

    assert main(["reconcile", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["operations"][0]["operation_id"] == "op-1"
    assert payload["operations"][0]["run_dir"]["state"] == "missing"
    assert payload["orphan_run_dirs"][0]["operation_id"] == "orphan"


def test_status_json_lists_partial_launch_without_process_session_resource(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["app"])
    ensure_run_dir(config, "op-1")
    update_agentbox_operation(
        config,
        "op-1",
        launch_state="failed_before_running",
        metadata={"launch_diagnostics": {"phase": "worktrees", "kind": "repo_failed"}},
    )

    assert main(["status", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert [item["operation_id"] for item in payload] == ["op-1"]
    assert payload[0]["launch_state"] == "failed_before_running"
    assert payload[0]["session"] is None
    assert payload[0]["resource_count"] == 0


def test_reconcile_json_reports_partial_launch_without_process_session_resource(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command="echo hi")
    paths = ensure_run_dir(config, "op-1")
    paths.stdout_path.unlink()
    update_agentbox_operation(config, "op-1", launch_state="failed_before_running")

    assert main(["reconcile", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    operation = payload["operations"][0]
    assert operation["operation_id"] == "op-1"
    assert operation["launch_state"] == "failed_before_running"
    assert operation["run_dir"]["state"] == "partial"
    assert operation["run_dir"]["missing_files"] == ["stdout.log"]
    assert operation["sessions"] == []


def test_status_json_reports_stale_process_session_via_mocked_tmux_subprocess(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command="sleep 10")
    session = session_name("op-1")
    open_operation_store(config).create_typed_resource(
        TypedResource(
            id="op-1:process-session",
            operation_id="op-1",
            resource_type=ResourceType.PROCESS_SESSION,
            name=session,
            details={"provider": "tmux", "session_name": session},
        )
    )
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        assert kwargs["check"] is False
        assert kwargs["text"] is True
        return subprocess.CompletedProcess(
            argv,
            1,
            stdout="",
            stderr="can't find session: agentbox-op-1",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert main(["status", "op-1", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert calls == [["tmux", "has-session", "-t", session]]
    assert payload["session"]["state"] == "missing"
    assert payload["session"]["exists"] is False
    assert payload["session"]["detail"] == "can't find session: agentbox-op-1"


def test_logs_json_uses_mocked_tmux_capture_only_for_live_recorded_session(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    create_agentbox_operation(config, "op-1", command="echo hi")
    ensure_run_dir(config, "op-1")
    session = session_name("op-1")
    open_operation_store(config).create_typed_resource(
        TypedResource(
            id="op-1:process-session",
            operation_id="op-1",
            resource_type=ResourceType.PROCESS_SESSION,
            name=session,
            details={"provider": "tmux", "session_name": session},
        )
    )
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if argv[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if argv[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(argv, 0, stdout="live tail\n", stderr="")
        raise AssertionError(f"unexpected subprocess argv: {argv}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert main(["logs", "op-1", "--lines", "7", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert calls == [
        ["tmux", "has-session", "-t", session],
        ["tmux", "has-session", "-t", session],
        ["tmux", "capture-pane", "-p", "-t", session, "-S", "-7"],
    ]
    assert payload["logs"] == [
        {
            "stream": "tmux",
            "path": None,
            "exists": True,
            "text": "live tail",
            "session_name": session,
            "operation_id": "op-1",
        }
    ]


def test_cli_loads_config_from_environment_in_subprocess(tmp_path: Path) -> None:
    config_path, config = _config_file(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi")

    result = subprocess.run(
        [sys.executable, "-m", "agentbox", "status", "op-1", "--json"],
        cwd=REPO_ROOT,
        env={AGENTBOX_CONFIG_ENV: str(config_path)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["operation_id"] == "op-1"


def test_cli_source_has_no_forbidden_invocation_reference() -> None:
    source = Path("agentbox/cli.py").read_text(encoding="utf-8").lower()

    assert "megaplan" not in source


def _config_file(tmp_path: Path) -> tuple[Path, AgentBoxConfig]:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    config_path = tmp_path / "agentbox.yaml"
    config_path.write_text(
        yaml.safe_dump({"workspace_root": str(config.workspace_root)}),
        encoding="utf-8",
    )
    return config_path, config
