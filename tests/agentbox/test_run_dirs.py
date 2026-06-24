from __future__ import annotations

import json
from pathlib import Path

from arnold.runtime.durable_ops import ResourceType

from agentbox.config import AgentBoxConfig
from agentbox.operations import create_agentbox_operation, open_operation_store
from agentbox.run_dirs import (
    append_event,
    append_stderr,
    append_stdout,
    ensure_run_dir,
    read_metadata,
    record_log_resources,
    run_dir_paths,
    write_metadata,
)


def test_ensure_run_dir_creates_logs_events_and_metadata(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")

    paths = ensure_run_dir(config, "op-1", metadata={"command": "echo hi"})

    assert paths.root == config.runs_root / "op-1"
    assert paths.events_path.read_text(encoding="utf-8") == ""
    assert paths.stdout_path.read_text(encoding="utf-8") == ""
    assert paths.stderr_path.read_text(encoding="utf-8") == ""
    assert read_metadata(paths) == {"command": "echo hi"}


def test_append_event_appends_ndjson_without_replacing_existing_lines(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    paths = ensure_run_dir(config, "op-1")

    first = append_event(paths, "launch.started", payload={"attempt": 1}, event_id="first")
    second = append_event(paths, "launch.ready", payload={"attempt": 1}, event_id="second")
    lines = [
        json.loads(line)
        for line in paths.events_path.read_text(encoding="utf-8").splitlines()
    ]

    assert lines == [first, second]
    assert lines[0]["event_type"] == "launch.started"
    assert lines[1]["event_type"] == "launch.ready"


def test_stdout_and_stderr_helpers_append_logs(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    paths = ensure_run_dir(config, "op-1")

    append_stdout(paths, "one\n")
    append_stdout(paths, "two\n")
    append_stderr(paths, "err\n")

    assert paths.stdout_path.read_text(encoding="utf-8") == "one\ntwo\n"
    assert paths.stderr_path.read_text(encoding="utf-8") == "err\n"


def test_metadata_helpers_replace_with_json_object(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    paths = ensure_run_dir(config, "op-1", metadata={"first": True})

    write_metadata(paths, {"second": 2})

    assert read_metadata(paths) == {"second": 2}


def test_record_log_resources_is_idempotent_and_uses_log_resource_type(
    tmp_path: Path,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    create_agentbox_operation(config, "op-1", command="echo hi")

    first_stdout, first_stderr = record_log_resources(config, "op-1")
    second_stdout, second_stderr = record_log_resources(config, "op-1")
    resources = open_operation_store(config).list_typed_resources("op-1")
    paths = run_dir_paths(config, "op-1")

    assert (first_stdout, first_stderr) == (second_stdout, second_stderr)
    assert len(resources) == 2
    assert {resource.resource_type for resource in resources} == {ResourceType.LOG}
    assert {resource.name for resource in resources} == {"stdout.log", "stderr.log"}
    assert {resource.details["stream"] for resource in resources} == {"stdout", "stderr"}
    assert {resource.details["relative_path"] for resource in resources} == {
        "stdout.log",
        "stderr.log",
    }
    assert paths.stdout_path.exists()
    assert paths.stderr_path.exists()
