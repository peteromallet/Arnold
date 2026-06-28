from __future__ import annotations

from arnold_pipelines.megaplan.cloud.cli import (
    _chain_start_command,
    _remote_chain_upload_path,
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
