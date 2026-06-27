from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.auto import DriverOutcome
from arnold_pipelines.megaplan.chain import _drive_plan
from arnold_pipelines.megaplan.chain.git_ops import (
    _clean_worktree_for_chain,
    _commit_and_push_phase,
    _commit_phase,
    _checkout_milestone_branch,
    _ensure_milestone_pr,
    _require_git_worktree_root,
)
from arnold_pipelines.megaplan.chain.spec import MilestoneSpec
from arnold_pipelines.megaplan.cli import _reset_chain_worktree_target
from arnold_pipelines.megaplan.types import CliError


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if check:
        assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")


def _worktree_registered(repo: Path, target: Path) -> bool:
    proc = _git(repo, "worktree", "list", "--porcelain")
    return any(
        line.removeprefix("worktree ").strip() == str(target)
        for line in proc.stdout.splitlines()
        if line.startswith("worktree ")
    )


def test_chain_fresh_refuses_to_delete_unregistered_spec_directory(tmp_path: Path) -> None:
    invoking_repo = tmp_path / "app"
    _init_repo(invoking_repo)
    spec_dir = tmp_path / "spec-worktree"
    (spec_dir / ".megaplan" / "briefs").mkdir(parents=True)
    spec_file = spec_dir / ".megaplan" / "briefs" / "chain.yaml"
    spec_file.write_text("milestones: []\n", encoding="utf-8")

    with pytest.raises(CliError) as exc_info:
        _reset_chain_worktree_target(
            invoking_repo,
            spec_dir,
            "spec-worktree",
            worktree_registered=_worktree_registered,
        )

    assert exc_info.value.code == "worktree_reset_refused"
    assert spec_file.read_text(encoding="utf-8") == "milestones: []\n"


def test_chain_fresh_refuses_to_delete_explicitly_protected_spec_directory(
    tmp_path: Path,
) -> None:
    invoking_repo = tmp_path / "app"
    _init_repo(invoking_repo)
    spec_dir = tmp_path / "registered-spec"
    _git(invoking_repo, "worktree", "add", "-b", "registered-spec", str(spec_dir), "HEAD")
    spec_file = spec_dir / ".megaplan" / "briefs" / "chain.yaml"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text("milestones: []\n", encoding="utf-8")

    with pytest.raises(CliError) as exc_info:
        _reset_chain_worktree_target(
            invoking_repo,
            spec_dir,
            "registered-spec",
            worktree_registered=_worktree_registered,
            protected_paths=[spec_dir],
        )

    assert exc_info.value.code == "worktree_reset_refused"
    assert _worktree_registered(invoking_repo, spec_dir)
    assert spec_file.exists()


def test_chain_git_guards_accept_linked_worktree_and_clean_preserves_repo(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    target = tmp_path / "linked"
    _git(repo, "worktree", "add", "-b", "chain-test", str(target), "HEAD")
    (target / "scratch.txt").write_text("remove me\n", encoding="utf-8")

    _require_git_worktree_root(target, operation="test")
    _clean_worktree_for_chain(target, writer=lambda _message: None)

    assert _git(target, "rev-parse", "--show-toplevel").stdout.strip() == str(target)
    assert (target / "README.md").read_text(encoding="utf-8") == "base\n"
    assert not (target / "scratch.txt").exists()


def test_chain_commit_refuses_non_git_directory_without_deleting_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "not-a-repo"
    (root / ".megaplan").mkdir(parents=True)
    keep = root / "source.py"
    keep.write_text("print('keep')\n", encoding="utf-8")

    with pytest.raises(CliError) as exc_info:
        _commit_phase(root, "plan-x", "execute", writer=lambda _message: None)

    assert exc_info.value.code == "chain_git_worktree_required"
    assert keep.read_text(encoding="utf-8") == "print('keep')\n"


def test_ensure_milestone_pr_skips_when_gh_missing(monkeypatch) -> None:
    messages: list[str] = []
    milestone = MilestoneSpec(
        label="m1",
        idea=Path("m1.md"),
        branch="test/m1",
    )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops.shutil.which",
        lambda name: None if name == "gh" else "/bin/other",
    )

    assert (
        _ensure_milestone_pr(
            Path.cwd(),
            milestone,
            base_branch="main",
            writer=messages.append,
        )
        is None
    )
    assert any("gh executable not found" in message for message in messages)


def test_checkout_existing_milestone_reconciles_with_refreshed_base(
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin.git"
    source = tmp_path / "source"
    runner = tmp_path / "runner"
    messages: list[str] = []

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(source))
    _git(source, "config", "user.email", "test@example.com")
    _git(source, "config", "user.name", "Test User")
    (source / "chain.yaml").write_text("profile: partnered-5\n", encoding="utf-8")
    _git(source, "add", "chain.yaml")
    _git(source, "commit", "-m", "base")
    _git(source, "branch", "-M", "native-python-working-tree")
    _git(source, "push", "-u", "origin", "native-python-working-tree")

    _git(source, "checkout", "-b", "epic-m1")
    (source / "milestone.txt").write_text("m1\n", encoding="utf-8")
    _git(source, "add", "milestone.txt")
    _git(source, "commit", "-m", "milestone")
    _git(source, "push", "-u", "origin", "epic-m1")

    _git(source, "checkout", "native-python-working-tree")
    (source / "chain.yaml").write_text(
        "profile: hermes:kimi:kimi-k2.7-code\n",
        encoding="utf-8",
    )
    _git(source, "add", "chain.yaml")
    _git(source, "commit", "-m", "route through kimi")
    _git(source, "push", "origin", "native-python-working-tree")

    _git(
        tmp_path,
        "clone",
        "--branch",
        "native-python-working-tree",
        str(origin),
        str(runner),
    )
    _git(runner, "config", "user.email", "test@example.com")
    _git(runner, "config", "user.name", "Test User")

    _checkout_milestone_branch(
        runner,
        "epic-m1",
        base_branch="native-python-working-tree",
        writer=messages.append,
        from_origin=True,
    )

    assert _git(runner, "branch", "--show-current").stdout.strip() == "epic-m1"
    assert "hermes:kimi:kimi-k2.7-code" in (runner / "chain.yaml").read_text(
        encoding="utf-8"
    )
    assert (runner / "milestone.txt").read_text(encoding="utf-8") == "m1\n"
    remote_branch = _git(
        runner,
        "rev-parse",
        "origin/epic-m1",
    ).stdout.strip()
    local_branch = _git(runner, "rev-parse", "HEAD").stdout.strip()
    assert remote_branch == local_branch
    assert any("git rebase origin/native-python-working-tree -> rc=0" in m for m in messages)


def test_commit_and_push_phase_continues_when_rebase_abort_has_no_rebase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    messages: list[str] = []
    subprocess_calls: list[list[str]] = []
    run_command_calls: list[list[str]] = []

    def fake_commit_phase(*_args, **_kwargs) -> str:
        return "abc123"

    def fake_run(cmd, **_kwargs):
        subprocess_calls.append(list(cmd))
        if cmd[:3] == ["git", "fetch", "origin"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:2] == ["git", "rebase"] and cmd[2] != "--abort":
            return subprocess.CompletedProcess(cmd, 1, "", "conflict")
        if cmd == ["git", "rebase", "--abort"]:
            return subprocess.CompletedProcess(cmd, 128, "", "No rebase in progress?")
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    def fake_run_command(_root, cmd, **_kwargs):
        run_command_calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._commit_phase",
        fake_commit_phase,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            subprocess=SimpleNamespace(
                run=fake_run,
                TimeoutExpired=subprocess.TimeoutExpired,
            ),
            _run_command=fake_run_command,
        ),
    )

    _commit_and_push_phase(root, "branch-x", "plan-x", "finalize", writer=messages.append)

    assert ["git", "rebase", "--abort"] in subprocess_calls
    assert ["git", "push", "--no-verify", "--force-with-lease", "origin", "branch-x"] in run_command_calls
    assert any("warning: git rebase --abort failed" in message for message in messages)


def test_drive_plan_restores_process_cwd_after_auto_driver(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    other = tmp_path / "other"
    _init_repo(root)
    other.mkdir()
    monkeypatch.chdir(root)

    def fake_auto_drive(*_args, **_kwargs):
        os.chdir(other)
        return DriverOutcome(
            status="done",
            plan="plan-x",
            final_state="done",
            iterations=1,
        )

    monkeypatch.setattr("arnold_pipelines.megaplan.chain.auto_drive", fake_auto_drive)

    outcome = _drive_plan(
        root,
        "plan-x",
        SimpleNamespace(
            stall_threshold=1,
            max_iterations=1,
            escalate_action="force-proceed",
            poll_sleep=0,
            phase_timeout=1,
            status_timeout=1,
        ),
        writer=lambda _message: None,
    )

    assert outcome.status == "done"
    assert Path.cwd() == root
