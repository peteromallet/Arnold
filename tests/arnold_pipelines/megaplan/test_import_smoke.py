"""Dynamic import smoke coverage for ``arnold_pipelines.megaplan`` surfaces.

Verifies that importing public/runtime surfaces (megaplan, CLI, pipeline,
runtime, and shipped pipeline packages) does **not** pull the legacy
``_pipeline`` or ``stages`` modules into ``sys.modules``.

Each import is exercised in a subprocess to avoid cross-contamination.
Real execution is out of scope — only import-time side effects are
measured.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


# ── helpers ────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[3]

# Surfaces that the upstream M3 migration aims to keep clean.
PUBLIC_SURFACES: tuple[tuple[str, str], ...] = (
    # (label, import statement)
    ("megaplan", "import arnold_pipelines.megaplan"),
    ("pipeline", "import arnold_pipelines.megaplan.pipeline"),
    ("cli", "import arnold_pipelines.megaplan.cli"),
    ("runtime", "import arnold_pipelines.megaplan.runtime"),
)

# Shipped pipeline packages discovered via the canonical registry.  Each
# entry is a (label, import_module) pair that resolves to a package with
# a public ``build_pipeline`` callable.
SHIPPED_PIPELINE_SURFACES: tuple[tuple[str, str], ...] = (
    ("jokes", "arnold_pipelines.megaplan.pipelines.jokes"),
    ("creative", "arnold_pipelines.megaplan.pipelines.creative"),
    ("doc", "arnold_pipelines.megaplan.pipelines.doc"),
    ("planning", "arnold_pipelines.megaplan.pipelines.planning"),
    ("live_supervisor", "arnold_pipelines.megaplan.pipelines.live_supervisor"),
    ("evidence_pack", "arnold_pipelines.evidence_pack"),
    ("_template", "arnold_pipelines._template"),
)


def _import_check_code(import_stmt: str, repo_root: str) -> str:
    """Return a self-contained Python snippet that imports *import_stmt*
    and reports whether ``_pipeline`` or ``stages`` modules were loaded.

    The snippet exits with code 0 when **no** legacy modules are loaded and
    code 1 otherwise.  Stdout carries a human-readable summary.
    """
    return f'''
import sys
sys.path.insert(0, {repo_root!r})

before = set(sys.modules.keys())
{import_stmt}
after = set(sys.modules.keys())

new = sorted(after - before)
legacy = [m for m in new if "_pipeline" in m.split(".") or "stages" in m.split(".")]

if legacy:
    print("LEGACY_LOADED:" + ",".join(legacy))
    sys.exit(1)
else:
    print("CLEAN: " + str(len(new)) + " new modules, no legacy")
    sys.exit(0)
'''


def _run_import_check(import_stmt: str) -> tuple[bool, str]:
    """Run *import_stmt* in a subprocess.  Returns (clean, output)."""
    code = _import_check_code(import_stmt, str(REPO_ROOT))
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=45,
    )
    output = result.stdout.strip()
    if result.stderr:
        output += "\n[stderr]\n" + result.stderr.strip()
    return result.returncode == 0, output


# ── tests ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("label,import_stmt", PUBLIC_SURFACES)
def test_public_surface_does_not_load_pipeline_or_stages(
    label: str, import_stmt: str
) -> None:
    """Importing *label* must not pull ``_pipeline`` or ``stages`` into
    ``sys.modules``."""
    clean, output = _run_import_check(import_stmt)
    assert clean, (
        f"Import of {label!r} ({import_stmt!r}) loaded legacy modules.\n\n"
        f"{output}"
    )


@pytest.mark.parametrize("label,module_name", SHIPPED_PIPELINE_SURFACES)
def test_shipped_pipeline_does_not_load_pipeline_or_stages(
    label: str, module_name: str
) -> None:
    """Importing shipped pipeline *label* must not pull ``_pipeline`` or
    ``stages`` into ``sys.modules``."""
    import_stmt = f"import {module_name}"
    clean, output = _run_import_check(import_stmt)
    assert clean, (
        f"Import of {label!r} ({import_stmt!r}) loaded legacy modules.\n\n"
        f"{output}"
    )
