from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan._core.state import write_plan_state


def _base_state(current_state: str) -> dict:
    return {
        "schema_version": 1,
        "current_state": current_state,
        "history": [],
        "meta": {},
        "sessions": {},
        "config": {},
    }


def test_execute_success_atomically_arms_recoverable_review_handoff(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution.json").write_text('{"output":"done"}', encoding="utf-8")
    state = _base_state("executed")
    state["active_step"] = {"phase": "execute", "worker_pid": 999_999}
    state["history"].append({"step": "execute", "result": "success"})

    persisted = write_plan_state(plan_dir, mode="replace", state=state)
    on_disk = json.loads((plan_dir / "state.json").read_text())

    assert persisted == on_disk
    assert "active_step" not in on_disk
    handoff = on_disk["pending_phase_handoff"]
    assert handoff["from_phase"] == "execute"
    assert handoff["to_phase"] == "review"
    assert handoff["status"] == "recovery_required"
    assert handoff["recovery_action"] == "resume_review"


def test_review_claim_and_crossing_are_durable_state_transitions(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution.json").write_text('{"output":"done"}', encoding="utf-8")
    state = _base_state("executed")
    state["history"].append({"step": "execute", "result": "success"})
    armed = write_plan_state(plan_dir, mode="replace", state=state)

    claimed = write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={
            "active_step": {
                "phase": "review",
                "run_id": "review-run",
                "worker_pid": 123,
            }
        },
    )
    assert claimed["pending_phase_handoff"]["status"] == "claimed"
    assert claimed["pending_phase_handoff"]["claim_run_id"] == "review-run"

    crossed_state = dict(claimed)
    crossed_state["current_state"] = "done"
    crossed_state["history"] = [
        *claimed["history"],
        {"step": "review", "result": "success"},
    ]
    crossed = write_plan_state(plan_dir, mode="replace", state=crossed_state)

    assert "pending_phase_handoff" not in crossed
    receipt = crossed["meta"]["phase_handoff_receipts"][-1]
    assert receipt["status"] == "crossed"
    assert receipt["crossed_to_state"] == "done"
