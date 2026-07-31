"""Tests exercising real_producer_cases.bundle.json through semantic-health inspection.

Each real-producer case writes its inline artifact data (state, phase_result,
boundary_receipts, and stub artifact files) into a temporary plan directory,
then calls ``inspect_semantic_health``.

- Healthy cases must produce no ERROR-severity findings for their own boundary.
- Broken cases document which corruptions semantic-health can detect;
  deep structural compatibility checking is the domain of
  ``CompatibilityEvaluator`` (test_boundary_compatibility_replay.py).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from arnold.workflow.boundary_compatibility import (
    CompatibilityDiagnosticCode,
    CompatibilityEvaluator,
    CompatibilityStatus,
)
from arnold.workflow.boundary_evidence import FindingSeverity, SemanticFinding
from arnold_pipelines.megaplan.semantic_health import inspect_semantic_health


# ── helpers ────────────────────────────────────────────────────────────────

BUNDLE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures"
    / "workflow_boundary_contracts"
    / "real_producer_cases.bundle.json"
)


def _load_bundle():
    """Load the real_producer_cases bundle and return its cases list."""
    with open(BUNDLE_PATH, encoding="utf-8") as handle:
        data = json.load(handle)
    return data["cases"]


def _write_case_artifacts(case: dict, plan_dir: Path) -> None:
    """Write a case's inline artifact data into *plan_dir*.

    Writes ``state.json``, ``phase_result.json``, every entry in
    ``boundary_receipts/``, and empty stub files for required artifacts
    listed in the manifest so that semantic-health inspection does not
    report missing-artifact errors for the boundary under test.
    """
    plan_dir.mkdir(parents=True, exist_ok=True)
    artifacts = case["artifacts"]

    # state.json
    state_data = artifacts.get("state")
    if isinstance(state_data, dict):
        (plan_dir / "state.json").write_text(
            json.dumps(state_data), encoding="utf-8"
        )

    # phase_result.json
    pr_data = artifacts.get("phase_result")
    if isinstance(pr_data, dict):
        (plan_dir / "phase_result.json").write_text(
            json.dumps(pr_data), encoding="utf-8"
        )

    # boundary_receipts/
    receipts = artifacts.get("boundary_receipts")
    if isinstance(receipts, dict):
        receipt_dir = plan_dir / "boundary_receipts"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        for filename, receipt_data in receipts.items():
            (receipt_dir / filename).write_text(
                json.dumps(receipt_data), encoding="utf-8"
            )

    # Stub required artifact files so the case's own boundary does not
    # produce missing-artifact ERROR findings.  The manifest's
    # artifact_refs list tells us which files the boundary contract
    # declares as required.
    manifest = artifacts.get("manifest")
    if isinstance(manifest, dict):
        for ref in manifest.get("artifact_refs") or []:
            stub = plan_dir / ref
            if not stub.exists():
                stub.write_text("", encoding="utf-8")

    # Stub human_verifications.json for review_human_verification boundary.
    # Semantic-health requires this authority evidence file when the boundary
    # contract includes human-verification semantics.
    boundary_id = case.get("boundary_id", "")
    if boundary_id == "review_human_verification":
        hv_path = plan_dir / "human_verifications.json"
        if not hv_path.exists():
            hv_path.write_text("[]", encoding="utf-8")


def _error_findings(findings: list[SemanticFinding]) -> list[SemanticFinding]:
    """Return only ERROR-severity findings."""
    return [f for f in findings if f.severity == FindingSeverity.ERROR]


# ── bundle load ────────────────────────────────────────────────────────────

ALL_CASES = _load_bundle()
HEALTHY_CASES = [c for c in ALL_CASES if c.get("case_type") == "healthy"]
BROKEN_CASES = [c for c in ALL_CASES if c.get("case_type") == "broken"]

# ── structural preconditions ───────────────────────────────────────────────

class TestBundleStructure:
    """Verify the bundle itself is well-formed before running semantic-health."""

    def test_bundle_has_sixteen_cases(self) -> None:
        assert len(ALL_CASES) == 16, f"expected 16 cases, got {len(ALL_CASES)}"

    def test_bundle_has_eight_healthy_cases(self) -> None:
        assert len(HEALTHY_CASES) == 8, f"expected 8 healthy, got {len(HEALTHY_CASES)}"

    def test_bundle_has_eight_broken_cases(self) -> None:
        assert len(BROKEN_CASES) == 8, f"expected 8 broken, got {len(BROKEN_CASES)}"

    @pytest.mark.parametrize("case", HEALTHY_CASES, ids=lambda c: c["case_id"])
    def test_healthy_case_has_expected_compatible(self, case: dict) -> None:
        assert case.get("expected_compatibility") == "compatible", (
            f"{case['case_id']}: expected_compatibility must be 'compatible'"
        )

    @pytest.mark.parametrize("case", BROKEN_CASES, ids=lambda c: c["case_id"])
    def test_broken_case_has_expected_incompatible(self, case: dict) -> None:
        assert case.get("expected_compatibility") in ("incompatible", "unknown"), (
            f"{case['case_id']}: broken cases must be incompatible or unknown"
        )

    @pytest.mark.parametrize("case", BROKEN_CASES, ids=lambda c: c["case_id"])
    def test_broken_case_has_corruption_record(self, case: dict) -> None:
        corruption = case.get("corruption")
        assert isinstance(corruption, dict), (
            f"{case['case_id']}: broken case must have a corruption dict"
        )
        assert "corruption_id" in corruption
        assert "target_relation" in corruption
        assert "description" in corruption

    def test_required_phase_families_present(self) -> None:
        required = {
            "prep", "plan_revise", "critique_gate", "tiebreaker",
            "execute", "finalize", "review", "override",
        }
        present = {c["phase_family"] for c in ALL_CASES}
        missing = required - present
        assert not missing, f"Missing phase families: {missing}"

    def test_each_phase_family_has_one_healthy_one_broken(self) -> None:
        from collections import Counter
        healthy_counts = Counter(c["phase_family"] for c in HEALTHY_CASES)
        broken_counts = Counter(c["phase_family"] for c in BROKEN_CASES)
        for family in {c["phase_family"] for c in ALL_CASES}:
            assert healthy_counts[family] == 1, (
                f"{family}: expected 1 healthy, got {healthy_counts[family]}"
            )
            assert broken_counts[family] == 1, (
                f"{family}: expected 1 broken, got {broken_counts[family]}"
            )


# ── semantic-health inspection ─────────────────────────────────────────────


class TestHealthyCasesSemanticHealth:
    """Healthy cases must produce no ERROR-severity findings for their own boundary."""

    @pytest.mark.parametrize("case", HEALTHY_CASES, ids=lambda c: c["case_id"])
    def test_healthy_case_no_error_findings(self, case: dict) -> None:
        boundary_id = case["boundary_id"]
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            _write_case_artifacts(case, plan_dir)
            findings = inspect_semantic_health(plan_dir)
            own_findings = [f for f in findings if f.boundary_id == boundary_id]
            errors = _error_findings(own_findings)
            assert not errors, (
                f"{case['case_id']} ({boundary_id}): "
                f"unexpected ERROR findings for own boundary: "
                + "; ".join(f"{f.finding_id}: {f.description}" for f in errors)
            )


class TestBrokenCasesSemanticHealth:
    """Broken cases demonstrate that semantic-health inspection runs without
    crashing and that findings are structurally valid SemanticFinding objects.

    Deep structural compatibility (CBC diagnostic codes) is the domain of
    ``CompatibilityEvaluator``, tested in ``test_boundary_compatibility_replay.py``.
    This class verifies that semantic-health can at least load, materialize,
    and inspect every broken case without exceptions.
    """

    @pytest.mark.parametrize("case", BROKEN_CASES, ids=lambda c: c["case_id"])
    def test_broken_case_inspects_without_exception(self, case: dict) -> None:
        """Every broken case must survive inspection without raising."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            _write_case_artifacts(case, plan_dir)
            findings = inspect_semantic_health(plan_dir)
            assert isinstance(findings, list)
            for f in findings:
                assert isinstance(f, SemanticFinding)
                assert f.finding_id
                assert f.boundary_id

    @pytest.mark.parametrize("case", BROKEN_CASES, ids=lambda c: c["case_id"])
    def test_broken_case_has_exact_structural_compatibility_diagnostics(
        self,
        case: dict,
        tmp_path: Path,
    ) -> None:
        """CompatibilityEvaluator is the canonical owner of fixture corruption."""
        expected = tuple(case["expected_diagnostics"])
        assert expected, f"{case['case_id']}: broken case needs explicit diagnostics"
        known_diagnostics = {member.value for member in CompatibilityDiagnosticCode}
        assert all(code in known_diagnostics for code in expected)

        fixture_path = tmp_path / f"{case['case_id']}.json"
        fixture_path.write_text(json.dumps(case), encoding="utf-8")
        result = CompatibilityEvaluator().evaluate_fixture(fixture_path)

        assert result.status is not CompatibilityStatus.COMPATIBLE
        assert tuple(result.details["structural_issues"]) == expected

    @pytest.mark.parametrize("case", BROKEN_CASES, ids=lambda c: c["case_id"])
    def test_broken_case_findings_are_well_formed(self, case: dict) -> None:
        """Every finding produced must carry required fields."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            _write_case_artifacts(case, plan_dir)
            findings = inspect_semantic_health(plan_dir)
            for f in findings:
                assert f.finding_id, f"finding missing finding_id in {case['case_id']}"
                assert f.boundary_id, f"finding missing boundary_id in {case['case_id']}"
                assert f.severity in FindingSeverity, (
                    f"bad severity {f.severity} in {case['case_id']}"
                )
                assert f.description, f"finding missing description in {case['case_id']}"


class TestRealProducerCasesMaterialized:
    """Verify that all 16 cases can be materialized and inspected."""

    @pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c["case_id"])
    def test_case_materializes_and_inspects(self, case: dict) -> None:
        """Every case must materialize without exception and return findings."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            _write_case_artifacts(case, plan_dir)
            findings = inspect_semantic_health(plan_dir)
            assert isinstance(findings, list)
            for f in findings:
                assert isinstance(f, SemanticFinding)
                assert f.finding_id
                assert f.boundary_id
                assert f.severity in FindingSeverity
