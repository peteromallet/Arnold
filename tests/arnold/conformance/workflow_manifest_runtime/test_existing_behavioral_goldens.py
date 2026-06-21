from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from arnold.conformance.workflow_manifest_runtime import GoldenRegressionRule

BEHAVIORAL_GOLDENS = (
    "tests/fixtures/golden/pipeline_fresh_run.json",
    "tests/fixtures/golden/pipeline_iterate.json",
    "tests/fixtures/golden/pipeline_resume_after_finalize.json",
)


@pytest.mark.parametrize("fixture", BEHAVIORAL_GOLDENS)
def test_existing_behavioral_goldens_do_not_change_without_explanation(fixture: str) -> None:
    path = Path(fixture)
    old = subprocess.run(
        ["git", "show", f"origin/main:{fixture}"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    new = path.read_text(encoding="utf-8")
    rule = GoldenRegressionRule(path, path.with_suffix(path.suffix + ".explanation.md"))

    assert rule.is_explained(old_text=old, new_text=new)
