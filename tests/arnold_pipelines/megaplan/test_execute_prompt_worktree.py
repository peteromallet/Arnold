from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.prompts.execute import _execute_batch_prompt


def test_execute_batch_prompt_requires_verification_in_project_worktree(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "worktree-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "description": "Verify from the session worktree.",
                        "files": [],
                        "commands": [],
                    }
                ],
                "sense_checks": [],
            }
        ),
        encoding="utf-8",
    )
    state = {
        "config": {
            "plan": "worktree-plan",
            "plan_name": "worktree-plan",
            "project_dir": str(tmp_path),
            "mode": "code",
        },
        "meta": {},
        "current_state": "finalized",
    }

    prompt = _execute_batch_prompt(state, plan_dir, ["T1"], root=tmp_path)

    assert "All terminal verification commands must run from the Project directory" in prompt
    assert f"(`{tmp_path}`)" in prompt
    assert "Do not `cd` to `/workspace/arnold`" in prompt
    assert "editable-engine mirror" in prompt


def test_execute_batch_prompt_annotates_rework_tasks_with_review_directives(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "rework-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "description": "Old finalize prose that no longer matches the rework target.",
                        "files": [],
                        "commands": [],
                    }
                ],
                "sense_checks": [],
            }
        ),
        encoding="utf-8",
    )
    state = {
        "config": {
            "plan": "rework-plan",
            "plan_name": "rework-plan",
            "project_dir": str(tmp_path),
            "mode": "code",
        },
        "meta": {},
        "current_state": "finalized",
    }

    prompt = _execute_batch_prompt(
        state,
        plan_dir,
        ["T1"],
        root=tmp_path,
        rework_context={
            "rework_items": [
                {
                    "task_id": "T1",
                    "issue": "Rewrite the metadata file instead of replaying the old artifact-copy step.",
                    "expected": "plan_v3.meta.json carries only the 21 approved selectors.",
                    "actual": "The stale 312-selector expansion is still present.",
                    "evidence_file": ".megaplan/plans/example/plan_v3.meta.json",
                    "source": "review_metadata_check",
                }
            ]
        },
    )

    assert '"review_rework_directives"' in prompt
    assert "Rewrite the metadata file instead of replaying the old artifact-copy step." in prompt
    assert '"review_rework_evidence_files"' in prompt
    assert ".megaplan/plans/example/plan_v3.meta.json" in prompt
    assert "higher-authority instructions than stale original task prose" in prompt
