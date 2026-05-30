"""Unit tests for megaplan._pipeline.pattern_stops."""

from __future__ import annotations

import pytest

from megaplan._pipeline.pattern_stops import (
    LoopState,
    max_iters,
    no_improvement,
    plateau,
    threshold_reached,
)


def _ls(state=None, *, iteration=0, last=None):
    return LoopState(state=state or {}, last_fanout_results=last, iteration=iteration)


def test_loopstate_is_frozen():
    ls = _ls({"a": 1}, iteration=2)
    with pytest.raises(Exception):
        ls.iteration = 5  # type: ignore[misc]


def test_loopstate_fields():
    ls = LoopState(state={"x": 1}, last_fanout_results=["r"], iteration=3)
    assert ls.state == {"x": 1}
    assert ls.last_fanout_results == ["r"]
    assert ls.iteration == 3


def test_plateau_short_history_returns_false():
    assert plateau(window=3, eps=1e-3)(_ls({"history": [1.0, 1.0]})) is False


def test_plateau_within_eps_returns_true():
    assert plateau(window=3, eps=1e-3)(_ls({"history": [1.0, 1.0005, 1.0009]})) is True


def test_plateau_outside_eps_returns_false():
    assert plateau(window=3, eps=1e-3)(_ls({"history": [1.0, 1.0, 1.1]})) is False


def test_max_iters_below_returns_false():
    assert max_iters(5)(_ls(iteration=4)) is False


def test_max_iters_at_returns_true():
    assert max_iters(5)(_ls(iteration=5)) is True


def test_max_iters_above_returns_true():
    assert max_iters(5)(_ls(iteration=99)) is True


def test_threshold_reached_missing_field_returns_false():
    assert threshold_reached("score", 0.9)(_ls({})) is False


def test_threshold_reached_below_returns_false():
    assert threshold_reached("score", 0.9)(_ls({"score": 0.5})) is False


def test_threshold_reached_at_or_above_returns_true():
    assert threshold_reached("score", 0.9)(_ls({"score": 0.9})) is True
    assert threshold_reached("score", 0.9)(_ls({"score": 1.0})) is True


def test_no_improvement_short_history_returns_false():
    assert no_improvement(window=3)(_ls({"history": [1.0]})) is False


def test_no_improvement_stuck_returns_true():
    assert no_improvement(window=3)(_ls({"history": [1.0, 1.0, 1.0]})) is True
    assert no_improvement(window=3)(_ls({"history": [3.0, 2.0, 1.0]})) is True


def test_no_improvement_with_gain_returns_false():
    assert no_improvement(window=3)(_ls({"history": [1.0, 1.0, 1.1]})) is False


def test_predicates_are_callable_returning_bool():
    for pred in (plateau(), max_iters(1), threshold_reached("x", 0.0), no_improvement()):
        assert callable(pred)
        assert isinstance(pred(_ls()), bool)
