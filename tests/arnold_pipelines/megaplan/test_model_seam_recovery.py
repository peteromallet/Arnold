from __future__ import annotations

import json

from arnold.pipeline import StepInvocation
from arnold_pipelines.megaplan.model_seam import capture_step_output


def test_plan_recovery_prefers_later_structured_plan_over_summary_payload(
    tmp_path,
) -> None:
    """Plan capture should not promote an early summary when raw output has the real plan."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "plan_output.json"

    summary_payload = {
        "plan": "Created the M2 implementation plan from the worker prompt.",
        "questions": [],
        "success_criteria": [{"criterion": "Cleanup is planned", "priority": "must"}],
        "assumptions": [],
    }
    structured_payload = {
        "plan": "\n".join(
            [
                "# Implementation Plan: M2 Parity And Delete",
                "",
                "## Overview",
                "",
                "Move callers to the canonical package, prove parity, then delete the duplicate root.",
                "",
                "## Phase 1: Canonical Migration",
                "",
                "### Step 1: Establish Baseline",
                "",
                "1. Scan `arnold_pipelines/megaplan` and `tests` for legacy imports.",
                "2. Record the current parity status in `.megaplan` artifacts.",
                "",
                "## Validation Order",
                "",
                "1. Run `python -m pytest tests/arnold_pipelines/megaplan/test_model_seam_recovery.py -q`.",
            ]
        ),
        "questions": [],
        "success_criteria": [{"criterion": "Cleanup has executable steps", "priority": "must"}],
        "assumptions": [],
    }
    output_path.write_text(json.dumps(summary_payload), encoding="utf-8")
    raw = "\n".join(
        [
            json.dumps({"type": "message", "content": json.dumps(summary_payload)}),
            json.dumps({"type": "message", "content": json.dumps(structured_payload)}),
        ]
    )

    invocation = StepInvocation(
        kind="model",
        metadata={
            "capture_recovery": {
                "step": "plan",
                "plan_dir": str(plan_dir),
                "output_path": str(output_path),
                "prefer_output_file": True,
            },
        },
    )

    outcome = capture_step_output(invocation, raw)

    assert outcome.legacy_payload == structured_payload
    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:raw_output",
    )
