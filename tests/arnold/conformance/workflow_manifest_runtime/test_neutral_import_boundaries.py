from __future__ import annotations

import sys
from pathlib import Path

from arnold.manifest import WorkflowManifest
from arnold.conformance.workflow_manifest_runtime import scan_neutral_product_imports
from arnold.workflow import WorkflowManifest as WorkflowCompatManifest
from arnold.workflow.manifests import WorkflowManifest as WorkflowModuleCompatManifest


def test_neutral_manifest_workflow_and_kernel_do_not_import_product_modules() -> None:
    paths = (
        list(Path("arnold/manifest").rglob("*.py"))
        + list(Path("arnold/workflow").rglob("*.py"))
        + list(Path("arnold/kernel").rglob("*.py"))
    )

    assert scan_neutral_product_imports(paths) == {}


def test_manifest_import_does_not_load_workflow_package() -> None:
    for module_name in list(sys.modules):
        if module_name.startswith("arnold.workflow"):
            del sys.modules[module_name]

    import arnold.manifest  # noqa: F401

    assert not any(module_name.startswith("arnold.workflow") for module_name in sys.modules)


def test_workflow_manifest_exports_preserve_neutral_type_identity() -> None:
    assert WorkflowCompatManifest is WorkflowManifest
    assert WorkflowModuleCompatManifest is WorkflowManifest


def test_scanner_flags_type_checking_product_imports(tmp_path: Path) -> None:
    path = tmp_path / "arnold" / "workflow" / "bad.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from arnold.pipelines.megaplan.foo import Bar\n",
        encoding="utf-8",
    )

    violations = scan_neutral_product_imports((path,))

    assert violations[str(path)] == ("arnold.pipelines.megaplan",)
