"""Structural guardrails for the neutral completion shadow modules."""

from __future__ import annotations

import ast
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[3]
COMPLETION_ROOT = REPOSITORY_ROOT / "arnold" / "workflow" / "completion"
ADAPTER_ROOT = REPOSITORY_ROOT / "arnold_pipelines" / "megaplan" / "completion"
TEST_ROOTS = (
    REPOSITORY_ROOT / "tests" / "arnold" / "workflow",
    REPOSITORY_ROOT / "tests" / "arnold_pipelines" / "megaplan" / "completion",
)


def _function_nodes(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return concrete function definitions, including nested helpers."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _conditional_depth(node: ast.AST, depth: int = 0) -> int:
    """Return the maximum nested conditional depth beneath *node*."""
    children = ast.iter_child_nodes(node)
    maximum = depth
    for child in children:
        child_depth = depth + 1 if isinstance(child, (ast.If, ast.IfExp, ast.Try)) else depth
        maximum = max(maximum, _conditional_depth(child, child_depth))
    return maximum


def test_shadow_modules_obey_size_and_function_limits() -> None:
    """All C1 production and test modules remain easy to audit."""
    production_paths = sorted(COMPLETION_ROOT.glob("*.py")) + sorted(
        ADAPTER_ROOT.glob("*.py")
    )
    test_paths = [
        path
        for root in TEST_ROOTS
        for path in sorted(root.glob("test_completion_*.py"))
    ]
    test_paths.append(
        REPOSITORY_ROOT
        / "tests"
        / "arnold_pipelines"
        / "megaplan"
        / "completion"
        / "test_adapter.py"
    )
    for path in production_paths + test_paths:
        tree = ast.parse(path.read_text(), filename=str(path))
        assert len(path.read_text().splitlines()) < 500
        for function in _function_nodes(tree):
            assert function.end_lineno - function.lineno + 1 <= 80, function.name
        if path in production_paths:
            assert _conditional_depth(tree) <= 3
