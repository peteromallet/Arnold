"""Acceptance test #3 — fan-out judges demo lands the exact 3+1+1 artifact set."""

from __future__ import annotations

import json
from pathlib import Path


def test_demo_judges_artifact_set(tmp_path: Path) -> None:
    from megaplan._pipeline.demo_judges import run_demo

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

    result = run_demo(fixture, tmp_path)

    expected = [
        tmp_path / "judges" / "judge_clarity" / "verdict.json",
        tmp_path / "judges" / "judge_concreteness" / "verdict.json",
        tmp_path / "judges" / "judge_brevity" / "verdict.json",
        tmp_path / "synthesis" / "synthesis.md",
        tmp_path / "state.json",
    ]
    for path in expected:
        assert path.exists(), f"missing artifact: {path}"

    for verdict_path in expected[:3]:
        data = json.loads(verdict_path.read_text())
        assert isinstance(data, dict)
        assert isinstance(data.get("score"), float)

    state = json.loads((tmp_path / "state.json").read_text())
    assert "judges" in state

    verdicts_found = list(tmp_path.rglob("verdict.json"))
    syntheses_found = list(tmp_path.rglob("synthesis.md"))
    assert len(verdicts_found) == 3, f"expected 3 verdict.json, got {verdicts_found}"
    assert len(syntheses_found) == 1, f"expected 1 synthesis.md, got {syntheses_found}"

    assert result.get("final_stage") == "synthesis"
