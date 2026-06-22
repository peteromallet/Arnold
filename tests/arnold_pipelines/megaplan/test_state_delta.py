"""Unit tests for arnold_pipelines.megaplan.state_delta — CAS concurrency control.

Covers:
- replace (last-writer-wins) with version bumping
- accumulate (append-to-list with retention)
- deep_merge (recursive mapping merge)
- Stale version conflict detection and exception attributes
- State not mutated on conflict
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.state_delta import (
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


class TestVersionIndependence:
    """Separate keys have independent version counters."""

    def test_independent_keys(self) -> None:
        state: dict = {}
        d1 = StateDelta(op="replace", key="a", value=1, version=0)
        d2 = StateDelta(op="replace", key="b", value=2, version=0)
        s, _ = apply_delta(state, d1)
        s, _ = apply_delta(s, d2)
        assert s["_state_meta"]["versions"]["a"] == 1
        assert s["_state_meta"]["versions"]["b"] == 1

    def test_same_key_sequential(self) -> None:
        state: dict = {}
        d1 = StateDelta(op="replace", key="a", value=1, version=0)
        d2 = StateDelta(op="replace", key="a", value=2, version=1)
        s, v1 = apply_delta(state, d1)
        assert v1 == 1
        s, v2 = apply_delta(s, d2)
        assert v2 == 2
        assert s["_state_meta"]["versions"]["a"] == 2


class TestEdgeCases:
    def test_missing_state_meta_treated_as_version_0(self) -> None:
        """Keys absent from _state_meta.versions default to version 0."""
        state: dict = {"x": "old"}
        delta = StateDelta(op="replace", key="x", value="new", version=0)
        new_state, v = apply_delta(state, delta)
        assert v == 1
        assert new_state["x"] == "new"

    def test_accumulate_creates_versions_entry(self) -> None:
        state: dict = {}
        delta = StateDelta(op="accumulate", key="log", value="first", version=0)
        new_state, v = apply_delta(state, delta)
        assert v == 1
        assert new_state["_state_meta"]["versions"]["log"] == 1

    def test_deep_merge_creates_versions_entry(self) -> None:
        state: dict = {}
        delta = StateDelta(op="deep_merge", key="cfg", value={"a": 1}, version=0)
        new_state, v = apply_delta(state, delta)
        assert v == 1
        assert new_state["_state_meta"]["versions"]["cfg"] == 1
