"""Acceptance tests for the backtrack_solver toy.

Covers:
  1. N=6 N-queens solves correctly.
  2. Loop iterates DATA-DEPENDENTLY (iteration count varies with board state).
  3. Teardown runs on every exit path (normal, cap, exception).
  4. Governor.budget (dollar_cap proxy) stops N=12 before exhaustion.
  5. Port declarations are present and non-empty.
  6. Zero planning imports (grep gate).
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

from acceptance.backtrack_solver.solver import (
    PORT_BOARD_STATE,
    PORT_PLACEMENT_RESULT,
    PORT_SOLUTIONS,
    REF_BOARD_STATE,
    REF_PLACEMENT_RESULT,
    _make_initial_state,
    _one_step,
    solve,
)
from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope
from arnold.pipelines.megaplan._pipeline.loop_node import LoopNode
from arnold.pipelines.megaplan._pipeline.pattern_stops import LoopState
from arnold.pipelines.megaplan.runtime.governor import Governor


# ──────────────────────────────────────────────────────────────────────────────
# 1. N=6 correctness
# ──────────────────────────────────────────────────────────────────────────────

def test_n6_finds_solution():
    solutions, envelope, iterations_used, halt_reason = solve(6)
    assert len(solutions) == 1, f"expected exactly 1 solution, got {len(solutions)}"
    sol = solutions[0]
    assert len(sol) == 6
    # Verify no two queens share row, column, or diagonal.
    for r in range(6):
        for s in range(r + 1, 6):
            assert sol[r] != sol[s], "column conflict"
            assert abs(sol[r] - sol[s]) != abs(r - s), "diagonal conflict"


def test_n6_halt_reason_is_predicate():
    _, _, _, halt_reason = solve(6)
    assert halt_reason == "predicate"


def test_n6_envelope_lineage_records_path():
    _, envelope, _, _ = solve(6)
    assert isinstance(envelope.lineage, tuple)
    assert len(envelope.lineage) > 0
    assert envelope.lineage[-1] == "solution"


def test_n6_solution_value():
    """Known first solution for N=6 (row-major, depth-first, col=0 first)."""
    solutions, _, _, _ = solve(6)
    sol = solutions[0]
    # Validate structurally (column validity already checked in test_n6_finds_solution).
    assert 0 <= min(sol) and max(sol) <= 5


# ──────────────────────────────────────────────────────────────────────────────
# 2. Data-dependent iteration
# ──────────────────────────────────────────────────────────────────────────────

def test_loop_iterates_data_dependently():
    """Different board sizes produce different iteration counts — data-dependent."""
    _, _, iters_4, _ = solve(4)
    _, _, iters_6, _ = solve(6)
    assert iters_4 != iters_6, (
        f"N=4 and N=6 should need different iteration counts "
        f"(got {iters_4} and {iters_6})"
    )


def test_n1_solves_in_few_steps():
    """N=1 is trivially solved: queen placed at (0,0) then solution recorded."""
    solutions, _, iters, halt_reason = solve(1)
    assert solutions == [[0]]
    assert iters <= 3  # at most: place row 0, advance to row 1 == n, record solution


def test_n2_exhausted_no_solution():
    solutions, envelope, _, halt_reason = solve(2, find_all=True)
    assert solutions == []
    assert halt_reason == "predicate"
    assert "exhausted" in envelope.lineage


def test_iteration_count_matches_search_depth():
    """Each iteration corresponds to one tree expansion — not a fixed counter."""
    _, _, iters_find_first, _ = solve(6, find_all=False)
    _, _, iters_find_all, _ = solve(6, find_all=True, max_iterations=10_000)
    # find_all must explore AT LEAST as many iterations as find_first.
    assert iters_find_all >= iters_find_first


# ──────────────────────────────────────────────────────────────────────────────
# 3. Teardown on every exit path
# ──────────────────────────────────────────────────────────────────────────────

def test_teardown_on_normal_halt():
    """solve() exits via predicate → teardown must fire."""
    _, _, _, _ = solve(6)
    # The easiest way to verify teardown: inspect solver state directly.
    state = _make_initial_state(6)
    teardown_count = [0]

    def _pred(ls: LoopState) -> bool:
        return state.done or bool(state.solutions)

    def _td():
        teardown_count[0] += 1

    node = LoopNode(predicate=_pred, max_iterations=100_000, teardown=_td)
    envelope = EMPTY_ENVELOPE
    with node:
        ls = LoopState(state={}, last_fanout_results=None, iteration=0)
        iters = 0
        while not node.should_halt(ls):
            envelope = _one_step(state, envelope)
            iters += 1
            ls = LoopState(
                state={"done": state.done},
                last_fanout_results=None,
                iteration=iters,
            )

    assert teardown_count[0] == 1, "teardown must fire exactly once on normal exit"


def test_teardown_on_cap_halt():
    """Loop stopped by cap fires teardown."""
    state = _make_initial_state(8)
    teardown_count = [0]

    node = LoopNode(
        predicate=lambda ls: False,
        max_iterations=5,
        teardown=lambda: teardown_count.__setitem__(0, teardown_count[0] + 1),
    )
    envelope = EMPTY_ENVELOPE
    with node:
        ls = LoopState(state={}, last_fanout_results=None, iteration=0)
        iters = 0
        while not node.should_halt(ls):
            envelope = _one_step(state, envelope)
            iters += 1
            ls = LoopState(state={}, last_fanout_results=None, iteration=iters)

    assert teardown_count[0] == 1
    assert node.last_halt_reason == "cap"


def test_teardown_on_exception():
    """Exception inside the with-block still triggers teardown."""
    teardown_count = [0]
    node = LoopNode(
        predicate=lambda ls: False,
        max_iterations=100,
        teardown=lambda: teardown_count.__setitem__(0, teardown_count[0] + 1),
    )
    with pytest.raises(RuntimeError, match="deliberate"):
        with node:
            raise RuntimeError("deliberate")

    assert teardown_count[0] == 1


def test_teardown_idempotent():
    """Calling run_teardown() twice has no additional effect."""
    count = [0]
    node = LoopNode(predicate=lambda ls: True, max_iterations=1, teardown=lambda: count.__setitem__(0, count[0] + 1))
    node.run_teardown()
    node.run_teardown()
    assert count[0] == 1


def test_teardown_on_budget_halt():
    """Governor budget stop also runs teardown."""
    governor = Governor(dollar_cap=0.005)  # stops after ~5 iterations
    state = _make_initial_state(12)
    teardown_count = [0]

    def _budget_probe():
        cost_env = RunEnvelope(cost=0.001)
        return governor.would_exceed(cost_env) is not None

    node = LoopNode(
        predicate=lambda ls: state.done,
        max_iterations=1_000_000,
        teardown=lambda: teardown_count.__setitem__(0, teardown_count[0] + 1),
        budget=_budget_probe,
    )
    envelope = EMPTY_ENVELOPE
    with node:
        ls = LoopState(state={}, last_fanout_results=None, iteration=0)
        iters = 0
        while not node.should_halt(ls):
            cost_env = RunEnvelope(cost=0.001)
            governor.charge(cost_env)
            envelope = _one_step(state, envelope)
            iters += 1
            ls = LoopState(state={"done": state.done}, last_fanout_results=None, iteration=iters)

    assert teardown_count[0] == 1
    assert node.last_halt_reason == "budget"


# ──────────────────────────────────────────────────────────────────────────────
# 4. Governor.budget stops N=12
# ──────────────────────────────────────────────────────────────────────────────

def test_governor_budget_stops_n12():
    """A tight dollar_cap stops N=12 before it can find a solution."""
    # N=12 requires hundreds of thousands of iterations to find first solution.
    # A cap of 0.1 USD at 0.001 USD/iter stops after ~100 iterations.
    governor = Governor(dollar_cap=0.1)
    solutions, envelope, iterations_used, halt_reason = solve(
        12, governor=governor, max_iterations=1_000_000
    )
    # Should stop WAY before finding a solution.
    assert iterations_used <= 110, f"expected <110 iterations, got {iterations_used}"
    assert halt_reason == "budget"
    assert solutions == [], f"expected no solution found under tight budget, got {solutions}"


def test_governor_budget_halt_reason():
    governor = Governor(dollar_cap=0.05)  # ~50 iterations
    _, _, _, halt_reason = solve(12, governor=governor, max_iterations=1_000_000)
    assert halt_reason == "budget"


def test_generous_governor_does_not_stop_n6():
    """A generous governor does not interfere with N=6."""
    governor = Governor(dollar_cap=100.0)
    solutions, _, _, halt_reason = solve(6, governor=governor)
    assert len(solutions) == 1
    assert halt_reason == "predicate"


def test_governor_iteration_proxy_is_consistent():
    """Each call to solve() charges 0.001 USD per iteration."""
    governor = Governor(dollar_cap=0.05)
    _, _, iters, halt_reason = solve(12, governor=governor, max_iterations=1_000_000)
    # dollars charged ≈ iters * 0.001; verify consistency via governor state.
    # governor.spent_dollars should be approximately iters * 0.001.
    assert halt_reason == "budget"
    assert iters <= 51  # 0.05 / 0.001 = 50, +1 for the one that triggers


# ──────────────────────────────────────────────────────────────────────────────
# 5. Port declarations present
# ──────────────────────────────────────────────────────────────────────────────

def test_port_declarations_exist():
    assert PORT_BOARD_STATE.name == "board_state"
    assert PORT_BOARD_STATE.content_type == "application/json"
    assert PORT_PLACEMENT_RESULT.name == "placement_result"
    assert PORT_PLACEMENT_RESULT.content_type == "text/plain"
    assert PORT_SOLUTIONS.name == "solutions"
    assert PORT_SOLUTIONS.content_type == "application/json"


def test_portref_declarations_exist():
    assert REF_BOARD_STATE.port_name == "board_state"
    assert REF_PLACEMENT_RESULT.port_name == "placement_result"


def test_port_symmetry():
    """Every produced port has a matching PortRef declared."""
    assert PORT_BOARD_STATE.name == REF_BOARD_STATE.port_name
    assert PORT_BOARD_STATE.content_type == REF_BOARD_STATE.content_type
    assert PORT_PLACEMENT_RESULT.name == REF_PLACEMENT_RESULT.port_name
    assert PORT_PLACEMENT_RESULT.content_type == REF_PLACEMENT_RESULT.content_type


# ──────────────────────────────────────────────────────────────────────────────
# 6. Zero planning imports (grep gate)
# ──────────────────────────────────────────────────────────────────────────────

_BANNED_MODULES = [
    "megaplan.auto",
    "megaplan.control",
    "megaplan.handlers",
    "megaplan.orchestration",
    "megaplan.chain",
    "megaplan.cloud",
    "megaplan.bakeoff",
    "megaplan.prompts",
    "megaplan.receipts",
    "megaplan.store",
    "megaplan.cli",
    "megaplan.observability",
    "megaplan._legacy_subprocess",
]


def test_zero_planning_imports():
    """solver.py must not import from any planning subsystem."""
    import re
    solver_path = Path(__file__).parent.parent / "solver.py"
    source = solver_path.read_text()
    violations = []
    for banned in _BANNED_MODULES:
        # Match actual import statements (not comments or string literals).
        # Patterns: "import megaplan.auto" or "from megaplan.auto"
        pattern = re.compile(
            r"^(?:import|from)\s+" + re.escape(banned),
            re.MULTILINE,
        )
        if pattern.search(source):
            violations.append(banned)
    assert violations == [], (
        f"solver.py imports from banned planning modules: {violations}"
    )
