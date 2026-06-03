"""Tests for Arnold ``pattern_stops`` module (M3a T21).

Exercises :func:`plateau`, :func:`max_iters`, :func:`threshold_reached`,
and :func:`no_improvement` through the Arnold import path.
"""

from __future__ import annotations

from arnold.pipeline.pattern_stops import (
    LoopState,
    max_iters,
    no_improvement,
    plateau,
    threshold_reached,
)


# ---------------------------------------------------------------------------
# LoopState helper
# ---------------------------------------------------------------------------


def _ls(state: dict | None = None, iteration: int = 0) -> LoopState:
    return LoopState(state=state or {}, last_fanout_results=None, iteration=iteration)


# ---------------------------------------------------------------------------
# plateau
# ---------------------------------------------------------------------------


class TestPlateau:
    def test_plateau_detected(self) -> None:
        pred = plateau(window=3, eps=1e-3)
        state = {"history": [1.0, 1.0, 1.0]}
        assert pred(_ls(state, 3)) is True

    def test_not_enough_history(self) -> None:
        pred = plateau(window=3, eps=1e-3)
        state = {"history": [1.0, 2.0]}
        assert pred(_ls(state, 2)) is False

    def test_spread_exceeds_eps(self) -> None:
        pred = plateau(window=3, eps=0.1)
        state = {"history": [1.0, 1.5, 1.0]}
        assert pred(_ls(state, 3)) is False

    def test_larger_window(self) -> None:
        pred = plateau(window=5, eps=0.01)
        state = {"history": [1.0, 1.0, 1.0, 1.0, 1.0]}
        assert pred(_ls(state, 5)) is True

    def test_empty_history(self) -> None:
        pred = plateau(window=3)
        assert pred(_ls({}, 0)) is False


# ---------------------------------------------------------------------------
# max_iters
# ---------------------------------------------------------------------------


class TestMaxIters:
    def test_stops_when_reached(self) -> None:
        pred = max_iters(10)
        assert pred(_ls(iteration=10)) is True

    def test_continues_before_limit(self) -> None:
        pred = max_iters(5)
        assert pred(_ls(iteration=4)) is False

    def test_zero_iterations_stops_immediately(self) -> None:
        pred = max_iters(0)
        assert pred(_ls(iteration=0)) is True

    def test_negative_n_stops_immediately(self) -> None:
        pred = max_iters(-1)
        assert pred(_ls(iteration=0)) is True


# ---------------------------------------------------------------------------
# threshold_reached
# ---------------------------------------------------------------------------


class TestThresholdReached:
    def test_above_threshold_stops(self) -> None:
        pred = threshold_reached("score", 0.8)
        assert pred(_ls({"score": 0.9}, 5)) is True

    def test_exact_threshold_stops(self) -> None:
        pred = threshold_reached("score", 0.5)
        assert pred(_ls({"score": 0.5}, 1)) is True

    def test_below_threshold_continues(self) -> None:
        pred = threshold_reached("score", 0.8)
        assert pred(_ls({"score": 0.3}, 1)) is False

    def test_missing_field_continues(self) -> None:
        pred = threshold_reached("missing", 0.5)
        assert pred(_ls({}, 0)) is False

    def test_none_value_continues(self) -> None:
        pred = threshold_reached("score", 0.5)
        assert pred(_ls({"score": None}, 0)) is False


# ---------------------------------------------------------------------------
# no_improvement
# ---------------------------------------------------------------------------


class TestNoImprovement:
    def test_no_improvement_detected(self) -> None:
        pred = no_improvement(window=3)
        state = {"history": [10.0, 9.0, 8.0]}
        assert pred(_ls(state, 3)) is True

    def test_strictly_increasing_is_improvement(self) -> None:
        pred = no_improvement(window=3)
        state = {"history": [1.0, 2.0, 3.0]}
        assert pred(_ls(state, 3)) is False

    def test_mixed_with_one_ascent_is_improvement(self) -> None:
        pred = no_improvement(window=3)
        state = {"history": [1.0, 0.5, 1.2]}
        assert pred(_ls(state, 3)) is False

    def test_flat_is_no_improvement(self) -> None:
        pred = no_improvement(window=3)
        state = {"history": [5.0, 5.0, 5.0]}
        assert pred(_ls(state, 3)) is True

    def test_not_enough_history(self) -> None:
        pred = no_improvement(window=5)
        state = {"history": [1.0, 2.0]}
        assert pred(_ls(state, 2)) is False

    def test_custom_window(self) -> None:
        pred = no_improvement(window=2)
        state = {"history": [1.0, 0.5]}
        assert pred(_ls(state, 2)) is True

    def test_empty_history(self) -> None:
        pred = no_improvement(window=3)
        assert pred(_ls({}, 0)) is False


# ---------------------------------------------------------------------------
# Boundary — no Megaplan imports
# ---------------------------------------------------------------------------


class TestPatternStopsBoundary:
    def test_pattern_stops_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = P(__file__).parents[3] / "arnold" / "pipeline" / "pattern_stops.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("megaplan"), (
                            f"pattern_stops.py imports megaplan: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not node.module.startswith(
                        "megaplan"
                    ), (
                        f"pattern_stops.py imports from megaplan: {node.module!r}"
                    )

    def test_loop_state_importable_from_arnold(self) -> None:
        from arnold.pipeline.pattern_stops import LoopState as LS
        assert LS is LoopState
