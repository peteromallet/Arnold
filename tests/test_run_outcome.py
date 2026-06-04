from __future__ import annotations

import megaplan
from megaplan.execute._binding.reducer import BatchOutcome
from megaplan.run_outcome import (
    RunOutcome,
    run_metadata_from_batch_outcome,
    run_outcome_from_batch_outcome,
)
from megaplan.planning.state import STATE_AWAITING_HUMAN, STATE_AWAITING_HUMAN_VERIFY


def test_run_outcome_values_are_exact() -> None:
    assert [outcome.value for outcome in RunOutcome] == [
        "succeeded",
        "failed",
        "escalated",
        "blocked",
        "awaiting_human",
    ]
    assert megaplan.RunOutcome is RunOutcome


def test_batch_outcome_mapping_is_exact_with_blocking_reasons() -> None:
    expected = {
        BatchOutcome.SUCCESS: ("succeeded", None),
        BatchOutcome.BLOCKED_BY_QUALITY: ("blocked", "quality"),
        BatchOutcome.BLOCKED_BY_PREREQ: ("blocked", "prereq"),
        BatchOutcome.TIMEOUT: ("failed", None),
    }

    assert {
        outcome: (
            run_metadata_from_batch_outcome(outcome).outcome.value,
            run_metadata_from_batch_outcome(outcome).blocking_reason,
        )
        for outcome in BatchOutcome
    } == expected


def test_execute_reducer_outcomes_never_map_to_escalated_or_awaiting_human() -> None:
    mapped = {run_outcome_from_batch_outcome(outcome) for outcome in BatchOutcome}

    assert RunOutcome.ESCALATED not in mapped
    assert RunOutcome.AWAITING_HUMAN not in mapped


def test_planning_human_states_project_to_awaiting_human_without_renaming_state() -> None:
    planning_human_states = [
        STATE_AWAITING_HUMAN,
        STATE_AWAITING_HUMAN_VERIFY,
    ]

    assert planning_human_states == [
        "awaiting_human_verify",
        "awaiting_human_verify",
    ]
    assert {state: RunOutcome.AWAITING_HUMAN for state in planning_human_states} == {
        "awaiting_human_verify": RunOutcome.AWAITING_HUMAN,
    }
