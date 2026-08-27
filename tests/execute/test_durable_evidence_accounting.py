from __future__ import annotations

import json
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.execute.aggregation import _compute_execute_scope_drift
from arnold_pipelines.megaplan._core.io import (
    list_batch_artifacts,
    resolve_batch_artifact,
)
from arnold_pipelines.megaplan.auto import _latest_recorded_execute_head
from arnold_pipelines.megaplan.orchestration.execution_evidence import validate_execution_evidence


def _commit(project_dir: Path, message: str) -> str:
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=project_dir, check=True, capture_output=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_dir, text=True).strip()


def _init_repo(project_dir: Path) -> str:
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_dir, check=True)
    (project_dir / "base.py").write_text("BASE = 1\n", encoding="utf-8")
    return _commit(project_dir, "base")


def _write_s4_attempt(
    plan_dir: Path,
    *,
    batch_index: int,
    digest: str,
    head: str,
    fence_token: int | None,
) -> Path:
    batch_dir = plan_dir / "execute_batches" / f"batch_{batch_index}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "task_updates": [
            {
                "task_id": f"T{batch_index}",
                "status": "done",
                "commands_run": ["pytest -q"],
                "head_sha": head,
            }
        ]
    }
    if fence_token is not None:
        payload["dispatch_identity"] = {
            "fence": {"token": fence_token},
        }
    path = batch_dir / f"tasks_{digest}.json"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def test_reused_batch_index_prefers_fenced_attempt_over_lexicographic_first(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    stale = _write_s4_attempt(
        plan_dir,
        batch_index=1,
        digest="000000000000",
        head="stale-head",
        fence_token=None,
    )
    accepted = _write_s4_attempt(
        plan_dir,
        batch_index=1,
        digest="ffffffffffff",
        head="accepted-head",
        fence_token=7,
    )

    assert stale.name < accepted.name
    assert resolve_batch_artifact(plan_dir, 1) == accepted
    assert list_batch_artifacts(plan_dir) == [accepted]


def test_latest_execute_head_uses_newest_fence_not_highest_batch_number(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    newest_retry = _write_s4_attempt(
        plan_dir,
        batch_index=1,
        digest="newest",
        head="current-head",
        fence_token=7,
    )
    _write_s4_attempt(
        plan_dir,
        batch_index=21,
        digest="older",
        head="old-head",
        fence_token=4,
    )

    assert newest_retry in list_batch_artifacts(plan_dir)
    assert _latest_recorded_execute_head(plan_dir) == "current-head"


def test_terminal_quality_uses_finalized_evidence_and_current_partial_batch(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    base_sha = _init_repo(project_dir)
    (project_dir / "prior.py").write_text("PRIOR = 1\n", encoding="utf-8")
    (project_dir / "current.py").write_text("CURRENT = 1\n", encoding="utf-8")
    _commit(project_dir, "implementation")

    plan_dir = project_dir / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    finalized_tasks = [
        {
            "id": "T1",
            "status": "done",
            "files_changed": ["prior.py"],
            "commands_run": ["pytest tests/test_prior.py -q"],
            "head_sha": "pre-replay-head",
        },
        {
            "id": "T2",
            "status": "pending",
            "files_changed": ["unexecuted.py"],
            "commands_run": ["pytest tests/test_unexecuted.py -q"],
        },
    ]
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": finalized_tasks, "sense_checks": []}) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_2.json").write_text(
        json.dumps(
            {
                "files_changed": ["current.py"],
                "task_updates": [
                    {
                        "task_id": "T3",
                        "status": "done",
                        "files_changed": ["current.py"],
                        "commands_run": ["pytest tests/test_current.py -q"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    state = {
        "config": {"robustness": "full"},
        "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
    }
    drift = _compute_execute_scope_drift(
        project_dir,
        {"files_changed": ["current.py"]},
        state,
        plan_dir=plan_dir,
    )

    assert drift.files_added == []


def test_top_level_artifact_evidence_cannot_promote_pending_task_or_check(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "execution_batch_8.json").write_text(
        json.dumps(
            {
                "files_changed": ["runtime.py"],
                "commands_run": ["python -m py_compile runtime.py"],
                "task_updates": [
                    {"task_id": "T8", "status": "pending"}
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    finalized = {
        "tasks": [
            {
                "id": "T8",
                "status": "pending",
                "files_changed": ["runtime.py"],
                "commands_run": ["python -m py_compile runtime.py"],
                "executor_notes": "",
            }
        ],
        "sense_checks": [{"id": "SC8", "task_id": "T8", "executor_note": ""}],
    }

    before = json.loads(json.dumps(finalized))
    validate_execution_evidence(finalized, tmp_path / "project", plan_dir=plan_dir)

    assert finalized == before


from arnold_pipelines.megaplan.execute.aggregation import (
    reconcile_finalized_review_scope_claims,
)


def test_review_scope_reconciliation_requires_terminal_task_and_committed_evidence(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "review-project"
    base_sha = _init_repo(project_dir)
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "poller.py").write_text("POLL = 1\n", encoding="utf-8")
    (project_dir / "runtime.py").write_text("RUNTIME = 1\n", encoding="utf-8")
    _commit(project_dir, "reviewed work")

    plan_dir = project_dir / ".megaplan" / "plans" / "review-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "review.json").write_text(
        json.dumps(
            {
                "task_verdicts": [
                    {"task_id": "T1", "evidence_files": ["tests/poller.py"]},
                    {"task_id": "T2", "evidence_files": ["runtime.py"]},
                    {"task_id": "T3", "evidence_files": ["not-in-diff.py"]},
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": [], "commands_run": ["pytest"]},
            {"id": "T2", "status": "pending", "files_changed": [], "commands_run": []},
            {"id": "T3", "status": "done", "files_changed": [], "commands_run": ["pytest"]},
        ]
    }
    reconciled = reconcile_finalized_review_scope_claims(
        finalize_data,
        plan_dir=plan_dir,
        project_dir=project_dir,
        state={"meta": {"chain_policy": {"milestone_base_sha": base_sha}}},
    )

    assert reconciled == {"T1": ["tests/poller.py"]}
    assert finalize_data["tasks"][0]["files_changed"] == ["tests/poller.py"]
    assert finalize_data["tasks"][1]["files_changed"] == []
    assert finalize_data["tasks"][2]["files_changed"] == []


from arnold_pipelines.megaplan.orchestration.authority_readers import (
    has_durable_terminal_task_evidence,
)


def test_terminal_authority_evidence_requires_outputs_not_terminal_label() -> None:
    assert has_durable_terminal_task_evidence(
        {"status": "done", "files_changed": ["tests/poller.py"]}
    )
    assert has_durable_terminal_task_evidence(
        {"status": "done", "commands_run": ["pytest tests/test_runtime.py -q"]}
    )
    assert has_durable_terminal_task_evidence(
        {"status": "skipped", "executor_notes": "ComfyUI prerequisite is unavailable."}
    )
    assert not has_durable_terminal_task_evidence(
        {"status": "done", "files_changed": [], "commands_run": []}
    )
    assert not has_durable_terminal_task_evidence(
        {"status": "pending", "files_changed": ["speculative.py"]}
    )


from arnold_pipelines.megaplan import chain as chain_module


def test_admission_rearms_only_revalidated_execute_authority_divergence(tmp_path: Path, monkeypatch) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(json.dumps({"current_state": "blocked", "latest_failure": {"kind": "authority_divergence", "phase": "execute", "message": "execute terminal success lacks corroborated task completion"}}) + "\n", encoding="utf-8")
    monkeypatch.setattr(chain_module, "_latest_execution_batch_all_tasks_done", lambda _plan_dir: (True, "finalize.json"))
    assert chain_module._rearm_stale_execute_authority_divergence(plan_dir, writer=lambda _text: None)
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "executed"
    assert "latest_failure" not in state
    assert "resume_cursor" not in state
    assert state["meta"]["authority_divergence_recoveries"][0]["authority_reason"] == "finalize.json"


def test_admission_keeps_live_execute_authority_divergence_blocked(tmp_path: Path, monkeypatch) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(json.dumps({"current_state": "blocked", "latest_failure": {"kind": "authority_divergence", "phase": "execute", "message": "execute terminal success lacks corroborated task completion"}}) + "\n", encoding="utf-8")
    monkeypatch.setattr(chain_module, "_latest_execution_batch_all_tasks_done", lambda _plan_dir: (False, "non-authoritative"))
    assert not chain_module._rearm_stale_execute_authority_divergence(plan_dir, writer=lambda _text: None)
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "blocked"


def test_admission_rearms_exact_terminal_review_cursor_mismatch(tmp_path: Path, monkeypatch) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(json.dumps({"current_state": "blocked", "latest_failure": {"kind": "workflow_cursor_mismatch", "phase": "execute", "message": "workflow cursor from last_step expects one of [review] but control projection offered [execute]"}}) + "\n", encoding="utf-8")
    monkeypatch.setattr(chain_module, "_latest_execution_batch_all_tasks_done", lambda _plan_dir: (True, "finalize.json"))
    assert chain_module._rearm_stale_terminal_execute_cursor_mismatch(plan_dir, writer=lambda _text: None)
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "executed"
    assert "latest_failure" not in state


def test_admission_keeps_nonexact_terminal_cursor_mismatch_blocked(tmp_path: Path, monkeypatch) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(json.dumps({"current_state": "blocked", "latest_failure": {"kind": "workflow_cursor_mismatch", "phase": "execute", "message": "different cursor mismatch"}}) + "\n", encoding="utf-8")
    monkeypatch.setattr(chain_module, "_latest_execution_batch_all_tasks_done", lambda _plan_dir: (True, "finalize.json"))
    assert not chain_module._rearm_stale_terminal_execute_cursor_mismatch(plan_dir, writer=lambda _text: None)


def test_committed_clean_file_in_window_counts_zero_added_loc(tmp_path: Path) -> None:
    """Scope-drift must not count a committed-clean tracked file as fully-added.

    Regression for the astrid m2 permanent blocked_by_quality: files committed
    by the fixer/repair lineage inside the milestone window (clean in the
    worktree, no diff vs HEAD) were counted at FULL file line count by
    collect_loc_by_file's fallback, tripping scope_drift=high (>20 LOC
    unclaimed) on every execute closeout even after every task completed.
    """
    from arnold_pipelines.megaplan.receipts.drift import collect_loc_by_file

    repo = tmp_path / "repo"
    base_sha = _init_repo(repo)
    # A committed-clean file inside the milestone window (after the base).
    (repo / "committed_clean.py").write_text("X = 1\n" * 100, encoding="utf-8")
    _commit(repo, "fixer commit")
    loc = collect_loc_by_file(repo, {"committed_clean.py"})
    assert loc["committed_clean.py"] == 0, loc
    # Untracked files still fall back to a full-file count.
    (repo / "untracked.py").write_text("Y = 2\n" * 50, encoding="utf-8")
    loc = collect_loc_by_file(repo, {"untracked.py"})
    assert loc["untracked.py"] == 50, loc
    assert base_sha


def test_terminal_task_write_set_counts_as_claimed_paths(tmp_path: Path) -> None:
    """A done task's admitted write_set is durable ownership even when
    files_changed is empty (FLAG-006 softening) — adopt-miss read-path fix.

    Regression for the astrid m2 kit.py case: T24_impl done with write_set
    admitting astrid/core/conformance/kit.py but files_changed=[]; the scope
    drift reader only read files_changed, so a committed-window file owned by
    a terminal task was mis-read as unclaimed and blocked every closeout.
    """
    from arnold_pipelines.megaplan.execute.aggregation import (
        _collect_finalized_task_claimed_paths,
    )

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T24_impl",
                        "status": "done",
                        "files_changed": [],
                        "write_set": {
                            "paths": [
                                "astrid/core/conformance/kit.py",
                                "tests/v10/conftest.py",
                            ],
                            "complete": True,
                        },
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    claimed = _collect_finalized_task_claimed_paths(plan_dir, tmp_path)
    assert "astrid/core/conformance/kit.py" in claimed
    assert "tests/v10/conftest.py" in claimed


def test_execution_evidence_declared_range_accepts_untracked_present_claim(
    tmp_path: Path,
) -> None:
    """A claimed file present in the working tree is not a phantom claim.

    Regression for occurrence 944dd380108d: under a declared base_ref the
    landed-diff coverage set was narrowed to the committed range, so the
    milestone's untracked-but-present work (committed only by the later
    auto-publish) was reported as "not present in git status" — false, since
    git status did show it — and the chain refused milestone adoption.
    """
    from arnold_pipelines.megaplan.orchestration.execution_evidence import (
        validate_execution_evidence,
    )

    repo = tmp_path / "repo"
    base_sha = _init_repo(repo)
    # Committed after base: stays an unclaimed committed-range finding.
    (repo / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
    _commit(repo, "unrelated implementation")
    # Untracked but present on disk: claimed by the task, must not be phantom.
    (repo / "generated.py").write_text("GENERATED = 1\n", encoding="utf-8")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": ["generated.py", "missing.py"],
                "commands_run": ["pytest -q"],
            }
        ]
    }

    result = validate_execution_evidence(
        finalize_data,
        repo,
        plan_dir=plan_dir,
        base_ref=base_sha,
    )

    findings = result["findings"]
    assert result["files_claimed_worktree_only"] == ["generated.py"]
    assert not any("generated.py" in finding for finding in findings), findings
    phantom = [f for f in findings if "missing.py" in f]
    assert len(phantom) == 1, findings
    assert "absent from both the committed evidence range and working-tree status" in phantom[0]
    unclaimed = [f for f in findings if "other.py" in f]
    assert len(unclaimed) == 1, findings
    assert "Declared committed evidence range contains files not claimed" in unclaimed[0]
