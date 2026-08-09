"""Exhaustive drain-vs-indeterminate mapping for cutover quiesce (CL5 Step 12a).

During cutover quiesce (CL5 Step 12b) every in-flight attempt must be
classified so the cutover can decide whether to wait for a natural terminal
event or to mark the attempt ``INDETERMINATE``. This module defines that
classification as an explicit, exhaustive mapping over **every**
:class:`~arnold.workflow.execution_attempt_ledger.AttemptEventType` value:

* **TERMINAL_DRAIN** (3) — ``COMPLETED``, ``FAILED``, ``CANCELLED``. These are
  the terminal attempt states (``_TERMINAL_EVENT_TYPES`` in
  ``execution_attempt_ledger``). They drain naturally: the attempt reached a
  clean terminal outcome, so no indeterminate marking is required.
* **INDETERMINATE** (7) — ``STARTED``, ``RETRY_SCHEDULED``, ``SUSPENDED``,
  ``RESUMED``, ``EXTERNAL_EFFECT_INTENT``, ``EXTERNAL_EFFECT_OUTCOME``,
  ``RECONCILIATION``. These are non-terminal states with no clean drain: if an
  attempt has not reached a terminal event by the quiesce timeout it becomes
  ``INDETERMINATE`` (fail-closed default).
* **PERSISTENCE_FAIL_CLOSED** (1) — ``PERSISTENCE_FAILED``. A persistence
  failure means the attempt's recorded state is uncertain, so it always
  becomes ``INDETERMINATE``. It gets its own category so callers can
  distinguish "uncertain because it never drained" from "uncertain because
  persistence failed", while both resolve to the indeterminate outcome.

The mapping is exhaustive: every member of ``AttemptEventType`` is classified
exactly once, and :func:`assert_drain_map_exhaustive` enforces that
invariant at import/test time.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from arnold.workflow.execution_attempt_ledger import (
    AttemptEventType,
    AttemptOutcome,
    _TERMINAL_EVENT_TYPES,
)


class DrainCategory(StrEnum):
    """How a given ``AttemptEventType`` is handled during cutover drain."""

    TERMINAL_DRAIN = "terminal_drain"
    INDETERMINATE = "indeterminate"
    PERSISTENCE_FAIL_CLOSED = "persistence_fail_closed"


# Terminal drain set — mirrors ``_TERMINAL_EVENT_TYPES`` exactly (asserted in
# tests) so the drain map never drifts from the source-of-truth terminal set.
TERMINAL_DRAIN_EVENT_TYPES: frozenset[AttemptEventType] = frozenset(
    {
        AttemptEventType.COMPLETED,
        AttemptEventType.FAILED,
        AttemptEventType.CANCELLED,
    }
)

# Non-terminal states that become INDETERMINATE if they fail to drain by the
# quiesce timeout.
INDETERMINATE_EVENT_TYPES: frozenset[AttemptEventType] = frozenset(
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

# PERSISTENCE_FAILED is its own fail-closed category: persistence failure means
# the attempt's recorded state is uncertain, so it resolves to INDETERMINATE.
PERSISTENCE_FAIL_CLOSED_EVENT_TYPES: frozenset[AttemptEventType] = frozenset(
    {AttemptEventType.PERSISTENCE_FAILED}
)


def _build_drain_map() -> Mapping[AttemptEventType, DrainCategory]:
    mapping: dict[AttemptEventType, DrainCategory] = {}
    for event_type in TERMINAL_DRAIN_EVENT_TYPES:
        mapping[event_type] = DrainCategory.TERMINAL_DRAIN
    for event_type in INDETERMINATE_EVENT_TYPES:
        mapping[event_type] = DrainCategory.INDETERMINATE
    for event_type in PERSISTENCE_FAIL_CLOSED_EVENT_TYPES:
        mapping[event_type] = DrainCategory.PERSISTENCE_FAIL_CLOSED
    return MappingProxyType(mapping)


#: Exhaustive, immutable classification of every ``AttemptEventType``.
DRAIN_MAP: Mapping[AttemptEventType, DrainCategory] = _build_drain_map()


def classify_drain(event_type: AttemptEventType) -> DrainCategory:
    """Return the :class:`DrainCategory` for ``event_type``.

    Raises :class:`KeyError` for any value not present in :data:`DRAIN_MAP`
    — which, for a current ``AttemptEventType`` member, never happens because
    the map is exhaustive (enforced by
    :func:`assert_drain_map_exhaustive`). A ``KeyError`` therefore signals a
    new ``AttemptEventType`` member was added without updating the drain map,
    which the cutover must treat as a hard failure rather than guessing.
    """
    try:
        return DRAIN_MAP[event_type]
    except KeyError:
        raise KeyError(
            f"AttemptEventType.{event_type.name} is not classified in the "
            "cutover drain map; add it before cutting over."
        ) from None


def resolves_to_indeterminate(event_type: AttemptEventType) -> bool:
    """Whether ``event_type`` resolves to the ``INDETERMINATE`` outcome during
    quiesce (i.e. it is NOT a natural terminal drain)."""
    return classify_drain(event_type) is not DrainCategory.TERMINAL_DRAIN


def indeterminate_outcome(event_type: AttemptEventType) -> AttemptOutcome:
    """The terminal outcome a non-drained attempt resolves to.

    Terminal-drain event types keep their natural outcome mapping
    (``COMPLETED``→``SUCCEEDED``, ``FAILED``→``FAILED``,
    ``CANCELLED``→``CANCELLED``); every other event type resolves to
    :attr:`AttemptOutcome.INDETERMINATE`.
    """
    if classify_drain(event_type) is DrainCategory.TERMINAL_DRAIN:
        return {
            AttemptEventType.COMPLETED: AttemptOutcome.SUCCEEDED,
            AttemptEventType.FAILED: AttemptOutcome.FAILED,
            AttemptEventType.CANCELLED: AttemptOutcome.CANCELLED,
        }[event_type]
    return AttemptOutcome.INDETERMINATE


# Category counts — documented contract; asserted by the exhaustiveness tests.
TERMINAL_DRAIN_COUNT: int = 3
INDETERMINATE_COUNT: int = 7
PERSISTENCE_FAIL_CLOSED_COUNT: int = 1


def assert_drain_map_exhaustive() -> None:
    """Assert the drain map classifies every ``AttemptEventType`` exactly once.

    Called by the exhaustiveness tests. A new enum member added without
    updating the drain map fails this assertion, preventing a silent gap in
    the cutover classification.
    """
    all_members = set(AttemptEventType)
    classified = set(DRAIN_MAP)
    missing = all_members - classified
    extra = classified - all_members
    assert not missing, (
        f"AttemptEventType values missing from DRAIN_MAP: "
        f"{sorted(e.name for e in missing)}"
    )
    assert not extra, (
        f"DRAIN_MAP classifies non-members: {sorted(e.name for e in extra)}"
    )
    # The categories are disjoint by construction; assert it explicitly.
    assert (
        TERMINAL_DRAIN_EVENT_TYPES.isdisjoint(INDETERMINATE_EVENT_TYPES)
    ), "terminal-drain and indeterminate sets overlap"
    assert (
        TERMINAL_DRAIN_EVENT_TYPES.isdisjoint(PERSISTENCE_FAIL_CLOSED_EVENT_TYPES)
    ), "terminal-drain and persistence-fail-closed sets overlap"
    assert (
        INDETERMINATE_EVENT_TYPES.isdisjoint(PERSISTENCE_FAIL_CLOSED_EVENT_TYPES)
    ), "indeterminate and persistence-fail-closed sets overlap"
    assert len(TERMINAL_DRAIN_EVENT_TYPES) == TERMINAL_DRAIN_COUNT
    assert len(INDETERMINATE_EVENT_TYPES) == INDETERMINATE_COUNT
    assert (
        len(PERSISTENCE_FAIL_CLOSED_EVENT_TYPES) == PERSISTENCE_FAIL_CLOSED_COUNT
    )


# Fail fast at import if the enum and the map ever drift apart, so a stale
# drain map can never silently cut over an unclassified event type.
assert_drain_map_exhaustive()
