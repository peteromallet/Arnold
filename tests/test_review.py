from __future__ import annotations

import json

import pytest

import arnold.pipelines.megaplan as megaplan
import arnold.pipelines.megaplan.execute.aggregation as megaplan_execute_aggregation
import arnold.pipelines.megaplan.execute.batch as megaplan_execute_batch
import arnold.pipelines.megaplan.execute.core as megaplan_execute_core
import arnold.pipelines.megaplan.handlers as megaplan_handlers
import arnold.pipelines.megaplan.execute.merge as megaplan_execute_merge
import arnold.pipelines.megaplan.workers as megaplan_workers
from arnold.pipelines.megaplan.workers import WorkerResult

from tests.conftest import PlanFixture, load_state, read_json


def test_validate_merge_inputs_filters_malformed_entries() -> None:
    valid = megaplan.execute.merge._validate_merge_inputs(
        [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Implemented.",
                "files_changed": ["megaplan/handlers.py"],
                "commands_run": ["pytest tests/test_megaplan.py"],
            },
            {"task_id": "T2", "status": 1, "executor_notes": "Bad type"},
            {"task_id": "T3", "executor_notes": "Missing status"},
            "bad-entry",
        ],
        required_fields=("task_id", "status", "executor_notes", "files_changed", "commands_run"),
        enum_fields={"status": {"done", "skipped", "blocked"}},
        array_fields=("files_changed", "commands_run"),
        label="task_updates",
    )
    empty = megaplan.execute.merge._validate_merge_inputs(
        [],
        required_fields=("task_id", "reviewer_verdict"),
        label="task_verdicts",
    )

    assert valid == [
        {
            "task_id": "T1",
            "status": "done",
            "executor_notes": "Implemented.",
            "files_changed": ["megaplan/handlers.py"],
            "commands_run": ["pytest tests/test_megaplan.py"],
        }
    ]
    assert empty == []


def test_validate_merge_inputs_rejects_empty_required_content() -> None:
    deviations: list[str] = []
    valid = megaplan.execute.merge._validate_merge_inputs(
        [
            {"task_id": "T1", "status": "done", "executor_notes": "  "},
            {"task_id": "T2", "status": "done", "executor_notes": "\t"},
            {"task_id": "T3", "status": "skipped", "executor_notes": "Investigated and skipped."},
        ],
        required_fields=("task_id", "status", "executor_notes"),
        enum_fields={"status": {"done", "skipped", "blocked"}},
        nonempty_fields={"executor_notes"},
        deviations=deviations,
        label="task_updates",
    )

    assert valid == [{"task_id": "T3", "status": "skipped", "executor_notes": "Investigated and skipped."}]
    assert deviations == [
        "Skipped task_updates[0]: 'executor_notes' must not be empty.",
        "Skipped task_updates[1]: 'executor_notes' must not be empty.",
    ]


def test_validate_merge_inputs_accepts_array_fields() -> None:
    deviations: list[str] = []
    valid = megaplan.execute.merge._validate_merge_inputs(
        [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Implemented.",
                "files_changed": ["megaplan/handlers.py"],
                "commands_run": ["pytest tests/test_megaplan.py"],
            },
            {
                "task_id": "T2",
                "status": "done",
                "executor_notes": "Bad arrays.",
                "files_changed": "megaplan/handlers.py",
                "commands_run": [],
            },
        ],
        required_fields=("task_id", "status", "executor_notes", "files_changed", "commands_run"),
        enum_fields={"status": {"done", "skipped", "blocked"}},
        nonempty_fields={"executor_notes"},
        array_fields=("files_changed", "commands_run"),
        deviations=deviations,
        label="task_updates",
    )

    assert valid == [
        {
            "task_id": "T1",
            "status": "done",
            "executor_notes": "Implemented.",
            "files_changed": ["megaplan/handlers.py"],
            "commands_run": ["pytest tests/test_megaplan.py"],
        }
    ]
    assert deviations == [
        "Skipped malformed task_updates[1]: invalid field types or enum values.",
    ]


def test_validate_merge_inputs_rejects_empty_reviewer_verdict() -> None:
    deviations: list[str] = []
    valid = megaplan.execute.merge._validate_merge_inputs(
        [
            {"task_id": "T1", "reviewer_verdict": ""},
            {"task_id": "T2", "reviewer_verdict": "   "},
            {"task_id": "T3", "reviewer_verdict": "Looks good."},
        ],
        required_fields=("task_id", "reviewer_verdict"),
        nonempty_fields={"reviewer_verdict"},
        deviations=deviations,
        label="task_verdicts",
    )

    assert valid == [{"task_id": "T3", "reviewer_verdict": "Looks good."}]
    assert deviations == [
        "Skipped task_verdicts[0]: 'reviewer_verdict' must not be empty.",
        "Skipped task_verdicts[1]: 'reviewer_verdict' must not be empty.",
    ]


def test_validate_merge_inputs_rejects_empty_sense_check_verdict() -> None:
    deviations: list[str] = []
    valid = megaplan.execute.merge._validate_merge_inputs(
        [
            {"sense_check_id": "SC1", "verdict": ""},
            {"sense_check_id": "SC2", "verdict": "Confirmed."},
        ],
        required_fields=("sense_check_id", "verdict"),
        nonempty_fields={"verdict"},
        deviations=deviations,
        label="sense_check_verdicts",
    )

    assert valid == [{"sense_check_id": "SC2", "verdict": "Confirmed."}]
    assert deviations == [
        "Skipped sense_check_verdicts[0]: 'verdict' must not be empty.",
    ]


def test_duplicate_sense_check_verdict_dedup() -> None:
    """Two verdicts for SC1, zero for SC2 — should count 1 unique, not 2."""
    deviations: list[str] = []
    valid = megaplan.execute.merge._validate_merge_inputs(
        [
            {"sense_check_id": "SC1", "verdict": "First pass."},
            {"sense_check_id": "SC1", "verdict": "Second pass."},
        ],
        required_fields=("sense_check_id", "verdict"),
        nonempty_fields={"verdict"},
        deviations=deviations,
        label="sense_check_verdicts",
    )

    # Both entries pass validation (last-entry-wins happens at merge time in handler)
    assert len(valid) == 2
    assert valid[0]["verdict"] == "First pass."
    assert valid[1]["verdict"] == "Second pass."


def test_is_substantive_reviewer_verdict_accepts_real_verdict() -> None:
    verdict = "Verification work is acceptable and was checked through command evidence captured in the executor notes."
    assert megaplan.handlers._is_substantive_reviewer_verdict(verdict) is True


def test_is_substantive_reviewer_verdict_rejects_short_string() -> None:
    assert megaplan.handlers._is_substantive_reviewer_verdict("Looks good.") is False


def test_is_substantive_reviewer_verdict_rejects_repeated_words() -> None:
    assert megaplan.handlers._is_substantive_reviewer_verdict("ok ok ok ok ok ok ok") is False


def test_is_substantive_reviewer_verdict_accepts_boundary_case() -> None:
    assert megaplan.handlers._is_substantive_reviewer_verdict("alpha beta beta gamma") is True


def test_review_flags_incomplete_verdicts(plan_fixture: PlanFixture) -> None:
    """When reviewer returns fewer verdicts than tasks exist, issues surface it."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    response = megaplan.handle_review(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    # Mock review provides verdicts for T1 and T2, matching mock finalize's tasks
    # So no "Incomplete review" issue expected in the happy path
    assert response["state"] == megaplan.STATE_DONE


def test_validate_merge_inputs_tracks_deviations() -> None:
    """Verify that _validate_merge_inputs populates the deviations list for malformed input."""
    deviations: list[str] = []
    megaplan.execute.merge._validate_merge_inputs(
        [
            "not-a-dict",
            {"task_id": "T1"},  # missing required fields
            {"task_id": "T2", "status": "invalid_enum", "executor_notes": "x"},  # bad enum
        ],
        required_fields=("task_id", "status", "executor_notes"),
        enum_fields={"status": {"done", "skipped", "blocked"}},
        deviations=deviations,
        label="task_updates",
    )
    assert len(deviations) == 3
    assert "expected object" in deviations[0]
    assert "missing required" in deviations[1]
    assert "invalid field" in deviations[2]


def test_validate_merge_inputs_non_list_returns_empty() -> None:
    """Non-list input returns empty with no crash."""
    assert megaplan.execute.merge._validate_merge_inputs(
        "not-a-list",
        required_fields=("task_id",),
        label="test",
    ) == []
    assert megaplan.execute.merge._validate_merge_inputs(
        None,
        required_fields=("task_id",),
        label="test",
    ) == []


def test_review_blocks_incomplete_coverage_and_allows_rerun(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    first_review = WorkerResult(
        payload={
            "review_verdict": "approved",
            "criteria": [{"name": "criterion", "pass": True, "evidence": "checked"}],
            "issues": [],
            "summary": "Partial review.",
            "task_verdicts": [
                {
                    "task_id": "T1",
                    "reviewer_verdict": "Pass - partial.",
                    "evidence_files": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                },
                {
                    "task_id": "T1",
                    "reviewer_verdict": "Pass - final.",
                    "evidence_files": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                },
            ],
            "sense_check_verdicts": [
                {"sense_check_id": "SC1", "verdict": "Confirmed."},
            ],
        },
        raw_output="partial review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-partial",
    )
    second_review = WorkerResult(
        payload={
            "review_verdict": "approved",
            "criteria": [{"name": "criterion", "pass": True, "evidence": "checked again"}],
            "issues": [],
            "summary": "Complete review.",
            "task_verdicts": [
                {
                    "task_id": "T1",
                    "reviewer_verdict": "Pass - rerun.",
                    "evidence_files": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                },
                {
                    "task_id": "T2",
                    "reviewer_verdict": "Pass - rerun with command evidence that is substantive enough for FLAG-006 softening.",
                    "evidence_files": [],
                },
            ],
            "sense_check_verdicts": [
                {"sense_check_id": "SC1", "verdict": "Confirmed on rerun."},
                {"sense_check_id": "SC2", "verdict": "Confirmed on rerun."},
            ],
        },
        raw_output="complete review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-complete",
    )
    results = iter([first_review, second_review])
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (next(results), "codex", "persistent", False),
    )

    blocked = megaplan.handle_review(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    after_block = read_json(plan_fixture.plan_dir / "finalize.json")
    blocked_state = load_state(plan_fixture.plan_dir)
    blocked_entry = blocked_state["history"][-1]
    blocked_md = (plan_fixture.plan_dir / "final.md").read_text(encoding="utf-8")

    assert blocked["success"] is False
    assert blocked["state"] == megaplan.STATE_EXECUTED
    assert blocked["next_step"] == "review"
    assert blocked["summary"] == (
        "Blocked: incomplete review coverage (1/2 task verdicts, 1/2 sense checks). "
        "Re-run review to complete."
    )
    assert "Duplicate task_verdict for 'T1' — last entry wins." in blocked["issues"]
    blocked_review = read_json(plan_fixture.plan_dir / "review.json")
    assert blocked_review["task_verdicts"][-1]["reviewer_verdict"] == "Pass - final."
    assert after_block["tasks"][0]["reviewer_verdict"] == ""
    assert after_block["tasks"][1]["reviewer_verdict"] == ""
    assert blocked_entry["result"] == "blocked"
    assert (plan_fixture.plan_dir / "review.json").exists()
    assert "## Coverage Gaps" in blocked_md
    assert "Reviewer verdicts pending: 1" in blocked_md
    assert "Sense-check verdicts pending: 1" in blocked_md
    # Verify phase_result.json is written with success (review always emits success)
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result
    pr_blocked = read_phase_result(plan_fixture.plan_dir)
    assert pr_blocked is not None, "phase_result.json must be written after review"
    assert pr_blocked.exit_kind == "success"
    assert pr_blocked.phase == "review"

    completed = megaplan.handle_review(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    final_state = load_state(plan_fixture.plan_dir)
    final_data = read_json(plan_fixture.plan_dir / "finalize.json")
    final_review = read_json(plan_fixture.plan_dir / "review.json")

    assert completed["success"] is True
    assert completed["state"] == megaplan.STATE_DONE
    assert completed["next_step"] is None
    assert final_state["current_state"] == megaplan.STATE_DONE
    assert final_review["task_verdicts"][0]["reviewer_verdict"] == "Pass - rerun."
    assert (
        final_review["task_verdicts"][1]["reviewer_verdict"]
        == "Pass - rerun with command evidence that is substantive enough for FLAG-006 softening."
    )
    assert all(task["reviewer_verdict"] == "" for task in final_data["tasks"])
    assert all(check.get("verdict", "") == "" for check in final_data["sense_checks"])
    assert all(check["verdict"] == "Confirmed on rerun." for check in final_review["sense_check_verdicts"])
    # Verify phase_result.json is written for the second review call too
    pr_completed = read_phase_result(plan_fixture.plan_dir)
    assert pr_completed is not None
    assert pr_completed.exit_kind == "success"
    assert pr_completed.phase == "review"


def test_review_blocks_empty_evidence_files_without_substantive_verdict(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    worker = WorkerResult(
        payload={
            "review_verdict": "approved",
            "criteria": [{"name": "criterion", "pass": True, "evidence": "checked"}],
            "issues": [],
            "summary": "Review missing evidence files.",
            "task_verdicts": [
                {
                    "task_id": "T1",
                    "reviewer_verdict": "Pass - file backed.",
                    "evidence_files": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                },
                {
                    "task_id": "T2",
                    "reviewer_verdict": "Pass.",
                    "evidence_files": [],
                },
            ],
            "sense_check_verdicts": [
                {"sense_check_id": "SC1", "verdict": "Confirmed."},
                {"sense_check_id": "SC2", "verdict": "Confirmed."},
            ],
        },
        raw_output="review missing evidence files",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-missing-evidence-files",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_review(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_EXECUTED
    assert response["next_step"] == "review"
    assert "missing reviewer evidence_files" in response["summary"]
    # Verify phase_result.json is written
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result
    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written after review"
    assert pr.exit_kind == "success"


def test_review_softens_substantive_verdict_without_evidence_files_and_can_kick_back(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    worker = WorkerResult(
        payload={
            "review_verdict": "needs_rework",
            "criteria": [{"name": "criterion", "pass": False, "evidence": "Task T1 still needs follow-up edits."}],
            "issues": ["T1 implementation is incomplete and needs another execute pass."],
            "summary": "Needs rework: one task is still incomplete.",
            "task_verdicts": [
                {
                    "task_id": "T1",
                    "reviewer_verdict": "Needs more work. The main implementation is not complete yet.",
                    "evidence_files": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                },
                {
                    "task_id": "T2",
                    "reviewer_verdict": "Verification work is acceptable and was checked through command evidence captured in the executor notes.",
                    "evidence_files": [],
                },
            ],
            "sense_check_verdicts": [
                {"sense_check_id": "SC1", "verdict": "Needs another execute pass."},
                {"sense_check_id": "SC2", "verdict": "Confirmed for the verification task."},
            ],
        },
        raw_output="review needs rework",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-needs-rework",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_review(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    stored_review = read_json(plan_fixture.plan_dir / "review.json")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert response["summary"] == "Review requested another execute pass. Re-run execute using the review findings as context."
    assert any("FLAG-006 softening" in issue for issue in response["issues"])
    assert state["current_state"] == megaplan.STATE_FINALIZED
    assert state["history"][-1]["result"] == "needs_rework"
    assert stored_review["review_verdict"] == "needs_rework"
    # Verify phase_result.json emission
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result
    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written after review"
    assert pr.exit_kind == "success"


def test_review_force_proceed_records_outcome_matching_hashed_artifact(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    state = load_state(plan_fixture.plan_dir)
    state["history"].extend(
        {"step": "review", "result": "needs_rework"} for _ in range(3)
    )
    megaplan._core.atomic_write_json(plan_fixture.plan_dir / "state.json", state)

    worker = WorkerResult(
        payload={
            "review_verdict": "needs_rework",
            "criteria": [
                {"name": "copy polish", "priority": "should", "pass": False, "evidence": "Minor wording remains."}
            ],
            "issues": ["Minor cosmetic wording remains."],
            "summary": "Needs cosmetic rework.",
            "rework_items": [
                {
                    "task_id": "T1",
                    "issue": "nit: wording",
                    "expected": "Cleaner copy.",
                    "actual": "Acceptable but not polished.",
                    "severity": "minor",
                }
            ],
            "task_verdicts": [
                {"task_id": "T1", "reviewer_verdict": "Pass with cosmetic nit.", "evidence_files": ["IMPLEMENTED_BY_MEGAPLAN.txt"]},
                {"task_id": "T2", "reviewer_verdict": "Pass with command evidence.", "evidence_files": ["IMPLEMENTED_BY_MEGAPLAN.txt"]},
            ],
            "sense_check_verdicts": [
                {"sense_check_id": "SC1", "verdict": "Confirmed."},
                {"sense_check_id": "SC2", "verdict": "Confirmed."},
            ],
        },
        raw_output="review cosmetic rework",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-force-proceeded",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_review(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    state_after = load_state(plan_fixture.plan_dir)
    stored_review = read_json(plan_fixture.plan_dir / "review.json")
    receipt = read_json(plan_fixture.plan_dir / "step_receipt_review_v1.json")
    artifact_hash = megaplan._core.sha256_file(plan_fixture.plan_dir / "review.json")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_DONE
    assert state_after["current_state"] == megaplan.STATE_DONE
    assert state_after["history"][-1]["result"] == "force_proceeded"
    assert state_after["history"][-1]["artifact_hash"] == artifact_hash
    assert stored_review["review_verdict"] == "needs_rework"
    assert stored_review["outcome"]["result"] == "force_proceeded"
    assert receipt["verdict"] == "force_proceeded"


def test_review_incomplete_rework_payload_stays_in_review(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    worker = WorkerResult(
        payload={
            "review_verdict": "needs_rework",
            "criteria": [{"name": "criterion", "pass": False, "evidence": "review did not inspect repository"}],
            "issues": ["No repository inspection was performed; review output is incomplete."],
            "summary": "Review infrastructure failed.",
            "rework_items": [
                {
                    "task_id": "T1",
                    "issue": "No repository inspection was performed.",
                    "expected": "Review should inspect repository state before requesting implementation rework.",
                    "actual": "Placeholder review response.",
                    "source": "review_incomplete",
                }
            ],
            "task_verdicts": [
                {"task_id": "T1", "reviewer_verdict": "Placeholder.", "evidence_files": ["IMPLEMENTED_BY_MEGAPLAN.txt"]},
                {"task_id": "T2", "reviewer_verdict": "Placeholder.", "evidence_files": ["IMPLEMENTED_BY_MEGAPLAN.txt"]},
            ],
            "sense_check_verdicts": [
                {"sense_check_id": "SC1", "verdict": "Placeholder."},
                {"sense_check_id": "SC2", "verdict": "Placeholder."},
            ],
        },
        raw_output="review incomplete",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-incomplete",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_review(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_EXECUTED
    assert response["next_step"] == "review"
    assert "review infrastructure" in response["summary"]
    assert state["current_state"] == megaplan.STATE_EXECUTED
    assert state["history"][-1]["result"] == "blocked"


def test_review_works_after_batch_by_batch_execution(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args

    def _local_setup_two_batch_plan() -> None:
        megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
        megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
        megaplan.handle_override(
            plan_fixture.root,
            make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
        )
        megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
        finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
        finalize_data["tasks"] = [
            {
                "id": "T1",
                "description": "First batch",
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
                "description": "Second batch",
                "depends_on": ["T1"],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
        ]
        finalize_data["sense_checks"] = [
            {"id": "SC1", "task_id": "T1", "question": "Batch one?", "executor_note": "", "verdict": ""},
            {"id": "SC2", "task_id": "T2", "question": "Batch two?", "executor_note": "", "verdict": ""},
        ]
        (plan_fixture.plan_dir / "finalize.json").write_text(
            json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
        )

    def _local_batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["batch1.py"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Completed the first batch.",
                        "files_changed": ["batch1.py"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one."}
                ],
            }
            return WorkerResult(
                payload=payload,
                raw_output="batch1",
                duration_ms=2,
                cost_usd=0.1,
                session_id="batch-1",
            ), "codex", "persistent", False
        if "[T2]" in prompt_override:
            payload = {
                "output": "Batch two complete.",
                "files_changed": ["batch2.py"],
                "commands_run": ["pytest -k batch2"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "executor_notes": "Completed the second batch.",
                        "files_changed": ["batch2.py"],
                        "commands_run": ["pytest -k batch2"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC2", "executor_note": "Confirmed batch two."}
                ],
            }
            return WorkerResult(
                payload=payload,
                raw_output="batch2",
                duration_ms=3,
                cost_usd=0.2,
                session_id="batch-2",
            ), "codex", "persistent", False
        raise AssertionError(f"Unexpected batch prompt: {prompt_override}")

    _local_setup_two_batch_plan()
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_: ({}, None))

    original_run_step = megaplan.workers.run_step_with_worker

    def _worker_dispatch(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        if step == "execute":
            return _local_batch_worker(
                step,
                state,
                plan_dir,
                args,
                root=root,
                resolved=resolved,
                prompt_override=prompt_override,
            )
        return original_run_step(step, state, plan_dir, args, root=root, resolved=resolved, prompt_override=prompt_override)

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _worker_dispatch)

    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=2),
    )
    review = megaplan.handle_review(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name),
    )
    assert review["state"] == megaplan.STATE_DONE
    # Verify phase_result.json is written after this review too
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result
    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written after review"
    assert pr.exit_kind == "success"


def test_validate_merge_inputs_accepts_blocked_status() -> None:
    """`status=blocked` must be accepted (not silently discarded) so workers
    can signal a poisoned/broken environment without megaplan dropping it."""
    deviations: list[str] = []
    valid = megaplan.execute.merge._validate_merge_inputs(
        [
            {
                "task_id": "T1",
                "status": "blocked",
                "executor_notes": "bwrap: Creating new namespace failed — env broken.",
                "files_changed": [],
                "commands_run": [],
            }
        ],
        required_fields=("task_id", "status", "executor_notes", "files_changed", "commands_run"),
        enum_fields={"status": {"done", "skipped", "completed", "blocked"}},
        nonempty_fields={"executor_notes"},
        array_fields=("files_changed", "commands_run"),
        deviations=deviations,
        label="task_updates",
    )
    assert len(valid) == 1
    assert valid[0]["status"] == "blocked"
    assert deviations == []


def test_execution_merge_config_includes_blocked_status() -> None:
    """The enum_fields passed to the execute merge path must include blocked."""
    # Import source to sanity-check the constant survives future edits.
    import inspect
    import arnold.pipelines.megaplan.execute.core as execution_module

    source = inspect.getsource(execution_module._merge_batch_results)
    assert '"blocked"' in source, (
        "execution._merge_batch_results must include 'blocked' in the task_updates "
        "status enum so workers can report poisoned-environment outcomes."
    )
