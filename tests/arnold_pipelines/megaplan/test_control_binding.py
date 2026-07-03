from __future__ import annotations

from arnold_pipelines.megaplan.planning.control_binding import (
    planning_control_binding,
    planning_run_state_view,
)


def test_blocked_review_recovery_does_not_project_illegal_rerun() -> None:
    state = {
        "name": "demo",
        "current_state": "blocked",
        "config": {},
        "resume_cursor": {
            "phase": "review",
            "retry_strategy": "manual_review",
        },
        "latest_failure": {
            "kind": "blocked_recovery_not_resolved",
            "phase": "recover-blocked",
            "message": "recover-blocked requires every current blocker to be explicitly resolved as non-terminal",
        },
    }

    binding = planning_control_binding()
    targets = binding.recover_targets(planning_run_state_view(state))

    assert [target.id for target in targets] == ["recover-blocked"]
