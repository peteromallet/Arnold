"""Loop-stop predicates for pattern_dynamic and similar control loops.

Each public factory returns a pure ``Callable[[LoopState], bool]``.  The
predicates inspect a :class:`LoopState` snapshot and decide whether the
enclosing loop should terminate.

Conventions
-----------
- ``plateau`` and ``no_improvement`` consult ``state['history']`` — a
  sequence of scalar objective values appended once per iteration.
- ``threshold_reached`` consults a named scalar field on ``state``.
- ``max_iters`` consults ``LoopState.iteration`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class LoopState:
    """Immutable snapshot of a control-loop's observable state."""

    state: Mapping[str, Any]
    last_fanout_results: Any
    iteration: int


def _history(ls: LoopState) -> list[float]:
    h = ls.state.get("history", [])
    return [float(x) for x in h]


def plateau(window: int = 3, eps: float = 1e-3) -> Callable[[LoopState], bool]:
    """Stop when the spread of the last ``window`` history values is ≤ ``eps``."""

    def _pred(ls: LoopState) -> bool:
        h = _history(ls)
        if len(h) < window:
            return False
        tail = h[-window:]
        return (max(tail) - min(tail)) <= eps

    return _pred


def max_iters(n: int) -> Callable[[LoopState], bool]:
    """Stop once ``iteration`` has reached ``n``."""

    def _pred(ls: LoopState) -> bool:
        return ls.iteration >= n

    return _pred


def threshold_reached(field: str, min_value: float) -> Callable[[LoopState], bool]:
    """Stop once ``state[field]`` is ≥ ``min_value``."""

    def _pred(ls: LoopState) -> bool:
        v = ls.state.get(field)
        if v is None:
            return False
        return float(v) >= float(min_value)

    return _pred


def no_improvement(window: int = 3) -> Callable[[LoopState], bool]:
    """Stop when the last ``window`` history values show no strict improvement.

    "Improvement" is defined as strictly increasing; if no pair in the
    trailing window is strictly increasing, the loop is judged stuck.
    """

    def _pred(ls: LoopState) -> bool:
        h = _history(ls)
        if len(h) < window:
            return False
        tail = h[-window:]
        for a, b in zip(tail, tail[1:]):
            if b > a:
                return False
        return True

    return _pred
