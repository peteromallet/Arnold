"""Workflow manifest runtime conformance guardrails."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

NEUTRAL_PACKAGE_PREFIXES = (
    "arnold.workflow",
    "arnold.kernel",
    "arnold.execution",
    "arnold.agent",
    "arnold.control",
    "arnold.conformance",
)
FORBIDDEN_PRODUCT_PREFIXES = (
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan",
    "megaplan",
)


@dataclass(frozen=True)
class GoldenRegressionRule:
    """Rule deciding whether behavioral golden changes are explained."""

    fixture_path: Path
    explanation_path: Path

    def is_explained(self, *, old_text: str, new_text: str) -> bool:
        if old_text == new_text:
            return True
        if not self.explanation_path.exists():
            return False
        return bool(self.explanation_path.read_text(encoding="utf-8").strip())


def scan_neutral_product_imports(paths: Iterable[Path]) -> dict[str, tuple[str, ...]]:
    """Return forbidden product imports found in neutral package files."""

    violations: dict[str, tuple[str, ...]] = {}
    for path in sorted(paths):
        if path.suffix != ".py" or not path.exists():
            continue
        module = _module_name(path)
        if not module.startswith(NEUTRAL_PACKAGE_PREFIXES):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        hits: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _record_import(alias.name, hits)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                _record_import(node.module, hits)
        if hits:
            violations[str(path)] = tuple(sorted(hits))
    return violations


def _record_import(module: str, hits: set[str]) -> None:
    for forbidden in FORBIDDEN_PRODUCT_PREFIXES:
        if module == forbidden or module.startswith(forbidden + "."):
            hits.add(forbidden)


def _module_name(path: Path) -> str:
    parts = path.with_suffix("").parts
    if "arnold" not in parts:
        return path.stem
    start = parts.index("arnold")
    return ".".join(parts[start:])
