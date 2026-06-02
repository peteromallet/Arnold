"""Boundary tests for the Arnold runtime package.

These tests live under ``tests/arnold/runtime/`` because they guard the
*Arnold runtime boundary* — verifying that the neutral carriers under
``arnold/runtime/`` remain opinion-free and do not import or reference
Megaplan policy, phase names, gate labels, or override vocabularies.

The ``tests/arnold/runtime/`` root parallels the ``arnold/runtime/``
package root one-to-one, so any developer looking for Arnold runtime tests
can follow the same mental directory tree.

Boundary invariants enforced here
---------------------------------

1. **No Megaplan imports** — No ``arnold/runtime/**.py`` file may contain
   ``import megaplan`` or ``from megaplan``.
2. **No Megaplan vocabulary literals** — Forbidden phase names, override
   actions, and gate labels must not appear as string literals.
3. **No transitive Megaplan in ``sys.modules``** — Importing
   ``arnold.runtime`` must not pull ``megaplan`` into ``sys.modules``
   (verified via subprocess to avoid test-process contamination).
"""

from __future__ import annotations

import ast
import itertools
import os
import subprocess
import sys
from pathlib import Path
from typing import FrozenSet

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RUNTIME_PKG = Path(__file__).resolve().parent.parent.parent.parent / "arnold" / "runtime"

FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = ("import megaplan", "from megaplan")

# Forbidden Megaplan-phase-names and override-action literals that must not
# appear as string constants in any ``arnold/runtime/**.py`` source file.
FORBIDDEN_STRING_LITERALS: FrozenSet[str] = frozenset(
    {
        # Megaplan phase names
        "planning",
        "critique",
        "finalize",
        "tiebreaker",
        "escalate",
        # Megaplan override actions
        "force_proceed",
        "abort",
        "replan",
        "add_note",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _python_source_files(root: Path) -> list[Path]:
    """Return every ``.py`` source file under *root*, excluding ``__pycache__``."""
    return sorted(
        p for p in root.rglob("*.py") if "__pycache__" not in p.parts
    )


def _ast_import_violations(file_path: Path) -> list[str]:
    """Return a list of human-readable violation strings for forbidden imports.

    Scans for ``import megaplan`` and ``from megaplan`` at the AST level
    so that even commented-out or conditional imports are flagged.
    """
    violations: list[str] = []
    try:
        tree = ast.parse(file_path.read_text(), filename=str(file_path))
    except SyntaxError as exc:
        violations.append(f"{file_path}: syntax error — {exc}")
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "megaplan":
                    violations.append(
                        f"{file_path}:{node.lineno}: forbidden import — "
                        f"`import {alias.name}`"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and node.module.split(".")[0] == "megaplan":
                names = ", ".join(a.name for a in node.names)
                violations.append(
                    f"{file_path}:{node.lineno}: forbidden import — "
                    f"`from {node.module} import {names}`"
                )
    return violations


def _ast_string_literal_violations(file_path: Path) -> list[str]:
    """Return violations for forbidden string literals found in AST constants."""
    violations: list[str] = []
    try:
        tree = ast.parse(file_path.read_text(), filename=str(file_path))
    except SyntaxError:
        return violations  # already reported by _ast_import_violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in FORBIDDEN_STRING_LITERALS:
                violations.append(
                    f"{file_path}:{node.lineno}: forbidden string literal — "
                    f"'{node.value}'"
                )
    return violations


# ---------------------------------------------------------------------------
# Static gate: no Megaplan imports
# ---------------------------------------------------------------------------


class TestStaticGateNoMegaplanImports:
    """No source file under ``arnold/runtime/`` may import from megaplan."""

    def test_no_megaplan_imports_in_runtime_sources(self) -> None:
        violations: list[str] = []
        for source_file in _python_source_files(_RUNTIME_PKG):
            violations.extend(_ast_import_violations(source_file))
        if violations:
            pytest.fail(
                f"{len(violations)} forbidden import(s) found in arnold/runtime/:\n"
                + "\n".join(f"  • {v}" for v in violations)
            )


# ---------------------------------------------------------------------------
# Static gate: no Megaplan vocabulary string literals
# ---------------------------------------------------------------------------


class TestStaticGateNoMegaplanLiterals:
    """No source file under ``arnold/runtime/`` may contain forbidden literals."""

    def test_no_megaplan_phase_name_literals(self) -> None:
        """Megaplan phase names must not appear as string literals."""
        phase_names = {"planning", "critique", "finalize", "tiebreaker", "escalate"}
        violations: list[str] = []
        for source_file in _python_source_files(_RUNTIME_PKG):
            for v in _ast_string_literal_violations(source_file):
                for literal in phase_names:
                    if f"'{literal}'" in v:
                        violations.append(v)
                        break
        if violations:
            pytest.fail(
                f"Megaplan phase name literal(s) found in arnold/runtime/:\n"
                + "\n".join(f"  • {v}" for v in violations)
            )

    def test_no_megaplan_override_action_literals(self) -> None:
        """Megaplan override actions must not appear as string literals."""
        override_actions = {"force_proceed", "abort", "replan", "add_note"}
        violations: list[str] = []
        for source_file in _python_source_files(_RUNTIME_PKG):
            for v in _ast_string_literal_violations(source_file):
                for literal in override_actions:
                    if f"'{literal}'" in v:
                        violations.append(v)
                        break
        if violations:
            pytest.fail(
                f"Megaplan override action literal(s) found in arnold/runtime/:\n"
                + "\n".join(f"  • {v}" for v in violations)
            )


# ---------------------------------------------------------------------------
# No transitive Megaplan in sys.modules (hermetic subprocess check)
# ---------------------------------------------------------------------------


class TestNoTransitiveMegaplanImport:
    """Importing ``arnold.runtime`` must not pull ``megaplan`` into sys.modules."""

    def test_arnold_runtime_does_not_pull_megaplan_into_sys_modules(self) -> None:
        """Hermetic subprocess check: import arnold first, then arnold.runtime.

        Per FG-005 / the gate warning: we must ``import arnold`` BEFORE the
        ``before`` snapshot so that the pre-existing
        ``arnold/__init__.py::from megaplan import __version__`` lands in the
        baseline rather than the delta.  The boundary invariant is that
        ``arnold.runtime`` itself adds zero megaplan modules.
        """
        check_script = (
            "import sys; "
            "import arnold; "
            "before = {k for k in sys.modules if k.startswith('megaplan')}; "
            "import arnold.runtime; "
            "after = {k for k in sys.modules if k.startswith('megaplan')}; "
            "delta = after - before; "
            "print('DELTA:' + ','.join(sorted(delta)) if delta else 'DELTA:none')"
        )
        result = subprocess.run(
            [sys.executable, "-c", check_script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.dirname(str(_RUNTIME_PKG.parent.parent)),
        )
        if result.returncode != 0:
            pytest.fail(
                f"Subprocess failed (exit {result.returncode}):\n"
                f"stderr: {result.stderr}"
            )
        for line in result.stdout.splitlines():
            if line.startswith("DELTA:"):
                delta_str = line[len("DELTA:"):]
                if delta_str != "none":
                    modules = delta_str.split(",") if delta_str else []
                    pytest.fail(
                        f"Importing arnold.runtime pulled megaplan modules "
                        f"into sys.modules: {modules}"
                    )
                return
        pytest.fail("Subprocess output did not contain DELTA: marker")
