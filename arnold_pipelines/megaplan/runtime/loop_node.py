"""LoopNode primitive.

A :class:`LoopNode` is the explicit loop-control primitive that backs the
:func:`pattern_topology.iterate_until` topology helper. It bundles the
loop's predicate, mandatory iteration cap, optional budget probe, and
mandatory teardown into a single object that fires teardown on every
exit path (normal halt, cap, exception, or budget-exhausted).

T16 (M3): introduced to make loop-control invariants (cap + teardown)
explicit and testable.  Rehomed from ``arnold_pipelines.megaplan._pipeline.loop_node``
to ``arnold_pipelines.megaplan.runtime.loop_node`` during M4 physical deletion.

Contract
--------
``predicate(loop_state)`` returns True to stop the loop. ``loop_state``
is a :class:`arnold.pipeline.pattern_stops.LoopState` extended with a ``budget``
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

from arnold.pipeline.pattern_stops import LoopState


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
        """Return True if the loop should halt this iteration.

        Halting conditions are evaluated in order:

        1. ``predicate`` returns True (normal halt).
        2. ``iteration >= max_iterations`` (cap halt).
        3. ``budget()`` returns True (budget halt).

        The first matching reason is stored in ``last_halt_reason``.
        """
        if self.predicate(ls):
            self.last_halt_reason = "predicate"
            return True
        if ls.iteration >= self.max_iterations:
            self.last_halt_reason = "cap"
            return True
        if self.budget is not None and self.budget():
            self.last_halt_reason = "budget"
            return True
        return False

    def run(
        self,
        initial_state: Mapping[str, Any],
        step: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Run ``step`` iteratively until a halt condition is met.

        ``step`` receives the current state and returns the next state.
        Teardown is guaranteed to run exactly once on every exit path.
        """
        state = dict(initial_state)
        iteration = 0
        last_fanout_results: Any = None
        try:
            while True:
                ls = _LoopStateWithBudget(
                    state=state,
                    last_fanout_results=last_fanout_results,
                    iteration=iteration,
                    budget=self.budget,
                )
                if self.should_halt(ls):
                    break
                state = dict(step(state))
                iteration += 1
        finally:
            self._tear_down()
        return state

    def run_teardown(self) -> None:
        """Idempotent teardown; safe to call repeatedly."""
        if self._torn_down:
            return
        self._torn_down = True
        if self.teardown is not None:
            self.teardown()

    def _tear_down(self) -> None:
        # Backward-compatible alias for internal callers.
        self.run_teardown()

    def __enter__(self) -> "LoopNode":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        # Teardown runs on every exit path, including exception propagation.
        self.run_teardown()
        # Do not suppress exceptions.
        return None


__all__ = ["LoopNode", "_LoopStateWithBudget"]
