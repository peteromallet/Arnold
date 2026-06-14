"""Tests for ``megaplan._core.scheduler.topo`` — topological batch scheduling."""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan._core.scheduler.topo import schedule_batches


# ---------------------------------------------------------------------------
# Basic cases
# ---------------------------------------------------------------------------


class TestScheduleBatchesBasic:
    """Basic happy-path and edge cases."""

    def test_empty_returns_empty_list(self):
        """Empty work list → empty batch list."""
        assert schedule_batches([], max_batch_size=5) == []

    def test_single_node(self):
        """A single node with no dependencies → one batch with that node."""
        work = [{"id": "T1", "depends_on": []}]
        result = schedule_batches(work, max_batch_size=5)
        assert result == [["T1"]]

    def test_linear_chain(self):
        """T1 → T2 → T3 — each in its own batch."""
        work = [
            {"id": "T3", "depends_on": ["T2"]},
            {"id": "T2", "depends_on": ["T1"]},
            {"id": "T1", "depends_on": []},
        ]
        result = schedule_batches(work, max_batch_size=5)
        assert result == [["T1"], ["T2"], ["T3"]]

    def test_diamond(self):
        """T1 → T2, T3; T2, T3 → T4."""
        work = [
            {"id": "T1", "depends_on": []},
            {"id": "T2", "depends_on": ["T1"]},
            {"id": "T3", "depends_on": ["T1"]},
            {"id": "T4", "depends_on": ["T2", "T3"]},
        ]
        result = schedule_batches(work, max_batch_size=5)
        assert result == [["T1"], ["T2", "T3"], ["T4"]]

    def test_independent_nodes_same_batch(self):
        """Multiple independent nodes land in the same batch."""
        work = [
            {"id": "T1", "depends_on": []},
            {"id": "T2", "depends_on": []},
            {"id": "T3", "depends_on": []},
        ]
        result = schedule_batches(work, max_batch_size=5)
        assert result == [["T1", "T2", "T3"]]


# ---------------------------------------------------------------------------
# Error cases — matching megaplan/_core/io.py:83 and :99
# ---------------------------------------------------------------------------


class TestScheduleBatchesErrors:
    """Error cases that must match existing behaviour in ``_core/io.py``."""

    def test_unknown_dependency_raises_valueerror(self):
        """A dependency ID not in the work list raises ValueError."""
        work = [
            {"id": "T1", "depends_on": ["T99"]},
        ]
        with pytest.raises(ValueError, match="Unknown dependency ID"):
            schedule_batches(work, max_batch_size=5)

    def test_cycle_raises_valueerror(self):
        """A cyclic dependency graph raises ValueError."""
        work = [
            {"id": "T1", "depends_on": ["T2"]},
            {"id": "T2", "depends_on": ["T1"]},
        ]
        with pytest.raises(ValueError, match="Cyclic dependency"):
            schedule_batches(work, max_batch_size=5)

    def test_self_loop_raises_valueerror(self):
        """A self-loop (T1 depends on T1) raises ValueError (cycle)."""
        work = [
            {"id": "T1", "depends_on": ["T1"]},
        ]
        with pytest.raises(ValueError, match="Cyclic dependency"):
            schedule_batches(work, max_batch_size=5)

    def test_longer_cycle_raises_valueerror(self):
        """A longer cycle T1→T2→T3→T1 raises ValueError."""
        work = [
            {"id": "T1", "depends_on": ["T3"]},
            {"id": "T2", "depends_on": ["T1"]},
            {"id": "T3", "depends_on": ["T2"]},
        ]
        with pytest.raises(ValueError, match="Cyclic dependency"):
            schedule_batches(work, max_batch_size=5)


# ---------------------------------------------------------------------------
# Oversized batch splitting
# ---------------------------------------------------------------------------


class TestScheduleBatchesOversized:
    """Batch splitting via ``split_oversized_batches``."""

    def test_oversized_batch_is_split(self):
        """A batch larger than max_batch_size is split into chunks."""
        work = [{"id": f"T{i}", "depends_on": []} for i in range(1, 8)]
        result = schedule_batches(work, max_batch_size=3)
        # 7 independent nodes, max 3 per batch → 3 batches: 3, 3, 1
        assert len(result) == 3
        assert result[0] == ["T1", "T2", "T3"]
        assert result[1] == ["T4", "T5", "T6"]
        assert result[2] == ["T7"]

    def test_max_batch_size_zero_uses_default(self):
        """max_batch_size=0 falls back to default_max_size=5."""
        work = [{"id": f"T{i}", "depends_on": []} for i in range(1, 7)]
        result = schedule_batches(work, max_batch_size=0)
        # 6 nodes, max 5 → 2 batches: 5, 1
        assert len(result) == 2
        assert len(result[0]) == 5
        assert len(result[1]) == 1

    def test_max_batch_size_negative_uses_default(self):
        """max_batch_size=-1 falls back to default_max_size=5."""
        work = [{"id": f"T{i}", "depends_on": []} for i in range(1, 7)]
        result = schedule_batches(work, max_batch_size=-1)
        assert len(result) == 2
        assert len(result[0]) == 5
        assert len(result[1]) == 1

    def test_custom_default_max_size(self):
        """Custom default_max_size is used when max_batch_size ≤ 0."""
        work = [{"id": f"T{i}", "depends_on": []} for i in range(1, 11)]
        result = schedule_batches(work, max_batch_size=0, default_max_size=3)
        # 10 nodes, max 3 → 4 batches: 3, 3, 3, 1
        assert len(result) == 4
        assert all(len(b) <= 3 for b in result)


# ---------------------------------------------------------------------------
# completed_ids — matching auto-loop call at megaplan/execute/batch.py:1006
# ---------------------------------------------------------------------------


class TestScheduleBatchesCompletedIds:
    """``completed_ids`` threading through to ``compute_task_batches``."""

    def test_completed_ids_excludes_completed_nodes(self):
        """A completed dependency is treated as satisfied — the dependent
        task appears in the first batch alongside other ready nodes."""
        work = [
            {"id": "T1", "depends_on": []},
            {"id": "T2", "depends_on": ["T1"]},
            {"id": "T3", "depends_on": []},
        ]
        # T1 is already completed → T2 can run immediately
        result = schedule_batches(work, max_batch_size=5, completed_ids={"T1"})
        assert result == [["T2", "T3"]]

    def test_completed_ids_unknown_raises(self):
        """If a dependency is unknown (not in work list and not completed),
        it still raises ValueError (the completed check in compute_task_batches
        only allows deps that are either in task_id_set OR in completed)."""
        work = [
            {"id": "T1", "depends_on": ["T99"]},
        ]
        # T99 is neither in work nor completed → ValueError
        with pytest.raises(ValueError, match="Unknown dependency ID"):
            schedule_batches(work, max_batch_size=5, completed_ids={"T1"})

    def test_completed_ids_all_satisfied(self):
        """All dependencies completed → all nodes in first batch."""
        work = [
            {"id": "T1", "depends_on": ["TA"]},
            {"id": "T2", "depends_on": ["TB"]},
        ]
        result = schedule_batches(
            work, max_batch_size=5, completed_ids={"TA", "TB"}
        )
        assert result == [["T1", "T2"]]

    def test_completed_ids_partial(self):
        """Partially completed dependencies — only satisfied nodes advance."""
        work = [
            {"id": "T1", "depends_on": []},
            {"id": "T2", "depends_on": ["T1"]},
            {"id": "T3", "depends_on": ["T1"]},
            {"id": "T4", "depends_on": ["T2", "T3"]},
        ]
        # T1 is done, T2 and T3 can run
        result = schedule_batches(work, max_batch_size=5, completed_ids={"T1"})
        assert result == [["T2", "T3"], ["T4"]]

    def test_completed_ids_empty_keeps_phantom_dependency_blocked(self):
        """If the authority wrapper withholds a raw terminal claim, the dependent stays blocked."""
        work = [
            {"id": "T1", "depends_on": []},
            {"id": "T2", "depends_on": ["T1"]},
        ]

        assert schedule_batches(work, max_batch_size=5, completed_ids=set()) == [["T1"], ["T2"]]

    def test_completed_ids_only_unlock_when_wrapper_supplies_corroborated_dependency(self):
        """Scheduler unlocks solely from the corroborated completed_ids input contract."""
        work = [
            {"id": "T1", "depends_on": []},
            {"id": "T2", "depends_on": ["T1"]},
        ]

        assert schedule_batches(work, max_batch_size=5, completed_ids={"T1"}) == [["T2"]]


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------


class TestScheduleBatchesSanity:
    """Ensure the function rejects non-standard inputs gracefully."""

    def test_accepts_arbitrary_dicts_without_extra_fields(self):
        """The function does not require complexity/status/planning fields."""
        work = [
            {"id": "A", "depends_on": [], "extra_field": 42},
            {"id": "B", "depends_on": ["A"]},
        ]
        result = schedule_batches(work, max_batch_size=5)
        assert result == [["A"], ["B"]]

    def test_depends_on_not_a_list_treated_as_empty(self):
        """Non-list ``depends_on`` is treated as ``[]`` (io.py:74-75)."""
        work = [
            {"id": "T1", "depends_on": "not_a_list"},
        ]
        result = schedule_batches(work, max_batch_size=5)
        assert result == [["T1"]]

    def test_no_import_leak_from_execute_or_handlers(self):
        """The topo module MUST NOT import from arnold.pipelines.megaplan.execute or
        megaplan.handlers."""
        import arnold.pipelines.megaplan._core.scheduler.topo as mod

        source = open(mod.__file__).read()
        assert "arnold.pipelines.megaplan.execute" not in source, (
            "topo.py must not import from arnold.pipelines.megaplan.execute"
        )
        assert "arnold.pipelines.megaplan.handlers" not in source, (
            "topo.py must not import from arnold.pipelines.megaplan.handlers"
        )
