from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arnold_pipelines.megaplan.prompts.critique import _revise_retry_feedback
from arnold_pipelines.megaplan.receipts.extractors import load_and_extract
from arnold_pipelines.megaplan.receipts.schema import upstream_artifact_hashes


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_critique_custody_and_metrics_follow_latest_same_iteration_plan(
    tmp_path: Path,
) -> None:
    primary = "# Stale plan\n\n## Step 1: Old\n"
    current = "# Current plan\n\n## Step 1: New\n\n- [ ] current task\n"
    (tmp_path / "plan_v7.md").write_text(primary, encoding="utf-8")
    (tmp_path / "plan_v7c.md").write_text(current, encoding="utf-8")
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "iteration": 7,
                "plan_versions": [
                    {"version": 7, "file": "plan_v7.md", "hash": _sha256(primary)},
                    {"version": 7, "file": "plan_v7c.md", "hash": _sha256(current)},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert upstream_artifact_hashes(tmp_path, "critique", 7) == [
        f"sha256:{_sha256(current)}"
    ]
    metrics = load_and_extract(tmp_path, "plan", 7)
    assert metrics["task_count"] == 1


def test_revise_retry_feedback_surfaces_the_exact_structural_failure() -> None:
    state = {
        "history": [
            {
                "step": "revise",
                "result": "error",
                "message": "Revise output failed structural validation: Plan must include at least one step section",
            }
        ]
    }

    feedback = _revise_retry_feedback(state)  # type: ignore[arg-type]

    assert "PRIOR REVISE ATTEMPT FAILED STRUCTURAL VALIDATION" in feedback
    assert "Plan must include at least one step section" in feedback
    assert "## Step 1:" in feedback
