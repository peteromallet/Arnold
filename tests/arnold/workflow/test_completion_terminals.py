"""Adversarial named-exit custody tests."""

from __future__ import annotations

import pytest

from arnold.workflow.completion.terminals import (
    NamedExit,
    compute_exit_hash,
    evaluate_complete_capture_set_equality,
    superseded_by_named_exit,
    unwind_named_exit,
    validate_named_exit,
)


def _exit() -> NamedExit:
    return NamedExit(
        exit_name="exit:loop",
        target_loop_id="loop:1",
        source_declaration_ref="source:1",
        intervening_bindings=("binding:1", "binding:2"),
        ordered_unwind_set=("occurrence:2", "occurrence:1"),
    )


def test_exact_target_and_complete_binding_sequence_are_required() -> None:
    record = _exit()
    validate_named_exit(record, expected_target_loop_id="loop:1", expected_intervening_bindings=("binding:1", "binding:2"))
    with pytest.raises(ValueError, match="target"):
        validate_named_exit(record, expected_target_loop_id="loop:other")
    with pytest.raises(ValueError, match="incomplete or reordered"):
        superseded_by_named_exit(record, ("binding:1",))


def test_wrong_or_reordered_unwind_is_rejected_without_mutating_stack() -> None:
    record = _exit()
    stack = ["binding:1", "binding:2"]
    before = tuple(stack)
    with pytest.raises(ValueError, match="unwind order"):
        validate_named_exit(record, expected_unwind_order=("occurrence:1", "occurrence:2"))
    with pytest.raises(ValueError, match="incomplete or reordered"):
        unwind_named_exit(record, ["binding:2"])
    assert tuple(stack) == before


def test_successful_unwind_returns_new_stack_and_keeps_shadow_only_verdict() -> None:
    record = _exit()
    assert unwind_named_exit(record, ["parent", "binding:1", "binding:2"], target_loop_id="loop:1") == ("parent",)
    verdict = superseded_by_named_exit(record, ("binding:1", "binding:2"), expected_unwind_order=record.ordered_unwind_set)
    assert not verdict.accepted


def test_provided_hash_and_mutation_cases_fail_closed() -> None:
    record = _exit()
    with pytest.raises(ValueError, match="hash mismatch"):
        NamedExit(**{**record.to_dict(), "exit_hash": "sha256:" + "0" * 64})
    assert compute_exit_hash(
        record.exit_name,
        record.target_loop_id,
        record.source_declaration_ref,
        record.intervening_bindings,
        record.ordered_unwind_set,
        record.superseded_spec_hashes,
        record.previous_exit_hash,
    ) == record.exit_hash


def test_duplicate_or_incomplete_capture_is_not_a_clean_set() -> None:
    duplicate = evaluate_complete_capture_set_equality((1, 2, 3), (1, 1, 2, 3))
    assert duplicate.status == "rejected"
    assert duplicate.duplicate_ids == ("1",)
    assert len(duplicate.causal_occurrences) == 1
    assert len(duplicate.repair_frontier) == 1
    unknown = evaluate_complete_capture_set_equality((1, 2, 3), (1, 2), complete_capture=False)
    assert unknown.unknown


def test_unwind_failure_preserves_the_original_mutable_stack() -> None:
    record = _exit()
    stack = ["parent", "binding:1", "binding:2"]
    before = list(stack)
    with pytest.raises(ValueError, match="target"):
        unwind_named_exit(record, stack, target_loop_id="loop:wrong")
    assert stack == before


def test_unwind_order_must_cover_each_intervening_binding() -> None:
    with pytest.raises(ValueError, match="cover every"):
        NamedExit(
            exit_name="exit:short",
            target_loop_id="loop:1",
            source_declaration_ref="source:1",
            intervening_bindings=("binding:1", "binding:2"),
            ordered_unwind_set=("occurrence:2",),
        )
