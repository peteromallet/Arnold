"""StepwiseDriver Protocol and isolation-mode contract.

This module defines the step-level execution protocol that M2b drivers
will implement.  The surface is deliberately minimal: a
``runtime_checkable`` Protocol with three operations (``advance``,
``checkpoint``, ``resume``), a two-element isolation-mode constant
(:data:`ISOLATION_MODES`), and two frozen outcome carriers.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
:data:`ISOLATION_MODES` is a ``frozenset[str]`` rather than an enum so
that settings-validation code can do a membership test without importing
an enum type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.resume import ResumeCursorRef

__all__ = [
    "ISOLATION_MODES",
    "ADVANCE_OUTCOME_KINDS",
    "CHECKPOINT_OUTCOME_KINDS",
    "AdvanceOutcome",
    "CheckpointOutcome",
    "StepwiseDriver",
]


# ---------------------------------------------------------------------------
# Isolation-mode constant
# ---------------------------------------------------------------------------

ISOLATION_MODES: frozenset[str] = frozenset({"in_process", "subprocess_isolated"})
"""The complete set of isolation modes the runtime supports.

Exactly two members: ``"in_process"`` (same-process execution) and
``"subprocess_isolated"`` (forked subprocess with a clean environment).
Settings validation rejects any value outside this set.
"""


# ---------------------------------------------------------------------------
# Outcome kind constants
# ---------------------------------------------------------------------------

ADVANCE_OUTCOME_KINDS: frozenset[str] = frozenset(
    {"advanced", "halted", "awaiting", "failed"}
)
"""Prescribed ``kind`` literal set for :class:`AdvanceOutcome`.

``"advanced"``  — step executed and moved execution forward.
``"halted"``    — pipeline has reached a terminal state.
``"awaiting"``  — step is blocked pending an external signal.
``"failed"``    — step execution failed; ``errors`` carries detail.
"""

CHECKPOINT_OUTCOME_KINDS: frozenset[str] = frozenset(
    {"advanced", "halted", "awaiting", "failed"}
)
"""Prescribed ``kind`` literal set for :class:`CheckpointOutcome`.

Same four members as :data:`ADVANCE_OUTCOME_KINDS`; the shared set keeps
consumer code uniform across outcome types.
"""


# ---------------------------------------------------------------------------
# Outcome carriers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdvanceOutcome:
    """Result of one :meth:`StepwiseDriver.advance` call.

    ``kind`` must be a member of :data:`ADVANCE_OUTCOME_KINDS`.
    ``payload`` is opaque to Arnold.  ``errors`` follows the same
    convention as :class:`~arnold.runtime.operations.OperationResult`:
    first entry is a runtime-neutral error class, rest are driver detail.
    """

    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckpointOutcome:
    """Result of one :meth:`StepwiseDriver.checkpoint` call.

    ``kind`` must be a member of :data:`CHECKPOINT_OUTCOME_KINDS`.
    ``payload`` is opaque to Arnold.
    """

    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# StepwiseDriver Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StepwiseDriver(Protocol):
    """Protocol for Arnold step-level execution drivers.

    Drivers are responsible for the mechanics of executing one step at a
    time within a given isolation boundary.  M2b migrates
    ``megaplan/drivers/`` onto this surface.

    Attributes
    ----------
    isolation_mode:
        One of the two values in :data:`ISOLATION_MODES`:
        ``"in_process"`` or ``"subprocess_isolated"``.
    """

    isolation_mode: str

    def advance(self, envelope: RuntimeEnvelope) -> AdvanceOutcome:  # pragma: no cover
        ...

    def checkpoint(self, envelope: RuntimeEnvelope) -> CheckpointOutcome:  # pragma: no cover
        ...

    def resume(
        self,
        envelope: RuntimeEnvelope,
        cursor: ResumeCursorRef,
    ) -> RuntimeEnvelope:  # pragma: no cover
        ...
