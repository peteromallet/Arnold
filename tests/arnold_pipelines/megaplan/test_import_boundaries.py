"""Source and import-runtime boundary tests for ``arnold_pipelines.megaplan``.

These tests sit alongside ``test_import_boundaries.py`` and verify runtime
package boundaries in addition to the static source scan.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Static parity adapters explicitly allowed to import the legacy package.
M4_PARITY_ADAPTER_PATHS = {
    "arnold_pipelines/megaplan/workers/_impl.py",
    "arnold_pipelines/megaplan/workers/hermes.py",
}

REPO_ROOT = Path(__file__).parents[3]


def _collect_runtime_imports_of_legacy() -> set[str]:
    """Import arnold_pipelines.megaplan and record which legacy modules load."""

    before = set(sys.modules.keys())
    import arnold_pipelines.megaplan  # noqa: F401
    imported = set(sys.modules.keys()) - before
    return {m for m in imported if m.startswith("arnold.pipelines.megaplan.")}


def test_importing_new_package_only_loads_allowed_legacy_adapters() -> None:
    loaded = _collect_runtime_imports_of_legacy()
    # The new package should not statically import legacy modules. Dynamic
    # forwards from vendored agent adapters are a separate concern covered by
    # the arnold.agent boundary test.
    assert loaded == set(), f"arnold_pipelines.megaplan loaded legacy modules: {loaded}"


def test_new_package_source_does_not_import_legacy_except_adapters() -> None:
    root = REPO_ROOT / "arnold_pipelines" / "megaplan"
    violations: dict[str, list[str]] = {}

    for source in sorted(root.rglob("*.py")):
        rel = str(source.relative_to(root.parent.parent))
        if rel in M4_PARITY_ADAPTER_PATHS:
            continue
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except SyntaxError:
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
            violations[rel] = bad

    assert violations == {}, f"new-package source imports legacy package: {violations}"


def test_new_package_has_no_unlisted_parity_adapters() -> None:
    root = REPO_ROOT / "arnold_pipelines" / "megaplan"
    importers: set[str] = set()

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
                        importers.add(str(source.relative_to(root.parent.parent)))
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "arnold.pipelines.megaplan"
                    or node.module.startswith("arnold.pipelines.megaplan.")
                ):
                    importers.add(str(source.relative_to(root.parent.parent)))

    assert importers.issubset(M4_PARITY_ADAPTER_PATHS), (
        f"unlisted legacy importers: {importers - M4_PARITY_ADAPTER_PATHS}"
    )


def test_agentbox_resident_boundary_note_covers_ownership_categories() -> None:
    note = REPO_ROOT / "docs" / "agentbox-resident-boundary.md"
    text = note.read_text(encoding="utf-8").lower()

    required_categories = {
        "arnold-facing neutral seams": (
            "inboundevent",
            "outboundmessage",
            "emitprotocol",
        ),
        "megaplan-owned resident runtime details": (
            "residentruntime",
            "megaplanresidentprofile",
            "store",
        ),
        "agentbox-owned operator/profile/helper integration": (
            "operator",
            "profile",
            "helper",
        ),
    }

    missing = {
        category: tuple(term for term in terms if term not in text)
        for category, terms in required_categories.items()
        if category not in text or any(term not in text for term in terms)
    }
    assert missing == {}
