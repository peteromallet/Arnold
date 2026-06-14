from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from arnold.conformance import (
    ConformanceCheckResult,
    ConformanceSuiteResult,
    assert_conformance,
    assert_suite_compliant,
    run_conformance_suite,
)
from arnold.conformance.checks import (
    ACTIVE_MEGAPLAN_PACKAGE_NAMES,
    check_import_coupling,
    check_never_port_artifacts,
    check_package_name_staleness,
    check_public_workflow_layering,
    check_semantic_coupling,
)


def _arnold_root(tmp_path: Path) -> Path:
    root = tmp_path / "arnold"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    return root


def _write(root: Path, relative: str, content: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path


def test_conformance_public_symbols_are_importable() -> None:
    result = ConformanceCheckResult(check_id="example", passed=True)
    suite = ConformanceSuiteResult(suite_id="example", checks=(result,))

    assert result.passed is True
    assert suite.passed is True
    assert suite.check_count == 1
    assert suite.failure_count == 0
    assert_conformance(result)
    assert_suite_compliant(suite)


def test_current_tree_passes_initial_extraction_conformance_suite() -> None:
    suite = run_conformance_suite()

    assert suite.passed is True
    assert {
        "import-coupling",
        "package-name-staleness",
        "semantic-coupling",
        "public-workflow-layering",
        "never-port-artifacts",
    }.issubset({check.check_id for check in suite.checks})


def test_conformance_package_import_does_not_import_megaplan() -> None:
    script = """
import sys

class BlockMegaplan:
    def find_spec(self, fullname, path=None, target=None):
        blocked = (
            fullname == "megaplan"
            or fullname.startswith("arnold.pipelines.megaplan.")
            or fullname == "arnold.pipelines.megaplan"
            or fullname.startswith("arnold.pipelines.megaplan.")
            or fullname == "arnold_pipelines.megaplan"
            or fullname.startswith("arnold_pipelines.megaplan.")
        )
        if blocked:
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockMegaplan())
import arnold.conformance
assert not any("megaplan" in name for name in sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_active_megaplan_package_names_are_scanned() -> None:
    assert ACTIVE_MEGAPLAN_PACKAGE_NAMES == (
        "megaplan",
        "arnold.pipelines.megaplan",
        "arnold_pipelines.megaplan",
    )


def test_import_coupling_fails_on_new_generic_megaplan_import(tmp_path: Path) -> None:
    root = _arnold_root(tmp_path)
    _write(
        root,
        "generic_surface.py",
        """
        from arnold_pipelines.megaplan.runtime import Driver
        """,
    )

    result = check_import_coupling(package_root=root, allowlist=set())

    assert result.passed is False
    assert result.details["unexpected"] == {
        "arnold.generic_surface": (
            "arnold_pipelines.megaplan.runtime",
            "arnold_pipelines.megaplan.runtime.Driver",
        )
    }


def test_package_name_staleness_fails_on_runtime_string_reference(tmp_path: Path) -> None:
    root = _arnold_root(tmp_path)
    _write(
        root,
        "launcher.py",
        """
        COMMAND = "python -m arnold.pipelines.megaplan run"
        """,
    )

    result = check_package_name_staleness(package_root=root, allowlist=set())

    assert result.passed is False
    assert result.details["unexpected"] == {
        "arnold.launcher": ("arnold.pipelines.megaplan",)
    }


def test_semantic_coupling_fails_on_megaplan_workflow_vocabulary(tmp_path: Path) -> None:
    root = _arnold_root(tmp_path)
    _write(
        root,
        "workflow.py",
        """
        NEXT_HANDLER = "handle_tiebreaker"
        PHASE = "tiebreaker"
        STATE_CLASS = "PlanState"
        PLAN_ROOT = ".megaplan/plans/example"
        """,
    )

    result = check_semantic_coupling(package_root=root, allowlist=set())

    assert result.passed is False
    assert result.details["unexpected"] == {
        "arnold.workflow": (
            ".megaplan",
            "PlanState",
            "handler-name",
            "phase:tiebreaker",
            "tiebreaker",
        )
    }


def test_public_workflow_layering_fails_on_public_stage_export(tmp_path: Path) -> None:
    root = _arnold_root(tmp_path)
    _write(root, "pipelines/__init__.py")
    _write(
        root,
        "pipelines/example/__init__.py",
        """
        from arnold.pipeline import Stage

        __all__ = ["Stage", "build"]

        def build(stage: Stage) -> Stage:
            return stage
        """,
    )

    result = check_public_workflow_layering(package_root=root, allowlist=set())

    assert result.passed is False
    assert result.details["unexpected"] == {
        "arnold.pipelines.example": (
            "annotation-Stage",
            "exports-Stage",
            "package-imports-Stage",
        )
    }


def test_never_port_artifacts_fails_on_runtime_artifact_files(tmp_path: Path) -> None:
    _write(tmp_path, ".megaplan/_archived-plans/old/state.json", "{}")
    _write(tmp_path, ".hermes_state", "{}")
    _write(tmp_path, "data/run.db-wal", "")
    _write(tmp_path, "logs/driver-001.log", "")
    _write(tmp_path, "runs/prompt_dump.txt", "")
    _write(tmp_path, "runs/runtime_state.json", "{}")
    _write(tmp_path, "runs/receipt.json", "{}")

    result = check_never_port_artifacts(repo_root=tmp_path, allowlist=set())

    assert result.passed is False
    assert set(result.details["unexpected"]) == {
        ".hermes_state",
        ".megaplan/_archived-plans/old/state.json",
        "data/run.db-wal",
        "logs/driver-001.log",
        "runs/prompt_dump.txt",
        "runs/receipt.json",
        "runs/runtime_state.json",
    }


def test_active_megaplan_runtime_dirs_are_not_source_artifacts(tmp_path: Path) -> None:
    _write(tmp_path, ".megaplan/plans/current/step_receipt_execute_v2.json", "{}")
    _write(tmp_path, ".megaplan/verification/verification/raw_latest.log", "")
    _write(tmp_path, ".megaplan/.state-locks/current.lock", "")
    _write(tmp_path, ".megaplan/_archived-plans/old/state.json", "{}")

    result = check_never_port_artifacts(repo_root=tmp_path, allowlist=set())

    assert result.passed is False
    assert result.details["unexpected"] == {
        ".megaplan/_archived-plans/old/state.json": (".megaplan archived plan",)
    }


def test_allowlist_entries_are_ratchets_and_stale_entries_fail(tmp_path: Path) -> None:
    root = _arnold_root(tmp_path)
    _write(root, "neutral.py", "VALUE = 1\n")

    result = check_import_coupling(
        package_root=root,
        allowlist={"arnold.neutral"},
    )

    assert result.passed is False
    assert result.details["stale_allowlist"] == ["arnold.neutral"]
