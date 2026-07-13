from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import arnold_pipelines.megaplan.chain as chain_module
import arnold_pipelines.megaplan.chain.git_ops as git_ops
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


def test_chain_facade_reexports_git_push_helper() -> None:
    assert (
        chain_module._run_git_push_command is git_ops._run_git_push_command
    )



def test_git_push_helper_uses_noninteractive_github_token(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setenv("GITHUB_TOKEN", "gho_testtoken")
    monkeypatch.setattr(git_ops.subprocess, "run", fake_run)

    git_ops._run_git_push_command(
        tmp_path,
        ["git", "push", "--no-verify", "-u", "origin", "demo-branch"],
        writer=lambda _msg: None,
    )

    env = seen["env"]
    assert isinstance(env, dict)
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert env["GIT_CONFIG_VALUE_0"].startswith("AUTHORIZATION: basic ")


def test_gh_command_env_preserves_token_auth_for_first_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GH_TOKEN", "gho_testtoken")
    env = git_ops._command_env(["gh", "pr", "list"])

    assert isinstance(env, dict)
    assert env["GH_TOKEN"] == "gho_testtoken"


def test_run_command_retries_gh_without_env_on_bad_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(cmd, **kwargs):
        env = kwargs.get("env")
        calls.append({"cmd": list(cmd), "env": dict(env) if isinstance(env, dict) else env})
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                cmd,
                1,
                stdout="",
                stderr="authentication failed",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    monkeypatch.setenv("GH_TOKEN", "gho_badtoken")
    monkeypatch.setattr(git_ops.subprocess, "run", fake_run)
    monkeypatch.setattr(
        git_ops,
        "_compat",
        lambda: SimpleNamespace(
            subprocess=git_ops.subprocess,
            _command_env=git_ops._command_env,
            _command_env_without_gh_tokens=git_ops._command_env_without_gh_tokens,
            _should_retry_gh_without_env=git_ops._should_retry_gh_without_env,
        ),
    )

    proc = git_ops._run_command(
        tmp_path,
        ["gh", "pr", "list", "--json", "number"],
        writer=lambda _message: None,
        error_code="gh_pr_lookup_failed",
    )

    assert proc.returncode == 0
    assert len(calls) == 2
    assert calls[0]["env"]["GH_TOKEN"] == "gho_badtoken"
    assert "GH_TOKEN" not in calls[1]["env"]

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


def test_chain_clean_resets_skip_worktree_megaplan_runtime_journal(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    journal = repo / ".megaplan" / "epics" / "m1" / "events.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text('{"event":"base"}\n', encoding="utf-8")
    _git(repo, "add", ".megaplan/epics/m1/events.jsonl")
    _git(repo, "commit", "-m", "track journal")

    _git(repo, "update-index", "--skip-worktree", ".megaplan/epics/m1/events.jsonl")
    journal.write_text('{"event":"dirty runtime"}\n', encoding="utf-8")
    assert _git(repo, "ls-files", "-v", ".megaplan/epics/m1/events.jsonl").stdout.startswith("S ")
    messages: list[str] = []

    _clean_worktree_for_chain(repo, writer=messages.append)

    assert journal.read_text(encoding="utf-8") == '{"event":"base"}\n'
    assert _git(repo, "ls-files", "-v", ".megaplan/epics/m1/events.jsonl").stdout.startswith("H ")
    joined = "".join(messages)
    assert ".megaplan/epics/m1/events.jsonl" in joined
    assert ".megaplan/plans" not in joined


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


def test_enable_auto_merge_ignores_internal_runtime_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    runtime_cache = repo / ".megaplan" / "runtime" / "editable-engine"
    runtime_cache.mkdir(parents=True)
    (runtime_cache / "README.md").write_text("generated runtime mirror\n", encoding="utf-8")

    calls: list[list[str]] = []

    def record_run_command(_root, argv, **_kwargs):
        calls.append(list(argv))

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            subprocess=subprocess,
            _run_command=record_run_command,
            _pr_state=lambda *_args, **_kwargs: "open",
        ),
    )

    _enable_auto_merge(repo, 77, writer=lambda _message: None)

    assert calls
    assert calls[0][:4] == ["gh", "pr", "merge", "77"]


def test_enable_auto_merge_ignores_internal_run_telemetry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    incident_events = repo / ".megaplan" / "incident-ledger" / "events.jsonl"
    incident_events.parent.mkdir(parents=True)
    incident_events.write_text('{"event":"old"}\n', encoding="utf-8")
    epic_events = repo / ".megaplan" / "epics" / "m1" / "events.jsonl"
    epic_events.parent.mkdir(parents=True)
    epic_events.write_text('{"event":"old"}\n', encoding="utf-8")
    _git(repo, "add", ".megaplan/incident-ledger/events.jsonl", ".megaplan/epics/m1/events.jsonl")
    _git(repo, "commit", "-m", "track runtime telemetry")
    incident_events.write_text('{"event":"old"}\n{"event":"new"}\n', encoding="utf-8")
    epic_events.write_text('{"event":"old"}\n{"event":"new"}\n', encoding="utf-8")

    calls: list[list[str]] = []

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            subprocess=subprocess,
            _run_command=lambda _root, argv, **_kwargs: calls.append(list(argv)),
            _pr_state=lambda *_args, **_kwargs: "open",
        ),
    )

    _enable_auto_merge(repo, 77, writer=lambda _message: None)

    assert calls
    assert calls[0][:4] == ["gh", "pr", "merge", "77"]


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


def test_ensure_milestone_pr_defers_when_branch_has_no_commits_ahead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[str] = []
    milestone = MilestoneSpec(
        label="m1",
        idea=Path("m1.md"),
        branch="test/m1",
    )

    def fail_run_command(_root, _argv, **_kwargs):
        raise CliError(
            "gh_pr_create_failed",
            "gh pr create failed",
            extra={
                "stderr": (
                    "pull request create failed: GraphQL: "
                    "No commits between main and test/m1 (createPullRequest)"
                )
            },
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops.shutil.which",
        lambda name: "/usr/bin/gh" if name == "gh" else "/bin/other",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            _list_open_pr_for_branch=lambda *_args, **_kwargs: None,
            _run_command=fail_run_command,
            _parse_pr_number_from_url=lambda _output: None,
        ),
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
    assert any("deferring PR creation" in message for message in messages)


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


def test_checkout_existing_milestone_skips_rebase_when_remote_base_rewrites_away_expected_base(
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
    _git(source, "branch", "-M", "main")
    _git(source, "push", "-u", "origin", "main")
    expected_base = _git(source, "rev-parse", "HEAD").stdout.strip()

    _git(source, "checkout", "-b", "cloud/m1")
    (source / "milestone.txt").write_text("m1\n", encoding="utf-8")
    _git(source, "add", "milestone.txt")
    _git(source, "commit", "-m", "milestone")
    milestone_sha = _git(source, "rev-parse", "HEAD").stdout.strip()
    _git(source, "push", "-u", "origin", "cloud/m1")

    _git(source, "checkout", "--orphan", "rewrite-main")
    for path in source.iterdir():
        if path.name == ".git":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    (source / "README.md").write_text("rewritten main\n", encoding="utf-8")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "rewrite main unrelated")
    _git(source, "branch", "-M", "rewrite-main", "main")
    _git(source, "push", "--force", "origin", "main")

    _git(tmp_path, "clone", "--branch", "main", str(origin), str(runner))
    _git(runner, "config", "user.email", "test@example.com")
    _git(runner, "config", "user.name", "Test User")

    _checkout_milestone_branch(
        runner,
        "cloud/m1",
        base_branch="main",
        writer=messages.append,
        from_origin=True,
        expected_base_ref=expected_base,
    )

    assert _git(runner, "branch", "--show-current").stdout.strip() == "cloud/m1"
    assert _git(runner, "rev-parse", "HEAD").stdout.strip() == milestone_sha
    assert (runner / "milestone.txt").read_text(encoding="utf-8") == "m1\n"
    assert any("skipping automatic rebase for existing milestone branch cloud/m1" in m for m in messages)
    assert not any("git rebase origin/main" in m for m in messages)


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
            _run_git_push_command=git_ops._run_git_push_command,
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
            _run_git_push_command=git_ops._run_git_push_command,
        ),
    )

    _commit_and_push_phase(root, "branch-x", "plan-x", "finalize", writer=messages.append)

    assert ["git", "fetch", "origin", "branch-x"] in subprocess_calls
    assert ["git", "push", "--no-verify", "origin", "HEAD:branch-x"] in run_command_calls


def test_commit_and_push_phase_uses_extended_timeout_for_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    push_timeouts: list[float | None] = []

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._commit_phase",
        lambda *_args, **_kwargs: "abc123",
    )

    def fake_run(cmd, **_kwargs):
        if cmd[:3] == ["git", "fetch", "origin"]:
            return subprocess.CompletedProcess(cmd, 1, "", "missing remote branch")
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    def fake_run_command(_root, cmd, **kwargs):
        if cmd[:2] == ["git", "push"]:
            push_timeouts.append(kwargs.get("timeout"))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            subprocess=SimpleNamespace(
                run=fake_run,
                TimeoutExpired=subprocess.TimeoutExpired,
            ),
            _run_command=fake_run_command,
            _run_git_push_command=git_ops._run_git_push_command,
        ),
    )

    _commit_and_push_phase(root, "branch-x", "plan-x", "finalize", writer=lambda _msg: None)

    assert push_timeouts == [git_ops._GIT_PUSH_TIMEOUT_SECONDS]


def test_run_git_push_command_recovers_when_timeout_already_published_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    messages: list[str] = []

    def fake_run_command(_root, cmd, **_kwargs):
        raise CliError(
            "git_push_failed",
            "git push failed with timeout",
            extra={"command": cmd, "error": "Command timed out after 600 seconds"},
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            _run_command=fake_run_command,
        ),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._expected_remote_push_target",
        lambda *_args, **_kwargs: ("branch-x", "abc123"),
    )
    remote_heads = iter([None, "abc123"])
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._remote_branch_head",
        lambda *_args, **_kwargs: next(remote_heads),
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.chain.git_ops.time.sleep", lambda _seconds: None)

    proc = git_ops._run_git_push_command(
        root,
        ["git", "push", "--no-verify", "origin", "HEAD:branch-x"],
        writer=messages.append,
    )

    assert proc.returncode == 0
    assert any("timed out locally" in message for message in messages)


def test_run_git_push_command_retries_non_fast_forward_with_force_with_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    messages: list[str] = []
    calls: list[list[str]] = []

    def fake_run_command(_root, cmd, **_kwargs):
        calls.append(list(cmd))
        if cmd == ["git", "push", "--no-verify", "origin", "HEAD:branch-x"]:
            raise CliError(
                "git_push_failed",
                "git push failed",
                extra={"stderr": "! [rejected] HEAD -> branch-x (non-fast-forward)"},
            )
        if cmd == ["git", "push", "--no-verify", "--force-with-lease", "origin", "HEAD:branch-x"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            _run_command=fake_run_command,
        ),
    )

    proc = git_ops._run_git_push_command(
        root,
        ["git", "push", "--no-verify", "origin", "HEAD:branch-x"],
        writer=messages.append,
    )

    assert proc.returncode == 0
    assert calls == [
        ["git", "push", "--no-verify", "origin", "HEAD:branch-x"],
        ["git", "push", "--no-verify", "--force-with-lease", "origin", "HEAD:branch-x"],
    ]
    assert any("retrying with --force-with-lease" in message for message in messages)


def test_run_git_push_command_recovers_when_timeout_already_published_branch_with_u_origin_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    messages: list[str] = []

    def fake_run_command(_root, cmd, **_kwargs):
        raise CliError(
            "git_push_failed",
            "git push failed with timeout",
            extra={"command": cmd, "error": "Command timed out after 600 seconds"},
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            _run_command=fake_run_command,
        ),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._expected_remote_push_target",
        lambda *_args, **_kwargs: ("branch-x", "abc123"),
    )
    remote_heads = iter([None, "abc123"])
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._remote_branch_head",
        lambda *_args, **_kwargs: next(remote_heads),
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.chain.git_ops.time.sleep", lambda _seconds: None)

    proc = git_ops._run_git_push_command(
        root,
        ["git", "push", "--no-verify", "-u", "origin", "branch-x"],
        writer=messages.append,
    )

    assert proc.returncode == 0
    assert any("timed out locally" in message for message in messages)


def test_run_git_push_command_raises_when_timeout_not_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    def fake_run_command(_root, cmd, **_kwargs):
        raise CliError(
            "git_push_failed",
            "git push failed with timeout",
            extra={"command": cmd, "error": "Command timed out after 600 seconds"},
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            _run_command=fake_run_command,
        ),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._expected_remote_push_target",
        lambda *_args, **_kwargs: ("branch-x", "abc123"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._remote_branch_head",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops.time.monotonic",
        iter([0.0, 31.0]).__next__,
    )

    with pytest.raises(CliError, match="git push failed with timeout"):
        git_ops._run_git_push_command(
            root,
            ["git", "push", "--no-verify", "origin", "HEAD:branch-x"],
            writer=lambda _msg: None,
        )


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


def test_run_chain_resume_without_pr_creates_init_anchor_before_pr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    spec_path = _write_chain_spec(root)
    plan_dir = root / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        '{"name":"plan-m1","current_state":"initialized"}\n',
        encoding="utf-8",
    )
    save_chain_state(
        spec_path,
        chain_module.ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="initialized",
            pr_number=None,
            pr_state=None,
        ),
    )

    commit_calls: list[tuple[str, str, str]] = []
    ensure_calls: list[str] = []

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
        lambda *_args, **_kwargs: "initialized",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._capture_sync_state",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._resume_needs_init_anchor",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._commit_and_push_phase",
        lambda _root, branch, plan, phase, **_kwargs: commit_calls.append((branch, plan, phase)),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._ensure_milestone_pr",
        lambda _root, milestone, *, base_branch, writer: ensure_calls.append(milestone.label) or 81,
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
    assert commit_calls == [("test/m1", "plan-m1", "init")]
    assert ensure_calls == ["m1"]
    saved = load_chain_state(spec_path)
    assert saved.pr_number == 81
    assert saved.pr_state == "open"


def test_run_chain_retries_deferred_pr_creation_after_phase_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    spec_path = _write_chain_spec(root)
    _git(root, "add", "NORTHSTAR.md", "chain.yaml", "idea.md")
    _git(root, "commit", "-m", "add chain spec")

    ensure_calls: list[str] = []

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._preflight_agent_backends",
        lambda spec, *, writer: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.resolve_execution_environment",
        lambda **_kwargs: SimpleNamespace(to_dict=lambda: {}),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._refresh_base_branch",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
        lambda *args, **kwargs: None,
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
        "arnold_pipelines.megaplan.chain._commit_and_push_phase",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._capture_sync_state",
        lambda *args, **kwargs: None,
    )

    def fake_ensure(*_args, **_kwargs):
        ensure_calls.append("ensure")
        return None if len(ensure_calls) == 1 else 80

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._ensure_milestone_pr",
        fake_ensure,
    )

    def fake_drive_plan(*_args, on_phase_complete=None, **_kwargs):
        assert on_phase_complete is not None
        on_phase_complete("plan", 0, "", "")
        return DriverOutcome(
            status="done",
            plan="plan-m1",
            final_state="done",
            iterations=1,
            reason="ok",
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
        fake_drive_plan,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._record_chain_last_state_after_plan_run",
        lambda _root, _spec_path, state, outcome, *, writer: state,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._handle_outcome",
        lambda *args, **kwargs: "stop",
    )

    run_chain(spec_path, root, writer=lambda _message: None)

    saved = load_chain_state(spec_path)
    assert ensure_calls == ["ensure", "ensure"]
    assert saved.pr_number == 80
    assert saved.pr_state == "open"


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


@pytest.mark.parametrize(
    ("pr_states", "guard_results", "expected_status"),
    [
        (
            ["open", "open"],
            [(False, "no typed no-op completion waiver found")],
            "stopped",
        ),
        (
            ["open", "merged"],
            [
                (False, "open PR evidence is stale"),
                (True, "merged publication evidence is authoritative"),
            ],
            "done",
        ),
    ],
)
def test_run_chain_rechecks_pr_state_when_premerge_completion_guard_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pr_states: list[str],
    guard_results: list[tuple[bool, str]],
    expected_status: str,
) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    spec_path = _write_chain_spec(root)
    _git(root, "add", "NORTHSTAR.md", "chain.yaml", "idea.md")
    _git(root, "commit", "-m", "add chain spec")

    plan_dir = root / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "plan-m1", "current_state": "done"}),
        encoding="utf-8",
    )

    ready_calls: list[int] = []
    merge_calls: list[int] = []

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._preflight_agent_backends",
        lambda spec, *, writer: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.resolve_execution_environment",
        lambda **_kwargs: SimpleNamespace(to_dict=lambda: {}),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._refresh_base_branch",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
        lambda *args, **kwargs: None,
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
        "arnold_pipelines.megaplan.chain._commit_and_push_phase",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._capture_sync_state",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._ensure_milestone_pr",
        lambda *args, **kwargs: 80,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
        lambda *args, **kwargs: DriverOutcome(
            status="done",
            plan="plan-m1",
            final_state="done",
            iterations=1,
            reason="ok",
        ),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._record_chain_last_state_after_plan_run",
        lambda _root, _spec_path, state, outcome, *, writer: state,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._handle_outcome",
        lambda *args, **kwargs: "advance",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._plan_terminal_completion_is_authoritative",
        lambda *args, **kwargs: (True, "authoritative"),
    )
    guard_iter = iter(guard_results)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._chain_completion_guard",
        lambda *args, **kwargs: next(guard_iter),
    )
    pr_state_iter = iter(pr_states)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._pr_state",
        lambda *args, **kwargs: next(pr_state_iter),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._mark_pr_ready",
        lambda *args, **kwargs: ready_calls.append(1),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._enable_auto_merge",
        lambda *args, **kwargs: merge_calls.append(1) or "merged",
    )

    messages: list[str] = []
    result = run_chain(spec_path, root, writer=messages.append)

    assert result["status"] == expected_status
    assert ready_calls == []
    assert merge_calls == []

    saved = load_chain_state(spec_path)
    if expected_status == "stopped":
        assert "completion guard blocked before PR merge" in result["reason"]
        assert saved.last_state == "blocked"
        assert saved.pr_number == 80
        assert saved.pr_state == "open"
        assert saved.completed == []
    else:
        assert saved.last_state == "done"
        assert saved.current_milestone_index == 1
        assert saved.current_plan_name is None
        assert saved.completed[0]["label"] == "m1"
        assert saved.completed[0]["pr_state"] == "merged"
        assert any("merged while completion guard was evaluating" in msg for msg in messages)
