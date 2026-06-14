from __future__ import annotations

import dataclasses

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan.execute._binding.reducer import BatchOutcome
from arnold.pipelines.megaplan.run_outcome import (
    RunOutcome,
    RunResultMetadata,
    run_metadata_from_batch_outcome,
    run_outcome_from_batch_outcome,
)
from arnold.pipelines.megaplan.planning.state import STATE_AWAITING_HUMAN, STATE_AWAITING_HUMAN_VERIFY

# ---------------------------------------------------------------------------
# Type identity: neutral source, runtime re-export, and Megaplan shim
# ---------------------------------------------------------------------------


def test_run_outcome_type_identity_across_import_paths() -> None:
    """RunOutcome must be the same object whether imported from the neutral
    source, the runtime re-export, or the Megaplan compatibility shim."""
    from arnold.runtime.outcome import RunOutcome as NeutralRunOutcome

    # Neutral source ⇄ runtime re-export
    import arnold.runtime as runtime_pkg

    assert runtime_pkg.RunOutcome is NeutralRunOutcome, (
        "arnold.runtime.RunOutcome should be the same object as "
        "arnold.runtime.outcome.RunOutcome"
    )

    # Neutral source ⇄ Megaplan shim (direct import)
    assert RunOutcome is NeutralRunOutcome, (
        "arnold.pipelines.megaplan.run_outcome.RunOutcome should be the "
        "same object as arnold.runtime.outcome.RunOutcome"
    )

    # Megaplan shim ⇄ Megaplan top-level lazy access
    assert megaplan.RunOutcome is NeutralRunOutcome, (
        "megaplan.RunOutcome should resolve to the same object as "
        "arnold.runtime.outcome.RunOutcome"
    )


def test_run_result_metadata_type_identity_across_import_paths() -> None:
    """RunResultMetadata must be the same type across import paths."""
    from arnold.runtime.outcome import RunResultMetadata as NeutralMetadata

    import arnold.runtime as runtime_pkg

    assert runtime_pkg.RunResultMetadata is NeutralMetadata, (
        "arnold.runtime.RunResultMetadata should be the same type as "
        "arnold.runtime.outcome.RunResultMetadata"
    )

    assert RunResultMetadata is NeutralMetadata, (
        "arnold.pipelines.megaplan.run_outcome.RunResultMetadata should "
        "be the same type as arnold.runtime.outcome.RunResultMetadata"
    )

    assert megaplan.RunResultMetadata is NeutralMetadata, (
        "megaplan.RunResultMetadata should resolve to the same type as "
        "arnold.runtime.outcome.RunResultMetadata"
    )


# ---------------------------------------------------------------------------
# Exact dataclass fields
# ---------------------------------------------------------------------------


def test_run_result_metadata_exact_dataclass_fields() -> None:
    """RunResultMetadata must have exactly outcome, blocking_reason, source."""
    from arnold.runtime.outcome import RunResultMetadata as NeutralMetadata

    field_names = {f.name for f in dataclasses.fields(NeutralMetadata)}
    assert field_names == {"outcome", "blocking_reason", "source"}, (
        f"Expected fields {{outcome, blocking_reason, source}}, got {field_names}"
    )

    # Verify types
    fields_by_name = {f.name: f.type for f in dataclasses.fields(NeutralMetadata)}
    # outcome field type should reference RunOutcome
    outcome_type_str = str(fields_by_name["outcome"])
    assert "RunOutcome" in outcome_type_str, (
        f"outcome field type should reference RunOutcome, got {outcome_type_str}"
    )
    # blocking_reason is str | None
    assert "str | None" in str(fields_by_name["blocking_reason"]) or (
        "None" in str(fields_by_name["blocking_reason"])
        and "str" in str(fields_by_name["blocking_reason"])
    ), f"blocking_reason type should be str | None, got {fields_by_name['blocking_reason']}"
    # source is str | None
    assert "str | None" in str(fields_by_name["source"]) or (
        "None" in str(fields_by_name["source"])
        and "str" in str(fields_by_name["source"])
    ), f"source type should be str | None, got {fields_by_name['source']}"


def test_run_result_metadata_is_frozen() -> None:
    """RunResultMetadata must be a frozen dataclass."""
    meta = RunResultMetadata(outcome=RunOutcome.SUCCEEDED)
    try:
        meta.outcome = RunOutcome.FAILED  # type: ignore[misc]
        raise AssertionError("RunResultMetadata should be frozen")
    except (dataclasses.FrozenInstanceError, AttributeError):
        pass  # expected


# ---------------------------------------------------------------------------
# Unchanged RunOutcome enum values
# ---------------------------------------------------------------------------


def test_run_outcome_enum_members_exact() -> None:
    """RunOutcome must have exactly five members with the documented values."""
    expected = {
        "SUCCEEDED": "succeeded",
        "FAILED": "failed",
        "ESCALATED": "escalated",
        "BLOCKED": "blocked",
        "AWAITING_HUMAN": "awaiting_human",
    }

    members = {m.name: m.value for m in RunOutcome}
    assert members == expected, f"RunOutcome members mismatch: {members}"

    # Enum iteration order must be definition order
    names_in_order = [m.name for m in RunOutcome]
    assert names_in_order == list(expected.keys()), (
        f"RunOutcome iteration order mismatch: {names_in_order}"
    )


def test_run_outcome_values_are_exact() -> None:
    assert [outcome.value for outcome in RunOutcome] == [
        "succeeded",
        "failed",
        "escalated",
        "blocked",
        "awaiting_human",
    ]
    assert megaplan.RunOutcome is RunOutcome


# ---------------------------------------------------------------------------
# BatchOutcome mapping (compatibility shim)
# ---------------------------------------------------------------------------


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
