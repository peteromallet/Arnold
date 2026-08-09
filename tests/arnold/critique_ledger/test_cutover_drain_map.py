"""Exhaustiveness and category-count coverage for the cutover drain map (CL5 Step 12a).

These tests pin the cutover's attempt-state classification contract:

* every current :class:`AttemptEventType` is classified exactly once;
* category counts are exactly 3 terminal-drain, 7 nonterminal-indeterminate,
  and 1 persistence-fail-closed (3 + 7 + 1 = 11);
* the terminal-drain set mirrors the source-of-truth
  ``_TERMINAL_EVENT_TYPES`` so the drain map never drifts;
* PERSISTENCE_FAILED resolves fail-closed to INDETERMINATE, and every
  non-terminal event resolves to INDETERMINATE while terminal events keep
  their natural outcome.
"""

from __future__ import annotations

import pytest

from arnold.critique_ledger.cutover.drain_map import (
    DRAIN_MAP,
    INDETERMINATE_COUNT,
    INDETERMINATE_EVENT_TYPES,
    PERSISTENCE_FAIL_CLOSED_COUNT,
    PERSISTENCE_FAIL_CLOSED_EVENT_TYPES,
    TERMINAL_DRAIN_COUNT,
    TERMINAL_DRAIN_EVENT_TYPES,
    DrainCategory,
    assert_drain_map_exhaustive,
    classify_drain,
    indeterminate_outcome,
    resolves_to_indeterminate,
)
from arnold.workflow.execution_attempt_ledger import (
    AttemptEventType,
    AttemptOutcome,
    _TERMINAL_EVENT_TYPES,
)

# The authoritative list of all 11 AttemptEventType values, in enum order.
ALL_EVENT_TYPES: list[AttemptEventType] = list(AttemptEventType)


def test_all_eleven_event_types_are_classified_exactly_once() -> None:
    assert_drain_map_exhaustive()  # raises if any member is missing/extra
    # Every enum member maps to exactly one category.
    assert set(DRAIN_MAP) == set(ALL_EVENT_TYPES)
    assert len(DRAIN_MAP) == len(ALL_EVENT_TYPES) == 11


def test_category_counts_are_three_seven_one() -> None:
    terminal = [
        e for e in ALL_EVENT_TYPES
        if classify_drain(e) is DrainCategory.TERMINAL_DRAIN
    ]
    indeterminate = [
        e for e in ALL_EVENT_TYPES
        if classify_drain(e) is DrainCategory.INDETERMINATE
    ]
    persistence = [
        e for e in ALL_EVENT_TYPES
        if classify_drain(e) is DrainCategory.PERSISTENCE_FAIL_CLOSED
    ]
    assert len(terminal) == TERMINAL_DRAIN_COUNT == 3
    assert len(indeterminate) == INDETERMINATE_COUNT == 7
    assert len(persistence) == PERSISTENCE_FAIL_CLOSED_COUNT == 1
    # Exhaustive and disjoint: every member in exactly one bucket.
    assert len(terminal) + len(indeterminate) + len(persistence) == 11


def test_terminal_drain_set_matches_source_of_truth() -> None:
    # The drain map's terminal set MUST mirror the source-of-truth
    # _TERMINAL_EVENT_TYPES in execution_attempt_ledger.
    assert TERMINAL_DRAIN_EVENT_TYPES == _TERMINAL_EVENT_TYPES


def test_terminal_drain_members() -> None:
    assert TERMINAL_DRAIN_EVENT_TYPES == frozenset(
        {
            AttemptEventType.COMPLETED,
            AttemptEventType.FAILED,
            AttemptEventType.CANCELLED,
        }
    )


def test_indeterminate_members_are_the_seven_nonterminal_states() -> None:
    assert INDETERMINATE_EVENT_TYPES == frozenset(
        {
            AttemptEventType.STARTED,
            AttemptEventType.RETRY_SCHEDULED,
            AttemptEventType.SUSPENDED,
            AttemptEventType.RESUMED,
            AttemptEventType.EXTERNAL_EFFECT_INTENT,
            AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            AttemptEventType.RECONCILIATION,
        }
    )
    assert len(INDETERMINATE_EVENT_TYPES) == 7


def test_persistence_failed_is_fail_closed_indeterminate() -> None:
    assert PERSISTENCE_FAIL_CLOSED_EVENT_TYPES == frozenset(
        {AttemptEventType.PERSISTENCE_FAILED}
    )
    assert classify_drain(AttemptEventType.PERSISTENCE_FAILED) is (
        DrainCategory.PERSISTENCE_FAIL_CLOSED
    )


@pytest.mark.parametrize("event_type", list(AttemptEventType))
def test_classify_drain_returns_a_known_category(
    event_type: AttemptEventType,
) -> None:
    assert classify_drain(event_type) in set(DrainCategory)


@pytest.mark.parametrize(
    "event_type",
    [
        AttemptEventType.STARTED,
        AttemptEventType.RETRY_SCHEDULED,
        AttemptEventType.SUSPENDED,
        AttemptEventType.RESUMED,
        AttemptEventType.EXTERNAL_EFFECT_INTENT,
        AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
        AttemptEventType.RECONCILIATION,
        AttemptEventType.PERSISTENCE_FAILED,
    ],
)
def test_nonterminal_and_persistence_resolve_to_indeterminate(
    event_type: AttemptEventType,
) -> None:
    # Every non-terminal event (including PERSISTENCE_FAILED) resolves to the
    # INDETERMINATE outcome and is flagged as "not a natural terminal drain".
    assert resolves_to_indeterminate(event_type) is True
    assert indeterminate_outcome(event_type) is AttemptOutcome.INDETERMINATE


@pytest.mark.parametrize(
    "event_type,expected",
    [
        (AttemptEventType.COMPLETED, AttemptOutcome.SUCCEEDED),
        (AttemptEventType.FAILED, AttemptOutcome.FAILED),
        (AttemptEventType.CANCELLED, AttemptOutcome.CANCELLED),
    ],
)
def test_terminal_drains_keep_natural_outcome(
    event_type: AttemptEventType, expected: AttemptOutcome
) -> None:
    assert classify_drain(event_type) is DrainCategory.TERMINAL_DRAIN
    assert resolves_to_indeterminate(event_type) is False
    assert indeterminate_outcome(event_type) is expected


def test_drain_map_is_immutable() -> None:
    # MappingProxyType — assignment must raise.
    with pytest.raises(TypeError):
        DRAIN_MAP[AttemptEventType.STARTED] = DrainCategory.TERMINAL_DRAIN  # type: ignore[index]


def test_categories_are_disjoint() -> None:
    assert TERMINAL_DRAIN_EVENT_TYPES.isdisjoint(INDETERMINATE_EVENT_TYPES)
    assert TERMINAL_DRAIN_EVENT_TYPES.isdisjoint(
        PERSISTENCE_FAIL_CLOSED_EVENT_TYPES
    )
    assert INDETERMINATE_EVENT_TYPES.isdisjoint(
        PERSISTENCE_FAIL_CLOSED_EVENT_TYPES
    )
