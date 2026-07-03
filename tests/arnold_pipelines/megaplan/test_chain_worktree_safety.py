from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import arnold_pipelines.megaplan.chain as chain_module
from arnold_pipelines.megaplan.auto import DriverOutcome
from arnold_pipelines.megaplan.chain import (
    _drive_plan,
    _init_plan,
    _plan_state,
    load_chain_state,
    run_chain,
    save_chain_state,
)
from arnold_pipelines.megaplan.chain.git_ops import (
    _clean_worktree_for_chain,
    _commit_and_push_phase,
    _commit_phase,
    _checkout_milestone_branch,
    _enable_auto_merge,
    _ensure_milestone_pr,
    _require_git_worktree_root,
)
from arnold_pipelines.megaplan.chain.spec import MilestoneSpec
from arnold_pipelines.megaplan.chain.spec import load_spec
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
    _git(repo, "branch", "-M", "main")


def _write_chain_spec(
    root: Path,
    *,
    base_branch: str = "main",
    branch: str | None = "test/m1",
) -> Path:
    idea = root / "idea.md"
    idea.write_text("ship milestone\n", encoding="utf-8")
    north_star = root / "NORTHSTAR.md"
    north_star.write_text("north star\n", encoding="utf-8")
    spec_path = root / "chain.yaml"
    contents = (
        f"base_branch: {base_branch}\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        f"    idea: {idea}\n"
    )
    if branch:
        contents += f"    branch: {branch}\n"
    spec_path.write_text(contents, encoding="utf-8")
    return spec_path


def _worktree_registered(repo: Path, target: Path) -> bool:
    proc = _git(repo, "worktree", "list", "--porcelain")
    return any(
        line.removeprefix("worktree ").strip() == str(target)
        for line in proc.stdout.splitlines()
        if line.startswith("worktree ")
    )


def test_chain_marks_between_milestones_until_final_completion(tmp_path: Path) -> None:
    spec_path = _write_chain_spec(tmp_path, branch=None)
    idea2 = tmp_path / "idea2.md"
    idea2.write_text("ship second milestone\n", encoding="utf-8")
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8")
        + "  - label: m2\n"
        + f"    idea: {idea2}\n",
        encoding="utf-8",
    )
    spec = load_spec(spec_path)
    state = chain_module.ChainState(current_milestone_index=0, last_state="running")

    chain_module._mark_chain_after_milestone_advance(spec, state, next_index=1)

    assert state.current_milestone_index == 1
    assert state.current_plan_name is None
    assert state.last_state == "between_milestones"

    chain_module._mark_chain_after_milestone_advance(spec, state, next_index=2)

    assert state.current_milestone_index == 2
    assert state.last_state == "done"


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


def test_enable_auto_merge_refuses_dirty_worktree_before_gh_merge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    dirty = repo / "src.py"
    dirty.write_text("print('local only')\n", encoding="utf-8")

    def fail_run_command(*_args, **_kwargs):
        raise AssertionError("gh merge must not run with a dirty worktree")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            subprocess=subprocess,
            _run_command=fail_run_command,
        ),
    )

    with pytest.raises(CliError) as exc_info:
        _enable_auto_merge(repo, 77, writer=lambda _message: None)

    assert exc_info.value.code == "dirty_worktree_before_pr_merge"
    assert "src.py" in exc_info.value.message


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


def test_run_chain_repushes_deleted_remote_base_branch_from_local_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = tmp_path / "origin.git"
    source = tmp_path / "source"
    runner = tmp_path / "runner"
    base_branch = "stack/base"
    messages: list[str] = []

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(source))
    _git(source, "config", "user.email", "test@example.com")
    _git(source, "config", "user.name", "Test User")
    (source / "README.md").write_text("base\n", encoding="utf-8")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "base")
    _git(source, "branch", "-M", base_branch)
    _git(source, "push", "-u", "origin", base_branch)

    _git(tmp_path, "clone", "--branch", base_branch, str(origin), str(runner))
    _git(runner, "config", "user.email", "test@example.com")
    _git(runner, "config", "user.name", "Test User")

    spec_path = _write_chain_spec(runner, base_branch=base_branch, branch=None)
    local_base_sha = _git(runner, "rev-parse", f"refs/heads/{base_branch}").stdout.strip()

    _git(source, "push", "origin", f":{base_branch}")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._preflight_agent_backends",
        lambda spec, *, writer: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.resolve_execution_environment",
        lambda **_kwargs: SimpleNamespace(to_dict=lambda: {}),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._init_plan",
        lambda *args, **kwargs: "plan-m1",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._write_chain_policy_into_plan_meta",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._attach_chain_anchors_to_plan",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
        lambda *args, **kwargs: SimpleNamespace(status="blocked", reason="stop"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._handle_outcome",
        lambda *args, **kwargs: "stop",
    )

    result = run_chain(spec_path, runner, writer=messages.append)

    assert result["status"] == "stopped"
    assert _git(runner, "ls-remote", "--heads", "origin", base_branch).stdout.split()[0] == local_base_sha
    saved = load_chain_state(spec_path)
    assert saved.target_base_ref == local_base_sha
    assert any(
        f"re-pushed missing base branch {base_branch} from local at {local_base_sha}" in message
        for message in messages
    )


def test_run_chain_surfaces_unrecoverable_missing_base_branch_as_terminal_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = tmp_path / "origin.git"
    source = tmp_path / "source"
    runner = tmp_path / "runner"
    base_branch = "stack/base"

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(source))
    _git(source, "config", "user.email", "test@example.com")
    _git(source, "config", "user.name", "Test User")
    (source / "README.md").write_text("base\n", encoding="utf-8")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "base")
    base_sha = _git(source, "rev-parse", "HEAD").stdout.strip()
    _git(source, "branch", "-M", "main")
    _git(source, "push", "-u", "origin", "main")
    _git(source, "checkout", "-b", base_branch)
    _git(source, "push", "-u", "origin", base_branch)

    _git(tmp_path, "clone", "--branch", "main", str(origin), str(runner))
    _git(runner, "config", "user.email", "test@example.com")
    _git(runner, "config", "user.name", "Test User")
    _git(runner, "fetch", "origin", base_branch)
    _git(runner, "update-ref", "-d", f"refs/remotes/origin/{base_branch}")

    spec_path = _write_chain_spec(runner, base_branch=base_branch, branch=None)
    save_chain_state(
        spec_path,
        chain_module.ChainState(
            current_milestone_index=0,
            target_base_ref="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        ),
    )

    _git(source, "push", "origin", f":{base_branch}")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._preflight_agent_backends",
        lambda spec, *, writer: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.resolve_execution_environment",
        lambda **_kwargs: SimpleNamespace(to_dict=lambda: {}),
    )

    result = run_chain(spec_path, runner, writer=lambda _message: None)

    saved = load_chain_state(spec_path)
    assert result["status"] == "stopped"
    assert saved.last_state == "missing_base_ref"
    assert saved.metadata["missing_base_ref"]["base_branch"] == base_branch
    assert (
        saved.metadata["missing_base_ref"]["last_known_sha"]
        == "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    )
    assert "cannot be restored from local refs" in result["reason"]


def test_run_chain_preserves_dirty_retry_attempt_before_reinit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = tmp_path / "origin.git"
    source = tmp_path / "source"
    runner = tmp_path / "runner"

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(source))
    _git(source, "config", "user.email", "test@example.com")
    _git(source, "config", "user.name", "Test User")
    (source / "README.md").write_text("base\n", encoding="utf-8")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "base")
    _git(source, "branch", "-M", "main")
    _git(source, "push", "-u", "origin", "main")

    _git(tmp_path, "clone", str(origin), str(runner))
    _git(runner, "config", "user.email", "test@example.com")
    _git(runner, "config", "user.name", "Test User")
    spec_path = _write_chain_spec(runner, branch=None)
    text = spec_path.read_text(encoding="utf-8")
    spec_path.write_text("driver:\n  require_clean_base: true\n" + text, encoding="utf-8")
    _git(runner, "add", "NORTHSTAR.md", "chain.yaml", "idea.md")
    _git(runner, "commit", "-m", "add chain spec")

    init_calls: list[str] = []
    drive_calls = 0

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._preflight_agent_backends",
        lambda spec, *, writer: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.resolve_execution_environment",
        lambda **_kwargs: SimpleNamespace(to_dict=lambda: {}),
    )

    def fake_init(*_args, **_kwargs):
        plan_name = f"plan-{len(init_calls) + 1}"
        init_calls.append(plan_name)
        return plan_name

    def fake_drive(*_args, **_kwargs):
        nonlocal drive_calls
        drive_calls += 1
        (runner / "src.py").write_text(f"attempt {drive_calls}\n", encoding="utf-8")
        return SimpleNamespace(status="blocked", reason="cap")

    def fake_handle(*_args, **_kwargs):
        return "retry" if drive_calls == 1 else "stop"

    monkeypatch.setattr("arnold_pipelines.megaplan.chain._init_plan", fake_init)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._write_chain_policy_into_plan_meta",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._attach_chain_anchors_to_plan",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
        fake_drive,
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.chain._handle_outcome", fake_handle)

    messages: list[str] = []
    result = run_chain(spec_path, runner, writer=messages.append)

    assert result["status"] == "stopped"
    assert init_calls == ["plan-1", "plan-2"]
    assert "attempt 2\n" == (runner / "src.py").read_text(encoding="utf-8")
    assert "attempt 1" in _git(runner, "stash", "show", "-p", "--include-untracked", "stash@{0}").stdout
    saved = load_chain_state(spec_path)
    preserved = saved.metadata["retry_preserved_wip"]
    assert preserved[-1]["milestone"] == "m1"
    assert preserved[-1]["plan"] == "plan-1"
    assert preserved[-1]["stash_ref"].startswith("stash@{")
    assert any("preserving via git stash before retry" in msg for msg in messages)


def test_chain_child_python_commands_use_safe_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    idea = root / "idea.md"
    idea.write_text("do the thing\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        if "init" in cmd:
            return subprocess.CompletedProcess(cmd, 0, '{"plan": "plan-x"}\n', "")
        if "status" in cmd:
            return subprocess.CompletedProcess(cmd, 0, '{"state": "planned"}\n', "")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.subprocess.run",
        fake_run,
    )

    assert (
        _init_plan(
            root,
            str(idea),
            robustness="thorough",
            auto_approve=True,
            phase_model=["prep=hermes:kimi:kimi-k2.7-code"],
            writer=lambda _message: None,
        )
        == "plan-x"
    )
    assert _plan_state(root, "plan-x", timeout=30) == "planned"

    for cmd in calls:
        assert cmd[:3] == [sys.executable, "-P", "-m"]


def test_commit_phase_excludes_tracked_runtime_journals(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    event_log = root / ".megaplan" / "epics" / "epic-a" / "events.jsonl"
    event_log.parent.mkdir(parents=True)
    event_log.write_text('{"event":"old"}\n', encoding="utf-8")
    _git(root, "add", ".megaplan/epics/epic-a/events.jsonl")
    _git(root, "commit", "-m", "track event log")

    event_log.write_text('{"event":"old"}\n{"event":"new"}\n', encoding="utf-8")
    changed = root / "changed.txt"
    changed.write_text("real milestone work\n", encoding="utf-8")

    messages: list[str] = []
    commit_sha = _commit_phase(root, "plan-x", "review-cleanup", writer=messages.append)

    assert commit_sha is not None
    committed_paths = _git(root, "show", "--name-only", "--format=", commit_sha).stdout.splitlines()
    assert "changed.txt" in committed_paths
    assert ".megaplan/epics/epic-a/events.jsonl" not in committed_paths
    assert _git(root, "ls-files", "-v", ".megaplan/epics/epic-a/events.jsonl").stdout.startswith("S ")
    assert any("excluded runtime journal paths" in message for message in messages)


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
    assert ["git", "push", "--no-verify", "--force-with-lease", "origin", "HEAD:branch-x"] in run_command_calls
    assert any("warning: git rebase --abort failed" in message for message in messages)


def test_commit_and_push_phase_pushes_cleanup_only_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    messages: list[str] = []
    subprocess_calls: list[list[str]] = []
    run_command_calls: list[list[str]] = []
    commit_results = iter([None, "cleanup123"])

    def fake_commit_phase(*_args, **_kwargs) -> str | None:
        return next(commit_results)

    def fake_run(cmd, **_kwargs):
        subprocess_calls.append(list(cmd))
        if cmd[:3] == ["git", "fetch", "origin"]:
            return subprocess.CompletedProcess(cmd, 1, "", "missing remote branch")
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

    assert ["git", "fetch", "origin", "branch-x"] in subprocess_calls
    assert ["git", "push", "--no-verify", "origin", "HEAD:branch-x"] in run_command_calls


def test_run_chain_resume_refreshes_milestone_branch_and_pr_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    spec_path = _write_chain_spec(root)
    plan_dir = root / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        '{"name":"plan-m1","current_state":"planned"}\n',
        encoding="utf-8",
    )
    save_chain_state(
        spec_path,
        chain_module.ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="failed",
            pr_number=118,
            pr_state="merged",
        ),
    )

    checkout_calls: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._preflight_agent_backends",
        lambda spec, *, writer: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.resolve_execution_environment",
        lambda **_kwargs: SimpleNamespace(to_dict=lambda: {}),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._plan_state",
        lambda *_args, **_kwargs: "planned",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
        lambda _root, branch, *, base_branch, writer, from_origin=False, expected_base_ref=None: checkout_calls.append(
            (branch, base_branch, from_origin)
        ),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._capture_sync_state",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._ensure_milestone_pr",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("_ensure_milestone_pr should not run when PR state exists")
        ),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
        lambda *args, **kwargs: SimpleNamespace(status="blocked", reason="stop"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._handle_outcome",
        lambda *args, **kwargs: "stop",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._pr_state",
        lambda *args, **kwargs: "open",
    )

    result = run_chain(spec_path, root, writer=lambda _message: None)

    assert result["status"] == "stopped"
    assert checkout_calls == [("test/m1", "main", True)]
    saved = load_chain_state(spec_path)
    assert saved.pr_number == 118
    assert saved.pr_state == "merged"


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
