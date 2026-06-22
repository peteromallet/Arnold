from __future__ import annotations

import ast
from pathlib import Path


# New-package modules that are explicitly allowed to import the legacy
# `arnold.pipelines.megaplan` surface during M4.  These are parity adapters
# around the vendored Hermes agent runtime, which is intentionally left in
# the legacy tree until M6.
M4_PARITY_ADAPTER_PATHS = {
    "arnold_pipelines/megaplan/workers/_impl.py",
    "arnold_pipelines/megaplan/workers/hermes.py",
}


def _collect_import_violations(package_root: Path) -> dict[str, list[str]]:
    violations: dict[str, list[str]] = {}

    for source in sorted(package_root.rglob("*.py")):
        rel = source.relative_to(package_root.parent.parent)
        if str(rel) in M4_PARITY_ADAPTER_PATHS:
            continue

        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except SyntaxError:
            # Skip files that fail to parse (e.g. vendored debris that may
            # contain syntax oddities).  The package boundary test is about
            # intentional imports, not vendored parseability.
            continue

        bad: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "arnold.pipelines.megaplan" or alias.name.startswith(
                        "arnold.pipelines.megaplan."
                    ):
                        bad.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "arnold.pipelines.megaplan"
                    or node.module.startswith("arnold.pipelines.megaplan.")
                ):
                    bad.append(node.module)

        if bad:
            violations[str(rel)] = bad

    return violations


def test_new_package_does_not_import_legacy_megaplan() -> None:
    root = Path(__file__).parents[3] / "arnold_pipelines" / "megaplan"
    violations = _collect_import_violations(root)
    assert violations == {}, f"new-package code imports legacy package: {violations}"


def test_parity_adapters_are_explicitly_listed() -> None:
    root = Path(__file__).parents[3] / "arnold_pipelines" / "megaplan"
    all_legacy_importers: set[str] = set()

    for source in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "arnold.pipelines.megaplan" or alias.name.startswith(
                        "arnold.pipelines.megaplan."
                    ):
                        all_legacy_importers.add(str(source.relative_to(root.parent.parent)))
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "arnold.pipelines.megaplan"
                    or node.module.startswith("arnold.pipelines.megaplan.")
                ):
                    all_legacy_importers.add(str(source.relative_to(root.parent.parent)))

    assert all_legacy_importers.issubset(M4_PARITY_ADAPTER_PATHS), (
        f"found unlisted legacy importers: {all_legacy_importers - M4_PARITY_ADAPTER_PATHS}"
    )
