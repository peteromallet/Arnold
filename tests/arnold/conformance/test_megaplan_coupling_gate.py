"""Ratchet tests for generic Arnold to Megaplan coupling."""

from __future__ import annotations

import ast
from pathlib import Path

from arnold.conformance.checks import check_generic_arnold_megaplan_coupling
from arnold.conformance.suite import run_conformance_suite


def test_current_tree_passes_megaplan_coupling_gate() -> None:
    result = check_generic_arnold_megaplan_coupling()

    assert result.passed is True
    assert result.check_id == "generic-arnold-megaplan-coupling"
    assert result.details["allowlisted_count"] == 6
    assert result.details["coupled_count"] == 6
    assert result.details["unexpected"] == {}
    assert result.details["stale_allowlist"] == []


def test_conformance_suite_runs_megaplan_coupling_gate() -> None:
    suite = run_conformance_suite()

    result = next(
        check
        for check in suite.checks
        if check.check_id == "generic-arnold-megaplan-coupling"
    )
    assert result.passed is True


def test_new_generic_megaplan_import_fails_gate(tmp_path: Path) -> None:
    package_root = tmp_path / "arnold"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "new_surface.py").write_text(
        "\n".join(
            [
                "from arnold.pipelines import megaplan",
                "from arnold.pipelines.megaplan.run_outcome import RunOutcome",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = check_generic_arnold_megaplan_coupling(
        package_root=package_root,
        allowlist=set(),
    )

    assert result.passed is False
    assert "new generic Arnold Megaplan coupling" in result.message
    assert result.details["unexpected"] == {
        "arnold.new_surface": (
            "arnold.pipelines.megaplan",
            "arnold.pipelines.megaplan.run_outcome",
        )
    }


def test_allowlist_stale_entry_fails_gate(tmp_path: Path) -> None:
    package_root = tmp_path / "arnold"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "neutral.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = check_generic_arnold_megaplan_coupling(
        package_root=package_root,
        allowlist={"arnold.neutral"},
    )

    assert result.passed is False
    assert "stale Megaplan coupling allowlist entries" in result.message
    assert result.details["stale_allowlist"] == ["arnold.neutral"]


def test_c1_generic_pipeline_modules_do_not_import_megaplan() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    module_paths = [
        repo_root / "arnold/pipeline/step_io_handoff.py",
        repo_root / "arnold/pipeline/executor.py",
        repo_root / "arnold/pipeline/artifact_io.py",
        repo_root / "arnold/pipeline/step_io_telemetry.py",
    ]

    forbidden: dict[str, tuple[str, ...]] = {}
    for path in module_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = sorted(
            {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
                if alias.name == "arnold.pipelines.megaplan"
                or alias.name.startswith("arnold.pipelines.megaplan.")
            }
            | {
                (node.module or "")
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and (
                    (node.module or "") == "arnold.pipelines.megaplan"
                    or (node.module or "").startswith("arnold.pipelines.megaplan.")
                )
            }
        )
        if imports:
            forbidden[path.relative_to(repo_root).as_posix()] = tuple(imports)

    assert forbidden == {}
