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
from arnold_pipelines.megaplan.chain.spec import ChainState, load_spec
from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
    AcceptanceSnapshot,
    AcceptanceTransaction,
)
from arnold_pipelines.megaplan.orchestration.completion_io import (
    commit_acceptance_transaction,
    prepare_acceptance_transaction,
    store_acceptance_snapshot,
)
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
                    },
                    {
                        "task_id": "v3_api_tests",
                        "status": "done",
                        "commands_run": [
                            "pytest -q tests/arnold/workflow/test_source_compiler_api.py -q"
                        ],
                        "head_sha": base_sha,
                    },
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


def test_run_chain_accepts_local_completion_committed_during_pr_sync(
    tmp_path: Path,
) -> None:
    head = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _write_plan(
        tmp_path,
        current_state="done",
        base_sha=head,
        finalize_tasks=[{"id": "T1", "status": "done"}],
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="executed",
            pr_number=255,
            pr_state="open",
        ),
    )
    pr_lookups: list[int] = []
    messages: list[str] = []

    def pr_state(_root: Path, pr_number: int | None, **_kwargs) -> str:
        assert pr_number is not None, "local completion must not become PR #None"
        pr_lookups.append(pr_number)
        return "open"

    def capture_local_completion(
        _root: Path,
        _spec_path: Path,
        *,
        branch: str | None,
        pr_number: int | None,
    ) -> None:
        assert branch == "test/m1"
        if pr_number is None:
            return
        assert pr_number == 255
        state = load_chain_state(spec_path)
        state.completed = [
            {
                "label": "m1",
                "plan": "plan-m1",
                "status": "done",
                "pr_number": None,
                "local_commit_sha": head,
                "publication_evidence": "local_no_push_reconciliation",
            }
        ]
        state.current_milestone_index = 1
        state.current_plan_name = None
        state.last_state = "between_milestones"
        state.pr_number = None
        state.pr_state = None
        save_chain_state(spec_path, state)

    with (
        patch(
            "arnold_pipelines.megaplan.chain._reconcile_chain_from_ground_truth",
            side_effect=lambda _root, _spec_path, _spec, state, **_kwargs: state,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
            return_value=head,
        ),
        patch("arnold_pipelines.megaplan.chain._init_plan", return_value="plan-m1"),
        patch("arnold_pipelines.megaplan.chain._ensure_milestone_pr", return_value=255),
        patch("arnold_pipelines.megaplan.chain._pr_state", side_effect=pr_state),
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
            "arnold_pipelines.megaplan.chain._plan_terminal_completion_is_authoritative",
            return_value=(True, "ok"),
        ),
        patch(
            "arnold_pipelines.megaplan.chain._shadow_milestone_completion_verdict",
            return_value=False,
        ),
        patch("arnold_pipelines.megaplan.chain._run_full_suite_backstop_gate", return_value={}),
        patch("arnold_pipelines.megaplan.chain._commit_and_push_phase"),
        patch(
            "arnold_pipelines.megaplan.chain._capture_sync_state",
            side_effect=capture_local_completion,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._chain_completion_guard",
            return_value=(True, "accepted local completion"),
        ),
    ):
        result = run_chain(spec_path, tmp_path, writer=messages.append, mode="execute")

    saved = load_chain_state(spec_path)
    assert result["status"] == "done"
    assert saved.current_milestone_index == 1
    assert saved.current_plan_name is None
    assert pr_lookups == [255]
    assert not any("PR #None" in message for message in messages)
    assert any("continuing without PR metadata" in message for message in messages)


def test_reconcile_preserves_guarded_local_no_push_completion(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _git(tmp_path, "add", "chain.yaml", "idea.md", "NORTHSTAR.md")
    _git(tmp_path, "commit", "-m", "track chain inputs")
    _write_plan(
        tmp_path,
        current_state="done",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done"}],
    )
    local_commit_sha = _commit_semantic_change(tmp_path)
    state = ChainState(
        current_milestone_index=1,
        current_plan_name=None,
        last_state="between_milestones",
        completed=[
            {
                "label": "m1",
                "plan": "plan-m1",
                "status": "done",
                "pr_number": None,
                "local_commit_sha": local_commit_sha,
                "publication_evidence": "local_no_push_reconciliation",
            }
        ],
    )
    save_chain_state(spec_path, state)
    messages: list[str] = []

    with patch(
        "arnold_pipelines.megaplan.chain._pr_state",
        side_effect=AssertionError("local completion must not query a PR"),
    ):
        reconciled = chain_module._reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            load_spec(spec_path),
            state,
            writer=messages.append,
            push_enabled=True,
        )

    assert reconciled.current_milestone_index == 1
    assert reconciled.current_plan_name is None
    assert [record["label"] for record in reconciled.completed] == ["m1"]
    assert any("preserved accepted local/no-push completion" in msg for msg in messages)


def test_reconcile_rejects_unguarded_prless_branch_completion(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    state = ChainState(
        current_milestone_index=1,
        current_plan_name=None,
        last_state="between_milestones",
        completed=[{"label": "m1", "plan": "plan-m1", "status": "done"}],
    )
    save_chain_state(spec_path, state)

    reconciled = chain_module._reconcile_chain_from_ground_truth(
        tmp_path,
        spec_path,
        load_spec(spec_path),
        state,
        writer=lambda _message: None,
        push_enabled=True,
    )

    assert reconciled.current_milestone_index == 0
    assert reconciled.completed == []
    assert reconciled.last_state == "authority_divergence"


def test_reconcile_local_completion_clears_merge_wait_before_successor(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    with spec_path.open("a", encoding="utf-8") as handle:
        handle.write(
            "  - label: m2\n"
            f"    idea: {tmp_path / 'idea.md'}\n"
            "    branch: test/m2\n"
        )
    _write_plan(
        tmp_path,
        current_state="done",
        base_sha=base,
        finalize_tasks=[{"id": "T1", "status": "done"}],
    )
    _commit_semantic_change(tmp_path)
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-m1",
        last_state=STATE_AWAITING_PR_MERGE,
        pr_number=255,
        pr_state="open",
    )
    save_chain_state(spec_path, state)

    reconciled = chain_module._reconcile_chain_from_ground_truth(
        tmp_path,
        spec_path,
        load_spec(spec_path),
        state,
        writer=lambda _message: None,
        push_enabled=False,
    )

    assert reconciled.current_milestone_index == 1
    assert reconciled.current_plan_name is None
    assert reconciled.last_state == "between_milestones"
    assert reconciled.pr_number is None
    assert [record["label"] for record in reconciled.completed] == ["m1"]
    assert reconciled.completed[0]["publication_evidence"] == (
        "local_no_push_reconciliation"
    )


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


def test_run_chain_clears_missing_pr_context_while_resuming_blocked_plan(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    _write_plan(
        tmp_path,
        current_state="finalized",
        finalize_tasks=[{"id": "T1", "status": "done"}],
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="blocked",
            pr_number=99,
            pr_state="open",
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
            "arnold_pipelines.megaplan.chain._pr_state",
            return_value="closed",
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
    assert reason == "finalize.json"


def test_latest_execution_batch_all_tasks_done_blocks_uncovered_pending_finalize_tasks(
    tmp_path: Path,
) -> None:
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    plan_dir = _write_execute_authority_plan(tmp_path, base_sha=base)
    batch = json.loads((plan_dir / "execution_batch_1.json").read_text(encoding="utf-8"))
    batch["task_updates"] = [
        update
        for update in batch["task_updates"]
        if update.get("task_id") != "v3_api_tests"
    ]
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(batch) + "\n",
        encoding="utf-8",
    )

    ok, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert ok is False
    assert (
        "finalize.json has pending tasks without authoritative execution updates: "
        "v3_api_tests"
    ) in reason


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
    assert reason == "finalize.json"


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


def test_latest_execution_batch_all_tasks_done_blocks_stale_pending_finalize_rows(
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

    assert ok is False
    assert "pending tasks without authoritative execution updates: T2" in reason


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


def test_completion_guard_allows_published_pr_target_descending_from_chain_target(
    tmp_path: Path, monkeypatch
) -> None:
    base = _init_repo(tmp_path)
    local_branch = _git(tmp_path, "branch", "--show-current")
    published_sha = _commit_published_semantic_change(
        tmp_path,
        base,
        branch="published-not-landed",
        return_to=local_branch,
    )
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    def fake_published_target_from_gh(_root: Path, pr_number: int) -> tuple[str, str]:
        assert pr_number == 95
        return published_sha, "gh.pr#95.mergeCommit"

    monkeypatch.setattr(
        chain_module,
        "_published_pr_target_from_gh",
        fake_published_target_from_gh,
    )

    ok, reason = _chain_completion_guard(
        tmp_path,
        {**_record(), "pr_number": 95, "pr_state": "merged"},
        implementation_milestone=True,
        chain_state=ChainState(target_base_ref=local_branch),
    )

    assert ok is True
    assert "published PR target" in reason
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



# ---------------------------------------------------------------------------
# T33: Mode-aware completion guard — shadow fail-open, atomic fail-closed
# ---------------------------------------------------------------------------


def _atomic_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "atomic"
    return state


def _enforce_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "enforce"
    return state


def _shadow_state() -> ChainState:
    return ChainState()  # default == shadow


def _warn_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "warn"
    return state


def _off_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "off"
    return state


def _state_with_receipt(
    mode: str = "atomic",
    label: str = "m1",
    transaction_id: str = "tx-abc123",
    snapshot_hash: str = "sha256:deadbeef",
) -> ChainState:
    state = ChainState()
    state.completion_contract_mode = mode
    state.completed.append(
        {
            "label": label,
            "plan": "plan-m1",
            "status": "done",
            "acceptance_receipt": {
                "transaction_id": transaction_id,
                "snapshot_hash": snapshot_hash,
                "milestone_label": label,
                "plan_name": "plan-m1",
                "milestone_index": 0,
            },
        }
    )
    return state


_FULL_SHA = "a" * 40


def _state_with_committed_receipt(
    root: Path,
    *,
    mode: str = "atomic",
    label: str = "m1",
    milestone_index: int = 0,
    plan_name: str = "plan-m1",
    transaction_id: str = "tx-001",
    source_commit_ref: str = _FULL_SHA,
    runtime_identity: str = "ci-runner-7",
) -> ChainState:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    snapshot = AcceptanceSnapshot(
        transaction_id=transaction_id,
        chain_run_id="chain-run-1",
        milestone_label=label,
        milestone_index=milestone_index,
        plan_name=plan_name,
        source_commit_ref=source_commit_ref,
        runtime_identity=runtime_identity,
    )
    store_acceptance_snapshot(plan_dir, snapshot)
    transaction = AcceptanceTransaction(
        transaction_id=transaction_id,
        snapshot_hash=snapshot.content_hash,
        accepted=True,
        mode=mode,
        tested_commit_ref=source_commit_ref,
        tested_runtime_identity=runtime_identity,
    )
    prepare_acceptance_transaction(plan_dir, transaction)
    commit_acceptance_transaction(plan_dir, transaction_id)

    return ChainState(
        completion_contract_mode=mode,
        current_milestone_index=1,
        current_plan_name=None,
        last_state="blocked",
        completed=[
            {
                "label": label,
                "plan": plan_name,
                "status": "done",
                "milestone_index": milestone_index,
                "transaction_id": transaction_id,
                "snapshot_hash": snapshot.content_hash,
                "source_commit_ref": source_commit_ref,
                "runtime_identity": runtime_identity,
                "acceptance_receipt": snapshot.with_receipt().to_dict(),
            },
        ],
        metadata={
            "acceptance_plan_dirs": {
                label: str(plan_dir),
                plan_name: str(plan_dir),
            }
        },
    )


# -- Shadow mode retains fail-open behavior ----------------------------------


def test_shadow_completion_guard_fail_open_without_acceptance_receipt(
    tmp_path: Path,
) -> None:
    """Shadow mode (default) must NOT require an acceptance receipt — fail-open."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    state = _shadow_state()
    ok, reason = _append_completed_with_guard(
        tmp_path,
        state,
        _record(),
        implementation_milestone=True,
        writer=lambda _msg: None,
    )

    assert ok is True, f"shadow mode should pass: {reason}"
    assert len(state.completed) == 1
    assert state.completed[0]["label"] == "m1"


def test_shadow_completion_guard_still_blocks_on_guard_failure(
    tmp_path: Path,
) -> None:
    """Shadow mode must still block when the underlying guard fails (e.g. no diff)."""
    base = _init_repo(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    state = _shadow_state()
    ok, reason = _append_completed_with_guard(
        tmp_path,
        state,
        _record(),
        implementation_milestone=True,
        writer=lambda _msg: None,
    )

    assert ok is False
    assert "no semantic diff from milestone_base_sha" in reason
    assert state.completed == []
    assert state.last_state == "authority_divergence"


def test_warn_mode_fail_open_without_acceptance_receipt(
    tmp_path: Path,
) -> None:
    """Warn mode must NOT require an acceptance receipt — fail-open."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    state = _warn_state()
    ok, reason = _append_completed_with_guard(
        tmp_path,
        state,
        _record(),
        implementation_milestone=True,
        writer=lambda _msg: None,
    )

    assert ok is True, f"warn mode should pass: {reason}"
    assert len(state.completed) == 1


def test_off_mode_fail_open_without_acceptance_receipt(
    tmp_path: Path,
) -> None:
    """Off mode must NOT require an acceptance receipt — fail-open."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    state = _off_state()
    ok, reason = _append_completed_with_guard(
        tmp_path,
        state,
        _record(),
        implementation_milestone=True,
        writer=lambda _msg: None,
    )

    assert ok is True, f"off mode should pass: {reason}"
    assert len(state.completed) == 1


# -- Atomic/enforce mode fails closed without acceptance evidence --------------


def test_atomic_mode_fails_closed_without_acceptance_evidence(
    tmp_path: Path,
) -> None:
    """Atomic mode must block completion without acceptance evidence."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    state = _atomic_state()
    ok, reason = _append_completed_with_guard(
        tmp_path,
        state,
        _record(),
        implementation_milestone=True,
        writer=lambda _msg: None,
    )

    assert ok is False
    assert "requires an accepted acceptance boundary" in reason
    assert state.completed == []
    # Repair targets must be recorded
    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list)
    assert len(targets) >= 1
    assert targets[0]["kind"] == "unknown_acceptance_failure"


def test_enforce_mode_fails_closed_without_acceptance_evidence(
    tmp_path: Path,
) -> None:
    """Enforce mode (synonym of atomic) must also block without acceptance evidence."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    state = _enforce_state()
    ok, reason = _append_completed_with_guard(
        tmp_path,
        state,
        _record(),
        implementation_milestone=True,
        writer=lambda _msg: None,
    )

    assert ok is False
    assert "requires an accepted acceptance boundary" in reason
    assert state.completed == []


def test_atomic_mode_fails_closed_on_predicate_failure(
    tmp_path: Path,
) -> None:
    """Atomic mode must block and record typed repair targets when the guard fails."""
    base = _init_repo(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    state = _atomic_state()
    predicate_failures = [
        {
            "kind": "divergent",
            "evidence_kind": "artifact_hash",
            "summary": "declared hash mismatch for src/app.py",
            "details": {"expected": "sha256:abc", "observed": "sha256:def"},
        }
    ]
    ok, reason = _append_completed_with_guard(
        tmp_path,
        state,
        _record(),
        implementation_milestone=True,
        writer=lambda _msg: None,
        predicate_failures=predicate_failures,
    )

    assert ok is False
    assert state.completed == []
    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list)
    assert len(targets) >= 1
    assert targets[0]["kind"] == "divergent"
    assert "declared hash mismatch" in targets[0]["summary"]


def test_atomic_mode_with_guard_failure_records_legacy_target(
    tmp_path: Path,
) -> None:
    """Atomic mode with guard failure but no predicate_failures records legacy target."""
    base = _init_repo(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    state = _atomic_state()
    ok, reason = _append_completed_with_guard(
        tmp_path,
        state,
        _record(),
        implementation_milestone=True,
        writer=lambda _msg: None,
        # No predicate_failures — legacy path
    )

    assert ok is False
    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list)
    assert len(targets) >= 1
    assert targets[0]["kind"] == "unknown_acceptance_failure"
    assert targets[0]["details"].get("legacy") is True


# -- Shadow mode handles rejection reason (guard failure) the legacy way -----


def test_shadow_mode_predicate_failure_records_authority_divergence(
    tmp_path: Path,
) -> None:
    """Shadow mode records authority_divergence on guard failure, legacy behavior."""
    base = _init_repo(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    state = _shadow_state()
    ok, reason = _append_completed_with_guard(
        tmp_path,
        state,
        _record(),
        implementation_milestone=True,
        writer=lambda _msg: None,
    )

    assert ok is False
    assert state.last_state == "authority_divergence"
    # Shadow mode does NOT populate completion_guard_repair_targets
    assert "completion_guard_repair_targets" not in state.metadata


# -- Normalization preserves blocked markers in atomic mode -------------------


def test_normalization_preserves_blocked_in_atomic_without_receipt(
    tmp_path: Path,
) -> None:
    """_normalize_advanced_completed_cursor must preserve blocked markers
    in atomic mode when completed records lack acceptance receipts."""
    from arnold_pipelines.megaplan.chain.spec import (
        ChainSpec,
        MilestoneSpec,
        _normalize_advanced_completed_cursor,
    )

    spec = ChainSpec(
        base_branch="main",
        anchors={},
        milestones=[MilestoneSpec(label="m1", idea=tmp_path / "idea.md")],
    )
    state = ChainState(
        current_milestone_index=1,  # past m1
        current_plan_name=None,
        last_state="blocked",
        completed=[
            {"label": "m1", "plan": "plan-m1", "status": "done"},
        ],
    )
    state.completion_contract_mode = "atomic"

    normalized = _normalize_advanced_completed_cursor(state, spec)
    # Blocked marker must be preserved in atomic mode without receipt
    assert normalized.last_state == "blocked"


def test_normalization_preserves_authority_divergence_in_atomic_without_receipt(
    tmp_path: Path,
) -> None:
    """_normalize_advanced_completed_cursor must preserve authority_divergence
    in atomic mode when completed records lack acceptance receipts."""
    from arnold_pipelines.megaplan.chain.spec import (
        ChainSpec,
        MilestoneSpec,
        _normalize_advanced_completed_cursor,
    )

    spec = ChainSpec(
        base_branch="main",
        anchors={},
        milestones=[MilestoneSpec(label="m1", idea=tmp_path / "idea.md")],
    )
    state = ChainState(
        current_milestone_index=1,
        current_plan_name=None,
        last_state="authority_divergence",
        completed=[
            {"label": "m1", "plan": "plan-m1", "status": "done"},
        ],
    )
    state.completion_contract_mode = "atomic"

    normalized = _normalize_advanced_completed_cursor(state, spec)
    assert normalized.last_state == "authority_divergence"


def test_normalization_clears_blocked_in_atomic_with_valid_receipt(
    tmp_path: Path,
) -> None:
    """_normalize_advanced_completed_cursor clears blocked marker in atomic
    mode when the completed record carries a valid, identity-matched receipt."""
    from arnold_pipelines.megaplan.chain.spec import (
        ChainSpec,
        MilestoneSpec,
        _normalize_advanced_completed_cursor,
    )

    spec = ChainSpec(
        base_branch="main",
        anchors={},
        milestones=[MilestoneSpec(label="m1", idea=tmp_path / "idea.md")],
    )
    state = _state_with_committed_receipt(tmp_path)

    normalized = _normalize_advanced_completed_cursor(state, spec)
    # In atomic mode with committed acceptance evidence, blocked can be cleared.
    assert normalized.last_state == "done"


def test_normalization_clears_blocked_in_shadow_without_receipt(
    tmp_path: Path,
) -> None:
    """load_chain_state clears blocked marker in shadow mode even without receipt."""
    idea = tmp_path / "idea.md"
    idea.write_text("ship milestone\n", encoding="utf-8")
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        f"    idea: {idea}\n",
        encoding="utf-8",
    )
    (tmp_path / "NORTHSTAR.md").write_text("north star\n", encoding="utf-8")

    state = ChainState(
        current_milestone_index=1,
        current_plan_name=None,
        last_state="blocked",
        completed=[
            {"label": "m1", "plan": "plan-m1", "status": "done"},
        ],
    )
    # Default = shadow
    save_chain_state(spec_path, state)

    loaded = load_chain_state(spec_path)
    # In shadow mode, blocked is cleared (legacy behavior)
    assert loaded.last_state == "done"


def test_normalization_preserves_blocked_with_mismatched_receipt_identity(
    tmp_path: Path,
) -> None:
    """_normalize_advanced_completed_cursor must not clear blocked when receipt
    identity fields don't match the completed record."""
    from arnold_pipelines.megaplan.chain.spec import (
        ChainSpec,
        MilestoneSpec,
        _normalize_advanced_completed_cursor,
    )

    spec = ChainSpec(
        base_branch="main",
        anchors={},
        milestones=[MilestoneSpec(label="m1", idea=tmp_path / "idea.md")],
    )
    state = ChainState(
        current_milestone_index=1,
        current_plan_name=None,
        last_state="blocked",
        completed=[
            {
                "label": "m1",
                "plan": "plan-m1",
                "status": "done",
                "milestone_index": 0,
                "acceptance_receipt": {
                    "transaction_id": "tx-001",
                    "snapshot_hash": "sha256:abc123",
                    "milestone_label": "m2",  # WRONG label
                    "plan_name": "plan-m1",
                    "milestone_index": 0,
                },
            },
        ],
    )
    state.completion_contract_mode = "atomic"

    normalized = _normalize_advanced_completed_cursor(state, spec)
    # Receipt identity mismatch — blocked stays
    assert normalized.last_state == "blocked"


# -- Chain completion guard mode-aware integration ---------------------------


def test_chain_completion_guard_shadow_ignores_acceptance_context(
    tmp_path: Path,
) -> None:
    """_chain_completion_guard in shadow mode works regardless of chain_state mode."""
    base = _init_repo(tmp_path)
    _commit_semantic_change(tmp_path)
    _write_plan(tmp_path, base_sha=base, finalize_tasks=[{"id": "T1"}])

    # Pass a chain_state with atomic mode — guard itself is mode-agnostic
    state = _atomic_state()
    ok, reason = _chain_completion_guard(
        tmp_path,
        _record(),
        implementation_milestone=True,
        chain_state=state,
    )

    assert ok is True
    assert "completion guard passed" in reason


# -- _handle_completion_guard_failure in atomic mode -------------------------


def test_handle_completion_guard_failure_atomic_with_predicate_failures(
    tmp_path: Path,
) -> None:
    """_handle_completion_guard_failure stores typed repair targets for atomic mode."""
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
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-m1",
        completion_contract_mode="atomic",
    )
    spec = load_spec(spec_path)

    predicate_failures = [
        {
            "kind": "stale",
            "evidence_kind": "manifest_freshness",
            "summary": "execution batch not sequential",
            "details": {"batch_index": 2, "expected_previous": "batch_1"},
        }
    ]

    result = _handle_completion_guard_failure(
        root=tmp_path,
        spec_path=spec_path,
        spec=spec,
        state=state,
        milestone=spec.milestones[0],
        plan_name="plan-m1",
        outcome_status="done",
        reason="completion guard blocked in atomic mode",
        events=[],
        writer=lambda _msg: None,
        predicate_failures=predicate_failures,
        acceptance_transaction_id="tx-test",
        acceptance_snapshot_hash="sha256:test",
    )

    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list)
    assert len(targets) >= 1
    assert any(t.get("kind") == "stale" for t in targets)
    assert result["status"] == "stopped"


def test_handle_completion_guard_failure_legacy_callers_get_fail_closed_target(
    tmp_path: Path,
) -> None:
    """Legacy callers without predicate_failures get fail-closed unknown_acceptance_failure."""
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
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-m1",
        completion_contract_mode="atomic",
    )
    spec = load_spec(spec_path)

    result = _handle_completion_guard_failure(
        root=tmp_path,
        spec_path=spec_path,
        spec=spec,
        state=state,
        milestone=spec.milestones[0],
        plan_name="plan-m1",
        outcome_status="done",
        reason="no semantic diff",
        events=[],
        writer=lambda _msg: None,
        # No predicate_failures — legacy caller
    )

    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list)
    assert len(targets) >= 1
    legacy_target = targets[0]
    assert legacy_target["kind"] == "unknown_acceptance_failure"
    assert legacy_target["details"].get("legacy") is True
    assert result["status"] == "stopped"


def test_handle_completion_guard_failure_shadow_preserves_legacy_behavior(
    tmp_path: Path,
) -> None:
    """Shadow mode _handle_completion_guard_failure preserves legacy retry/abort
    behavior. Repair targets may be recorded (T13 added them for all modes) but the
    core chain response (stopped + retry) must remain identical to pre-T13."""
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
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-m1",
        # Default = shadow
    )
    spec = load_spec(spec_path)

    result = _handle_completion_guard_failure(
        root=tmp_path,
        spec_path=spec_path,
        spec=spec,
        state=state,
        milestone=spec.milestones[0],
        plan_name="plan-m1",
        outcome_status="done",
        reason="no semantic diff",
        events=[],
        writer=lambda _msg: None,
    )

    # Shadow mode: status is still "stopped" (retry ladder), legacy behavior preserved
    assert result["status"] == "stopped"
    assert "completion guard retrying" in result["reason"]
    # T13 added repair targets for all modes — verify a legacy target was recorded
    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list)
    assert len(targets) >= 1
    assert targets[0]["kind"] == "unknown_acceptance_failure"
    assert targets[0]["details"].get("legacy") is True
