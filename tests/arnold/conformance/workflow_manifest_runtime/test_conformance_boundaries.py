"""Additional conformance boundary gates for deleted Megaplan roots.

Extends the neutral-package import boundary coverage to ``arnold.conformance``
and ``arnold.agent``.  Imports of the deleted legacy product package
``arnold.pipelines.megaplan`` are forbidden outside explicit scanner targets.
"""

from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN = ("arnold.pipelines.megaplan",)
RUNTIME_RUNNER_MODULES = (
    "arnold.execution",
    "arnold.pipeline",
    "arnold.runner",
    "arnold.kernel",
    "arnold.agent",
)


def _scan_forbidden(package_root: Path) -> dict[str, tuple[str, ...]]:
    violations: dict[str, tuple[str, ...]] = {}
    for source in sorted(package_root.rglob("*.py")):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except SyntaxError:
            continue
        hits: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == FORBIDDEN[0] or alias.name.startswith(FORBIDDEN[0] + "."):
                        hits.add(FORBIDDEN[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module == FORBIDDEN[0] or node.module.startswith(FORBIDDEN[0] + "."):
                    hits.add(FORBIDDEN[0])
        if hits:
            violations[str(source)] = tuple(sorted(hits))
    return violations


def _scan_runtime_runner_imports(package_root: Path) -> dict[str, tuple[str, ...]]:
    """Return files that import real execution/runner modules in test/fixture code."""

    violations: dict[str, tuple[str, ...]] = {}
    for source in sorted(package_root.rglob("*.py")):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except SyntaxError:
            continue
        hits: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in RUNTIME_RUNNER_MODULES:
                        if alias.name == prefix or alias.name.startswith(prefix + "."):
                            hits.add(prefix)
            elif isinstance(node, ast.ImportFrom) and node.module:
                for prefix in RUNTIME_RUNNER_MODULES:
                    if node.module == prefix or node.module.startswith(prefix + "."):
                        hits.add(prefix)
        if hits:
            violations[str(source)] = tuple(sorted(hits))
    return violations


def test_conformance_package_does_not_import_deleted_product_package() -> None:
    root = Path(__file__).parents[4]
    violations = _scan_forbidden(root / "arnold" / "conformance")
    assert violations == {}, f"arnold.conformance imports deleted product package: {violations}"


def test_agent_package_does_not_import_deleted_product_package() -> None:
    root = Path(__file__).parents[4]
    violations = _scan_forbidden(root / "arnold" / "agent")
    assert violations == {}, f"arnold.agent imports deleted product package: {violations}"


def test_fixture_validation_tests_do_not_invoke_real_execution_runners() -> None:
    """Fixture validation must be compile-time only; no real runner imports."""

    root = Path(__file__).parents[4]
    violations = _scan_runtime_runner_imports(root / "tests" / "arnold" / "conformance" / "workflow_manifest_runtime")
    assert violations == {}, f"fixture validation tests import runtime runners: {violations}"
