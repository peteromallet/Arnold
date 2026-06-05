"""Acceptance test #3 — fan-out judges demo lands the exact 3+1+1 artifact set."""

from __future__ import annotations

import json
from pathlib import Path


def test_demo_judges_artifact_set(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._pipeline.demo_judges import run_demo

    fixture = tmp_path / "fixture.md"
    fixture.write_text(
        "The pipeline executor walks stages and dispatches steps in order. "
        "Each step writes artifacts under the plan directory it was handed. "
        "Judges score the fixture document along independent rubric axes. "
        "The synthesis stage merges every judge verdict into a single report. "
        "Sprint One freezes the dataclass shapes for downstream Sprint Two ports. "
        "The fan-out judges demo proves the executor can express parallel "
        "fan-out plus a barrier-join entirely through the new primitives. "
        "Three deterministic judges run concurrently against the same fixture "
        "and the synthesis stage merges their verdicts deterministically. "
        "This fixture exists purely to drive the rubric calculations and the "
        "shape of the artifacts written under the supplied plan directory."
    )

    artifact_root = tmp_path / "artifacts"
    result = run_demo(fixture, artifact_root)

    expected = {
        "judges/judge_clarity/verdict.json",
        "judges/judge_concreteness/verdict.json",
        "judges/judge_brevity/verdict.json",
        "synthesis/synthesis.md",
        "state.json",
        "events.ndjson",
        ".events.seq",
    }
    found = {
        path.relative_to(artifact_root).as_posix()
        for path in artifact_root.rglob("*")
        if path.is_file()
    }
    assert found == expected

    for verdict_path in sorted((artifact_root / "judges").rglob("verdict.json")):
        data = json.loads(verdict_path.read_text())
        assert isinstance(data, dict)
        assert isinstance(data.get("score"), float)

    state = json.loads((artifact_root / "state.json").read_text())
    assert "judges" in state
    assert {
        Path(path).relative_to(artifact_root).as_posix()
        for path in state["judge_verdict_paths"]
    } == {
        "judges/judge_clarity/verdict.json",
        "judges/judge_concreteness/verdict.json",
        "judges/judge_brevity/verdict.json",
    }

    assert result.get("final_stage") == "synthesis"
