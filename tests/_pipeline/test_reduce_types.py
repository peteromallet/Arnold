"""Unit tests for ReduceResult / SelectionResult / Reduce alias (M2 / T2a)."""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipelines.megaplan._pipeline.types import (
    Reduce,
    ReduceResult,
    SelectionResult,
    StepContext,
    StepResult,
)


class TestReduceResult:
    def test_construction_defaults(self) -> None:
        r = ReduceResult(value=42)
        assert r.value == 42
        assert r.scores == ()
        assert r.tally == {}
        assert r.provenance == ()
        assert r.label is None

    def test_full_construction(self) -> None:
        r = ReduceResult(
            value="x",
            scores=(0.1, 0.9),
            tally={"a": 1, "b": 2},
            provenance=("step.a", "step.b"),
            label="winner",
        )
        assert r.label == "winner"
        assert r.scores == (0.1, 0.9)

    def test_frozen(self) -> None:
        r = ReduceResult(value=1)
        with pytest.raises(Exception):
            r.value = 2  # type: ignore[misc]

    def test_equality(self) -> None:
        a = ReduceResult(value=1, scores=(0.5,), provenance=("s",))
        b = ReduceResult(value=1, scores=(0.5,), provenance=("s",))
        assert a == b

    def test_hashing_requires_hashable_fields(self) -> None:
        # tally defaults to a dict (mutable) so ReduceResult isn't hashable
        # in the general case; this is expected for frozen dataclasses with
        # Mapping defaults.
        r = ReduceResult(value=1, scores=(0.5,))
        with pytest.raises(TypeError):
            hash(r)


class TestSelectionResult:
    def test_construction_defaults(self) -> None:
        s = SelectionResult(winner=0)
        assert s.winner == 0
        assert s.subset == ()
        assert s.losers == ()
        assert s.scores == ()
        assert s.cleared is False

    def test_frozen(self) -> None:
        s = SelectionResult(winner=0)
        with pytest.raises(Exception):
            s.winner = 1  # type: ignore[misc]

    def test_equality_and_hashing(self) -> None:
        a = SelectionResult(winner=1, subset=(0, 1), losers=(2,), cleared=True)
        b = SelectionResult(winner=1, subset=(0, 1), losers=(2,), cleared=True)
        assert a == b
        assert hash(a) == hash(b)


class TestReduceAlias:
    def test_reduce_alias_is_callable_signature(self) -> None:
        def my_reduce(rs: list[StepResult], ctx: StepContext) -> ReduceResult:
            return ReduceResult(value=len(rs))

        fn: Reduce = my_reduce  # type-check shape via assignment
        ctx = StepContext(
            plan_dir=Path("/tmp"),
            state={},
            profile=None,
            mode="m",
        )
        out = fn([StepResult(), StepResult()], ctx)
        assert out.value == 2
