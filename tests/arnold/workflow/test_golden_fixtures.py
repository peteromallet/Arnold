from __future__ import annotations

import json
from pathlib import Path

REQUIRED_CASES = (
    "fresh-planning.json",
    "gate-iteration.json",
    "tiebreaker.json",
    "human-suspension.json",
    "finalize-execute-review.json",
    "override-fallback.json",
    "resume-sensitive.json",
)


def test_workflow_manifest_runtime_fixture_cases_are_present_and_normalized() -> None:
    root = Path("tests/fixtures/golden/workflow_manifest_runtime")

    for name in REQUIRED_CASES:
        path = root / name
        assert path.exists(), name
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema_version"] == "workflow-manifest-runtime.golden.v1"
        assert data["normalization"]["volatile_fields"] == sorted(
            data["normalization"]["volatile_fields"]
        )
