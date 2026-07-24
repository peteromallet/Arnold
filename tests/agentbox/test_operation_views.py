from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from arnold.runtime.durable_ops import OperationRun, OperationState, ResourceType, TypedResource

from agentbox.config import AgentBoxConfig
from agentbox.operation_views import logs_view, status_view
from agentbox.operations import create_agentbox_operation, open_operation_store, update_agentbox_operation
from agentbox.run_dirs import append_stdout, ensure_run_dir, record_log_resources, run_dir_paths
from agentbox.tmux import SessionStatus, session_name


def test_status_view_ticks_registered_adapters_before_rendering(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    handler = _TickHandler()
    adapter = SimpleNamespace(
        operation_type="megaplan_chain",
        load=lambda: handler,
    )
    monkeypatch.setattr("agentbox.operation_views.list_operation_adapters", lambda: (adapter,))
    open_operation_store(config).create_operation_run(
        OperationRun(
            id="chain-1",
            operation_type="megaplan_chain",
            operation_dir=str(config.runs_root / "chain-1"),
            metadata={"launch_state": "running", "repo_names": ["app"]},
        ).transition_to(OperationState.RUNNING)
    )

    payload = status_view(config, "chain-1")

    assert handler.tick_calls == ["chain-1"]
    assert payload["operation_id"] == "chain-1"
    assert payload["operation_state"] == "succeeded"
    assert payload["launch_state"] == "ticked"


def test_logs_view_returns_bounded_file_metadata_and_tmux_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    create_agentbox_operation(config, "op-1", command="echo hi")
    paths = ensure_run_dir(config, "op-1")
    record_log_resources(config, "op-1")
    append_stdout(paths, "one\n")
    append_stdout(paths, "two\n")
    append_stdout(paths, "three\n")

    file_payload = logs_view(config, "op-1", lines=2, stream="stdout")

    assert file_payload["logs"][0] == {
        "stream": "stdout",
        "path": str(paths.stdout_path),
        "exists": True,
        "text": "two\nthree\n",
        "requested_lines": 2,
        "returned_lines": 2,
        "truncated": True,
        "source": "file",
    }

    create_agentbox_operation(config, "op-2", command="sleep 10")
    ensure_run_dir(config, "op-2")
    session = session_name("op-2")
    open_operation_store(config).create_typed_resource(
        TypedResource(
            id="op-2:process-session",
            operation_id="op-2",
            resource_type=ResourceType.PROCESS_SESSION,
            name=session,
            details={"provider": "tmux", "session_name": session},
        )
    )
    monkeypatch.setattr(
        "agentbox.operation_views.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    monkeypatch.setattr(
        "agentbox.operation_views.capture_pane",
        lambda name, *, lines: f"pane {name} {lines}\n",
    )

    tmux_payload = logs_view(config, "op-2", lines=4, stream="stdout")

    assert tmux_payload["logs"] == [
        {
            "stream": "tmux",
            "path": None,
            "exists": True,
            "text": f"pane {session} 4\n",
            "session_name": session,
            "operation_id": "op-2",
            "requested_lines": 4,
            "returned_lines": 1,
            "truncated": False,
            "source": "tmux",
        }
    ]


def test_status_view_uses_conventional_run_dir_fields_for_discord_ready_callers(
    tmp_path: Path,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["app"])

    payload = status_view(config, "op-1")

    assert payload["operation_id"] == "op-1"
    assert payload["command"] == "echo hi"
    assert payload["repo_names"] == ["app"]
    assert payload["run_dir"] == str(run_dir_paths(config, "op-1").root)
    assert payload["session"] is None


class _TickHandler:
    def __init__(self) -> None:
        self.tick_calls: list[str] = []

    def tick(self, config, operation_id):
        self.tick_calls.append(operation_id)
        return update_agentbox_operation(
            config,
            operation_id,
            launch_state="ticked",
            state=OperationState.SUCCEEDED,
        )
