"""AST gate: no planning vocabulary in the four _core/ scheduler modules (T10).

This is the merge gate for any partial conversion of the unified execute
path.  It runs in the default CI suite.

Rejects any ast.Constant node of type str whose value is exactly one of
the four planning-vocabulary targets, regardless of whether it appears
bare, inside a set/frozenset/tuple/list/dict literal, or as a dict
key/value.  Also rejects any ast.Name whose .id == 'STATE_BLOCKED'.

English-prose occurrences inside docstrings are tolerated by virtue of
the exact-equality check (docstrings contain surrounding words, so their
string values will not equal a bare target).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# The four targeted modules
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TARGET_MODULES = [
    _REPO_ROOT / "megaplan" / "_core" / "dispatch.py",
    _REPO_ROOT / "megaplan" / "_core" / "scheduler" / "types.py",
    _REPO_ROOT / "megaplan" / "_core" / "scheduler" / "topo.py",
    _REPO_ROOT / "megaplan" / "_core" / "scheduler" / "run.py",
]

_BANNED_CONSTANTS: frozenset[str] = frozenset(
    {
        "success",
        "blocked_by_quality",
        "blocked_by_prereq",
        "timeout",
    }
)

_BANNED_NAME_ID = "STATE_BLOCKED"


def _collect_violations(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in _BANNED_CONSTANTS
        ):
            violations.append(
                f"{path.name}:{node.lineno}: banned constant {node.value!r}"
            )
        elif isinstance(node, ast.Name) and node.id == _BANNED_NAME_ID:
            violations.append(
                f"{path.name}:{node.lineno}: banned name {node.id!r}"
            )
    return violations


@pytest.mark.parametrize("module_path", _TARGET_MODULES, ids=[p.name for p in _TARGET_MODULES])
def test_no_planning_vocab_in_core_module(module_path: Path) -> None:
    """No planning vocabulary in the targeted _core/ module."""
    assert module_path.exists(), f"Module not found: {module_path}"
    violations = _collect_violations(module_path)
    assert not violations, (
        f"Planning vocabulary found in {module_path.name}:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_all_target_modules_exist() -> None:
    """All four target modules must be present on disk."""
    missing = [p for p in _TARGET_MODULES if not p.exists()]
    assert not missing, f"Missing modules: {missing}"
