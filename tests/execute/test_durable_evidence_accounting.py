from __future__ import annotations

import json
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.execute.aggregation import _compute_execute_scope_drift
from arnold_pipelines.megaplan.execute.batch import _durably_evidenced_finalized_task_ids
from arnold_pipelines.megaplan.orchestration.execution_evidence import (
    apply_authoritative_execute_overrides,
)


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
    assert _durably_evidenced_finalized_task_ids(finalized_tasks) == {"T1"}


def test_old_batch_cannot_replace_terminal_finalize_commands(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "execution_batch_8.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T8",
                        "status": "done",
                        "files_changed": ["runtime.py"],
                        "commands_run": ["python _obsolete_ad_hoc_gate.py"],
                    }
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
                "status": "done",
                "files_changed": ["runtime.py"],
                "commands_run": ["python -m py_compile runtime.py", "pytest tests/test_runtime.py -q"],
                "executor_notes": "Current verification completed.",
            }
        ],
        "sense_checks": [],
    }

    reconciled = apply_authoritative_execute_overrides(finalized, plan_dir=plan_dir)

    assert reconciled["tasks"][0]["commands_run"] == [
        "python -m py_compile runtime.py",
        "pytest tests/test_runtime.py -q",
    ]


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
