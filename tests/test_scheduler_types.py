"""Tests for ``megaplan._core.scheduler.types`` — generic Reduce[T] frozen dataclass."""

from __future__ import annotations

import ast
import textwrap

import pytest

from megaplan._core.scheduler.types import Reduce


class TestReduce:
    """Tests for the generic ``Reduce[T]`` frozen dataclass."""

    def test_reduce_generic_parameterizes_cleanly(self):
        """Reduce[int] instantiates with a value and is frozen."""
        r = Reduce[int](42)
        assert r.value == 42

    def test_reduce_with_string_type(self):
        """Reduce[str] works with string values."""
        r = Reduce[str]("hello")
        assert r.value == "hello"

    def test_reduce_with_list_type(self):
        """Reduce[list[int]] works with list values."""
        r = Reduce[list[int]]([1, 2, 3])
        assert r.value == [1, 2, 3]

    def test_reduce_is_frozen(self):
        """Reduce instances are immutable (frozen=True)."""
        r = Reduce[int](42)
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            r.value = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AST scans — no planning vocabulary
# ---------------------------------------------------------------------------


def test_scheduler_types_no_planning_vocabulary():
    """The scheduler types module must contain zero planning vocabulary:
    no ``_PHASE_OUTCOMES`` literal, no ``STATE_BLOCKED`` name, no ``BatchOutcome``,
    no ``BatchReduceResult``."""
    import megaplan._core.scheduler.types as mod

    source = textwrap.dedent(open(mod.__file__).read())
    tree = ast.parse(source)

    forbidden_constants = {"_PHASE_OUTCOMES"}
    forbidden_names = {"STATE_BLOCKED", "BatchOutcome", "BatchReduceResult"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in forbidden_constants:
                pytest.fail(
                    f"Forbidden constant '{node.value}' found in "
                    f"scheduler/types.py at line {node.lineno}"
                )
        if isinstance(node, ast.Name):
            if node.id in forbidden_names:
                pytest.fail(
                    f"Forbidden name '{node.id}' found in "
                    f"scheduler/types.py at line {node.lineno}"
                )
