from __future__ import annotations

import ast
from pathlib import Path

from arnold.conformance.deleted_surfaces import (
    DELETED_IMPORT_MODULES,
    DELETED_SOURCE_PATHS,
    DELETED_SURFACES,
    DeletedSurface,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def _module_to_source_path(module_name: str) -> Path:
    return REPO_ROOT / Path(*module_name.split(".")).with_suffix(".py")


def _module_to_package_path(module_name: str) -> Path:
    return REPO_ROOT / Path(*module_name.split("."))


def test_deleted_inventory_is_doc_traced_and_has_no_ambiguous_rows() -> None:
    assert DELETED_SURFACES
    assert all(isinstance(surface, DeletedSurface) for surface in DELETED_SURFACES)

    missing_trace = [
        surface.surface
        for surface in DELETED_SURFACES
        if not surface.source_doc or not surface.source_inventory or not surface.m6_action
    ]
    assert not missing_trace, f"deleted inventory rows missing doc trace: {missing_trace}"

    wildcard_rows = [surface for surface in DELETED_SURFACES if "*" in surface.surface]
    missing_expansion_note = [surface.surface for surface in wildcard_rows if not surface.note]
    assert not missing_expansion_note, (
        f"wildcard deletion rows need explicit expansion notes: {missing_expansion_note}"
    )


def test_source_tree_lacks_deleted_inventory_paths() -> None:
    deleted = [REPO_ROOT / path.rstrip("/") for path in DELETED_SOURCE_PATHS]
    present = [str(path.relative_to(REPO_ROOT)) for path in deleted if path.exists()]
    assert not present, f"deleted inventory paths still present: {present}"


def test_source_tree_lacks_arnold_pipelines_megaplan_package() -> None:
    deleted = REPO_ROOT / "arnold" / "pipelines" / "megaplan"
    assert not deleted.exists(), "arnold/pipelines/megaplan is an M6 deletion target"


def test_deleted_import_modules_are_physically_absent_from_source_tree() -> None:
    present: list[str] = []
    for module_name in DELETED_IMPORT_MODULES:
        package_path = _module_to_package_path(module_name)
        module_path = _module_to_source_path(module_name)
        if package_path.is_dir() or module_path.exists():
            present.append(module_name)

    assert not present, f"deleted import modules still have source files: {present}"


def test_product_source_does_not_import_deleted_arnold_pipelines_megaplan() -> None:
    product_roots = (REPO_ROOT / "arnold_pipelines",)
    violations: dict[str, tuple[str, ...]] = {}

    for root in product_roots:
        for source in sorted(root.rglob("*.py")):
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            except SyntaxError:
                continue

            hits: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "arnold.pipelines.megaplan" or alias.name.startswith(
                            "arnold.pipelines.megaplan."
                        ):
                            hits.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == "arnold.pipelines.megaplan" or node.module.startswith(
                        "arnold.pipelines.megaplan."
                    ):
                        hits.add(node.module)

            if hits:
                violations[str(source.relative_to(REPO_ROOT))] = tuple(sorted(hits))

    assert violations == {}, (
        "product source imports deleted arnold.pipelines.megaplan surfaces: "
        f"{violations}"
    )

