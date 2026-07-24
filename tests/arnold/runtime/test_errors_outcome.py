"""Tests for neutral runtime error and outcome carriers."""

from __future__ import annotations

from arnold.runtime import ArnoldError, RunOutcome, RunResultMetadata


def test_arnold_error_carries_code_message_and_exit_code() -> None:
    error = ArnoldError("bad_input", "Bad input", exit_code=2)

    assert str(error) == "Bad input"
    assert error.code == "bad_input"
    assert error.message == "Bad input"
    assert error.exit_code == 2


def test_run_result_metadata_carries_neutral_outcome() -> None:
    metadata = RunResultMetadata(
        outcome=RunOutcome.BLOCKED,
        blocking_reason="missing approval",
        source="unit-test",
    )

    assert metadata.outcome == RunOutcome.BLOCKED
    assert metadata.outcome.value == "blocked"
    assert metadata.blocking_reason == "missing approval"
    assert metadata.source == "unit-test"
