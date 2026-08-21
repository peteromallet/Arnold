from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentbox.cli import build_parser, main
from agentbox.config import AgentBoxConfig
from agentbox.guardian.scheduler import ensure_guardian_tasks
from agentbox.guardian.state import GuardianStateStore


def test_cli_guardian_run_once_executes_one_tick_and_exits(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )

    ensure_guardian_tasks(config, datetime(2026, 1, 1, tzinfo=UTC))

    result = main(["guardian", "run-once", "--json"])

    assert result == 0


def test_cli_guardian_pause_and_resume_persist_across_invocations(
    tmp_path, monkeypatch
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )

    pause_result = main(["guardian", "pause", "--json"])
    assert pause_result == 0

    state = GuardianStateStore(config).read()
    assert state["global_pause"]["paused"] is True

    resume_result = main(["guardian", "resume", "--json"])
    assert resume_result == 0

    state = GuardianStateStore(config).read()
    assert state["global_pause"]["paused"] is False


def test_cli_guardian_status_outputs_valid_json(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )

    ensure_guardian_tasks(config, datetime(2026, 1, 1, tzinfo=UTC))

    result = main(["guardian", "status", "--json"])

    assert result == 0


def test_cli_guardian_parser_has_all_subcommands() -> None:
    parser = build_parser()
    args = parser.parse_args(["guardian", "run-once"])
    assert args.command == "guardian"
    assert args.guardian_command == "run-once"

    args = parser.parse_args(["guardian", "run", "--poll-interval", "30"])
    assert args.guardian_command == "run"
    assert args.poll_interval == 30.0

    args = parser.parse_args(["guardian", "pause"])
    assert args.guardian_command == "pause"

    args = parser.parse_args(["guardian", "resume"])
    assert args.guardian_command == "resume"

    args = parser.parse_args(["guardian", "status", "--json"])
    assert args.guardian_command == "status"
    assert args.json is True


def test_cli_install_omp_agent_installs_packaged_agent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"

    result = main(["install-omp-agent", "arnold", "--target", str(target), "--json"])

    assert result == 0
    installed = target / "arnold.md"
    source = Path(__file__).parents[2] / "agentbox" / "agents" / "arnold.md"
    assert installed.is_file()
    assert installed.read_bytes() == source.read_bytes()


def test_cli_install_omp_agent_name_override_changes_filename_and_frontmatter(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"
    source = (Path(__file__).parents[2] / "agentbox" / "agents" / "arnold.md").read_bytes()

    result = main(
        [
            "install-omp-agent",
            "arnold",
            "--name",
            "my-op",
            "--target",
            str(target),
        ]
    )

    assert result == 0
    installed = (target / "my-op.md").read_bytes()
    assert installed.split(b"---", 2)[2] == source.split(b"---", 2)[2]
    assert b"name: my-op\n" in installed
    assert b"name: arnold\n" not in installed


def test_cli_install_omp_agent_description_override_preserves_name_and_body(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"
    source = (Path(__file__).parents[2] / "agentbox" / "agents" / "arnold.md").read_bytes()

    result = main(
        [
            "install-omp-agent",
            "arnold",
            "--description",
            "Op for X",
            "--target",
            str(target),
        ]
    )

    assert result == 0
    installed = (target / "arnold.md").read_bytes()
    assert installed.split(b"---", 2)[2] == source.split(b"---", 2)[2]
    assert b"name: arnold\n" in installed
    assert b'description: "Op for X"\n' in installed
    assert b'Arnold resident operator' not in installed


@pytest.mark.parametrize(
    ("template_name", "output_name"),
    [
        ("..", None),
        (".", None),
        ("a/b", None),
        ("", None),
        ("arnold", ""),
        ("arnold", "unsafe name"),
    ],
)
def test_cli_install_omp_agent_rejects_unsafe_names(
    tmp_path, monkeypatch, template_name, output_name
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"
    argv = ["install-omp-agent", template_name, "--target", str(target)]
    if output_name is not None:
        argv[2:2] = ["--name", output_name]

    result = main(argv)

    assert result == 1
    assert not target.exists()


def test_cli_install_omp_agent_rejects_existing_target_without_clobbering(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"
    target.mkdir()
    installed = target / "arnold.md"
    original = b"existing content\n"
    installed.write_bytes(original)

    result = main(["install-omp-agent", "arnold", "--target", str(target)])

    assert result == 1
    assert installed.read_bytes() == original


def test_cli_install_omp_agent_rejects_unknown_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"

    result = main(["install-omp-agent", "does-not-exist", "--target", str(target), "--json"])

    assert result == 1
    assert not target.exists()
