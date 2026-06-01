"""LoopNode primitive.

A :class:`LoopNode` is the explicit loop-control primitive that backs the
:func:`pattern_topology.iterate_until` topology helper. It bundles the
loop's predicate, mandatory iteration cap, optional budget probe, and
mandatory teardown into a single object that fires teardown on every
exit path (normal halt, cap, exception, or budget-exhausted).

T16 (M3): introduced to make loop-control invariants (cap + teardown)
explicit and testable.  ``iterate_until`` now constructs a LoopNode under
the hood; the legacy :func:`iterate_until` and :class:`SubloopStep`
shims continue to work unchanged for existing call sites.

Contract
--------
``predicate(loop_state)`` returns True to stop the loop. ``loop_state``
is a :class:`pattern_stops.LoopState` extended with a ``budget``
attribute (None when no budget is configured).

``max_iterations`` is REQUIRED — there is no "unbounded" mode. The cap
fires whenever ``iteration >= max_iterations``.

``budget()`` is an optional zero-arg probe; when supplied it is called
on every ``should_halt`` and returning True forces a halt with reason
``"budget"``.

``teardown()`` is an optional zero-arg callable that runs EXACTLY ONCE
on every exit path, including exception propagation. The
:class:`LoopNode` is a context manager so callers may simply ``with``
it; the test suite locks teardown-on-exception via that path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from megaplan._pipeline.pattern_stops import LoopState


@dataclass
class _LoopStateWithBudget:
    """LoopState extended with a ``budget`` field for predicate use."""

    state: Mapping[str, Any]
    last_fanout_results: Any
    iteration: int
    budget: Optional[Callable[[], bool]] = None


@dataclass
class LoopNode:
    """Explicit loop-control primitive.

    Fields:
        predicate: callable consulted each iteration; True => halt.
        max_iterations: REQUIRED iteration cap; halt when iteration >= cap.
        teardown: zero-arg cleanup; runs on every exit path.
        budget: optional zero-arg probe; True => force halt with reason "budget".
    """

    predicate: Callable[[Any], bool]
    max_iterations: int
    teardown: Optional[Callable[[], None]] = None
    budget: Optional[Callable[[], bool]] = None

    _torn_down: bool = field(default=False, init=False, repr=False)
    last_halt_reason: Optional[str] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_iterations is None:
            raise ValueError("LoopNode requires max_iterations (no unbounded mode)")
        if int(self.max_iterations) <= 0:
            raise ValueError(
                f"LoopNode max_iterations must be positive, got {self.max_iterations!r}"
            )

    def should_halt(
        self,
        ls: LoopState | _LoopStateWithBudget,
    ) -> bool:
        """Return True when the loop should terminate this iteration."""

        # Cap: hard ceiling, fires regardless of predicate.
        if ls.iteration >= self.max_iterations:
            self.last_halt_reason = "cap"
            return True

        # Budget: optional probe, halts before predicate runs.
        if self.budget is not None and self.budget():
            self.last_halt_reason = "budget"
            return True

        ext = _LoopStateWithBudget(
            state=ls.state,
            last_fanout_results=ls.last_fanout_results,
            iteration=ls.iteration,
            budget=self.budget,
        )
        if self.predicate(ext):
            self.last_halt_reason = "predicate"
            return True

        return False

    def run_teardown(self) -> None:
        """Idempotent teardown; safe to call repeatedly."""

        if self._torn_down:
            return
        self._torn_down = True
        if self.teardown is not None:
            self.teardown()

    def __enter__(self) -> "LoopNode":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        # Teardown runs on every exit path, including exception propagation.
        self.run_teardown()
        # Do not suppress exceptions.
        return None


__all__ = ["LoopNode", "_LoopStateWithBudget"]
