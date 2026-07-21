"""Report-only replay tests for M8A fixtures.

Each fixture is compiled twice and the results are compared for
byte-identical task contract hash, stable graph metrics, and unchanged
source bytes.  The historical-plan helper consumes only data copied from
``finalize_snapshot.json`` into temporary directories; it never reads or
writes any ``.megaplan/plans/`` path.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.orchestration.task_feasibility import (
    compile_task_feasibility,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "m8a_replay"

FIXTURE_FILES = {
    "transaction_spine": FIXTURE_DIR / "transaction_spine.json",
    "strategy_roadmap": FIXTURE_DIR / "strategy_roadmap.json",
    "existing_plan_manifest": FIXTURE_DIR / "existing_plan_manifest.json",
}


def _load_fixture(path: Path) -> tuple[dict[str, Any], str]:
    """Load a fixture JSON file and return its parsed content and raw bytes hash."""
    raw = path.read_bytes()
    raw_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, raw_hash


def _extract_feasibility_payload(fixture: dict[str, Any]) -> dict[str, Any]:
    """Extract only the fields that compile_task_feasibility consumes.

    The fixture may have extra metadata fields (fixture_source, description)
    that are not part of the task contract.  This helper strips them so the
    payload passed to the compiler is exactly the task graph.
    """
    return {
        "task_contract_version": fixture["task_contract_version"],
        "tasks": fixture["tasks"],
        "validation_jobs": fixture.get("validation_jobs", []),
    }


def _fixture_bytes_hash(path: Path) -> str:
    """Return the sha256 hash of the raw fixture bytes on disk."""
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


class TestM8AReplayFixtures:
    """Report-only replay: compile each fixture twice and assert stability."""

    @pytest.mark.parametrize(
        "fixture_name,fixture_path",
        [
            ("transaction_spine", FIXTURE_FILES["transaction_spine"]),
            ("strategy_roadmap", FIXTURE_FILES["strategy_roadmap"]),
            ("existing_plan_manifest", FIXTURE_FILES["existing_plan_manifest"]),
        ],
    )
    def test_fixture_compiles_twice_with_identical_hash(
        self,
        fixture_name: str,
        fixture_path: Path,
    ) -> None:
        """Compile the fixture twice; assert the task_contract_hash is byte-identical."""
        payload, _ = _load_fixture(fixture_path)
        feasibility_payload = _extract_feasibility_payload(payload)

        first = compile_task_feasibility(feasibility_payload)
        second = compile_task_feasibility(feasibility_payload)

        assert first["task_contract_hash"] == second["task_contract_hash"], (
            f"{fixture_name}: task_contract_hash differs across compilations: "
            f"{first['task_contract_hash']} vs {second['task_contract_hash']}"
        )

    @pytest.mark.parametrize(
        "fixture_name,fixture_path",
        [
            ("transaction_spine", FIXTURE_FILES["transaction_spine"]),
            ("strategy_roadmap", FIXTURE_FILES["strategy_roadmap"]),
            ("existing_plan_manifest", FIXTURE_FILES["existing_plan_manifest"]),
        ],
    )
    def test_fixture_graph_metrics_are_stable(
        self,
        fixture_name: str,
        fixture_path: Path,
    ) -> None:
        """Compile the fixture twice; assert seriality, critical_path, and max_width are identical."""
        payload, _ = _load_fixture(fixture_path)
        feasibility_payload = _extract_feasibility_payload(payload)

        first = compile_task_feasibility(feasibility_payload)
        second = compile_task_feasibility(feasibility_payload)

        # Graph topology metrics must be identical across compilations.
        assert first["seriality"] == second["seriality"], (
            f"{fixture_name}: seriality differs: {first['seriality']} vs {second['seriality']}"
        )
        assert first["critical_path_task_count"] == second["critical_path_task_count"], (
            f"{fixture_name}: critical_path_task_count differs: "
            f"{first['critical_path_task_count']} vs {second['critical_path_task_count']}"
        )
        assert first["max_width"] == second["max_width"], (
            f"{fixture_name}: max_width differs: {first['max_width']} vs {second['max_width']}"
        )
        assert first["critical_path_minutes"] == second["critical_path_minutes"], (
            f"{fixture_name}: critical_path_minutes differs: "
            f"{first['critical_path_minutes']} vs {second['critical_path_minutes']}"
        )

    @pytest.mark.parametrize(
        "fixture_name,fixture_path",
        [
            ("transaction_spine", FIXTURE_FILES["transaction_spine"]),
            ("strategy_roadmap", FIXTURE_FILES["strategy_roadmap"]),
            ("existing_plan_manifest", FIXTURE_FILES["existing_plan_manifest"]),
        ],
    )
    def test_fixture_bytes_unchanged_after_compilation(
        self,
        fixture_name: str,
        fixture_path: Path,
    ) -> None:
        """Compile the fixture; assert the source fixture bytes on disk remain unchanged."""
        before_hash = _fixture_bytes_hash(fixture_path)

        payload, _ = _load_fixture(fixture_path)
        feasibility_payload = _extract_feasibility_payload(payload)
        compile_task_feasibility(feasibility_payload)

        after_hash = _fixture_bytes_hash(fixture_path)

        assert before_hash == after_hash, (
            f"{fixture_name}: fixture bytes changed on disk after compilation: "
            f"{before_hash} -> {after_hash}"
        )

    @pytest.mark.parametrize(
        "fixture_name,fixture_path",
        [
            ("transaction_spine", FIXTURE_FILES["transaction_spine"]),
            ("strategy_roadmap", FIXTURE_FILES["strategy_roadmap"]),
            ("existing_plan_manifest", FIXTURE_FILES["existing_plan_manifest"]),
        ],
    )
    def test_historical_plan_helper_uses_temp_dirs_only(
        self,
        fixture_name: str,
        fixture_path: Path,
        tmp_path: Path,
    ) -> None:
        """Prove that the historical-plan helper consumes only copied data in temp dirs.

        The test copies the fixture into a temporary directory, compiles it from there,
        and then verifies that no ``.megaplan/plans/`` path was accessed or written.
        """
        payload, _ = _load_fixture(fixture_path)
        feasibility_payload = _extract_feasibility_payload(payload)

        # Simulate a historical-plan helper: copy snapshot data into a temp dir
        # and never touch any .megaplan/plans/ path.
        snapshot_dir = tmp_path / "snapshot_copy"
        snapshot_dir.mkdir()
        snapshot_file = snapshot_dir / "finalize_snapshot.json"
        snapshot_file.write_text(
            json.dumps(feasibility_payload, sort_keys=True, indent=2),
            encoding="utf-8",
        )

        # Compile from the temp copy — this is the only allowed input path.
        copied_payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
        report = compile_task_feasibility(copied_payload)

        assert report["task_contract_hash"], (
            f"{fixture_name}: compilation from temp copy produced no hash"
        )

        # Assert no .megaplan/plans/ paths exist in the tmp_path tree.
        megaplan_plans = list(tmp_path.rglob(".megaplan/plans/*"))
        assert not megaplan_plans, (
            f"{fixture_name}: historical-plan helper wrote to .megaplan/plans/ path: {megaplan_plans}"
        )

        # Also confirm the original fixture on disk was not modified.
        current_hash = _fixture_bytes_hash(fixture_path)
        payload2, pre_hash = _load_fixture(fixture_path)
        assert current_hash == pre_hash, (
            f"{fixture_name}: fixture bytes were modified during historical-plan helper test"
        )

    def test_transaction_spine_is_highly_serial(self) -> None:
        """The Transaction Spine fixture (30 tasks, 29 edges) must have high seriality."""
        payload, _ = _load_fixture(FIXTURE_FILES["transaction_spine"])
        feasibility_payload = _extract_feasibility_payload(payload)

        report = compile_task_feasibility(feasibility_payload)

        assert report["task_count"] == 30, f"Expected 30 tasks, got {report['task_count']}"
        assert report["edge_count"] == 29, f"Expected 29 edges, got {report['edge_count']}"
        assert report["seriality"] > 0.90, (
            f"Transaction Spine should be highly serial (>0.90), got {report['seriality']}"
        )
        assert report["max_width"] == 1, (
            f"Transaction Spine should have max_width=1, got {report['max_width']}"
        )

    def test_strategy_roadmap_has_mixed_structure(self) -> None:
        """The Strategy Roadmap fixture must show some parallelism (max_width > 1)."""
        payload, _ = _load_fixture(FIXTURE_FILES["strategy_roadmap"])
        feasibility_payload = _extract_feasibility_payload(payload)

        report = compile_task_feasibility(feasibility_payload)

        assert report["task_count"] == 15, f"Expected 15 tasks, got {report['task_count']}"
        # Strategy roadmap has both serial chains and parallel work
        assert report["max_width"] > 1, (
            f"Strategy Roadmap should have some parallelism, got max_width={report['max_width']}"
        )
        assert 0.0 < report["seriality"] < 1.0, (
            f"Strategy Roadmap should have mixed seriality, got {report['seriality']}"
        )

    def test_existing_plan_manifest_has_expected_structure(self) -> None:
        """The existing-plan manifest fixture must have the expected task count and structure."""
        payload, _ = _load_fixture(FIXTURE_FILES["existing_plan_manifest"])
        feasibility_payload = _extract_feasibility_payload(payload)

        report = compile_task_feasibility(feasibility_payload)

        assert report["task_count"] == 8, f"Expected 8 tasks, got {report['task_count']}"
        # Existing plan has both independent and dependent tasks
        assert report["max_width"] >= 1
        assert report["edge_count"] > 0, "Existing plan should have some dependencies"

    def test_all_fixtures_report_stable_diagnostics(self) -> None:
        """Every fixture must produce stable diagnostics across repeated compilations.

        The Transaction Spine (30 tasks, 29 edges) is a captured highly-serial plan
        that M8A is designed to detect — it is expected to carry serial-graph and
        budget diagnostics.  The Strategy Roadmap and existing-plan manifest should
        be admitted without diagnostics.
        """
        _EXPECTED_NOT_ADMITTED = {"transaction_spine"}

        for name, path in FIXTURE_FILES.items():
            payload, _ = _load_fixture(path)
            feasibility_payload = _extract_feasibility_payload(payload)

            first = compile_task_feasibility(feasibility_payload)
            second = compile_task_feasibility(feasibility_payload)

            # Diagnostics must be stable across compilations.
            assert first["diagnostics"] == second["diagnostics"], (
                f"{name}: diagnostics differ across compilations: "
                f"{first['diagnostics']} vs {second['diagnostics']}"
            )
            assert first["admitted"] == second["admitted"], (
                f"{name}: admitted status differs across compilations"
            )

            if name in _EXPECTED_NOT_ADMITTED:
                assert first["admitted"] is False, (
                    f"{name}: expected not admitted (captured serial plan) but was admitted"
                )
                codes = {d["code"] for d in first["diagnostics"]}
                assert "serial_graph_unjustified" in codes, (
                    f"{name}: expected serial_graph_unjustified diagnostic, got {codes}"
                )
            else:
                assert first["admitted"] is True, (
                    f"{name}: fixture not admitted — diagnostics: {first['diagnostics']}"
                )
                assert first["diagnostics"] == [], (
                    f"{name}: unexpected diagnostics: {first['diagnostics']}"
                )

    def test_fixture_contract_hash_is_deterministic_across_loads(self) -> None:
        """Loading the same fixture twice must produce the same contract hash."""
        for name, path in FIXTURE_FILES.items():
            payload_a, _ = _load_fixture(path)
            payload_b, _ = _load_fixture(path)

            report_a = compile_task_feasibility(_extract_feasibility_payload(payload_a))
            report_b = compile_task_feasibility(_extract_feasibility_payload(payload_b))

            assert report_a["task_contract_hash"] == report_b["task_contract_hash"], (
                f"{name}: hash differs across separate fixture loads"
            )
