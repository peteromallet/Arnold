from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from arnold.runtime.durable_ops import ResourceType

from agentbox.cli import main
from agentbox.config import AGENTBOX_CONFIG_ENV, AgentBoxConfig
from agentbox.git_worktree import has_local_branch, is_registered_worktree
from agentbox.host import launch_host
from agentbox.operations import create_agentbox_operation, open_operation_store
from agentbox.reconcile import reconcile
from agentbox.repos import register_repo
from agentbox.run_dirs import ensure_run_dir
from agentbox.tmux import SessionStatus, session_name
from agentbox.worktrees import (
    WorktreeAllocationError,
    allocate_worktree,
    branch_name,
    worktree_path,
)


def test_local_agentbox_smoke_launch_reattach_status_logs_and_reconcile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config, repo, config_path = _configured_registered_repo(tmp_path, "app")
    monkeypatch.setenv(AGENTBOX_CONFIG_ENV, str(config_path))

    monkeypatch.setattr(
        "agentbox.host.start_session",
        lambda operation_id, command, *, cwd=None, run_paths=None: session_name(operation_id),
    )
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = launch_host(config, "op-smoke", command=("printf", "hi"), repo_names=("app",))
    first_resource = _git_worktree_resource(config, "op-smoke", "app")

    assert result.launch_state == "running"
    assert first_resource.details["repo_name"] == "app"
    assert first_resource.details["worktree_path"] == str(worktree_path(config, "op-smoke", "app"))
    assert is_registered_worktree(repo, result.worktrees[0].worktree_path) is True

    _git(repo, "worktree", "remove", str(result.worktrees[0].worktree_path))
    retried = allocate_worktree(config, "op-smoke", "app")

    assert retried.status == "reattached_local_branch"
    assert retried.resource == first_resource
    assert _git_worktree_resource(config, "op-smoke", "app") == first_resource

    tmux_calls: list[list[str]] = []
    real_subprocess_run = subprocess.run

    def fake_tmux(argv, **kwargs):
        argv_list = list(argv)
        if argv_list[:1] != ["tmux"]:
            return real_subprocess_run(argv, **kwargs)
        tmux_calls.append(argv_list)
        if argv_list[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if argv_list[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(argv, 0, stdout="tmux smoke tail\n", stderr="")
        raise AssertionError(f"unexpected tmux argv: {argv}")

    monkeypatch.setattr(subprocess, "run", fake_tmux)

    assert main(["status", "op-smoke", "--json"]) == 0
    status_payload = json.loads(capsys.readouterr().out)
    assert status_payload["session"]["state"] == "running"

    assert main(["logs", "op-smoke", "--lines", "3", "--json"]) == 0
    logs_payload = json.loads(capsys.readouterr().out)
    assert logs_payload["logs"][0]["stream"] == "tmux"
    assert logs_payload["logs"][0]["text"] == "tmux smoke tail"
    assert tmux_calls == [
        ["tmux", "has-session", "-t", session_name("op-smoke")],
        ["tmux", "has-session", "-t", session_name("op-smoke")],
        ["tmux", "has-session", "-t", session_name("op-smoke")],
        ["tmux", "capture-pane", "-p", "-t", session_name("op-smoke"), "-S", "-3"],
    ]

    report = reconcile(config)
    operation = report.operations[0]
    assert operation.operation_id == "op-smoke"
    assert operation.worktrees[0].state == "ready"
    assert operation.sessions[0].state == "running"


def test_local_agentbox_smoke_remote_tracking_only_retry(tmp_path: Path) -> None:
    config, repo, _config_path = _configured_registered_repo(tmp_path, "app")
    create_agentbox_operation(config, "op-remote", command="echo hi", repo_names=["app"])
    branch = branch_name("op-remote", "app")
    _git(repo, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")

    with pytest.raises(WorktreeAllocationError) as exc_info:
        allocate_worktree(config, "op-remote", "app")

    assert exc_info.value.kind == "remote_tracking_branch_conflict"
    assert has_local_branch(repo, branch) is False
    assert worktree_path(config, "op-remote", "app").exists() is False
    assert open_operation_store(config).list_typed_resources("op-remote") == ()

    _git(repo, "update-ref", "-d", f"refs/remotes/origin/{branch}")
    allocation = allocate_worktree(config, "op-remote", "app")

    assert allocation.status == "created"
    assert has_local_branch(repo, branch) is True
    assert _git_worktree_resource(config, "op-remote", "app").details["branch"] == branch


def test_local_agentbox_smoke_reconcile_reports_partial_artifacts_without_deletion(
    tmp_path: Path,
) -> None:
    config, _repo, _config_path = _configured_registered_repo(tmp_path, "app")
    create_agentbox_operation(config, "op-partial", command="echo hi", repo_names=["app"])
    paths = ensure_run_dir(config, "op-partial")
    paths.stdout_path.unlink()
    target = worktree_path(config, "op-partial", "app")
    target.mkdir(parents=True)
    artifact = target / "keep.txt"
    artifact.write_text("preserve me\n", encoding="utf-8")

    report = reconcile(config)
    operation = report.operations[0]

    assert operation.run_dir.state == "partial"
    assert operation.run_dir.missing_files == ("stdout.log",)
    assert operation.worktrees[0].state == "worktree_path_conflict"
    assert operation.worktrees[0].recommended_action == "manual_inspection_required"
    assert artifact.read_text(encoding="utf-8") == "preserve me\n"


def _configured_registered_repo(
    tmp_path: Path,
    repo_name: str,
) -> tuple[AgentBoxConfig, Path, Path]:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    repo = _init_repo(config.repos_root / repo_name)
    register_repo(config, repo_name, path=repo)
    config_path = tmp_path / "agentbox.yaml"
    config_path.write_text(f"workspace_root: {config.workspace_root}\n", encoding="utf-8")
    return config, repo, config_path


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "agentbox@example.test")
    _git(path, "config", "user.name", "AgentBox Tests")
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "initial")
    return path


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _git_worktree_resource(config: AgentBoxConfig, operation_id: str, repo_name: str):
    resources = open_operation_store(config).list_typed_resources(operation_id)
    return [
        resource for resource in resources
        if resource.resource_type is ResourceType.GIT_WORKTREE
        and resource.details["repo_name"] == repo_name
    ][0]
