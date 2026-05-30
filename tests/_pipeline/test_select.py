"""T8 — tests for megaplan._pipeline.pattern_select."""

from __future__ import annotations

from megaplan._pipeline.pattern_select import (
    select,
    threshold,
    top_1,
    top_k,
)
from megaplan._pipeline.types import SelectionResult


def test_top_1_picks_highest_score():
    items = [("a", 0.3), ("b", 0.9), ("c", 0.6)]
    result = select(items, top_1())
    assert isinstance(result, SelectionResult)
    assert result.winner == 1
    assert result.subset == (1,)
    assert result.cleared is True
    assert set(result.losers) == {0, 2}


def test_top_k_returns_k_subset():
    items = [0.1, 0.4, 0.9, 0.7, 0.2]
    result = select(items, top_k(3))
    assert len(result.subset) == 3
    # Top 3 are indices 2, 3, 1 (scores 0.9, 0.7, 0.4)
    assert result.subset == (2, 3, 1)
    assert result.winner == 2
    assert result.cleared is True


def test_threshold_pass_keeps_qualifying_only():
    items = [("a", 0.2), ("b", 0.8), ("c", 0.6)]
    result = select(items, threshold(0.5))
    assert result.cleared is True
    assert result.winner == 1
    assert set(result.subset) == {1, 2}
    assert result.losers == (0,)


def test_threshold_miss_returns_empty_cleared_false():
    items = [("a", 0.1), ("b", 0.2)]
    result = select(items, threshold(0.9))
    assert result.cleared is False
    assert result.winner == -1
    assert result.subset == ()
