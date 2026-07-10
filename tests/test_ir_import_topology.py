"""Subprocess-based import-isolation tests for ``vibecomfy.ir``.

Verifies that ``vibecomfy/ir/types.py`` has zero module-level imports
from ``vibecomfy.contracts.*`` or ``vibecomfy.workflow`` (the source-level
constraint the plan mandates for the IR leaf module).

The subprocess checks keep the remaining known leak explicit:
``vibecomfy.ir.__init__`` imports ``vibecomfy.ir.workflow``, which imports
``vibecomfy.contracts.validation`` at module level.
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import subprocess
import sys

# ── repo root (one level above tests/) ──────────────────────────────────────
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_IR_TYPES = _REPO_ROOT / "vibecomfy" / "ir" / "types.py"

FORBIDDEN_NAMESPACES: list[str] = [
    "vibecomfy.contracts",
    "vibecomfy.workflow",
]
KNOWN_IR_WORKFLOW_CONTRACT_IMPORTS: list[str] = [
    "vibecomfy.contracts",
    "vibecomfy.contracts.intent_nodes",
    "vibecomfy.contracts.validation",
]


# ── source-level check: ir/types.py must have clean imports ─────────────────

def _module_level_imports(source: str, filename: str) -> list[str]:
    """Extract module-level import targets from Python source."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                imports.append(node.module)
    return imports


def test_ir_types_source_has_no_forbidden_imports() -> None:
    """``vibecomfy/ir/types.py`` must have zero module-level imports from
    ``vibecomfy.contracts.*`` or ``vibecomfy.workflow``."""
    source = _IR_TYPES.read_text()
    imports = _module_level_imports(source, str(_IR_TYPES))
    bad = [
        imp
        for imp in imports
        if any(
            imp == pfx or imp.startswith(pfx + ".")
            for pfx in FORBIDDEN_NAMESPACES
        )
    ]

    assert not bad, (
        f"vibecomfy/ir/types.py has forbidden module-level imports: {bad}\n"
        f"All imports: {imports}"
    )


def test_ir_all_source_files_except_workflow_have_no_forbidden_imports() -> None:
    """Every ``vibecomfy/ir/*.py`` file except ``workflow.py`` must have
    zero module-level imports from ``vibecomfy.contracts.*`` or
    ``vibecomfy.workflow``.

    ``workflow.py`` is excluded because it carries a known
    ``vibecomfy.contracts.validation`` import (inherited from the
    pre-decomposition monolithic ``workflow.py``).
    """
    ir_dir = _IR_TYPES.parent
    violations: dict[str, list[str]] = {}
    for path in sorted(ir_dir.glob("*.py")):
        if path.name == "workflow.py":
            continue  # known exception — see module docstring
        source = path.read_text()
        imports = _module_level_imports(source, str(path))
        bad = [
            imp
            for imp in imports
            if any(
                imp == pfx or imp.startswith(pfx + ".")
                for pfx in FORBIDDEN_NAMESPACES
            )
        ]
        if bad:
            violations[str(path.relative_to(_REPO_ROOT))] = bad

    assert not violations, (
        f"ir/ source files have forbidden module-level imports:\n"
        + "\n".join(f"  {k}: {v}" for k, v in violations.items())
    )


# ── subprocess-based import isolation ───────────────────────────────────────

def _build_forbidden_check_script(import_target: str) -> str:
    r"""Construct a Python script that imports *import_target*, then
    checks that none of ``FORBIDDEN_NAMESPACES`` appear as a key or
    prefix in ``sys.modules``."""

    forbidden_list_repr = repr(FORBIDDEN_NAMESPACES)
    return (
        "import json\n"
        "import sys\n"
        f"import {import_target}\n"
        f"forbidden_prefixes = {forbidden_list_repr}\n"
        "ir_workflow_loaded = 'vibecomfy.ir.workflow' in sys.modules\n"
        "found = sorted(\n"
        "    k for k in sys.modules\n"
        "    if any(k == pfx or k.startswith(pfx + '.') for pfx in forbidden_prefixes)\n"
        ")\n"
        "print(json.dumps({'found': found, 'ir_workflow_loaded': ir_workflow_loaded}))\n"
    )


def _run_isolation_check(import_target: str) -> dict[str, object]:
    """Run the isolation check in a fresh subprocess with the repo root
    on ``PYTHONPATH``."""
    check_script = _build_forbidden_check_script(import_target)
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(_REPO_ROOT) + (
        os.pathsep + existing if existing else ""
    )

    result = subprocess.run(
        [sys.executable, "-c", check_script],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode == 0, (
        f"{import_target} import subprocess failed (rc={result.returncode}).\n"
        f"stdout: {result.stdout.strip()}\n"
        f"stderr: {result.stderr.strip()}"
    )
    return json.loads(result.stdout)


def test_ir_types_import_isolation() -> None:
    """``import vibecomfy.ir.types`` still executes ``vibecomfy.ir.__init__``.

    The remaining subprocess violation is intentionally limited to
    ``vibecomfy.ir.workflow`` loading the contracts modules listed below.
    """
    payload = _run_isolation_check("vibecomfy.ir.types")

    assert payload["ir_workflow_loaded"] is True
    assert payload["found"] == KNOWN_IR_WORKFLOW_CONTRACT_IMPORTS


def test_ir_import_isolation() -> None:
    """``import vibecomfy.ir`` has the same explicit workflow-only leak."""
    payload = _run_isolation_check("vibecomfy.ir")

    assert payload["ir_workflow_loaded"] is True
    assert payload["found"] == KNOWN_IR_WORKFLOW_CONTRACT_IMPORTS
