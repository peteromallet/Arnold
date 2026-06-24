from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agentbox.git_worktree import (
    GitWorktreeError,
    attach_existing_local_branch,
    checked_out_branch_worktree,
    create_branch_worktree,
    git_operation_status,
    has_local_branch,
    has_remote_tracking_ref,
    is_registered_worktree,
    parse_worktree_porcelain,
    resolve_ref,
)


def test_ref_detection_separates_local_and_remote_tracking_refs(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "update-ref", "refs/remotes/origin/feature", "HEAD")

    assert has_local_branch(repo, "feature") is False
    assert has_remote_tracking_ref(repo, "origin/feature") is True
    assert has_remote_tracking_ref(repo, "refs/remotes/origin/feature") is True
    assert resolve_ref(repo, "origin/feature") == _git(repo, "rev-parse", "HEAD")


def test_checked_out_branch_detection_uses_porcelain_worktree_entries(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "branch", "feature")
    linked = tmp_path / "linked"
    attached = attach_existing_local_branch(repo, linked, "feature")

    assert attached.branch_name == "feature"
    assert checked_out_branch_worktree(repo, "feature") is not None
    assert checked_out_branch_worktree(repo, "feature").path == linked
    assert is_registered_worktree(repo, linked) is True
    assert is_registered_worktree(repo, tmp_path / "missing") is False


def test_create_branch_worktree_registers_new_local_branch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    linked = tmp_path / "new-worktree"

    created = create_branch_worktree(repo, linked, "new-branch", "HEAD")

    assert created.path == linked
    assert created.branch_name == "new-branch"
    assert has_local_branch(repo, "new-branch") is True


def test_attach_existing_local_branch_rejects_remote_only_ref(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "update-ref", "refs/remotes/origin/remote-only", "HEAD")

    assert has_local_branch(repo, "remote-only") is False
    assert has_remote_tracking_ref(repo, "origin/remote-only") is True

    with pytest.raises(GitWorktreeError, match="local branch"):
        attach_existing_local_branch(repo, tmp_path / "linked", "remote-only")

    assert (tmp_path / "linked").exists() is False


def test_parse_worktree_porcelain_preserves_detached_and_prunable_status() -> None:
    parsed = parse_worktree_porcelain(
        """
worktree /tmp/main
HEAD abc123
branch refs/heads/main

worktree /tmp/detached
HEAD def456
detached
prunable gitdir file points to non-existent location
""".strip()
    )

    assert [entry.branch_name for entry in parsed] == ["main", None]
    assert parsed[1].detached is True
    assert parsed[1].prunable_reason == "gitdir file points to non-existent location"


def test_git_operation_status_reports_markers_without_cleanup(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".git" / "MERGE_HEAD").write_text("abc123\n", encoding="utf-8")

    status = git_operation_status(repo)

    assert status.in_progress is True
    assert status.markers == ("MERGE_HEAD",)
    assert (repo / ".git" / "MERGE_HEAD").exists()


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
