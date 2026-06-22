"""Additional conformance boundary gates for M4.

Extends the neutral-package import boundary coverage to ``arnold.conformance``
and ``arnold.agent``.  Only imports of the new product package
``arnold_pipelines.megaplan`` are forbidden; legacy forwards to
``arnold.pipelines.megaplan`` are M4 parity shims outside this gate.
"""

from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN = ("arnold_pipelines.megaplan",)


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


def test_conformance_package_does_not_import_new_product_package() -> None:
    root = Path(__file__).parents[4]
    violations = _scan_forbidden(root / "arnold" / "conformance")
    assert violations == {}, f"arnold.conformance imports new product package: {violations}"


def test_agent_package_does_not_import_new_product_package() -> None:
    root = Path(__file__).parents[4]
    violations = _scan_forbidden(root / "arnold" / "agent")
    assert violations == {}, f"arnold.agent imports new product package: {violations}"
