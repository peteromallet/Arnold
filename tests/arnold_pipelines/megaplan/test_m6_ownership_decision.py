"""Focused tests for the M6 ownership decision artifacts (T14 — Step 13).

Covers:
- PC scope decision schema validation
- Ownership decision record schema validation
- PC scope defaults to program_counter
- PC scope blocker encodes unresolved human approval
- Ownership record covers all required owners (Run Authority, WBC, TransitionWriter/repair custody)
- All global blockers have status=blocked (not accepted)
- Stable row hashes across regeneration
- Composite hash stability
- North Star guard: unresolved approval is blocker, not acceptance
- Every owner has surfaces, classification_counts match surfaces
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
        "generate_m6_ownership_decision",
        str(REPO_ROOT / "tools" / "generate_m6_ownership_decision.py"),
    )
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_gen = _import_generator()

PC_SCOPE_PATH = REPO_ROOT / "evidence" / "pc-scope-decision.json"
OWNERSHIP_PATH = REPO_ROOT / "evidence" / "ownership-decision-record.json"

PC_SCOPE_SCHEMA = "m6.pc-scope-decision.v1"
OWNERSHIP_SCHEMA = "m6.ownership-decision-record.v1"

REQUIRED_OWNERS = {
    "Run Authority",
    "WBC",
    "TransitionWriter/repair custody",
}


# ── helpers ────────────────────────────────────────────────────────────────


def _load_pc_scope() -> dict[str, Any]:
    if not PC_SCOPE_PATH.exists():
        pytest.skip("PC scope decision not yet generated")
    with open(PC_SCOPE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_ownership() -> dict[str, Any]:
    if not OWNERSHIP_PATH.exists():
        pytest.skip("Ownership decision record not yet generated")
    with open(OWNERSHIP_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── PC scope decision tests ────────────────────────────────────────────────


class TestPCScopeDecision:
    """Tests for evidence/pc-scope-decision.json"""

    def test_schema_matches(self) -> None:
        """Schema is m6.pc-scope-decision.v1"""
        data = _load_pc_scope()
        assert data["schema"] == PC_SCOPE_SCHEMA

    def test_default_interpretation_is_program_counter(self) -> None:
        """Default interpretation must be 'program_counter'"""
        data = _load_pc_scope()
        assert data["default_interpretation"] == "program_counter", (
            "PC must default to program_counter unless repository evidence proves otherwise"
        )

    def test_has_at_least_one_decision(self) -> None:
        """At least one PC scope decision must exist"""
        data = _load_pc_scope()
        assert len(data["decisions"]) >= 1

    def test_decisions_have_required_fields(self) -> None:
        """Every decision has decision_id, surface, verdict, rationale, evidence, blockers, row_hash"""
        data = _load_pc_scope()
        required = {"decision_id", "surface", "verdict", "rationale", "evidence", "blockers", "row_hash"}
        for i, d in enumerate(data["decisions"]):
            missing = required - set(d.keys())
            assert not missing, f"Decision {i} missing fields: {missing}"

    def test_verdict_is_program_counter(self) -> None:
        """All PC scope verdicts must be 'program_counter' (no evidence for alternative)"""
        data = _load_pc_scope()
        for d in data["decisions"]:
            assert d["verdict"] == "program_counter", (
                f"Decision {d['decision_id']}: verdict must be 'program_counter', got '{d['verdict']}'"
            )

    def test_blockers_are_blocked_not_accepted(self) -> None:
        """All blockers must have status='blocked' — unresolved approval is a blocker, not acceptance"""
        data = _load_pc_scope()
        for d in data["decisions"]:
            for b in d.get("blockers", []):
                assert b["status"] == "blocked", (
                    f"Blocker {b.get('blocker_id')} in {d['decision_id']}: "
                    f"status must be 'blocked' (unresolved human approval), got '{b['status']}'"
                )

    def test_pc_scope_blocker_present(self) -> None:
        """PC scope decision must include the portfolio gate blocker"""
        data = _load_pc_scope()
        all_blocker_ids = []
        for d in data["decisions"]:
            for b in d.get("blockers", []):
                all_blocker_ids.append(b.get("blocker_id", ""))
        assert "PC-SCOPE-BLOCKER-001" in all_blocker_ids, (
            "Portfolio gate blocker (PC-SCOPE-BLOCKER-001) must be present"
        )

    def test_evidence_includes_source_files(self) -> None:
        """PC scope decision evidence must reference source files proving pc = program counter"""
        data = _load_pc_scope()
        for d in data["decisions"]:
            source_files = d.get("evidence", {}).get("source_files", [])
            assert len(source_files) >= 2, (
                f"Decision {d['decision_id']}: must reference at least 2 source files as evidence"
            )
            paths = [sf["path"] for sf in source_files]
            assert any("ir.py" in p for p in paths), "Must reference ir.py (program counter definition)"
            assert any("checkpoint.py" in p for p in paths), "Must reference checkpoint.py (cursor/pc usage)"

    def test_evidence_includes_migration_matrix_rows(self) -> None:
        """PC scope evidence must reference relevant migration matrix rows"""
        data = _load_pc_scope()
        for d in data["decisions"]:
            matrix_rows = d.get("evidence", {}).get("migration_matrix_rows", [])
            assert len(matrix_rows) >= 1, (
                f"Decision {d['decision_id']}: must reference at least 1 migration matrix row"
            )

    def test_composite_hash_matches(self) -> None:
        """Composite hash must be recomputable from decision row hashes"""
        data = _load_pc_scope()
        expected = _gen._compute_composite_hash(data["decisions"])
        assert data["composite_hash"] == expected, (
            f"Composite hash mismatch: expected {expected}, got {data['composite_hash']}"
        )

    def test_row_hashes_are_stable(self) -> None:
        """Row hashes are stable (recomputation matches stored value)"""
        data = _load_pc_scope()
        for d in data["decisions"]:
            recomputed = _gen._compute_row_hash(d)
            assert d["row_hash"] == recomputed, (
                f"Decision {d['decision_id']}: row hash mismatch "
                f"(stored={d['row_hash'][:12]}..., recomputed={recomputed[:12]}...)"
            )

    def test_blocker_count_matches(self) -> None:
        """blocker_count must equal total blockers across all decisions"""
        data = _load_pc_scope()
        actual = sum(len(d.get("blockers", [])) for d in data["decisions"])
        assert data["blocker_count"] == actual, (
            f"blocker_count {data['blocker_count']} != actual {actual}"
        )


# ── Ownership decision record tests ────────────────────────────────────────


class TestOwnershipDecisionRecord:
    """Tests for evidence/ownership-decision-record.json"""

    def test_schema_matches(self) -> None:
        """Schema is m6.ownership-decision-record.v1"""
        data = _load_ownership()
        assert data["schema"] == OWNERSHIP_SCHEMA

    def test_has_owner_decisions(self) -> None:
        """At least one owner decision must exist"""
        data = _load_ownership()
        assert len(data["owner_decisions"]) >= 1

    def test_required_owners_present(self) -> None:
        """Run Authority, WBC, and TransitionWriter/repair custody must be present"""
        data = _load_ownership()
        owners_present = {d["owner"] for d in data["owner_decisions"]}
        missing = REQUIRED_OWNERS - owners_present
        assert not missing, f"Missing required owners: {missing}"

    def test_no_duplicate_owners(self) -> None:
        """No duplicate owner entries"""
        data = _load_ownership()
        owners = [d["owner"] for d in data["owner_decisions"]]
        assert len(owners) == len(set(owners)), f"Duplicate owners found: {owners}"

    def test_every_owner_has_required_fields(self) -> None:
        """Every owner decision has required fields"""
        data = _load_ownership()
        required = {
            "owner", "canonical_owns", "canonical_must_not_own",
            "matrix_surface_count", "classification_counts",
            "residual_count", "blocked_count",
            "surfaces", "blockers", "row_hash",
        }
        for d in data["owner_decisions"]:
            missing = required - set(d.keys())
            assert not missing, f"Owner {d.get('owner', 'UNKNOWN')} missing fields: {missing}"

    def test_classification_counts_match_surfaces(self) -> None:
        """Classification counts must match actual surface classifications"""
        data = _load_ownership()
        for d in data["owner_decisions"]:
            actual: dict[str, int] = {}
            for s in d["surfaces"]:
                cls = s["classification"]
                actual[cls] = actual.get(cls, 0) + 1
            counts = d["classification_counts"]
            assert counts == actual, (
                f"Owner {d['owner']}: classification_counts {counts} != actual {actual}"
            )

    def test_surface_counts_match(self) -> None:
        """residual_count + blocked_count + prerequisite_satisfied_count + retired_count + out_of_scope_count == matrix_surface_count"""
        data = _load_ownership()
        for d in data["owner_decisions"]:
            total = (
                d["residual_count"]
                + d["blocked_count"]
                + d.get("prerequisite_satisfied_count", 0)
                + d.get("retired_count", 0)
                + d.get("out_of_scope_count", 0)
            )
            assert total == d["matrix_surface_count"], (
                f"Owner {d['owner']}: classification sum {total} != matrix_surface_count {d['matrix_surface_count']}"
            )

    def test_global_blockers_are_blocked(self) -> None:
        """All global blockers must have status='blocked' — unresolved approval is blocker, not acceptance"""
        data = _load_ownership()
        for b in data.get("global_blockers", []):
            assert b["status"] == "blocked", (
                f"Global blocker {b.get('blocker_id')}: "
                f"status must be 'blocked', got '{b['status']}'"
            )

    def test_run_authority_receipt_blocker_present(self) -> None:
        """OWNERSHIP-BLOCKER-001 (Run Authority M1-M3 receipts) must be present"""
        data = _load_ownership()
        blocker_ids = [b["blocker_id"] for b in data.get("global_blockers", [])]
        assert "OWNERSHIP-BLOCKER-001" in blocker_ids, (
            "Run Authority M1-M3 receipt blocker must be present"
        )

    def test_portfolio_gate_blocker_present(self) -> None:
        """OWNERSHIP-BLOCKER-002 (Portfolio gate PC scope) must be present"""
        data = _load_ownership()
        blocker_ids = [b["blocker_id"] for b in data.get("global_blockers", [])]
        assert "OWNERSHIP-BLOCKER-002" in blocker_ids, (
            "Portfolio gate PC scope blocker must be present"
        )

    def test_m5_bound_head_blocker_present(self) -> None:
        """OWNERSHIP-BLOCKER-003 (M5 bound-head mismatch) must be present"""
        data = _load_ownership()
        blocker_ids = [b["blocker_id"] for b in data.get("global_blockers", [])]
        assert "OWNERSHIP-BLOCKER-003" in blocker_ids, (
            "M5 bound-head mismatch blocker must be present"
        )

    def test_wbc_file_hash_blocker_present(self) -> None:
        """OWNERSHIP-BLOCKER-004 (WBC file hash mismatch) must be present"""
        data = _load_ownership()
        blocker_ids = [b["blocker_id"] for b in data.get("global_blockers", [])]
        assert "OWNERSHIP-BLOCKER-004" in blocker_ids, (
            "WBC file hash mismatch blocker must be present"
        )

    def test_explicit_ownership_matrix_present(self) -> None:
        """Explicit ownership matrix from research document must be included"""
        data = _load_ownership()
        matrix = data.get("explicit_ownership_matrix", [])
        assert len(matrix) >= 3, (
            "Explicit ownership matrix must have at least Run Authority, WBC, and TransitionWriter entries"
        )

    def test_north_star_principles_present(self) -> None:
        """North Star principles must be included"""
        data = _load_ownership()
        principles = data.get("north_star_principles", [])
        assert len(principles) >= 3, "At least 3 North Star principles must be present"

    def test_composite_hash_matches(self) -> None:
        """Composite hash must be recomputable from owner decision row hashes"""
        data = _load_ownership()
        expected = _gen._compute_composite_hash(data["owner_decisions"])
        assert data["composite_hash"] == expected, (
            f"Composite hash mismatch: expected {expected}, got {data['composite_hash']}"
        )

    def test_row_hashes_are_stable(self) -> None:
        """Row hashes are stable (recomputation matches stored value)"""
        data = _load_ownership()
        for d in data["owner_decisions"]:
            recomputed = _gen._compute_row_hash(d)
            assert d["row_hash"] == recomputed, (
                f"Owner {d['owner']}: row hash mismatch "
                f"(stored={d['row_hash'][:12]}..., recomputed={recomputed[:12]}...)"
            )

    def test_every_surface_has_classification(self) -> None:
        """Every surface entry must have a valid classification"""
        data = _load_ownership()
        valid = {"prerequisite-satisfied", "residual", "blocked", "retired", "out-of-supported-scope"}
        for d in data["owner_decisions"]:
            for s in d["surfaces"]:
                assert s["classification"] in valid, (
                    f"Owner {d['owner']} surface row {s['row_index']}: "
                    f"invalid classification '{s['classification']}'"
                )

    def test_total_surface_count_matches(self) -> None:
        """total_surface_count must match sum of all owner surface counts"""
        data = _load_ownership()
        actual = sum(d["matrix_surface_count"] for d in data["owner_decisions"])
        assert data["total_surface_count"] == actual, (
            f"total_surface_count {data['total_surface_count']} != actual sum {actual}"
        )

    def test_owner_count_matches(self) -> None:
        """owner_count must match number of owner_decisions"""
        data = _load_ownership()
        assert data["owner_count"] == len(data["owner_decisions"]), (
            f"owner_count {data['owner_count']} != len(owner_decisions) {len(data['owner_decisions'])}"
        )


# ── Cross-artifact integration tests ───────────────────────────────────────


class TestOwnershipDecisionIntegration:
    """Integration tests spanning both PC scope and ownership artifacts."""

    def test_pc_scope_and_ownership_both_loadable(self) -> None:
        """Both artifacts exist and are valid JSON"""
        pc = _load_pc_scope()
        own = _load_ownership()
        assert pc is not None
        assert own is not None

    def test_human_approval_is_never_accepted(self) -> None:
        """North Star guard: no human approval blocker should have status='accepted'"""
        pc = _load_pc_scope()
        own = _load_ownership()

        # Check all PC scope blockers
        for d in pc["decisions"]:
            for b in d.get("blockers", []):
                assert b["status"] != "accepted", (
                    f"PC scope blocker {b['blocker_id']}: unresolved human approval must NOT be accepted"
                )

        # Check all ownership global blockers
        for b in own.get("global_blockers", []):
            assert b["status"] != "accepted", (
                f"Ownership blocker {b['blocker_id']}: unresolved human approval must NOT be accepted"
            )

    def test_pc_scope_cited_in_ownership_blockers(self) -> None:
        """PC scope decision artifact must be cited in ownership blocker evidence"""
        own = _load_ownership()
        portfolio_blocker = None
        for b in own.get("global_blockers", []):
            if b["blocker_id"] == "OWNERSHIP-BLOCKER-002":
                portfolio_blocker = b
                break
        assert portfolio_blocker is not None, "Portfolio gate blocker not found"
        evidence_text = " ".join(portfolio_blocker.get("source_evidence", []))
        assert "pc-scope-decision.json" in evidence_text, (
            "Portfolio gate blocker must reference pc-scope-decision.json"
        )

    def test_regeneration_is_idempotent(self) -> None:
        """Regenerating produces identical composite hashes"""
        # Load current
        pc1 = _load_pc_scope()
        own1 = _load_ownership()

        # Regenerate in-memory to get new hashes
        import json as _json

        prerequisite_data = {}
        if _gen.PREREQ_PATH.exists():
            with open(_gen.PREREQ_PATH, "r") as fh:
                prerequisite_data = _json.load(fh)

        migration_matrix = {}
        if _gen.MIGRATION_MATRIX_PATH.exists():
            with open(_gen.MIGRATION_MATRIX_PATH, "r") as fh:
                migration_matrix = _json.load(fh)

        pc2 = _gen._build_pc_scope_decision(prerequisite_data, migration_matrix)

        # Compare composite hash (decision structure should be stable)
        # Note: generation timestamp differs, so we only compare composite hash of decisions
        hash1 = _gen._compute_composite_hash(pc1["decisions"])
        hash2 = _gen._compute_composite_hash(pc2["decisions"])
        assert hash1 == hash2, (
            f"PC scope composite hash changed on regeneration: {hash1[:12]}... != {hash2[:12]}..."
        )
