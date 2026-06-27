from __future__ import annotations

from arnold_pipelines.megaplan.workers.hermes import _recover_plan_payload_from_raw_markdown


def test_plan_payload_recovers_from_valid_raw_markdown() -> None:
    raw_plan = "\n".join(
        [
            "# Implementation Plan: Fix",
            "",
            "## Overview",
            "",
            "Repair the worker path.",
            "",
            "## Main Phase",
            "",
            "### Step 1: Patch worker (`arnold_pipelines/megaplan/workers/hermes.py`)",
            "",
            "1. Promote valid raw markdown into the plan payload.",
            "",
            "## Validation Order",
            "",
            "1. Run `python -m pytest tests/arnold_pipelines/megaplan/test_hermes_plan_recovery.py`.",
        ]
    )

    recovered = _recover_plan_payload_from_raw_markdown(
        {
            "plan": "summary only",
            "questions": ["q"],
            "success_criteria": [{"criterion": "passes", "priority": "must"}],
            "assumptions": ["a"],
        },
        raw_plan,
    )

    assert recovered is not None
    assert recovered["plan"].startswith("# Implementation Plan: Fix")
    assert recovered["questions"] == ["q"]
    assert recovered["success_criteria"] == [{"criterion": "passes", "priority": "must"}]
    assert recovered["assumptions"] == ["a"]


def test_plan_payload_does_not_recover_raw_without_steps() -> None:
    recovered = _recover_plan_payload_from_raw_markdown(
        {"questions": []},
        "# Summary\n\nNo implementation steps here.",
    )

    assert recovered is None
