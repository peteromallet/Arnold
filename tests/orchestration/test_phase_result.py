"""Tests for phase_result validation — M11 Steps 12-13.

Covers:
* Empty blocked_by_prereq with no blocked_tasks is rejected as invalid_phase_result.
* Auto driver does not reinterpret empty blocked_by_prereq as quality.
* Explicit quality blocks (blocked_by_quality) are preserved unchanged.
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.orchestration.phase_result import (
    BlockedTask,
    ExitKind,
    PhaseResult,
    _validate_phase_result_structure,
    validate_phase_result_current,
)


# ── Step 12: empty blocked_by_prereq is invalid ─────────────────────────


def test_empty_blocked_by_prereq_is_invalid():
    """Step 12: blocked_by_prereq with empty blocked_tasks is rejected.

    The executor must supply typed blocked tasks when reporting
    blocked_by_prereq. An empty list is a classification contradiction
    and must be rejected as invalid_phase_result / classification_incompatible.
    """
    # Constructing PhaseResult with blocked_by_prereq and no blocked_tasks
    # must raise ValueError
    with pytest.raises(ValueError, match="classification_incompatible"):
        PhaseResult(
            phase="execute",
            invocation_id="test-invocation-001",
            exit_kind=ExitKind.blocked_by_prereq.value,
            blocked_tasks=(),  # empty — should be rejected
        )

    # Same with empty list
    with pytest.raises(ValueError, match="classification_incompatible"):
        PhaseResult(
            phase="execute",
            invocation_id="test-invocation-002",
            exit_kind=ExitKind.blocked_by_prereq.value,
            blocked_tasks=[],  # empty list — should be rejected
        )


def test_empty_blocked_by_prereq_rejected_in_validation():
    """Step 12: structural validation also rejects empty blocked_by_prereq."""
    from arnold_pipelines.megaplan.types import CliError

    payload = {
        "schema": "megaplan.phase_result",
        "schema_version": 1,
        "phase_result_contract_version": 1,
        "phase": "execute",
        "invocation_id": "test-invocation-003",
        "exit_kind": "blocked_by_prereq",
        "blocked_tasks": [],  # empty
        "deviations": [],
        "artifacts_written": [],
        "cli_provenance": {},
    }

    with pytest.raises(CliError, match="classification_incompatible"):
        _validate_phase_result_structure(payload, require_current_schema=True)


def test_blocked_by_prereq_with_tasks_is_valid():
    """Step 12: blocked_by_prereq with actual blocked tasks is valid."""
    result = PhaseResult(
        phase="execute",
        invocation_id="test-invocation-004",
        exit_kind=ExitKind.blocked_by_prereq.value,
        blocked_tasks=(
            BlockedTask(task_id="T42", reason="missing prerequisite evidence"),
        ),
    )
    assert result.exit_kind == "blocked_by_prereq"
    assert len(result.blocked_tasks) == 1
    assert result.blocked_tasks[0].task_id == "T42"

    # to_dict / from_dict round-trip preserves the blocked task
    d = result.to_dict()
    reconstructed = PhaseResult.from_dict(d)
    assert reconstructed.exit_kind == "blocked_by_prereq"
    assert len(reconstructed.blocked_tasks) == 1
    assert reconstructed.blocked_tasks[0].task_id == "T42"


def test_blocked_by_prereq_with_multiple_tasks_is_valid():
    """Step 12: multiple blocked tasks are fine."""
    result = PhaseResult(
        phase="execute",
        invocation_id="test-invocation-005",
        exit_kind=ExitKind.blocked_by_prereq.value,
        blocked_tasks=(
            BlockedTask(task_id="T2", reason="missing M10 evidence"),
            BlockedTask(task_id="T3", reason="stale runtime identity"),
        ),
    )
    assert len(result.blocked_tasks) == 2


def test_blocked_by_quality_with_empty_tasks_is_valid():
    """Step 13: blocked_by_quality with empty blocked_tasks is valid.
    Quality blocks carry deviations, not necessarily blocked tasks.
    """
    result = PhaseResult(
        phase="execute",
        invocation_id="test-invocation-006",
        exit_kind=ExitKind.blocked_by_quality.value,
        blocked_tasks=(),  # quality blocks can have empty tasks
    )
    assert result.exit_kind == "blocked_by_quality"

    # Validation should pass
    validate_phase_result_current(result.to_dict())


def test_success_with_empty_tasks_is_valid():
    """Step 13: success with empty blocked_tasks is valid (normal case)."""
    result = PhaseResult(
        phase="execute",
        invocation_id="test-invocation-007",
        exit_kind=ExitKind.success.value,
        blocked_tasks=(),
    )
    assert result.exit_kind == "success"
    validate_phase_result_current(result.to_dict())


# ── Step 13: auto does not reinterpret empty prereq as quality ──────────


def test_auto_does_not_reinterpret_empty_prereq_as_quality():
    """Step 13: the auto driver does not reinterpret empty blocked_by_prereq
    as a quality block. The validation at the PhaseResult level already
    rejects such constructs, and the auto driver surfaces them as
    invalid_phase_result rather than silently reclassifying.

    This test verifies that the rejection happens at the PhaseResult
    construction level, which is the guard that prevents the auto driver
    from ever seeing an empty blocked_by_prereq to reinterpret.
    """
    # Verify that PhaseResult.__post_init__ rejects empty blocked_by_prereq
    # This is the defense-in-depth that prevents auto from reinterpreting
    with pytest.raises(ValueError, match="classification_incompatible"):
        PhaseResult(
            phase="execute",
            invocation_id="test-invocation-008",
            exit_kind="blocked_by_prereq",
            blocked_tasks=(),
        )

    # Verify that blocked_by_quality is NOT affected (preserved)
    result = PhaseResult(
        phase="execute",
        invocation_id="test-invocation-009",
        exit_kind="blocked_by_quality",
        blocked_tasks=(),
    )
    assert result.exit_kind == "blocked_by_quality"


def test_validate_phase_result_current_accepts_blocked_by_quality_empty():
    """Step 13: explicit quality blocks (blocked_by_quality) pass validation
    even with empty blocked_tasks — quality blocks are preserved unchanged.
    """
    payload = {
        "schema": "megaplan.phase_result",
        "schema_version": 1,
        "phase_result_contract_version": 1,
        "phase": "execute",
        "invocation_id": "test-invocation-010",
        "exit_kind": "blocked_by_quality",
        "blocked_tasks": [],
        "deviations": [
            {"kind": "quality_gate", "message": "scope drift detected"}
        ],
        "artifacts_written": ["finalize.json"],
        "cli_provenance": {},
    }
    # Should not raise
    _validate_phase_result_structure(payload, require_current_schema=True)


def test_blocked_tasks_preserve_blocker_kind():
    """Step 12: BlockedTask carries blocker_kind through serialization."""
    bt = BlockedTask(
        task_id="T99",
        reason="missing prerequisite",
        blocker_kind="m10_handoff",
        blocking_action_ids=("produce-evidence",),
    )
    d = bt.to_dict()
    assert d["blocker_kind"] == "m10_handoff"
    assert d["blocking_action_ids"] == ["produce-evidence"]

    reconstructed = BlockedTask.from_dict(d)
    assert reconstructed.blocker_kind == "m10_handoff"
    assert reconstructed.blocking_action_ids == ("produce-evidence",)
