"""Import-leak gate: ``arnold.agent`` must not pull in Megaplan policy at import time.

Design
------
Uses the same subprocess + ``sys.meta_path`` blocker pattern as
``tests/arnold/runtime/test_runtime_import_leakage.py``.  A fresh Python
interpreter with a MetaPathFinder that raises ``ModuleNotFoundError`` for
any ``arnold_pipelines.megaplan.*`` import attempts to import
``arnold.agent.run_agent``.  If the import chain is clean the subprocess
exits 0; otherwise it exits non-zero with the blocking module name in stderr.

Shared process lifecycle and mini-swe-agent discovery live on Arnold-neutral
surfaces.  Product adapters may import Megaplan lazily when invoked, but merely
importing the generic agent must load no Megaplan modules.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

# ---------------------------------------------------------------------------
# Static surface check: git grep for actual megaplan imports in arnold/agent/
# ---------------------------------------------------------------------------

_STATIC_CHECK_SCRIPT = textwrap.dedent("""\
import subprocess, sys

result = subprocess.run(
    ["git", "grep", "-nE", r"from arnold\\.pipelines\\.megaplan", "--", "arnold/agent/"],
    capture_output=True, text=True, cwd=sys.argv[1],
)
# Filter out comment/docstring false positives (lines containing "No imports from")
hits = [ln for ln in result.stdout.splitlines() if "No imports from" not in ln]
if hits:
    print("FAIL: real megaplan imports found in arnold/agent/:", file=sys.stderr)
    for h in hits:
        print(h, file=sys.stderr)
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
        if fullname == "arnold_pipelines.megaplan" or fullname.startswith(
            "arnold_pipelines.megaplan."
        ):
            raise ModuleNotFoundError(
                f"arnold_pipelines.megaplan import blocked by agent leak gate: {fullname}"
            )
        return None

sys.meta_path.insert(0, _BlockMegaplanFinder())

# This import must succeed with zero megaplan transitive dependencies.
import arnold.agent.run_agent  # noqa: E402
""")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgentImportLeakage:
    """arnold.agent must import without pulling in Megaplan policy."""

    def test_static_surface_clean(self) -> None:
        """git grep: zero real 'from arnold_pipelines.megaplan' in arnold/agent/."""
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
        """Subprocess: importing arnold.agent.run_agent loads zero megaplan modules."""
        result = subprocess.run(
            [sys.executable, "-c", _DYNAMIC_CHECK_SCRIPT],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"Subprocess exited {result.returncode} — megaplan leaked into "
            f"arnold.agent import chain.\n--- stderr ---\n{result.stderr}"
        )

    def test_megaplan_minisweagent_adapter_reexports_neutral_owner(self) -> None:
        """The compatibility path must not fork helper behavior."""
        import arnold.agent.minisweagent_path as neutral
        import arnold_pipelines.megaplan.agent.minisweagent_path as adapter

        assert adapter.discover_minisweagent_src is neutral.discover_minisweagent_src
        assert adapter.ensure_minisweagent_on_path is neutral.ensure_minisweagent_on_path
