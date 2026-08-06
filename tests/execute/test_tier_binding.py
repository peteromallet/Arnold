"""Tests for ``megaplan.execute._binding.tier`` — tier selection and validation."""

from __future__ import annotations

import ast
import textwrap

import pytest

from arnold_pipelines.megaplan.execute._binding.tier import (
    COMPLEXITY_SCALE,
    select_batch_tier,
    validate_task_complexity,
)


# ---------------------------------------------------------------------------
# validate_task_complexity — extracted from handlers/finalize.py:264–275
# ---------------------------------------------------------------------------


class TestValidateTaskComplexity:
    """Tests for ``validate_task_complexity`` — the hard-reject helper."""

    def test_valid_task(self):
        """A task with valid complexity and justification passes."""
        task = {
            "complexity": 3,
            "complexity_justification": "Multi-file change with contracts.",
        }
        assert validate_task_complexity(task, "T1") is None

    def test_missing_complexity(self):
        """Missing ``complexity`` key returns an error message."""
        task = {
            "complexity_justification": "Justification provided.",
        }
        error = validate_task_complexity(task, "T1")
        assert error is not None
        assert "complexity" in error.lower()
        assert "1..10" in error

    def test_non_integer_complexity(self):
        """A non-integer complexity value returns an error message."""
        task = {
            "complexity": "medium",
            "complexity_justification": "Justification provided.",
        }
        error = validate_task_complexity(task, "T2")
        assert error is not None
        assert "complexity" in error.lower()

    def test_boolean_complexity(self):
        """A boolean complexity (True) is rejected."""
        task = {
            "complexity": True,
            "complexity_justification": "Justification provided.",
        }
        error = validate_task_complexity(task, "T3")
        assert error is not None

    def test_complexity_out_of_range_low(self):
        """Complexity 0 (below range) returns an error message."""
        task = {
            "complexity": 0,
            "complexity_justification": "Justification provided.",
        }
        error = validate_task_complexity(task, "T4")
        assert error is not None

    def test_complexity_out_of_range_high(self):
        """Complexity 11 (above range) returns an error message."""
        task = {
            "complexity": 11,
            "complexity_justification": "Justification provided.",
        }
        error = validate_task_complexity(task, "T5")
        assert error is not None

    def test_missing_justification(self):
        """Missing ``complexity_justification`` returns an error message."""
        task = {"complexity": 3}
        error = validate_task_complexity(task, "T6")
        assert error is not None
        assert "complexity_justification" in error.lower()

    def test_empty_justification(self):
        """An empty-string justification returns an error message."""
        task = {"complexity": 3, "complexity_justification": "   "}
        error = validate_task_complexity(task, "T7")
        assert error is not None

    def test_none_justification(self):
        """A None justification returns an error message."""
        task = {"complexity": 3, "complexity_justification": None}
        error = validate_task_complexity(task, "T8")
        assert error is not None


# ---------------------------------------------------------------------------
# select_batch_tier — wraps compute_batch_complexity
# ---------------------------------------------------------------------------


class TestSelectBatchTier:
    """Tests for ``select_batch_tier``."""

    def test_select_batch_tier_returns_tier_ordinal(self):
        """``select_batch_tier`` returns an integer in 1..10."""
        finalize_data = {
            "tasks": [
                {
                    "id": "T1",
                    "complexity": 3,
                    "complexity_justification": "Multi-file change.",
                },
                {
                    "id": "T2",
                    "complexity": 1,
                    "complexity_justification": "Single-line change.",
                },
            ]
        }
        tier = select_batch_tier(finalize_data, ["T1", "T2"])
        assert isinstance(tier, int)
        assert tier == 3  # max of 3 and 1

    def test_select_batch_tier_fail_safe_empty_batch(self):
        """Empty batch falls through to 10 (fail-safe)."""
        tier = select_batch_tier({"tasks": []}, [])
        assert tier == 10

    def test_select_batch_tier_fail_safe_missing_complexity(self):
        """Missing complexity on a task → fail-safe 10."""
        finalize_data = {
            "tasks": [
                {
                    "id": "T1",
                    "complexity_justification": "Justification.",
                }
            ]
        }
        tier = select_batch_tier(finalize_data, ["T1"])
        assert tier == 10

    def test_select_batch_tier_fail_safe_missing_justification(self):
        """Missing justification on a task does NOT affect tier (only complexity matters)."""
        finalize_data = {
            "tasks": [
                {"id": "T1", "complexity": 2}
            ]
        }
        tier = select_batch_tier(finalize_data, ["T1"])
        assert tier == 2  # missing justification doesn't affect compute_batch_complexity

    def test_select_batch_tier_fail_safe_out_of_range(self):
        """Out-of-range complexity → fail-safe 10."""
        finalize_data = {
            "tasks": [
                {
                    "id": "T1",
                    "complexity": 99,
                    "complexity_justification": "Too high.",
                }
            ]
        }
        tier = select_batch_tier(finalize_data, ["T1"])
        assert tier == 10


# ---------------------------------------------------------------------------
# AST scan — select_batch_tier is the only call site referencing 1..10 scale
# ---------------------------------------------------------------------------


def test_tier_module_only_scale_reference_is_select_batch_tier():
    """``select_batch_tier`` is the only call site referencing the 1..10 scale.

    The ``COMPLEXITY_SCALE`` constant and the ``validate_task_complexity``
    helper may reference 1..10, but no other function/class in the module
    should embed the stale 1..5 scale as a literal.
    """
    import arnold_pipelines.megaplan.execute._binding.tier as mod

    source = textwrap.dedent(open(mod.__file__).read())
    tree = ast.parse(source)

    # Acceptable names that may reference 1..10
    _allowed_references = {"COMPLEXITY_SCALE", "validate_task_complexity"}

    # Walk all function/class definitions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in _allowed_references:
                continue
            # Search this node's body for stale 1..5 pattern
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    if "1..5" in sub.value or "1-5" in sub.value:
                        pytest.fail(
                            f"stale 1..5 scale referenced outside allowed call sites "
                            f"('COMPLEXITY_SCALE', 'validate_task_complexity'): "
                            f"found in {node.name!r} at line {sub.lineno}: {sub.value!r}"
                        )

    # Also verify select_batch_tier does not directly contain stale 1..5 literal
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "select_batch_tier":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    if "1..5" in sub.value or "1-5" in sub.value:
                        pytest.fail(
                            f"select_batch_tier should not embed stale 1..5 literal; "
                            f"found at line {sub.lineno}: {sub.value!r}"
                        )


def test_tier_module_exports_complexity_scale():
    """The 1..10 scale is accessible as ``COMPLEXITY_SCALE``."""
    assert COMPLEXITY_SCALE == frozenset(range(1, 11))
