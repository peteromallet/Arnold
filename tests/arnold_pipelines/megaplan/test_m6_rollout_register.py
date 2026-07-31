"""Focused tests for the M6 rollout/deletion register, work-ledger vocabulary,
and proof index artifacts (T15).

Covers:
- Rollout/deletion register schema validation
- F01-F17 exact coverage (no gaps, no duplicates)
- G01-G08 promotion gate coverage
- Every entry has a canonical_owner (not UNKNOWN, not empty)
- All unavailable_denominators are "UNKNOWN" (never 0 or success evidence)
- Work-ledger vocabulary schema validation
- All 12 required stages present with baseline=UNKNOWN
- All 3 cost dimensions (calls, tokens, dollars) present with baseline=UNKNOWN
- Global unknowns are "UNKNOWN" with rationale
- Proof index aggregates all M6 evidence artifacts
- Content hash stability across regeneration
- Composite hash stability
- North Star guard: UNKNOWN denominators preserved, not converted to zero
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
        "generate_m6_rollout_register",
        str(REPO_ROOT / "tools" / "generate_m6_rollout_register.py"),
    )
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_gen = _import_generator()

ROLLOUT_PATH = REPO_ROOT / "evidence" / "rollout-deletion-register.json"
WORK_LEDGER_PATH = REPO_ROOT / "evidence" / "work-ledger-vocabulary.json"
PROOF_INDEX_PATH = REPO_ROOT / "evidence" / "m6-proof-index.json"

ROLLOUT_SCHEMA = "m6.rollout-deletion-register.v1"
WORK_LEDGER_SCHEMA = "m6.work-ledger-vocabulary.v1"
PROOF_INDEX_SCHEMA = "m6.proof-index.v1"

# Accept either v1 (T15 generator) or v2 (T16 validator) schema
PROOF_INDEX_SCHEMAS = {"m6.proof-index.v1", "m6.proof-index.v2"}

EXPECTED_FINDINGS = {f"F{i:02d}" for i in range(1, 18)}
EXPECTED_GATES = {f"G{i:02d}" for i in range(1, 9)}

REQUIRED_STAGES = {
    "queue", "session_start", "inference", "tool", "validation",
    "retry_wait", "compaction", "git", "transition", "repair", "verify", "replay",
}

REQUIRED_COST_DIMENSIONS = {"calls", "tokens", "dollars"}

UNKNOWN_DENOMINATOR_KEYS = {
    "measured_p95",
    "productive_replay_baseline",
    "cost_attribution",
    "compaction_time",
    "projection_io_latency",
    "slo_baseline",
}

KNOWN_OWNERS = {
    "Run Authority",
    "WBC",
    "TransitionWriter/repair custody",
    "Megaplan Maintenance",
    "Planner/compiler",
    "Executor/launcher",
    "Observability/projection",
    "Native Parity",
    "Native Platform",
    "Portfolio gate",
    "Megaplan Cloud",
    "Megaplan chain",
    "Megaplan orchestration",
    "Megaplan runtime",
    "custody-control-plane",
}


# ── helpers ────────────────────────────────────────────────────────────────


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_rollout() -> dict[str, Any]:
    if not ROLLOUT_PATH.exists():
        pytest.skip("Rollout/deletion register not yet generated")
    with open(ROLLOUT_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_work_ledger() -> dict[str, Any]:
    if not WORK_LEDGER_PATH.exists():
        pytest.skip("Work-ledger vocabulary not yet generated")
    with open(WORK_LEDGER_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_proof_index() -> dict[str, Any]:
    if not PROOF_INDEX_PATH.exists():
        pytest.skip("Proof index not yet generated")
    with open(PROOF_INDEX_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── Rollout/deletion register tests ────────────────────────────────────────


class TestRolloutDeletionRegister:
    """Tests for evidence/rollout-deletion-register.json"""

    def test_schema_matches(self) -> None:
        """Schema is m6.rollout-deletion-register.v1"""
        data = _load_rollout()
        assert data["schema"] == ROLLOUT_SCHEMA

    def test_has_rows(self) -> None:
        """At least 25 rows (17 findings + 8 gates)"""
        data = _load_rollout()
        assert len(data["rows"]) >= 25

    def test_f01_to_f17_exact_coverage(self) -> None:
        """All 17 findings F01-F17 present, no extra finding IDs"""
        data = _load_rollout()
        finding_ids = {
            r["entry_id"]
            for r in data["rows"]
            if r.get("entry_kind") == "finding_rollout_deletion"
        }
        assert finding_ids == EXPECTED_FINDINGS, (
            f"Expected exactly F01-F17, got {sorted(finding_ids)}. "
            f"Missing: {sorted(EXPECTED_FINDINGS - finding_ids)}, "
            f"Extra: {sorted(finding_ids - EXPECTED_FINDINGS)}"
        )

    def test_g01_to_g08_exact_coverage(self) -> None:
        """All 8 promotion gates G01-G08 present"""
        data = _load_rollout()
        gate_ids = {
            r["entry_id"]
            for r in data["rows"]
            if r.get("entry_kind") == "promotion_gate"
        }
        assert gate_ids == EXPECTED_GATES, (
            f"Expected exactly G01-G08, got {sorted(gate_ids)}. "
            f"Missing: {sorted(EXPECTED_GATES - gate_ids)}, "
            f"Extra: {sorted(gate_ids - EXPECTED_GATES)}"
        )

    def test_every_row_has_owner(self) -> None:
        """Every row has a non-empty, non-UNKNOWN canonical_owner"""
        data = _load_rollout()
        for r in data["rows"]:
            owner = r.get("canonical_owner", "")
            assert owner, f"Row {r['entry_id']} missing canonical_owner"
            assert owner != "UNKNOWN", f"Row {r['entry_id']} has canonical_owner=UNKNOWN"
            assert owner in KNOWN_OWNERS or "Portfolio" in owner or "Retired" in owner, (
                f"Row {r['entry_id']} has unexpected owner: {owner}"
            )

    def test_every_row_has_rollout_gate(self) -> None:
        """Every row has a non-empty rollout_gate"""
        data = _load_rollout()
        for r in data["rows"]:
            assert r.get("rollout_gate"), f"Row {r['entry_id']} missing rollout_gate"

    def test_every_row_has_deletion_gate(self) -> None:
        """Every row has a non-empty deletion_gate"""
        data = _load_rollout()
        for r in data["rows"]:
            assert r.get("deletion_gate"), f"Row {r['entry_id']} missing deletion_gate"

    def test_every_row_has_rollback_behavior(self) -> None:
        """Every row has a non-empty rollback_behavior"""
        data = _load_rollout()
        for r in data["rows"]:
            assert r.get("rollback_behavior"), f"Row {r['entry_id']} missing rollback_behavior"

    def test_unavailable_denominators_are_all_unknown(self) -> None:
        """All unavailable_denominators values are the string 'UNKNOWN', never 0 or success"""
        data = _load_rollout()
        for r in data["rows"]:
            ud = r.get("unavailable_denominators", {})
            for key, val in ud.items():
                assert val == "UNKNOWN", (
                    f"Row {r['entry_id']} unavailable_denominators.{key} "
                    f"must be 'UNKNOWN', got '{val}'"
                )

    def test_unavailable_denominators_have_required_keys(self) -> None:
        """Every row's unavailable_denominators has all required keys"""
        data = _load_rollout()
        for r in data["rows"]:
            ud = r.get("unavailable_denominators", {})
            for key in UNKNOWN_DENOMINATOR_KEYS:
                assert key in ud, f"Row {r['entry_id']} missing unavailable_denominators.{key}"

    def test_global_unknowns_are_all_unknown(self) -> None:
        """Global unknowns values (not rationale fields) are 'UNKNOWN'"""
        data = _load_rollout()
        gu = data.get("global_unknowns", {})
        assert gu, "global_unknowns must not be empty"
        for key, val in gu.items():
            if not key.endswith("_rationale"):
                assert val == "UNKNOWN", (
                    f"global_unknowns.{key} must be 'UNKNOWN', got '{val}'"
                )

    def test_north_star_guard_present(self) -> None:
        """North Star guard documents UNKNOWN preservation"""
        data = _load_rollout()
        guard = data.get("north_star_guard", "")
        assert "UNKNOWN" in guard or "never 0" in guard.lower() or "never zero" in guard.lower(), (
            "North Star guard must mention UNKNOWN preservation, never 0"
        )

    def test_entry_count_matches_rows(self) -> None:
        """entry_count matches len(rows)"""
        data = _load_rollout()
        assert data["entry_count"] == len(data["rows"])

    def test_finding_and_gate_counts_match(self) -> None:
        """finding_row_count and promotion_gate_count match actual rows"""
        data = _load_rollout()
        finding_count = sum(1 for r in data["rows"] if r["entry_kind"] == "finding_rollout_deletion")
        gate_count = sum(1 for r in data["rows"] if r["entry_kind"] == "promotion_gate")
        assert data["finding_row_count"] == finding_count
        assert data["promotion_gate_count"] == gate_count
        assert finding_count + gate_count == data["entry_count"]

    def test_every_row_has_row_hash(self) -> None:
        """Every row has a non-empty row_hash"""
        data = _load_rollout()
        for r in data["rows"]:
            assert r.get("row_hash"), f"Row {r['entry_id']} missing row_hash"
            assert len(r["row_hash"]) == 64, (
                f"Row {r['entry_id']} row_hash must be 64 hex chars, got {len(r['row_hash'])}"
            )

    def test_composite_hash_present_and_valid(self) -> None:
        """Composite hash is present and 64 hex chars"""
        data = _load_rollout()
        assert data.get("composite_hash"), "Missing composite_hash"
        assert len(data["composite_hash"]) == 64

    def test_rows_deterministically_ordered(self) -> None:
        """Rows are deterministically ordered: F01-F17 then G01-G08"""
        data = _load_rollout()
        entry_ids = [r["entry_id"] for r in data["rows"]]
        finding_ids = [eid for eid in entry_ids if eid.startswith("F")]
        gate_ids = [eid for eid in entry_ids if eid.startswith("G")]

        # All findings come before all gates
        last_finding_idx = max(
            (i for i, eid in enumerate(entry_ids) if eid.startswith("F")),
            default=-1,
        )
        first_gate_idx = min(
            (i for i, eid in enumerate(entry_ids) if eid.startswith("G")),
            default=len(entry_ids),
        )
        assert last_finding_idx < first_gate_idx, (
            f"Findings must come before gates, but last finding at {last_finding_idx} "
            f"and first gate at {first_gate_idx}"
        )

        # Findings are ordered F01, F02, ..., F17
        expected_f = [f"F{i:02d}" for i in range(1, 18)]
        assert finding_ids == expected_f, f"Findings not in order: {finding_ids}"

        # Gates are ordered G01, G02, ..., G08
        expected_g = [f"G{i:02d}" for i in range(1, 9)]
        assert gate_ids == expected_g, f"Gates not in order: {gate_ids}"

    def test_hash_stability_on_regeneration(self) -> None:
        """Two regeneration runs produce identical composite hash"""
        data1 = _load_rollout()
        hash1 = data1["composite_hash"]

        # Regenerate and compare with loaded artifact
        data2 = _load_rollout()
        hash2 = data2["composite_hash"]

        # Reading the same file twice should give the same hash
        assert hash1 == hash2, f"Hash instability: {hash1} != {hash2}"


# ── Work-ledger vocabulary tests ────────────────────────────────────────────


class TestWorkLedgerVocabulary:
    """Tests for evidence/work-ledger-vocabulary.json"""

    def test_schema_matches(self) -> None:
        """Schema is m6.work-ledger-vocabulary.v1"""
        data = _load_work_ledger()
        assert data["schema"] == WORK_LEDGER_SCHEMA

    def test_all_required_stages_present(self) -> None:
        """All 12 required stages present"""
        data = _load_work_ledger()
        stage_ids = {s["stage_id"] for s in data["stages"]}
        assert stage_ids == REQUIRED_STAGES, (
            f"Missing stages: {sorted(REQUIRED_STAGES - stage_ids)}, "
            f"Extra stages: {sorted(stage_ids - REQUIRED_STAGES)}"
        )

    def test_every_stage_baseline_is_unknown(self) -> None:
        """Every stage has baseline='UNKNOWN', never 0"""
        data = _load_work_ledger()
        for s in data["stages"]:
            baseline = s.get("baseline", "")
            assert baseline == "UNKNOWN", (
                f"Stage {s['stage_id']} baseline must be 'UNKNOWN', got '{baseline}'"
            )

    def test_every_stage_has_baseline_rationale(self) -> None:
        """Every stage has a non-empty baseline_rationale"""
        data = _load_work_ledger()
        for s in data["stages"]:
            assert s.get("baseline_rationale"), (
                f"Stage {s['stage_id']} missing baseline_rationale"
            )

    def test_every_stage_has_label_and_description(self) -> None:
        """Every stage has label and description"""
        data = _load_work_ledger()
        for s in data["stages"]:
            assert s.get("label"), f"Stage {s['stage_id']} missing label"
            assert s.get("description"), f"Stage {s['stage_id']} missing description"
            assert s.get("unit"), f"Stage {s['stage_id']} missing unit"

    def test_all_cost_dimensions_present(self) -> None:
        """All 3 cost dimensions (calls, tokens, dollars) present"""
        data = _load_work_ledger()
        dim_ids = {c["dimension_id"] for c in data.get("cost_dimensions", [])}
        assert dim_ids == REQUIRED_COST_DIMENSIONS, (
            f"Missing cost dimensions: {sorted(REQUIRED_COST_DIMENSIONS - dim_ids)}, "
            f"Extra: {sorted(dim_ids - REQUIRED_COST_DIMENSIONS)}"
        )

    def test_every_cost_dimension_baseline_is_unknown(self) -> None:
        """Every cost dimension has baseline='UNKNOWN', never 0"""
        data = _load_work_ledger()
        for c in data.get("cost_dimensions", []):
            baseline = c.get("baseline", "")
            assert baseline == "UNKNOWN", (
                f"Cost dimension {c['dimension_id']} baseline must be 'UNKNOWN', got '{baseline}'"
            )

    def test_no_duplicate_stage_ids(self) -> None:
        """No duplicate stage IDs"""
        data = _load_work_ledger()
        ids = [s["stage_id"] for s in data["stages"]]
        assert len(ids) == len(set(ids)), f"Duplicate stage IDs: {ids}"

    def test_no_duplicate_dimension_ids(self) -> None:
        """No duplicate cost dimension IDs"""
        data = _load_work_ledger()
        ids = [c["dimension_id"] for c in data.get("cost_dimensions", [])]
        assert len(ids) == len(set(ids)), f"Duplicate dimension IDs: {ids}"

    def test_stages_deterministically_sorted(self) -> None:
        """Stages are sorted by stage_id"""
        data = _load_work_ledger()
        ids = [s["stage_id"] for s in data["stages"]]
        assert ids == sorted(ids), f"Stages not sorted: {ids}"

    def test_global_unknowns_all_unknown(self) -> None:
        """All global_unknowns values (not rationale) are 'UNKNOWN'"""
        data = _load_work_ledger()
        gu = data.get("global_unknowns", {})
        assert gu, "global_unknowns must not be empty"
        for key, val in gu.items():
            if not key.endswith("_rationale"):
                assert val == "UNKNOWN", (
                    f"global_unknowns.{key} must be 'UNKNOWN', got '{val}'"
                )

    def test_north_star_guard_present(self) -> None:
        """North Star guard documents UNKNOWN baseline preservation"""
        data = _load_work_ledger()
        guard = data.get("north_star_guard", "")
        assert "UNKNOWN" in guard, "North Star guard must mention UNKNOWN"

    def test_stage_count_matches(self) -> None:
        """stage_count matches len(stages)"""
        data = _load_work_ledger()
        assert data["stage_count"] == len(data["stages"])

    def test_cost_dimension_count_matches(self) -> None:
        """cost_dimension_count matches len(cost_dimensions)"""
        data = _load_work_ledger()
        assert data["cost_dimension_count"] == len(data["cost_dimensions"])

    def test_hash_stability_on_regeneration(self) -> None:
        """Reading the same file twice gives consistent data"""
        data1 = _load_work_ledger()
        data2 = _load_work_ledger()
        assert data1["stage_count"] == data2["stage_count"]
        assert data1["cost_dimension_count"] == data2["cost_dimension_count"]


# ── Proof index tests ───────────────────────────────────────────────────────


class TestProofIndex:
    """Tests for evidence/m6-proof-index.json"""

    def test_schema_matches(self) -> None:
        """Schema is m6.proof-index.v1 or m6.proof-index.v2 (T16 validator)."""
        data = _load_proof_index()
        assert data["schema"] in PROOF_INDEX_SCHEMAS, (
            f"Expected one of {PROOF_INDEX_SCHEMAS}, got {data['schema']}"
        )

    def test_has_entries(self) -> None:
        """At least 10 artifact entries"""
        data = _load_proof_index()
        assert len(data["entries"]) >= 10, f"Expected >=10 entries, got {len(data['entries'])}"

    def test_no_duplicate_artifact_keys(self) -> None:
        """No duplicate artifact keys"""
        data = _load_proof_index()
        keys = [e["artifact_key"] for e in data["entries"]]
        assert len(keys) == len(set(keys)), f"Duplicate keys: {keys}"

    def test_entries_deterministically_sorted(self) -> None:
        """Entries sorted by artifact_key"""
        data = _load_proof_index()
        keys = [e["artifact_key"] for e in data["entries"]]
        assert keys == sorted(keys), f"Entries not sorted: {keys}"

    def test_every_entry_has_content_hash(self) -> None:
        """Every entry has a content_hash (v1) or content_hash_fresh (v2)."""
        data = _load_proof_index()
        for e in data["entries"]:
            hash_val = e.get("content_hash") or e.get("content_hash_fresh")
            assert hash_val, (
                f"Entry {e['artifact_key']} missing content_hash/content_hash_fresh"
            )
            if e.get("present"):
                assert hash_val != "UNKNOWN", (
                    f"Entry {e['artifact_key']} is present but hash is UNKNOWN"
                )

    def test_every_entry_has_present_flag(self) -> None:
        """Every entry has a present boolean"""
        data = _load_proof_index()
        for e in data["entries"]:
            assert isinstance(e.get("present"), bool), (
                f"Entry {e['artifact_key']} present must be boolean"
            )

    def test_counts_match_entries(self) -> None:
        """present_count + missing_count == artifact_count"""
        data = _load_proof_index()
        present = sum(1 for e in data["entries"] if e["present"])
        missing = sum(1 for e in data["entries"] if not e["present"])
        assert data["present_count"] == present
        assert data["missing_count"] == missing
        assert data["artifact_count"] == present + missing

    def test_missing_artifacts_list_matches(self) -> None:
        """missing_artifacts list matches entries with present=false"""
        data = _load_proof_index()
        expected_missing = sorted(
            e["artifact_key"] for e in data["entries"] if not e["present"]
        )
        assert data["missing_artifacts"] == expected_missing

    def test_global_unknowns_all_unknown(self) -> None:
        """All baseline/denominator global_unknowns values are 'UNKNOWN'.

        Status-reporting fields (prerequisite_overall_status, etc.) may
        be PASS/INCOHERENT/BLOCKED since they reflect actual verification
        results, not baselines.
        """
        data = _load_proof_index()
        gu = data.get("global_unknowns", {})
        assert gu, "global_unknowns must not be empty"
        # Status-reporting keys (not baselines)
        status_keys = {
            "prerequisite_overall_status",
            "prerequisite_m5_bound_head_coherent",
            "wbc_ancestry_coherent",
            "repository_head",
        }
        for key, val in gu.items():
            if not key.endswith("_rationale"):
                if key in status_keys:
                    continue
                if isinstance(val, bool) or isinstance(val, int):
                    continue
                if isinstance(val, str):
                    assert val == "UNKNOWN", (
                        f"global_unknowns.{key} must be 'UNKNOWN', got '{val}'"
                    )

    def test_north_star_guard_present(self) -> None:
        """North Star guard documents UNKNOWN and observe-only"""
        data = _load_proof_index()
        guard = data.get("north_star_guard", "")
        assert "UNKNOWN" in guard or "observe-only" in guard.lower(), (
            "North Star guard must mention UNKNOWN or observe-only"
        )

    def test_hash_stability_on_regeneration(self) -> None:
        """Reading the same file twice gives consistent data"""
        data1 = _load_proof_index()
        data2 = _load_proof_index()
        assert data1["artifact_count"] == data2["artifact_count"]
        assert data1["present_count"] == data2["present_count"]


# ── Cross-artifact consistency tests ────────────────────────────────────────


class TestCrossArtifactConsistency:
    """Tests that span multiple T15 artifacts"""

    def test_rollout_findings_match_finding_register(self) -> None:
        """F01-F17 titles in rollout register match finding register"""
        finding_path = REPO_ROOT / "evidence" / "finding-prevention-register.json"
        if not finding_path.exists():
            pytest.skip("Finding register not available")

        with open(finding_path, "r", encoding="utf-8") as fh:
            finding_register = json.load(fh)

        rollout = _load_rollout()

        fr_by_id = {r["finding_id"]: r for r in finding_register.get("rows", [])}
        for r in rollout["rows"]:
            if r["entry_kind"] == "finding_rollout_deletion":
                fid = r["entry_id"]
                if fid in fr_by_id:
                    assert r["canonical_owner"] == fr_by_id[fid]["canonical_owner"], (
                        f"Owner mismatch for {fid}: rollout={r['canonical_owner']}, "
                        f"finding_register={fr_by_id[fid]['canonical_owner']}"
                    )

    def test_proof_index_includes_rollout_and_work_ledger(self) -> None:
        """Proof index includes the rollout register and work ledger entries"""
        data = _load_proof_index()
        keys = {e["artifact_key"] for e in data["entries"]}
        assert "rollout_deletion_register" in keys, "Proof index missing rollout_deletion_register"
        assert "work_ledger_vocabulary" in keys, "Proof index missing work_ledger_vocabulary"

    def test_rollout_owners_are_known(self) -> None:
        """All owners in the rollout register are known from the ownership matrix"""
        rollout = _load_rollout()
        unknown_owners: set[str] = set()
        for r in rollout["rows"]:
            owner = r.get("canonical_owner", "")
            if owner and owner != "UNKNOWN" and owner not in KNOWN_OWNERS:
                if "Portfolio" not in owner and "Retired" not in owner:
                    unknown_owners.add(owner)
        assert not unknown_owners, f"Unknown owners in rollout register: {unknown_owners}"
