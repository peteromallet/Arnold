from __future__ import annotations

import ast
from pathlib import Path

from scripts.generate_native_representation_evidence import generate_evidence_bundle
from arnold.conformance.deleted_surfaces import (
    DELETED_IMPORT_MODULES,
    DELETED_SOURCE_PATHS,
    DELETED_SURFACES,
    DeletedSurface,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFORMANCE_PATH = REPO_ROOT / "docs/arnold/megaplan-native-representation-conformance.yaml"
TRACEABILITY_PATH = REPO_ROOT / "docs/arnold/megaplan-native-representation-traceability.yaml"


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


def test_generated_evidence_bundle_records_dead_delete_mutation_scan() -> None:
    bundle = generate_evidence_bundle(
        conformance_path=CONFORMANCE_PATH,
        traceability_path=TRACEABILITY_PATH,
        repo_root=REPO_ROOT,
    )
    record = bundle["dead_delete_mutation_checks"][0]
    present_deleted_paths = [
        str((REPO_ROOT / path.rstrip("/")).relative_to(REPO_ROOT))
        for path in DELETED_SOURCE_PATHS
        if (REPO_ROOT / path.rstrip("/")).exists()
    ]
    present_deleted_modules: list[str] = []
    for module_name in DELETED_IMPORT_MODULES:
        package_path = _module_to_package_path(module_name)
        module_path = _module_to_source_path(module_name)
        if package_path.is_dir() or module_path.exists():
            present_deleted_modules.append(module_name)
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

    assert record["check_id"] == "dead_delete_mutation"
    assert record["row_ids"] == ["source-path-reconciliation"]
    assert record["proof_artifact_path"] == "tests/arnold/conformance/test_deleted_surfaces.py"
    assert record["deleted_source_path_count"] == len(DELETED_SOURCE_PATHS)
    assert record["deleted_import_module_count"] == len(DELETED_IMPORT_MODULES)
    assert record["present_deleted_paths"] == present_deleted_paths
    assert record["present_deleted_modules"] == present_deleted_modules
    assert record["product_import_violations"] == {
        path: list(imports) for path, imports in sorted(violations.items())
    }
    assert record["passed"] is (
        not present_deleted_paths and not present_deleted_modules and not violations
    )
