from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

from arnold.runtime.durable_ops import OperationRun, OperationState, ResourceType, TypedResource

from agentbox.cli import main
from agentbox.config import AGENTBOX_CONFIG_ENV, AgentBoxConfig
from agentbox.operations import create_agentbox_operation, open_operation_store, update_agentbox_operation
from agentbox.run_dirs import append_stderr, append_stdout, ensure_run_dir, record_log_resources, run_dir_paths
from agentbox.tmux import SessionStatus, session_name


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_dispatches_registered_handler_and_returns_stable_json(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    handler = _FakeRunHandler()
    _install_fake_run_adapter(monkeypatch, handler)

    assert (
        main(
            [
                "run",
                "--repo",
                "app",
                "--kind",
                "fake_chain",
                "--spec",
                "chain.yaml",
                "--operation-id",
                "chain-1",
                "--json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert handler.launch_calls == [
        {
            "operation_id": "chain-1",
            "repo_name": "app",
            "spec_path": Path("chain.yaml"),
        }
    ]
    assert payload["operation_id"] == "chain-1"
    assert payload["kind"] == "fake_chain"
    assert payload["operation_type"] == "megaplan_chain"
    assert payload["operation_state"] == "running"
    assert payload["launch_state"] == "running"
    assert payload["run_dir"] == str(run_dir_paths(config, "chain-1").root)
    assert payload["resources"][0]["type"] == "log"
    assert payload["resolved_spec_path"] == str(config.workspace_root / "resolved-chain.yaml")
    assert payload["validation"] == {
        "status": "passed",
        "spec_path": str(config.workspace_root / "resolved-chain.yaml"),
    }
    assert payload["classification"] == {
        "effective_status": "running",
        "operation_state": "running",
        "reason": "fake",
    }
    assert payload["diagnostics"] is None


def test_run_returns_nonzero_json_for_handler_retry_errors(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    handler = _FakeRunHandler(error_kind="terminal_operation")
    _install_fake_run_adapter(monkeypatch, handler)

    assert (
        main(
            [
                "run",
                "--repo",
                "app",
                "--kind",
                "fake_chain",
                "--spec",
                "chain.yaml",
                "--operation-id",
                "chain-1",
                "--json",
            ]
        )
        == 1
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["operation_id"] == "chain-1"
    assert payload["operation_state"] == "failed"
    assert payload["launch_state"] == "failed_before_running"
    assert payload["run_dir"] == str(run_dir_paths(config, "chain-1").root)
    assert payload["validation"]["status"] == "failed"
    assert payload["diagnostics"]["kind"] == "terminal_operation"
    assert payload["error"] == "terminal retry refused"


def test_run_reports_duplicate_live_session_without_error(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, _config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    handler = _FakeRunHandler(diagnostics={"kind": "already_running", "session_name": "live"})
    _install_fake_run_adapter(monkeypatch, handler)

    assert (
        main(
            [
                "run",
                "--repo",
                "app",
                "--kind",
                "fake_chain",
                "--spec",
                "chain.yaml",
                "--operation-id",
                "chain-1",
                "--json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["operation_state"] == "running"
    assert payload["diagnostics"] == {"kind": "already_running", "session_name": "live"}


def test_run_missing_and_unknown_arguments_are_nonzero(
    monkeypatch,
) -> None:
    _install_fake_run_adapter(monkeypatch, _FakeRunHandler())

    assert main(["run", "--repo", "app", "--kind", "fake_chain"]) == 2
    assert (
        main(
            [
                "run",
                "--repo",
                "app",
                "--kind",
                "unknown",
                "--spec",
                "chain.yaml",
            ]
        )
        == 2
    )


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
        "agentbox.operation_views.inspect_session",
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
            "requested_lines": 2,
            "returned_lines": 2,
            "truncated": True,
            "source": "file",
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
        "agentbox.operation_views.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    monkeypatch.setattr(
        "agentbox.operation_views.capture_pane",
        lambda name, *, lines: f"captured {name} {lines}\n",
    )

    assert main(["logs", "op-1", "--lines", "5", "--stream", "stdout", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["logs"][0]["stream"] == "tmux"
    assert payload["logs"][0]["text"] == f"captured {session_name('op-1')} 5\n"
    assert payload["logs"][0]["requested_lines"] == 5
    assert payload["logs"][0]["returned_lines"] == 1


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


def test_status_and_logs_accept_registered_adapter_operation_type(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    run = open_operation_store(config).create_operation_run(
        OperationRun(
            id="chain-1",
            operation_type="megaplan_chain",
            operation_dir=str(config.runs_root / "chain-1"),
            metadata={
                "command": ["megaplan", "chain", "start", "spec.yaml"],
                "launch_state": "running",
                "repo_names": ["app"],
            },
        ).transition_to(OperationState.RUNNING)
    )
    paths = ensure_run_dir(config, run.id, metadata=dict(run.metadata))
    record_log_resources(config, run.id)
    append_stdout(paths, "chain output\n")

    assert main(["status", "chain-1", "--json"]) == 0
    status_payload = json.loads(capsys.readouterr().out)
    assert status_payload["operation_id"] == "chain-1"
    assert status_payload["operation_type"] == "megaplan_chain"
    assert status_payload["operation_state"] == "suspended"

    assert main(["logs", "chain-1", "--stream", "stdout", "--json"]) == 0
    logs_payload = json.loads(capsys.readouterr().out)
    assert logs_payload["logs"][0]["text"] == "chain output\n"


def test_status_ticks_registered_adapter_before_rendering(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path, config = _config_file(tmp_path)
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))
    handler = _FakeRunHandler()
    _install_fake_run_adapter(monkeypatch, handler)
    create_agentbox_operation(
        config,
        "op-1",
        command="echo host",
        repo_names=["app"],
        launch_state="running",
    )
    open_operation_store(config).create_operation_run(
        OperationRun(
            id="chain-1",
            operation_type="megaplan_chain",
            operation_dir=str(config.runs_root / "chain-1"),
            metadata={
                "command": ["fake", "run"],
                "launch_state": "running",
                "repo_names": ["app"],
            },
        ).transition_to(OperationState.RUNNING)
    )

    assert main(["status", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    by_id = {item["operation_id"]: item for item in payload}
    assert handler.tick_calls == ["chain-1"]
    assert by_id["chain-1"]["operation_state"] == "succeeded"
    assert by_id["chain-1"]["launch_state"] == "ticked"
    assert by_id["op-1"] == {
        "operation_id": "op-1",
        "operation_type": "agentbox_host",
        "operation_state": "pending",
        "launch_state": "running",
        "command": "echo host",
        "repo_names": ["app"],
        "run_dir": str(run_dir_paths(config, "op-1").root),
        "run_dir_exists": False,
        "resource_count": 0,
        "session": None,
    }


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
            "requested_lines": 7,
            "returned_lines": 1,
            "truncated": False,
            "source": "tmux",
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


class _FakeRunHandler:
    def __init__(
        self,
        *,
        diagnostics: dict[str, object] | None = None,
        error_kind: str | None = None,
    ) -> None:
        self.diagnostics = diagnostics
        self.error_kind = error_kind
        self.launch_calls: list[dict[str, object]] = []
        self.tick_calls: list[str] = []

    def launch(self, config, operation_id, *, repo_name, spec_path):
        self.launch_calls.append(
            {
                "operation_id": operation_id,
                "repo_name": repo_name,
                "spec_path": spec_path,
            }
        )
        paths = ensure_run_dir(config, operation_id)
        if self.error_kind:
            create_agentbox_operation(
                config,
                operation_id,
                operation_type="megaplan_chain",
                command=("fake", "run"),
                repo_names=[repo_name],
                metadata={
                    "validation": {"status": "failed"},
                    "launch_diagnostics": {
                        "kind": self.error_kind,
                        "message": "terminal retry refused",
                    },
                },
            )
            update_agentbox_operation(
                config,
                operation_id,
                launch_state="failed_before_running",
                state=OperationState.FAILED,
            )
            raise _FakeRunError(
                "terminal retry refused",
                diagnostics={"kind": self.error_kind, "message": "terminal retry refused"},
            )

        create_agentbox_operation(
            config,
            operation_id,
            operation_type="megaplan_chain",
            command=("fake", "run"),
            repo_names=[repo_name],
            metadata={
                "resolved_spec_path": str(config.workspace_root / "resolved-chain.yaml"),
                "validation": {
                    "status": "passed",
                    "spec_path": str(config.workspace_root / "resolved-chain.yaml"),
                },
            },
        )
        update_agentbox_operation(
            config,
            operation_id,
            launch_state="running",
            state=OperationState.RUNNING,
        )
        record_log_resources(config, operation_id)
        return SimpleNamespace(
            resolved_spec_path=config.workspace_root / "resolved-chain.yaml",
            host_result=SimpleNamespace(diagnostics=self.diagnostics),
        )

    def status(self, config, operation_id):
        return SimpleNamespace(
            classification=SimpleNamespace(
                to_dict=lambda: {
                    "effective_status": "running",
                    "operation_state": "running",
                    "reason": "fake",
                }
            )
        )

    def tick(self, config, operation_id):
        self.tick_calls.append(operation_id)
        return update_agentbox_operation(
            config,
            operation_id,
            launch_state="ticked",
            state=OperationState.SUCCEEDED,
        )


class _FakeRunError(RuntimeError):
    def __init__(self, message: str, *, diagnostics: dict[str, object]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


def _install_fake_run_adapter(monkeypatch, handler: _FakeRunHandler) -> None:
    adapter = SimpleNamespace(
        kind="fake_chain",
        operation_type="megaplan_chain",
        load=lambda: handler,
    )
    monkeypatch.setattr("agentbox.cli.list_operation_adapters", lambda: (adapter,))
    monkeypatch.setattr("agentbox.cli.get_operation_adapter", lambda kind: adapter)
    monkeypatch.setattr("agentbox.operation_views.list_operation_adapters", lambda: (adapter,))


def _config_file(tmp_path: Path) -> tuple[Path, AgentBoxConfig]:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    config_path = tmp_path / "agentbox.yaml"
    config_path.write_text(
        yaml.safe_dump({"workspace_root": str(config.workspace_root)}),
        encoding="utf-8",
    )
    return config_path, config
