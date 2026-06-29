from __future__ import annotations

import json
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


def _push_base_ref() -> str:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            before = json.loads(Path(event_path).read_text(encoding="utf-8")).get("before")
        except (OSError, json.JSONDecodeError):
            before = None
        if before and set(before) != {"0"}:
            subprocess.run(
                ["git", "fetch", "--depth=1", "origin", before],
                check=False,
                capture_output=True,
            )
            return before
    return "origin/main"


def _base_ref() -> str:
    # In PR CI, compare against the target branch; locally fall back to origin/main.
    # Push CI does not set GITHUB_BASE_REF, so compare against the pushed-from SHA.
    base = os.environ.get("GITHUB_BASE_REF")
    if base:
        subprocess.run(["git", "fetch", "origin", base], check=False, capture_output=True)
        return f"origin/{base}"
    if os.environ.get("GITHUB_EVENT_NAME") == "push":
        return _push_base_ref()
    return "origin/main"


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
