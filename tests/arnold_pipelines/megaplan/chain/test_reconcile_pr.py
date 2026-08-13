"""Slice B — reconcile milestone PR lifecycle tests.

Covers the fail-closed reconcile PR creation/deletion primitives in
``chain/git_ops.py`` and the chain-level await-merge behavior for the
generated ``kind: reconcile`` milestone: merged advances, an intentionally
closed PR is recorded as a rejection and proceeds to terminal close (never
``_stop_for_closed_pr``), and unknown/open states keep the chain parked at
``awaiting_pr_merge``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import arnold_pipelines.megaplan.chain as chain_module
import arnold_pipelines.megaplan.chain.git_ops as git_ops
from arnold_pipelines.megaplan.chain.git_ops import (
    _delete_reconcile_pr_branch,
    _ensure_reconcile_pr,
)
from arnold_pipelines.megaplan.chain.spec import MilestoneSpec
from arnold_pipelines.megaplan.chain.spec import ChainState, load_spec, save_chain_state
from arnold_pipelines.megaplan.chain import run_chain
from arnold_pipelines.megaplan.types import CliError

STATE_AWAITING_PR_MERGE = "awaiting_pr_merge"


def _reconcile_milestone(
    *,
    label: str = "reconcile",
    branch: str = "reconcile/test-epic-20260811",
    target_branch: str = "main",
) -> MilestoneSpec:
    return MilestoneSpec(
        label=label,
        idea=Path("briefs/reconcile.md"),
        branch=branch,
        kind="reconcile",
        target_branch=target_branch,
        merge_policy="review",
        phase_model=["execute=codex"],
    )


# ── _ensure_reconcile_pr (fail-closed) ───────────────────────────────────


def test_ensure_reconcile_pr_fails_closed_when_gh_missing(monkeypatch) -> None:
    messages: list[str] = []
    milestone = _reconcile_milestone()

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops.shutil.which",
        lambda name: None if name == "gh" else "/bin/other",
    )

    with pytest.raises(CliError) as excinfo:
        _ensure_reconcile_pr(
            Path.cwd(),
            milestone,
            base_branch="main",
            writer=messages.append,
        )
    assert excinfo.value.code == "gh_unavailable"
    assert "fail-closed" in excinfo.value.message
    assert messages == []


def test_ensure_reconcile_pr_creates_with_recorded_target_base(monkeypatch) -> None:
    messages: list[str] = []
    milestone = _reconcile_milestone(branch="reconcile/test-epic-20260811")
    captured: list[list[str]] = []

    def fake_run_command(_root, argv, **_kwargs):
        captured.append(list(argv))
        return SimpleNamespace(stdout="https://github.com/acme/arnold/pull/88\n")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops.shutil.which",
        lambda name: "/usr/bin/gh" if name == "gh" else "/bin/other",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            _list_open_pr_for_branch=lambda *_args, **_kwargs: None,
            _run_command=fake_run_command,
            _parse_pr_number_from_url=lambda output: int(
                output.strip().rstrip("/").rsplit("/", 1)[-1]
            ),
        ),
    )

    number = _ensure_reconcile_pr(
        Path.cwd(),
        milestone,
        base_branch="main",
        writer=messages.append,
    )

    assert number == 88
    create = captured[0]
    assert create[0] == "gh"
    assert create[1:4] == ["pr", "create", "--base"]
    assert create[4] == "main"  # the recorded target, not the chain base
    assert create[6] == "reconcile/test-epic-20260811"
    assert "megaplan reconcile" in create[8]  # title
    assert any("reconcile" in str(part) for part in create)


def test_ensure_reconcile_pr_reuses_open_pr(monkeypatch) -> None:
    messages: list[str] = []
    milestone = _reconcile_milestone()

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops.shutil.which",
        lambda name: "/usr/bin/gh" if name == "gh" else "/bin/other",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: SimpleNamespace(
            _list_open_pr_for_branch=lambda *_args, **_kwargs: {"number": 42, "state": "open"},
            _run_command=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("must not re-create an existing PR")
            ),
            _parse_pr_number_from_url=lambda _output: None,
        ),
    )

    number = _ensure_reconcile_pr(
        Path.cwd(),
        milestone,
        base_branch="main",
        writer=messages.append,
    )

    assert number == 42
    assert any("reusing PR #42" in message for message in messages)


def test_ensure_reconcile_pr_defers_no_commits(monkeypatch) -> None:
    messages: list[str] = []
    milestone = _reconcile_milestone()

    def fail_run_command(_root, _argv, **_kwargs):
        raise CliError(
            "gh_reconcile_pr_create_failed",
            "gh pr create failed",
            extra={
                "stderr": (
                    "pull request create failed: GraphQL: "
                    "No commits between main and reconcile/test-epic-20260811 "
                    "(createPullRequest)"
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
        _ensure_reconcile_pr(
            Path.cwd(),
            milestone,
            base_branch="main",
            writer=messages.append,
        )
        is None
    )
    assert any("deferring reconcile PR creation" in message for message in messages)


def test_ensure_reconcile_pr_propagates_other_gh_errors(monkeypatch) -> None:
    messages: list[str] = []
    milestone = _reconcile_milestone()

    def fail_run_command(_root, _argv, **_kwargs):
        raise CliError(
            "gh_reconcile_pr_create_failed",
            "gh pr create failed",
            extra={"stderr": "GraphQL: Repository was archived (createPullRequest)"},
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

    with pytest.raises(CliError) as excinfo:
        _ensure_reconcile_pr(
            Path.cwd(),
            milestone,
            base_branch="main",
            writer=messages.append,
        )
    assert excinfo.value.code == "gh_reconcile_pr_create_failed"
    assert not any("deferring" in message for message in messages)


# ── _delete_reconcile_pr_branch ──────────────────────────────────────────


def _delete_compat(run_command):
    return SimpleNamespace(_run_command=run_command)


def _sandbox_census_stores(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Point the reference census at sandboxed (initially absent) stores."""
    monkeypatch.setenv("ARNOLD_BASE_DIR", "")
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST_DIR", str(tmp_path / "ref-manifests"))
    monkeypatch.setenv("ARNOLD_REFERENCE_CHAIN_STORE", str(tmp_path / "ref-chains"))
    monkeypatch.setenv("ARNOLD_REFERENCE_MARKER_STORE", str(tmp_path / "ref-markers"))
    monkeypatch.setenv(
        "ARNOLD_REFERENCE_SCHEDULE_STORES", str(tmp_path / "ref-schedules")
    )
    monkeypatch.setenv(
        "ARNOLD_REFERENCE_REPAIR_QUEUE", str(tmp_path / "ref-repair-queue")
    )
    monkeypatch.setenv("ARNOLD_REFERENCE_LEASE_STORE", str(tmp_path / "ref-leases"))


def test_delete_reconcile_pr_branch_deletes_local_and_remote(monkeypatch) -> None:
    messages: list[str] = []
    calls: list[list[str]] = []

    def run_command(_root, argv, **_kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: _delete_compat(run_command),
    )

    assert _delete_reconcile_pr_branch(
        Path.cwd(), "reconcile/test-epic-20260811", writer=messages.append
    )
    assert calls[0] == ["git", "branch", "-D", "reconcile/test-epic-20260811"]
    assert calls[1] == ["git", "push", "origin", "--delete", "reconcile/test-epic-20260811"]
    assert any("deleted reconcile PR branch" in message for message in messages)


def test_delete_reconcile_pr_branch_treats_missing_remote_as_success(
    monkeypatch,
) -> None:
    messages: list[str] = []
    calls: list[list[str]] = []

    def run_command(_root, argv, **_kwargs):
        calls.append(list(argv))
        if argv[1] == "push":
            raise CliError(
                "git_push_delete_reconcile_branch_failed",
                "git push origin --delete reconcile/x exited 1",
                extra={"stderr": "remote ref does not exist"},
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: _delete_compat(run_command),
    )

    assert _delete_reconcile_pr_branch(
        Path.cwd(), "reconcile/x", writer=messages.append
    )
    assert any("already deleted on origin" in message for message in messages)


def test_delete_reconcile_pr_branch_raises_on_unexpected_failure(
    monkeypatch,
) -> None:
    messages: list[str] = []

    def run_command(_root, argv, **_kwargs):
        if argv[1] == "push":
            raise CliError(
                "git_push_delete_reconcile_branch_failed",
                "git push origin --delete reconcile/x exited 1",
                extra={"stderr": "permission denied"},
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: _delete_compat(run_command),
    )

    with pytest.raises(CliError):
        _delete_reconcile_pr_branch(Path.cwd(), "reconcile/x", writer=messages.append)


def test_delete_reconcile_pr_branch_refuses_referenced_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reconcile branch whose checkout root is still referenced by a
    runtime store (T-0027 reference census REFERENCED) is never deleted:
    zero local ``git branch -D`` / origin ``push --delete`` calls."""
    _sandbox_census_stores(monkeypatch, tmp_path)
    store = tmp_path / "ref-chains"
    store.mkdir(parents=True)
    (store / "chain-ref.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "execution_environment": {"engine_root": str(Path.cwd())}
                }
            }
        ),
        encoding="utf-8",
    )
    messages: list[str] = []
    calls: list[list[str]] = []

    def run_command(_root, argv, **_kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: _delete_compat(run_command),
    )

    result = _delete_reconcile_pr_branch(
        Path.cwd(), "reconcile/test-epic-20260811", writer=messages.append
    )
    assert result is False
    assert calls == []
    assert any("NOT deleting reconcile PR branch" in message for message in messages)
    assert any("REFERENCED" in message for message in messages)


def test_delete_reconcile_pr_branch_blocks_on_unknown_census(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupt reference store makes the census UNKNOWN and BLOCKS the
    branch deletion (fail-closed: delete-on-unknown never happens)."""
    _sandbox_census_stores(monkeypatch, tmp_path)
    store = tmp_path / "ref-chains"
    store.mkdir(parents=True)
    (store / "corrupt.json").write_text(
        '{"metadata": {"execution_environment": ', encoding="utf-8"
    )
    messages: list[str] = []
    calls: list[list[str]] = []

    def run_command(_root, argv, **_kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: _delete_compat(run_command),
    )

    result = _delete_reconcile_pr_branch(
        Path.cwd(), "reconcile/test-epic-20260811", writer=messages.append
    )
    assert result is False
    assert calls == []
    assert any("NOT deleting reconcile PR branch" in message for message in messages)
    assert any("UNKNOWN" in message for message in messages)


def test_delete_reconcile_pr_branch_proceeds_on_clear_census(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CLEAR reference census keeps the route authority: the reconcile
    branch is deleted locally and on origin exactly as before."""
    _sandbox_census_stores(monkeypatch, tmp_path)
    messages: list[str] = []
    calls: list[list[str]] = []

    def run_command(_root, argv, **_kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.git_ops._compat",
        lambda: _delete_compat(run_command),
    )

    assert _delete_reconcile_pr_branch(
        Path.cwd(), "reconcile/test-epic-20260811", writer=messages.append
    )
    assert calls[0] == ["git", "branch", "-D", "reconcile/test-epic-20260811"]
    assert calls[1] == ["git", "push", "origin", "--delete", "reconcile/test-epic-20260811"]
    assert any("deleted reconcile PR branch" in message for message in messages)


def _git(
    repo: Path,
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=env,
    )
    if check:
        assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc


def _commit(
    repo: Path,
    path: str,
    content: str,
    message: str,
    *,
    committer_date: str | None = None,
) -> str:
    full = repo / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    env = None
    if committer_date is not None:
        # Backdate so a cherry-picked twin can never share the commit
        # metadata (identical tree/parent/message plus a same-second
        # committer timestamp would otherwise reproduce the SAME sha).
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = committer_date
        env["GIT_COMMITTER_DATE"] = committer_date
    _git(repo, "commit", "-m", message, env=env)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _init_repo_with_origin(tmp_path: Path) -> None:
    """Local repo with a bare origin so reachability is verifiable."""
    _init_repo(tmp_path)
    origin = tmp_path.parent / f"{tmp_path.name}-origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=False)
    _git(tmp_path, "remote", "add", "origin", str(origin))
    _git(tmp_path, "push", "-q", "-u", "origin", "main")
    _git(tmp_path, "checkout", "-q", "-b", "reconcile/test-epic-20260811")
    _git(tmp_path, "push", "-q", "-u", "origin", "reconcile/test-epic-20260811")
    _git(tmp_path, "checkout", "-q", "main")


# ── _cherry_pick_reconcile_selection (controller-side validation) ────────


def test_cherry_pick_reconcile_selection_applies_engine_commits(
    tmp_path: Path,
) -> None:
    _init_repo_with_origin(tmp_path)
    engine_sha = _commit(
        tmp_path,
        "arnold_pipelines/engine.py",
        "def run():\n    pass\n",
        "feat(engine): add run",
        # Backdated so the cherry-picked twin (committer date = now) can
        # never reproduce the identical commit SHA within the same second.
        committer_date="2020-01-01T00:00:00Z",
    )
    doc_sha = _commit(tmp_path, "docs/note.md", "note\n", "docs: note")
    _git(tmp_path, "push", "-q", "origin", "main")

    milestone = _reconcile_milestone()
    messages: list[str] = []
    head = git_ops._cherry_pick_reconcile_selection(
        tmp_path,
        milestone,
        base_branch="main",
        selected_shas=[engine_sha, doc_sha],
        writer=messages.append,
    )

    assert head != engine_sha
    assert head == _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert (tmp_path / "arnold_pipelines" / "engine.py").exists()
    # doc_sha touches no engine source -> excluded, so docs/note.md is absent.
    assert not (tmp_path / "docs" / "note.md").exists()
    assert any("excluding chain-control commit" in message for message in messages)


def test_cherry_pick_reconcile_selection_rejects_unreachable_commit(
    tmp_path: Path,
) -> None:
    _init_repo_with_origin(tmp_path)
    _git(tmp_path, "checkout", "-q", "-b", "side-branch")
    side_sha = _commit(
        tmp_path, "arnold_pipelines/side.py", "x\n", "feat(engine): side work"
    )
    _git(tmp_path, "checkout", "-q", "main")

    milestone = _reconcile_milestone()
    messages: list[str] = []
    with pytest.raises(CliError) as excinfo:
        git_ops._cherry_pick_reconcile_selection(
            tmp_path,
            milestone,
            base_branch="main",
            selected_shas=[side_sha],
            writer=messages.append,
        )
    assert excinfo.value.code == "reconcile_unreachable_commit"


def test_cherry_pick_reconcile_selection_unresolvable_target_fails_closed(
    tmp_path: Path,
) -> None:
    # No origin at all: reachability cannot be verified, so the controller
    # must fail closed rather than cherry-pick unchecked.
    _init_repo(tmp_path)
    engine_sha = _commit(
        tmp_path, "arnold_pipelines/engine.py", "x\n", "feat(engine): work"
    )
    milestone = _reconcile_milestone()
    messages: list[str] = []
    with pytest.raises(CliError) as excinfo:
        git_ops._cherry_pick_reconcile_selection(
            tmp_path,
            milestone,
            base_branch="main",
            selected_shas=[engine_sha],
            writer=messages.append,
        )
    assert excinfo.value.code == "reconcile_target_unresolvable"


def test_cherry_pick_reconcile_selection_conflict_fails_closed(
    tmp_path: Path,
) -> None:
    _init_repo_with_origin(tmp_path)
    _git(tmp_path, "checkout", "-q", "reconcile/test-epic-20260811")
    _commit(tmp_path, "arnold_pipelines/engine.py", "branch version\n", "branch work")
    _git(tmp_path, "push", "-q", "origin", "reconcile/test-epic-20260811")
    _git(tmp_path, "checkout", "-q", "main")
    engine_sha = _commit(
        tmp_path, "arnold_pipelines/engine.py", "main version\n", "feat(engine): main work"
    )
    _git(tmp_path, "push", "-q", "origin", "main")

    milestone = _reconcile_milestone()
    messages: list[str] = []
    with pytest.raises(CliError) as excinfo:
        git_ops._cherry_pick_reconcile_selection(
            tmp_path,
            milestone,
            base_branch="main",
            selected_shas=[engine_sha],
            writer=messages.append,
        )
    assert excinfo.value.code == "reconcile_cherry_pick_failed"
    # The in-progress cherry-pick must be aborted (clean tree, no CHERRY_PICK_HEAD).
    assert not (tmp_path / ".git" / "CHERRY_PICK_HEAD").exists()
    assert _git(tmp_path, "status", "--porcelain").stdout.strip() == ""


# ── _publish_reconcile_selection (controller orchestration) ──────────────


def _batch_artifact_with_selection(plan_dir: Path) -> Path:
    artifact = plan_dir / "execution_batch_1.json"
    artifact.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "output": {
                            "selected_shas": ["a" * 40, "b" * 40],
                            "verification_evidence": {
                                "reachability_checked": True,
                                "all_selected_reachable_from_target": True,
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return artifact


def test_publish_reconcile_selection_reads_evidence_and_creates_pr(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    spec_path = _write_reconcile_spec(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-reconcile"
    plan_dir.mkdir(parents=True)
    _batch_artifact_with_selection(plan_dir)
    spec = load_spec(spec_path)
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-reconcile",
        last_state="executed",
        completed=[],
    )
    milestone = spec.milestones[0]
    messages: list[str] = []
    pushed: list[list[str]] = []

    def fake_push(root, cmd, **kwargs):
        pushed.append(list(cmd))

    with (
        patch(
            "arnold_pipelines.megaplan.chain._cherry_pick_reconcile_selection",
            return_value="c" * 40,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._run_git_push_command",
            side_effect=fake_push,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._ensure_reconcile_pr",
            return_value=99,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._record_reconcile_pr_ready_dm_best_effort",
        ),
    ):
        reason = chain_module._publish_reconcile_selection(
            tmp_path,
            spec_path,
            spec,
            state,
            milestone,
            plan_dir=plan_dir,
            writer=messages.append,
            log=messages.append,
        )

    assert reason is None
    assert state.pr_number == 99
    assert state.pr_state == "open"
    assert state.metadata["reconcile_target"]["branch"] == "main"
    assert pushed == [["git", "push", "origin", "reconcile/test-epic-20260811"]]
    assert any("reconcile PR #99 opened" in message for message in messages)


def test_publish_reconcile_selection_no_evidence_fails_closed(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    spec_path = _write_reconcile_spec(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-reconcile"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"tasks": [{"id": "T1", "status": "done", "output": {"files_changed": []}}]}),
        encoding="utf-8",
    )
    spec = load_spec(spec_path)
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-reconcile",
        last_state="executed",
        completed=[],
    )
    milestone = spec.milestones[0]
    messages: list[str] = []

    reason = chain_module._publish_reconcile_selection(
        tmp_path,
        spec_path,
        spec,
        state,
        milestone,
        plan_dir=plan_dir,
        writer=messages.append,
        log=messages.append,
    )

    assert reason is not None
    assert "no selected_shas found" in reason
    assert state.pr_number is None


def test_publish_reconcile_selection_interrupted_on_pr_create_fails_closed(
    tmp_path: Path,
) -> None:
    """Publication interrupted AFTER the reconcile branch push: ``gh pr
    create`` fails (auth). The controller must fail closed — the push
    already happened, but no open-PR state may be recorded, the persisted PR
    identity stays absent, and the reconcile branch is never deleted
    (interrupted publication is not a terminal merged/rejected outcome)."""
    _init_repo(tmp_path)
    spec_path = _write_reconcile_spec(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-reconcile"
    plan_dir.mkdir(parents=True)
    _batch_artifact_with_selection(plan_dir)
    spec = load_spec(spec_path)
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-reconcile",
        last_state="executed",
        completed=[],
    )
    milestone = spec.milestones[0]
    save_chain_state(spec_path, state)
    messages: list[str] = []
    pushed: list[list[str]] = []
    delete_calls: list[list[str]] = []

    def fake_push(root, cmd, **kwargs):
        pushed.append(list(cmd))

    def fail_pr_create(*_args, **_kwargs):
        raise CliError(
            "gh_reconcile_pr_create_failed",
            "gh pr create failed",
            extra={"stderr": "HTTP 401: authentication failed (Bad credentials)"},
        )

    def fake_delete(root, branch, *, writer):
        delete_calls.append([str(root), branch])

    with (
        patch(
            "arnold_pipelines.megaplan.chain._cherry_pick_reconcile_selection",
            return_value="c" * 40,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._run_git_push_command",
            side_effect=fake_push,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._ensure_reconcile_pr",
            side_effect=fail_pr_create,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._delete_reconcile_pr_branch",
            side_effect=fake_delete,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._record_reconcile_pr_ready_dm_best_effort",
        ),
    ):
        with pytest.raises(CliError) as excinfo:
            chain_module._publish_reconcile_selection(
                tmp_path,
                spec_path,
                spec,
                state,
                milestone,
                plan_dir=plan_dir,
                writer=messages.append,
                log=messages.append,
            )

    assert excinfo.value.code == "gh_reconcile_pr_create_failed"
    # The reconcile branch was pushed (publication interrupted mid-flight)...
    assert pushed == [["git", "push", "origin", "reconcile/test-epic-20260811"]]
    # ...but nothing is recorded as published and nothing is deleted.
    assert state.pr_number is None
    assert state.pr_state is None
    assert "reconcile_outcome" not in state.metadata
    assert delete_calls == []
    saved = chain_module.load_chain_state(spec_path)
    assert saved.pr_number is None
    assert saved.pr_state is None
    assert saved.completed == []


def test_publish_reconcile_selection_interrupted_on_push_fails_closed(
    tmp_path: Path,
) -> None:
    """Publication interrupted BEFORE the branch push: ``git push`` fails.
    The reconcile branch was never published, so PR creation must never be
    attempted and no publication state may be recorded; the failure
    propagates (fail-closed)."""
    _init_repo(tmp_path)
    spec_path = _write_reconcile_spec(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-reconcile"
    plan_dir.mkdir(parents=True)
    _batch_artifact_with_selection(plan_dir)
    spec = load_spec(spec_path)
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-reconcile",
        last_state="executed",
        completed=[],
    )
    milestone = spec.milestones[0]
    messages: list[str] = []
    pr_create_calls: list[list[str]] = []

    def fail_push(root, cmd, **kwargs):
        raise CliError(
            "git_push_reconcile_branch_failed",
            "git push origin reconcile/test-epic-20260811 exited 1",
            extra={"stderr": "fatal: unable to access: Could not resolve host"},
        )

    with (
        patch(
            "arnold_pipelines.megaplan.chain._cherry_pick_reconcile_selection",
            return_value="c" * 40,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._run_git_push_command",
            side_effect=fail_push,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._ensure_reconcile_pr",
            side_effect=lambda *_args, **_kwargs: pr_create_calls.append(_args) or 99,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._record_reconcile_pr_ready_dm_best_effort",
        ),
    ):
        with pytest.raises(CliError) as excinfo:
            chain_module._publish_reconcile_selection(
                tmp_path,
                spec_path,
                spec,
                state,
                milestone,
                plan_dir=plan_dir,
                writer=messages.append,
                log=messages.append,
            )

    assert excinfo.value.code == "git_push_reconcile_branch_failed"
    assert pr_create_calls == []  # PR creation must never be attempted
    assert state.pr_number is None
    assert state.pr_state is None


def test_publish_reconcile_selection_rerun_after_interrupt_is_idempotent(
    tmp_path: Path,
) -> None:
    """A re-run after an interrupted publication must be a no-op once the PR
    identity is persisted: no re-cherry-pick, no re-push, no re-opened PR —
    the recorded target and persisted branch identity stay untouched."""
    _init_repo(tmp_path)
    spec_path = _write_reconcile_spec(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-reconcile"
    plan_dir.mkdir(parents=True)
    _batch_artifact_with_selection(plan_dir)
    spec = load_spec(spec_path)
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-reconcile",
        last_state=STATE_AWAITING_PR_MERGE,
        pr_number=99,
        pr_state="open",
        completed=[],
    )
    milestone = spec.milestones[0]
    messages: list[str] = []

    def must_not(*_args, **_kwargs):
        raise AssertionError("re-run after interrupt must not re-publish")

    with (
        patch(
            "arnold_pipelines.megaplan.chain._cherry_pick_reconcile_selection",
            side_effect=must_not,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._run_git_push_command",
            side_effect=must_not,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._ensure_reconcile_pr",
            side_effect=must_not,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._record_reconcile_pr_ready_dm_best_effort",
            side_effect=must_not,
        ),
    ):
        reason = chain_module._publish_reconcile_selection(
            tmp_path,
            spec_path,
            spec,
            state,
            milestone,
            plan_dir=plan_dir,
            writer=messages.append,
            log=messages.append,
        )

    assert reason is None
    assert state.pr_number == 99
    assert state.pr_state == "open"



def _init_repo(repo: Path) -> None:
    repo.mkdir(exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=False)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True, check=False
    )
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True, check=False)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, capture_output=True, check=False)


def _write_reconcile_spec(root: Path) -> Path:
    idea = root / "briefs" / "reconcile.md"
    idea.parent.mkdir(parents=True, exist_ok=True)
    idea.write_text("select and publish engine commits\n", encoding="utf-8")
    north_star = root / "NORTHSTAR.md"
    north_star.write_text("north star\n", encoding="utf-8")
    spec_path = root / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: reconcile\n"
        "    kind: reconcile\n"
        "    idea: briefs/reconcile.md\n"
        "    branch: reconcile/test-epic-20260811\n"
        "    target_branch: main\n"
        "    merge_policy: review\n"
        "    phase_model: [execute=codex]\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=root, capture_output=True, check=False)
    subprocess.run(
        ["git", "commit", "-m", "track chain inputs"], cwd=root, capture_output=True, check=False
    )
    return spec_path


def _awaiting_state(*, pr_state: str = "open", pr_number: int = 77) -> ChainState:
    return ChainState(
        current_milestone_index=0,
        current_plan_name="plan-reconcile",
        last_state=STATE_AWAITING_PR_MERGE,
        pr_number=pr_number,
        pr_state=pr_state,
        completed=[],
    )


def _run_awaiting_tick(tmp_path: Path, pr_states, extra_patches=None):
    _init_repo(tmp_path)
    spec_path = _write_reconcile_spec(tmp_path)
    save_chain_state(spec_path, _awaiting_state())
    messages: list[str] = []

    patches = [
        patch(
            "arnold_pipelines.megaplan.chain._reconcile_chain_from_ground_truth",
            side_effect=lambda _root, _spec_path, _spec, state, **_kwargs: state,
        ),
        patch("arnold_pipelines.megaplan.chain._pr_state", side_effect=pr_states),
        patch("arnold_pipelines.megaplan.chain._mark_plan_completed_by_chain"),
        patch("arnold_pipelines.megaplan.chain._delete_reconcile_pr_branch"),
        patch(
            "arnold_pipelines.megaplan.chain._append_completed_with_guard",
            side_effect=lambda _root, state, record, **kwargs: (
                state.completed.append(dict(record)) or (True, "accepted")
            ),
        ),
    ]
    if extra_patches:
        patches.extend(extra_patches)
    from contextlib import ExitStack

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = run_chain(spec_path, tmp_path, writer=messages.append, mode="execute")
    return result, spec_path, messages


def test_reconcile_await_merge_rejected_records_and_proceeds_to_close(
    tmp_path: Path,
) -> None:
    delete_calls: list[list[str]] = []

    def fake_delete(root, branch, *, writer):
        delete_calls.append([str(root), branch])

    result, spec_path, messages = _run_awaiting_tick(
        tmp_path,
        ["closed", "closed"],
        extra_patches=[
            patch(
                "arnold_pipelines.megaplan.chain._delete_reconcile_pr_branch",
                side_effect=fake_delete,
            )
        ],
    )

    saved = chain_module.load_chain_state(spec_path)
    assert result["status"] == "done"
    assert saved.current_milestone_index == 1
    assert saved.pr_number is None
    assert saved.pr_state is None
    assert saved.metadata["reconcile_outcome"]["outcome"] == "rejected"
    assert saved.metadata["reconcile_outcome"]["reason"].startswith(
        "reconcile PR #77 was closed without merging"
    )
    assert len(saved.completed) == 1
    record = saved.completed[0]
    assert record["label"] == "reconcile"
    assert record["status"] == "rejected"
    assert record["pr_number"] == 77
    assert record["pr_state"] == "closed"
    assert record["kind"] == "reconcile"
    assert record["target_branch"] == "main"
    assert "rejection_reason" in record
    assert delete_calls and delete_calls[0][1] == "reconcile/test-epic-20260811"
    assert not any("stopping chain" in message for message in messages)
    assert not any("pr_closed" in message for message in messages)


def test_reconcile_await_merge_open_keeps_parked(tmp_path: Path) -> None:
    delete_calls: list[list[str]] = []

    def fake_delete(root, branch, *, writer):
        delete_calls.append([str(root), branch])

    result, spec_path, messages = _run_awaiting_tick(
        tmp_path,
        ["open", "open"],
        extra_patches=[
            patch(
                "arnold_pipelines.megaplan.chain._delete_reconcile_pr_branch",
                side_effect=fake_delete,
            )
        ],
    )

    saved = chain_module.load_chain_state(spec_path)
    assert result["status"] == STATE_AWAITING_PR_MERGE
    assert saved.pr_number == 77
    assert saved.last_state == STATE_AWAITING_PR_MERGE
    assert saved.completed == []
    assert delete_calls == []
    assert any("awaiting human review/merge" in message for message in messages)


def test_reconcile_await_merge_auth_failure_blocks_without_delete(
    tmp_path: Path,
) -> None:
    """A gh auth failure while polling an open reconcile PR must fail closed:
    the persisted PR identity is preserved, the chain never advances to
    close, and the reconcile branch is never deleted (an auth failure is not
    a rejection — only merged/rejected are branch-delete eligible)."""
    delete_calls: list[list[str]] = []

    def fake_delete(root, branch, *, writer):
        delete_calls.append([str(root), branch])

    auth_error = CliError(
        "gh_pr_view_failed",
        "gh pr view 77 failed",
        extra={"stderr": "HTTP 401: authentication failed (Bad credentials)"},
    )
    with pytest.raises(CliError) as excinfo:
        _run_awaiting_tick(
            tmp_path,
            [auth_error, auth_error],
            extra_patches=[
                patch(
                    "arnold_pipelines.megaplan.chain._delete_reconcile_pr_branch",
                    side_effect=fake_delete,
                )
            ],
        )
    assert excinfo.value.code == "gh_pr_view_failed"
    assert "authentication" in (excinfo.value.extra.get("stderr") or "")

    saved = chain_module.load_chain_state(tmp_path / "chain.yaml")
    assert saved.pr_number == 77
    assert saved.last_state == STATE_AWAITING_PR_MERGE
    assert saved.completed == []
    assert delete_calls == []


def test_reconcile_await_merge_indeterminate_state_blocks_without_delete(
    tmp_path: Path,
) -> None:
    """gh returning no usable PR state is an unknown — never a rejection: the
    chain stays parked at awaiting_pr_merge with the PR identity intact and
    the reconcile branch untouched."""
    delete_calls: list[list[str]] = []

    def fake_delete(root, branch, *, writer):
        delete_calls.append([str(root), branch])

    indeterminate_error = CliError(
        "gh_pr_view_failed",
        "gh pr view did not return a string state",
        extra={"stderr": '{"data": {"repository": {"pullRequest": {"state": null}}}}'},
    )
    with pytest.raises(CliError) as excinfo:
        _run_awaiting_tick(
            tmp_path,
            [indeterminate_error, indeterminate_error],
            extra_patches=[
                patch(
                    "arnold_pipelines.megaplan.chain._delete_reconcile_pr_branch",
                    side_effect=fake_delete,
                )
            ],
        )
    assert excinfo.value.code == "gh_pr_view_failed"

    saved = chain_module.load_chain_state(tmp_path / "chain.yaml")
    assert saved.pr_number == 77
    assert saved.last_state == STATE_AWAITING_PR_MERGE
    assert saved.completed == []
    assert delete_calls == []


def test_reconcile_await_merge_unrecognized_state_parks_without_delete(
    tmp_path: Path,
) -> None:
    """A PR state the controller does not recognize (``unknown``) keeps the
    chain parked: it is neither merged (advance) nor an intentional closed
    rejection (record + close), so no branch deletion may occur."""
    delete_calls: list[list[str]] = []

    def fake_delete(root, branch, *, writer):
        delete_calls.append([str(root), branch])

    result, spec_path, messages = _run_awaiting_tick(
        tmp_path,
        ["unknown", "unknown"],
        extra_patches=[
            patch(
                "arnold_pipelines.megaplan.chain._delete_reconcile_pr_branch",
                side_effect=fake_delete,
            )
        ],
    )

    saved = chain_module.load_chain_state(spec_path)
    assert result["status"] == STATE_AWAITING_PR_MERGE
    assert saved.pr_number == 77
    assert saved.pr_state == "unknown"
    assert saved.last_state == STATE_AWAITING_PR_MERGE
    assert saved.completed == []
    assert delete_calls == []
    assert any("awaiting human review/merge" in message for message in messages)


def test_reconcile_await_merge_merged_advances_and_deletes_branch(
    tmp_path: Path,
) -> None:
    delete_calls: list[list[str]] = []

    def fake_delete(root, branch, *, writer):
        delete_calls.append([str(root), branch])

    def fake_guard(root, state, record, **kwargs):
        assert record.get("kind") == "reconcile"
        assert record.get("target_branch") == "main"
        assert record.get("pr_state") == "merged"
        state.completed.append(dict(record))
        return (True, "merged reconcile accepted")

    result, spec_path, messages = _run_awaiting_tick(
        tmp_path,
        ["merged", "merged"],
        extra_patches=[
            patch(
                "arnold_pipelines.megaplan.chain._plan_state_payload_from_name",
                return_value={"current_state": "done"},
            ),
            patch(
                "arnold_pipelines.megaplan.chain._ensure_published_claimed_changes_for_pr_progression",
                return_value=(True, "ok"),
            ),
            patch(
                "arnold_pipelines.megaplan.chain._run_milestone_validations_blocking",
                return_value=None,
            ),
            patch(
                "arnold_pipelines.megaplan.chain._finalize_validation_artifacts_after_done_append",
                return_value=None,
            ),
            patch(
                "arnold_pipelines.megaplan.chain._delete_reconcile_pr_branch",
                side_effect=fake_delete,
            ),
            patch(
                "arnold_pipelines.megaplan.chain._append_completed_with_guard",
                side_effect=fake_guard,
            ),
        ],
    )

    saved = chain_module.load_chain_state(spec_path)
    assert result["status"] == "done"
    assert saved.current_milestone_index == 1
    assert saved.pr_number is None
    assert saved.metadata["reconcile_outcome"]["outcome"] == "merged"
    assert len(saved.completed) == 1
    assert saved.completed[0]["pr_state"] == "merged"
    assert saved.completed[0]["kind"] == "reconcile"
    assert delete_calls and delete_calls[0][1] == "reconcile/test-epic-20260811"
    assert any("merged" in message for message in messages)
