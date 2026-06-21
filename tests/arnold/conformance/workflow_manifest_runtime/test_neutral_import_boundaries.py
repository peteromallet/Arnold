from __future__ import annotations

from pathlib import Path

from arnold.conformance.workflow_manifest_runtime import scan_neutral_product_imports


def test_neutral_workflow_and_kernel_do_not_import_product_modules() -> None:
    paths = list(Path("arnold/workflow").rglob("*.py")) + list(Path("arnold/kernel").rglob("*.py"))

    assert scan_neutral_product_imports(paths) == {}


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
