from __future__ import annotations

from arnold.pipelines.megaplan.execute.core import _merge_batch_results


def test_merge_batch_results_propagates_creative_stance_and_stop_signal():
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "description": "Write the opening image.",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "sections_written": [],
            }
        ],
        "sense_checks": [
            {
                "id": "SC1",
                "task_id": "T1",
                "question": "Does the image land?",
                "executor_note": "",
            }
        ],
    }
    stance = {
        "challenge_engaged": "I engaged poem-cut-explanation.",
        "angle_taken": "I chose the image because it exposes the lie.",
        "what_changed": "I killed the summary line.",
    }
    stop_signal = {"requested": False, "defense": ""}
    issues: list[str] = []

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload={
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Wrote the opening image.",
                    "sections_written": ["opening_image"],
                    "stance": stance,
                    "stop_signal": stop_signal,
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed the image lands."}
            ],
        },
        batch_task_ids=["T1"],
        batch_sense_check_ids=["SC1"],
        issues=issues,
        mode="creative",
    )

    assert merged == (1, 1, 1, 1)
    task = finalize_data["tasks"][0]
    assert task["stance"] == stance
    assert task["stop_signal"] == stop_signal
    assert issues == []


def test_merge_batch_results_soft_records_stance_violations():
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "description": "Write the opening image.",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "sections_written": [],
            }
        ],
        "sense_checks": [],
    }
    issues: list[str] = []

    _merge_batch_results(
        finalize_data=finalize_data,
        payload={
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Wrote the opening image.",
                    "sections_written": ["opening_image"],
                    "stance": {
                        "challenge_engaged": "The provocation was engaged.",
                        "angle_taken": "The line was attempted for clarity.",
                        "what_changed": "The poem changed.",
                    },
                    "stop_signal": {"requested": False, "defense": ""},
                }
            ],
            "sense_check_acknowledgments": [],
        },
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        issues=issues,
        mode="creative",
    )

    task = finalize_data["tasks"][0]
    assert "stance_violations" in task
    assert any("first person" in violation for violation in task["stance_violations"])
    assert any("hedging verb" in violation for violation in task["stance_violations"])
    assert task["status"] == "done"
