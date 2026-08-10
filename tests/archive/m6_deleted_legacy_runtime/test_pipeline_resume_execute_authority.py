from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan._core.workflow import _resume_execute_authority_failure


def test_resume_later_phase_uses_execute_completion_authority_policy(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_dir = project_dir / ".megaplan" / "plans" / "resume-review-authority"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "config": {"project_dir": str(project_dir)},
                "meta": {"execution_baseline": {"head": "base-sha"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "skipped",
                        "kind": "test",
                        "reviewer_verdict": "deferred_baseline_unavailable",
                        "executor_notes": (
                            "Deferred by harness: baseline_test_failures is null, "
                            "so this no-new-failures checkpoint cannot compare "
                            "against a recorded baseline."
                        ),
                    },
                    {
                        "id": "T9",
                        "status": "blocked",
                        "kind": "docs",
                        "files_changed": ["docs/governance/contracts/compatibility-shims.md"],
                        "commands_run": ["npm run quality:check"],
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    failure = _resume_execute_authority_failure(
        plan_dir,
        cursor={"phase": "review", "retry_strategy": "rerun_phase"},
        guard="before_later_phase_dispatch",
    )

    assert failure is None
