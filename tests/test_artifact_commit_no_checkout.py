"""Regression test for bug 4: artifact commit must not ``git checkout <base>``.

Advancing a finalized plan-all-first milestone commits the immutable plan
artifacts onto ``base_branch``. The previous implementation did this with a
``git checkout <base_branch>``, which exits 128 when ``base_branch`` is already
checked out in a *different* git worktree (git forbids the same branch in two
worktrees) -> ``git_commit_artifacts_failed``.

The durable fix commits the artifacts onto ``base_branch`` purely via git
plumbing (``read-tree`` / ``write-tree`` / ``commit-tree`` / ``update-ref``)
without ever checking out the base branch, so it succeeds even when base is
checked out elsewhere, and still works when base IS the current branch.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from megaplan.chain.git_ops import commit_plan_artifacts_to_base
from megaplan.types import CliError


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )


def _init_repo(path: Path) -> None:
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    _git(path, "checkout", "-b", "main")
    (path / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (path / "README.md").write_text("root\n", encoding="utf-8")
    _git(path, "add", ".gitignore", "README.md")
    _git(path, "commit", "-m", "init")


def _write_artifacts(root: Path, plan_name: str) -> list[Path]:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    final_path = plan_dir / "final.md"
    contract_path = plan_dir / "contract.json"
    state_path.write_text('{"current_state":"finalized"}\n', encoding="utf-8")
    final_path.write_text("final review\n", encoding="utf-8")
    contract_path.write_text('{"provides":[],"assumes":[]}\n', encoding="utf-8")
    return [state_path, final_path, contract_path]


def _tracked_on(repo: Path, branch: str) -> list[str]:
    return _git(repo, "ls-tree", "-r", "--name-only", branch).stdout.splitlines()


def test_commit_succeeds_when_base_checked_out_in_other_worktree(tmp_path: Path) -> None:
    """The exact bug-4 condition: base ('main') is checked out in a *linked*
    worktree while the primary worktree (on 'feature') commits artifacts onto
    'main'. The old ``git checkout main`` path would exit 128 here."""
    primary = tmp_path / "primary"
    primary.mkdir()
    _init_repo(primary)

    # Move the primary worktree off 'main' first; git forbids the same branch
    # being checked out in two worktrees, so we cannot link a 'main' worktree
    # while the primary is still on 'main'.
    _git(primary, "checkout", "-b", "feature")

    # Link a second worktree that checks out 'main' — now 'main' is "checked
    # out elsewhere" and git forbids checking it out in the primary worktree.
    linked = tmp_path / "linked-main"
    _git(primary, "worktree", "add", str(linked), "main")

    # Sanity: prove a plain checkout of base from the primary worktree fails 128.
    blocked = subprocess.run(
        ["git", "checkout", "main"], cwd=str(primary), capture_output=True, text=True
    )
    assert blocked.returncode == 128, "test premise: base must be un-checkout-able here"
    assert _git(primary, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "feature"

    artifacts = _write_artifacts(primary, "plan-m1")

    result = commit_plan_artifacts_to_base(
        primary, "main", "plan-m1", artifacts, push_enabled=False
    )

    assert result.committed is True
    assert result.commit_sha
    # Artifacts landed on 'main' via plumbing...
    tracked = _tracked_on(primary, "main")
    assert ".megaplan/plans/plan-m1/state.json" in tracked
    assert ".megaplan/plans/plan-m1/final.md" in tracked
    assert ".megaplan/plans/plan-m1/contract.json" in tracked
    # ...and HEAD of the primary worktree never moved off 'feature'.
    assert _git(primary, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "feature"


def test_commit_works_when_base_is_current_branch_and_leaves_clean_worktree(
    tmp_path: Path,
) -> None:
    """The common case: base IS the currently checked-out branch. Artifacts
    must commit onto it and the worktree must read clean afterward (no spurious
    staged-deletion from advancing the ref under the live index)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)  # HEAD is on 'main'
    artifacts = _write_artifacts(repo, "plan-m1")

    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    result = commit_plan_artifacts_to_base(
        repo, "main", "plan-m1", artifacts, push_enabled=False
    )

    assert result.committed is True
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_after == result.commit_sha
    assert head_after != head_before, "base branch (== HEAD) advanced"
    tracked = _tracked_on(repo, "main")
    assert ".megaplan/plans/plan-m1/state.json" in tracked
    # Worktree must read clean — no spurious 'D' staged deletions.
    status = _git(repo, "status", "--porcelain", "-uall").stdout.strip()
    assert status == "", f"expected clean worktree, got: {status!r}"


def test_commit_no_changes_is_idempotent(tmp_path: Path) -> None:
    """Re-committing identical artifacts is a no-op (write-tree matches base)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    artifacts = _write_artifacts(repo, "plan-m1")

    first = commit_plan_artifacts_to_base(repo, "main", "plan-m1", artifacts, push_enabled=False)
    assert first.committed is True

    second = commit_plan_artifacts_to_base(repo, "main", "plan-m1", artifacts, push_enabled=False)
    assert second.committed is False
    assert "no staged artifact changes" in second.audit_notes
    status = _git(repo, "status", "--porcelain", "-uall").stdout.strip()
    assert status == ""


def test_commit_does_not_invoke_git_checkout_of_base(tmp_path: Path, monkeypatch) -> None:
    """Belt-and-suspenders: assert the implementation never shells out to
    ``git checkout <base>`` (the operation that triggered bug 4)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _git(repo, "checkout", "-b", "feature")
    artifacts = _write_artifacts(repo, "plan-m1")

    import megaplan.chain as chain_module

    real_run = chain_module.subprocess.run
    checkout_base_calls: list[list[str]] = []

    def _spy_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and list(cmd[:2]) == ["git", "checkout"]:
            if "main" in cmd:
                checkout_base_calls.append(list(cmd))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(chain_module.subprocess, "run", _spy_run)

    result = commit_plan_artifacts_to_base(repo, "main", "plan-m1", artifacts, push_enabled=False)
    assert result.committed is True
    assert checkout_base_calls == [], f"unexpected git checkout of base: {checkout_base_calls}"
