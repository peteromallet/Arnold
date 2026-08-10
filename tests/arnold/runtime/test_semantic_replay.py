"""Tests for arnold.runtime.semantic_replay.

Covers:
- semantic_equivalent: identity, byte-different equivalence, ignore_paths,
  unordered_paths, glob/wildcard rejection, type/key/length mismatches
- semantic_replay_journal: reconstruction from events, None on empty,
  equivalence checking with expected_plan
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.runtime.event_journal import NdjsonEventSink
from arnold.runtime.semantic_replay import (
    semantic_equivalent,
    semantic_replay_journal,
)


# ── helpers ─────────────────────────────────────────────────────────────────


def _make_plan(version: int = 1) -> dict[str, Any]:
    return {
        "plan_version": version,
        "sections": [
            {"title": "Summary", "content": "A plan."},
            {"title": "Details", "content": "More details."},
        ],
        "changelog": [
            {
                "critique": "Needs more detail.",
                "verdict": "accept",
                "reason": "Valid.",
                "applied_change": "Added detail.",
            },
        ],
    }


# ── semantic_equivalent ─────────────────────────────────────────────────────


class TestSemanticEquivalentIdentity:
    """Identity and basic equivalence."""

    def test_identical_dicts(self) -> None:
        d = _make_plan()
        eq, diffs = semantic_equivalent(d, d)
        assert eq is True
        assert diffs == []

    def test_identical_lists(self) -> None:
        lst = [1, "two", 3.0, None, True]
        eq, diffs = semantic_equivalent(lst, lst)
        assert eq is True
        assert diffs == []

    def test_identical_scalars(self) -> None:
        for val in [42, "hello", 3.14, True, False, None]:
            eq, diffs = semantic_equivalent(val, val)
            assert eq is True
            assert diffs == []

    def test_numeric_cross_type(self) -> None:
        """int 1 and float 1.0 are semantically equivalent."""
        eq, diffs = semantic_equivalent(1, 1.0)
        assert eq is True
        assert diffs == []

    def test_numeric_cross_type_different_value(self) -> None:
        """int 1 and float 1.5 are NOT equivalent."""
        eq, diffs = semantic_equivalent(1, 1.5)
        assert eq is False


class TestSemanticEquivalentByteDifferent:
    """Byte-different but structurally equivalent inputs."""

    def test_compact_vs_pretty_json(self) -> None:
        d = _make_plan()
        compact = json.dumps(d, separators=(",", ":"))
        pretty = json.dumps(d, indent=2, sort_keys=True)
        assert compact != pretty

        a = json.loads(compact)
        b = json.loads(pretty)
        eq, diffs = semantic_equivalent(a, b)
        assert eq is True
        assert diffs == []

    def test_different_key_ordering(self) -> None:
        a = {"a": 1, "b": 2, "c": 3}
        b = {"c": 3, "a": 1, "b": 2}
        eq, diffs = semantic_equivalent(a, b)
        assert eq is True
        assert diffs == []


class TestSemanticEquivalentIgnorePaths:
    """ignore_paths behaviour."""

    def test_version_path_ignored(self) -> None:
        a = _make_plan(version=1)
        b = _make_plan(version=99)

        # Without ignore_paths — should fail
        eq, diffs = semantic_equivalent(a, b)
        assert eq is False
        assert any("plan_version" in d for d in diffs)

        # With ignore_paths — should pass
        eq, diffs = semantic_equivalent(a, b, ignore_paths=["plan_version"])
        assert eq is True
        assert diffs == []

    def test_nested_ignore_path(self) -> None:
        a = _make_plan()
        b = _make_plan()
        b["changelog"][0]["verdict"] = "reject"

        # Without ignore
        eq, diffs = semantic_equivalent(a, b)
        assert eq is False
        assert any("verdict" in d for d in diffs)

        # With nested ignore
        eq, diffs = semantic_equivalent(
            a, b, ignore_paths=["changelog.0.verdict"],
        )
        assert eq is True
        assert diffs == []

    def test_frozenset_ignore_paths(self) -> None:
        """frozenset (Iterable[str]) works as ignore_paths."""
        a = _make_plan(version=1)
        b = _make_plan(version=99)
        eq, diffs = semantic_equivalent(
            a, b, ignore_paths=frozenset({"plan_version"}),
        )
        assert eq is True


class TestSemanticEquivalentUnorderedPaths:
    """unordered_paths behaviour."""

    def test_unordered_lists_equivalent(self) -> None:
        a = {"items": [1, 2, 3]}
        b = {"items": [3, 1, 2]}
        eq, diffs = semantic_equivalent(a, b, unordered_paths=["items"])
        assert eq is True
        assert diffs == []

    def test_unordered_lists_different_length(self) -> None:
        a = {"items": [1, 2, 3]}
        b = {"items": [1, 2]}
        eq, diffs = semantic_equivalent(a, b, unordered_paths=["items"])
        assert eq is False
        assert any("items" in d for d in diffs)

    def test_unordered_lists_different_content(self) -> None:
        a = {"items": [1, 2, 3]}
        b = {"items": [1, 2, 4]}
        eq, diffs = semantic_equivalent(a, b, unordered_paths=["items"])
        assert eq is False

    def test_unordered_nested(self) -> None:
        a = {"data": {"records": [{"id": 1}, {"id": 2}]}}
        b = {"data": {"records": [{"id": 2}, {"id": 1}]}}
        eq, diffs = semantic_equivalent(a, b, unordered_paths=["data.records"])
        assert eq is True
        assert diffs == []

    def test_unordered_not_applied_without_path(self) -> None:
        """Without unordered_paths, list order matters."""
        a = {"items": [1, 2, 3]}
        b = {"items": [3, 2, 1]}
        eq, diffs = semantic_equivalent(a, b)
        assert eq is False  # order differs


class TestSemanticEquivalentGlobRejection:
    """Glob/wildcard in ignore_paths or unordered_paths raises ValueError."""

    def test_ignore_glob_star_raises(self) -> None:
        with pytest.raises(ValueError, match="glob/wildcard"):
            semantic_equivalent({}, {}, ignore_paths=["changelog.*"])

    def test_ignore_question_mark_raises(self) -> None:
        with pytest.raises(ValueError, match="glob/wildcard"):
            semantic_equivalent({}, {}, ignore_paths=["changelog.?.verdict"])

    def test_ignore_bracket_raises(self) -> None:
        with pytest.raises(ValueError, match="glob/wildcard"):
            semantic_equivalent({}, {}, ignore_paths=["changelog.[0]"])

    def test_unordered_glob_star_raises(self) -> None:
        with pytest.raises(ValueError, match="glob/wildcard"):
            semantic_equivalent({}, {}, unordered_paths=["items.*"])

    def test_unordered_double_dot_raises(self) -> None:
        """Double-dot (..) is also rejected as a traversal pattern."""
        with pytest.raises(ValueError, match="glob/wildcard"):
            semantic_equivalent({}, {}, unordered_paths=["items..sub"])

    def test_dotted_only_paths_accepted(self) -> None:
        """Literal dotted paths without glob chars do NOT raise."""
        eq, diffs = semantic_equivalent(
            _make_plan(), _make_plan(),
            ignore_paths=["changelog.0.verdict", "plan_version"],
            unordered_paths=["sections"],
        )
        assert eq is True
        assert diffs == []


class TestSemanticEquivalentMismatches:
    """Substantive differences are detected and reported."""

    def test_type_mismatch(self) -> None:
        eq, diffs = semantic_equivalent({"key": "val"}, ["not", "a", "dict"])
        assert eq is False
        assert len(diffs) > 0

    def test_key_mismatch(self) -> None:
        eq, diffs = semantic_equivalent({"a": 1}, {"a": 1, "b": 2})
        assert eq is False
        assert len(diffs) > 0

    def test_list_length_mismatch(self) -> None:
        eq, diffs = semantic_equivalent([1, 2], [1, 2, 3])
        assert eq is False
        assert len(diffs) > 0

    def test_scalar_difference(self) -> None:
        eq, diffs = semantic_equivalent("hello", "world")
        assert eq is False
        assert len(diffs) > 0

    def test_bool_vs_int(self) -> None:
        """bool and int are different types."""
        eq, diffs = semantic_equivalent(True, 1)
        assert eq is False

    def test_none_vs_false(self) -> None:
        eq, diffs = semantic_equivalent(None, False)
        assert eq is False

    def test_mutated_verdict_reports_path(self) -> None:
        a = _make_plan()
        b = _make_plan()
        b["changelog"][0]["verdict"] = "reject"

        eq, diffs = semantic_equivalent(a, b)
        assert eq is False
        assert any("changelog" in d and "verdict" in d for d in diffs), (
            f"Expected path containing 'changelog'/'verdict', got {diffs}"
        )

    def test_mutated_section_content_reports_path(self) -> None:
        a = _make_plan()
        b = _make_plan()
        b["sections"][0]["content"] = "Completely different."

        eq, diffs = semantic_equivalent(a, b)
        assert eq is False
        assert any("sections" in d and "content" in d for d in diffs), (
            f"Expected path containing 'sections'/'content', got {diffs}"
        )

    def test_root_difference_reported(self) -> None:
        """Two completely different scalars at root report <root>."""
        eq, diffs = semantic_equivalent(1, 2)
        assert eq is False
        assert diffs == ["<root>"]


# ── semantic_replay_journal ─────────────────────────────────────────────────


class TestSemanticReplayJournal:
    """semantic_replay_journal: reconstruction + equivalence checking."""

    def test_returns_none_for_empty_journal(self, tmp_path: Path) -> None:
        plan, (eq, diffs) = semantic_replay_journal(tmp_path)
        assert plan is None
        assert eq is True
        assert diffs == []

    def test_returns_none_when_no_events_file(self, tmp_path: Path) -> None:
        plan, (eq, diffs) = semantic_replay_journal(tmp_path / "nonexistent")
        assert plan is None
        assert eq is True

    def test_reconstructs_plan_from_state_events(self, tmp_path: Path) -> None:
        sink = NdjsonEventSink(tmp_path)

        # First state event
        sink.emit(
            "state",
            payload={
                "layer": 0,
                "state": {
                    "plan_version": 1,
                    "sections": [{"title": "First", "content": "Initial draft."}],
                },
            },
            phase="layer_1_synth",
        )
        # Second state event (overwrites)
        sink.emit(
            "state",
            payload={
                "layer": 1,
                "state": {
                    "plan_version": 2,
                    "sections": [{"title": "Revised", "content": "Better draft."}],
                },
            },
            phase="layer_2_synth",
        )

        plan, (eq, diffs) = semantic_replay_journal(tmp_path)
        assert plan is not None
        assert plan["plan_version"] == 2
        assert plan["sections"][0]["title"] == "Revised"

    def test_equivalence_check_passes(self, tmp_path: Path) -> None:
        sink = NdjsonEventSink(tmp_path)
        expected = {
            "plan_version": 1,
            "sections": [{"title": "T", "content": "C"}],
        }
        sink.emit(
            "state",
            payload={"layer": 0, "state": expected},
            phase="test",
        )

        plan, (eq, diffs) = semantic_replay_journal(
            tmp_path, expected_plan=expected,
        )
        assert plan is not None
        assert eq is True
        assert diffs == []

    def test_equivalence_check_fails_on_difference(self, tmp_path: Path) -> None:
        sink = NdjsonEventSink(tmp_path)
        actual = {
            "plan_version": 1,
            "sections": [{"title": "T", "content": "C"}],
        }
        sink.emit(
            "state",
            payload={"layer": 0, "state": actual},
            phase="test",
        )

        expected = {
            "plan_version": 1,
            "sections": [{"title": "T", "content": "DIFFERENT"}],
        }
        plan, (eq, diffs) = semantic_replay_journal(
            tmp_path, expected_plan=expected,
        )
        assert plan is not None
        assert eq is False
        assert len(diffs) > 0

    def test_equivalence_with_ignore_paths(self, tmp_path: Path) -> None:
        sink = NdjsonEventSink(tmp_path)
        actual = {
            "plan_version": 99,
            "sections": [{"title": "T", "content": "C"}],
        }
        sink.emit(
            "state",
            payload={"layer": 0, "state": actual},
            phase="test",
        )

        expected = {
            "plan_version": 1,  # different but ignored
            "sections": [{"title": "T", "content": "C"}],
        }
        plan, (eq, diffs) = semantic_replay_journal(
            tmp_path,
            expected_plan=expected,
            ignore_paths=["plan_version"],
        )
        assert plan is not None
        assert eq is True
        assert diffs == []

    def test_ignores_non_state_events(self, tmp_path: Path) -> None:
        sink = NdjsonEventSink(tmp_path)
        # Write a non-state event that should be ignored
        sink.emit(
            "metric",
            payload={"tokens": 100},
            phase="usage",
        )

        plan, (eq, diffs) = semantic_replay_journal(tmp_path)
        assert plan is None  # no state events

    def test_plan_is_original_dict_reference(self, tmp_path: Path) -> None:
        """The returned plan is the folded result, not a copy of expected."""
        sink = NdjsonEventSink(tmp_path)
        data = {"plan_version": 1, "sections": []}
        sink.emit(
            "state",
            payload={"layer": 0, "state": data},
            phase="test",
        )

        plan, (eq, _) = semantic_replay_journal(tmp_path)
        assert plan is not None
        assert plan["plan_version"] == 1
