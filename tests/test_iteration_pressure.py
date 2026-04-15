"""Tests for megaplan.iteration_pressure — flag history, fuzzy grouping, pressure computation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan.iteration_pressure import (
    IterationPressureEntry,
    compute_flag_history,
    compute_fuzzy_groups,
    compute_iteration_pressure,
    has_mechanical_recurrence,
    render_pressure_table,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_critique(plan_dir: Path, iteration: int, flags: list[dict]) -> None:
    data = {"flags": flags, "checks": []}
    (plan_dir / f"critique_v{iteration}.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


def _make_state(iteration: int = 1) -> dict:
    return {"iteration": iteration, "config": {"project_dir": "/tmp"}}


# ---------------------------------------------------------------------------
# compute_flag_history
# ---------------------------------------------------------------------------


class TestComputeFlagHistory:
    def test_single_critique(self, tmp_path: Path) -> None:
        _write_critique(tmp_path, 1, [
            {"id": "F1", "status": "open", "concern": "missing validation"},
        ])
        history = compute_flag_history(tmp_path, 1)
        assert len(history) == 1
        assert history[0]["id"] == "F1"
        assert history[0]["addressed_then_reopened_count"] == 0

    def test_addressed_then_reopened(self, tmp_path: Path) -> None:
        _write_critique(tmp_path, 1, [
            {"id": "F1", "status": "open", "concern": "bootstrap race condition"},
        ])
        _write_critique(tmp_path, 2, [
            {"id": "F1", "status": "addressed", "concern": "bootstrap race condition"},
        ])
        _write_critique(tmp_path, 3, [
            {"id": "F1", "status": "open", "concern": "bootstrap race condition"},
        ])
        history = compute_flag_history(tmp_path, 3)
        assert len(history) == 1
        assert history[0]["addressed_then_reopened_count"] == 1

    def test_double_reopen_gives_count_2(self, tmp_path: Path) -> None:
        """Flag raised -> addressed -> reopened -> addressed -> reopened = count 2."""
        _write_critique(tmp_path, 1, [
            {"id": "F1", "status": "open", "concern": "architectural conflict"},
        ])
        _write_critique(tmp_path, 2, [
            {"id": "F1", "status": "addressed", "concern": "architectural conflict"},
        ])
        _write_critique(tmp_path, 3, [
            {"id": "F1", "status": "open", "concern": "architectural conflict"},
        ])
        _write_critique(tmp_path, 4, [
            {"id": "F1", "status": "addressed", "concern": "architectural conflict"},
        ])
        _write_critique(tmp_path, 5, [
            {"id": "F1", "status": "open", "concern": "architectural conflict"},
        ])
        history = compute_flag_history(tmp_path, 5)
        assert len(history) == 1
        assert history[0]["addressed_then_reopened_count"] == 2

    def test_faults_only_for_new_flags(self, tmp_path: Path) -> None:
        _write_critique(tmp_path, 1, [
            {"id": "F1", "status": "open", "concern": "concern A"},
        ])
        faults = {"flags": [
            {"id": "F1", "status": "open", "concern": "concern A"},
            {"id": "F2", "status": "open", "concern": "concern B"},
        ]}
        (tmp_path / "faults.json").write_text(json.dumps(faults), encoding="utf-8")
        history = compute_flag_history(tmp_path, 1)
        ids = {h["id"] for h in history}
        assert "F1" in ids
        assert "F2" in ids
        f2 = [h for h in history if h["id"] == "F2"][0]
        assert f2["iterations"] == [0]

    def test_no_critiques(self, tmp_path: Path) -> None:
        history = compute_flag_history(tmp_path, 3)
        assert history == []


# ---------------------------------------------------------------------------
# compute_fuzzy_groups
# ---------------------------------------------------------------------------


class TestComputeFuzzyGroups:
    def test_similar_flags_grouped(self) -> None:
        flags = [
            {"id": "F1", "concern": "bootstrap race condition in startup"},
            {"id": "F2", "concern": "bootstrap race condition in initialization"},
        ]
        groups = compute_fuzzy_groups(flags, threshold=0.6)
        assert len(groups) == 1
        gid = list(groups.keys())[0]
        assert set(groups[gid]) == {"F1", "F2"}

    def test_dissimilar_flags_separate(self) -> None:
        flags = [
            {"id": "F1", "concern": "bootstrap race condition in startup"},
            {"id": "F2", "concern": "missing input validation for user email"},
        ]
        groups = compute_fuzzy_groups(flags, threshold=0.6)
        assert len(groups) == 2

    def test_empty_flags(self) -> None:
        groups = compute_fuzzy_groups([], threshold=0.6)
        assert groups == {}

    def test_single_flag(self) -> None:
        flags = [{"id": "F1", "concern": "something"}]
        groups = compute_fuzzy_groups(flags, threshold=0.6)
        assert len(groups) == 1
        assert list(groups.values())[0] == ["F1"]


# ---------------------------------------------------------------------------
# compute_iteration_pressure (end-to-end)
# ---------------------------------------------------------------------------


class TestComputeIterationPressure:
    def test_end_to_end_double_reopen(self, tmp_path: Path) -> None:
        """v1: open, v2: addressed, v2 critique: reopened, v3: addressed, v3 critique: reopened."""
        _write_critique(tmp_path, 1, [
            {"id": "F1", "status": "open", "concern": "store vs RQ first"},
        ])
        _write_critique(tmp_path, 2, [
            {"id": "F1", "status": "addressed", "concern": "store vs RQ first"},
            {"id": "F1", "status": "open", "concern": "store vs RQ first"},
        ])
        _write_critique(tmp_path, 3, [
            {"id": "F1", "status": "addressed", "concern": "store vs RQ first"},
            {"id": "F1", "status": "open", "concern": "store vs RQ first"},
        ])
        state = _make_state(iteration=3)
        entries = compute_iteration_pressure(tmp_path, state)
        assert len(entries) >= 1
        f1_entry = [e for e in entries if "F1" in e["member_flag_ids"]][0]
        assert f1_entry["addressed_then_reopened_count"] == 2

    def test_no_pressure_without_critiques(self, tmp_path: Path) -> None:
        state = _make_state(iteration=1)
        entries = compute_iteration_pressure(tmp_path, state)
        assert entries == []

    def test_multiple_groups(self, tmp_path: Path) -> None:
        _write_critique(tmp_path, 1, [
            {"id": "F1", "status": "open", "concern": "bootstrap race condition"},
            {"id": "F2", "status": "open", "concern": "missing email validation"},
        ])
        state = _make_state(iteration=1)
        entries = compute_iteration_pressure(tmp_path, state)
        assert len(entries) == 2


# ---------------------------------------------------------------------------
# has_mechanical_recurrence
# ---------------------------------------------------------------------------


class TestHasMechanicalRecurrence:
    def test_true_on_reopen_count(self) -> None:
        entries: list[IterationPressureEntry] = [
            IterationPressureEntry(
                fuzzy_group_id="FG-001",
                member_flag_ids=["F1"],
                iterations_open=3,
                addressed_then_reopened_count=2,
                representative_concern="test",
            )
        ]
        assert has_mechanical_recurrence(entries) is True

    def test_true_on_multi_flag_multi_iter(self) -> None:
        entries: list[IterationPressureEntry] = [
            IterationPressureEntry(
                fuzzy_group_id="FG-001",
                member_flag_ids=["F1", "F2"],
                iterations_open=2,
                addressed_then_reopened_count=0,
                representative_concern="test",
            )
        ]
        assert has_mechanical_recurrence(entries) is True

    def test_false_below_threshold(self) -> None:
        entries: list[IterationPressureEntry] = [
            IterationPressureEntry(
                fuzzy_group_id="FG-001",
                member_flag_ids=["F1"],
                iterations_open=1,
                addressed_then_reopened_count=1,
                representative_concern="test",
            )
        ]
        assert has_mechanical_recurrence(entries) is False

    def test_false_on_empty(self) -> None:
        assert has_mechanical_recurrence([]) is False


# ---------------------------------------------------------------------------
# render_pressure_table
# ---------------------------------------------------------------------------


class TestRenderPressureTable:
    def test_renders_nonempty(self) -> None:
        entries: list[IterationPressureEntry] = [
            IterationPressureEntry(
                fuzzy_group_id="FG-001",
                member_flag_ids=["F1", "F2"],
                iterations_open=3,
                addressed_then_reopened_count=2,
                representative_concern="bootstrap race condition",
            )
        ]
        table = render_pressure_table(entries)
        assert "FG-001" in table
        assert "Iteration Pressure" in table

    def test_empty_returns_empty_string(self) -> None:
        assert render_pressure_table([]) == ""
