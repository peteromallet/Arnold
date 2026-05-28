"""Direct mock payload tests for megaplan.workers."""

from __future__ import annotations

from pathlib import Path

import pytest

from megaplan.orchestration.evaluation import validate_plan_structure
from megaplan.types import CliError
from megaplan.workers import _build_mock_payload, validate_payload
from tests._workers_helpers import _mock_state


def test_mock_plan_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("plan", state, plan_dir)
    assert "plan" in result.payload
    assert "questions" in result.payload
    assert "success_criteria" in result.payload
    assert "assumptions" in result.payload
    assert validate_plan_structure(result.payload["plan"]) == []

def test_mock_prep_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("prep", state, plan_dir)
    assert "task_summary" in result.payload
    assert "key_evidence" in result.payload
    assert "relevant_code" in result.payload
    assert "test_expectations" in result.payload
    assert "constraints" in result.payload
    assert "suggested_approach" in result.payload

def test_build_mock_payload_execute_returns_complete_payload(tmp_path: Path) -> None:
    plan_dir, state = _mock_state(tmp_path)
    payload = _build_mock_payload(
        "execute",
        state,
        plan_dir,
        task_updates=[
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Verified the targeted execute payload override keeps the schema intact.",
                "files_changed": ["megaplan/workers.py"],
                "commands_run": ["pytest tests/test_workers.py -k build_mock_payload"],
            }
        ],
    )

    assert payload["output"] == "Mock execution completed successfully."
    assert payload["task_updates"][0]["task_id"] == "T1"
    assert len(payload["task_updates"]) == 1
    assert payload["sense_check_acknowledgments"]

def test_build_mock_payload_execute_scopes_batch_from_prompt_override(tmp_path: Path) -> None:
    plan_dir, state = _mock_state(tmp_path)
    payload = _build_mock_payload(
        "execute",
        state,
        plan_dir,
        prompt_override="Only produce task_updates for these tasks: [T2]",
    )

    assert [item["task_id"] for item in payload["task_updates"]] == ["T2"]
    assert [item["sense_check_id"] for item in payload["sense_check_acknowledgments"]] == ["SC2"]

def test_mock_critique_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("critique", state, plan_dir)
    assert "flags" in result.payload
    assert isinstance(result.payload["flags"], list)

def test_mock_revise_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("revise", state, plan_dir)
    assert "plan" in result.payload
    assert "changes_summary" in result.payload
    assert "flags_addressed" in result.payload
    assert "assumptions" in result.payload
    assert "success_criteria" in result.payload
    assert "questions" in result.payload
    assert validate_plan_structure(result.payload["plan"]) == []

def test_mock_gate_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("gate", state, plan_dir)
    assert "recommendation" in result.payload
    assert result.payload["recommendation"] in {"PROCEED", "ITERATE", "ESCALATE"}
    assert "rationale" in result.payload
    assert "signals_assessment" in result.payload
    assert "warnings" in result.payload
    assert "settled_decisions" in result.payload
    assert "flag_resolutions" in result.payload
    assert "accepted_tradeoffs" in result.payload

def test_mock_finalize_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("finalize", state, plan_dir)
    validate_payload("finalize", result.payload)
    assert "tasks" in result.payload
    assert "watch_items" in result.payload
    assert "sense_checks" in result.payload
    assert "meta_commentary" in result.payload
    assert "validation" in result.payload
    assert "baseline_test_failures" not in result.payload
    assert "baseline_test_command" not in result.payload
    assert "baseline_test_note" not in result.payload
    assert isinstance(result.payload["tasks"], list)
    assert isinstance(result.payload["watch_items"], list)
    assert result.payload["tasks"][0]["status"] == "pending"
    assert result.payload["sense_checks"][0]["task_id"] == "T1"
    validation = result.payload["validation"]
    assert "plan_steps_covered" in validation
    assert "orphan_tasks" in validation
    assert "coverage_complete" in validation
    assert isinstance(validation["plan_steps_covered"], list)

def test_mock_execute_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("execute", state, plan_dir)
    assert "output" in result.payload
    assert "files_changed" in result.payload
    assert "commands_run" in result.payload
    assert "deviations" in result.payload
    assert "task_updates" in result.payload
    assert "sense_check_acknowledgments" in result.payload
    assert result.payload["task_updates"][0]["task_id"] == "T1"

def test_mock_review_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("review", state, plan_dir)
    assert result.payload["review_verdict"] == "approved"
    assert "checks" in result.payload
    assert "pre_check_flags" in result.payload
    assert "verified_flag_ids" in result.payload
    assert "disputed_flag_ids" in result.payload
    assert "criteria" in result.payload
    assert "issues" in result.payload
    assert "rework_items" in result.payload
    assert "summary" in result.payload
    assert "task_verdicts" in result.payload
    assert "sense_check_verdicts" in result.payload
    assert result.payload["rework_items"] == []

def test_mock_unsupported_step_raises(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    with pytest.raises(CliError, match="does not support"):
        mock_worker_output("nonexistent", state, plan_dir)

