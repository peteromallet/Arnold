"""Import-leak gate: ``arnold.pipelines.deliberation`` must not pull in Megaplan.

Design
------
Uses the same subprocess + ``sys.meta_path`` blocker pattern as
``tests/boundary/test_import_leak.py``.  A fresh Python interpreter
with a MetaPathFinder that raises ``ModuleNotFoundError`` for any
``arnold.pipelines.megaplan.*``, ``arnold_pipelines.megaplan.*``, or
``megaplan.*`` import attempts to import ``arnold.pipelines.deliberation`` and
``arnold.pipelines.deliberation.build_pipeline``.
If the import chain is clean the subprocess exits 0; otherwise it
exits non-zero with the blocking module name in stderr.

Additionally, a static git-grep check scoped to
``arnold/pipelines/deliberation/`` verifies that zero
``from arnold.pipelines.megaplan`` or
``import arnold.pipelines.megaplan`` statements exist in the
deliberation source tree.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest


# ---------------------------------------------------------------------------
# Static surface check: git grep for megaplan imports in deliberation/
# ---------------------------------------------------------------------------

_STATIC_CHECK_SCRIPT = textwrap.dedent("""\
import subprocess, sys

result = subprocess.run(
    ["git", "grep", "-nE",
     r"^(from arnold\\.pipelines\\.megaplan|import arnold\\.pipelines\\.megaplan)",
     "--", "arnold/pipelines/deliberation/"],
    capture_output=True, text=True, cwd=sys.argv[1],
)
if result.stdout.strip():
    print("FAIL: megaplan imports found in arnold/pipelines/deliberation/:", file=sys.stderr)
    print(result.stdout, file=sys.stderr)
    sys.exit(1)
sys.exit(0)
""")


# ---------------------------------------------------------------------------
# Dynamic coupling check: fresh-interpreter smoke with meta_path blocker
# ---------------------------------------------------------------------------

_DYNAMIC_CHECK_SCRIPT = textwrap.dedent("""\
import sys

class _BlockMegaplanFinder:
    def find_spec(self, fullname, path, target=None):
        # Block canonical/mirrored Megaplan packages and legacy bare imports.
        if (fullname == "arnold_pipelines.megaplan"
                or fullname.startswith("arnold_pipelines.megaplan.")
                or fullname == "arnold.pipelines.megaplan"
                or fullname.startswith("arnold.pipelines.megaplan.")
                or fullname == "megaplan"
                or fullname.startswith("megaplan.")):
            raise ModuleNotFoundError(
                f"megaplan import blocked by deliberation leak gate: {fullname}"
            )
        return None

sys.meta_path.insert(0, _BlockMegaplanFinder())

# These imports must succeed with zero megaplan transitive dependencies.
import arnold.pipelines.deliberation  # noqa: E402
from arnold.pipelines.deliberation import build_pipeline  # noqa: E402, F401

sys.exit(0)
""")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeliberationImportLeakage:
    """arnold.pipelines.deliberation must import without pulling in Megaplan."""

    def test_static_surface_clean(self) -> None:
        """git grep: zero megaplan imports in arnold/pipelines/deliberation/."""
        import pathlib
        repo_root = str(pathlib.Path(__file__).resolve().parents[3])
        result = subprocess.run(
            [sys.executable, "-c", _STATIC_CHECK_SCRIPT, repo_root],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Static surface check failed.\n--- stderr ---\n{result.stderr}"
        )

    def test_fresh_interpreter_import_loads_zero_megaplan_modules(self) -> None:
        """Subprocess: importing deliberation loads zero megaplan modules."""
        result = subprocess.run(
            [sys.executable, "-c", _DYNAMIC_CHECK_SCRIPT],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"Subprocess exited {result.returncode} — megaplan leaked into "
            f"deliberation import chain.\n--- stderr ---\n{result.stderr}"
        )
