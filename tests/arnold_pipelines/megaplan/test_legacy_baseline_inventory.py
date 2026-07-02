"""Inventory and guard tests for M5 idea paths and legacy graph baseline references.

Validates that:
- Every M5 idea path is classified in the inventory.
- Active classifications match on-disk reality.
- ``_build_legacy_graph_pipeline`` imports/helpers do not reappear
  in active (non-archive) test files outside the known delete-target.
- Archive-only paths are excluded from active rewrite scope.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INVENTORY_PATH = (
    PROJECT_ROOT
    / "tests/arnold_pipelines/megaplan/fixtures/native_goldens"
    / "legacy_baseline_inventory.json"
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _load_inventory() -> Dict[str, Any]:
    assert INVENTORY_PATH.is_file(), f"Inventory not found: {INVENTORY_PATH}"
    return json.loads(INVENTORY_PATH.read_text())


def _active_file_exists(relpath: str) -> bool:
    return (PROJECT_ROOT / relpath).is_file()


def _archive_file_exists(relpath: str) -> bool:
    return (PROJECT_ROOT / relpath).is_file()


# ---------------------------------------------------------------------------
# inventory structure & completeness
# ---------------------------------------------------------------------------


class TestInventoryStructure:
    """Structural checks on the legacy baseline inventory."""

    def test_inventory_file_is_valid_json(self) -> None:
        """The inventory must parse as JSON with the expected top-level keys."""
        inv = _load_inventory()
        assert isinstance(inv, dict)
        for key in (
            "_meta",
            "active_rename_targets",
            "deleted_active_files",
            "archive_only",
            "absent_from_active_tree",
            "_build_legacy_graph_pipeline_references",
        ):
            assert key in inv, f"Missing top-level key: {key}"

    def test_all_m5_idea_paths_are_classified(self) -> None:
        """Every path from the M5 idea must appear in exactly one classification list."""
        inv = _load_inventory()

        rename_paths = {
            e["m5_idea_path"] for e in inv["active_rename_targets"]
        }
        deleted_paths = {
            e["m5_idea_path"] for e in inv["deleted_active_files"]
        }
        archive_paths = {e["m5_idea_path"] for e in inv["archive_only"]}
        absent_paths = {
            e["m5_idea_path"] for e in inv["absent_from_active_tree"]
        }

        all_classified = rename_paths | deleted_paths | archive_paths | absent_paths

        # All M5 idea paths (from the idea snapshot)
        expected_paths = {
            "tests/arnold/pipelines/megaplan/parity_harness.py",
            "tests/arnold/pipeline/native/parity_trace.py",
            "tests/parity/test_graph_projection_parity.py",
            "tests/parity/test_no_state_carry.py",
            "tests/parity/fixtures/workflow_next_matrix.json",
            "tests/test_pipeline_parity.py",
            "tests/test_pipeline_planning_parity.py",
            "tests/test_workflow_topology_parity.py",
            "tests/test_workflow_topology_parity_gate.py",
            "tests/editorial_parity.py",
            "tests/_pipeline/test_planning_discovered_parity.py",
            "tests/_pipeline/test_receipt_planning_parity.py",
            "tests/arnold/pipeline/native/test_graph_parity.py",
            "tests/arnold/pipeline/native/test_runtime_parity.py",
            "tests/arnold/pipeline/test_model_seam_parity.py",
            "tests/arnold/pipelines/deliberation/test_native_parity.py",
            "tests/arnold/pipelines/megaplan/test_creative_native_parity.py",
            "tests/arnold/pipelines/megaplan/test_doc_native_parity.py",
            "tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py",
            "tests/arnold/pipelines/megaplan/test_jokes_native_parity.py",
            "tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py",
            "tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py",
            "tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py",
            "tests/arnold/pipelines/megaplan/test_native_execution_parity_fixtures.py",
            "tests/arnold/pipelines/megaplan/test_native_parity.py",
            "tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py",
            "tests/arnold/pipelines/megaplan/test_graph_baseline.py",
            "tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py",
            "tests/arnold/pipelines/megaplan/test_parity_harness.py",
            "tests/arnold/pipelines/megaplan/test_step_contracts_parity.py",
            "tests/arnold/pipelines/megaplan/data/native_parity/__init__.py",
            "tests/arnold/pipelines/megaplan/data/native_parity/scenarios.py",
            "tests/arnold/pipelines/megaplan/data/native_parity/escalate_golden_graph_trace.json",
            "tests/arnold/pipelines/megaplan/data/native_parity/execute_review_artifact_golden_graph_trace.json",
            "tests/arnold/pipelines/megaplan/data/native_parity/happy_finalize_golden_graph_trace.json",
            "tests/arnold/pipelines/megaplan/data/native_parity/override_abort_golden_graph_trace.json",
            "tests/arnold/pipelines/megaplan/data/native_parity/override_force_proceed_golden_graph_trace.json",
            "tests/arnold/pipelines/megaplan/data/native_parity/revise_loop_golden_graph_trace.json",
            "tests/arnold/pipelines/megaplan/data/native_parity/suspension_resume_golden_graph_trace.json",
            "tests/arnold/pipelines/megaplan/data/native_parity/tiebreaker_golden_graph_trace.json",
        }

        assert all_classified == expected_paths, (
            f"Classification mismatch.\n"
            f"Missing from inventory: {expected_paths - all_classified}\n"
            f"Extra in inventory:   {all_classified - expected_paths}"
        )

    def test_no_duplicate_classifications(self) -> None:
        """No M5 idea path appears in more than one classification list."""
        inv = _load_inventory()
        rename = {e["m5_idea_path"] for e in inv["active_rename_targets"]}
        deleted = {e["m5_idea_path"] for e in inv["deleted_active_files"]}
        archive = {e["m5_idea_path"] for e in inv["archive_only"]}
        absent = {e["m5_idea_path"] for e in inv["absent_from_active_tree"]}

        overlaps = []
        for a, b, label_a, label_b in [
            (rename, deleted, "active_rename_targets", "deleted_active_files"),
            (rename, archive, "active_rename_targets", "archive_only"),
            (rename, absent, "active_rename_targets", "absent_from_active_tree"),
            (deleted, archive, "deleted_active_files", "archive_only"),
            (deleted, absent, "deleted_active_files", "absent_from_active_tree"),
            (archive, absent, "archive_only", "absent_from_active_tree"),
        ]:
            overlap = a & b
            if overlap:
                overlaps.append(f"{label_a} ∩ {label_b}: {overlap}")

        assert not overlaps, f"Duplicate classifications found: {overlaps}"


# ---------------------------------------------------------------------------
# on-disk reality checks
# ---------------------------------------------------------------------------


class TestInventoryReality:
    """Verify that the inventory classification matches the actual filesystem."""

    def test_active_rename_targets_exist_on_disk(self) -> None:
        """Every active rename target must exist at its active_surviving_path."""
        inv = _load_inventory()
        for entry in inv["active_rename_targets"]:
            path = entry["active_surviving_path"]
            assert _active_file_exists(path), (
                f"Rename target listed as active but not on disk: {path}"
            )

    def test_deleted_active_files_exist_on_disk(self) -> None:
        """Every file marked for deletion must currently exist on disk."""
        inv = _load_inventory()
        for entry in inv["deleted_active_files"]:
            path = entry["active_surviving_path"]
            assert _active_file_exists(path), (
                f"Delete target listed as active but not on disk: {path}"
            )

    def test_archive_only_paths_exist_in_archive(self) -> None:
        """Every archive-only path must exist at its archive_path."""
        inv = _load_inventory()
        for entry in inv["archive_only"]:
            archive_path = entry["archive_path"]
            assert archive_path is not None, (
                f"Archive-only entry missing archive_path: {entry['m5_idea_path']}"
            )
            assert _archive_file_exists(archive_path), (
                f"Archive-only path not found in archive: {archive_path}"
            )

    def test_absent_paths_are_really_absent(self) -> None:
        """Paths classified as absent must not exist on the active filesystem."""
        inv = _load_inventory()
        for entry in inv["absent_from_active_tree"]:
            m5_path = entry["m5_idea_path"]
            assert not _active_file_exists(m5_path), (
                f"Path classified as absent but exists on disk: {m5_path}"
            )

    def test_archive_only_paths_not_in_active_tree(self) -> None:
        """Archive-only paths must not also exist in the active tree."""
        inv = _load_inventory()
        for entry in inv["archive_only"]:
            m5_path = entry["m5_idea_path"]
            assert not _active_file_exists(m5_path), (
                f"Archive-only path also exists in active tree: {m5_path}"
            )


# ---------------------------------------------------------------------------
# _build_legacy_graph_pipeline guard
# ---------------------------------------------------------------------------


def _active_test_files() -> List[Path]:
    """Return all .py files under tests/ excluding archive directories."""
    tests_dir = PROJECT_ROOT / "tests"
    files: List[Path] = []
    for py_file in tests_dir.rglob("*.py"):
        if "archive" in py_file.parts:
            continue
        files.append(py_file)
    return files


def _grep_in_file(path: Path, pattern: str) -> List[int]:
    """Return line numbers where *pattern* appears in *path*."""
    try:
        text = path.read_text()
    except Exception:
        return []
    return [i + 1 for i, line in enumerate(text.splitlines()) if pattern in line]


class TestLegacyGraphPipelineGuard:
    """Ensure _build_legacy_graph_pipeline does not reappear in active tests."""

    def test_known_active_references_match_inventory(self) -> None:
        """The inventory's recorded active references must match reality."""
        inv = _load_inventory()
        recorded = inv["_build_legacy_graph_pipeline_references"]["active_test_files"]

        recorded_paths = {entry["path"] for entry in recorded}
        _SELF = "tests/arnold_pipelines/megaplan/test_legacy_baseline_inventory.py"

        # Find all active test files referencing _build_legacy_graph_pipeline
        actual: Dict[str, List[int]] = {}
        for test_file in _active_test_files():
            rel = str(test_file.relative_to(PROJECT_ROOT))
            if rel == _SELF:
                continue  # this file references the symbol in its own assertions
            lines = _grep_in_file(test_file, "_build_legacy_graph_pipeline")
            if lines:
                actual[rel] = lines

        assert set(actual.keys()) == recorded_paths, (
            f"Mismatch between recorded and actual active references.\n"
            f"Recorded: {recorded_paths}\n"
            f"Actual:   {set(actual.keys())}"
        )

        for entry in recorded:
            path = entry["path"]
            assert path in actual, f"Recorded path not found in actual grep: {path}"
            assert entry["lines"] == actual[path], (
                f"Line mismatch for {path}: "
                f"recorded={entry['lines']}, actual={actual[path]}"
            )

    def test_no_unexpected_legacy_graph_imports(self) -> None:
        """No active test file outside the known delete-target imports
        or references ``_build_legacy_graph_pipeline``."""
        inv = _load_inventory()
        known_bad = {
            entry["path"]
            for entry in inv["_build_legacy_graph_pipeline_references"][
                "active_test_files"
            ]
        }
        _SELF = "tests/arnold_pipelines/megaplan/test_legacy_baseline_inventory.py"

        unexpected: Dict[str, List[int]] = {}
        for test_file in _active_test_files():
            rel = str(test_file.relative_to(PROJECT_ROOT))
            if rel in known_bad or rel == _SELF:
                continue
            lines = _grep_in_file(test_file, "_build_legacy_graph_pipeline")
            if lines:
                unexpected[rel] = lines

        assert not unexpected, (
            f"_build_legacy_graph_pipeline found in unexpected active test files:\n"
            + "\n".join(f"  {p}: lines {ls}" for p, ls in unexpected.items())
        )

    def test_archive_only_paths_not_in_rewrite_scope(self) -> None:
        """Archive-only entries must not appear in active rename/rewrite target lists."""
        inv = _load_inventory()
        archive_paths = {e["m5_idea_path"] for e in inv["archive_only"]}
        rename_paths = {e["m5_idea_path"] for e in inv["active_rename_targets"]}
        deleted_paths = {e["m5_idea_path"] for e in inv["deleted_active_files"]}

        # Archive paths should not be in active rename or delete targets
        in_rename = archive_paths & rename_paths
        in_deleted = archive_paths & deleted_paths

        assert not in_rename, (
            f"Archive-only paths incorrectly listed as rename targets: {in_rename}"
        )
        assert not in_deleted, (
            f"Archive-only paths incorrectly listed as delete targets: {in_deleted}"
        )

    def test_old_graph_era_single_file_goldens_absent(self) -> None:
        """No golden_graph_trace.json files exist in the active tree (SD2)."""
        tests_dir = PROJECT_ROOT / "tests"
        active_goldens = []
        for f in tests_dir.rglob("*golden_graph_trace*"):
            if "archive" not in f.parts:
                active_goldens.append(str(f.relative_to(PROJECT_ROOT)))

        assert not active_goldens, (
            f"Old graph-era single-file goldens found in active tree: {active_goldens}"
        )

    def test_inventory_meta_total_matches(self) -> None:
        """The _meta.total_paths must equal the sum of all classification lists."""
        inv = _load_inventory()
        total = (
            len(inv["active_rename_targets"])
            + len(inv["deleted_active_files"])
            + len(inv["archive_only"])
            + len(inv["absent_from_active_tree"])
        )
        assert total == inv["_meta"]["total_paths"], (
            f"Meta total_paths={inv['_meta']['total_paths']} "
            f"but classification sum={total}"
        )
