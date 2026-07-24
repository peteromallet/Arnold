"""Boundary tests for the neutral Arnold control package."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest


_CONTROL_PKG = Path(__file__).resolve().parents[3] / "arnold" / "control"
_RUNTIME_PKG = Path(__file__).resolve().parents[3] / "arnold" / "runtime"
_INTERFACE_FILE = _CONTROL_PKG / "interface.py"

FORBIDDEN_IMPORT_ROOTS: tuple[str, ...] = (
    "megaplan",
    "arnold_pipelines.megaplan",
)

FORBIDDEN_IMPORT_MODULES: tuple[str, ...] = (
    "arnold_pipelines.megaplan.planning",
    "arnold_pipelines.megaplan.planning.state",
    "arnold_pipelines.megaplan.run_outcome",
    "arnold_pipelines.megaplan._pipeline",
    "arnold.pipeline.state",
)

FORBIDDEN_RAW_SOURCE_TOKENS: tuple[str, ...] = (
    ".megaplan",
    "MEGAPLAN_",
    "STATE_",
    "arnold_pipelines.megaplan.run_outcome",
    "arnold_pipelines.megaplan.planning.state",
    "arnold.pipeline.state",
)


def _python_source_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _ast_import_violations(file_path: Path) -> list[str]:
    violations: list[str] = []
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if any(name == root or name.startswith(f"{root}.") for root in FORBIDDEN_IMPORT_ROOTS):
                    violations.append(
                        f"{file_path}:{node.lineno}: forbidden import `import {name}`"
                    )
                if any(name == module or name.startswith(f"{module}.") for module in FORBIDDEN_IMPORT_MODULES):
                    violations.append(
                        f"{file_path}:{node.lineno}: forbidden import `import {name}`"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            module = node.module
            if any(module == root or module.startswith(f"{root}.") for root in FORBIDDEN_IMPORT_ROOTS):
                violations.append(
                    f"{file_path}:{node.lineno}: forbidden import `from {module} import ...`"
                )
            if any(module == blocked or module.startswith(f"{blocked}.") for blocked in FORBIDDEN_IMPORT_MODULES):
                violations.append(
                    f"{file_path}:{node.lineno}: forbidden import `from {module} import ...`"
                )
    return violations


def _raw_source_token_violations(file_path: Path) -> list[str]:
    violations: list[str] = []
    source = file_path.read_text(encoding="utf-8")
    for lineno, line in enumerate(source.splitlines(), start=1):
        for token in FORBIDDEN_RAW_SOURCE_TOKENS:
            if token in line:
                violations.append(
                    f"{file_path}:{lineno}: forbidden raw-source token {token!r}"
                )
    return violations


def _megaplan_modules_loaded_by(import_target: str) -> set[str]:
    script = (
        "import json, sys; "
        "import arnold; "
        "before = {k for k in sys.modules if k.startswith('arnold_pipelines.megaplan')}; "
        f"import {import_target}; "
        "after = {k for k in sys.modules if k.startswith('arnold_pipelines.megaplan')}; "
        "print(json.dumps(sorted(after - before)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    stdout = result.stdout.strip()
    return set(__import__("json").loads(stdout or "[]"))


def test_control_sources_do_not_import_megaplan_or_state_primitives() -> None:
    violations: list[str] = []
    for source_file in _python_source_files(_CONTROL_PKG):
        violations.extend(_ast_import_violations(source_file))
    if violations:
        pytest.fail("\n".join(violations))


def test_control_sources_do_not_reference_megaplan_raw_tokens() -> None:
    violations: list[str] = []
    for source_file in _python_source_files(_CONTROL_PKG):
        violations.extend(_raw_source_token_violations(source_file))
    if violations:
        pytest.fail("\n".join(violations))


@pytest.mark.parametrize("import_target", ["arnold.control", "arnold.control.interface"])
def test_importing_control_surfaces_does_not_load_megaplan_modules(import_target: str) -> None:
    assert _megaplan_modules_loaded_by(import_target) == set()


def test_control_abort_literal_is_owned_by_control_boundary_not_runtime() -> None:
    interface_source = _INTERFACE_FILE.read_text(encoding="utf-8")
    runtime_sources = [
        path.read_text(encoding="utf-8")
        for path in _python_source_files(_RUNTIME_PKG)
    ]

    assert 'CONTROL_TARGET_ABORT = "abort"' in interface_source
    assert all('"abort"' not in source and "'abort'" not in source for source in runtime_sources)
