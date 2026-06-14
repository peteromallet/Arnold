"""Tests for the finalize scrubber (T2).

Covers the repurposed ``_ensure_verification_task`` scrubber and the
inverted strict validation in ``_validate_finalize_payload``.
"""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.handlers.finalize import (
    _ensure_verification_task,
    _task_matches_verification_pattern,
)


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def test_detection_standalone_test_suite_is_not_a_match() -> None:
    """The standalone 'test suite' keyword is dropped — no longer a match."""
    assert not _task_matches_verification_pattern(
        {"description": "Write the test suite for the new API endpoint"}
    )
    assert not _task_matches_verification_pattern(
        {"description": "The test suite should be comprehensive"}
    )


def test_detection_requires_action_co_occurring_with_target() -> None:
    """Tightened keywords: 'run'/'re-run' must co-occur with 'test'/'pytest'/'verification'."""
    assert _task_matches_verification_pattern(
        {"description": "Run the tests and verify they pass"}
    )
    assert _task_matches_verification_pattern(
        {"description": "Re-run pytest until everything is green"}
    )
    assert _task_matches_verification_pattern(
        {"description": "Rerun verification after the fix"}
    )
    # Action without target → no match
    assert not _task_matches_verification_pattern(
        {"description": "Run the linter on changed files"}
    )
    # Target without action → no match
    assert not _task_matches_verification_pattern(
        {"description": "Write test cases for the parser"}
    )


def test_detection_catch_all_regexes() -> None:
    """Catch-all regexes catch re-run-until-pass phrasing regardless of keywords."""
    # re-?run.*(until|all).*(pass|green)
    assert _task_matches_verification_pattern(
        {"description": "execute the complete test collection and iterate until all assertions succeed"}
    )
    # iterate.*until.*(pass|succeed)
    assert _task_matches_verification_pattern(
        {"description": "iterate until tests pass"}
    )
    # loop.*(test|suite)
    assert _task_matches_verification_pattern(
        {"description": "loop the test suite"}
    )
    assert _task_matches_verification_pattern(
        {"description": "re-run until all pass"}
    )
    assert _task_matches_verification_pattern(
        {"description": "rerun until green"}
    )


def test_detection_empty_and_missing_description() -> None:
    """Empty or missing descriptions are not matches."""
    assert not _task_matches_verification_pattern({"description": ""})
    assert not _task_matches_verification_pattern({"id": "T1"})


# ---------------------------------------------------------------------------
# Scrubber — rewrite behaviour
# ---------------------------------------------------------------------------

_REWRITTEN = (
    "Introduce no new failures vs the recorded baseline; "
    "do not try to make pre-existing baseline failures pass; "
    "do not narrow to individual functions. "
    "The harness will run the authoritative post-execute verification — "
    "do not loop the suite."
)


def _make_task(description: str, id: str = "T1") -> dict:
    return {
        "id": id,
        "description": description,
        "depends_on": [],
        "status": "pending",
        "executor_notes": "",
        "files_changed": [],
        "commands_run": [],
        "evidence_files": [],
        "reviewer_verdict": "",
    }


def _make_state() -> dict:
    return {"config": {"mode": "code"}, "idea": "", "notes": []}


def test_scrubber_rewrites_keyword_match_in_tasks0() -> None:
    """Keyword match in tasks[0] is rewritten."""
    payload = {
        "tasks": [
            _make_task("Run the tests and verify correctness"),
            _make_task("Ship the change", id="T2"),
        ],
        "sense_checks": [],
    }
    _ensure_verification_task(payload, _make_state())
    assert payload["tasks"][0]["description"] == _REWRITTEN
    # T2 untouched
    assert payload["tasks"][1]["description"] == "Ship the change"
    # No new task injected
    assert len(payload["tasks"]) == 2


def test_scrubber_rewrites_match_in_middle_position() -> None:
    """Match in the middle of the task list is rewritten (not just tasks[-1])."""
    payload = {
        "tasks": [
            _make_task("Set up the project", id="T1"),
            _make_task("Re-run tests until green", id="T2"),
            _make_task("Ship the change", id="T3"),
        ],
        "sense_checks": [],
    }
    _ensure_verification_task(payload, _make_state())
    assert payload["tasks"][0]["description"] == "Set up the project"
    assert payload["tasks"][1]["description"] == _REWRITTEN
    assert payload["tasks"][2]["description"] == "Ship the change"
    assert len(payload["tasks"]) == 3


def test_scrubber_rewrites_regex_catch_all() -> None:
    """Catch-all regex matches are rewritten."""
    payload = {
        "tasks": [
            _make_task("execute the complete test collection and iterate until all assertions succeed"),
        ],
        "sense_checks": [],
    }
    _ensure_verification_task(payload, _make_state())
    assert payload["tasks"][0]["description"] == _REWRITTEN
    assert len(payload["tasks"]) == 1


def test_scrubber_rewrites_multiple_matching_tasks() -> None:
    """Every matching task is rewritten, not just the first."""
    payload = {
        "tasks": [
            _make_task("Run verification tests", id="T1"),
            _make_task("Do other work", id="T2"),
            _make_task("Re-run pytest until all pass", id="T3"),
        ],
        "sense_checks": [],
    }
    _ensure_verification_task(payload, _make_state())
    assert payload["tasks"][0]["description"] == _REWRITTEN
    assert payload["tasks"][1]["description"] == "Do other work"
    assert payload["tasks"][2]["description"] == _REWRITTEN
    assert len(payload["tasks"]) == 3


def test_scrubber_injects_nothing_when_no_match() -> None:
    """Non-matching payload yields no injected task and no changes."""
    payload = {
        "tasks": [
            _make_task("Ship the change"),
            _make_task("Write documentation", id="T2"),
        ],
        "sense_checks": [],
    }
    _ensure_verification_task(payload, _make_state())
    assert len(payload["tasks"]) == 2
    assert payload["tasks"][0]["description"] == "Ship the change"
    assert payload["tasks"][1]["description"] == "Write documentation"


def test_scrubber_no_sense_check_side_effect() -> None:
    """The scrubber does NOT inject a sense check (side-effect removed)."""
    payload = {
        "tasks": [
            _make_task("Run pytest and verify"),
        ],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "question": "Did the work?", "executor_note": "", "verdict": ""}
        ],
    }
    _ensure_verification_task(payload, _make_state())
    # Only the original sense check remains
    assert len(payload["sense_checks"]) == 1
    assert payload["sense_checks"][0]["id"] == "SC1"


def test_scrubber_no_plan_step_coverage_side_effect() -> None:
    """The scrubber does NOT call _append_plan_step_coverage."""
    payload = {
        "tasks": [
            _make_task("Run the test suite and iterate until green"),
        ],
        "sense_checks": [],
        "validation": {
            "plan_steps_covered": [],
            "orphan_tasks": [],
            "completeness_notes": "",
            "coverage_complete": False,
        },
    }
    _ensure_verification_task(payload, _make_state())
    # plan_steps_covered should NOT have gained a verification entry
    assert payload["validation"]["plan_steps_covered"] == []


# ---------------------------------------------------------------------------
# Baseline-failure note routing
# ---------------------------------------------------------------------------

def test_baseline_note_appended_to_rewritten_task() -> None:
    """When a task IS rewritten, the baseline-failure note is appended to it."""
    payload = {
        "tasks": [
            _make_task("Re-run the test suite until green"),
        ],
        "sense_checks": [],
        "baseline_test_failures": ["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
    }
    _ensure_verification_task(payload, _make_state())
    assert _REWRITTEN in payload["tasks"][0]["description"]
    assert "Note: 2 tests were already failing" in payload["tasks"][0]["description"]
    assert "baseline_test_note" not in payload  # should be on task, not top-level


def test_baseline_note_routed_via_payload_when_no_rewrite() -> None:
    """When NO task is rewritten, the baseline note goes to baseline_test_note."""
    payload = {
        "tasks": [
            _make_task("Ship the code"),
        ],
        "sense_checks": [],
        "baseline_test_failures": ["tests/test_a.py::test_z"],
    }
    _ensure_verification_task(payload, _make_state())
    # Task unchanged
    assert payload["tasks"][0]["description"] == "Ship the code"
    # Note surfaced via baseline_test_note
    assert "baseline_test_note" in payload
    assert "tests were already failing" in payload["baseline_test_note"]


def test_baseline_note_not_dumped_on_unrelated_task() -> None:
    """Even with baseline failures, an unrelated last task is not touched."""
    payload = {
        "tasks": [
            _make_task("Re-run verification", id="T1"),
            _make_task("Write release notes", id="T2"),
        ],
        "sense_checks": [],
        "baseline_test_failures": ["tests/test_x.py::test_fail"],
    }
    _ensure_verification_task(payload, _make_state())
    # T1 (rewritten) gets the note
    assert "Note: 1 tests were already failing" in payload["tasks"][0]["description"]
    # T2 (not rewritten) is untouched
    assert payload["tasks"][1]["description"] == "Write release notes"
    assert "Note:" not in payload["tasks"][1]["description"]


# ---------------------------------------------------------------------------
# Empty-tasks early return
# ---------------------------------------------------------------------------

def test_scrubber_empty_tasks_early_return() -> None:
    """Empty task list returns immediately (no crash)."""
    payload: dict = {"tasks": [], "sense_checks": []}
    _ensure_verification_task(payload, _make_state())
    assert payload["tasks"] == []


def test_scrubber_missing_tasks_key_early_return() -> None:
    """Missing 'tasks' key returns immediately."""
    payload: dict = {"sense_checks": []}
    _ensure_verification_task(payload, _make_state())
    assert "tasks" not in payload


# ---------------------------------------------------------------------------
# Strict validation integration
# ---------------------------------------------------------------------------

def test_strict_validation_accepts_payload_without_verification_task(
    plan_fixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strict validation accepts a payload that has no verification task."""
    import arnold.pipelines.megaplan as megaplan
    import arnold.pipelines.megaplan.workers as megaplan_workers
    from arnold.pipelines.megaplan.workers import WorkerResult
    from tests.conftest import load_state

    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )

    # Payload with NO verification task — should be accepted under strict validation
    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the code change",
                "depends_on": [],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Simple change, tier 2.",
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
        payload=payload,
        raw_output="no verification task",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-no-verify",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )
    monkeypatch.setenv("MEGAPLAN_FINALIZE_STRICT_VALIDATION", "1")

    # Should NOT raise — payload without verification task is accepted
    response = megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    assert response["success"] is True


def test_strict_validation_rejects_rerun_until_pass_task(
    plan_fixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strict validation rejects a payload where a re-run-until-pass task survives."""
    import arnold.pipelines.megaplan as megaplan
    import arnold.pipelines.megaplan.workers as megaplan_workers
    from arnold.pipelines.megaplan.workers import WorkerResult

    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )

    # Payload WITH a re-run-until-pass task — should be REJECTED
    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Run pytest and re-run until all tests pass",
                "depends_on": [],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Test verification.",
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
                "question": "Did tests pass?",
                "executor_note": "",
                "verdict": "",
            }
        ],
        "meta_commentary": "ok",
    }
    worker = WorkerResult(
        payload=payload,
        raw_output="re-run-until-pass task",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-rerun-pass",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )
    monkeypatch.setenv("MEGAPLAN_FINALIZE_STRICT_VALIDATION", "1")

    with pytest.raises(megaplan.CliError, match="re-run-until-pass task"):
        megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
