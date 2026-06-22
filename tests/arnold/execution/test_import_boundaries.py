from __future__ import annotations

import ast
import sys
from pathlib import Path


FORBIDDEN_PREFIXES = (
    "arnold.workflow",
    "arnold.patterns",
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan",
    "megaplan",
)


def _is_forbidden(name: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in FORBIDDEN_PREFIXES)


def test_execution_imports_do_not_load_workflow_or_product_modules() -> None:
    before = set(sys.modules)
    import arnold.execution  # noqa: F401

    imported = set(sys.modules) - before
    forbidden = {name for name in imported if _is_forbidden(name)}

    assert forbidden == set()


def test_execution_source_has_no_forbidden_imports() -> None:
    package_root = Path(__file__).parents[3] / "arnold" / "execution"
    violations: dict[str, list[str]] = {}

    for source in sorted(package_root.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names if _is_forbidden(alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module and _is_forbidden(node.module):
                imports.append(node.module)
        if imports:
            violations[str(source.relative_to(package_root.parent.parent))] = imports

    assert violations == {}


def test_execution_public_namespace_is_narrow() -> None:
    import arnold.execution as execution

    assert set(execution.__all__) == {
        "ExecutionBackend",
        "ExecutionDiagnostic",
        "ExecutionLogger",
        "ExecutionRegistries",
        "ExecutionResult",
        "ExecutionState",
        "FileStateStore",
        "RunCheckpoint",
        "SkeletalBackend",
        "StateStore",
        "run",
    }
