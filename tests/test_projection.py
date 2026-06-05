"""Focused unit tests for megaplan.prompts._projection."""

from __future__ import annotations

import textwrap
from typing import Any

import pytest

from arnold.pipelines.megaplan.types import CliError

from arnold.pipelines.megaplan.prompts._projection import (
    MAX_COMPLEXITY_JUSTIFICATION_CHARS,
    MAX_DESCRIPTION_CHARS,
    MAX_EXECUTION_DEVIATIONS,
    MAX_EXECUTION_DEVIATION_CHARS,
    MAX_EXECUTION_OUTPUT_CHARS,
    MAX_EXECUTOR_NOTES_CHARS,
    MAX_META_COMMENTARY_CHARS,
    MAX_SENSE_CHECK_QUESTION_CHARS,
    PromptProjectionCapabilities,
    _brief_text,
    _project_task,
    _project_sense_check,
    _resolve_prompt_size_limit,
    check_prompt_size,
    is_prompt_oversized,
    oversized_prompt_error,
    project_execution_audit_context,
    project_execute_context,
    project_review_context,
    project_rework_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synthetic_oversized_finalize() -> dict[str, Any]:
    """Return a finalize.json-shaped dict with artificially long fields."""
    long_note = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 200
    long_justification = "This task is complex because " * 100
    long_description = "Implement the thing " * 100
    long_question = "Does the implementation correctly handle " * 100
    long_commentary = "Meta guidance: " * 500

    return {
        "tasks": [
            {
                "id": "T1",
                "description": "Active task: fix the auth bug in handlers.py",
                "depends_on": [],
                "status": "done",
                "kind": "code",
                "complexity": 3,
                "complexity_justification": "Touches auth middleware.",
                "executor_notes": "Fixed the bug by updating the handler.",
                "files_changed": ["megaplan/handlers.py"],
                "commands_run": ["pytest tests/test_auth.py"],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
            {
                "id": "T2",
                "description": long_description,
                "depends_on": ["T1"],
                "status": "pending",
                "kind": "code",
                "complexity": 2,
                "complexity_justification": long_justification,
                "executor_notes": long_note,
                "files_changed": ["megaplan/utils.py"],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
        ],
        "sense_checks": [
            {
                "id": "SC1",
                "task_id": "T1",
                "question": "Did the auth fix preserve existing behavior?",
                "verdict": "",
                "executor_note": "Confirmed via test run.",
            },
            {
                "id": "SC2",
                "task_id": "T2",
                "question": long_question,
                "verdict": "",
                "executor_note": long_note,
            },
        ],
        "watch_items": ["Check assumptions.", "Verify edge cases."],
        "user_actions": [
            {
                "id": "U1",
                "description": "Set API key in .env",
                "blocks_task_ids": ["T2"],
                "requires_human_only_reason": "Secret the executor cannot mint",
            }
        ],
        "meta_commentary": long_commentary,
        "baseline_test_failures": ["test_legacy_bug", "test_known_flaky"],
        "baseline_test_command": "pytest tests/",
    }


# ---------------------------------------------------------------------------
# _brief_text
# ---------------------------------------------------------------------------


def test_brief_text_short() -> None:
    assert _brief_text("hello", limit=10) == "hello"


def test_brief_text_exact() -> None:
    assert _brief_text("1234567890", limit=10) == "1234567890"


def test_brief_text_truncates() -> None:
    result = _brief_text("1234567890abc", limit=10)
    assert result == "1234567..."


def test_brief_text_empty() -> None:
    assert _brief_text("", limit=10) == ""


def test_brief_text_none() -> None:
    assert _brief_text(None, limit=10) == ""


def test_brief_text_collapses_whitespace() -> None:
    assert _brief_text("  hello   world  ", limit=20) == "hello world"


# ---------------------------------------------------------------------------
# PromptProjectionCapabilities
# ---------------------------------------------------------------------------


def test_capabilities_conservative() -> None:
    caps = PromptProjectionCapabilities.conservative()
    assert caps.can_read_plan_dir is False
    assert caps.can_read_project_dir is False
    assert caps.has_file_tools is False
    assert caps.artifact_reference_allowed(path_hint="anything") is False


def test_capabilities_full() -> None:
    caps = PromptProjectionCapabilities.full()
    assert caps.can_read_plan_dir is True
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is True
    assert caps.artifact_reference_allowed(path_hint="src/main.py") is True


def test_capabilities_from_worker_caps_none() -> None:
    caps = PromptProjectionCapabilities.from_worker_caps(None)
    assert caps.can_read_plan_dir is False
    assert caps.can_read_project_dir is False


def test_capabilities_from_worker_caps_read_files() -> None:
    caps = PromptProjectionCapabilities.from_worker_caps({"read_files"})
    assert caps.can_read_plan_dir is True
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is True


def test_capabilities_from_worker_caps_run_shell_only() -> None:
    caps = PromptProjectionCapabilities.from_worker_caps({"run_shell"})
    assert caps.can_read_plan_dir is True
    assert caps.can_read_project_dir is True
    assert caps.has_file_tools is False


def test_capabilities_from_worker_caps_empty() -> None:
    caps = PromptProjectionCapabilities.from_worker_caps(set())
    assert caps.can_read_plan_dir is False
    assert caps.can_read_project_dir is False
    assert caps.has_file_tools is False


def test_artifact_reference_gating_plan_dir() -> None:
    caps = PromptProjectionCapabilities(can_read_plan_dir=False, can_read_project_dir=True)
    assert caps.artifact_reference_allowed(path_hint="/some/.megaplan/plans/foo/finalize.json") is False


def test_artifact_reference_gating_project_dir() -> None:
    caps = PromptProjectionCapabilities(can_read_plan_dir=True, can_read_project_dir=False)
    assert caps.artifact_reference_allowed(path_hint="src/main.py") is False


def test_artifact_reference_gating_no_file_tools() -> None:
    caps = PromptProjectionCapabilities(
        can_read_plan_dir=True, can_read_project_dir=False, has_file_tools=False
    )
    # Without has_file_tools AND without can_read_project_dir, denied
    assert caps.artifact_reference_allowed(path_hint="src/main.py") is False


# ---------------------------------------------------------------------------
# _project_task
# ---------------------------------------------------------------------------


def test_project_task_preserves_structural_fields() -> None:
    task = {
        "id": "T1",
        "depends_on": ["T0"],
        "status": "done",
        "kind": "code",
        "complexity": 3,
        "reviewer_verdict": "approved",
        "stance": "conservative",
        "stop_signal": None,
    }
    projected = _project_task(task)
    assert projected["id"] == "T1"
    assert projected["depends_on"] == ["T0"]
    assert projected["status"] == "done"
    assert projected["kind"] == "code"
    assert projected["complexity"] == 3
    assert projected["reviewer_verdict"] == "approved"


def test_project_task_truncates_long_executor_notes() -> None:
    long_note = "x" * (MAX_EXECUTOR_NOTES_CHARS + 100)
    task = {"id": "T1", "executor_notes": long_note, "status": "done"}
    projected = _project_task(task)
    assert len(projected["executor_notes"]) <= MAX_EXECUTOR_NOTES_CHARS
    assert projected["executor_notes"].endswith("...")


def test_project_task_preserves_short_executor_notes() -> None:
    task = {"id": "T1", "executor_notes": "Short note.", "status": "done"}
    projected = _project_task(task)
    assert projected["executor_notes"] == "Short note."


def test_project_task_truncates_long_description() -> None:
    long_desc = "y" * (MAX_DESCRIPTION_CHARS + 50)
    task = {"id": "T1", "description": long_desc, "status": "pending"}
    projected = _project_task(task)
    assert len(projected["description"]) <= MAX_DESCRIPTION_CHARS


def test_project_task_truncates_long_justification() -> None:
    long_just = "z" * (MAX_COMPLEXITY_JUSTIFICATION_CHARS + 50)
    task = {"id": "T1", "complexity_justification": long_just, "status": "pending"}
    projected = _project_task(task)
    assert len(projected["complexity_justification"]) <= MAX_COMPLEXITY_JUSTIFICATION_CHARS


def test_project_task_caps_evidence_lists() -> None:
    task = {
        "id": "T1",
        "files_changed": [f"file_{i}.py" for i in range(30)],
        "commands_run": [f"cmd_{i}" for i in range(30)],
        "evidence_files": [f"ev_{i}.json" for i in range(30)],
        "status": "done",
    }
    projected = _project_task(task)
    assert len(projected["files_changed"]) <= 20
    assert len(projected["commands_run"]) <= 20
    assert len(projected["evidence_files"]) <= 20


# ---------------------------------------------------------------------------
# _project_sense_check
# ---------------------------------------------------------------------------


def test_project_sense_check_preserves_core() -> None:
    sc = {"id": "SC1", "task_id": "T1", "question": "Did it work?", "verdict": "passed"}
    projected = _project_sense_check(sc)
    assert projected["id"] == "SC1"
    assert projected["task_id"] == "T1"
    assert projected["question"] == "Did it work?"
    assert projected["verdict"] == "passed"


def test_project_sense_check_truncates_long_question() -> None:
    long_q = "q" * (MAX_SENSE_CHECK_QUESTION_CHARS + 50)
    sc = {"id": "SC1", "task_id": "T1", "question": long_q}
    projected = _project_sense_check(sc)
    assert len(projected["question"]) <= MAX_SENSE_CHECK_QUESTION_CHARS


def test_project_sense_check_truncates_long_executor_note() -> None:
    long_note = "n" * (MAX_EXECUTOR_NOTES_CHARS + 50)
    sc = {"id": "SC1", "task_id": "T1", "question": "OK?", "executor_note": long_note}
    projected = _project_sense_check(sc)
    assert len(projected["executor_note"]) <= MAX_EXECUTOR_NOTES_CHARS


# ---------------------------------------------------------------------------
# project_execute_context
# ---------------------------------------------------------------------------


def test_project_execute_context_preserves_active_task_details() -> None:
    """Active task descriptions, criteria, and evidence stay inline."""
    data = _synthetic_oversized_finalize()
    projected = project_execute_context(data)

    tasks = projected["tasks"]
    assert len(tasks) == 2

    # T1: short active task — everything should be preserved
    t1 = tasks[0]
    assert t1["id"] == "T1"
    assert t1["description"] == "Active task: fix the auth bug in handlers.py"
    assert t1["files_changed"] == ["megaplan/handlers.py"]
    assert t1["commands_run"] == ["pytest tests/test_auth.py"]
    assert "Fixed the bug" in t1["executor_notes"]

    # T2: long fields should be truncated
    t2 = tasks[1]
    assert t2["id"] == "T2"
    assert len(t2["executor_notes"]) <= MAX_EXECUTOR_NOTES_CHARS
    assert len(t2["complexity_justification"]) <= MAX_COMPLEXITY_JUSTIFICATION_CHARS
    assert len(t2["description"]) <= MAX_DESCRIPTION_CHARS


def test_project_execute_context_preserves_sense_check_questions() -> None:
    """Sense-check questions are preserved; long ones are truncated but present."""
    data = _synthetic_oversized_finalize()
    projected = project_execute_context(data)

    checks = projected["sense_checks"]
    assert len(checks) == 2

    # SC1: short question preserved verbatim
    assert checks[0]["question"] == "Did the auth fix preserve existing behavior?"

    # SC2: long question truncated but contains recognizable prefix
    assert "Does the implementation correctly handle" in checks[1]["question"]


def test_project_execute_context_preserves_baseline_failures() -> None:
    data = _synthetic_oversized_finalize()
    projected = project_execute_context(data)
    assert projected["baseline_test_failures"] == ["test_legacy_bug", "test_known_flaky"]


def test_project_execute_context_preserves_user_actions() -> None:
    data = _synthetic_oversized_finalize()
    projected = project_execute_context(data)
    assert len(projected["user_actions"]) == 1
    assert projected["user_actions"][0]["id"] == "U1"


def test_project_execute_context_truncates_meta_commentary() -> None:
    data = _synthetic_oversized_finalize()
    projected = project_execute_context(data)
    assert len(projected["meta_commentary"]) <= MAX_META_COMMENTARY_CHARS


def test_project_execute_context_drops_irrelevant_long_notes() -> None:
    """Long irrelevant executor notes are truncated while active task info stays."""
    long_note = "IRRELEVANT DETAIL " * 500
    data = {
        "tasks": [
            {
                "id": "T1",
                "description": "Critical auth fix",
                "depends_on": [],
                "status": "done",
                "executor_notes": long_note,
                "files_changed": ["auth.py"],
                "commands_run": ["pytest"],
            }
        ],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "question": "Auth working?", "executor_note": long_note}
        ],
    }
    projected = project_execute_context(data)

    t1 = projected["tasks"][0]
    # Active description preserved
    assert t1["description"] == "Critical auth fix"
    # Evidence preserved
    assert t1["files_changed"] == ["auth.py"]
    assert t1["commands_run"] == ["pytest"]
    # Long notes truncated
    assert len(t1["executor_notes"]) <= MAX_EXECUTOR_NOTES_CHARS
    assert "IRRELEVANT DETAIL" in t1["executor_notes"]

    sc1 = projected["sense_checks"][0]
    assert sc1["question"] == "Auth working?"
    assert len(sc1["executor_note"]) <= MAX_EXECUTOR_NOTES_CHARS


def test_project_execute_context_conservative_capabilities() -> None:
    """With conservative caps, structural data still projects correctly."""
    data = _synthetic_oversized_finalize()
    caps = PromptProjectionCapabilities.conservative()
    projected = project_execute_context(data, capabilities=caps)

    # Core structure preserved regardless of capabilities
    assert len(projected["tasks"]) == 2
    assert len(projected["sense_checks"]) == 2
    assert projected["baseline_test_failures"] == ["test_legacy_bug", "test_known_flaky"]


# ---------------------------------------------------------------------------
# project_review_context
# ---------------------------------------------------------------------------


def test_project_review_context_projects_tasks_and_checks() -> None:
    data = _synthetic_oversized_finalize()
    execution = {
        "output": "done",
        "deviations": [],
        "files_changed": ["megaplan/handlers.py"],
        "commands_run": ["pytest"],
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Fixed it.",
                "files_changed": ["megaplan/handlers.py"],
                "commands_run": ["pytest"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC1", "executor_note": "Confirmed."}
        ],
    }
    projected = project_review_context(data, execution)

    assert len(projected["tasks"]) == 2
    assert len(projected["sense_checks"]) == 2
    assert len(projected["task_updates"]) == 1
    assert projected["task_updates"][0]["task_id"] == "T1"
    assert len(projected["sense_check_acknowledgments"]) == 1
    assert projected["sense_check_acknowledgments"][0]["sense_check_id"] == "SC1"
    assert projected["output"] == "done"


def test_project_review_context_without_execution_data() -> None:
    data = _synthetic_oversized_finalize()
    projected = project_review_context(data, None)
    assert len(projected["tasks"]) == 2
    assert len(projected["sense_checks"]) == 2
    assert "task_updates" not in projected


def test_project_review_context_caps_noisy_execution_fields() -> None:
    data = _synthetic_oversized_finalize()
    execution = {
        "output": "OUTPUT-BLOAT " * 500,
        "deviations": [f"DEVIATION-{i} " + ("x" * 2000) for i in range(50)],
        "files_changed": [f"src/file_{i}.py" for i in range(50)],
        "commands_run": [f"pytest tests/test_{i}.py " + ("--verbose " * 100) for i in range(50)],
    }

    projected = project_review_context(data, execution)

    assert len(projected["output"]) <= MAX_EXECUTION_OUTPUT_CHARS
    assert len(projected["deviations"]) == MAX_EXECUTION_DEVIATIONS + 1
    assert projected["deviations"][-1]["omitted_count"] == 30
    assert len(projected["deviations"][0]) <= MAX_EXECUTION_DEVIATION_CHARS
    assert len(projected["files_changed"]) == 20
    assert len(projected["commands_run"]) == 21
    assert projected["commands_run"][-1]["omitted_count"] == 30


def test_project_execution_audit_context_keeps_review_fields_compact() -> None:
    audit = {
        "findings": [("needs more detail " * 80).strip(), "short finding"],
        "files_in_diff": [f"src/file_{i}.py" for i in range(50)],
        "files_claimed": [f"src/claimed_{i}.py" for i in range(50)],
        "auto_attribution": [f"record-{i}" for i in range(50)],
        "skipped": False,
        "reason": "",
    }

    projected = project_execution_audit_context(audit)

    assert projected["skipped"] is False
    assert len(projected["findings"]) == 2
    assert len(projected["findings"][0]) <= MAX_EXECUTOR_NOTES_CHARS
    assert len(projected["files_in_diff"]) == 40
    assert len(projected["files_claimed"]) == 40
    assert len(projected["auto_attribution"]) == 40


# ---------------------------------------------------------------------------
# project_rework_context
# ---------------------------------------------------------------------------


def test_project_rework_context_focuses_on_failures() -> None:
    review = {
        "rework_items": [
            {
                "task_id": "T1",
                "issue": "Auth handler missing edge case",
                "expected": "Should handle empty tokens",
                "actual": "Raises 500 on empty token",
                "evidence_file": "/some/.megaplan/plans/foo/evidence.txt",
            }
        ],
        "issues": ["Auth edge case missing"],
        "criteria": [
            {"name": "Auth works", "priority": "must", "pass": "pass", "evidence": "OK"},
            {"name": "Edge cases", "priority": "must", "pass": "fail", "evidence": "Missing"},
            {"name": "Style", "priority": "should", "pass": "pass", "evidence": "Fine"},
        ],
        "summary": "Needs auth fix.",
    }
    projected = project_rework_context(review)

    assert len(projected["rework_items"]) == 1
    assert projected["rework_items"][0]["task_id"] == "T1"
    assert projected["rework_items"][0]["issue"] == "Auth handler missing edge case"

    # Only failed criteria preserved
    assert len(projected["criteria"]) == 1
    assert projected["criteria"][0]["name"] == "Edge cases"

    assert projected["issues"] == ["Auth edge case missing"]
    assert projected["summary"] == "Needs auth fix."


def test_project_rework_context_gates_evidence_file() -> None:
    """Evidence file references are gated when worker lacks plan-dir access."""
    review = {
        "rework_items": [
            {
                "task_id": "T1",
                "issue": "Missing edge case",
                "expected": "Handle empty",
                "actual": "500 error",
                "evidence_file": "/home/user/.megaplan/plans/proj/evidence.txt",
            }
        ],
        "criteria": [],
        "issues": [],
    }
    caps = PromptProjectionCapabilities(can_read_plan_dir=False, can_read_project_dir=True)
    projected = project_rework_context(review, capabilities=caps)

    assert len(projected["rework_items"]) == 1
    assert "gated" in projected["rework_items"][0]["evidence_file"]


def test_project_rework_context_allows_evidence_file_with_caps() -> None:
    review = {
        "rework_items": [
            {
                "task_id": "T1",
                "issue": "Missing edge case",
                "expected": "Handle empty",
                "actual": "500 error",
                "evidence_file": "src/auth.py",
            }
        ],
        "criteria": [],
        "issues": [],
    }
    caps = PromptProjectionCapabilities.full()
    projected = project_rework_context(review, capabilities=caps)

    assert projected["rework_items"][0]["evidence_file"] == "src/auth.py"


# ---------------------------------------------------------------------------
# is_prompt_oversized / oversized_prompt_error
# ---------------------------------------------------------------------------


def test_is_prompt_oversized_under_limit() -> None:
    assert is_prompt_oversized("short", max_chars=100) is False


def test_is_prompt_oversized_over_limit() -> None:
    assert is_prompt_oversized("x" * 201, max_chars=200) is True


def test_is_prompt_oversized_default_limit() -> None:
    assert is_prompt_oversized("x" * 200_001) is True
    assert is_prompt_oversized("x" * 199_999) is False


def test_oversized_prompt_error_execute() -> None:
    msg = oversized_prompt_error("execute", 250_000, 200_000)
    assert "LLM_CALL_ERROR" in msg
    assert "execute" in msg
    assert "250,000" in msg
    assert "200,000" in msg


def test_oversized_prompt_error_with_guidance() -> None:
    msg = oversized_prompt_error(
        "review", 300_000, 150_000, extra_guidance="Try reducing batch size."
    )
    assert "LLM_CALL_ERROR" in msg
    assert "Try reducing batch size." in msg


def test_project_execute_context_sense_check_1() -> None:
    """SC1: Projection keeps active task descriptions, criteria, sense-check
    questions, baseline failures, user actions, and concise evidence inline
    while omitting long irrelevant notes from oversized synthetic ledgers."""
    data = _synthetic_oversized_finalize()
    projected = project_execute_context(data)

    # Active task descriptions preserved
    tasks = projected["tasks"]
    assert tasks[0]["description"] == "Active task: fix the auth bug in handlers.py"

    # Sense-check questions preserved (SC1 short, SC2 truncated but recognizable)
    checks = projected["sense_checks"]
    assert checks[0]["question"] == "Did the auth fix preserve existing behavior?"
    assert "correctly handle" in checks[1]["question"]

    # Baseline failures preserved
    assert projected["baseline_test_failures"] == ["test_legacy_bug", "test_known_flaky"]

    # User actions preserved
    assert projected["user_actions"][0]["id"] == "U1"

    # Concise evidence inline
    assert tasks[0]["files_changed"] == ["megaplan/handlers.py"]
    assert tasks[0]["commands_run"] == ["pytest tests/test_auth.py"]

    # Long irrelevant notes truncated
    assert len(tasks[1]["executor_notes"]) <= MAX_EXECUTOR_NOTES_CHARS
    assert tasks[1]["executor_notes"].endswith("...")

    # Long meta_commentary truncated
    assert len(projected["meta_commentary"]) <= MAX_META_COMMENTARY_CHARS


# ---------------------------------------------------------------------------
# _resolve_prompt_size_limit
# ---------------------------------------------------------------------------


def test_resolve_limit_default_execute() -> None:
    """Execute phase defaults to 200,000."""
    assert _resolve_prompt_size_limit("execute") == 200_000


def test_resolve_limit_default_review() -> None:
    """Review phase defaults to 600,000 (calibrated to premium model windows)."""
    assert _resolve_prompt_size_limit("review") == 600_000


def test_resolve_limit_default_unknown_phase() -> None:
    """Unknown phase falls back to sentinel 200,000."""
    assert _resolve_prompt_size_limit("nonexistent") == 200_000


def test_resolve_limit_env_global_override(monkeypatch) -> None:
    """MEGAPLAN_PROMPT_SIZE_LIMIT overrides all phase defaults."""
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT", "50000")
    assert _resolve_prompt_size_limit("execute") == 50_000
    assert _resolve_prompt_size_limit("review") == 50_000
    assert _resolve_prompt_size_limit("finalize") == 50_000


def test_resolve_limit_env_phase_specific_override(monkeypatch) -> None:
    """MEGAPLAN_PROMPT_SIZE_LIMIT_EXECUTE overrides only execute phase."""
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT_EXECUTE", "30000")
    assert _resolve_prompt_size_limit("execute") == 30_000
    # Other phases unchanged
    assert _resolve_prompt_size_limit("review") == 600_000


def test_resolve_limit_env_phase_overrides_global(monkeypatch) -> None:
    """Phase-specific env var takes priority over global."""
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT", "50000")
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT_EXECUTE", "80000")
    assert _resolve_prompt_size_limit("execute") == 80_000
    assert _resolve_prompt_size_limit("review") == 50_000


def test_resolve_limit_env_phase_with_hyphens(monkeypatch) -> None:
    """Phase names with hyphens get underscores in env var names."""
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT_EXECUTE_BATCH", "45000")
    assert _resolve_prompt_size_limit("execute-batch") == 45_000


def test_resolve_limit_env_invalid_value_falls_back(monkeypatch) -> None:
    """Invalid env values are ignored; defaults apply."""
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT", "not-a-number")
    assert _resolve_prompt_size_limit("execute") == 200_000


def test_resolve_limit_env_phase_invalid_value_falls_back(monkeypatch) -> None:
    """Invalid phase-specific env values are ignored."""
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT_EXECUTE", "xyz")
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT", "75000")
    # Phase-specific invalid -> skip, global override applies
    assert _resolve_prompt_size_limit("execute") == 75_000


# ---------------------------------------------------------------------------
# check_prompt_size
# ---------------------------------------------------------------------------


def test_check_prompt_size_under_limit_does_not_raise() -> None:
    """No error when prompt is within the phase limit."""
    check_prompt_size("short prompt", phase="execute")  # should not raise


def test_check_prompt_size_at_limit_does_not_raise() -> None:
    """No error when prompt is exactly at the phase limit."""
    limit = _resolve_prompt_size_limit("execute")
    check_prompt_size("x" * limit, phase="execute")  # should not raise


def test_check_prompt_size_over_limit_raises_cli_error() -> None:
    """CliError raised when prompt exceeds the phase limit."""
    limit = _resolve_prompt_size_limit("execute")
    with pytest.raises(CliError) as exc_info:
        check_prompt_size("x" * (limit + 1), phase="execute")
    assert exc_info.value.code == "prompt_oversized"
    assert "LLM_CALL_ERROR" in exc_info.value.message
    assert "execute" in exc_info.value.message
    assert exc_info.value.extra["phase"] == "execute"
    assert exc_info.value.extra["prompt_size"] == limit + 1
    assert exc_info.value.extra["max_chars"] == limit


def test_check_prompt_size_review_phase_message() -> None:
    """Review phase error includes review-specific guidance."""
    limit = _resolve_prompt_size_limit("review")
    with pytest.raises(CliError) as exc_info:
        check_prompt_size("x" * (limit + 1), phase="review")
    assert "review" in exc_info.value.message
    assert "reviewing fewer tasks" in exc_info.value.message.lower()


def test_check_prompt_size_execute_phase_message() -> None:
    """Execute phase error includes batch-specific guidance."""
    limit = _resolve_prompt_size_limit("execute")
    with pytest.raises(CliError) as exc_info:
        check_prompt_size("x" * (limit + 1), phase="execute")
    assert "reducing batch size" in exc_info.value.message.lower()


def test_check_prompt_size_finalize_phase_message() -> None:
    """Finalize phase error includes finalize-specific guidance."""
    limit = _resolve_prompt_size_limit("finalize")
    with pytest.raises(CliError) as exc_info:
        check_prompt_size("x" * (limit + 1), phase="finalize")
    assert "reducing task count" in exc_info.value.message.lower()


def test_check_prompt_size_env_override_respected(monkeypatch) -> None:
    """check_prompt_size respects environment variable overrides."""
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT", "100")
    # Under the env override limit
    check_prompt_size("x" * 100, phase="execute")  # should not raise
    # Over the env override limit
    with pytest.raises(CliError) as exc_info:
        check_prompt_size("x" * 101, phase="execute")
    assert exc_info.value.extra["max_chars"] == 100


def test_check_prompt_size_phase_specific_env_override(monkeypatch) -> None:
    """check_prompt_size respects phase-specific env override."""
    monkeypatch.setenv("MEGAPLAN_PROMPT_SIZE_LIMIT_REVIEW", "50")
    # execute still uses default
    check_prompt_size("x" * 199_999, phase="execute")  # should not raise
    # review uses the override
    with pytest.raises(CliError) as exc_info:
        check_prompt_size("x" * 51, phase="review")
    assert exc_info.value.extra["max_chars"] == 50


def test_check_prompt_size_unknown_phase_no_specific_guidance() -> None:
    """Unknown phase raises CliError without specific guidance text."""
    with pytest.raises(CliError) as exc_info:
        check_prompt_size("x" * 200_001, phase="unknown-phase")
    assert exc_info.value.code == "prompt_oversized"
    assert "LLM_CALL_ERROR" in exc_info.value.message
