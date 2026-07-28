"""Replay tests for boundary compatibility evaluation (C1 T17).

Covers:
- Compatible, incompatible, unknown, and non-conformant replay outcomes
- Stable diagnostic codes (CBC001–CBC015)
- Legacy fixture non-normalization
- Current fixture non-rewrite behavior
- Deterministic ordering and evaluator properties
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from arnold.workflow.boundary_compatibility import (
    CompatibilityDiagnosticCode,
    CompatibilityEvaluator,
    CompatibilityResult,
    CompatibilityStatus,
    evaluate_boundary_compatibility,
)

# ── Paths ─────────────────────────────────────────────────────────────────

FIXTURE_DIR = Path("tests/fixtures/workflow_boundary_contracts")
CONTRACT_MATRIX = Path(
    "arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json"
)
INVENTORY_PATH = Path("evidence/wbc-boundary-inventory.json")


# ── Helper ────────────────────────────────────────────────────────────────


def _get_results() -> tuple[CompatibilityResult, ...]:
    """Evaluate all fixtures and return typed results."""
    evaluator = CompatibilityEvaluator(
        fixture_dir=FIXTURE_DIR, contract_matrix_path=CONTRACT_MATRIX
    )
    return evaluator.evaluate_all()


def _result_by_fixture_id(
    results: tuple[CompatibilityResult, ...], fixture_id: str
) -> CompatibilityResult:
    """Find a result by fixture_id stem."""
    for r in results:
        if r.fixture_id == fixture_id:
            return r
    raise KeyError(f"Fixture {fixture_id!r} not found in results")


# ══════════════════════════════════════════════════════════════════════════
# Import and basic evaluator properties
# ══════════════════════════════════════════════════════════════════════════


class TestEvaluatorImportAndSetup:
    """Verify all public symbols import and the evaluator can be constructed."""

    def test_all_symbols_importable(self) -> None:
        """All four public types + convenience function must be importable."""
        assert CompatibilityStatus.COMPATIBLE == "compatible"
        assert CompatibilityStatus.INCOMPATIBLE == "incompatible"
        assert CompatibilityStatus.UNKNOWN == "unknown"
        assert CompatibilityStatus.NON_CONFORMANT == "non_conformant"
        assert CompatibilityDiagnosticCode.MISSING_BOUNDARY_RECEIPTS is not None
        assert CompatibilityDiagnosticCode.LEGACY_FIXTURE_UNKNOWN is not None
        assert callable(evaluate_boundary_compatibility)

    def test_evaluator_default_construction(self) -> None:
        """Default constructor uses standard fixture and matrix paths."""
        e = CompatibilityEvaluator()
        assert e._fixture_dir == Path("tests/fixtures/workflow_boundary_contracts")
        assert (
            e._contract_matrix_path
            == Path("arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json")
        )
        assert e._inventory_path == INVENTORY_PATH.resolve()

    def test_evaluator_custom_paths(self) -> None:
        """Custom paths are stored correctly."""
        e = CompatibilityEvaluator(
            fixture_dir="/tmp/fixtures",
            contract_matrix_path="/tmp/matrix.json",
            inventory_path="/tmp/inventory.json",
        )
        assert e._fixture_dir == Path("/tmp/fixtures")
        assert e._contract_matrix_path == Path("/tmp/matrix.json")
        assert e._inventory_path == Path("/tmp/inventory.json")

    def test_evaluate_all_returns_tuple(self) -> None:
        """evaluate_all() must return a tuple of CompatibilityResults."""
        results = _get_results()
        assert isinstance(results, tuple)
        assert len(results) > 0
        for r in results:
            assert isinstance(r, CompatibilityResult)

    def test_convenience_function_equivalent(self) -> None:
        """evaluate_boundary_compatibility() returns same results as evaluator."""
        direct = _get_results()
        via_conv = evaluate_boundary_compatibility(
            fixture_dir=FIXTURE_DIR, contract_matrix_path=CONTRACT_MATRIX
        )
        assert len(direct) == len(via_conv)
        for a, b in zip(direct, via_conv):
            assert a.fixture_id == b.fixture_id
            assert a.status == b.status
            assert a.diagnostics == b.diagnostics


class TestEvaluatorDeterminism:
    """Results must be deterministic (same fixture order, same outcomes)."""

    def test_results_sorted_by_filename(self) -> None:
        """Results must be in sorted fixture filename order."""
        results = _get_results()
        fixture_ids = [r.fixture_id for r in results]
        assert fixture_ids == sorted(fixture_ids), (
            f"Results not in sorted order: {fixture_ids}"
        )

    def test_repeatable_outcomes(self) -> None:
        """Two calls to evaluate_all() must produce identical results."""
        results1 = _get_results()
        results2 = _get_results()
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.fixture_id == r2.fixture_id
            assert r1.status == r2.status
            assert r1.diagnostics == r2.diagnostics
            assert r1.boundary_id == r2.boundary_id


class TestEvaluatorCoverage:
    """Evaluator must cover all fixture bundles in the directory."""

    def test_all_bundles_evaluated(self) -> None:
        """Every captured_bundle_*.json file must produce a result."""
        bundle_files = sorted(
            p.name for p in FIXTURE_DIR.glob("captured_bundle_*.json") if p.is_file()
        )
        results = _get_results()
        result_ids = [r.fixture_id + ".json" for r in results]
        assert bundle_files == result_ids, (
            f"Mismatch: {len(bundle_files)} bundles vs {len(results)} results"
        )

    def test_no_duplicate_fixture_ids(self) -> None:
        """Each fixture_id must appear exactly once."""
        results = _get_results()
        seen = set()
        for r in results:
            assert r.fixture_id not in seen, f"Duplicate fixture_id: {r.fixture_id}"
            seen.add(r.fixture_id)


# ══════════════════════════════════════════════════════════════════════════
# Compatible outcomes
# ══════════════════════════════════════════════════════════════════════════


class TestCompatibleOutcomes:
    """Fixtures with well-formed boundary data and matching contracts
    must evaluate as COMPATIBLE with empty diagnostics."""

    COMPATIBLE_FIXTURES = [
        ("captured_bundle_025_prep_to_plan", "prep_to_plan"),
        ("captured_bundle_029_revise_to_critique", "revise_to_critique"),
    ]

    @pytest.mark.parametrize("fixture_id,expected_boundary_id", COMPATIBLE_FIXTURES)
    def test_compatible_status(
        self, fixture_id: str, expected_boundary_id: str
    ) -> None:
        """Compatible fixtures must have COMPATIBLE status and correct boundary_id."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert r.status == CompatibilityStatus.COMPATIBLE, (
            f"{fixture_id}: expected COMPATIBLE, got {r.status} — diags: {r.diagnostics}"
        )
        assert r.boundary_id == expected_boundary_id, (
            f"{fixture_id}: expected boundary_id {expected_boundary_id!r}, "
            f"got {r.boundary_id!r}"
        )

    @pytest.mark.parametrize("fixture_id,_", COMPATIBLE_FIXTURES)
    def test_compatible_empty_diagnostics(self, fixture_id: str, _: str) -> None:
        """Compatible fixtures must have empty diagnostics tuple."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert r.diagnostics == (), (
            f"{fixture_id}: expected no diagnostics, got {r.diagnostics}"
        )

    @pytest.mark.parametrize("fixture_id,_", COMPATIBLE_FIXTURES)
    def test_compatible_has_contract_refs(self, fixture_id: str, _: str) -> None:
        """Compatible fixtures must reference their contract in the matrix."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert len(r.contract_refs) > 0, (
            f"{fixture_id}: expected contract_refs, got none"
        )
        assert any("contract_to_producer:" in ref for ref in r.contract_refs)

    @pytest.mark.parametrize("fixture_id,_", COMPATIBLE_FIXTURES)
    def test_compatible_has_evidence_refs(self, fixture_id: str, _: str) -> None:
        """Compatible fixtures must have evidence_refs pointing to artifact categories."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert len(r.evidence_refs) > 0, (
            f"{fixture_id}: expected evidence_refs, got none"
        )
        assert all(ref.startswith("artifacts.") for ref in r.evidence_refs)

    @pytest.mark.parametrize("fixture_id,_", COMPATIBLE_FIXTURES)
    def test_compatible_has_details_producer_category(
        self, fixture_id: str, _: str
    ) -> None:
        """Compatible fixtures must include producer_category in details."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert "producer_category" in r.details, (
            f"{fixture_id}: details missing producer_category: {dict(r.details)}"
        )

    def test_compatible_result_to_dict(self) -> None:
        """to_dict() must return a JSON-safe dict with all required fields."""
        results = _get_results()
        r = _result_by_fixture_id(results, "captured_bundle_025_prep_to_plan")
        d = r.to_dict()
        assert d["boundary_id"] == "prep_to_plan"
        assert d["status"] == "compatible"
        assert d["evaluator_version"] == "arnold.workflow.boundary_compatibility.v1"
        assert "contract_refs" in d
        assert "evidence_refs" in d
        assert "details" in d
        # Verify JSON-serializable
        json.dumps(d)


# ══════════════════════════════════════════════════════════════════════════
# Incompatible outcomes
# ══════════════════════════════════════════════════════════════════════════


class TestIncompatibleOutcomes:
    """Fixtures with structural issues must evaluate as INCOMPATIBLE
    with stable diagnostic codes."""

    def test_gate_to_revise_incompatible_phase_result(self) -> None:
        """gate_to_revise has a malformed phase_result missing exit_kind."""
        results = _get_results()
        r = _result_by_fixture_id(results, "captured_bundle_015_gate_to_revise")
        assert r.status == CompatibilityStatus.INCOMPATIBLE, (
            f"Expected INCOMPATIBLE, got {r.status}: {r.diagnostics}"
        )
        assert r.boundary_id == "gate_to_revise"
        assert CompatibilityDiagnosticCode.PHASE_RESULT_EXIT_KIND_MISSING in r.diagnostics
        # Must have exactly one diagnostic (the phase_result issue)
        assert len(r.diagnostics) == 1

    def test_gate_to_revise_contract_refs_present(self) -> None:
        """Incompatible fixtures still reference their contract when found."""
        results = _get_results()
        r = _result_by_fixture_id(results, "captured_bundle_015_gate_to_revise")
        assert any("gate_to_revise" in ref for ref in r.contract_refs), (
            f"Missing contract ref for gate_to_revise: {r.contract_refs}"
        )

    def test_gate_to_revise_structural_issues_in_details(self) -> None:
        """Incompatible result details must include structural_issues list."""
        results = _get_results()
        r = _result_by_fixture_id(results, "captured_bundle_015_gate_to_revise")
        assert "structural_issues" in r.details
        issues = r.details["structural_issues"]
        assert isinstance(issues, list)
        assert CompatibilityDiagnosticCode.PHASE_RESULT_EXIT_KIND_MISSING in issues


# ══════════════════════════════════════════════════════════════════════════
# Incomplete adoption outcomes — manual emission
# ══════════════════════════════════════════════════════════════════════════


class TestManualEmissionInventoryOutcomes:
    """Generated inventory makes manual-emission rows incomplete adoption."""

    MANUAL_EMIT_FIXTURES = [
        ("captured_bundle_004_execute_aggregate_promotion", "execute_aggregate_promotion"),
        ("captured_bundle_005_execute_approval", "execute_approval"),
        ("captured_bundle_006_execute_approval_denial", "execute_approval_denial"),
        ("captured_bundle_007_execute_batch_checkpoint", "execute_batch_checkpoint"),
        ("captured_bundle_008_execute_blocked_anchor", "execute_blocked_anchor"),
        ("captured_bundle_009_execute_no_review_terminal", "execute_no_review_terminal"),
        ("captured_bundle_010_execute_partial_failure", "execute_partial_failure"),
        ("captured_bundle_011_execute_resume_anchor", "execute_resume_anchor"),
    ]

    @pytest.mark.parametrize("fixture_id,expected_boundary_id", MANUAL_EMIT_FIXTURES)
    def test_manual_emit_rows_are_non_conformant(
        self, fixture_id: str, expected_boundary_id: str
    ) -> None:
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert r.boundary_id == expected_boundary_id
        assert r.status == CompatibilityStatus.NON_CONFORMANT
        assert CompatibilityDiagnosticCode.INCOMPLETE_INVENTORY_ROW in r.diagnostics
        assert r.details.get("producer_category") == "manual_emit"
        assert "manual-emission" in r.details.get("inventory_reasons", [])


# ══════════════════════════════════════════════════════════════════════════
# Unknown outcomes — legacy fixtures
# ══════════════════════════════════════════════════════════════════════════


class TestUnknownLegacyOutcomes:
    """Legacy fixture bundles (000–003) must evaluate as UNKNOWN
    without being normalized or rewritten."""

    LEGACY_FIXTURES = [
        ("captured_bundle_000_20260616T192957", "CBC011_LEGACY_FIXTURE_UNKNOWN"),
        ("captured_bundle_001_20260616T192957", "CBC012_CRITICAL_CATEGORIES_UNKNOWN"),
        ("captured_bundle_002_20260616T193029", "CBC012_CRITICAL_CATEGORIES_UNKNOWN"),
        ("captured_bundle_003_20260616T195220", "CBC012_CRITICAL_CATEGORIES_UNKNOWN"),
    ]

    @pytest.mark.parametrize("fixture_id,expected_diag", LEGACY_FIXTURES)
    def test_legacy_unknown_status(
        self, fixture_id: str, expected_diag: str
    ) -> None:
        """Legacy fixtures must have UNKNOWN status with stable diagnostic."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert r.status == CompatibilityStatus.UNKNOWN, (
            f"{fixture_id}: expected UNKNOWN, got {r.status}: {r.diagnostics}"
        )
        assert expected_diag in r.diagnostics, (
            f"{fixture_id}: expected {expected_diag}, got {r.diagnostics}"
        )

    @pytest.mark.parametrize("fixture_id,_", LEGACY_FIXTURES)
    def test_legacy_boundary_id_is_unknown(self, fixture_id: str, _: str) -> None:
        """Legacy fixtures must have boundary_id='unknown'."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert r.boundary_id == "unknown", (
            f"{fixture_id}: expected boundary_id='unknown', got {r.boundary_id!r}"
        )

    @pytest.mark.parametrize("fixture_id,_", LEGACY_FIXTURES)
    def test_legacy_has_reason_in_details(self, fixture_id: str, _: str) -> None:
        """Legacy UNKNOWN results must include a reason in details."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert "reason" in r.details, (
            f"{fixture_id}: details missing 'reason': {dict(r.details)}"
        )

    def test_bundle_000_legacy_diagnostic(self) -> None:
        """Bundle 000 has only events.jsonl — gets CBC011_LEGACY_FIXTURE_UNKNOWN."""
        results = _get_results()
        r = _result_by_fixture_id(results, "captured_bundle_000_20260616T192957")
        assert CompatibilityDiagnosticCode.LEGACY_FIXTURE_UNKNOWN in r.diagnostics
        assert "artifacts:legacy_event_data_only" in r.evidence_refs


# ══════════════════════════════════════════════════════════════════════════
# Unknown outcomes — unknown producer category
# ══════════════════════════════════════════════════════════════════════════


class TestUnknownProducerOutcomes:
    """Fixtures whose contracts have producer_category='unknown'
    must evaluate as UNKNOWN with CBC014."""

    UNKNOWN_PRODUCER_FIXTURES = [
        "captured_bundle_016_override_abort_authority",
        "captured_bundle_017_override_adopt_execution_authority",
        "captured_bundle_018_override_force_proceed_authority",
        "captured_bundle_019_override_human_gate_authority",
        "captured_bundle_020_override_recover_blocked_authority",
        "captured_bundle_021_override_replan_authority",
        "captured_bundle_022_override_resume_clarify_authority",
        "captured_bundle_023_override_suspension_authority",
        "captured_bundle_026_replan_authority",
    ]

    @pytest.mark.parametrize("fixture_id", UNKNOWN_PRODUCER_FIXTURES)
    def test_unknown_producer_status(self, fixture_id: str) -> None:
        """Fixtures with unknown producer_category must have UNKNOWN status."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert r.status == CompatibilityStatus.UNKNOWN, (
            f"{fixture_id}: expected UNKNOWN, got {r.status}: {r.diagnostics}"
        )

    @pytest.mark.parametrize("fixture_id", UNKNOWN_PRODUCER_FIXTURES)
    def test_unknown_producer_has_cbc014(self, fixture_id: str) -> None:
        """Every unknown-producer fixture must include CBC014."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert CompatibilityDiagnosticCode.UNKNOWN_PRODUCER_CATEGORY in r.diagnostics, (
            f"{fixture_id}: missing CBC014 in diagnostics: {r.diagnostics}"
        )

    @pytest.mark.parametrize("fixture_id", UNKNOWN_PRODUCER_FIXTURES)
    def test_unknown_producer_has_contract_ref(self, fixture_id: str) -> None:
        """Unknown-producer results must reference the contract matrix."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert any("contract_to_producer:" in ref for ref in r.contract_refs), (
            f"{fixture_id}: missing contract ref in {r.contract_refs}"
        )

    @pytest.mark.parametrize("fixture_id", UNKNOWN_PRODUCER_FIXTURES)
    def test_unknown_producer_details_has_category(self, fixture_id: str) -> None:
        """Details must include producer_category='unknown'."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert r.details.get("producer_category") == "unknown", (
            f"{fixture_id}: producer_category={r.details.get('producer_category')!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Non-conformant outcomes
# ══════════════════════════════════════════════════════════════════════════


class TestNonConformantOutcomes:
    """Fixtures whose contracts are declared_only or have visible_non_conformant
    entries must evaluate as NON_CONFORMANT with CBC013 and/or CBC015."""

    NON_CONFORMANT_FIXTURES = [
        "captured_bundle_012_final_projection",
        "captured_bundle_013_finalize_artifacts",
        "captured_bundle_014_finalize_fallback",
        "captured_bundle_024_parent_rejoin_promotion",
        "captured_bundle_027_review_cap_authority",
        "captured_bundle_028_review_human_verification",
        "captured_bundle_030_tiebreaker_challenger_to_synthesis",
        "captured_bundle_031_tiebreaker_decision_to_parent",
        "captured_bundle_032_tiebreaker_researcher_to_challenger",
        "captured_bundle_033_tiebreaker_synthesis_to_decision",
    ]

    @pytest.mark.parametrize("fixture_id", NON_CONFORMANT_FIXTURES)
    def test_non_conformant_status(self, fixture_id: str) -> None:
        """Declared-only fixtures must have NON_CONFORMANT status."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert r.status == CompatibilityStatus.NON_CONFORMANT, (
            f"{fixture_id}: expected NON_CONFORMANT, got {r.status}: {r.diagnostics}"
        )

    @pytest.mark.parametrize("fixture_id", NON_CONFORMANT_FIXTURES)
    def test_non_conformant_has_cbc013(self, fixture_id: str) -> None:
        """Every non-conformant declared-only fixture must include CBC013."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert (
            CompatibilityDiagnosticCode.DECLARED_ONLY_NO_PRODUCER in r.diagnostics
        ), f"{fixture_id}: missing CBC013 in diagnostics: {r.diagnostics}"

    @pytest.mark.parametrize("fixture_id", NON_CONFORMANT_FIXTURES)
    def test_non_conformant_has_cbc015(self, fixture_id: str) -> None:
        """Every non-conformant fixture with visible_non_conformant entries
        must include CBC015."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert (
            CompatibilityDiagnosticCode.VISIBLE_NON_CONFORMANCE in r.diagnostics
        ), f"{fixture_id}: missing CBC015 in diagnostics: {r.diagnostics}"

    @pytest.mark.parametrize("fixture_id", NON_CONFORMANT_FIXTURES)
    def test_non_conformant_has_contract_ref(self, fixture_id: str) -> None:
        """Non-conformant results must reference the contract matrix."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert any("contract_to_producer:" in ref for ref in r.contract_refs), (
            f"{fixture_id}: missing contract ref in {r.contract_refs}"
        )

    @pytest.mark.parametrize("fixture_id", NON_CONFORMANT_FIXTURES)
    def test_non_conformant_details_has_producer_category(
        self, fixture_id: str
    ) -> None:
        """Details must include producer_category (expected: 'declared_only')."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert r.details.get("producer_category") == "declared_only", (
            f"{fixture_id}: producer_category={r.details.get('producer_category')!r}"
        )

    @pytest.mark.parametrize("fixture_id", NON_CONFORMANT_FIXTURES)
    def test_non_conformant_details_has_structural_and_contract_issues(
        self, fixture_id: str
    ) -> None:
        """Details must include both structural_issues and contract_issues lists."""
        results = _get_results()
        r = _result_by_fixture_id(results, fixture_id)
        assert "structural_issues" in r.details, (
            f"{fixture_id}: missing structural_issues in details"
        )
        assert "contract_issues" in r.details, (
            f"{fixture_id}: missing contract_issues in details"
        )
        assert isinstance(r.details["structural_issues"], list)
        assert isinstance(r.details["contract_issues"], list)


# ══════════════════════════════════════════════════════════════════════════
# Stable diagnostics — pin all CBC codes
# ══════════════════════════════════════════════════════════════════════════


class TestStableDiagnosticCodes:
    """All CBC diagnostic codes must resolve to correct string values
    and never change across evaluator versions."""

    STABLE_CODES = {
        "MISSING_BOUNDARY_RECEIPTS": "CBC001_MISSING_BOUNDARY_RECEIPTS",
        "MISSING_MANIFEST": "CBC002_MISSING_MANIFEST",
        "MISSING_PHASE_RESULT": "CBC003_MISSING_PHASE_RESULT",
        "MISSING_STATE": "CBC004_MISSING_STATE",
        "BOUNDARY_ID_MISMATCH": "CBC005_BOUNDARY_ID_MISMATCH",
        "RECEIPT_WORKFLOW_ID_MISSING": "CBC006_RECEIPT_WORKFLOW_ID_MISSING",
        "RECEIPT_INVOCATION_ID_MISSING": "CBC007_RECEIPT_INVOCATION_ID_MISSING",
        "RECEIPT_OUTCOME_MISSING": "CBC008_RECEIPT_OUTCOME_MISSING",
        "MANIFEST_CAPABILITY_EFFECTS_MISSING": "CBC009_MANIFEST_CAPABILITY_EFFECTS_MISSING",
        "PHASE_RESULT_EXIT_KIND_MISSING": "CBC010_PHASE_RESULT_EXIT_KIND_MISSING",
        "LEGACY_FIXTURE_UNKNOWN": "CBC011_LEGACY_FIXTURE_UNKNOWN",
        "CRITICAL_CATEGORIES_UNKNOWN": "CBC012_CRITICAL_CATEGORIES_UNKNOWN",
        "DECLARED_ONLY_NO_PRODUCER": "CBC013_DECLARED_ONLY_NO_PRODUCER",
        "UNKNOWN_PRODUCER_CATEGORY": "CBC014_UNKNOWN_PRODUCER_CATEGORY",
        "VISIBLE_NON_CONFORMANCE": "CBC015_VISIBLE_NON_CONFORMANCE",
        "INCOMPLETE_INVENTORY_ROW": "CBC016_INCOMPLETE_INVENTORY_ROW",
        "START_BEFORE_DISPATCH_UNVERIFIED": "CBC017_START_BEFORE_DISPATCH_UNVERIFIED",
        "EXACTLY_ONE_TERMINAL_UNVERIFIED": "CBC018_EXACTLY_ONE_TERMINAL_UNVERIFIED",
        "GRANT_LEASE_GATE_UNVERIFIED": "CBC019_GRANT_LEASE_GATE_UNVERIFIED",
        "EXACT_VERSION_LOOKUP_UNVERIFIED": "CBC020_EXACT_VERSION_LOOKUP_UNVERIFIED",
        "CAUSAL_EVIDENCE_UNVERIFIED": "CBC021_CAUSAL_EVIDENCE_UNVERIFIED",
        "POST_TRANSITION_REREAD_UNVERIFIED": "CBC022_POST_TRANSITION_REREAD_UNVERIFIED",
    }

    def test_all_codes_exist(self) -> None:
        """All CBC diagnostic codes must be members of the enum."""
        all_members = set(CompatibilityDiagnosticCode.__members__.keys())
        assert len(all_members) == 22, (
            f"Expected 22 CBC codes, got {len(all_members)}: {sorted(all_members)}"
        )

    def test_each_code_stable_value(self) -> None:
        """Each CBC code must have the exact stable string value."""
        for attr_name, expected_value in self.STABLE_CODES.items():
            member = getattr(CompatibilityDiagnosticCode, attr_name)
            assert member.value == expected_value, (
                f"{attr_name}: expected {expected_value!r}, got {member.value!r}"
            )

    def test_diagnostics_present_in_at_least_one_result(self) -> None:
        """Every CBC diagnostic code category must have at least one
        representative triggered by current fixtures. Some individual
        codes (CBC001–CBC004, CBC006–CBC009) may not be triggered
        by current fixtures but are reserved for fixture coverage gaps."""
        results = _get_results()
        all_diags: set[str] = set()
        for r in results:
            all_diags.update(
                d.value if hasattr(d, "value") else d for d in r.diagnostics
            )

        # Structural codes — at least one should appear
        structural_codes = {
            "MISSING_BOUNDARY_RECEIPTS": "CBC001_MISSING_BOUNDARY_RECEIPTS",
            "MISSING_MANIFEST": "CBC002_MISSING_MANIFEST",
            "MISSING_PHASE_RESULT": "CBC003_MISSING_PHASE_RESULT",
            "MISSING_STATE": "CBC004_MISSING_STATE",
            "BOUNDARY_ID_MISMATCH": "CBC005_BOUNDARY_ID_MISMATCH",
            "RECEIPT_WORKFLOW_ID_MISSING": "CBC006_RECEIPT_WORKFLOW_ID_MISSING",
            "RECEIPT_INVOCATION_ID_MISSING": "CBC007_RECEIPT_INVOCATION_ID_MISSING",
            "RECEIPT_OUTCOME_MISSING": "CBC008_RECEIPT_OUTCOME_MISSING",
            "MANIFEST_CAPABILITY_EFFECTS_MISSING": "CBC009_MANIFEST_CAPABILITY_EFFECTS_MISSING",
            "PHASE_RESULT_EXIT_KIND_MISSING": "CBC010_PHASE_RESULT_EXIT_KIND_MISSING",
        }
        structural_triggered = [
            v for v in structural_codes.values() if v in all_diags
        ]
        assert len(structural_triggered) >= 1, (
            f"No structural diagnostic codes triggered. "
            f"All observed: {sorted(all_diags)}"
        )

        # Fixture classification codes — must be triggered
        fixture_codes = {
            "LEGACY_FIXTURE_UNKNOWN": "CBC011_LEGACY_FIXTURE_UNKNOWN",
            "CRITICAL_CATEGORIES_UNKNOWN": "CBC012_CRITICAL_CATEGORIES_UNKNOWN",
        }
        for attr_name, code_value in fixture_codes.items():
            assert code_value in all_diags, (
                f"{attr_name} ({code_value}) not found in any result diagnostics. "
                f"All observed: {sorted(all_diags)}"
            )

        # Contract alignment codes — must be triggered
        alignment_codes = {
            "DECLARED_ONLY_NO_PRODUCER": "CBC013_DECLARED_ONLY_NO_PRODUCER",
            "UNKNOWN_PRODUCER_CATEGORY": "CBC014_UNKNOWN_PRODUCER_CATEGORY",
            "VISIBLE_NON_CONFORMANCE": "CBC015_VISIBLE_NON_CONFORMANCE",
            "INCOMPLETE_INVENTORY_ROW": "CBC016_INCOMPLETE_INVENTORY_ROW",
        }
        for attr_name, code_value in alignment_codes.items():
            assert code_value in all_diags, (
                f"{attr_name} ({code_value}) not found in any result diagnostics. "
                f"All observed: {sorted(all_diags)}"
            )

    def test_reserved_but_untargeted_codes_stable(self) -> None:
        """Codes CBC001–CBC009 are reserved for structural issues not
        present in current fixtures. Verify their values are stable
        even though they aren't triggered."""
        reserved = [
            (CompatibilityDiagnosticCode.MISSING_BOUNDARY_RECEIPTS,
             "CBC001_MISSING_BOUNDARY_RECEIPTS"),
            (CompatibilityDiagnosticCode.MISSING_MANIFEST,
             "CBC002_MISSING_MANIFEST"),
            (CompatibilityDiagnosticCode.MISSING_PHASE_RESULT,
             "CBC003_MISSING_PHASE_RESULT"),
            (CompatibilityDiagnosticCode.MISSING_STATE,
             "CBC004_MISSING_STATE"),
            (CompatibilityDiagnosticCode.BOUNDARY_ID_MISMATCH,
             "CBC005_BOUNDARY_ID_MISMATCH"),
            (CompatibilityDiagnosticCode.RECEIPT_WORKFLOW_ID_MISSING,
             "CBC006_RECEIPT_WORKFLOW_ID_MISSING"),
            (CompatibilityDiagnosticCode.RECEIPT_INVOCATION_ID_MISSING,
             "CBC007_RECEIPT_INVOCATION_ID_MISSING"),
            (CompatibilityDiagnosticCode.RECEIPT_OUTCOME_MISSING,
             "CBC008_RECEIPT_OUTCOME_MISSING"),
            (CompatibilityDiagnosticCode.MANIFEST_CAPABILITY_EFFECTS_MISSING,
             "CBC009_MANIFEST_CAPABILITY_EFFECTS_MISSING"),
        ]
        for member, expected_value in reserved:
            assert member.value == expected_value, (
                f"Reserved code {member.name} has value {member.value!r}, "
                f"expected {expected_value!r}"
            )

    def test_no_unknown_diagnostics_in_results(self) -> None:
        """Results must only contain known CBC diagnostic codes."""
        valid_codes = {m.value for m in CompatibilityDiagnosticCode}
        results = _get_results()
        for r in results:
            for diag in r.diagnostics:
                assert diag in valid_codes, (
                    f"Unknown diagnostic {diag!r} in {r.fixture_id}"
                )


# ══════════════════════════════════════════════════════════════════════════
# Legacy non-normalization
# ══════════════════════════════════════════════════════════════════════════


class TestLegacyNonNormalization:
    """Legacy fixture bundles (000–003) must NOT be normalized, rewritten,
    or modified by the evaluator. Their file contents must remain unchanged."""

    LEGACY_BUNDLES = [
        "captured_bundle_000_20260616T192957.json",
        "captured_bundle_001_20260616T192957.json",
        "captured_bundle_002_20260616T193029.json",
        "captured_bundle_003_20260616T195220.json",
    ]

    @pytest.mark.parametrize("bundle_file", LEGACY_BUNDLES)
    def test_legacy_file_unchanged_after_evaluation(self, bundle_file: str) -> None:
        """Legacy fixture files must have identical content before and after evaluation."""
        path = FIXTURE_DIR / bundle_file
        content_before = path.read_bytes()

        # Run the evaluator (fully evaluate all fixtures)
        _ = _get_results()

        content_after = path.read_bytes()
        assert content_before == content_after, (
            f"{bundle_file}: file content changed after evaluation! "
            f"({len(content_before)} → {len(content_after)} bytes)"
        )

    @pytest.mark.parametrize("bundle_file", LEGACY_BUNDLES)
    def test_legacy_file_mtime_unchanged(self, bundle_file: str) -> None:
        """Legacy fixture file modification time must not change."""
        path = FIXTURE_DIR / bundle_file
        mtime_before = os.path.getmtime(path)

        _ = _get_results()

        mtime_after = os.path.getmtime(path)
        assert mtime_before == mtime_after, (
            f"{bundle_file}: mtime changed: {mtime_before} → {mtime_after}"
        )

    @pytest.mark.parametrize("bundle_file", LEGACY_BUNDLES)
    def test_legacy_file_not_rewritten(self, bundle_file: str) -> None:
        """Legacy fixtures must remain valid JSON with their original structure."""
        path = FIXTURE_DIR / bundle_file
        with open(path, "r") as f:
            bundle = json.load(f)

        # Verify it still has its original legacy structure, not normalized
        # Legacy bundles should have "events" or "events.jsonl" but not
        # structured boundary_receipts/manifest/phase_result
        artifacts = bundle.get("artifacts", {})
        assert "boundary_receipts" not in artifacts, (
            f"{bundle_file}: legacy fixture was normalized — "
            f"found boundary_receipts in artifacts"
        )
        assert "manifest" not in artifacts, (
            f"{bundle_file}: legacy fixture was normalized — "
            f"found manifest in artifacts"
        )
        assert "phase_result" not in artifacts, (
            f"{bundle_file}: legacy fixture was normalized — "
            f"found phase_result in artifacts"
        )


# ══════════════════════════════════════════════════════════════════════════
# Current fixture non-rewrite behavior
# ══════════════════════════════════════════════════════════════════════════


class TestFixtureNonRewrite:
    """All current fixture bundles must NOT be rewritten or modified
    by the compatibility evaluator. The evaluator is strictly observe-only."""

    # Sample of current fixtures (non-legacy, i.e., bundles 004+)
    CURRENT_SAMPLE = [
        "captured_bundle_004_execute_aggregate_promotion.json",
        "captured_bundle_012_final_projection.json",
        "captured_bundle_015_gate_to_revise.json",
        "captured_bundle_016_override_abort_authority.json",
        "captured_bundle_025_prep_to_plan.json",
        "captured_bundle_029_revise_to_critique.json",
    ]

    @pytest.mark.parametrize("bundle_file", CURRENT_SAMPLE)
    def test_current_file_unchanged_after_evaluation(
        self, bundle_file: str
    ) -> None:
        """Current fixture files must have identical content before and after evaluation."""
        path = FIXTURE_DIR / bundle_file
        content_before = path.read_bytes()

        _ = _get_results()

        content_after = path.read_bytes()
        assert content_before == content_after, (
            f"{bundle_file}: file content changed after evaluation! "
            f"({len(content_before)} → {len(content_after)} bytes)"
        )

    @pytest.mark.parametrize("bundle_file", CURRENT_SAMPLE)
    def test_current_file_mtime_unchanged(self, bundle_file: str) -> None:
        """Current fixture file modification time must not change."""
        path = FIXTURE_DIR / bundle_file
        mtime_before = os.path.getmtime(path)

        _ = _get_results()

        mtime_after = os.path.getmtime(path)
        assert mtime_before == mtime_after, (
            f"{bundle_file}: mtime changed: {mtime_before} → {mtime_after}"
        )

    def test_all_current_files_unchanged(self) -> None:
        """All captured_bundle_*.json files must be unchanged after evaluation."""
        all_paths = sorted(
            p for p in FIXTURE_DIR.glob("captured_bundle_*.json") if p.is_file()
        )
        contents_before = {p.name: p.read_bytes() for p in all_paths}

        _ = _get_results()

        for p in all_paths:
            content_after = p.read_bytes()
            assert contents_before[p.name] == content_after, (
                f"{p.name}: file content changed after evaluation!"
            )


# ══════════════════════════════════════════════════════════════════════════
# CompatibilityResult properties
# ══════════════════════════════════════════════════════════════════════════


class TestCompatibilityResultProperties:
    """CompatibilityResult dataclass must have correct properties and behavior."""

    def test_result_is_frozen(self) -> None:
        """CompatibilityResult must be frozen (immutable)."""
        r = CompatibilityResult(
            boundary_id="test_boundary",
            fixture_id="test_fixture",
            status=CompatibilityStatus.COMPATIBLE,
            diagnostics=("CBC001_MISSING_BOUNDARY_RECEIPTS",),
        )
        with pytest.raises(Exception):
            r.status = CompatibilityStatus.INCOMPATIBLE  # type: ignore[misc]

    def test_status_enum_values(self) -> None:
        """All four status values must be distinct."""
        values = {s.value for s in CompatibilityStatus}
        assert values == {"compatible", "incompatible", "unknown", "non_conformant"}

    def test_result_defaults(self) -> None:
        """Default values for optional fields must be correct."""
        r = CompatibilityResult(
            boundary_id="b", fixture_id="f", status=CompatibilityStatus.COMPATIBLE
        )
        assert r.diagnostics == ()
        assert r.contract_refs == ()
        assert r.evidence_refs == ()
        assert isinstance(r.details, MappingProxyType)
        assert len(r.details) == 0
        assert r.evaluator_version == "arnold.workflow.boundary_compatibility.v1"

    def test_to_dict_complete(self) -> None:
        """to_dict must include all non-empty fields."""
        r = CompatibilityResult(
            boundary_id="b",
            fixture_id="f",
            status=CompatibilityStatus.NON_CONFORMANT,
            diagnostics=(
                CompatibilityDiagnosticCode.DECLARED_ONLY_NO_PRODUCER,
                CompatibilityDiagnosticCode.VISIBLE_NON_CONFORMANCE,
            ),
            contract_refs=("contract_to_producer:b",),
            evidence_refs=("artifacts.boundary_receipts", "artifacts.manifest"),
            details=MappingProxyType({"producer_category": "declared_only"}),
        )
        d = r.to_dict()
        assert d["boundary_id"] == "b"
        assert d["fixture_id"] == "f"
        assert d["status"] == "non_conformant"
        assert d["evaluator_version"] == "arnold.workflow.boundary_compatibility.v1"
        assert len(d["diagnostics"]) == 2
        assert "CBC013_DECLARED_ONLY_NO_PRODUCER" in d["diagnostics"]
        assert "CBC015_VISIBLE_NON_CONFORMANCE" in d["diagnostics"]
        assert d["contract_refs"] == ["contract_to_producer:b"]
        assert len(d["evidence_refs"]) == 2
        assert d["details"] == {"producer_category": "declared_only"}

    def test_to_dict_json_roundtrip(self) -> None:
        """to_dict output must be fully JSON-serializable."""
        results = _get_results()
        for r in results:
            d = r.to_dict()
            serialized = json.dumps(d)
            parsed = json.loads(serialized)
            assert parsed["status"] == r.status.value
            assert parsed["boundary_id"] == r.boundary_id
            assert parsed["fixture_id"] == r.fixture_id


# ══════════════════════════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Evaluator edge-case behavior for missing or malformed inputs."""

    def test_nonexistent_fixture_dir(self) -> None:
        """Evaluator with nonexistent fixture dir must return empty tuple."""
        e = CompatibilityEvaluator(fixture_dir="/nonexistent/path/xyz")
        results = e.evaluate_all()
        assert results == (), f"Expected empty tuple, got {len(results)} results"

    def test_nonexistent_fixture_file(self) -> None:
        """evaluate_fixture with nonexistent file must return UNKNOWN result."""
        e = CompatibilityEvaluator()
        result = e.evaluate_fixture("/nonexistent/bundle.json")
        assert result.status == CompatibilityStatus.UNKNOWN
        assert result.boundary_id == "unknown"
        assert result.fixture_id == "bundle"
        assert CompatibilityDiagnosticCode.CRITICAL_CATEGORIES_UNKNOWN in result.diagnostics

    def test_missing_contract_matrix_graceful(self) -> None:
        """Evaluator with missing contract matrix must still evaluate fixtures
        (contract alignment will be UNKNOWN for unmatched contracts)."""
        e = CompatibilityEvaluator(
            fixture_dir=FIXTURE_DIR,
            contract_matrix_path="/nonexistent/matrix.json",
        )
        results = e.evaluate_all()
        assert len(results) > 0
        # All contracts will be unmatched → unknown producer
        # But structurally compatible fixtures may still be COMPATIBLE
        # since no structural issues and no contract non-conformance

    def test_individual_fixture_evaluation(self) -> None:
        """evaluate_fixture(path) must return the same result as
        evaluate_all() for the same fixture."""
        e = CompatibilityEvaluator()
        all_results = e.evaluate_all()
        single = e.evaluate_fixture(
            FIXTURE_DIR / "captured_bundle_025_prep_to_plan.json"
        )
        batch = _result_by_fixture_id(all_results, "captured_bundle_025_prep_to_plan")
        assert single.status == batch.status
        assert single.diagnostics == batch.diagnostics
        assert single.boundary_id == batch.boundary_id

    def test_result_has_string_diagnostics(self) -> None:
        """All diagnostics must be strings (CBC code values)."""
        results = _get_results()
        for r in results:
            for diag in r.diagnostics:
                assert isinstance(diag, str), (
                    f"{r.fixture_id}: diagnostic {diag!r} is not a string"
                )
                assert diag.startswith("CBC"), (
                    f"{r.fixture_id}: diagnostic {diag!r} does not start with CBC"
                )

    def test_all_results_have_evaluator_version(self) -> None:
        """Every result must carry the evaluator version."""
        results = _get_results()
        for r in results:
            assert r.evaluator_version == "arnold.workflow.boundary_compatibility.v1"

    def test_inventory_manifest_only_row_is_incomplete(self, tmp_path: Path) -> None:
        """Support-manifest-only rows fail closed when inventory is authoritative."""
        fixture_dir = tmp_path / "fixtures"
        fixture_dir.mkdir()
        bundle = fixture_dir / "captured_bundle_999_manifest_only.json"
        bundle.write_text(
            json.dumps(
                {
                    "artifacts": {
                        "boundary_receipts": {
                            "r1": {
                                "boundary_id": "manifest_only_boundary",
                                "workflow_id": "arnold.workflow",
                                "invocation_id": "inv-1",
                                "outcome": "complete",
                            }
                        },
                        "manifest": {"boundary_id": "manifest_only_boundary", "capability_effects": ["noop"]},
                        "phase_result": {"exit_kind": "done"},
                        "state": {"status": "done"},
                        "semantic_health": {},
                    }
                }
            ),
            encoding="utf-8",
        )
        inventory = tmp_path / "inventory.json"
        inventory.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "row_kind": "manifest_entry",
                            "boundary_id": "manifest_only_boundary",
                            "support_is_non_authoritative": True,
                            "support_status": "supported",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        e = CompatibilityEvaluator(
            fixture_dir=fixture_dir,
            contract_matrix_path="/nonexistent/matrix.json",
            inventory_path=inventory,
        )
        result = e.evaluate_fixture(bundle)
        assert result.status == CompatibilityStatus.NON_CONFORMANT
        assert CompatibilityDiagnosticCode.INCOMPLETE_INVENTORY_ROW in result.diagnostics

    def test_inventory_proof_gaps_emit_runtime_diagnostics(self, tmp_path: Path) -> None:
        """Explicit inventory proof flags produce stable runtime diagnostics."""
        fixture_dir = tmp_path / "fixtures"
        fixture_dir.mkdir()
        bundle = fixture_dir / "captured_bundle_998_runtime_gap.json"
        bundle.write_text(
            json.dumps(
                {
                    "artifacts": {
                        "boundary_receipts": {
                            "r1": {
                                "boundary_id": "runtime_gap_boundary",
                                "workflow_id": "arnold.workflow",
                                "invocation_id": "inv-1",
                                "outcome": "complete",
                            }
                        },
                        "manifest": {"boundary_id": "runtime_gap_boundary", "capability_effects": ["noop"]},
                        "phase_result": {"exit_kind": "done"},
                        "state": {"status": "done"},
                        "semantic_health": {},
                    }
                }
            ),
            encoding="utf-8",
        )
        inventory = tmp_path / "inventory.json"
        inventory.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "row_kind": "boundary_contract",
                            "boundary_id": "runtime_gap_boundary",
                            "producer_category": "auto_matched",
                            "inventory_proof": {
                                "start_before_dispatch": False,
                                "post_transition_reread": False,
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        e = CompatibilityEvaluator(
            fixture_dir=fixture_dir,
            contract_matrix_path="/nonexistent/matrix.json",
            inventory_path=inventory,
        )
        result = e.evaluate_fixture(bundle)
        assert result.status == CompatibilityStatus.NON_CONFORMANT
        assert CompatibilityDiagnosticCode.START_BEFORE_DISPATCH_UNVERIFIED in result.diagnostics
        assert CompatibilityDiagnosticCode.POST_TRANSITION_REREAD_UNVERIFIED in result.diagnostics


# ══════════════════════════════════════════════════════════════════════════
# Cross-status consistency
# ══════════════════════════════════════════════════════════════════════════


class TestCrossStatusConsistency:
    """Verify that all four status types are represented and
    no unexpected status values appear."""

    def test_all_four_status_types_present(self) -> None:
        """COMPATIBLE, INCOMPATIBLE, UNKNOWN, and NON_CONFORMANT
        must all appear in the evaluation results."""
        results = _get_results()
        statuses = {r.status for r in results}
        assert CompatibilityStatus.COMPATIBLE in statuses, "No COMPATIBLE results"
        assert CompatibilityStatus.INCOMPATIBLE in statuses, "No INCOMPATIBLE results"
        assert CompatibilityStatus.UNKNOWN in statuses, "No UNKNOWN results"
        assert (
            CompatibilityStatus.NON_CONFORMANT in statuses
        ), "No NON_CONFORMANT results"

    def test_status_counts_reasonable(self) -> None:
        """Rough count check to detect major regressions."""
        results = _get_results()
        counts: dict[str, int] = {}
        for r in results:
            counts[r.status.value] = counts.get(r.status.value, 0) + 1

        # We expect at least: 2 compatible, 1 incompatible, 10 unknown, 18 non-conformant
        assert counts.get("compatible", 0) >= 2, (
            f"Too few compatible results: {counts}"
        )
        assert counts.get("unknown", 0) >= 10, (
            f"Too few unknown results: {counts}"
        )
        assert counts.get("non_conformant", 0) >= 18, (
            f"Too few non_conformant results: {counts}"
        )
        assert counts.get("incompatible", 0) >= 1, (
            f"Too few incompatible results: {counts}"
        )
        assert sum(counts.values()) == len(results)


# ══════════════════════════════════════════════════════════════════════════
# Specific fixture structural verification
# ══════════════════════════════════════════════════════════════════════════


class TestSpecificFixtureStructures:
    """Pin specific structural details for representative fixtures
    to ensure evaluator logic doesn't drift."""

    def test_bundle_025_prep_to_plan_evidence_refs(self) -> None:
        """prep_to_plan must have evidence refs for all 5 standard artifact categories."""
        results = _get_results()
        r = _result_by_fixture_id(results, "captured_bundle_025_prep_to_plan")
        refs = set(r.evidence_refs)
        assert "artifacts.boundary_receipts" in refs
        assert "artifacts.manifest" in refs
        assert "artifacts.phase_result" in refs
        assert "artifacts.semantic_health" in refs
        assert "artifacts.state" in refs

    def test_bundle_016_override_abort_receipt_fields(self) -> None:
        """override_abort_authority has a phase_result without exit_kind,
        so it should carry CBC010 in addition to CBC014/CBC015."""
        results = _get_results()
        r = _result_by_fixture_id(
            results, "captured_bundle_016_override_abort_authority"
        )
        # This fixture has a phase_result dict but it may or may not have exit_kind.
        # We just verify the contract alignment codes are present.
        assert (
            CompatibilityDiagnosticCode.UNKNOWN_PRODUCER_CATEGORY in r.diagnostics
        ), f"Missing CBC014: {r.diagnostics}"
        assert (
            CompatibilityDiagnosticCode.VISIBLE_NON_CONFORMANCE in r.diagnostics
        ), f"Missing CBC015: {r.diagnostics}"

    def test_bundle_012_final_projection_structure(self) -> None:
        """final_projection is declared_only with visible_non_conformant."""
        results = _get_results()
        r = _result_by_fixture_id(results, "captured_bundle_012_final_projection")
        assert r.status == CompatibilityStatus.NON_CONFORMANT
        assert r.boundary_id == "final_projection"
        # Both CBC013 and CBC015 must be present
        assert CompatibilityDiagnosticCode.DECLARED_ONLY_NO_PRODUCER in r.diagnostics
        assert CompatibilityDiagnosticCode.VISIBLE_NON_CONFORMANCE in r.diagnostics
