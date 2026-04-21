from __future__ import annotations

import pytest

import megaplan
import megaplan.workers
from megaplan.workers import WorkerResult
from tests.conftest import PlanFixture, load_state, read_json


def test_handle_finalize_validates_payload_shape(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )

    valid_payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the change",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [
            {
                "id": "SC1",
                "task_id": "T1",
                "question": "Did it work?",
                "executor_note": "",
                "verdict": "",
            }
        ],
        "meta_commentary": "ok",
    }
    worker = WorkerResult(
        payload=valid_payload,
        raw_output="valid finalize payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-valid",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    response = megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_FINALIZED
    assert read_json(plan_fixture.plan_dir / "finalize.json")["tasks"][0]["status"] == "pending"


def test_handle_finalize_rejects_invalid_payload(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )

    invalid_worker = WorkerResult(
        payload={
            "tasks": [
                {
                    "id": "T1",
                    "description": "Broken finalize task",
                    "depends_on": [],
                    "status": "done",
                    "executor_notes": "",
                    "files_changed": [],
                    "commands_run": [],
                    "evidence_files": [],
                    "reviewer_verdict": "",
                }
            ],
            "watch_items": [],
            "sense_checks": [],
        },
        raw_output="invalid finalize payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-invalid",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (invalid_worker, "claude", "persistent", False),
    )

    with pytest.raises(megaplan.CliError, match="status `pending`"):
        megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    state = load_state(plan_fixture.plan_dir)
    assert state["history"][-1]["result"] == "error"


def test_finalize_snapshot_remains_pending_after_execute(plan_fixture: PlanFixture) -> None:
    from megaplan._core import load_finalize_snapshot

    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )

    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    snapshot_before_execute = load_finalize_snapshot(plan_fixture.plan_dir)
    assert (plan_fixture.plan_dir / "finalize_snapshot.json").exists()
    assert all(task["status"] == "pending" for task in snapshot_before_execute["tasks"])

    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    finalize_after_execute = read_json(plan_fixture.plan_dir / "finalize.json")
    snapshot_after_execute = load_finalize_snapshot(plan_fixture.plan_dir)

    assert all(task["status"] == "done" for task in finalize_after_execute["tasks"])
    assert snapshot_after_execute == snapshot_before_execute
    assert all(task["status"] == "pending" for task in snapshot_after_execute["tasks"])


def test_render_final_md_pending_partially_done_and_reviewed_states() -> None:
    from megaplan._core import render_final_md

    pending = {
        "tasks": [
            {
                "id": "T1",
                "description": "Do work",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": ["Watch this."],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "question": "Did it work?", "executor_note": "", "verdict": ""}
        ],
        "meta_commentary": "Pending state.",
    }
    partial = {
        **pending,
        "tasks": [
            {
                **pending["tasks"][0],
                "status": "done",
                "executor_notes": "Implemented.",
                "files_changed": ["megaplan/handlers.py"],
            }
        ],
        "sense_checks": [
            {
                **pending["sense_checks"][0],
                "executor_note": "Confirmed execute evidence coverage.",
            }
        ],
    }
    reviewed = {
        **partial,
        "tasks": [
            {
                **partial["tasks"][0],
                "reviewer_verdict": "Pass",
                "evidence_files": ["megaplan/handlers.py"],
            }
        ],
        "sense_checks": [
            {
                **partial["sense_checks"][0],
                "verdict": "Confirmed.",
            }
        ],
    }

    pending_md = render_final_md(pending)
    partial_md = render_final_md(partial)
    reviewed_md = render_final_md(reviewed)

    assert "# Execution Checklist" in pending_md
    assert "## Watch Items" in pending_md
    assert "## Sense Checks" in pending_md
    assert "## Meta" in pending_md
    assert "- [ ] **T1:** Do work" in pending_md
    assert "- [x] **T1:** Do work" in partial_md
    assert "Executor notes: Implemented." in partial_md
    assert "Files changed:" in partial_md
    assert "Executor note: Confirmed execute evidence coverage." in partial_md
    assert "Reviewer verdict: Pass" in reviewed_md
    assert "Evidence files:" in reviewed_md
    assert "Verdict: Confirmed." in reviewed_md


def test_render_final_md_phase_marks_gaps_only_when_due() -> None:
    from megaplan._core import render_final_md

    data = {
        "tasks": [
            {
                "id": "T1",
                "description": "Do work",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
            {
                "id": "T2",
                "description": "Ship work",
                "depends_on": ["T1"],
                "status": "done",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
        ],
        "watch_items": [],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "question": "Did it work?", "executor_note": "", "verdict": ""},
            {"id": "SC2", "task_id": "T2", "question": "Was it reviewed?", "executor_note": "", "verdict": ""},
        ],
        "meta_commentary": "Status overview.",
    }

    finalize_md = render_final_md(data)
    execute_md = render_final_md(data, phase="execute")
    review_md = render_final_md(data, phase="review")

    assert "Executor notes: [MISSING]" not in finalize_md
    assert "Reviewer verdict: [PENDING]" not in finalize_md
    assert "## Coverage Gaps" not in finalize_md
    assert "Executor notes: [MISSING]" in execute_md
    assert "Reviewer verdict: [PENDING]" not in execute_md
    assert "Tasks without executor updates: 1" in execute_md
    assert "Executor notes missing: 1" in execute_md
    assert "Sense-check acknowledgments missing: 2" in execute_md
    assert "Reviewer verdict: [PENDING]" in review_md
    assert "Verdict: [PENDING]" in review_md
    assert "Reviewer verdicts pending: 2" in review_md
    assert "Sense-check verdicts pending: 2" in review_md
