"""Unit tests for StateDelta / apply_delta CAS semantics (M2 / T2b)."""

from __future__ import annotations

import pytest

from megaplan._pipeline.types import (
    StateDelta,
    StateDeltaConflict,
    apply_delta,
)


class TestReplaceLWW:
    def test_replace_sets_value_and_bumps_version(self) -> None:
        state: dict = {"x": 1}
        delta = StateDelta(op="replace", key="x", value=99, version=0)
        new_state, new_version = apply_delta(state, delta)
        assert new_state["x"] == 99
        assert new_version == 1
        assert new_state["_state_meta"]["versions"]["x"] == 1

    def test_replace_with_existing_version(self) -> None:
        state: dict = {
            "x": "a",
            "_state_meta": {"versions": {"x": 3}},
        }
        delta = StateDelta(op="replace", key="x", value="b", version=3)
        new_state, new_version = apply_delta(state, delta)
        assert new_state["x"] == "b"
        assert new_version == 4


class TestAccumulateRetention:
    def test_accumulate_appends(self) -> None:
        state: dict = {"events": ["a"]}
        delta = StateDelta(op="accumulate", key="events", value="b", version=0)
        new_state, _ = apply_delta(state, delta)
        assert new_state["events"] == ["a", "b"]

    def test_accumulate_into_missing_key(self) -> None:
        state: dict = {}
        delta = StateDelta(op="accumulate", key="events", value="x", version=0)
        new_state, _ = apply_delta(state, delta)
        assert new_state["events"] == ["x"]


class TestStaleVersionReject:
    def test_stale_version_raises(self) -> None:
        state: dict = {
            "x": 1,
            "_state_meta": {"versions": {"x": 5}},
        }
        delta = StateDelta(op="replace", key="x", value=2, version=3)
        with pytest.raises(StateDeltaConflict) as ei:
            apply_delta(state, delta)
        assert ei.value.key == "x"
        assert ei.value.expected == 3
        assert ei.value.actual == 5

    def test_state_not_mutated_on_conflict(self) -> None:
        state: dict = {"x": 1, "_state_meta": {"versions": {"x": 2}}}
        before = {"x": state["x"], "v": state["_state_meta"]["versions"]["x"]}
        with pytest.raises(StateDeltaConflict):
            apply_delta(
                state, StateDelta(op="replace", key="x", value=9, version=0)
            )
        assert state["x"] == before["x"]
        assert state["_state_meta"]["versions"]["x"] == before["v"]


class TestDeepMerge:
    def test_deep_merge_recurses(self) -> None:
        state: dict = {"cfg": {"a": 1, "nested": {"b": 2}}}
        delta = StateDelta(
            op="deep_merge",
            key="cfg",
            value={"nested": {"c": 3}, "d": 4},
            version=0,
        )
        new_state, _ = apply_delta(state, delta)
        assert new_state["cfg"] == {
            "a": 1,
            "nested": {"b": 2, "c": 3},
            "d": 4,
        }

    def test_deep_merge_overwrites_non_mapping_leaves(self) -> None:
        state: dict = {"cfg": {"x": 1}}
        delta = StateDelta(
            op="deep_merge", key="cfg", value={"x": 9}, version=0
        )
        new_state, _ = apply_delta(state, delta)
        assert new_state["cfg"]["x"] == 9
