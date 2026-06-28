from __future__ import annotations

import argparse
from types import SimpleNamespace
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud.cli import (
    _bootstrap_launch_command,
    _derive_bootstrap_session_name,
    _run_bootstrap_wrapper,
    _chain_start_command,
    _remote_chain_upload_path,
    _remote_chain_workspace_path,
)


def test_chain_start_command_sources_cloud_hot_env_before_launch() -> None:
    command = _chain_start_command(
        "/workspace/project/.megaplan/briefs/demo/chain.yaml",
        project_dir="/workspace/project",
        engine_dir="/workspace/arnold",
    )

    assert "if [ -f /workspace/.cloud-hot-env ]; then set -a; . /workspace/.cloud-hot-env; set +a; fi;" in command
    assert "cd /workspace/arnold &&" in command
    assert "MEGAPLAN_TRUSTED_CONTAINER=1 python -P -m arnold_pipelines.megaplan chain start" in command


def test_remote_chain_upload_path_anchors_relative_briefs_to_workspace() -> None:
    path = _remote_chain_upload_path(
        ".megaplan/briefs/god-file-splits/m1.md",
        source_workspace="/workspace",
        target_workspace="/workspace/vibecomfy-god-file-splits",
    )

    assert path == "/workspace/vibecomfy-god-file-splits/.megaplan/briefs/god-file-splits/m1.md"


def test_remote_chain_workspace_path_preserves_spec_relative_path() -> None:
    path = _remote_chain_workspace_path(
        Path("/workspace/.megaplan/briefs/god-file-splits/chain.yaml"),
        local_root=Path("/workspace"),
        target_workspace="/workspace/vibecomfy-god-file-splits",
    )

    assert path == "/workspace/vibecomfy-god-file-splits/.megaplan/briefs/god-file-splits/chain.yaml"


def test_bootstrap_launch_command_writes_plan_marker_and_relaunch_command() -> None:
    command = _bootstrap_launch_command(
        workspace="/workspace/vibecomfy-per-workflow-window-chat-20260628",
        remote_idea_path="/workspace/vibecomfy-per-workflow-window-chat-20260628/idea.txt",
        plan_name="per-workflow-window-chat-cloud-20260628",
        robustness="full",
        session_name="vibecomfy-per-workflow-window-chat",
        engine_dir="/workspace/arnold",
    )

    assert "/workspace/.megaplan/cloud-sessions/vibecomfy-per-workflow-window-chat.json" in command
    assert '"run_kind": "plan"' in command
    assert '"plan_name": "per-workflow-window-chat-cloud-20260628"' in command
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan per-workflow-window-chat-cloud-20260628" in command
    assert "arnold init --project-dir /workspace/vibecomfy-per-workflow-window-chat-20260628" in command
    assert "--name per-workflow-window-chat-cloud-20260628" in command


def test_run_bootstrap_wrapper_writes_marker_using_repo_named_session(tmp_path: Path, monkeypatch) -> None:
    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("Per workflow window chat", encoding="utf-8")
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []

    class CaptureProvider:
        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    spec = SimpleNamespace(
        repo=SimpleNamespace(
            url="https://github.com/example/vibecomfy-per-workflow-window-chat.git",
            workspace="/workspace/vibecomfy-per-workflow-window-chat-20260628",
        ),
        megaplan=SimpleNamespace(src_path="/workspace/arnold"),
        secrets=[],
    )
    args = argparse.Namespace(
        idea_file=str(idea_file),
        plan_name="per-workflow-window-chat-cloud-20260628",
        robustness="full",
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._ensure_repo_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._relay_output", lambda *_args, **_kwargs: None)

    assert _derive_bootstrap_session_name(spec) == "vibecomfy-per-workflow-window-chat"
    assert _run_bootstrap_wrapper(args, spec, CaptureProvider()) == 0
    assert uploads == [(idea_file.resolve(), "/workspace/vibecomfy-per-workflow-window-chat-20260628/idea.txt")]
    assert len(commands) == 1
    assert "/workspace/.megaplan/cloud-sessions/vibecomfy-per-workflow-window-chat.json" in commands[0]
