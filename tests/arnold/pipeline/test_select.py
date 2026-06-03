"""Tests for Arnold ``pattern_select`` module (M3a T21).

Exercises :func:`select`, :func:`top_1`, :func:`top_k`, and
:func:`threshold` through the Arnold import path.
"""

from __future__ import annotations

from arnold.pipeline.pattern_select import (
    select,
    threshold,
    top_1,
    top_k,
)
from arnold.pipeline.types import SelectionResult


# ---------------------------------------------------------------------------
# top_1
# ---------------------------------------------------------------------------


class TestTop1:
    def test_picks_highest_score(self) -> None:
        items = [("a", 0.3), ("b", 0.9), ("c", 0.6)]
        result = select(items, top_1())
        assert isinstance(result, SelectionResult)
        assert result.winner == 1
        assert result.subset == (1,)
        assert result.cleared is True
        assert set(result.losers) == {0, 2}

    def test_single_item_wins(self) -> None:
        items = [("only", 0.5)]
        result = select(items, top_1())
        assert result.winner == 0
        assert result.subset == (0,)
        assert result.losers == ()
        assert result.cleared is True

    def test_bare_scores_work(self) -> None:
        """Items passed as bare numeric scores (not tuples)."""
        items = [0.1, 0.8, 0.3]
        result = select(items, top_1())
        assert result.winner == 1
        assert result.cleared is True

    def test_empty_list_returns_no_winner(self) -> None:
        result = select([], top_1())
        assert result.winner == -1
        assert result.cleared is False

    def test_tie_picks_first_by_index(self) -> None:
        """Tied scores: highest index with that score wins (stable sort)."""
        items = [("a", 0.5), ("b", 0.5), ("c", 0.3)]
        result = select(items, top_1())
        assert result.winner == 0  # first occurrence of 0.5

    def test_scores_preserved_in_result(self) -> None:
        items = [("a", 0.2), ("b", 0.9), ("c", 0.6)]
        result = select(items, top_1())
        # scores are in original order, floats
        assert len(result.scores) == 3
        assert result.scores[0] == 0.2
        assert result.scores[1] == 0.9
        assert result.scores[2] == 0.6


# ---------------------------------------------------------------------------
# top_k
# ---------------------------------------------------------------------------


class TestTopK:
    def test_top_k_returns_k_subset(self) -> None:
        items = [0.1, 0.4, 0.9, 0.7, 0.2]
        result = select(items, top_k(3))
        assert len(result.subset) == 3
        assert result.subset == (2, 3, 1)  # scores 0.9, 0.7, 0.4
        assert result.winner == 2
        assert result.cleared is True

    def test_top_k_larger_than_items(self) -> None:
        items = [("a", 0.3), ("b", 0.5)]
        result = select(items, top_k(10))
        assert len(result.subset) == 2
        assert result.cleared is True

    def test_top_k_zero_returns_empty(self) -> None:
        items = [("a", 0.3), ("b", 0.5)]
        result = select(items, top_k(0))
        assert result.subset == ()
        assert result.cleared is False

    def test_top_k_with_ties(self) -> None:
        items = [("a", 0.8), ("b", 0.8), ("c", 0.5)]
        result = select(items, top_k(2))
        assert len(result.subset) == 2
        assert result.cleared is True

    def test_empty_list_top_k(self) -> None:
        result = select([], top_k(3))
        assert result.winner == -1
        assert result.cleared is False


# ---------------------------------------------------------------------------
# threshold
# ---------------------------------------------------------------------------


class TestThreshold:
    def test_threshold_passes_qualifying_only(self) -> None:
        items = [("a", 0.2), ("b", 0.8), ("c", 0.6)]
        result = select(items, threshold(0.5))
        assert result.cleared is True
        assert result.winner == 1
        assert set(result.subset) == {1, 2}
        assert result.losers == (0,)

    def test_threshold_miss_returns_empty_cleared_false(self) -> None:
        items = [("a", 0.1), ("b", 0.2)]
        result = select(items, threshold(0.9))
        assert result.cleared is False
        assert result.winner == -1
        assert result.subset == ()

    def test_threshold_exact_match_passes(self) -> None:
        items = [("a", 0.5), ("b", 0.3)]
        result = select(items, threshold(0.5))
        assert result.cleared is True
        assert result.winner == 0
        assert result.subset == (0,)

    def test_threshold_all_pass(self) -> None:
        items = [("a", 0.7), ("b", 0.8), ("c", 0.9)]
        result = select(items, threshold(0.0))
        assert result.cleared is True
        assert len(result.subset) == 3

    def test_threshold_negative_scores(self) -> None:
        items = [("a", -0.5), ("b", 0.3)]
        result = select(items, threshold(-0.1))
        assert result.cleared is True
        assert result.winner == 1

    def test_empty_list_threshold(self) -> None:
        result = select([], threshold(0.5))
        assert result.cleared is False
        assert result.winner == -1


# ---------------------------------------------------------------------------
# Boundary — no Megaplan imports
# ---------------------------------------------------------------------------


class TestSelectBoundary:
    def test_pattern_select_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = P(__file__).parents[3] / "arnold" / "pipeline" / "pattern_select.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("megaplan"), (
                            f"pattern_select.py imports megaplan: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not node.module.startswith(
                        "megaplan"
                    ), (
                        f"pattern_select.py imports from megaplan: {node.module!r}"
                    )

    def test_select_importable_from_arnold(self) -> None:
        from arnold.pipeline.pattern_select import select as s
        assert s is select
