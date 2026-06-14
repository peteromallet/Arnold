from __future__ import annotations

import json
from pathlib import Path

from arnold.pipelines.megaplan.chain import _latest_execution_batch_all_tasks_done

_BASELINE_DESC = (
    "Introduce no new failures vs the recorded baseline; do not try to make "
    "pre-existing baseline failures pass; do not narrow to individual functions."
)


def _write_plan(plan_dir: Path, *, finalize_tasks: list[dict], baseline) -> None:
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "id": "T1",
                        "status": "done",
                        "files_changed": ["docs/m1.md"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "docs").mkdir(exist_ok=True)
    (plan_dir / "docs" / "m1.md").write_text("done\n", encoding="utf-8")
    (plan_dir / "finalize.json").write_text(
        json.dumps({"baseline_test_failures": baseline, "tasks": finalize_tasks}),
        encoding="utf-8",
    )


def test_null_baseline_checkpoint_does_not_block_completion(tmp_path: Path) -> None:
    _write_plan(
        tmp_path,
        baseline=None,
        finalize_tasks=[
            {"id": "T1", "status": "done", "files_changed": ["docs/m1.md"]},
            {"id": "T10", "status": "blocked", "description": _BASELINE_DESC},
        ],
    )

    all_done, reason = _latest_execution_batch_all_tasks_done(tmp_path)

    assert all_done is True, reason


def test_real_incomplete_non_baseline_task_still_blocks(tmp_path: Path) -> None:
    _write_plan(
        tmp_path,
        baseline=None,
        finalize_tasks=[
            {"id": "T1", "status": "done", "files_changed": ["docs/m1.md"]},
            {"id": "T10", "status": "blocked", "description": _BASELINE_DESC},
            {"id": "T2", "status": "blocked", "description": "Implement the runner."},
        ],
    )

    all_done, reason = _latest_execution_batch_all_tasks_done(tmp_path)

    assert all_done is False
    assert "T2" in reason


def test_with_real_baseline_normal_block_still_applies(tmp_path: Path) -> None:
    _write_plan(
        tmp_path,
        baseline=["tests/test_x.py::test_y"],
        finalize_tasks=[
            {"id": "T1", "status": "done", "files_changed": ["docs/m1.md"]},
            {"id": "T10", "status": "blocked", "description": _BASELINE_DESC},
        ],
    )

    all_done, reason = _latest_execution_batch_all_tasks_done(tmp_path)

    assert all_done is False
    assert "T10" in reason
