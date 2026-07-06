from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock
from unittest.mock import patch

import arnold_pipelines.megaplan.chain as chain_module
from arnold_pipelines.megaplan.chain import (
    _append_completed_with_guard,
    _chain_completion_guard,
    _handle_completion_guard_failure,
    _mark_plan_completed_by_chain,
    load_chain_state,
    run_chain,
    save_chain_state,
)
from arnold_pipelines.megaplan.chain.spec import ChainSpec, ChainState, load_spec
from arnold_pipelines.megaplan.planning.state import STATE_AWAITING_PR_MERGE


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc.stdout.strip()


def _init_repo(root: Path) -> str:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('base')\n", encoding="utf-8")
    _git(root, "add", "README.md", "src/app.py")
    _git(root, "commit", "-m", "base")
    return _git(root, "rev-parse", "HEAD")


def _commit_semantic_change(root: Path) -> str:
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "app.py").write_text("print('done')\n", encoding="utf-8")
    _git(root, "add", "src/app.py")
    _git(root, "commit", "-m", "semantic change")
    return _git(root, "rev-parse", "HEAD")


def _commit_published_megaplan_only_change(
    root: Path, base_sha: str, *, branch: str, return_to: str
) -> str:
    _git(root, "checkout", "-b", branch, base_sha)
    (root / ".megaplan").mkdir(exist_ok=True)
    (root / ".megaplan" / f"{branch}.json").write_text(
        json.dumps({"published": branch}) + "\n",
        encoding="utf-8",
    )
    _git(root, "add", ".megaplan")
    _git(root, "commit", "-m", f"{branch} megaplan artifacts")
    sha = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", return_to)
    return sha


def _commit_published_semantic_change(
    root: Path, base_sha: str, *, branch: str, return_to: str
) -> str:
    _git(root, "checkout", "-b", branch, base_sha)
    (root / "src" / "app.py").write_text("print('published')\n", encoding="utf-8")
    _git(root, "add", "src/app.py")
    _git(root, "commit", "-m", f"{branch} semantic change")
    sha = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", return_to)
    return sha


def _write_plan(
    root: Path,
    *,
    current_state: str = "done",
    base_sha: str | None = None,
    finalize_tasks: list[dict[str, object]] | None = None,
    execution_batch: bool = True,
    waiver: bool = False,
    latest_failure: dict[str, object] | None = None,
) -> Path:
    plan_dir = root / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state: dict[str, object] = {"name": "plan-m1", "current_state": current_state}
    if latest_failure is not None:
        state["latest_failure"] = latest_failure
    if base_sha is not None:
        state["meta"] = {"chain_policy": {"milestone_base_sha": base_sha}}
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    if finalize_tasks is not None:
        (plan_dir / "finalize_output.json").write_text(
            json.dumps({"tasks": finalize_tasks}) + "\n",
            encoding="utf-8",
        )
    if execution_batch:
        (plan_dir / "execution_batch_1.json").write_text(
            json.dumps(
                {
                    "task_updates": [
                        {
                            "task_id": "T1",
                            "status": "done",
                            "files_changed": ["src/app.py"],
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if waiver:
        (plan_dir / "completion_noop.json").write_text(
            json.dumps(
                {
                    "schema": "megaplan.noop_completion",
                    "plan": "plan-m1",
                    "milestone_label": "m1",
                    "reason": "base already contains this milestone",
                    "scope": "already_satisfied_by_base",
                    "base_sha": base_sha or _git(root, "rev-parse", "HEAD"),
                }
            )
            + "\n",
            encoding="utf-8",
        )
    return plan_dir


def _write_execute_authority_plan(root: Path, *, base_sha: str) -> Path:
    plan_dir = root / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": "plan-m1",
        "current_state": "blocked",
        "config": {"project_dir": str(root)},
        "meta": {"execution_baseline": {"head": base_sha}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "t6_add_focused_api_regressions",
                        "status": "done",
                        "kind": "code",
                        "commands_run": [
                            "pytest -q tests/arnold/workflow/test_source_compiler_api.py -q"
                        ],
                    },
                    {
                        "id": "v3_api_tests",
                        "status": "pending",
                        "kind": "test",
                        "commands_run": [
                            "pytest -q tests/arnold/workflow/test_source_compiler_api.py -q"
                        ],
                        "head_sha": base_sha,
                    },
                    {
                        "id": "v4_optional_diagnostics_contract",
                        "status": "skipped",
                        "kind": "test",
                        "executor_notes": "Skipped by contract: no diagnostic registry or keyword contract changed.",
                        "head_sha": base_sha,
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "t6_add_focused_api_regressions",
                        "status": "done",
                        "commands_run": [
                            "pytest -q tests/arnold/workflow/test_source_compiler_api.py -q"
                        ],
                        "head_sha": base_sha,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return plan_dir


def _record() -> dict[str, object]:
    return {"label": "m1", "plan": "plan-m1", "status": "done"}


def _write_chain_spec(root: Path) -> Path:
    idea = root / "idea.md"
    idea.write_text("ship milestone\n", encoding="utf-8")
    north_star = root / "NORTHSTAR.md"
    north_star.write_text("north star\n", encoding="utf-8")
    spec_path = root / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        f"    idea: {idea}\n"
        "    branch: test/m1\n",
        encoding="utf-8",
    )
    return spec_path


def _write_base_branch_chain_spec(root: Path) -> Path:
    idea = root / "idea.md"
    idea.write_text("ship milestone on base\n", encoding="utf-8")
    north_star = root / "NORTHSTAR.md"
    north_star.write_text("north star\n", encoding="utf-8")
    spec_path = root / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        f"    idea: {idea}\n",
        encoding="utf-8",
    )
    return spec_path


def test_run_chain_commits_base_branch_milestone_without_pr_branch(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_base_branch_chain_spec(tmp_path)
    _write_plan(
        tmp_path,
        current_state="done",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done"}],
    )

    def execute_produces_work(*_args, **_kwargs):
        (tmp_path / "src" / "app.py").write_text("print('execute output')\n", encoding="utf-8")
        return chain_module.DriverOutcome(
            status="done",
            plan="plan-m1",
            final_state="done",
            iterations=1,
            reason="ok",
        )

    with (
        patch("arnold_pipelines.megaplan.chain._refresh_base_branch", lambda *args, **kwargs: None),
        patch("arnold_pipelines.megaplan.chain._init_plan", return_value="plan-m1"),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            side_effect=execute_produces_work,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._plan_terminal_completion_is_authoritative",
            return_value=(True, "ok"),
        ),
        patch(
            "arnold_pipelines.megaplan.chain._shadow_milestone_completion_verdict",
            return_value=False,
        ),
        patch("arnold_pipelines.megaplan.chain._commit_and_push_phase") as commit_and_push,
    ):
        result = run_chain(spec_path, tmp_path, writer=lambda _msg: None, mode="execute")

    head = _git(tmp_path, "rev-parse", "HEAD")
    assert result["status"] == "done"
    assert head != base
    assert int(_git(tmp_path, "rev-list", "--count", f"{base}..HEAD")) == 1
    assert "src/app.py" not in _git(tmp_path, "status", "--porcelain")
    assert "src/app.py" in _git(tmp_path, "diff", "--name-only", f"{base}..HEAD")
    saved = load_chain_state(spec_path)
    assert saved.completed[-1]["local_commit_sha"] == head
    commit_and_push.assert_not_called()


def test_non_terminal_gated_plan_cannot_complete_from_pr_merge_alone(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(
        tmp_path, current_state="gated", base_sha=base, finalize_tasks=[{"id": "T1"}]
    )

    state = ChainState()
    appended, reason = _append_completed_with_guard(
        tmp_path,
        state,
        {**_record(), "pr_state": "merged"},
        implementation_milestone=True,
        writer=lambda _msg: None,
    )

    assert appended is False
    assert state.completed == []
    assert state.last_state == "authority_divergence"
    assert "current_state='gated'" in reason


def test_run_chain_pr_merge_resume_blocks_non_terminal_plan(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _write_plan(
        tmp_path,
        current_state="gated",
        finalize_tasks=[],
        execution_batch=False,
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state=STATE_AWAITING_PR_MERGE,
            pr_number=99,
            pr_state="awaiting_merge",
        ),
    )

    with (
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="merged"),
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            mode="execute",
        )

    saved = load_chain_state(spec_path)
    assert result["status"] == "blocked"
    assert saved.completed == []
    assert saved.current_milestone_index == 0
    assert saved.current_plan_name == "plan-m1"
    assert saved.last_state == "authority_divergence"
    assert "current_state='gated'" in result["reason"]


def test_stale_merged_pr_recovery_accepts_failed_no_next_step_blocked_execute(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _git(tmp_path, "add", "chain.yaml", "idea.md", "NORTHSTAR.md")
    _git(tmp_path, "commit", "-m", "track chain inputs")
    head = _commit_semantic_change(tmp_path)
    spec = load_spec(spec_path)
    milestone = spec.milestones[0]
    plan_dir = _write_plan(
        tmp_path,
        current_state="failed",
        base_sha=base,
        finalize_tasks=[
            {
                "id": "T1",
                "status": "done",
                "kind": "code",
                "files_changed": ["src/app.py"],
                "head_sha": head,
            },
            {
                "id": "T2",
                "status": "skipped",
                "kind": "test",
                "reviewer_verdict": "deferred_baseline_unavailable",
                "executor_notes": (
                    "Deferred by harness: baseline_test_failures is null, so this "
                    "no-new-failures checkpoint cannot compare against a recorded baseline."
                ),
            },
        ],
        execution_batch=False,
        latest_failure={
            "kind": "no_next_step",
            "message": "no next_step and no override available",
        },
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "plan-m1",
                "current_state": "failed",
                "config": {"project_dir": str(tmp_path)},
                "meta": {
                    "chain_policy": {"milestone_base_sha": base},
                    "execution_baseline": {"head": base},
                },
                "history": [{"step": "execute", "result": "blocked"}],
                "latest_failure": {
                    "kind": "no_next_step",
                    "message": "no next_step and no override available",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_failures": None,
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "code",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    },
                    {
                        "id": "T2",
                        "status": "skipped",
                        "kind": "test",
                        "reviewer_verdict": "deferred_baseline_unavailable",
                        "executor_notes": (
                            "Deferred by harness: baseline_test_failures is null, "
                            "so this no-new-failures checkpoint cannot compare "
                            "against a recorded baseline."
                        ),
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state=STATE_AWAITING_PR_MERGE,
            pr_number=99,
            pr_state="awaiting_merge",
        ),
    )
    state = load_chain_state(spec_path)

    recovered_state, reason = chain_module._recover_stale_merged_pr_for_unfinished_plan(
        tmp_path,
        spec_path,
        state,
        milestone,
        json.loads((plan_dir / "state.json").read_text(encoding="utf-8")),
        writer=lambda _msg: None,
    )

    assert recovered_state is not None
    assert "cleared stale PR cursor" in reason
    assert recovered_state.last_state == "executed"
    assert recovered_state.pr_number is None
    assert recovered_state.pr_state is None
    assert recovered_state.metadata["stale_merged_pr_recovery"]["plan_current_state"] == "failed"
    assert (
        recovered_state.metadata["stale_merged_pr_recovery"]["canonical_plan_current_state"]
        == "executed"
    )


def test_run_chain_stops_when_resumed_pr_is_closed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _write_plan(
        tmp_path,
        current_state="gated",
        finalize_tasks=[],
        execution_batch=False,
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state=STATE_AWAITING_PR_MERGE,
            pr_number=99,
            pr_state="awaiting_merge",
        ),
    )

    with (
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="closed"),
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            mode="execute",
        )

    saved = load_chain_state(spec_path)
    assert result["status"] == "stopped"
    assert result["reason"] == "milestone m1 PR #99 is closed"
    assert saved.pr_state == "closed"
    assert saved.last_state == "pr_closed"


def test_run_chain_publishes_claimed_changes_before_auto_merge(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _git(tmp_path, "add", "chain.yaml", "idea.md", "NORTHSTAR.md")
    _git(tmp_path, "commit", "-m", "track chain inputs")
    plan_dir = _write_plan(
        tmp_path,
        current_state="finalized",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}],
        execution_batch=False,
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {"tasks": [{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}]}
        )
        + "\n",
        encoding="utf-8",
    )
    _git(tmp_path, "checkout", "-b", "test/m1")
    (tmp_path / "src" / "app.py").write_text("print('resume publish')\n", encoding="utf-8")
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state=STATE_AWAITING_PR_MERGE,
            pr_number=122,
            pr_state="open",
        ),
    )

    def fake_commit_and_push(
        root: Path,
        branch: str,
        plan: str,
        phase: str,
        *,
        writer,
        preexisting_dirty_paths: list[Path] | None = None,
    ) -> None:
        assert branch == "test/m1"
        assert plan == "plan-m1"
        assert phase == "resume-publish"
        _git(root, "add", "src/app.py")
        _git(root, "commit", "-m", "resume publish")

    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._capture_sync_state"),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="open"),
        patch("arnold_pipelines.megaplan.chain._mark_pr_ready"),
        patch("arnold_pipelines.megaplan.chain._enable_auto_merge", return_value="open"),
        patch(
            "arnold_pipelines.megaplan.chain._commit_and_push_phase",
            side_effect=fake_commit_and_push,
        ) as commit_and_push,
        patch("arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery") as drive,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            mode="execute",
        )

    drive.assert_not_called()
    commit_and_push.assert_called_once()
    assert result["status"] == STATE_AWAITING_PR_MERGE
    assert "src/app.py" not in _git(tmp_path, "status", "--porcelain")


def test_run_chain_recovers_merged_pr_with_unfinished_claimed_changes(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _git(tmp_path, "add", "chain.yaml", "idea.md", "NORTHSTAR.md")
    _git(tmp_path, "commit", "-m", "track chain inputs")
    plan_dir = _write_plan(
        tmp_path,
        current_state="finalized",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}],
        execution_batch=False,
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {"tasks": [{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}]}
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text("print('local only')\n", encoding="utf-8")
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="authority_divergence",
            pr_number=122,
            pr_state="merged",
        ),
    )

    def fake_commit_and_push(
        root: Path,
        branch: str,
        plan: str,
        phase: str,
        *,
        writer,
        preexisting_dirty_paths: list[Path] | None = None,
    ) -> None:
        assert branch == "test/m1"
        assert plan == "plan-m1"
        assert phase == "stale-merged-pr-recovery"
        _git(root, "add", "src/app.py")
        _git(root, "commit", "-m", "recover stale merged pr")

    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="merged"),
        patch("arnold_pipelines.megaplan.chain._plan_state", return_value="finalized"),
        patch(
            "arnold_pipelines.megaplan.chain._commit_and_push_phase",
            side_effect=fake_commit_and_push,
        ) as commit_and_push,
        patch("arnold_pipelines.megaplan.chain._checkout_milestone_branch"),
        patch("arnold_pipelines.megaplan.chain._capture_sync_state"),
        patch("arnold_pipelines.megaplan.chain._ensure_milestone_pr", return_value=123),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            return_value=chain_module.DriverOutcome(
                status="finalized",
                plan="plan-m1",
                final_state="finalized",
                iterations=1,
                reason="still executing",
            ),
        ) as drive,
        patch("arnold_pipelines.megaplan.chain._run_milestone_validations_blocking") as validate,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            mode="execute",
        )

    validate.assert_not_called()
    commit_and_push.assert_called_once()
    drive.assert_called_once()
    saved = load_chain_state(spec_path)
    assert result["status"] == "stopped"
    assert saved.pr_number == 123
    assert saved.pr_state == "open"
    assert saved.metadata["stale_merged_pr_recovery"]["stale_pr_number"] == 122
    assert "src/app.py" not in _git(tmp_path, "status", "--porcelain")


def test_run_chain_logs_stale_merged_pr_recovery_for_unfinished_plan(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _git(tmp_path, "add", "chain.yaml", "idea.md", "NORTHSTAR.md")
    _git(tmp_path, "commit", "-m", "track chain inputs")
    plan_dir = _write_plan(
        tmp_path,
        current_state="finalized",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}],
        execution_batch=False,
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {"tasks": [{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}]}
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text("print('local only')\n", encoding="utf-8")
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="authority_divergence",
            pr_number=122,
            pr_state="merged",
        ),
    )
    messages: list[str] = []

    def fake_commit_and_push(
        root: Path,
        branch: str,
        plan: str,
        phase: str,
        *,
        writer,
        preexisting_dirty_paths: list[Path] | None = None,
    ) -> None:
        _git(root, "add", "src/app.py")
        _git(root, "commit", "-m", "recover stale merged pr")

    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="merged"),
        patch("arnold_pipelines.megaplan.chain._plan_state", return_value="finalized"),
        patch(
            "arnold_pipelines.megaplan.chain._commit_and_push_phase",
            side_effect=fake_commit_and_push,
        ),
        patch("arnold_pipelines.megaplan.chain._checkout_milestone_branch"),
        patch("arnold_pipelines.megaplan.chain._capture_sync_state"),
        patch("arnold_pipelines.megaplan.chain._ensure_milestone_pr", return_value=123),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            return_value=chain_module.DriverOutcome(
                status="finalized",
                plan="plan-m1",
                final_state="finalized",
                iterations=1,
                reason="still executing",
            ),
        ),
        patch("arnold_pipelines.megaplan.chain._run_milestone_validations_blocking") as validate,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=messages.append,
            mode="execute",
        )

    validate.assert_not_called()
    assert result["status"] == "stopped"
    assert any(
        message.startswith("[chain] recovered stale merged PR #122 for unfinished plan plan-m1; ")
        and "published 1 local change(s) to test/m1 (1 claimed, 0 unclaimed active-execute)" in message
        for message in messages
    )


def test_claimed_paths_include_execution_batch_artifacts(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    plan_dir = _write_plan(
        tmp_path,
        current_state="finalized",
        finalize_tasks=[{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}],
        execution_batch=False,
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {"tasks": [{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}]}
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "files_changed": ["src/top_level.ts"],
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "files_changed": ["src/batched.ts"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert chain_module._claimed_paths(tmp_path, "plan-m1") == {
        "src/app.py",
        "src/batched.ts",
        "src/top_level.ts",
    }


def test_run_chain_recovers_batched_untracked_execute_output_as_claimed(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _git(tmp_path, "add", "chain.yaml", "idea.md", "NORTHSTAR.md")
    _git(tmp_path, "commit", "-m", "track chain inputs")
    plan_dir = _write_plan(
        tmp_path,
        current_state="finalized",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}],
        execution_batch=False,
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {"tasks": [{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}]}
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "files_changed": ["src/newdir/new.py"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text("print('local only')\n", encoding="utf-8")
    (tmp_path / "src" / "newdir").mkdir()
    (tmp_path / "src" / "newdir" / "new.py").write_text("print('nested')\n", encoding="utf-8")
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="authority_divergence",
            pr_number=122,
            pr_state="merged",
        ),
    )

    def fake_commit_and_push(
        root: Path,
        branch: str,
        plan: str,
        phase: str,
        *,
        writer,
        preexisting_dirty_paths: list[Path] | None = None,
    ) -> None:
        assert phase == "stale-merged-pr-recovery"
        _git(root, "add", "src/app.py", "src/newdir/new.py")
        _git(root, "commit", "-m", "recover batched output")

    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="merged"),
        patch("arnold_pipelines.megaplan.chain._plan_state", return_value="finalized"),
        patch(
            "arnold_pipelines.megaplan.chain._commit_and_push_phase",
            side_effect=fake_commit_and_push,
        ) as commit_and_push,
        patch("arnold_pipelines.megaplan.chain._checkout_milestone_branch"),
        patch("arnold_pipelines.megaplan.chain._capture_sync_state"),
        patch("arnold_pipelines.megaplan.chain._ensure_milestone_pr", return_value=123),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            return_value=chain_module.DriverOutcome(
                status="finalized",
                plan="plan-m1",
                final_state="finalized",
                iterations=1,
                reason="still executing",
            ),
        ),
        patch("arnold_pipelines.megaplan.chain._run_milestone_validations_blocking") as validate,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            mode="execute",
        )

    validate.assert_not_called()
    commit_and_push.assert_called_once()
    assert result["status"] == "stopped"
    assert "src/newdir/new.py" not in _git(tmp_path, "status", "--porcelain")


def test_run_chain_blocks_stale_merged_pr_recovery_with_unrelated_dirty_paths(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _git(tmp_path, "add", "chain.yaml", "idea.md", "NORTHSTAR.md")
    _git(tmp_path, "commit", "-m", "track chain inputs")
    plan_dir = _write_plan(
        tmp_path,
        current_state="finalized",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}],
        execution_batch=False,
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {"tasks": [{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}]}
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text("print('local only')\n", encoding="utf-8")
    (tmp_path / "src" / "scratch.py").write_text("print('unclaimed')\n", encoding="utf-8")
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="authority_divergence",
            pr_number=122,
            pr_state="merged",
        ),
    )

    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="merged"),
        patch("arnold_pipelines.megaplan.chain._plan_state", return_value="finalized"),
        patch("arnold_pipelines.megaplan.chain._commit_and_push_phase") as commit_and_push,
        patch("arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery") as drive,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            mode="execute",
        )

    commit_and_push.assert_not_called()
    drive.assert_not_called()
    saved = load_chain_state(spec_path)
    assert result["status"] == "blocked"
    assert saved.last_state == "authority_divergence"
    assert "unrelated dirty paths prevent recovery" in result["reason"]
    assert "src/scratch.py" in result["reason"]


def test_run_chain_recovers_unclaimed_dirty_paths_from_active_execute(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _git(tmp_path, "add", "chain.yaml", "idea.md", "NORTHSTAR.md")
    _git(tmp_path, "commit", "-m", "track chain inputs")
    plan_dir = _write_plan(
        tmp_path,
        current_state="finalized",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}],
        execution_batch=False,
    )
    state_path = plan_dir / "state.json"
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["active_step"] = {"phase": "execute", "run_id": "worker-1"}
    state_path.write_text(json.dumps(state_payload) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {"tasks": [{"id": "T1", "status": "done", "files_changed": ["src/app.py"]}]}
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text("print('local only')\n", encoding="utf-8")
    (tmp_path / "src" / "scratch.py").write_text("print('execute partial')\n", encoding="utf-8")
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="authority_divergence",
            pr_number=122,
            pr_state="merged",
        ),
    )

    def fake_commit_and_push(
        root: Path,
        branch: str,
        plan: str,
        phase: str,
        *,
        writer,
        preexisting_dirty_paths: list[Path] | None = None,
    ) -> None:
        assert phase == "stale-merged-pr-recovery"
        _git(root, "add", "src/app.py", "src/scratch.py")
        _git(root, "commit", "-m", "recover active execute")

    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="merged"),
        patch("arnold_pipelines.megaplan.chain._plan_state", return_value="finalized"),
        patch(
            "arnold_pipelines.megaplan.chain._commit_and_push_phase",
            side_effect=fake_commit_and_push,
        ) as commit_and_push,
        patch("arnold_pipelines.megaplan.chain._checkout_milestone_branch"),
        patch("arnold_pipelines.megaplan.chain._capture_sync_state"),
        patch("arnold_pipelines.megaplan.chain._ensure_milestone_pr", return_value=123),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            return_value=chain_module.DriverOutcome(
                status="finalized",
                plan="plan-m1",
                final_state="finalized",
                iterations=1,
                reason="still executing",
            ),
        ),
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            mode="execute",
        )

    commit_and_push.assert_called_once()
    saved = load_chain_state(spec_path)
    assert result["status"] == "stopped"
    assert saved.metadata["stale_merged_pr_recovery"]["dirty_claimed_paths"] == ["src/app.py"]
    assert saved.metadata["stale_merged_pr_recovery"]["unclaimed_execute_dirty_paths"] == [
        "src/scratch.py"
    ]
    assert "src/scratch.py" not in _git(tmp_path, "status", "--porcelain")


def test_completion_guard_failure_uses_retry_ladder(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "on_failure:\n"
        "  retry: retry_milestone\n"
        "  abort: stop_chain\n"
        "milestones:\n"
        "  - label: m1\n"
        f"    idea: {tmp_path / 'idea.md'}\n",
        encoding="utf-8",
    )
    (tmp_path / "idea.md").write_text("ship milestone\n", encoding="utf-8")
    (tmp_path / "NORTHSTAR.md").write_text("north star\n", encoding="utf-8")
    _write_plan(
        tmp_path,
        current_state="done",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done"}],
    )
    state = ChainState(current_milestone_index=0, current_plan_name="plan-m1")
    spec = load_spec(spec_path)

    result = _handle_completion_guard_failure(
        root=tmp_path,
        spec_path=spec_path,
        spec=spec,
        state=state,
        milestone=spec.milestones[0],
        plan_name="plan-m1",
        outcome_status="done",
        reason="no semantic diff from milestone_base_sha to local HEAD",
        events=[],
        writer=lambda _msg: None,
    )

    saved = load_chain_state(spec_path)
    assert result["status"] == "stopped"
    assert "completion guard retrying" in result["reason"]
    assert saved.current_plan_name is None
    assert saved.last_state == "blocked"
    assert saved.retry_counts["m1"] == 1


def test_pr_merge_completion_guard_failure_uses_retry_ladder(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "on_failure:\n"
        "  retry: retry_milestone\n"
        "  abort: stop_chain\n"
        "milestones:\n"
        "  - label: m1\n"
        f"    idea: {tmp_path / 'idea.md'}\n"
        "    branch: test/m1\n",
        encoding="utf-8",
    )
    (tmp_path / "idea.md").write_text("ship milestone\n", encoding="utf-8")
    (tmp_path / "NORTHSTAR.md").write_text("north star\n", encoding="utf-8")
    _write_plan(
        tmp_path,
        current_state="done",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done"}],
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state=STATE_AWAITING_PR_MERGE,
            pr_number=62,
            pr_state="awaiting_merge",
        ),
    )

    with (
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="merged"),
        patch(
            "arnold_pipelines.megaplan.chain._append_completed_with_guard",
            return_value=(False, "no semantic diff from milestone_base_sha to local HEAD"),
        ),
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            mode="execute",
        )

    saved = load_chain_state(spec_path)
    assert result["status"] == "stopped"
    assert "completion guard retrying" in result["reason"]
    assert saved.current_plan_name is None
    assert saved.last_state == "blocked"
    assert saved.retry_counts["m1"] == 1


def test_run_chain_clears_stale_closed_pr_state_on_restart(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _write_plan(
        tmp_path,
        current_state="done",
        finalize_tasks=[{"id": "T1", "status": "done"}],
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="pr_closed",
            pr_number=99,
            pr_state="closed",
        ),
    )

    with (
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
            lambda *args, **kwargs: None,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._capture_sync_state",
            lambda *args, **kwargs: None,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._commit_and_push_phase",
            lambda *args, **kwargs: None,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._ensure_milestone_pr",
            return_value=123,
        ) as ensure_pr,
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            return_value=chain_module.DriverOutcome(
                status="done",
                plan="plan-m1",
                final_state="done",
                iterations=1,
                reason="ok",
            ),
        ),
        patch(
            "arnold_pipelines.megaplan.chain._handle_outcome",
            return_value="skip",
        ),
        patch(
            "arnold_pipelines.megaplan.chain._plan_terminal_completion_is_authoritative",
            return_value=(True, "ok"),
        ),
        patch(
            "arnold_pipelines.megaplan.chain._append_completed_with_guard",
            return_value=(True, ""),
        ),
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            mode="execute",
        )

    saved = load_chain_state(spec_path)
    assert result["status"] == "done"
    assert ensure_pr.call_count == 1
    assert saved.current_milestone_index == 1
    assert saved.pr_number is None
    assert saved.pr_state is None
    assert saved.last_state == "done"


def test_latest_execution_batch_all_tasks_done_accepts_execution_window_authority(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    plan_dir = _write_execute_authority_plan(tmp_path, base_sha=base)

    ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is True
    assert reason == "execution_batch_1.json"


def test_latest_execution_batch_all_tasks_done_uses_persisted_execute_baseline_head(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    _git(tmp_path, "checkout", "-b", "work")
    work_head = _commit_semantic_change(tmp_path)
    plan_dir = _write_execute_authority_plan(tmp_path, base_sha=work_head)

    _git(tmp_path, "checkout", "-B", "native-python-working-tree", base)

    ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is True
    assert reason == "execution_batch_1.json"


def test_latest_execution_batch_all_tasks_done_ignores_deferred_baseline_batch(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    head = _commit_semantic_change(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": "plan-m1",
        "current_state": "finalized",
        "config": {"project_dir": str(tmp_path)},
        "meta": {"execution_baseline": {"head": base}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_failures": None,
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "code",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    },
                    {
                        "id": "T2",
                        "description": (
                            "Introduce no new failures vs the recorded baseline; "
                            "do not try to make pre-existing baseline failures "
                            "pass; do not narrow to individual functions. The "
                            "harness will run the authoritative post-execute "
                            "verification — do not loop the suite."
                        ),
                        "status": "skipped",
                        "kind": "test",
                        "reviewer_verdict": "deferred_baseline_unavailable",
                        "executor_notes": (
                            "Deferred by harness: baseline_test_failures is null, "
                            "so this no-new-failures checkpoint cannot compare "
                            "against a recorded baseline."
                        ),
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_2.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "blocked",
                        "commands_run": ["pytest"],
                        "executor_notes": "Full-suite gate was deferred by the harness.",
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is True
    assert reason in {"execution_batch_2.json", "finalize.json"}


def test_latest_execution_batch_all_tasks_done_prefers_authoritative_batch_update_over_stale_finalize(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    head = _commit_semantic_change(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": "plan-m1",
        "current_state": "finalized",
        "config": {"project_dir": str(tmp_path)},
        "meta": {"execution_baseline": {"head": base}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "code",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    },
                    {
                        "id": "T2",
                        "status": "blocked",
                        "kind": "code",
                        "commands_run": ["find stale prerequisite"],
                        "executor_notes": "Stale finalize snapshot.",
                        "head_sha": base,
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_2.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "executor_notes": "Authoritative batch update.",
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is True
    assert reason in {"execution_batch_2.json", "finalize.json"}


def test_recover_blocked_execute_if_tasks_done_handles_failed_no_next_step_projection(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    head = _commit_semantic_change(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": "plan-m1",
        "current_state": "failed",
        "config": {"project_dir": str(tmp_path)},
        "meta": {"execution_baseline": {"head": base}},
        "history": [{"step": "execute", "result": "blocked"}],
        "latest_failure": {
            "kind": "no_next_step",
            "message": "no next_step and no override available",
        },
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_failures": None,
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "code",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    },
                    {
                        "id": "T2",
                        "status": "skipped",
                        "kind": "test",
                        "reviewer_verdict": "deferred_baseline_unavailable",
                        "executor_notes": (
                            "Deferred by harness: baseline_test_failures is null, "
                            "so this no-new-failures checkpoint cannot compare "
                            "against a recorded baseline."
                        ),
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    writer = mock.Mock()
    outcome = chain_module.DriverOutcome(
        plan="plan-m1",
        status="failed",
        final_state="failed",
        iterations=2,
        reason="no next_step and no override available",
        last_phase="status",
    )

    recovered = chain_module._recover_blocked_execute_if_tasks_done(
        tmp_path,
        tmp_path / "chain.yaml",
        ChainSpec(milestones=[]),
        outcome,
        writer=writer,
    )

    assert recovered is True
    saved = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert saved["current_state"] == "executed"
    assert "latest_failure" not in saved
    assert "resume_cursor" not in saved
    writer.assert_called_once()
    assert "continuing from executed state" in writer.call_args.args[0]


def test_latest_execution_batch_all_tasks_done_ignores_stale_pending_finalize_rows(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    head = _commit_semantic_change(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": "plan-m1",
        "current_state": "finalized",
        "config": {"project_dir": str(tmp_path)},
        "meta": {"execution_baseline": {"head": base}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "code",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    },
                    {
                        "id": "T2",
                        "status": "pending",
                        "kind": "test",
                        "executor_notes": "Never executed before finalize snapshot.",
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is True
    assert reason == "execution_batch_1.json"


def test_latest_execution_batch_all_tasks_done_accepts_explained_noop_finalize_rows(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    head = _commit_semantic_change(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": "plan-m1",
        "current_state": "blocked",
        "config": {"project_dir": str(tmp_path)},
        "meta": {"execution_baseline": {"head": base}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "code",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    },
                    {
                        "id": "T9",
                        "status": "done",
                        "kind": "test",
                        "executor_notes": (
                            "No code change needed. Existing progress-auditor coverage "
                            "already proves this signal."
                        ),
                        "files_changed": [],
                        "commands_run": [],
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is True
    assert reason == "finalize.json"


def test_latest_execution_batch_all_tasks_done_falls_back_to_authoritative_finalize_when_latest_batch_is_stale(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    head = _commit_semantic_change(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": "plan-m1",
        "current_state": "blocked",
        "config": {"project_dir": str(tmp_path)},
        "meta": {"execution_baseline": {"head": base}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "code",
                        "files_changed": ["src/app.py"],
                        "head_sha": head,
                    },
                    {
                        "id": "T2",
                        "status": "done",
                        "kind": "test",
                        "commands_run": ["pytest -q"],
                        "executor_notes": "Authoritative finalize snapshot.",
                        "head_sha": head,
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "commands_run": ["git diff -- src/app.py"],
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_2.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "executor_notes": "Partial checkpoint omitted corroborating outputs.",
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is True
    assert reason in {"execution_batch_2.json", "finalize.json"}


def test_latest_execution_batch_all_tasks_done_ignores_stale_pending_batch_override(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    head = _commit_semantic_change(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": "plan-m1",
        "current_state": "done",
        "config": {"project_dir": str(tmp_path)},
        "meta": {"execution_baseline": {"head": base}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T7",
                        "status": "done",
                        "kind": "test",
                        "files_changed": ["src/app.py"],
                        "commands_run": ["pytest -q"],
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T7",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "commands_run": ["pytest -q"],
                        "head_sha": head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_2.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T7",
                        "status": "pending",
                        "files_changed": [],
                        "commands_run": [],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is True
    assert reason == "finalize.json"


def test_latest_execution_batch_all_tasks_done_prefers_latest_recorded_head_over_stale_baseline(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    _git(tmp_path, "checkout", "-b", "work")
    recorded_head = _commit_semantic_change(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": "plan-m1",
        "current_state": "blocked",
        "config": {"project_dir": str(tmp_path)},
        "meta": {"execution_baseline": {"head": base}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "code",
                        "files_changed": ["src/app.py"],
                        "head_sha": recorded_head,
                    },
                    {
                        "id": "T2",
                        "status": "pending",
                        "kind": "test",
                        "commands_run": ["pytest -q tests/test_app.py"],
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                        "head_sha": recorded_head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    real_run = subprocess.run

    def _fake_run(cmd: list[str], *args: object, **kwargs: object):
        if cmd[:3] == ["git", "rev-parse", "HEAD"]:
            raise subprocess.SubprocessError("simulated rev-parse failure")
        return real_run(cmd, *args, **kwargs)

    with patch("arnold_pipelines.megaplan.chain.subprocess.run", side_effect=_fake_run):
        ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is False
    assert "T2='unsatisfied':missing_linked_evidence" in reason
    assert "T1" not in reason


def test_empty_finalize_tasks_and_no_execution_batch_blocks(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(
        tmp_path,
        base_sha=base,
        finalize_tasks=[],
        execution_batch=False,
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
    )

    assert ok is False
    assert "no execution_batch_*.json" in reason


def test_authoritative_finalize_json_overrides_empty_scratch_template(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    plan_dir = _write_plan(
        tmp_path,
        base_sha=base,
        finalize_tasks=[{"id": "T1"}],
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "kind": "code",
                        "files_changed": ["src/app.py"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize_output.json").write_text(
        json.dumps({"tasks": []}) + "\n",
        encoding="utf-8",
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
    )

    assert ok is True
    assert "finalize.json tasks is non-empty" in reason


def test_empty_semantic_diff_from_milestone_base_blocks(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
    )

    assert ok is False
    assert "no semantic diff from milestone_base_sha" in reason


def test_typed_noop_waiver_allows_empty_diff_and_empty_tasks_when_done(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    _write_plan(
        tmp_path,
        base_sha=base,
        finalize_tasks=[],
        execution_batch=False,
        waiver=True,
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
    )

    assert ok is True
    assert "typed no-op waiver accepted" in reason


def test_typed_noop_waiver_does_not_allow_non_terminal_plan(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    _write_plan(
        tmp_path,
        current_state="gated",
        base_sha=base,
        finalize_tasks=[],
        execution_batch=False,
        waiver=True,
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
    )

    assert ok is False
    assert "current_state='gated'" in reason


def test_typed_noop_waiver_must_match_plan_and_milestone(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    _write_plan(
        tmp_path,
        base_sha=base,
        finalize_tasks=[],
        execution_batch=False,
        waiver=True,
    )
    waiver_path = tmp_path / ".megaplan" / "plans" / "plan-m1" / "completion_noop.json"
    payload = json.loads(waiver_path.read_text(encoding="utf-8"))
    payload["milestone_label"] = "wrong"
    waiver_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
    )

    assert ok is False
    assert "milestone_label" in reason


def test_successful_completion_guard_passes(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
    )

    assert ok is True
    assert "completion guard passed" in reason


def test_merged_pr_completion_blocks_when_published_diff_is_megaplan_only(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    local_branch = _git(tmp_path, "branch", "--show-current")
    published_sha = _commit_published_megaplan_only_change(
        tmp_path,
        base,
        branch="published-megaplan-only",
        return_to=local_branch,
    )
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    ok, reason = _chain_completion_guard(
        tmp_path,
        {
            **_record(),
            "pr_number": 62,
            "pr_state": "merged",
            "pr_merge_sha": published_sha,
        },
        implementation_milestone=True,
    )

    assert ok is False
    assert "published PR target" in reason
    assert "no semantic diff" in reason


def test_merged_pr_completion_allows_published_semantic_diff(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    local_branch = _git(tmp_path, "branch", "--show-current")
    published_sha = _commit_published_semantic_change(
        tmp_path,
        base,
        branch="published-semantic",
        return_to=local_branch,
    )
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    ok, reason = _chain_completion_guard(
        tmp_path,
        {
            **_record(),
            "pr_number": 62,
            "pr_state": "merged",
            "pr_merge_sha": published_sha,
        },
        implementation_milestone=True,
    )

    assert ok is True
    assert "published PR target" in reason


def test_published_pr_diff_fetches_missing_remote_commit_before_blocking(
    tmp_path: Path,
) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote.git"
    other = tmp_path / "other"
    local.mkdir()
    remote.mkdir()
    _git(remote, "init", "--bare")
    base = _init_repo(local)
    _git(local, "branch", "-M", "main")
    _git(local, "remote", "add", "origin", str(remote))
    _git(local, "push", "-u", "origin", "main")
    _git(tmp_path, "clone", str(remote), str(other))
    _git(other, "config", "user.email", "test@example.com")
    _git(other, "config", "user.name", "Test User")
    (other / "src" / "app.py").write_text("print('remote done')\n", encoding="utf-8")
    _git(other, "add", "src/app.py")
    _git(other, "commit", "-m", "remote semantic change")
    target = _git(other, "rev-parse", "HEAD")
    _git(other, "push", "origin", "main")

    missing = subprocess.run(
        ["git", "cat-file", "-t", target],
        cwd=local,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode != 0

    ok, reason = chain_module._semantic_diff_nonempty_between_refs(
        local,
        base,
        target,
        target_label=f"published PR target {target[:12]}",
    )

    assert ok is True
    assert "published PR target" in reason


def test_merged_pr_completion_allows_authoritative_true_noop_diff(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    ok, reason = _chain_completion_guard(
        tmp_path,
        {
            **_record(),
            "pr_number": 62,
            "pr_state": "merged",
            "pr_merge_sha": base,
        },
        implementation_milestone=True,
    )

    assert ok is True
    assert "authoritative execution" in reason
    assert "true no-op diff" in reason


def test_merged_pr_completion_allows_finalized_plan_with_published_semantic_diff(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    local_branch = _git(tmp_path, "branch", "--show-current")
    published_sha = _commit_published_semantic_change(
        tmp_path,
        base,
        branch="published-finalized-semantic",
        return_to=local_branch,
    )
    _write_plan(
        tmp_path,
        current_state="finalized",
        base_sha=base,
        finalize_tasks=[{"id": "T1"}],
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        {
            **_record(),
            "pr_number": 62,
            "pr_state": "merged",
            "pr_merge_sha": published_sha,
        },
        implementation_milestone=True,
    )

    assert ok is True
    assert "published PR target" in reason


def test_merged_pr_completion_allows_authority_block_with_published_semantic_diff(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    local_branch = _git(tmp_path, "branch", "--show-current")
    published_sha = _commit_published_semantic_change(
        tmp_path,
        base,
        branch="published-authority-block-semantic",
        return_to=local_branch,
    )
    _write_plan(
        tmp_path,
        current_state="blocked",
        base_sha=base,
        finalize_tasks=[{"id": "T1"}],
        latest_failure={
            "kind": "authority_divergence",
            "message": "execute terminal success lacks corroborated task completion",
        },
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        {
            **_record(),
            "pr_number": 62,
            "pr_state": "merged",
            "pr_merge_sha": published_sha,
        },
        implementation_milestone=True,
    )

    assert ok is True
    assert "published PR target" in reason


def test_chain_completion_reconciliation_clears_stale_plan_failure(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    plan_dir = _write_plan(
        tmp_path,
        current_state="blocked",
        finalize_tasks=[{"id": "T1"}],
        latest_failure={
            "kind": "authority_divergence",
            "message": "execute terminal success lacks corroborated task completion",
        },
    )

    _mark_plan_completed_by_chain(
        tmp_path,
        "plan-m1",
        milestone_label="m1",
        completion_reason="completion guard passed",
        writer=lambda _text: None,
    )

    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "done"
    assert "latest_failure" not in state
    events = (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    assert any('"kind":"plan_finished"' in line for line in events)


def test_merged_pr_completion_allows_blocked_plan_with_published_semantic_diff(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    local_branch = _git(tmp_path, "branch", "--show-current")
    published_sha = _commit_published_semantic_change(
        tmp_path,
        base,
        branch="published-blocked-semantic",
        return_to=local_branch,
    )
    _write_plan(
        tmp_path,
        current_state="blocked",
        base_sha=base,
        finalize_tasks=[{"id": "T1"}],
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        {
            **_record(),
            "pr_number": 62,
            "pr_state": "merged",
            "pr_merge_sha": published_sha,
        },
        implementation_milestone=True,
    )

    assert ok is True
    assert "internal plan state 'blocked' bypassed because PR is merged" in reason
    assert "published PR target" in reason


def test_non_merged_blocked_plan_still_fails_completion_guard(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(
        tmp_path,
        current_state="blocked",
        base_sha=base,
        finalize_tasks=[{"id": "T1"}],
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
    )

    assert ok is False
    assert "current_state='blocked'" in reason


def test_merged_pr_completion_allows_published_semantic_diff_with_stale_local_head(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    local_branch = _git(tmp_path, "branch", "--show-current")
    published_sha = _commit_published_semantic_change(
        tmp_path,
        base,
        branch="published-semantic-stale-local",
        return_to=local_branch,
    )
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    ok, reason = _chain_completion_guard(
        tmp_path,
        {
            **_record(),
            "pr_number": 62,
            "pr_state": "merged",
            "pr_merge_sha": published_sha,
        },
        implementation_milestone=True,
    )

    assert ok is True
    assert "published PR target" in reason


def test_merged_pr_completion_queries_gh_when_only_pr_number_is_recorded(
    tmp_path: Path, monkeypatch
) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    local_branch = _git(tmp_path, "branch", "--show-current")
    published_sha = _commit_published_semantic_change(
        tmp_path,
        base,
        branch="published-gh-semantic",
        return_to=local_branch,
    )
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])
    calls: list[int] = []

    def fake_published_target_from_gh(_root: Path, pr_number: int) -> tuple[str, str]:
        calls.append(pr_number)
        return published_sha, f"gh.pr#{pr_number}.mergeCommit"

    monkeypatch.setattr(
        chain_module,
        "_published_pr_target_from_gh",
        fake_published_target_from_gh,
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        {**_record(), "pr_number": 62, "pr_state": "merged"},
        implementation_milestone=True,
    )

    assert ok is True
    assert calls == [62]
    assert "gh.pr#62.mergeCommit" in reason


def test_merged_pr_completion_prefers_gh_merge_commit_over_stale_chain_pr_head(
    tmp_path: Path, monkeypatch
) -> None:
    base = _init_repo(tmp_path)
    local_branch = _git(tmp_path, "branch", "--show-current")
    stale_pr_head = _commit_published_megaplan_only_change(
        tmp_path,
        base,
        branch="stale-pr-head",
        return_to=local_branch,
    )
    published_merge_sha = _commit_published_semantic_change(
        tmp_path,
        base,
        branch="published-merge",
        return_to=local_branch,
    )
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    def fake_published_target_from_gh(_root: Path, pr_number: int) -> tuple[str, str]:
        assert pr_number == 128
        return published_merge_sha, "gh.pr#128.mergeCommit"

    monkeypatch.setattr(
        chain_module,
        "_published_pr_target_from_gh",
        fake_published_target_from_gh,
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        {**_record(), "pr_number": 128, "pr_state": "merged"},
        implementation_milestone=True,
        chain_state=ChainState(pr_head=stale_pr_head),
    )

    assert ok is True
    assert "gh.pr#128.mergeCommit" in reason
    assert stale_pr_head[:12] not in reason


def test_missing_milestone_base_sha_blocks_without_waiver(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, finalize_tasks=[{"id": "T1"}])

    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
    )

    assert ok is False
    assert "milestone_base_sha unavailable" in reason


# ---------------------------------------------------------------------------
# T15: Completion guard fetch-and-retry coverage
# ---------------------------------------------------------------------------


def _empty_completed_process() -> subprocess.CompletedProcess[str]:
    """Return a successful empty CompletedProcess (used as a stub for fetch)."""
    return subprocess.CompletedProcess(
        args=["git", "fetch", "origin", "--prune"],
        returncode=0,
        stdout="",
        stderr="",
    )


def test_diff_name_only_fetch_once_retry_once_via_subprocess_mock(
    tmp_path: Path,
) -> None:
    """Mocked fatal pattern: diff fails with 'bad object', fetch runs once,
    retry succeeds.  Verify exactly one fetch + one retry diff call."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    _real_run = subprocess.run
    captured: list[list[str]] = []

    def _selective_run(args, **kwargs):
        cmd = [str(a) for a in args]
        is_diff = any("diff" in a for a in cmd)
        is_fetch = any("fetch" in a for a in cmd)
        if is_diff or is_fetch:
            captured.append(cmd)
        if is_diff:
            if len([c for c in captured if "diff" in c]) == 1:
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=128,
                    stdout="",
                    stderr="fatal: bad object abc123\n",
                )
            # Retry diff: succeed
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="src/app.py\n",
                stderr="",
            )
        if is_fetch:
            return _empty_completed_process()
        return _real_run(args, **kwargs)

    with mock.patch("subprocess.run", side_effect=_selective_run):
        ok, reason = _chain_completion_guard(
            tmp_path,
            _record(),
            implementation_milestone=True,
        )

    assert ok is True, f"completion guard should pass: {reason}"
    assert "completion guard passed" in reason
    diff_calls = [c for c in captured if "diff" in c]
    fetch_calls = [c for c in captured if "fetch" in c]
    assert len(diff_calls) == 2, (
        f"Expected 2 git diff calls (fail + retry); got {len(diff_calls)}: {captured}"
    )
    assert len(fetch_calls) == 1, (
        f"Expected exactly 1 git fetch call; got {len(fetch_calls)}: {captured}"
    )


def test_diff_name_only_non_ref_error_skips_fetch_via_subprocess_mock(
    tmp_path: Path,
) -> None:
    """Non-ref-resolution error (e.g. 'not a git repository') must NOT trigger
    fetch — the error surfaces immediately with only one diff call."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    _real_run = subprocess.run
    captured: list[list[str]] = []

    def _selective_run(args, **kwargs):
        cmd = [str(a) for a in args]
        is_diff = any("diff" in a for a in cmd)
        is_fetch = any("fetch" in a for a in cmd)
        if is_diff or is_fetch:
            captured.append(cmd)
        if is_diff or is_fetch:
            return subprocess.CompletedProcess(
                args=args,
                returncode=128,
                stdout="",
                stderr="fatal: not a git repository\n",
            )
        return _real_run(args, **kwargs)

    with mock.patch("subprocess.run", side_effect=_selective_run):
        ok, reason = _chain_completion_guard(
            tmp_path,
            _record(),
            implementation_milestone=True,
        )

    assert ok is False, "non-ref error should fail the guard"
    diff_calls = [c for c in captured if "diff" in c]
    fetch_calls = [c for c in captured if "fetch" in c]
    assert len(diff_calls) == 1, (
        f"Expected exactly 1 git diff call (no retry); got {len(diff_calls)}: {captured}"
    )
    assert len(fetch_calls) == 0, (
        f"Expected 0 git fetch calls for non-ref error; got {len(fetch_calls)}: {captured}"
    )


def test_completion_guard_bare_origin_fetch_supplies_missing_object(
    tmp_path: Path,
) -> None:
    """Local/bare Git workflow: a merge commit exists on origin but not locally.
    _chain_completion_guard with pr_merge_sha pointing to the remote-only commit
    must fetch --prune and pass the guard."""
    local = tmp_path / "local"
    remote = tmp_path / "remote.git"
    other = tmp_path / "other"
    local.mkdir()
    remote.mkdir()
    _git(remote, "init", "--bare")
    base = _init_repo(local)
    _git(local, "branch", "-M", "main")
    _git(local, "remote", "add", "origin", str(remote))
    _git(local, "push", "-u", "origin", "main")

    # Create a remote-only commit from a separate clone
    _git(tmp_path, "clone", str(remote), str(other))
    _git(other, "config", "user.email", "test@example.com")
    _git(other, "config", "user.name", "Test User")
    (other / "src").mkdir(exist_ok=True)
    (other / "src" / "app.py").write_text("print('remote done')\n", encoding="utf-8")
    _git(other, "add", "src/app.py")
    _git(other, "commit", "-m", "remote semantic change")
    remote_sha = _git(other, "rev-parse", "HEAD")
    _git(other, "push", "origin", "main")

    # Confirm local doesn't have the remote commit
    missing = subprocess.run(
        ["git", "cat-file", "-t", remote_sha],
        cwd=local,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode != 0, "remote commit should be missing locally"

    # Write plan state with base_sha
    _write_plan(local, base_sha=base, finalize_tasks=[{"id": "T1"}])

    # Run completion guard — fetch should bring the missing object in
    ok, reason = _chain_completion_guard(
        local,
        {
            **_record(),
            "pr_number": 42,
            "pr_state": "merged",
            "pr_merge_sha": remote_sha,
        },
        implementation_milestone=True,
    )

    assert ok is True, f"completion guard should pass after fetch: {reason}"
    assert (
        "published PR target" in reason or "completion guard passed" in reason
    ), f"unexpected reason: {reason}"


def test_completion_guard_surfaces_unresolved_error_after_fetch_retry(
    tmp_path: Path,
) -> None:
    """When fetch succeeds but the retry diff still fails (truly bogus SHA),
    the real error is surfaced through the completion guard, not swallowed."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    bogus_sha = "deadbeef" * 5  # 40 hex chars, not a real object anywhere

    _real_run = subprocess.run
    captured: list[list[str]] = []

    def _selective_run(args, **kwargs):
        cmd = [str(a) for a in args]
        is_diff = any("diff" in a for a in cmd)
        is_fetch = any("fetch" in a for a in cmd)
        cmd_str = " ".join(cmd)
        involves_bogus = "deadbeef" in cmd_str
        if (is_diff and involves_bogus) or is_fetch:
            captured.append(cmd)
        if is_fetch:
            return _empty_completed_process()
        if is_diff and involves_bogus:
            return subprocess.CompletedProcess(
                args=args,
                returncode=128,
                stdout="",
                stderr="fatal: bad object deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n",
            )
        return _real_run(args, **kwargs)

    with mock.patch("subprocess.run", side_effect=_selective_run):
        ok, reason = _chain_completion_guard(
            tmp_path,
            {
                **_record(),
                "pr_number": 99,
                "pr_state": "merged",
                "pr_merge_sha": bogus_sha,
            },
            implementation_milestone=True,
        )

    assert ok is False, f"truly bogus SHA should fail after fetch+retry, got ok={ok}: {reason}"
    diff_calls = [c for c in captured if "diff" in c]
    fetch_calls = [c for c in captured if "fetch" in c]
    assert len(diff_calls) == 2, (
        f"Expected 2 diff calls (first fail + retry fail); got {len(diff_calls)}: {captured}"
    )
    assert len(fetch_calls) == 1, (
        f"Expected 1 fetch call; got {len(fetch_calls)}: {captured}"
    )
    # The error reason must mention the failed diff
    assert (
        "failed" in reason.lower()
        or "bad object" in reason.lower()
        or "git diff" in reason.lower()
    ), f"reason should surface the unresolved error: {reason}"


def test_semantic_diff_nonempty_from_base_fetch_once_retry_once(
    tmp_path: Path,
) -> None:
    """Through _semantic_diff_nonempty_from_base: first diff fails with
    'unknown revision', fetch runs once, retry succeeds.  Verifies the
    fetch-and-retry at the lower helper layer called by the completion guard."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)

    _real_run = subprocess.run
    captured: list[list[str]] = []

    def _selective_run(args, **kwargs):
        cmd = [str(a) for a in args]
        is_diff = any("diff" in a for a in cmd)
        is_fetch = any("fetch" in a for a in cmd)
        if is_diff or is_fetch:
            captured.append(cmd)
        if is_diff:
            if len([c for c in captured if "diff" in c]) == 1:
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=128,
                    stdout="",
                    stderr="fatal: unknown revision or path not in the working tree\n",
                )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="src/app.py\n",
                stderr="",
            )
        if is_fetch:
            return _empty_completed_process()
        return _real_run(args, **kwargs)

    with mock.patch("subprocess.run", side_effect=_selective_run):
        ok, reason = chain_module._semantic_diff_nonempty_from_base(
            tmp_path, base
        )

    assert ok is True, f"semantic diff should pass after fetch: {reason}"
    assert "local HEAD" in reason
    diff_calls = [c for c in captured if "diff" in c]
    fetch_calls = [c for c in captured if "fetch" in c]
    assert len(diff_calls) == 2, (
        f"Expected 2 git diff calls (fail + retry); got {len(diff_calls)}: {captured}"
    )
    assert len(fetch_calls) == 1, (
        f"Expected exactly 1 git fetch call; got {len(fetch_calls)}: {captured}"
    )
