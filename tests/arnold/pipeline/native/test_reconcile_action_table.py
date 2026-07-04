from __future__ import annotations

import subprocess
from pathlib import Path

from arnold.pipeline.native.reconcile import (
    ACTION_TABLE,
    ReconcileMetadata,
    reconcile_file_write,
    reconcile_git_branch_create,
    reconcile_git_commit,
    reconcile_git_worktree,
)


def test_action_table_covers_planned_states() -> None:
    states = {entry.state for entry in ACTION_TABLE}

    assert {
        "clean",
        "dirty_owned_changes",
        "dirty_unknown_changes",
        "in_progress_git_operation",
        "branch_already_exists",
        "commit_already_exists",
        "expected_file_write_already_applied",
        "unknown",
    }.issubset(states)


def test_file_write_reconcile_skips_when_expected_content_already_applied(
    tmp_path: Path,
) -> None:
    target = tmp_path / "out.txt"
    target.write_text("done\n", encoding="utf-8")

    decision = reconcile_file_write(
        target,
        ReconcileMetadata(
            operation="file_write",
            target="out.txt",
            expected_content="done\n",
        ),
    )

    assert decision.state == "expected_file_write_already_applied"
    assert decision.skip_execution is True
    assert decision.blocked is False


def test_file_write_reconcile_blocks_unowned_mismatch(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("unexpected\n", encoding="utf-8")

    decision = reconcile_file_write(
        target,
        ReconcileMetadata(
            operation="file_write",
            target="out.txt",
            expected_content="done\n",
        ),
    )

    assert decision.state == "dirty_unknown_changes"
    assert decision.blocked is True


def test_file_write_reconcile_allows_owned_mismatch_to_continue(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("partial\n", encoding="utf-8")

    decision = reconcile_file_write(
        target,
        ReconcileMetadata(
            operation="file_write",
            target="out.txt",
            expected_content="done\n",
            owned_paths=frozenset({"out.txt"}),
        ),
    )

    assert decision.state == "dirty_owned_changes"
    assert decision.continue_execution is True


def test_git_worktree_reconcile_distinguishes_clean_owned_and_unknown_dirty(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")

    clean = reconcile_git_worktree(repo, ReconcileMetadata(operation="git_worktree_op"))
    assert clean.state == "clean"
    assert clean.continue_execution is True

    tracked = repo / "README.md"
    tracked.write_text("# changed\n", encoding="utf-8")
    unknown = reconcile_git_worktree(repo, ReconcileMetadata(operation="git_worktree_op"))
    assert unknown.state == "dirty_unknown_changes"
    assert unknown.blocked is True

    owned = reconcile_git_worktree(
        repo,
        ReconcileMetadata(
            operation="git_worktree_op",
            owned_paths=frozenset({"README.md"}),
        ),
    )
    assert owned.state == "dirty_owned_changes"
    assert owned.continue_execution is True


def test_git_worktree_reconcile_blocks_in_progress_operations(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".git" / "MERGE_HEAD").write_text("abc123\n", encoding="utf-8")

    decision = reconcile_git_worktree(repo, ReconcileMetadata(operation="git_worktree_op"))

    assert decision.state == "in_progress_git_operation"
    assert decision.blocked is True


def test_git_branch_reconcile_skips_when_branch_already_exists_at_expected_ref(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "branch", "feature")
    head = _git(repo, "rev-parse", "HEAD")

    decision = reconcile_git_branch_create(
        repo,
        ReconcileMetadata(
            operation="git_branch_create",
            target="feature",
            expected_ref=head,
        ),
    )

    assert decision.state == "branch_already_exists"
    assert decision.skip_execution is True


def test_git_branch_reconcile_fails_closed_on_ref_mismatch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "branch", "feature")

    decision = reconcile_git_branch_create(
        repo,
        ReconcileMetadata(
            operation="git_branch_create",
            target="feature",
            expected_ref="deadbeef",
        ),
    )

    assert decision.state == "unknown"
    assert decision.blocked is True


def test_git_commit_reconcile_skips_when_expected_commit_exists(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    head = _git(repo, "rev-parse", "HEAD")

    decision = reconcile_git_commit(
        repo,
        ReconcileMetadata(
            operation="git_commit",
            expected_commit=head,
        ),
    )

    assert decision.state == "commit_already_exists"
    assert decision.skip_execution is True


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
