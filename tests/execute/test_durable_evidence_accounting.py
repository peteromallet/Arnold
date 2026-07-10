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
