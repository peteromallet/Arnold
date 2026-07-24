"""Focused tests for the M6 authority-reader registry (T12 — Step 11).

Covers:
- Schema validation
- Reader coverage across all required categories (python, shell_wrapper,
  resident, cloud_status_watchdog, provider, projection, compatibility,
  historical_reader)
- Every row has all required fields (reader_id, reader_path, reader_category,
  surface_types, owner, current_contract, target_contract, boundary_conditions,
  fail_closed, proof, rollback_policy, mixed_version_policy, retirement_gate,
  evidence_ref, row_hash)
- Stable row hashes across regeneration
- Composite hash stability
- Ownership distribution sanity
- NORTH STAR GUARD: projections, liveness, status snapshots, and support labels
  CANNOT be positive authority
- Non-authoritative readers are correctly marked is_authority=false
- Fail-closed default enforcement
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

FIXTURE_PATH = REPO_ROOT / "evidence" / "authority-reader-registry.json"
SCHEMA = "m6.authority-reader-registry.v1"

REQUIRED_FIELDS = {
    "reader_id",
    "reader_path",
    "reader_category",
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
    "cloud_status_watchdog",
    "provider",
    "projection",
    "compatibility",
    "historical_reader",
}

VALID_OWNERS = {
    "WBC",
    "Run Authority",
    "TransitionWriter/repair custody",
}

# Surfaces that MUST NOT be positive authority
NON_AUTHORITATIVE_SURFACES = {
    "projection",
    "liveness",
    "status_snapshot",
    "support_label",
}


# ── helpers ────────────────────────────────────────────────────────────────


def _load_fixture() -> dict[str, Any]:
    """Load the fixture artifact, skipping if not found."""
    if not FIXTURE_PATH.exists():
        pytest.skip("Authority-reader registry not yet generated")
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


class TestReaderRegistrySchema:
    """Validate the top-level structure of the reader registry artifact."""

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

    def test_has_reader_count(self) -> None:
        fixture = _load_fixture()
        assert fixture["reader_count"] > 0
        assert fixture["reader_count"] == len(fixture["rows"])

    def test_has_category_counts(self) -> None:
        fixture = _load_fixture()
        assert "category_counts" in fixture
        total_from_counts = sum(fixture["category_counts"].values())
        assert total_from_counts == fixture["reader_count"]

    def test_has_generator(self) -> None:
        fixture = _load_fixture()
        assert "generator" in fixture
        assert "generate_m6_controlled_registries" in fixture["generator"]

    def test_has_source_inventory(self) -> None:
        fixture = _load_fixture()
        assert "source_inventory" in fixture
        assert "wbc-boundary-inventory" in fixture["source_inventory"]

    def test_has_north_star_guard(self) -> None:
        fixture = _load_fixture()
        assert "north_star_guard" in fixture
        guard = fixture["north_star_guard"].lower()
        assert "projections" in guard
        assert "liveness" in guard
        assert "status snapshots" in guard or "status_snapshot" in guard
        assert "support labels" in guard or "support_label" in guard

    def test_has_non_authoritative_count(self) -> None:
        fixture = _load_fixture()
        assert "non_authoritative_count" in fixture
        assert fixture["non_authoritative_count"] >= 0

    def test_has_non_authoritative_reader_ids(self) -> None:
        fixture = _load_fixture()
        assert "non_authoritative_reader_ids" in fixture
        assert isinstance(fixture["non_authoritative_reader_ids"], list)

    def test_has_fail_closed_default(self) -> None:
        fixture = _load_fixture()
        assert "fail_closed_default" in fixture

    def test_rows_is_list(self) -> None:
        fixture = _load_fixture()
        assert isinstance(fixture["rows"], list)


# ── category coverage tests ────────────────────────────────────────────────


class TestReaderCategoryCoverage:
    """Verify that all required reader categories are represented."""

    def test_all_required_categories_present(self) -> None:
        fixture = _load_fixture()
        categories_found = set(fixture.get("reader_categories", []))
        missing = REQUIRED_CATEGORIES - categories_found
        assert not missing, (
            f"Missing required categories: {sorted(missing)}. "
            f"Found: {sorted(categories_found)}"
        )

    def test_python_readers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("python", 0) > 0

    def test_projection_readers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("projection", 0) > 0

    def test_cloud_watchdog_readers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("cloud_status_watchdog", 0) > 0

    def test_shell_wrapper_readers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("shell_wrapper", 0) > 0

    def test_historical_readers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("historical_reader", 0) > 0

    def test_compatibility_readers_exist(self) -> None:
        fixture = _load_fixture()
        assert fixture["category_counts"].get("compatibility", 0) > 0

    def test_no_unknown_category(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["reader_category"] in REQUIRED_CATEGORIES, (
                f"Row {row['reader_id']}: unknown category "
                f"'{row['reader_category']}'"
            )


# ── field completeness tests ───────────────────────────────────────────────


class TestReaderRequiredFields:
    """Every row must have all required fields with non-empty values."""

    def test_all_rows_have_required_fields(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            rid = row.get("reader_id", "?")
            missing = REQUIRED_FIELDS - set(row.keys())
            assert not missing, (
                f"Row {rid}: missing fields {sorted(missing)}"
            )

    def test_all_reader_ids_are_unique(self) -> None:
        fixture = _load_fixture()
        ids = [r["reader_id"] for r in fixture["rows"]]
        assert len(ids) == len(set(ids)), (
            f"Duplicate reader IDs: "
            f"{[i for i in ids if ids.count(i) > 1]}"
        )

    def test_all_reader_paths_are_unique(self) -> None:
        fixture = _load_fixture()
        paths = [r["reader_path"] for r in fixture["rows"]]
        assert len(paths) == len(set(paths)), (
            f"Duplicate reader paths: "
            f"{[p for p in paths if paths.count(p) > 1]}"
        )

    def test_all_critical_fields_are_non_empty(self) -> None:
        fixture = _load_fixture()
        critical_fields = {
            "reader_id", "reader_path", "reader_category",
            "owner", "current_contract", "target_contract",
            "boundary_conditions", "fail_closed", "proof",
            "rollback_policy", "mixed_version_policy", "retirement_gate",
        }
        for row in fixture["rows"]:
            rid = row.get("reader_id", "?")
            for field in critical_fields:
                value = row.get(field)
                assert value, (
                    f"Row {rid}: {field} is empty or missing"
                )

    def test_all_rows_have_evidence_ref(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["evidence_ref"], (
                f"Row {row['reader_id']}: evidence_ref is empty"
            )

    def test_surface_types_is_list(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert isinstance(row["surface_types"], list), (
                f"Row {row['reader_id']}: surface_types is not a list"
            )


# ── ownership tests ────────────────────────────────────────────────────────


class TestReaderOwnershipDistribution:
    """Sanity checks on the ownership distribution."""

    def test_all_owners_are_valid(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["owner"] in VALID_OWNERS, (
                f"Row {row['reader_id']}: unknown owner "
                f"'{row['owner']}'"
            )

    def test_historical_readers_owned_by_wbc(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            if row["reader_category"] == "historical_reader":
                assert row["owner"] == "WBC", (
                    f"Historical reader {row['reader_id']} has owner "
                    f"'{row['owner']}', expected WBC"
                )


# ── hash stability tests ───────────────────────────────────────────────────


class TestReaderHashStability:
    """Row and composite hashes must be stable and verifiable."""

    def test_all_row_hashes_are_valid_sha256(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            h = row["row_hash"]
            assert len(h) == 64, (
                f"Row {row['reader_id']}: hash length {len(h)} != 64"
            )
            assert all(c in "0123456789abcdef" for c in h), (
                f"Row {row['reader_id']}: hash is not hex"
            )

    def test_row_hashes_match_computed(self) -> None:
        """Each row's stored hash must match the computed hash."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            computed = _compute_row_hash(row)
            stored = row["row_hash"]
            assert computed == stored, (
                f"Row {row['reader_id']}: stored hash {stored[:12]}... "
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
        artifact1 = _gen.generate_reader_registry(output_path=None)
        artifact2 = _gen.generate_reader_registry(output_path=None)

        assert artifact1["composite_hash"] == artifact2["composite_hash"], (
            "Composite hash changed between regeneration runs"
        )

        rows1 = {r["reader_id"]: r for r in artifact1["rows"]}
        rows2 = {r["reader_id"]: r for r in artifact2["rows"]}
        assert rows1.keys() == rows2.keys()

        for rid in sorted(rows1.keys()):
            assert rows1[rid]["row_hash"] == rows2[rid]["row_hash"], (
                f"Row {rid}: hash changed between runs"
            )
            for field in REQUIRED_FIELDS - {"row_hash"}:
                assert rows1[rid][field] == rows2[rid][field], (
                    f"Row {rid}: field {field} changed between runs"
                )

    def test_row_hashes_exclude_hash_field(self) -> None:
        """Row hash must be computed excluding the row_hash field."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            original_hash = row["row_hash"]
            row["row_hash"] = "0" * 64
            recomputed = _compute_row_hash(row)
            assert recomputed == original_hash, (
                f"Row {row['reader_id']}: hash computation is not "
                f"independent of the row_hash field"
            )


# ── North Star guard tests ─────────────────────────────────────────────────


class TestNorthStarGuard:
    """Projections, liveness, status snapshots, and support labels
    CANNOT be positive authority."""

    def test_projection_readers_not_authority(self) -> None:
        """Every projection reader must have is_authority=false."""
        fixture = _load_fixture()
        projection_rows = [
            r for r in fixture["rows"]
            if r["reader_category"] == "projection"
        ]
        assert len(projection_rows) > 0, "No projection readers found"
        for r in projection_rows:
            assert not r.get("is_authority", True), (
                f"NORTH STAR VIOLATION: Projection reader "
                f"{r['reader_id']} has is_authority=true"
            )

    def test_liveness_surfaces_not_authority(self) -> None:
        """Every reader with liveness surface must have is_authority=false."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            sts = set(row.get("surface_types", []))
            if "liveness" in sts:
                assert not row.get("is_authority", True), (
                    f"NORTH STAR VIOLATION: Liveness reader "
                    f"{row['reader_id']} has is_authority=true. "
                    f"Liveness cannot be positive authority."
                )

    def test_status_snapshot_surfaces_not_authority(self) -> None:
        """Every reader with status_snapshot surface must have
        is_authority=false."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            sts = set(row.get("surface_types", []))
            if "status_snapshot" in sts:
                assert not row.get("is_authority", True), (
                    f"NORTH STAR VIOLATION: Status snapshot reader "
                    f"{row['reader_id']} has is_authority=true. "
                    f"Status snapshots cannot be positive authority."
                )

    def test_support_label_surfaces_not_authority(self) -> None:
        """Every reader with support_label surface must have
        is_authority=false."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            sts = set(row.get("surface_types", []))
            if "support_label" in sts:
                assert not row.get("is_authority", True), (
                    f"NORTH STAR VIOLATION: Support label reader "
                    f"{row['reader_id']} has is_authority=true. "
                    f"Support labels cannot be positive authority."
                )

    def test_non_authoritative_count_matches_actual(self) -> None:
        """Declared non_authoritative_count must match actual count of
        is_authority=false rows."""
        fixture = _load_fixture()
        declared = fixture["non_authoritative_count"]
        actual = sum(
            1 for r in fixture["rows"]
            if not r.get("is_authority", True)
        )
        assert declared == actual, (
            f"non_authoritative_count mismatch: "
            f"declared={declared}, actual={actual}"
        )

    def test_non_authoritative_ids_list_matches(self) -> None:
        """Every reader in non_authoritative_reader_ids must have
        is_authority=false."""
        fixture = _load_fixture()
        non_auth_ids = set(fixture["non_authoritative_reader_ids"])
        by_id = {r["reader_id"]: r for r in fixture["rows"]}
        for rid in non_auth_ids:
            assert rid in by_id, f"{rid} in non_authoritative_ids but not in rows"
            assert not by_id[rid].get("is_authority", True), (
                f"{rid} is in non_authoritative_reader_ids but has is_authority=true"
            )

    def test_authority_readers_route_coverage(self) -> None:
        """At least 27 authority_readers.py routes must be in the registry."""
        fixture = _load_fixture()
        route_readers = [
            r for r in fixture["rows"]
            if "authority_readers.py::" in r["reader_path"]
        ]
        assert len(route_readers) >= 27, (
            f"Expected at least 27 authority_readers.py routes, "
            f"got {len(route_readers)}"
        )

    def test_chained_01_enforced_reader_is_authority(self) -> None:
        """CHAIN-01 is the only enforced route; it must be is_authority=true."""
        fixture = _load_fixture()
        by_id = {r["reader_id"]: r for r in fixture["rows"]}
        chain_01_id = "reader.authority_readers.py::CHAIN_01"
        assert chain_01_id in by_id, f"{chain_01_id} not found in registry"
        chain_01 = by_id[chain_01_id]
        assert chain_01.get("is_authority", False), (
            f"CHAIN-01 (enforced) must be is_authority=true, "
            f"got {chain_01.get('is_authority')}"
        )
        assert "enforced_reader" in chain_01.get("surface_types", []), (
            "CHAIN-01 must have enforced_reader surface type"
        )

    def test_all_non_enforced_routes_are_not_authority(self) -> None:
        """All warn-only/shadow-only/informational/deferred routes
        must have is_authority=false."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            if "authority_readers.py::" not in row["reader_path"]:
                continue
            disposition = row.get("disposition", "")
            if disposition == "enforced":
                continue
            assert not row.get("is_authority", True), (
                f"Route {row['reader_id']} has disposition "
                f"'{disposition}' but is_authority=true. "
                f"Only enforced readers can be authority."
            )

    def test_projections_from_inventory_are_non_authoritative(self) -> None:
        """Every projection surface from the WBC inventory must be
        non-authoritative."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            if row["reader_category"] == "projection":
                assert not row.get("is_authority", True), (
                    f"Projection {row['reader_id']} has is_authority=true"
                )
                assert "non_authoritative_read" in row.get("surface_types", []), (
                    f"Projection {row['reader_id']} missing "
                    f"non_authoritative_read surface type"
                )


# ── fail-closed tests ──────────────────────────────────────────────────────


class TestReaderFailClosedDefault:
    """Every reader must default to fail-closed behavior."""

    def test_fail_closed_is_deny(self) -> None:
        fixture = _load_fixture()
        deny_keywords = {"reject", "block", "denied", "error", "abort", "fail", "unknown", "deny"}
        for row in fixture["rows"]:
            fc_lower = row["fail_closed"].lower()
            has_deny = any(kw in fc_lower for kw in deny_keywords)
            assert has_deny, (
                f"Row {row['reader_id']}: fail_closed does not describe "
                f"a deny/block/error behavior: '{row['fail_closed'][:80]}...'"
            )

    def test_rollback_does_not_restore_dual_authority(self) -> None:
        fixture = _load_fixture()
        no_dual_keywords = {
            "never restore", "no direct", "no dual", "without restoring",
            "disable", "no legacy", "remove",
        }
        for row in fixture["rows"]:
            rp = row["rollback_policy"].lower()
            has_safe = any(kw in rp for kw in no_dual_keywords)
            assert has_safe, (
                f"Row {row['reader_id']}: rollback_policy may restore "
                f"dual authority: '{row['rollback_policy'][:80]}...'"
            )


# ── deterministic ordering test ────────────────────────────────────────────


class TestReaderDeterministicOrdering:
    """The registry must be deterministically ordered."""

    def test_rows_sorted_by_category_then_path(self) -> None:
        fixture = _load_fixture()
        categories_in_order = [
            r["reader_category"] + "/" + r["reader_path"]
            for r in fixture["rows"]
        ]
        assert categories_in_order == sorted(categories_in_order), (
            "Rows not deterministically sorted"
        )

    def test_no_duplicate_rows(self) -> None:
        fixture = _load_fixture()
        ids = [r["reader_id"] for r in fixture["rows"]]
        assert len(ids) == len(set(ids))


# ── specific reader tests ──────────────────────────────────────────────────


class TestSpecificReaders:
    """Verify that key known readers are present with correct metadata."""

    def test_authority_readers_module_is_registered(self) -> None:
        fixture = _load_fixture()
        by_id = {r["reader_id"]: r for r in fixture["rows"]}
        wid = "reader.arnold_pipelines.megaplan.orchestration.authority_readers"
        assert wid in by_id, "authority_readers.py not in registry"
        w = by_id[wid]
        assert "authority_reader" in w["surface_types"]
        assert w["owner"] == "Run Authority"

    def test_advisory_projection_is_registered_as_non_authority(self) -> None:
        fixture = _load_fixture()
        by_id = {r["reader_id"]: r for r in fixture["rows"]}
        wid = "reader.arnold_pipelines.megaplan.orchestration.advisory_projection"
        assert wid in by_id, "advisory_projection.py not in registry"
        w = by_id[wid]
        assert w["reader_category"] == "projection"
        assert not w.get("is_authority", True), (
            "advisory_projection must be is_authority=false"
        )
        assert "non_authoritative_read" in w["surface_types"]
        assert "projection" in w["surface_types"]

    def test_accepted_attempt_projection_is_registered_as_non_authority(self) -> None:
        fixture = _load_fixture()
        by_id = {r["reader_id"]: r for r in fixture["rows"]}
        wid = "reader.arnold_pipelines.megaplan.orchestration.authority_readers.py::AcceptedAttemptProjection"
        assert wid in by_id, "AcceptedAttemptProjection not in registry"
        w = by_id[wid]
        assert w["reader_category"] == "projection"
        assert not w.get("is_authority", True), (
            "AcceptedAttemptProjection must be is_authority=false"
        )

    def test_watchdog_is_registered_as_non_authority(self) -> None:
        fixture = _load_fixture()
        by_id = {r["reader_id"]: r for r in fixture["rows"]}
        wid = "reader.arnold_pipelines.megaplan.cloud.watchdog"
        assert wid in by_id, "watchdog.py not in registry"
        w = by_id[wid]
        assert w["reader_category"] == "cloud_status_watchdog"
        # watchdog may or may not be non-authoritative depending on classification
        # but if it has liveness surface, it must be non-authoritative
        if "liveness" in w.get("surface_types", []):
            assert not w.get("is_authority", True)

    def test_liveness_is_registered_as_non_authority(self) -> None:
        fixture = _load_fixture()
        by_id = {r["reader_id"]: r for r in fixture["rows"]}
        wid = "reader.arnold_pipelines.megaplan.observability.liveness"
        assert wid in by_id, "liveness.py not in registry"
        w = by_id[wid]
        assert not w.get("is_authority", True), (
            "liveness must be is_authority=false"
        )

    def test_status_snapshot_is_registered_as_non_authority(self) -> None:
        fixture = _load_fixture()
        by_id = {r["reader_id"]: r for r in fixture["rows"]}
        wid = "reader.arnold_pipelines.megaplan.cloud.status_snapshot"
        assert wid in by_id, "status_snapshot.py not in registry"
        w = by_id[wid]
        assert not w.get("is_authority", True), (
            "status_snapshot must be is_authority=false"
        )

    def test_historical_readers_are_registered(self) -> None:
        fixture = _load_fixture()
        historical = [
            r for r in fixture["rows"]
            if r["reader_category"] == "historical_reader"
        ]
        assert len(historical) >= 7, (
            f"Expected at least 7 historical readers, got {len(historical)}"
        )
        for h in historical:
            assert h["owner"] == "WBC"

    def test_shell_readers_are_registered(self) -> None:
        fixture = _load_fixture()
        shell = [
            r for r in fixture["rows"]
            if r["reader_category"] == "shell_wrapper"
        ]
        assert len(shell) >= 3, (
            f"Expected at least 3 shell readers, got {len(shell)}"
        )

    def test_compatibility_readers_are_registered(self) -> None:
        fixture = _load_fixture()
        compat = [
            r for r in fixture["rows"]
            if r["reader_category"] == "compatibility"
        ]
        assert len(compat) >= 1, (
            f"Expected at least 1 compatibility reader, got {len(compat)}"
        )


# ── generator properties ──────────────────────────────────────────────────


class TestGeneratorProperties:
    """Verify generator-level invariants."""

    def test_generator_is_read_only(self) -> None:
        """The generator must not mutate the WBC inventory."""
        inv_path = REPO_ROOT / "evidence" / "wbc-boundary-inventory.json"
        assert inv_path.exists(), "WBC inventory missing"

        before = inv_path.read_text(encoding="utf-8")
        _gen.generate_reader_registry(output_path=None)
        after = inv_path.read_text(encoding="utf-8")

        assert before == after, (
            "Generator mutated the WBC inventory — this is a read-only violation"
        )

    def test_registry_rows_is_not_empty(self) -> None:
        fixture = _load_fixture()
        assert len(fixture["rows"]) > 0

    def test_reader_count_matches_category_counts(self) -> None:
        fixture = _load_fixture()
        total = sum(fixture["category_counts"].values())
        assert total == fixture["reader_count"], (
            f"category_counts sum ({total}) != reader_count "
            f"({fixture['reader_count']})"
        )
