from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from arnold.conformance.workflow_manifest_runtime import GoldenRegressionRule

BEHAVIORAL_GOLDENS = (
    "tests/fixtures/golden/pipeline_fresh_run.json",
    "tests/fixtures/golden/pipeline_iterate.json",
    "tests/fixtures/golden/pipeline_resume_after_finalize.json",
)


def _base_ref() -> str:
    # In CI, compare against the PR target branch; locally fall back to origin/main.
    base = os.environ.get("GITHUB_BASE_REF", "main")
    ref = f"origin/{base}"
    # Make sure the base ref is available in CI (actions/checkout may not fetch it).
    if "GITHUB_BASE_REF" in os.environ:
        subprocess.run(["git", "fetch", "origin", base], check=False, capture_output=True)
    return ref


@pytest.mark.parametrize("fixture", BEHAVIORAL_GOLDENS)
def test_existing_behavioral_goldens_do_not_change_without_explanation(fixture: str) -> None:
    path = Path(fixture)
    old = subprocess.run(
        ["git", "show", f"{_base_ref()}:{fixture}"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    new = path.read_text(encoding="utf-8")
    rule = GoldenRegressionRule(path, path.with_suffix(path.suffix + ".explanation.md"))

    assert rule.is_explained(old_text=old, new_text=new)
