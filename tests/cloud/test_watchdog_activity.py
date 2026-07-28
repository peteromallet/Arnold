from __future__ import annotations

from arnold_pipelines.megaplan.cloud.watchdog import (
    assess_watchdog_accepted_progress,
)


def test_assess_watchdog_accepted_progress_emits_drift_for_repair_activity() -> None:
    result = assess_watchdog_accepted_progress(
        {
            "status": "repairing",
            "repairing": True,
            "repair_state": {"active": True},
            "accepted_progress": {
                "waiting_for_acceptance": False,
                "final_milestone_accepted": True,
                "acceptance_required": True,
                "accepted_milestones": ["m8"],
            },
        },
        chain_complete=True,
        is_fail_closed=True,
        has_declared_successors=True,
    )

    assert result["activity_classification"] == "accepted_progress"
    assert result["drift_detected"] is True
    assert result["drift_reason"] == "accepted_progress_conflicts_with_repair_activity"
