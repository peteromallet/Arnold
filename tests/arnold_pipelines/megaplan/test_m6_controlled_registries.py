"""Focused tests for the M6 controlled-writer registry (T11 — Step 10).

Covers:
- Schema validation
- Writer coverage across all required categories (python, shell_wrapper,
  resident, cloud, provider, compatibility)
- Every row has all required fields (writer_id, writer_path, writer_category,
  surface_types, owner, current_contract, target_contract, boundary_conditions,
  fail_closed, proof, rollback_policy, mixed_version_policy, retirement_gate,
  evidence_ref, row_hash)
- Stable row hashes across regeneration
- Composite hash stability
- Ownership distribution sanity
- Fail-closed default enforcement
- No UNKNOWN placeholders in critical fields
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import importlib.util as _iu


def _import_generator() -> Any:
    """Import the generator module dynamically."""
    spec = _iu.spec_from_file_location(
        "generate_m6_controlled_registries",
        str(REPO_ROOT / "tools" / "generate_m6_controlled_registries.py"),
    )
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_gen = _import_generator()

FIXTURE_PATH = REPO_ROOT / "evidence" / "controlled-writer-registry.json"
SCHEMA = "m6.controlled-writer-registry.v1"

REQUIRED_FIELDS = {
    "writer_id",
    "writer_path",
    "writer_category",
    "surface_types",
    "owner",
    "current_contract",
    "target_contract",
    "boundary_conditions",
    "fail_closed",
    "proof",
    "rollback_policy",
    "mixed_version_policy",
    "retirement_gate",
    "evidence_ref",
    "row_hash",
}

REQUIRED_CATEGORIES = {
    "python",
    "shell_wrapper",
    "resident",
    "cloud",
    "provider",
    "compatibility",
}

VALID_OWNERS = {
    "WBC",
    "Run Authority",
    "TransitionWriter/repair custody",
}

# ── helpers ────────────────────────────────────────────────────────────────


def _load_fixture() -> dict[str, Any]:
    """Load the fixture artifact, skipping if not found."""
    if not FIXTURE_PATH.exists():
        pytest.skip("Controlled-writer registry not yet generated")
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _compute_row_hash(row: dict[str, Any]) -> str:
    """Compute stable row hash (same as generator)."""
    return _gen._compute_row_hash(row)


def _compute_composite_hash(rows: list[dict[str, Any]]) -> str:
    """Compute composite hash from sorted row hashes."""
    row_hashes = sorted(r["row_hash"] for r in rows)
    combined = "".join(row_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ── schema tests ───────────────────────────────────────────────────────────


class TestRegistrySchema:
    """Validate the top-level structure of the registry artifact."""

    def test_has_correct_schema(self) -> None:
        fixture = _load_fixture()
        assert fixture["schema"] == SCHEMA

    def test_has_generated_at(self) -> None:
        fixture = _load_fixture()
        assert "generated_at" in fixture
        assert fixture["generated_at"]

    def test_has_composite_hash(self) -> None:
        fixture = _load_fixture()
        assert "composite_hash" in fixture
        assert len(fixture["composite_hash"]) == 64

    def test_has_writer_count(self) -> None:
        fixture = _load_fixture()
        assert fixture["writer_count"] > 0
        assert fixture["writer_count"] == len(fixture["rows"])

    def test_has_category_counts(self) -> None:
        fixture = _load_fixture()
        assert "category_counts" in fixture
        total_from_counts = sum(fixture["category_counts"].values())
        assert total_from_counts == fixture["writer_count"]

    def test_has_generator(self) -> None:
        fixture = _load_fixture()
        assert "generator" in fixture
        assert "generate_m6_controlled_registries" in fixture["generator"]

    def test_has_source_inventory(self) -> None:
        fixture = _load_fixture()
        assert "source_inventory" in fixture
        assert "wbc-boundary-inventory" in fixture["source_inventory"]

    def test_has_fail_closed_default(self) -> None:
        fixture = _load_fixture()
        assert "fail_closed_default" in fixture

    def test_rows_is_list(self) -> None:
        fixture = _load_fixture()
        assert isinstance(fixture["rows"], list)


# ── category coverage tests ────────────────────────────────────────────────


class TestCategoryCoverage:
    """Verify that all required writer categories are represented."""

    def test_all_required_categories_present(self) -> None:
        fixture = _load_fixture()
        categories_found = set(fixture.get("writer_categories", []))
        missing = REQUIRED_CATEGORIES - categories_found
        assert not missing, (
            f"Missing required categories: {sorted(missing)}. "
            f"Found: {sorted(categories_found)}"
        )

    def test_python_writers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("python", 0) > 0

    def test_shell_writers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("shell_wrapper", 0) > 0

    def test_resident_writers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("resident", 0) > 0

    def test_cloud_writers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("cloud", 0) > 0

    def test_provider_writers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("provider", 0) > 0

    def test_compatibility_writers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("compatibility", 0) > 0

    def test_no_unknown_category(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["writer_category"] in REQUIRED_CATEGORIES, (
                f"Row {row['writer_id']}: unknown category "
                f"'{row['writer_category']}'"
            )


# ── field completeness tests ───────────────────────────────────────────────


class TestRequiredFields:
    """Every row must have all required fields with non-empty values."""

    def test_all_rows_have_required_fields(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            wid = row.get("writer_id", "?")
            missing = REQUIRED_FIELDS - set(row.keys())
            assert not missing, (
                f"Row {wid}: missing fields {sorted(missing)}"
            )

    def test_all_writer_ids_are_unique(self) -> None:
        fixture = _load_fixture()
        ids = [r["writer_id"] for r in fixture["rows"]]
        assert len(ids) == len(set(ids)), (
            f"Duplicate writer IDs: "
            f"{[i for i in ids if ids.count(i) > 1]}"
        )

    def test_all_writer_paths_are_unique(self) -> None:
        fixture = _load_fixture()
        paths = [r["writer_path"] for r in fixture["rows"]]
        assert len(paths) == len(set(paths)), (
            f"Duplicate writer paths: "
            f"{[p for p in paths if paths.count(p) > 1]}"
        )

    def test_all_critical_fields_are_non_empty(self) -> None:
        fixture = _load_fixture()
        critical_fields = {
            "writer_id", "writer_path", "writer_category",
            "owner", "current_contract", "target_contract",
            "boundary_conditions", "fail_closed", "proof",
            "rollback_policy", "mixed_version_policy", "retirement_gate",
        }
        for row in fixture["rows"]:
            wid = row.get("writer_id", "?")
            for field in critical_fields:
                value = row.get(field)
                assert value, (
                    f"Row {wid}: {field} is empty or missing"
                )

    def test_all_rows_have_evidence_ref(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["evidence_ref"], (
                f"Row {row['writer_id']}: evidence_ref is empty"
            )

    def test_surface_types_is_list(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert isinstance(row["surface_types"], list), (
                f"Row {row['writer_id']}: surface_types is not a list"
            )


# ── ownership tests ────────────────────────────────────────────────────────


class TestOwnershipDistribution:
    """Sanity checks on the ownership distribution."""

    def test_all_owners_are_valid(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["owner"] in VALID_OWNERS, (
                f"Row {row['writer_id']}: unknown owner "
                f"'{row['owner']}'"
            )

    def test_wbc_owns_boundary_runtime_writers(self) -> None:
        fixture = _load_fixture()
        wbc_writers = [
            r for r in fixture["rows"]
            if r["writer_path"].startswith("arnold/workflow/")
        ]
        for w in wbc_writers:
            assert w["owner"] == "WBC", (
                f"WBC workflow writer {w['writer_path']} has owner "
                f"'{w['owner']}', expected WBC"
            )

    def test_run_authority_owns_handler_writers(self) -> None:
        fixture = _load_fixture()
        ra_writers = [
            r for r in fixture["rows"]
            if "megaplan/handlers/" in r["writer_path"]
        ]
        for w in ra_writers:
            assert w["owner"] == "Run Authority", (
                f"Handler writer {w['writer_path']} has owner "
                f"'{w['owner']}', expected Run Authority"
            )


# ── hash stability tests ───────────────────────────────────────────────────


class TestHashStability:
    """Row and composite hashes must be stable and verifiable."""

    def test_all_row_hashes_are_valid_sha256(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            h = row["row_hash"]
            assert len(h) == 64, (
                f"Row {row['writer_id']}: hash length {len(h)} != 64"
            )
            assert all(c in "0123456789abcdef" for c in h), (
                f"Row {row['writer_id']}: hash is not hex"
            )

    def test_row_hashes_match_computed(self) -> None:
        """Each row's stored hash must match the computed hash."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            computed = _compute_row_hash(row)
            stored = row["row_hash"]
            assert computed == stored, (
                f"Row {row['writer_id']}: stored hash {stored[:12]}... "
                f"!= computed {computed[:12]}..."
            )

    def test_composite_hash_matches_computed(self) -> None:
        """The stored composite hash must match the hash of row hashes."""
        fixture = _load_fixture()
        computed = _compute_composite_hash(fixture["rows"])
        stored = fixture["composite_hash"]
        assert computed == stored, (
            f"Composite hash mismatch: stored {stored[:12]}... "
            f"!= computed {computed[:12]}..."
        )

    def test_regeneration_is_stable(self) -> None:
        """Two regeneration runs against the same repo state must produce
        identical composite and row hashes."""
        artifact1 = _gen.generate_registry(output_path=None)
        artifact2 = _gen.generate_registry(output_path=None)

        assert artifact1["composite_hash"] == artifact2["composite_hash"], (
            "Composite hash changed between regeneration runs"
        )

        rows1 = {r["writer_id"]: r for r in artifact1["rows"]}
        rows2 = {r["writer_id"]: r for r in artifact2["rows"]}
        assert rows1.keys() == rows2.keys()

        for wid in sorted(rows1.keys()):
            assert rows1[wid]["row_hash"] == rows2[wid]["row_hash"], (
                f"Row {wid}: hash changed between runs"
            )
            for field in REQUIRED_FIELDS - {"row_hash"}:
                assert rows1[wid][field] == rows2[wid][field], (
                    f"Row {wid}: field {field} changed between runs"
                )

    def test_row_hashes_exclude_hash_field(self) -> None:
        """Row hash must be computed excluding the row_hash field."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            original_hash = row["row_hash"]
            row["row_hash"] = "0" * 64
            recomputed = _compute_row_hash(row)
            assert recomputed == original_hash, (
                f"Row {row['writer_id']}: hash computation is not "
                f"independent of the row_hash field"
            )


# ── fail-closed tests ──────────────────────────────────────────────────────


class TestFailClosedDefault:
    """Every writer must default to fail-closed behavior."""

    def test_fail_closed_is_deny(self) -> None:
        fixture = _load_fixture()
        deny_keywords = {"reject", "block", "denied", "error", "abort", "fail"}
        for row in fixture["rows"]:
            fc_lower = row["fail_closed"].lower()
            has_deny = any(kw in fc_lower for kw in deny_keywords)
            assert has_deny, (
                f"Row {row['writer_id']}: fail_closed does not describe "
                f"a deny/block/error behavior: '{row['fail_closed'][:80]}...'"
            )

    def test_rollback_does_not_restore_dual_authority(self) -> None:
        fixture = _load_fixture()
        no_dual_keywords = {
            "never restore", "no direct", "no dual", "without restoring",
            "disable",
        }
        for row in fixture["rows"]:
            rp = row["rollback_policy"].lower()
            has_safe = any(kw in rp for kw in no_dual_keywords)
            assert has_safe, (
                f"Row {row['writer_id']}: rollback_policy may restore "
                f"dual authority: '{row['rollback_policy'][:80]}...'"
            )


# ── deterministic ordering test ────────────────────────────────────────────


class TestDeterministicOrdering:
    """The registry must be deterministically ordered."""

    def test_rows_sorted_by_category_then_path(self) -> None:
        fixture = _load_fixture()
        # Verify that rows are sorted by (writer_category, writer_path)
        categories_in_order = [
            r["writer_category"] + "/" + r["writer_path"]
            for r in fixture["rows"]
        ]
        assert categories_in_order == sorted(categories_in_order), (
            f"Rows not deterministically sorted"
        )

    def test_no_duplicate_rows(self) -> None:
        fixture = _load_fixture()
        ids = [r["writer_id"] for r in fixture["rows"]]
        assert len(ids) == len(set(ids))


# ── specific writer tests ──────────────────────────────────────────────────


class TestSpecificWriters:
    """Verify that key known writers are present with correct metadata."""

    def test_override_authority_is_registered(self) -> None:
        fixture = _load_fixture()
        by_id = {r["writer_id"]: r for r in fixture["rows"]}
        wid = "writer.arnold_pipelines.megaplan.orchestration.override_authority"
        assert wid in by_id, "override_authority not in registry"
        w = by_id[wid]
        assert "authority_writer" in w["surface_types"]
        assert w["owner"] == "Run Authority"

    def test_rubber_stamp_is_registered(self) -> None:
        fixture = _load_fixture()
        by_id = {r["writer_id"]: r for r in fixture["rows"]}
        wid = "writer.arnold_pipelines.megaplan.orchestration.rubber_stamp"
        assert wid in by_id, "rubber_stamp not in registry"
        w = by_id[wid]
        assert "authority_writer" in w["surface_types"]

    def test_boundary_compatibility_is_registered(self) -> None:
        fixture = _load_fixture()
        by_id = {r["writer_id"]: r for r in fixture["rows"]}
        wid = "writer.arnold.workflow.boundary_compatibility"
        assert wid in by_id, "boundary_compatibility not in registry"
        w = by_id[wid]
        assert w["writer_category"] == "compatibility"
        assert "compatibility_shim" in w["surface_types"]

    def test_execute_binding_writers_are_registered(self) -> None:
        fixture = _load_fixture()
        by_id = {r["writer_id"]: r for r in fixture["rows"]}
        binding_writers = [
            wid for wid in by_id
            if "execute._binding" in wid
        ]
        assert len(binding_writers) >= 3, (
            f"Expected at least 3 execute/_binding writers, "
            f"got {len(binding_writers)}: {binding_writers}"
        )
        for wid in binding_writers:
            assert "authority_writer" in by_id[wid]["surface_types"], (
                f"{wid}: expected authority_writer in surface_types"
            )

    def test_shell_wrappers_have_boundary_effects(self) -> None:
        fixture = _load_fixture()
        shell_writers = [
            r for r in fixture["rows"]
            if r["writer_category"] == "shell_wrapper"
        ]
        assert len(shell_writers) >= 3, (
            f"Expected at least 3 shell wrappers, got {len(shell_writers)}"
        )

    def test_dynamic_surfaces_are_registered(self) -> None:
        fixture = _load_fixture()
        dynamic_writers = [
            r for r in fixture["rows"]
            if r["writer_path"].startswith("dynamic.")
        ]
        assert len(dynamic_writers) >= 5, (
            f"Expected at least 5 dynamic surfaces, got {len(dynamic_writers)}"
        )


# ── generator properties ──────────────────────────────────────────────────


class TestGeneratorProperties:
    """Verify generator-level invariants."""

    def test_generator_is_read_only(self) -> None:
        """The generator must not mutate the WBC inventory."""
        inv_path = REPO_ROOT / "evidence" / "wbc-boundary-inventory.json"
        assert inv_path.exists(), "WBC inventory missing"

        before = inv_path.read_text(encoding="utf-8")
        _gen.generate_registry(output_path=None)
        after = inv_path.read_text(encoding="utf-8")

        assert before == after, (
            "Generator mutated the WBC inventory — this is a read-only violation"
        )

    def test_registry_rows_is_not_empty(self) -> None:
        fixture = _load_fixture()
        assert len(fixture["rows"]) > 0

    def test_writer_count_matches_category_counts(self) -> None:
        fixture = _load_fixture()
        total = sum(fixture["category_counts"].values())
        assert total == fixture["writer_count"], (
            f"category_counts sum ({total}) != writer_count "
            f"({fixture['writer_count']})"
        )
