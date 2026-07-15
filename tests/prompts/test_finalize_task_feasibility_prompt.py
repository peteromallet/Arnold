from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.prompts.finalize import _finalize_prompt


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _minimal_state(tmp_path: Path) -> dict[str, Any]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (plan_dir / "plan_v1.md").write_text(
        "# Plan\n\n## Step 1: Change the behavior\n",
        encoding="utf-8",
    )
    _write_json(
        plan_dir / "plan_v1.meta.json",
        {"success_criteria": [{"criterion": "Focused behavior passes."}]},
    )
    _write_json(
        plan_dir / "gate.json",
        {
            "recommendation": "PROCEED",
            "rationale": "Ready.",
            "signals_assessment": "Clear.",
            "warnings": [],
            "settled_decisions": [],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
            "north_star_actions": [],
        },
    )
    return {
        "name": "demo",
        "idea": "Change the behavior.",
        "iteration": 1,
        "config": {
            "project_dir": str(project_dir),
            "mode": "code",
            "robustness": "full",
        },
        "meta": {},
        "sessions": {},
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "history": [],
    }


def test_finalize_prompt_forbids_routing_only_dependencies_and_model_full_suite(
    tmp_path: Path,
) -> None:
    state = _minimal_state(tmp_path)
    prompt = _finalize_prompt(state, tmp_path / "plan", root=tmp_path)

    assert "`depends_on` is correctness authority, not a routing hint" in prompt
    assert "Never add an edge merely to isolate a model tier" in prompt
    assert "A ready frontier wider than 5 is valid" in prompt
    assert "linearize via `depends_on`" not in prompt
    assert "Do NOT add a final integration/full-suite test task" in prompt
    assert "Narrow verification should consume at most 2 minutes" in prompt
    assert "at most one diagnostic rerun" in prompt
    assert "`task_contract_version` to `2`" in prompt
    assert "integer 1-15" in prompt
    assert "at most 3 changed-behavior selectors" in prompt
