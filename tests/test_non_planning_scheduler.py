"""Non-planning scheduler integration + static import scan (T12).

Drives megaplan._core.run_scheduler from OUTSIDE megaplan/execute/ with:
  - produce() yielding toy {'id', 'depends_on', 'payload'} items
  - process_driver: inline fake that uppercases payloads
  - reduce: returns Reduce[Literal['accepted','rejected']]

Asserts:
  - Scheduler returns the binding's non-planning outcome vocabulary unchanged.
  - No module under megaplan/_core/ imports anything from megaplan/execute/
    or megaplan/handlers/.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Literal

import pytest

from megaplan._core import run_scheduler
from megaplan._core.scheduler.types import Reduce


# ---------------------------------------------------------------------------
# Toy fixtures
# ---------------------------------------------------------------------------


def _make_work_item(id_: str, depends_on: list[str], payload: str) -> dict[str, Any]:
    return {"id": id_, "depends_on": depends_on, "payload": payload}


class _FakeProcessDriver:
    """Fake driver: records batches received, uppercases payloads."""

    def __init__(self, work_items: list[dict[str, Any]]) -> None:
        self._items_by_id = {item["id"]: item for item in work_items}
        self.batches_received: list[list[str]] = []

    def process(self, batch: list[str]) -> dict[str, list[str]]:
        self.batches_received.append(list(batch))
        return {
            task_id: self._items_by_id[task_id]["payload"].upper()
            for task_id in batch
            if task_id in self._items_by_id
        }


def _make_reduce(
    expected_outcome: Literal["accepted", "rejected"],
) -> Any:
    def _reduce(
        batch_result: Any,
        *,
        batch: list[str],
        batch_index: int,
    ) -> Reduce[Literal["accepted", "rejected"]]:
        return Reduce(value=expected_outcome)

    return _reduce


# ---------------------------------------------------------------------------
# Scheduler functional tests
# ---------------------------------------------------------------------------


def test_run_scheduler_single_node_returns_binding_outcome() -> None:
    """Single-node graph returns the binding's outcome vocabulary unchanged."""
    items = [_make_work_item("A", [], "hello")]
    driver = _FakeProcessDriver(items)
    results = run_scheduler(
        produce=lambda: items,
        process_driver=driver,
        reduce=_make_reduce("accepted"),
        max_batch_size=5,
    )
    assert len(results) == 1
    assert results[0].value == "accepted"


def test_run_scheduler_returns_reduce_instances() -> None:
    """Each result is a Reduce instance, not a plain value."""
    items = [_make_work_item("A", [], "x")]
    driver = _FakeProcessDriver(items)
    results = run_scheduler(
        produce=lambda: items,
        process_driver=driver,
        reduce=_make_reduce("accepted"),
        max_batch_size=5,
    )
    assert all(isinstance(r, Reduce) for r in results)


def test_run_scheduler_linear_chain_correct_batch_ordering() -> None:
    """A → B → C produces three batches in topological order."""
    items = [
        _make_work_item("A", [], "a"),
        _make_work_item("B", ["A"], "b"),
        _make_work_item("C", ["B"], "c"),
    ]
    driver = _FakeProcessDriver(items)
    results = run_scheduler(
        produce=lambda: items,
        process_driver=driver,
        reduce=_make_reduce("accepted"),
        max_batch_size=5,
    )
    assert len(results) == 3
    assert driver.batches_received == [["A"], ["B"], ["C"]]


def test_run_scheduler_reduce_called_once_per_batch() -> None:
    """reduce is invoked exactly once per batch."""
    items = [
        _make_work_item("A", [], "a"),
        _make_work_item("B", [], "b"),
    ]
    call_count = 0

    def _counting_reduce(
        batch_result: Any, *, batch: list[str], batch_index: int
    ) -> Reduce[str]:
        nonlocal call_count
        call_count += 1
        return Reduce(value="accepted")

    driver = _FakeProcessDriver(items)
    run_scheduler(
        produce=lambda: items,
        process_driver=driver,
        reduce=_counting_reduce,
        max_batch_size=5,
    )
    # A and B have no dependencies → one batch → one reduce call
    assert call_count == 1


def test_run_scheduler_reduce_receives_batch_result() -> None:
    """reduce receives the process_driver's return value as batch_result."""
    items = [_make_work_item("A", [], "hello")]
    received: list[Any] = []

    def _capturing_reduce(
        batch_result: Any, *, batch: list[str], batch_index: int
    ) -> Reduce[str]:
        received.append(batch_result)
        return Reduce(value="accepted")

    driver = _FakeProcessDriver(items)
    run_scheduler(
        produce=lambda: items,
        process_driver=driver,
        reduce=_capturing_reduce,
        max_batch_size=5,
    )
    assert len(received) == 1
    assert received[0] == {"A": "HELLO"}


def test_run_scheduler_outcome_vocabulary_unchanged() -> None:
    """Scheduler returns the binding's outcome vocab unchanged — 'rejected' survives."""
    items = [_make_work_item("X", [], "x")]
    driver = _FakeProcessDriver(items)
    results = run_scheduler(
        produce=lambda: items,
        process_driver=driver,
        reduce=_make_reduce("rejected"),
        max_batch_size=5,
    )
    assert results[0].value == "rejected"


def test_run_scheduler_completed_ids_excludes_nodes() -> None:
    """completed_ids correctly excludes already-done tasks from scheduling."""
    items = [
        _make_work_item("A", [], "a"),
        _make_work_item("B", ["A"], "b"),
    ]
    driver = _FakeProcessDriver(items)
    results = run_scheduler(
        produce=lambda: items,
        process_driver=driver,
        reduce=_make_reduce("accepted"),
        max_batch_size=5,
        completed_ids={"A"},
    )
    # Only B should be scheduled
    assert len(results) == 1
    assert driver.batches_received == [["B"]]


def test_run_scheduler_diamond_correct_order() -> None:
    """Diamond graph: A → B,C → D produces correct batches."""
    items = [
        _make_work_item("A", [], "a"),
        _make_work_item("B", ["A"], "b"),
        _make_work_item("C", ["A"], "c"),
        _make_work_item("D", ["B", "C"], "d"),
    ]
    driver = _FakeProcessDriver(items)
    run_scheduler(
        produce=lambda: items,
        process_driver=driver,
        reduce=_make_reduce("accepted"),
        max_batch_size=5,
    )
    batches = driver.batches_received
    # A must be first, D must be last, B and C can be in any order in one batch
    assert batches[0] == ["A"]
    assert set(batches[1]) == {"B", "C"}
    assert batches[2] == ["D"]


# ---------------------------------------------------------------------------
# Static import scan: no _core/ module imports from execute/ or handlers/
# ---------------------------------------------------------------------------


def _core_root() -> Path:
    # Scan only the scheduler subpackage — the new clean infrastructure.
    # megaplan/_core/io.py has a pre-existing conditional import from
    # megaplan.handlers.shared (io.py:255, inside an except handler) that
    # predates F5 and is out of scope for this test.
    return Path(__file__).resolve().parent.parent / "megaplan" / "_core" / "scheduler"


def _collect_banned_imports(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "megaplan.execute" in alias.name or "megaplan.handlers" in alias.name:
                        violations.append(
                            f"{path.name}:{node.lineno}: imports {alias.name!r}"
                        )
                continue
            if "megaplan.execute" in module or "megaplan.handlers" in module:
                violations.append(
                    f"{path.name}:{node.lineno}: imports from {module!r}"
                )
    return violations


def test_no_core_module_imports_execute_or_handlers() -> None:
    """No module under megaplan/_core/scheduler/ imports from megaplan/execute/ or megaplan/handlers/."""
    core_root = _core_root()
    assert core_root.exists(), f"_core/scheduler root not found: {core_root}"

    all_violations: list[str] = []
    for py_file in sorted(core_root.rglob("*.py")):
        violations = _collect_banned_imports(py_file)
        all_violations.extend(violations)

    assert not all_violations, (
        "Found banned imports from megaplan/execute/ or megaplan/handlers/ in _core/scheduler/:\n"
        + "\n".join(f"  {v}" for v in all_violations)
    )
