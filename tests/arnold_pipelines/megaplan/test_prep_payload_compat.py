from __future__ import annotations

import json

from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan.model_seam import capture_step_output
from arnold_pipelines.megaplan.prompts._shared import _render_prep_block
from arnold_pipelines.megaplan.receipts.extractors import prep_metrics


def test_prep_capture_accepts_suggested_approach_array() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "validation_step": "prep",
            "compatibility_validation_step": "prep",
        },
    )

    outcome = capture_step_output(
        invocation,
        {
            "skip": False,
            "task_summary": "Ship fallback chains.",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": ["Author the design doc.", "Add baseline tests."],
        },
    )

    assert outcome.legacy_payload["suggested_approach"] == [
        "Author the design doc.",
        "Add baseline tests.",
    ]


def test_render_prep_block_renders_suggested_approach_array(tmp_path) -> None:
    (tmp_path / "prep.json").write_text(
        json.dumps(
            {
            "task_summary": "Ship fallback chains.",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": ["Author the design doc.", "Add baseline tests."],
            }
        ),
        encoding="utf-8",
    )
    brief, instruction = _render_prep_block(tmp_path)

    assert "### Suggested Approach" in brief
    assert "- Author the design doc." in brief
    assert "- Add baseline tests." in brief
    assert "default working context" in instruction


def test_prep_metrics_treats_empty_suggested_approach_array_as_missing() -> None:
    assert prep_metrics({"suggested_approach": []})["suggested_approach_present"] is False
    assert prep_metrics({"suggested_approach": ["Phase 0"]})["suggested_approach_present"] is True
