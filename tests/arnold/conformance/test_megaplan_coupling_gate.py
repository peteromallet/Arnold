"""Ratchet tests for generic Arnold to Megaplan coupling."""

from __future__ import annotations

import ast
from pathlib import Path

from arnold.conformance.checks import check_generic_arnold_megaplan_coupling
from arnold.conformance.suite import run_conformance_suite
from scripts.generate_native_representation_evidence import (
    FORBIDDEN_AUTHORITY_SCANS,
    generate_evidence_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFORMANCE_PATH = REPO_ROOT / "docs/arnold/megaplan-native-representation-conformance.yaml"
TRACEABILITY_PATH = REPO_ROOT / "docs/arnold/megaplan-native-representation-traceability.yaml"


def test_current_tree_passes_megaplan_coupling_gate() -> None:
    result = check_generic_arnold_megaplan_coupling()

    assert result.passed is True
    assert result.check_id == "generic-arnold-megaplan-coupling"
    assert result.details["allowlisted_count"] == 11
    assert result.details["coupled_count"] == 11
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
                "from arnold_pipelines.megaplan.run_outcome import RunOutcome",
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
            "arnold_pipelines.megaplan.run_outcome",
            "arnold_pipelines.megaplan.run_outcome.RunOutcome",
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
    repo_root = REPO_ROOT
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
                if alias.name == "arnold_pipelines.megaplan"
                or alias.name.startswith("arnold_pipelines.megaplan.")
            }
            | {
                (node.module or "")
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and (
                    (node.module or "") == "arnold_pipelines.megaplan"
                    or (node.module or "").startswith("arnold_pipelines.megaplan.")
                )
            }
        )
        if imports:
            forbidden[path.relative_to(repo_root).as_posix()] = tuple(imports)

    assert forbidden == {}


def test_generated_evidence_bundle_records_compatibility_quarantine_gate() -> None:
    bundle = generate_evidence_bundle(
        conformance_path=CONFORMANCE_PATH,
        traceability_path=TRACEABILITY_PATH,
        repo_root=REPO_ROOT,
    )
    record = bundle["compatibility_quarantine_checks"][0]
    coupling_gate = check_generic_arnold_megaplan_coupling()

    assert record["check_id"] == "compatibility_quarantine"
    assert record["row_ids"] == ["source-path-reconciliation"]
    assert record["proof_artifact_path"] == "tests/arnold/conformance/test_megaplan_coupling_gate.py"
    assert record["quarantined_scan_ids"] == [scan.scan_id for scan in FORBIDDEN_AUTHORITY_SCANS]
    assert record["quarantine_record_count"] == len(FORBIDDEN_AUTHORITY_SCANS)
    assert record["authority_conflicts"] == {}
    assert record["coupling_gate"] == {
        "passed": coupling_gate.passed,
        "check_id": coupling_gate.check_id,
        "message": coupling_gate.message,
        "details": coupling_gate.details,
    }
    assert record["passed"] is coupling_gate.passed
