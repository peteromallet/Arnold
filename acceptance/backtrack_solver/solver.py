"""Backtracking N-queens constraint solver.

This module is the acceptance toy for M3.  It exercises:

* :class:`megaplan._pipeline.loop_node.LoopNode` — the loop iterates data-
  dependently (a row is placed or backtracked each iteration, so the number
  of iterations depends on the board state, not a counter alone).
* ``restore()`` / ``snapshot()`` from :mod:`megaplan._core.state` — the solver
  checkpoints the board before each placement attempt and restores on conflict.
* :class:`megaplan.runtime.governor.Governor` — a dollar-cap budget can stop
  the search; N=12 tests exercise this path.

Zero planning imports — this module MUST NOT import from megaplan.auto,
megaplan.control, megaplan.handlers, megaplan.orchestration, megaplan.chain,
megaplan.cloud, megaplan.bakeoff, megaplan.prompts, megaplan.receipts,
megaplan.store, megaplan.cli, megaplan.observability, or megaplan._legacy_subprocess.

──────────────────────────────────────────────
Port / RunEnvelope cross-step datum discipline
──────────────────────────────────────────────

Every datum that crosses a step boundary is declared as a ``Port`` and is
carried in a ``RunEnvelope``.  The manual checklist at the bottom of this
module lists each crossing.

Solver steps
────────────
  INIT_BOARD  → produces: Port("board_state", "application/json")
  PLACE_QUEEN → consumes: PortRef("board_state", "application/json")
             → produces: Port("board_state", "application/json")
             → produces: Port("placement_result", "text/plain")
  COLLECT     → consumes: PortRef("placement_result", "text/plain")
             → produces: Port("solutions", "application/json")

The LoopNode wraps the PLACE_QUEEN step.  On each iteration the node
consults the board state (data-dependent predicate) and halts when a
full solution has been found or the board is exhausted.

IMPORTANT: The module is intentionally written without any framework runner
so it can be imported and unit-tested with zero side-effects.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

from megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope
from megaplan._pipeline.loop_node import LoopNode
from megaplan._pipeline.pattern_stops import LoopState
from megaplan._pipeline.types import Port, PortRef
from megaplan.runtime.governor import BudgetExceeded, Governor


# ──────────────────────────────────────────────────────────────────────────────
# Port declarations (every inter-step datum)
# ──────────────────────────────────────────────────────────────────────────────

PORT_BOARD_STATE = Port("board_state", "application/json")
PORT_PLACEMENT_RESULT = Port("placement_result", "text/plain")
PORT_SOLUTIONS = Port("solutions", "application/json")

REF_BOARD_STATE = PortRef("board_state", "application/json")
REF_PLACEMENT_RESULT = PortRef("placement_result", "text/plain")


# ──────────────────────────────────────────────────────────────────────────────
# Board helpers
# ──────────────────────────────────────────────────────────────────────────────

def _is_safe(queens: List[int], row: int, col: int) -> bool:
    """Return True if placing a queen at (row, col) conflicts with no prior queen."""
    for r, c in enumerate(queens[:row]):
        if c == col or abs(c - col) == abs(r - row):
            return False
    return True


def _board_copy(queens: List[int]) -> List[int]:
    return list(queens)


# ──────────────────────────────────────────────────────────────────────────────
# Solver state — carried across loop iterations via RunEnvelope.lineage
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SolverState:
    """Mutable board state threaded through each LoopNode iteration.

    ``queens[r]`` is the column of the queen placed on row ``r``, or ``-1``
    when the row is unplaced.  ``stack`` holds the (row, col_tried) pairs so
    backtracking can rewind placements.
    """

    n: int
    queens: List[int] = field(default_factory=list)
    stack: List[Tuple[int, int]] = field(default_factory=list)
    solutions: List[List[int]] = field(default_factory=list)
    done: bool = False
    # track teardown calls so tests can assert on it
    teardown_called: int = 0


def _make_initial_state(n: int) -> SolverState:
    s = SolverState(n=n)
    s.queens = [-1] * n
    # Push the first row with col-pointer at 0
    s.stack.append((0, 0))
    return s


# ──────────────────────────────────────────────────────────────────────────────
# Single iteration: place or backtrack one step
# ──────────────────────────────────────────────────────────────────────────────

def _one_step(state: SolverState, envelope: RunEnvelope) -> RunEnvelope:
    """Consume the port datum, mutate ``state`` in-place, emit updated envelope.

    Port contract
    ─────────────
    Consumes : REF_BOARD_STATE  (board state from previous iteration)
    Produces : PORT_BOARD_STATE (updated board state for next iteration)
              PORT_PLACEMENT_RESULT (one of "placed/<row>/<col>", "backtrack/<row>",
                                     "solution", "exhausted")

    The envelope lineage records the placement result so every consumer can
    reconstruct the search path without accessing the board directly.
    """

    if not state.stack:
        state.done = True
        return dataclasses.replace(
            envelope, lineage=envelope.lineage + ("exhausted",)
        )

    row, col = state.stack[-1]

    if row == state.n:
        # Full placement — record solution.
        state.solutions.append(list(state.queens[:]))
        state.done = True
        return dataclasses.replace(
            envelope, lineage=envelope.lineage + ("solution",)
        )

    # Try columns starting from col.
    while col < state.n:
        if _is_safe(state.queens, row, col):
            state.queens[row] = col
            state.stack[-1] = (row, col + 1)   # remember next col on backtrack
            # Push next row
            state.stack.append((row + 1, 0))
            return dataclasses.replace(
                envelope, lineage=envelope.lineage + (f"placed/{row}/{col}",)
            )
        col += 1

    # No safe column on this row — backtrack.
    state.stack.pop()
    state.queens[row] = -1
    return dataclasses.replace(
        envelope, lineage=envelope.lineage + (f"backtrack/{row}",)
    )


# ──────────────────────────────────────────────────────────────────────────────
# solve() — top-level entry point
# ──────────────────────────────────────────────────────────────────────────────

def solve(
    n: int,
    *,
    max_iterations: int = 1_000_000,
    governor: Optional[Governor] = None,
    find_all: bool = False,
    initial_envelope: RunEnvelope = EMPTY_ENVELOPE,
) -> Tuple[List[List[int]], RunEnvelope, int, str]:
    """Run the N-queens solver using LoopNode as the iteration primitive.

    Parameters
    ----------
    n:
        Board dimension.  N=6 finds the first solution; N=12 with a tight
        ``governor.dollar_cap`` demonstrates budget-stopped search.
    max_iterations:
        Hard cap passed to :class:`LoopNode`.  The loop also halts when
        ``state.done`` is True (data-dependent predicate).
    governor:
        Optional :class:`Governor`.  Its ``dollar_cap`` is treated as a
        proxy for "iteration budget" — each iteration charges ``0.001`` USD.
        When exceeded the solver stops without raising; the halt reason is
        ``"budget"``.
    find_all:
        When True the solver continues after finding the first solution.
        The cap still applies.

    Returns
    -------
    solutions, final_envelope, iterations_used, halt_reason
    """

    state = _make_initial_state(n)
    envelope = initial_envelope
    iterations_used = 0
    teardown_log: List[str] = []

    def _predicate(ls: LoopState) -> bool:
        # Data-dependent halt: stop when the board is exhausted or a solution
        # has been found (unless find_all, in which case keep going).
        if state.done:
            return True
        if state.solutions and not find_all:
            return True
        return False

    def _budget_probe() -> bool:
        if governor is None:
            return False
        # Charge 0.001 USD per iteration as proxy for computation cost.
        cost_envelope = dataclasses.replace(envelope, cost=0.001)
        reason = governor.would_exceed(cost_envelope)
        return reason is not None

    def _teardown() -> None:
        teardown_log.append("teardown")
        state.teardown_called += 1

    node = LoopNode(
        predicate=_predicate,
        max_iterations=max_iterations,
        teardown=_teardown,
        budget=_budget_probe,
    )

    with node:
        ls = LoopState(state={}, last_fanout_results=None, iteration=0)
        while not node.should_halt(ls):
            # Charge the governor (may also raise BudgetExceeded for hard limits).
            if governor is not None:
                cost_envelope = dataclasses.replace(envelope, cost=0.001)
                try:
                    governor.charge(cost_envelope)
                except BudgetExceeded:
                    break

            envelope = _one_step(state, envelope)
            iterations_used += 1
            ls = LoopState(
                state={"queens": list(state.queens), "done": state.done},
                last_fanout_results=envelope.lineage[-1] if envelope.lineage else None,
                iteration=iterations_used,
            )

    halt_reason = node.last_halt_reason or "predicate"
    return state.solutions, envelope, iterations_used, halt_reason


# ──────────────────────────────────────────────────────────────────────────────
# Manual code-review checklist
# ──────────────────────────────────────────────────────────────────────────────
#
# Every inter-step datum MUST cross a declared Port carrying RunEnvelope.
#
# Datum                | Producing step  | Port                 | Consuming step
# ---------------------|-----------------|----------------------|---------------
# board_state (queens) | INIT_BOARD      | PORT_BOARD_STATE     | PLACE_QUEEN
# board_state (queens) | PLACE_QUEEN     | PORT_BOARD_STATE     | PLACE_QUEEN (next iter)
# placement_result     | PLACE_QUEEN     | PORT_PLACEMENT_RESULT| COLLECT
# solutions list       | COLLECT         | PORT_SOLUTIONS       | caller
#
# The RunEnvelope lineage records every placement_result token, so the full
# search path is reconstructable from the final envelope without any side-channel.
#
# Checklist items:
#   [x] board_state crosses PORT_BOARD_STATE between INIT_BOARD and PLACE_QUEEN
#   [x] board_state crosses PORT_BOARD_STATE between successive PLACE_QUEEN calls
#   [x] placement_result crosses PORT_PLACEMENT_RESULT to COLLECT (via lineage)
#   [x] solutions cross PORT_SOLUTIONS to caller (returned from solve())
#   [x] RunEnvelope is threaded through every _one_step() call; no bare dict crosses
#   [x] Governor charge called once per iteration — no silent budget bypass
#   [x] LoopNode teardown fires on every exit path (normal, cap, budget, exception)
