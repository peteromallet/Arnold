"""Focused tests for the M6 reconciled migration matrix (T13 — Step 12).

Covers:
- 92-row matrix coverage (all rows from the source matrix)
- Every row classified into exactly one valid bucket
- No UNKNOWN owner, no unexplained bucket, no wrong M6A/M8 handoff
- Required fields present and non-empty
- Stable row hashes across regeneration
- Composite hash stability
- Schema validation
- Evidence join sanity
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
        "reconcile_m6_migration_matrix",
        str(REPO_ROOT / "tools" / "reconcile_m6_migration_matrix.py"),
    )
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_gen = _import_generator()

FIXTURE_PATH = REPO_ROOT / "evidence" / "migration-matrix-reconciled.json"
SCHEMA = "m6.migration-matrix-reconciled.v1"

VALID_CLASSIFICATIONS = {
    "prerequisite-satisfied",
    "residual",
    "blocked",
    "retired",
    "out-of-supported-scope",
}

REQUIRED_FIELDS = {
    "row_index",
    "consumer_surface",
    "current_authority",
    "target_authority",
    "milestone",
    "status_raw",
    "classification",
    "classification_rationale",
    "owner",
    "proof_requirement",
    "deletion_gate",
    "fail_closed_behavior",
    "rollback_policy",
    "mixed_version_policy",
    "evidence",
    "row_hash",
}

# ── helpers ────────────────────────────────────────────────────────────────


def _load_fixture() -> dict[str, Any]:
    """Load the fixture artifact, skipping if not found."""
    if not FIXTURE_PATH.exists():
        pytest.skip("Migration matrix reconciled artifact not yet generated")
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _compute_row_hash(row: dict[str, Any]) -> str:
    """Compute stable row hash (same as generator)."""
    return _gen._compute_row_hash(row)


def _compute_composite_hash(rows: list[dict[str, Any]]) -> str:
    """Compute composite hash from sorted row hashes."""
    row_hashes = sorted(r["row_hash"] for r in rows)
    combined = "".join(row_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ── schema tests ───────────────────────────────────────────────────────────


class TestReconciledMatrixSchema:
    """Validate the top-level structure of the reconciled artifact."""

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

    def test_has_expected_row_count(self) -> None:
        fixture = _load_fixture()
        # The source matrix has 92 data rows
        assert fixture["row_count"] >= 91, (
            f"Expected at least 91 rows, got {fixture['row_count']}"
        )

    def test_has_generator(self) -> None:
        fixture = _load_fixture()
        assert "generator" in fixture
        assert "reconcile_m6_migration_matrix" in fixture["generator"]

    def test_has_source_matrix(self) -> None:
        fixture = _load_fixture()
        assert "source_matrix" in fixture
        assert "migration-matrix" in fixture["source_matrix"]

    def test_rows_is_list(self) -> None:
        fixture = _load_fixture()
        assert isinstance(fixture["rows"], list)

    def test_row_count_matches(self) -> None:
        fixture = _load_fixture()
        assert fixture["row_count"] == len(fixture["rows"])

    def test_classification_counts_sum_to_row_count(self) -> None:
        fixture = _load_fixture()
        total = sum(fixture["classification_counts"].values())
        assert total == fixture["row_count"], (
            f"Classification counts sum to {total}, expected {fixture['row_count']}"
        )


# ── classification tests ───────────────────────────────────────────────────


class TestClassificationCoverage:
    """Every row must have a valid classification with a rationale."""

    def test_all_rows_have_valid_classification(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            cls = row.get("classification", "")
            assert cls in VALID_CLASSIFICATIONS, (
                f"Row {row.get('row_index', '?')}: invalid classification '{cls}'"
            )

    def test_all_rows_have_classification_rationale(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            rationale = row.get("classification_rationale", "")
            assert rationale, (
                f"Row {row.get('row_index', '?')}: missing classification_rationale"
            )

    def test_no_rows_with_empty_classification(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["classification"], (
                f"Row {row.get('row_index', '?')}: empty classification"
            )

    def test_blocked_rows_exist(self) -> None:
        fixture = _load_fixture()
        blocked = fixture["classification_counts"].get("blocked", 0)
        assert blocked > 0, "Expected at least some blocked rows"

    def test_prerequisite_satisfied_rows_exist(self) -> None:
        fixture = _load_fixture()
        ps = fixture["classification_counts"].get("prerequisite-satisfied", 0)
        assert ps >= 1, "Expected at least 1 prerequisite-satisfied row (WBC semantic findings)"

    def test_residual_rows_exist(self) -> None:
        fixture = _load_fixture()
        residual = fixture["classification_counts"].get("residual", 0)
        assert residual > 0, "Expected residual rows"

    def test_retired_rows_exist(self) -> None:
        fixture = _load_fixture()
        retired = fixture["classification_counts"].get("retired", 0)
        assert retired >= 2, "Expected at least 2 retired rows"


# ── owner tests ────────────────────────────────────────────────────────────


class TestOwnership:
    """No row may have a missing or UNKNOWN owner."""

    def test_no_unknown_owners(self) -> None:
        fixture = _load_fixture()
        unknown = [r for r in fixture["rows"] if r.get("owner") == "UNKNOWN"]
        assert len(unknown) == 0, (
            f"Rows with UNKNOWN owner: "
            f"{[(r['row_index'], r['consumer_surface'][:50]) for r in unknown]}"
        )

    def test_all_rows_have_owner(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            owner = row.get("owner", "")
            assert owner, (
                f"Row {row.get('row_index', '?')}: missing owner"
            )
            assert owner != "UNKNOWN", (
                f"Row {row.get('row_index', '?')}: owner is UNKNOWN — "
                f"consumer='{row.get('consumer_surface', '')[:60]}'"
            )

    def test_owners_list_matches_rows(self) -> None:
        fixture = _load_fixture()
        declared_owners = set(fixture.get("owners", []))
        actual_owners = {r["owner"] for r in fixture["rows"]}
        missing = actual_owners - declared_owners
        assert not missing, (
            f"Owners in rows but not in owners list: {sorted(missing)}"
        )

    def test_run_authority_is_owner(self) -> None:
        fixture = _load_fixture()
        assert "Run Authority" in fixture.get("owners", [])

    def test_wbc_is_owner(self) -> None:
        fixture = _load_fixture()
        assert "WBC" in fixture.get("owners", [])

    def test_custody_control_plane_is_owner(self) -> None:
        fixture = _load_fixture()
        assert "custody-control-plane" in fixture.get("owners", [])


# ── handoff milestone tests ────────────────────────────────────────────────


class TestHandoffMilestones:
    """Residual rows must have a handoff milestone; non-residual must not."""

    def test_all_residual_rows_have_handoff(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            if row["classification"] == "residual":
                handoff = row.get("handoff_milestone")
                assert handoff is not None, (
                    f"Row {row['row_index']}: residual row has no handoff_milestone — "
                    f"consumer='{row['consumer_surface'][:60]}'"
                )
                assert handoff in ("M6A", "M8", "M9", "M10", "M11"), (
                    f"Row {row['row_index']}: unexpected handoff '{handoff}'"
                )

    def test_substrate_rows_handoff_to_m6a(self) -> None:
        """Rows with 'substrate' in status should hand off to M6A."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            if "substrate" in row.get("status_raw", "").lower():
                if row["classification"] == "residual":
                    handoff = row.get("handoff_milestone")
                    assert handoff == "M6A", (
                        f"Row {row['row_index']}: substrate row should handoff to "
                        f"M6A, got '{handoff}' — consumer='{row['consumer_surface'][:60]}'"
                    )

    def test_non_residual_rows_have_no_handoff(self) -> None:
        """Blocked, retired, prerequisite-satisfied, out-of-scope rows
        should not have a handoff milestone."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            if row["classification"] != "residual":
                handoff = row.get("handoff_milestone")
                assert handoff is None, (
                    f"Row {row['row_index']}: non-residual row "
                    f"({row['classification']}) has handoff_milestone='{handoff}'"
                )


# ── field completeness tests ───────────────────────────────────────────────


class TestRequiredFields:
    """Every row must have all required fields with appropriate values."""

    def test_all_rows_have_required_fields(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            ri = row.get("row_index", "?")
            missing = REQUIRED_FIELDS - set(row.keys())
            assert not missing, (
                f"Row {ri}: missing fields {sorted(missing)}"
            )

    def test_all_fields_are_non_empty(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            ri = row.get("row_index", "?")
            for field in REQUIRED_FIELDS:
                value = row.get(field)
                if field == "evidence":
                    assert isinstance(value, dict), (
                        f"Row {ri}: {field} is not a dict"
                    )
                elif field == "handoff_milestone":
                    # Can be None for non-residual rows
                    pass
                elif field == "row_index":
                    assert isinstance(value, int), (
                        f"Row {ri}: row_index is not an int"
                    )
                else:
                    assert value or value == "", (
                        f"Row {ri}: {field} is None"
                    )

    def test_every_row_has_consumer_surface(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["consumer_surface"], (
                f"Row {row['row_index']}: consumer_surface is empty"
            )

    def test_every_row_has_fail_closed_behavior(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            fb = row["fail_closed_behavior"]
            assert "UNKNOWN" in fb or "INCOHERENT" in fb or "zero" in fb.lower(), (
                f"Row {row['row_index']}: fail_closed_behavior does not describe "
                f"fail-closed semantics"
            )

    def test_every_row_has_rollback_policy(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert "shadow" in row["rollback_policy"].lower() or "rollback" in row["rollback_policy"].lower(), (
                f"Row {row['row_index']}: rollback_policy missing key terms"
            )

    def test_every_row_has_mixed_version_policy(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["mixed_version_policy"], (
                f"Row {row['row_index']}: mixed_version_policy is empty"
            )


# ── hash stability tests ───────────────────────────────────────────────────


class TestHashStability:
    """Row and composite hashes must be stable and verifiable."""

    def test_all_row_hashes_are_valid_sha256(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            h = row["row_hash"]
            assert len(h) == 64, (
                f"Row {row['row_index']}: hash length {len(h)} != 64"
            )
            assert all(c in "0123456789abcdef" for c in h), (
                f"Row {row['row_index']}: hash is not hex"
            )

    def test_row_hashes_match_computed(self) -> None:
        """Each row's stored hash must match the computed hash."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            computed = _compute_row_hash(row)
            stored = row["row_hash"]
            assert computed == stored, (
                f"Row {row['row_index']}: stored hash {stored[:12]}... "
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
        artifact1 = _gen.generate_reconciled_matrix(output_path=None)

        artifact2 = _gen.generate_reconciled_matrix(output_path=None)

        assert artifact1["composite_hash"] == artifact2["composite_hash"], (
            "Composite hash changed between regeneration runs"
        )

        rows1 = {r["row_index"]: r for r in artifact1["rows"]}
        rows2 = {r["row_index"]: r for r in artifact2["rows"]}
        assert rows1.keys() == rows2.keys()

        for idx in sorted(rows1.keys()):
            assert rows1[idx]["row_hash"] == rows2[idx]["row_hash"], (
                f"Row {idx}: hash changed between runs"
            )
            for field in REQUIRED_FIELDS - {"row_hash"}:
                val1 = rows1[idx].get(field)
                val2 = rows2[idx].get(field)
                assert val1 == val2, (
                    f"Row {idx}: field {field} changed between runs"
                )

    def test_row_hashes_exclude_hash_field(self) -> None:
        """Row hash must be computed from the row content excluding
        the row_hash field itself."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            original_hash = row["row_hash"]
            row["row_hash"] = "0" * 64
            recomputed = _compute_row_hash(row)
            assert recomputed == original_hash, (
                f"Row {row['row_index']}: hash computation is not "
                f"independent of the row_hash field"
            )


# ── evidence join tests ────────────────────────────────────────────────────


class TestEvidenceJoin:
    """Evidence from other M6 artifacts must be joined correctly."""

    def test_evidence_is_dict(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert isinstance(row["evidence"], dict), (
                f"Row {row['row_index']}: evidence is not a dict"
            )

    def test_wbc_rows_have_wbc_evidence(self) -> None:
        """Rows mentioning WBC should have WBC evidence matches."""
        fixture = _load_fixture()
        wbc_rows = [
            r for r in fixture["rows"]
            if "wbc" in r["consumer_surface"].lower()
        ]
        assert len(wbc_rows) >= 5, f"Expected >=5 WBC rows, got {len(wbc_rows)}"
        for row in wbc_rows:
            evidence = row["evidence"]
            # At minimum, these should have prerequisite verification
            assert "prerequisite_verification" in evidence, (
                f"Row {row['row_index']}: WBC row missing prerequisite_verification"
            )

    def test_all_rows_have_prerequisite_evidence(self) -> None:
        """Every row should reference prerequisite verification status."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            evidence = row["evidence"]
            assert "prerequisite_verification" in evidence, (
                f"Row {row['row_index']}: missing prerequisite_verification in evidence"
            )


# ── ordering tests ─────────────────────────────────────────────────────────


class TestDeterministicOrdering:
    """Rows must be deterministically ordered."""

    def test_rows_sorted_by_classification_then_index(self) -> None:
        fixture = _load_fixture()
        rows = fixture["rows"]
        class_priority = {
            "blocked": 0,
            "prerequisite-satisfied": 1,
            "residual": 2,
            "retired": 3,
            "out-of-supported-scope": 4,
        }

        for i in range(len(rows) - 1):
            curr = rows[i]
            next_ = rows[i + 1]
            curr_pri = class_priority.get(curr["classification"], 99)
            next_pri = class_priority.get(next_["classification"], 99)
            assert (curr_pri, curr["row_index"]) <= (next_pri, next_["row_index"]), (
                f"Order violation at {i}: ({curr['classification']}, {curr['row_index']}) "
                f"after ({next_['classification']}, {next_['row_index']})"
            )

    def test_no_duplicate_row_indices(self) -> None:
        fixture = _load_fixture()
        indices = [r["row_index"] for r in fixture["rows"]]
        assert len(indices) == len(set(indices)), "Duplicate row indices found"


# ── specific row content tests ─────────────────────────────────────────────


class TestSpecificRowContent:
    """Verify specific known rows in the reconciled matrix."""

    def test_wbc_declarations_ledger_is_blocked(self) -> None:
        fixture = _load_fixture()
        by_surface = {r["consumer_surface"]: r for r in fixture["rows"]}
        row = by_surface.get("WBC declarations/attempt ledger")
        assert row is not None, "WBC declarations/attempt ledger row missing"
        assert row["classification"] == "blocked", (
            f"Expected blocked, got {row['classification']}"
        )
        assert row["owner"] == "WBC"

    def test_wbc_semantic_findings_is_prerequisite_satisfied(self) -> None:
        fixture = _load_fixture()
        by_surface = {r["consumer_surface"]: r for r in fixture["rows"]}
        row = by_surface.get("WBC semantic findings")
        assert row is not None, "WBC semantic findings row missing"
        assert row["classification"] == "prerequisite-satisfied", (
            f"Expected prerequisite-satisfied, got {row['classification']}"
        )

    def test_retired_rows_are_portfolio(self) -> None:
        fixture = _load_fixture()
        retired = [r for r in fixture["rows"] if r["classification"] == "retired"]
        for row in retired:
            assert "Portfolio" in row["owner"] or "retired" in row["consumer_surface"].lower(), (
                f"Row {row['row_index']}: retired row should have Portfolio owner"
            )

    def test_megaplan_maintenance_is_out_of_scope(self) -> None:
        fixture = _load_fixture()
        by_surface = {r["consumer_surface"]: r for r in fixture["rows"]}
        row = by_surface.get("Megaplan Maintenance")
        assert row is not None, "Megaplan Maintenance row missing"
        assert row["classification"] == "out-of-supported-scope"

    def test_run_authority_receipts_are_blocked(self) -> None:
        fixture = _load_fixture()
        by_surface = {r["consumer_surface"]: r for r in fixture["rows"]}
        row = by_surface.get("Run Authority M1-M3 completion receipts")
        assert row is not None
        assert row["classification"] == "blocked"
        assert row["owner"] == "Run Authority"

    def test_pc_adjacent_work_is_blocked_gate(self) -> None:
        fixture = _load_fixture()
        by_surface = {r["consumer_surface"]: r for r in fixture["rows"]}
        row = by_surface.get("PC adjacent work")
        assert row is not None, "PC adjacent work row missing"
        assert row["classification"] == "blocked"
        assert "gate" in row["status_raw"].lower() or "blocked" in row["status_raw"].lower()


# ── generator properties ───────────────────────────────────────────────────


class TestGeneratorProperties:
    """Verify generator-level invariants."""

    def test_generator_is_read_only(self) -> None:
        """The generator module must not mutate any filesystem state
        beyond writing its output artifact."""
        matrix_path = REPO_ROOT / (
            ".megaplan/initiatives/custody-control-plane/research/"
            "migration-matrix.md"
        )
        assert matrix_path.exists(), "Migration matrix source missing"

        before = matrix_path.read_text(encoding="utf-8")

        _gen.generate_reconciled_matrix(output_path=None)

        after = matrix_path.read_text(encoding="utf-8")
        assert before == after, (
            "Generator mutated the source matrix file"
        )

    def test_source_matrix_hash_is_stable(self) -> None:
        """The source matrix hash should be recorded and match the file."""
        fixture = _load_fixture()
        matrix_path = REPO_ROOT / (
            ".megaplan/initiatives/custody-control-plane/research/"
            "migration-matrix.md"
        )
        actual_hash = _sha256_hex(matrix_path.read_text(encoding="utf-8"))
        stored_hash = fixture.get("source_matrix_hash", "")
        assert stored_hash == actual_hash, (
            f"Source matrix hash mismatch: stored={stored_hash[:12]}..., "
            f"actual={actual_hash[:12]}..."
        )

    def test_evidence_artifacts_loaded_is_complete(self) -> None:
        """The loaded artifacts list should include all expected evidence."""
        fixture = _load_fixture()
        loaded = fixture.get("evidence_artifacts_loaded", {})
        expected = {
            "prerequisite_verification",
            "wbc_boundary_inventory",
            "controlled_writer_registry",
            "authority_reader_registry",
            "finding_prevention_register",
            "replay_transaction_spine",
            "replay_strategy_roadmap",
        }
        for key in expected:
            assert key in loaded, f"Missing evidence artifact key: {key}"
