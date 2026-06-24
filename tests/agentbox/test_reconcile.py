from __future__ import annotations

import subprocess
from pathlib import Path

from arnold.runtime.durable_ops import OperationState, ResourceType, TypedResource

from agentbox.config import AgentBoxConfig
from agentbox.operations import (
    create_agentbox_operation,
    open_operation_store,
    update_agentbox_operation,
)
from agentbox.reconcile import reconcile
from agentbox.repos import register_repo
from agentbox.run_dirs import ensure_run_dir
from agentbox.tmux import SessionStatus, session_name
from agentbox.worktrees import allocate_worktree, branch_name, worktree_path


def test_reconcile_reports_ready_operation_resources_run_dir_and_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="sleep 10", repo_names=["demo"])
    ensure_run_dir(config, "op-1")
    allocation = allocate_worktree(config, "op-1", "demo")
    process_resource = TypedResource(
        id="op-1:process-session",
        operation_id="op-1",
        resource_type=ResourceType.PROCESS_SESSION,
        name=session_name("op-1"),
        details={"provider": "tmux", "session_name": session_name("op-1")},
    )
    open_operation_store(config).create_typed_resource(process_resource)
    update_agentbox_operation(
        config,
        "op-1",
        metadata={"session_name": session_name("op-1")},
        launch_state="running",
        state=OperationState.RUNNING,
    )
    monkeypatch.setattr(
        "agentbox.reconcile.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    report = reconcile(config)
    op = report.operations[0]

    assert op.operation_id == "op-1"
    assert op.operation_state == "running"
    assert op.run_dir.state == "ready"
    assert op.resource_count == 2
    assert op.worktrees[0].state == "ready"
    assert op.worktrees[0].recommended_action == "none"
    assert op.worktrees[0].canonical_repo_path == str(repo)
    assert op.worktrees[0].worktree_path == str(allocation.worktree_path)
    assert op.sessions[0].state == "running"
    assert op.sessions[0].durable_resource_id == process_resource.id
    assert report.orphan_run_dirs == ()


def test_reconcile_distinguishes_local_branch_missing_worktree_from_remote_only(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(
        config,
        "op-1",
        command="echo hi",
        repo_names=["local", "remote"],
    )
    register_repo(config, "local", path=repo)
    register_repo(config, "remote", path=repo)
    _git(repo, "branch", branch_name("op-1", "local"))
    _git(repo, "update-ref", f"refs/remotes/origin/{branch_name('op-1', 'remote')}", "HEAD")

    report = reconcile(config)
    by_repo = {item.repo_name: item for item in report.operations[0].worktrees}

    assert by_repo["local"].state == "local_branch_missing_worktree"
    assert by_repo["local"].local_branch_exists is True
    assert by_repo["local"].remote_tracking_only is False
    assert by_repo["local"].recommended_action == "attach_existing_local_branch"
    assert by_repo["remote"].state == "remote_tracking_only_ref"
    assert by_repo["remote"].local_branch_exists is False
    assert by_repo["remote"].remote_tracking_ref_exists is True
    assert by_repo["remote"].remote_tracking_only is True
    assert by_repo["remote"].recommended_action == "inspect_remote_tracking_ref"
    assert not worktree_path(config, "op-1", "remote").exists()


def test_reconcile_classifies_partial_worktree_states_without_cleanup(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(
        config,
        "op-1",
        command="echo hi",
        repo_names=["elsewhere", "path-conflict"],
    )
    register_repo(config, "elsewhere", path=repo)
    register_repo(config, "path-conflict", path=repo)
    elsewhere_branch = branch_name("op-1", "elsewhere")
    elsewhere_path = tmp_path / "elsewhere-worktree"
    _git(repo, "branch", elsewhere_branch)
    _git(repo, "worktree", "add", str(elsewhere_path), elsewhere_branch)
    target = worktree_path(config, "op-1", "path-conflict")
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("do not delete\n", encoding="utf-8")

    report = reconcile(config)
    by_repo = {item.repo_name: item for item in report.operations[0].worktrees}

    assert by_repo["elsewhere"].state == "branch_checked_out_elsewhere"
    assert by_repo["elsewhere"].checked_out_path == str(elsewhere_path)
    assert by_repo["elsewhere"].recommended_action == "manual_inspection_required"
    assert by_repo["path-conflict"].state == "worktree_path_conflict"
    assert (target / "keep.txt").read_text(encoding="utf-8") == "do not delete\n"


def test_reconcile_reports_missing_and_orphan_run_dirs(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    create_agentbox_operation(config, "op-1", command="echo hi")
    orphan = config.runs_root / "orphan"
    orphan.mkdir(parents=True)

    report = reconcile(config)

    assert report.operations[0].run_dir.state == "missing"
    assert report.operations[0].run_dir.exists is False
    assert report.orphan_run_dirs[0].operation_id == "orphan"
    assert report.orphan_run_dirs[0].state == "orphan_run_dir"


def _registered_repo(tmp_path: Path) -> tuple[AgentBoxConfig, Path]:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    repo = _init_repo(config.repos_root / "demo")
    register_repo(config, "demo", path=repo)
    return config, repo


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
