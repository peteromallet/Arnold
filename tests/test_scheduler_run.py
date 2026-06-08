"""Tests for ``megaplan._core.scheduler.run`` — the scatter→batch→process→reduce loop.

Drives the scheduler with a fake synchronous in-memory ``process_driver`` and
a fake ``reduce`` returning a non-planning ``Reduce[Literal['ok','retry']]``,
asserting correct batch ordering, that ``reduce`` is invoked once per batch
with the batch's process result, and that the scheduler returns the typed
``Reduce`` items unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import pytest

from arnold.pipelines.megaplan._core.scheduler.run import ProcessDriver, run_scheduler
from arnold.pipelines.megaplan._core.scheduler.types import Reduce


# ---------------------------------------------------------------------------
# Fake driver and reduce for testing
# ---------------------------------------------------------------------------


class FakeProcessDriver:
    """In-memory process driver that records every batch it processes."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def process(self, batch: list[str]) -> dict[str, Any]:
        """Record the batch IDs and return a simple result dict."""
        self.calls.append(list(batch))
        return {"processed": list(batch), "count": len(batch)}


@dataclass
class FakeReduceResult:
    """Result returned by the fake reduce, for assertion purposes."""

    batch_ids: list[str]
    batch_index: int
    processed_count: int


def fake_reduce(
    batch_result: dict[str, Any],
    *,
    batch: list[str],
    batch_index: int,
) -> Reduce[Literal["ok", "retry"]]:
    """Fake reduce that returns ok/retry based on count."""
    # Store for assertions
    _fake_reduce_calls.append(
        FakeReduceResult(
            batch_ids=list(batch),
            batch_index=batch_index,
            processed_count=batch_result["count"],
        )
    )
    outcome: Literal["ok", "retry"] = "ok" if batch_result["count"] > 0 else "retry"
    return Reduce(value=outcome)


_fake_reduce_calls: list[FakeReduceResult] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(task_id: str, depends_on: list[str] | None = None) -> dict[str, Any]:
    """Create a minimal task dict with ``id`` and ``depends_on``."""
    return {"id": task_id, "depends_on": depends_on or []}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunScheduler:
    """Tests for ``run_scheduler``."""

    def setup_method(self) -> None:
        """Reset global state before each test."""
        global _fake_reduce_calls
        _fake_reduce_calls = []

    # -- basic scheduling ---------------------------------------------------

    def test_single_node_single_batch(self):
        """Single task → one batch → one reduce call."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return [_make_task("T1")]

        results = run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=5,
        )

        assert len(results) == 1
        assert results[0].value == "ok"
        assert driver.calls == [["T1"]]
        assert len(_fake_reduce_calls) == 1
        assert _fake_reduce_calls[0].batch_ids == ["T1"]
        assert _fake_reduce_calls[0].batch_index == 0

    def test_linear_chain_two_batches(self):
        """Linear chain T1→T2 → two sequential batches."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return [
                _make_task("T1"),
                _make_task("T2", depends_on=["T1"]),
            ]

        results = run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=5,
        )

        assert len(results) == 2
        assert results[0].value == "ok"
        assert results[1].value == "ok"
        assert driver.calls == [["T1"], ["T2"]]
        assert len(_fake_reduce_calls) == 2
        assert _fake_reduce_calls[0].batch_ids == ["T1"]
        assert _fake_reduce_calls[0].batch_index == 0
        assert _fake_reduce_calls[1].batch_ids == ["T2"]
        assert _fake_reduce_calls[1].batch_index == 1

    def test_diamond_dependency(self):
        """Diamond: T1→T2, T1→T3, T2+T3→T4."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return [
                _make_task("T1"),
                _make_task("T2", depends_on=["T1"]),
                _make_task("T3", depends_on=["T1"]),
                _make_task("T4", depends_on=["T2", "T3"]),
            ]

        results = run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=5,
        )

        # T1 in batch 0; T2+T3 (both depend on T1) in batch 1; T4 in batch 2
        assert len(results) == 3
        assert driver.calls[0] == ["T1"]
        assert set(driver.calls[1]) == {"T2", "T3"}
        assert driver.calls[2] == ["T4"]
        assert len(_fake_reduce_calls) == 3

    # -- completed_ids ------------------------------------------------------

    def test_completed_ids_skip_task(self):
        """Completed task is excluded from scheduling."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return [
                _make_task("T1"),
                _make_task("T2", depends_on=["T1"]),
            ]

        results = run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=5,
            completed_ids={"T1"},
        )

        # Only T2 should be scheduled (T1's dependency satisfied by completed)
        assert len(results) == 1
        assert driver.calls == [["T2"]]
        assert _fake_reduce_calls[0].batch_ids == ["T2"]

    def test_all_completed_empty_result(self):
        """All tasks completed → empty result list."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return [_make_task("T1")]

        results = run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=5,
            completed_ids={"T1"},
        )

        assert results == []
        assert driver.calls == []

    # -- batch ordering -----------------------------------------------------

    def test_independent_nodes_same_batch(self):
        """Independent nodes (no deps) → batched together."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return [
                _make_task("T1"),
                _make_task("T2"),
                _make_task("T3"),
            ]

        results = run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=5,
        )

        assert len(results) == 1
        assert set(driver.calls[0]) == {"T1", "T2", "T3"}

    def test_oversized_batch_split(self):
        """Batch exceeding max_batch_size is split."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return [_make_task(f"T{i}") for i in range(1, 8)]

        results = run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=3,
        )

        # 7 tasks, max 3 per batch → 3 batches (3, 3, 1)
        assert len(results) == 3
        assert len(driver.calls[0]) == 3
        assert len(driver.calls[1]) == 3
        assert len(driver.calls[2]) == 1

    # -- reduce contract ----------------------------------------------------

    def test_reduce_receives_correct_batch(self):
        """Each reduce call receives the batch that was processed."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return [
                _make_task("T1"),
                _make_task("T2", depends_on=["T1"]),
            ]

        run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=5,
        )

        assert len(_fake_reduce_calls) == 2
        assert _fake_reduce_calls[0].batch_ids == ["T1"]
        assert _fake_reduce_calls[0].processed_count == 1
        assert _fake_reduce_calls[1].batch_ids == ["T2"]
        assert _fake_reduce_calls[1].processed_count == 1

    def test_reduce_result_preserved(self):
        """Scheduler returns Reduce items unchanged (typed pass-through)."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return [_make_task("T1")]

        results = run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=5,
        )

        assert len(results) == 1
        assert isinstance(results[0], Reduce)
        assert results[0].value == "ok"

    # -- no classification leakage ------------------------------------------

    def test_no_classification_in_scheduler(self):
        """Scheduler contains no classification vocabulary in its source."""
        import ast
        import inspect

        source = inspect.getsource(run_scheduler)
        tree = ast.parse(source)

        # Collect all string constants
        strings: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                strings.add(node.value)

        # Classification / planning vocabulary must not appear
        forbidden = {
            "complexity",
            "tier",
            "classification",
            "planning",
            "rubric",
            "success",
            "blocked",
            "phase_outcome",
        }
        found = forbidden & {s.lower() for s in strings}
        assert not found, f"Scheduler source contains forbidden tokens: {found}"

    def test_empty_work_list(self):
        """Empty work list → empty result."""
        driver = FakeProcessDriver()

        def produce() -> list[dict[str, Any]]:
            return []

        results = run_scheduler(
            produce=produce,
            process_driver=driver,
            reduce=fake_reduce,
            max_batch_size=5,
        )

        assert results == []
        assert driver.calls == []


# ---------------------------------------------------------------------------
# Protocol test
# ---------------------------------------------------------------------------


class TestProcessDriverProtocol:
    """The inline ProcessDriver Protocol is structural — any class with
    ``process(self, batch: list) -> Any`` satisfies it."""

    def test_fake_driver_satisfies_protocol(self):
        """FakeProcessDriver is structurally compatible with ProcessDriver."""
        driver: ProcessDriver = FakeProcessDriver()
        result = driver.process(["T1"])
        assert result == {"processed": ["T1"], "count": 1}
