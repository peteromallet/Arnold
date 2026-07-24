"""Import-boundary tests for the neutral ``arnold.agent`` package.

``arnold.agent`` must remain product-neutral: it must not statically import
``arnold_pipelines.megaplan`` or ``arnold_pipelines.megaplan``.  Dynamic
runtime forwards to vendored legacy agent tools are allowed only when they go
through ``arnold_pipelines.megaplan.agent`` (the M4 parity shim), not the new
product package.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


FORBIDDEN = ("arnold_pipelines.megaplan",)


def _is_forbidden(name: str) -> bool:
    return name == FORBIDDEN[0] or name.startswith(FORBIDDEN[0] + ".")


def test_agent_import_does_not_load_new_product_package() -> None:
    before = set(sys.modules)
    import arnold.agent  # noqa: F401

    imported = set(sys.modules) - before
    forbidden = {name for name in imported if _is_forbidden(name)}

    assert not forbidden, f"arnold.agent imported forbidden new product package: {forbidden}"


def test_agent_source_has_no_new_product_imports() -> None:
    package_root = Path(__file__).parents[3] / "arnold" / "agent"
    violations: dict[str, list[str]] = {}

    for source in sorted(package_root.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names if _is_forbidden(alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module and _is_forbidden(node.module):
                imports.append(node.module)
        if imports:
            violations[str(source.relative_to(package_root.parent.parent))] = imports

    assert violations == {}, f"forbidden new product imports in arnold.agent: {violations}"
