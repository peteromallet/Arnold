"""Focused tests for the M6 finding-prevention register (T10 — Step 9).

Covers:
- Exact F01-F17 coverage (exactly 17 rows, no missing, no duplicates)
- Every row has all required fields (owner, control, proof, rollout gate,
  rollback behavior, deletion gate, evidence references, row hash)
- Stable row hashes across regeneration
- Composite hash stability
- Schema validation
- Ownership distribution sanity
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
        "generate_m6_finding_register",
        str(REPO_ROOT / "tools" / "generate_m6_finding_register.py"),
    )
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_gen = _import_generator()

FIXTURE_PATH = REPO_ROOT / "evidence" / "finding-prevention-register.json"
SCHEMA = "m6.finding-prevention-register.v1"

EXPECTED_FINDING_IDS = {f"F{i:02d}" for i in range(1, 18)}

REQUIRED_FIELDS = {
    "finding_id",
    "title",
    "root_cause",
    "canonical_owner",
    "owner_control",
    "acceptance_proof",
    "rollout_gate",
    "rollback_behavior",
    "deletion_gate",
    "evidence_references",
    "row_hash",
}

KNOWN_OWNERS = {
    "Run Authority",
    "WBC",
    "TransitionWriter/repair custody",
    "Megaplan Maintenance",
    "Planner/compiler",
    "Executor/launcher",
    "Observability/projection",
}

# ── helpers ────────────────────────────────────────────────────────────────


def _load_fixture() -> dict[str, Any]:
    """Load the fixture artifact, skipping if not found."""
    if not FIXTURE_PATH.exists():
        pytest.skip("Finding prevention register not yet generated")
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


class TestFindingRegisterSchema:
    """Validate the top-level structure of the register artifact."""

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
        assert len(fixture["composite_hash"]) == 64  # SHA-256 hex

    def test_has_expected_coverage(self) -> None:
        fixture = _load_fixture()
        assert "expected_coverage" in fixture
        assert "F01" in fixture["expected_coverage"]
        assert "F17" in fixture["expected_coverage"]

    def test_has_finding_count(self) -> None:
        fixture = _load_fixture()
        assert fixture["finding_count"] == 17

    def test_has_generator(self) -> None:
        fixture = _load_fixture()
        assert "generator" in fixture
        assert "generate_m6_finding_register" in fixture["generator"]

    def test_has_source_document(self) -> None:
        fixture = _load_fixture()
        assert "source_document" in fixture
        assert "unified-authority-efficiency-prevention" in fixture["source_document"]

    def test_rows_is_list(self) -> None:
        fixture = _load_fixture()
        assert isinstance(fixture["rows"], list)


# ── coverage tests ─────────────────────────────────────────────────────────


class TestExactCoverage:
    """Verify exactly F01-F17 with no omissions or duplicates."""

    def test_exactly_17_rows(self) -> None:
        fixture = _load_fixture()
        assert len(fixture["rows"]) == 17, (
            f"Expected 17 rows, got {len(fixture['rows'])}"
        )

    def test_all_finding_ids_present(self) -> None:
        fixture = _load_fixture()
        row_ids = {r["finding_id"] for r in fixture["rows"]}
        assert row_ids == EXPECTED_FINDING_IDS, (
            f"Missing: {sorted(EXPECTED_FINDING_IDS - row_ids)}, "
            f"Extra: {sorted(row_ids - EXPECTED_FINDING_IDS)}"
        )

    def test_no_duplicate_finding_ids(self) -> None:
        fixture = _load_fixture()
        ids = [r["finding_id"] for r in fixture["rows"]]
        assert len(ids) == len(set(ids)), (
            f"Duplicate finding IDs: {[i for i in ids if ids.count(i) > 1]}"
        )

    def test_rows_sorted_by_finding_id(self) -> None:
        fixture = _load_fixture()
        ids = [r["finding_id"] for r in fixture["rows"]]
        assert ids == sorted(ids), f"Rows not sorted: {ids}"


# ── field completeness tests ───────────────────────────────────────────────


class TestRequiredFields:
    """Every row must have all required fields with non-empty values."""

    def test_all_rows_have_required_fields(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            fid = row.get("finding_id", "?")
            missing = REQUIRED_FIELDS - set(row.keys())
            assert not missing, (
                f"Row {fid}: missing fields {sorted(missing)}"
            )

    def test_all_fields_are_non_empty(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            fid = row.get("finding_id", "?")
            for field in REQUIRED_FIELDS:
                value = row.get(field)
                # evidence_references can be empty list
                if field == "evidence_references":
                    assert isinstance(value, list), (
                        f"Row {fid}: {field} is not a list"
                    )
                else:
                    assert value, (
                        f"Row {fid}: {field} is empty or missing"
                    )

    def test_every_row_has_title(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["title"], f"Row {row['finding_id']}: title is empty"

    def test_every_row_has_root_cause(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["root_cause"], (
                f"Row {row['finding_id']}: root_cause is empty"
            )

    def test_every_row_has_owner_control(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["owner_control"], (
                f"Row {row['finding_id']}: owner_control is empty"
            )

    def test_every_row_has_acceptance_proof(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["acceptance_proof"], (
                f"Row {row['finding_id']}: acceptance_proof is empty"
            )

    def test_every_row_has_rollout_gate(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["rollout_gate"], (
                f"Row {row['finding_id']}: rollout_gate is empty"
            )

    def test_every_row_has_deletion_gate(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["deletion_gate"], (
                f"Row {row['finding_id']}: deletion_gate is empty"
            )
            assert row["deletion_gate"] != "UNKNOWN", (
                f"Row {row['finding_id']}: deletion_gate is UNKNOWN"
            )

    def test_every_row_has_evidence_references(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            refs = row["evidence_references"]
            assert isinstance(refs, list), (
                f"Row {row['finding_id']}: evidence_references is not a list"
            )
            assert len(refs) >= 1, (
                f"Row {row['finding_id']}: evidence_references is empty"
            )
            assert "unified-authority-efficiency-prevention" in refs[0], (
                f"Row {row['finding_id']}: evidence_references missing "
                f"unified synthesis reference"
            )


# ── hash stability tests ───────────────────────────────────────────────────


class TestHashStability:
    """Row and composite hashes must be stable and verifiable."""

    def test_all_row_hashes_are_valid_sha256(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            h = row["row_hash"]
            assert len(h) == 64, (
                f"Row {row['finding_id']}: hash length {len(h)} != 64"
            )
            assert all(c in "0123456789abcdef" for c in h), (
                f"Row {row['finding_id']}: hash is not hex"
            )

    def test_row_hashes_match_computed(self) -> None:
        """Each row's stored hash must match the computed hash."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            computed = _compute_row_hash(row)
            stored = row["row_hash"]
            assert computed == stored, (
                f"Row {row['finding_id']}: stored hash {stored[:12]}... "
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
        # Generate once
        artifact1 = _gen.generate_register(output_path=None)

        # Generate again
        artifact2 = _gen.generate_register(output_path=None)

        # Compare composite hashes (ignore generated_at timestamp)
        assert artifact1["composite_hash"] == artifact2["composite_hash"], (
            "Composite hash changed between regeneration runs"
        )

        # Compare each row hash
        rows1 = {r["finding_id"]: r for r in artifact1["rows"]}
        rows2 = {r["finding_id"]: r for r in artifact2["rows"]}
        assert rows1.keys() == rows2.keys()

        for fid in sorted(rows1.keys()):
            assert rows1[fid]["row_hash"] == rows2[fid]["row_hash"], (
                f"Row {fid}: hash changed between runs"
            )

            # Also verify all non-hash fields match
            for field in REQUIRED_FIELDS - {"row_hash"}:
                assert rows1[fid][field] == rows2[fid][field], (
                    f"Row {fid}: field {field} changed between runs"
                )

    def test_row_hashes_exclude_hash_field(self) -> None:
        """Row hash must be computed from the row content excluding
        the row_hash field itself — verified by checking that changing
        the hash doesn't change the computed hash."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            original_hash = row["row_hash"]
            # Modify only the hash field
            row["row_hash"] = "0" * 64
            recomputed = _compute_row_hash(row)
            # Recompute should give the same hash (since it ignores row_hash)
            assert recomputed == original_hash, (
                f"Row {row['finding_id']}: hash computation is not "
                f"independent of the row_hash field"
            )


# ── ownership tests ────────────────────────────────────────────────────────


class TestOwnershipDistribution:
    """Sanity checks on the ownership distribution across F01-F17."""

    def test_all_owners_are_known(self) -> None:
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["canonical_owner"] in KNOWN_OWNERS, (
                f"Row {row['finding_id']}: unknown canonical_owner "
                f"'{row['canonical_owner']}'"
            )

    def test_ownership_covers_all_findings(self) -> None:
        """Every finding must have a non-UNKNOWN owner."""
        fixture = _load_fixture()
        for row in fixture["rows"]:
            assert row["canonical_owner"] != "UNKNOWN", (
                f"Row {row['finding_id']}: canonical_owner is UNKNOWN"
            )

    def test_expected_run_authority_findings(self) -> None:
        """F01 and F05 are Run Authority owned."""
        fixture = _load_fixture()
        by_id = {r["finding_id"]: r for r in fixture["rows"]}
        assert by_id["F01"]["canonical_owner"] == "Run Authority"
        assert by_id["F05"]["canonical_owner"] == "Run Authority"

    def test_expected_wbc_findings(self) -> None:
        """F02, F03, F04, F17 are WBC owned."""
        fixture = _load_fixture()
        by_id = {r["finding_id"]: r for r in fixture["rows"]}
        for fid in ["F02", "F03", "F04", "F17"]:
            assert by_id[fid]["canonical_owner"] == "WBC", (
                f"{fid}: expected WBC, got {by_id[fid]['canonical_owner']}"
            )

    def test_expected_planner_findings(self) -> None:
        """F07, F08, F09, F12 are Planner/compiler owned."""
        fixture = _load_fixture()
        by_id = {r["finding_id"]: r for r in fixture["rows"]}
        for fid in ["F07", "F08", "F09", "F12"]:
            assert by_id[fid]["canonical_owner"] == "Planner/compiler", (
                f"{fid}: expected Planner/compiler, "
                f"got {by_id[fid]['canonical_owner']}"
            )

    def test_expected_executor_findings(self) -> None:
        """F10, F11, F13 are Executor/launcher owned."""
        fixture = _load_fixture()
        by_id = {r["finding_id"]: r for r in fixture["rows"]}
        for fid in ["F10", "F11", "F13"]:
            assert by_id[fid]["canonical_owner"] == "Executor/launcher", (
                f"{fid}: expected Executor/launcher, "
                f"got {by_id[fid]['canonical_owner']}"
            )

    def test_expected_observability_findings(self) -> None:
        """F06, F14, F16 are Observability/projection owned."""
        fixture = _load_fixture()
        by_id = {r["finding_id"]: r for r in fixture["rows"]}
        for fid in ["F06", "F14", "F16"]:
            assert by_id[fid]["canonical_owner"] == "Observability/projection", (
                f"{fid}: expected Observability/projection, "
                f"got {by_id[fid]['canonical_owner']}"
            )

    def test_expected_repair_custody_finding(self) -> None:
        """F15 is TransitionWriter/repair custody owned."""
        fixture = _load_fixture()
        by_id = {r["finding_id"]: r for r in fixture["rows"]}
        assert (
            by_id["F15"]["canonical_owner"] == "TransitionWriter/repair custody"
        ), (
            f"F15: expected TransitionWriter/repair custody, "
            f"got {by_id['F15']['canonical_owner']}"
        )


# ── ordering test ──────────────────────────────────────────────────────────


class TestDeterministicOrdering:
    """The register must be deterministically ordered."""

    def test_rows_are_f01_to_f17_in_order(self) -> None:
        fixture = _load_fixture()
        ids = [r["finding_id"] for r in fixture["rows"]]
        expected = [f"F{i:02d}" for i in range(1, 18)]
        assert ids == expected, (
            f"Row order: expected F01..F17, got {ids}"
        )


# ── specific finding content tests ─────────────────────────────────────────


class TestSpecificFindingContent:
    """Verify specific known content in key findings."""

    def test_f01_stale_repair_identity(self) -> None:
        fixture = _load_fixture()
        by_id = {r["finding_id"]: r for r in fixture["rows"]}
        f01 = by_id["F01"]
        assert "stale repair identity" in f01["title"].lower()
        assert "Run Authority" in f01["owner_control"]
        assert "M7" in f01["acceptance_proof"] or "M10" in f01["acceptance_proof"]

    def test_f02_scan_driven_recovery(self) -> None:
        fixture = _load_fixture()
        by_id = {r["finding_id"]: r for r in fixture["rows"]}
        f02 = by_id["F02"]
        assert "scan" in f02["title"].lower()
        assert "WBC" in f02["owner_control"]

    def test_f17_mixed_provenance(self) -> None:
        fixture = _load_fixture()
        by_id = {r["finding_id"]: r for r in fixture["rows"]}
        f17 = by_id["F17"]
        assert "version" in f17["title"].lower() or "provenance" in f17["title"].lower()
        assert "WBC" in f17["owner_control"]
        assert "Run Authority" in f17["owner_control"]


# ── generator properties ───────────────────────────────────────────────────


class TestGeneratorProperties:
    """Verify generator-level invariants."""

    def test_generator_is_read_only(self) -> None:
        """The generator module must not mutate any filesystem state
        beyond writing its output artifact."""
        # This is verified by design — the generator only reads files
        # and writes to its output path.  We test by running it and
        # checking that the research document is unchanged.
        research_path = REPO_ROOT / (
            ".megaplan/initiatives/custody-control-plane/research/"
            "unified-authority-efficiency-prevention-20260714.md"
        )
        assert research_path.exists(), "Research document missing"

        before = research_path.read_text(encoding="utf-8")

        # Run the generator
        _gen.generate_register(output_path=None)

        after = research_path.read_text(encoding="utf-8")
        assert before == after, (
            "Generator mutated the research document"
        )

    def test_parse_findings_returns_17(self) -> None:
        """The parser must extract exactly 17 findings from the document."""
        research_path = REPO_ROOT / (
            ".megaplan/initiatives/custody-control-plane/research/"
            "unified-authority-efficiency-prevention-20260714.md"
        )
        doc_text = research_path.read_text(encoding="utf-8")
        findings = _gen._parse_findings(doc_text)
        assert len(findings) == 17, (
            f"Parser returned {len(findings)} findings, expected 17"
        )

    def test_compute_row_hash_deterministic(self) -> None:
        """_compute_row_hash must produce the same hash for the same input."""
        row = {
            "finding_id": "F01",
            "title": "Test",
            "root_cause": "Something",
            "canonical_owner": "Run Authority",
            "owner_control": "Run Authority defines",
            "acceptance_proof": "M7",
            "rollout_gate": "shadow",
            "rollback_behavior": "fail closed",
            "deletion_gate": "after proof",
            "evidence_references": ["ref.md"],
        }
        h1 = _gen._compute_row_hash(row)
        h2 = _gen._compute_row_hash(row)
        assert h1 == h2, f"Hash not deterministic: {h1} != {h2}"

    def test_compute_row_hash_changes_with_content(self) -> None:
        """Different content must produce different hashes."""
        row1 = {
            "finding_id": "F01",
            "title": "Test A",
            "root_cause": "Something",
            "canonical_owner": "Run Authority",
            "owner_control": "Run Authority defines",
            "acceptance_proof": "M7",
            "rollout_gate": "shadow",
            "rollback_behavior": "fail closed",
            "deletion_gate": "after proof",
            "evidence_references": ["ref.md"],
        }
        row2 = {**row1, "title": "Test B"}
        h1 = _gen._compute_row_hash(row1)
        h2 = _gen._compute_row_hash(row2)
        assert h1 != h2, "Different content produced same hash"

    def test_compute_row_hash_ignores_row_hash_field(self) -> None:
        """The row_hash field must not affect the computed hash."""
        row = {
            "finding_id": "F01",
            "title": "Test",
            "root_cause": "Something",
            "canonical_owner": "Run Authority",
            "owner_control": "Run Authority defines",
            "acceptance_proof": "M7",
            "rollout_gate": "shadow",
            "rollback_behavior": "fail closed",
            "deletion_gate": "after proof",
            "evidence_references": ["ref.md"],
            "row_hash": "abc123",
        }
        h1 = _gen._compute_row_hash(row)
        row["row_hash"] = "xyz789"
        h2 = _gen._compute_row_hash(row)
        assert h1 == h2, "Row hash affected computed hash"
