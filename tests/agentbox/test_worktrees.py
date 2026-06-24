from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from arnold.runtime.durable_ops import ResourceType, TypedResource

from agentbox.config import AgentBoxConfig
from agentbox.git_worktree import has_local_branch, is_registered_worktree
from agentbox.operations import create_agentbox_operation, open_operation_store
from agentbox.repos import register_repo
from agentbox.worktrees import (
    WorktreeAllocationError,
    allocate_worktree,
    branch_name,
    worktree_path,
)


def test_allocate_worktree_creates_branch_path_and_one_git_resource(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])

    allocation = allocate_worktree(config, "op-1", "demo")
    retried = allocate_worktree(config, "op-1", "demo")
    resources = open_operation_store(config).list_typed_resources("op-1")

    assert allocation.worktree_path == config.runs_root / "op-1" / "worktrees" / "demo"
    assert allocation.branch == "agentbox/op-1/demo"
    assert allocation.status == "created"
    assert retried.status == "reused_registered_worktree"
    assert retried.resource == allocation.resource
    assert has_local_branch(repo, "agentbox/op-1/demo") is True
    assert is_registered_worktree(repo, allocation.worktree_path) is True
    assert len(resources) == 1
    assert resources[0].resource_type is ResourceType.GIT_WORKTREE
    assert resources[0].details["repo_name"] == "demo"
    assert resources[0].details["canonical_repo_path"] == str(repo)
    assert resources[0].details["worktree_path"] == str(allocation.worktree_path)
    assert resources[0].details["branch"] == "agentbox/op-1/demo"
    assert resources[0].details["base_ref"] == "HEAD"
    assert resources[0].details["base_sha"] == _git(repo, "rev-parse", "HEAD")


def test_allocate_worktree_reattaches_existing_local_branch_without_resource(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    branch = branch_name("op-1", "demo")
    target = worktree_path(config, "op-1", "demo")
    _git(repo, "branch", branch)

    allocation = allocate_worktree(config, "op-1", "demo")

    assert allocation.status == "reattached_local_branch"
    assert allocation.worktree_path == target
    assert is_registered_worktree(repo, target) is True
    assert len(open_operation_store(config).list_typed_resources("op-1")) == 1


def test_allocate_worktree_reattaches_existing_local_branch_and_reuses_resource(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    first = allocate_worktree(config, "op-1", "demo")
    _git(repo, "worktree", "remove", str(first.worktree_path))

    retried = allocate_worktree(config, "op-1", "demo")

    assert retried.status == "reattached_local_branch"
    assert retried.resource == first.resource
    assert is_registered_worktree(repo, first.worktree_path) is True
    assert len(open_operation_store(config).list_typed_resources("op-1")) == 1


def test_allocate_worktree_reuses_durable_resource_after_missing_worktree(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    first = allocate_worktree(config, "op-1", "demo")
    store = open_operation_store(config)
    before_resources = store.list_typed_resources("op-1")
    _git(repo, "worktree", "remove", str(first.worktree_path))

    retried = allocate_worktree(config, "op-1", "demo")
    after_resources = store.list_typed_resources("op-1")

    assert retried.status == "reattached_local_branch"
    assert retried.resource == first.resource
    assert after_resources == before_resources
    assert is_registered_worktree(repo, first.worktree_path) is True


def test_allocate_worktree_reports_branch_checked_out_elsewhere_without_cleanup(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    branch = branch_name("op-1", "demo")
    other_path = tmp_path / "other-worktree"
    _git(repo, "branch", branch)
    _git(repo, "worktree", "add", str(other_path), branch)
    (other_path / "artifact.txt").write_text("keep me\n", encoding="utf-8")

    with pytest.raises(WorktreeAllocationError) as exc_info:
        allocate_worktree(config, "op-1", "demo")

    assert exc_info.value.kind == "branch_checked_out_elsewhere"
    assert other_path.exists()
    assert (other_path / "artifact.txt").read_text(encoding="utf-8") == "keep me\n"
    assert is_registered_worktree(repo, other_path) is True
    assert worktree_path(config, "op-1", "demo").exists() is False
    assert open_operation_store(config).list_typed_resources("op-1") == ()


def test_allocate_worktree_reports_target_path_conflict_without_cleanup(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    target = worktree_path(config, "op-1", "demo")
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("do not delete\n", encoding="utf-8")

    with pytest.raises(WorktreeAllocationError) as exc_info:
        allocate_worktree(config, "op-1", "demo")

    assert exc_info.value.kind == "worktree_path_conflict"
    assert (target / "keep.txt").read_text(encoding="utf-8") == "do not delete\n"
    assert has_local_branch(repo, branch_name("op-1", "demo")) is False
    assert open_operation_store(config).list_typed_resources("op-1") == ()


def test_allocate_worktree_reports_registered_target_with_wrong_branch(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    target = worktree_path(config, "op-1", "demo")
    _git(repo, "branch", "other-branch")
    _git(repo, "worktree", "add", str(target), "other-branch")

    with pytest.raises(WorktreeAllocationError) as exc_info:
        allocate_worktree(config, "op-1", "demo")

    assert exc_info.value.kind == "worktree_path_conflict"
    assert exc_info.value.details["observed_branch"] == "other-branch"
    assert is_registered_worktree(repo, target) is True
    assert open_operation_store(config).list_typed_resources("op-1") == ()


def test_allocate_worktree_reports_mismatched_existing_resource(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    open_operation_store(config).create_typed_resource(
        TypedResource(
            id="op-1:demo:git-worktree",
            operation_id="op-1",
            resource_type=ResourceType.GIT_WORKTREE,
            name="demo worktree",
            details={
                "repo_name": "demo",
                "canonical_repo_path": str(repo),
                "worktree_path": str(tmp_path / "wrong-path"),
                "branch": branch_name("op-1", "demo"),
            },
        )
    )

    with pytest.raises(WorktreeAllocationError) as exc_info:
        allocate_worktree(config, "op-1", "demo")

    assert exc_info.value.kind == "git_worktree_resource_conflict"
    assert worktree_path(config, "op-1", "demo").exists() is False
    assert has_local_branch(repo, branch_name("op-1", "demo")) is False


def test_allocate_worktree_reports_remote_tracking_only_branch_without_local_attach(
    tmp_path: Path,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    branch = branch_name("op-1", "demo")
    _git(repo, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")

    with pytest.raises(WorktreeAllocationError) as exc_info:
        allocate_worktree(config, "op-1", "demo")

    assert exc_info.value.kind == "remote_tracking_branch_conflict"
    assert has_local_branch(repo, branch) is False
    assert worktree_path(config, "op-1", "demo").exists() is False
    assert open_operation_store(config).list_typed_resources("op-1") == ()


def test_allocate_worktree_maps_git_rejection_to_remote_tracking_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    branch = branch_name("op-1", "demo")

    from agentbox import git_worktree
    from agentbox import worktrees

    def reject_with_git_error(*args: object) -> object:
        _git(repo, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")
        raise git_worktree.GitWorktreeError("fatal: branch rejected")

    monkeypatch.setattr(worktrees, "create_branch_worktree", reject_with_git_error)

    with pytest.raises(WorktreeAllocationError) as exc_info:
        allocate_worktree(config, "op-1", "demo")

    assert exc_info.value.kind == "remote_tracking_branch_conflict"
    assert has_local_branch(repo, branch) is False
    assert worktree_path(config, "op-1", "demo").exists() is False
    assert open_operation_store(config).list_typed_resources("op-1") == ()


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
