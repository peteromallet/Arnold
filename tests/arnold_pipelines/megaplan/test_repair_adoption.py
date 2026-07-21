"""Tests for repair adoption — M8A T13.

Covers:
- verify_repair_adoption with matching receipts (ADOPT)
- verify_repair_adoption with mismatched fields (QUARANTINE)
- verify_repair_adoption with non-RepairReceipt inputs (INVALID)
- verify_repair_adoption_from_view convenience wrapper
- _adopt_repair_receipts handler integration (projection metadata)
- Non-authority principle: receipt labels never become authority
- Normal execution continues despite quarantine
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold_pipelines.megaplan.custody.contracts import (
    CustodyTargetKey,
    RepairOccurrenceKey,
)
from arnold_pipelines.megaplan.custody.repair_receipt import (
    RepairReceipt,
    RepairReceiptStatus,
    build_repair_receipt,
    normalize_repair_receipt,
)
from arnold_pipelines.megaplan.orchestration.repair_adoption import (
    AdoptionCheckKind,
    AdoptionDiagnostic,
    AdoptionReport,
    AdoptionVerdict,
    verify_repair_adoption,
    verify_repair_adoption_from_view,
)


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------


def _make_target(task_id: str = "T1") -> CustodyTargetKey:
    return CustodyTargetKey(
        subject_type="plan",
        subject_id="test-plan",
        action="execute",
        target_kind="task",
        target_id=task_id,
        contract_id="contract-xyz",
    )


def _make_occurrence(attempt: int = 1) -> RepairOccurrenceKey:
    return RepairOccurrenceKey(
        environment_id="env-001",
        session_id="session-001",
        chain_id="chain-001",
        plan_revision="rev-1",
        phase="execute",
        task_id="T1",
        attempt_number=attempt,
        failure_kind="budget_exhausted",
        blocker_digest="sha256:abc123",
        coordinator_fence_token="42",
    )


def _make_matching_receipt(
    grant_id: str = "grant-abc",
    revision: str = "rev-1",
    task_contract: str = "contract-xyz",
    tree_commit: str = "abc123def",
    fence_token: int = 42,
    lease_id: str = "lease-001",
    epoch: int = 7,
    test_results: dict | None = None,
) -> RepairReceipt | None:
    return build_repair_receipt(
        target=_make_target(),
        occurrence_key=_make_occurrence(),
        run_authority_grant_id=grant_id,
        plan_revision=revision,
        phase="execute",
        task_contract=task_contract,
        subject_attempt="attempt-1",
        tree_commit=tree_commit,
        test_results=test_results or {"passed": True},
        coordinator_fence_token=fence_token,
        custody_lease_id=lease_id,
        custody_epoch=epoch,
    )


def _current_state(
    grant_id: str = "grant-abc",
    revision: str = "rev-1",
    task_contract: str = "contract-xyz",
    tree_commit: str = "abc123def",
    test_result_hash: str = "",
    fence_token: int = 42,
    lease_id: str = "lease-001",
    epoch: int = 7,
) -> dict:
    return {
        "current_grant_id": grant_id,
        "current_revision": revision,
        "current_task_contract": task_contract,
        "current_tree_commit": tree_commit,
        "current_test_result_hash": test_result_hash,
        "current_fence_token": fence_token,
        "current_lease_id": lease_id,
        "current_epoch": epoch,
    }


# ---------------------------------------------------------------------------
# ADOPT verdict — all checks pass
# ---------------------------------------------------------------------------


class TestAdoptVerdict:
    """When every evidence field matches, the verdict is ADOPT."""

    def test_all_fields_match_produces_adopt(self):
        receipt = _make_matching_receipt()
        assert receipt is not None
        ctx = _current_state(test_result_hash=receipt.payload_hash)

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.ADOPT
        assert report.passed is True
        assert len(report.failed_checks) == 0
        assert len(report.diagnostics) == 8  # all 8 checks
        assert all(d.passed for d in report.diagnostics)

    def test_adopt_report_has_deterministic_digest(self):
        receipt = _make_matching_receipt()
        assert receipt is not None
        ctx = _current_state(test_result_hash=receipt.payload_hash)

        report1 = verify_repair_adoption(receipt, **ctx)
        report2 = verify_repair_adoption(receipt, **ctx)

        assert report1.report_digest == report2.report_digest
        assert report1.report_digest.startswith("sha256:")

    def test_adopt_sets_correct_receipt_id(self):
        receipt = _make_matching_receipt()
        assert receipt is not None
        ctx = _current_state(test_result_hash=receipt.payload_hash)

        report = verify_repair_adoption(receipt, **ctx)

        assert report.receipt_id == receipt.receipt_id
        assert report.receipt_id != ""


# ---------------------------------------------------------------------------
# QUARANTINE verdict — field mismatches
# ---------------------------------------------------------------------------


class TestQuarantineVerdict:
    """When any evidence field mismatches, the verdict is QUARANTINE."""

    def test_grant_mismatch_produces_quarantine(self):
        receipt = _make_matching_receipt(grant_id="grant-abc")
        assert receipt is not None
        ctx = _current_state(grant_id="grant-different")

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        assert report.passed is False
        assert len(report.failed_checks) >= 1
        grant_diag = [d for d in report.failed_checks if d.kind == AdoptionCheckKind.GRANT]
        assert len(grant_diag) == 1
        assert "grant" in grant_diag[0].detail.lower()

    def test_revision_mismatch_produces_quarantine(self):
        receipt = _make_matching_receipt(revision="rev-1")
        assert receipt is not None
        ctx = _current_state(revision="rev-2")

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        rev_diag = [d for d in report.failed_checks if d.kind == AdoptionCheckKind.REVISION]
        assert len(rev_diag) == 1

    def test_task_contract_mismatch_produces_quarantine(self):
        receipt = _make_matching_receipt(task_contract="contract-xyz")
        assert receipt is not None
        ctx = _current_state(task_contract="contract-abc")

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        tc_diag = [d for d in report.failed_checks if d.kind == AdoptionCheckKind.TASK_CONTRACT]
        assert len(tc_diag) == 1

    def test_tree_commit_mismatch_produces_quarantine(self):
        receipt = _make_matching_receipt(tree_commit="abc123def")
        assert receipt is not None
        ctx = _current_state(tree_commit="999different")

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        tree_diag = [d for d in report.failed_checks if d.kind == AdoptionCheckKind.TREE_COMMIT]
        assert len(tree_diag) == 1

    def test_test_result_hash_mismatch_produces_quarantine(self):
        receipt = _make_matching_receipt(test_results={"passed": True})
        assert receipt is not None
        # The receipt's payload_hash encodes the test results; a different
        # current_test_result_hash triggers a mismatch.
        ctx = _current_state(test_result_hash="different-hash")

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        tr_diag = [d for d in report.failed_checks if d.kind == AdoptionCheckKind.TEST_RESULT_HASH]
        assert len(tr_diag) == 1

    def test_fence_mismatch_produces_quarantine(self):
        receipt = _make_matching_receipt(fence_token=42)
        assert receipt is not None
        ctx = _current_state(fence_token=99)

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        fence_diag = [d for d in report.failed_checks if d.kind == AdoptionCheckKind.FENCE]
        assert len(fence_diag) == 1

    def test_lease_mismatch_produces_quarantine(self):
        receipt = _make_matching_receipt(lease_id="lease-001")
        assert receipt is not None
        ctx = _current_state(lease_id="lease-002")

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        lease_diag = [d for d in report.failed_checks if d.kind == AdoptionCheckKind.LEASE]
        assert len(lease_diag) == 1

    def test_epoch_mismatch_produces_quarantine(self):
        receipt = _make_matching_receipt(epoch=7)
        assert receipt is not None
        ctx = _current_state(epoch=8)

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        epoch_diag = [d for d in report.failed_checks if d.kind == AdoptionCheckKind.EPOCH]
        assert len(epoch_diag) == 1

    def test_multiple_mismatches_all_reported(self):
        """All mismatched fields appear in failed_checks, not just the first."""
        receipt = _make_matching_receipt(
            grant_id="grant-abc",
            revision="rev-1",
            task_contract="contract-xyz",
        )
        assert receipt is not None
        ctx = _current_state(
            grant_id="different-grant",
            revision="different-rev",
            task_contract="different-contract",
        )

        report = verify_repair_adoption(receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        failed_kinds = {d.kind for d in report.failed_checks}
        assert AdoptionCheckKind.GRANT in failed_kinds
        assert AdoptionCheckKind.REVISION in failed_kinds
        assert AdoptionCheckKind.TASK_CONTRACT in failed_kinds


# ---------------------------------------------------------------------------
# INVALID verdict — structural guards
# ---------------------------------------------------------------------------


class TestInvalidVerdict:
    """Non-RepairReceipt or empty-receipt-id inputs produce INVALID."""

    def test_non_repair_receipt_input_is_invalid(self):
        report = verify_repair_adoption(
            {"not": "a receipt"},
            **_current_state(),
        )
        assert report.verdict == AdoptionVerdict.INVALID
        assert report.receipt_id == ""
        assert len(report.diagnostics) == 0

    def test_none_input_is_invalid(self):
        report = verify_repair_adoption(None, **_current_state())
        assert report.verdict == AdoptionVerdict.INVALID

    def test_string_input_is_invalid(self):
        report = verify_repair_adoption("not-a-receipt", **_current_state())
        assert report.verdict == AdoptionVerdict.INVALID

    def test_empty_receipt_id_is_invalid(self):
        # Build a receipt-like dict with empty receipt_id, then normalize.
        # The normalize_repair_receipt function will reject it.
        payload = {
            "receipt_id": "",
            "status": "attempt",
            "target": {
                "subject_type": "plan",
                "subject_id": "test-plan",
                "action": "execute",
                "target_kind": "task",
                "target_id": "T1",
                "contract_id": "contract-xyz",
            },
            "occurrence_key": {
                "environment_id": "env-001",
                "session_id": "session-001",
                "chain_id": "chain-001",
                "plan_revision": "rev-1",
                "phase": "execute",
                "task_id": "T1",
                "attempt_number": 1,
                "failure_kind": "budget_exhausted",
                "blocker_digest": "",
                "coordinator_fence_token": "42",
            },
            "run_authority_grant_id": "grant-abc",
            "plan_revision": "rev-1",
            "phase": "execute",
            "task_contract": "contract-xyz",
            "subject_attempt": "attempt-1",
            "tree_commit": "abc123def",
        }
        receipt = normalize_repair_receipt(payload)
        # Empty receipt_id should cause normalize_repair_receipt to return None
        # because RepairReceipt.__post_init__ requires non-empty receipt_id.
        assert receipt is None, (
            "normalize_repair_receipt should reject empty receipt_id"
        )

    def test_invalid_report_has_no_diagnostics(self):
        report = verify_repair_adoption([1, 2, 3], **_current_state())
        assert report.verdict == AdoptionVerdict.INVALID
        assert len(report.diagnostics) == 0
        assert report.receipt_id == ""


# ---------------------------------------------------------------------------
# verify_repair_adoption_from_view
# ---------------------------------------------------------------------------


class TestVerifyFromView:
    """The convenience wrapper derives task_contract/tree_commit/test_result_hash
    from the receipt itself for self-consistency."""

    def test_view_matching_receipt_produces_adopt(self):
        receipt = _make_matching_receipt()
        assert receipt is not None

        report = verify_repair_adoption_from_view(
            receipt,
            current_grant_id="grant-abc",
            current_revision="rev-1",
            current_fence_token=42,
            lease_id="lease-001",
            lease_epoch=7,
        )

        assert report.verdict == AdoptionVerdict.ADOPT

    def test_view_grant_mismatch_produces_quarantine(self):
        receipt = _make_matching_receipt(grant_id="grant-abc")
        assert receipt is not None

        report = verify_repair_adoption_from_view(
            receipt,
            current_grant_id="different-grant",
            current_revision="rev-1",
            current_fence_token=42,
            lease_id="lease-001",
            lease_epoch=7,
        )

        assert report.verdict == AdoptionVerdict.QUARANTINE

    def test_view_non_receipt_is_invalid(self):
        report = verify_repair_adoption_from_view(
            {"not": "receipt"},
            current_grant_id="grant-abc",
            current_revision="rev-1",
        )
        assert report.verdict == AdoptionVerdict.INVALID


# ---------------------------------------------------------------------------
# _adopt_repair_receipts handler integration
# ---------------------------------------------------------------------------


class TestAdoptRepairReceiptsHandler:
    """Test the handler-level _adopt_repair_receipts function.

    These tests use temporary plan directories with receipt files to
    verify the full adopt/quarantine/invalid projection flow.
    """

    def _write_receipt_artifact(
        self,
        plan_dir: Path,
        receipt: RepairReceipt,
        filename: str = "repair_receipts.json",
    ) -> None:
        """Write a receipt as a JSON artifact in the plan directory."""
        payload = {
            "receipt_id": receipt.receipt_id,
            "status": receipt.status.value,
            "target": {
                "subject_type": receipt.target.subject_type,
                "subject_id": receipt.target.subject_id,
                "action": receipt.target.action,
                "target_kind": receipt.target.target_kind,
                "target_id": receipt.target.target_id,
                "contract_id": receipt.target.contract_id,
            },
            "occurrence_key": {
                "environment_id": receipt.occurrence_key.environment_id,
                "session_id": receipt.occurrence_key.session_id,
                "chain_id": receipt.occurrence_key.chain_id,
                "plan_revision": receipt.occurrence_key.plan_revision,
                "phase": receipt.occurrence_key.phase,
                "task_id": receipt.occurrence_key.task_id,
                "attempt_number": receipt.occurrence_key.attempt_number,
                "failure_kind": receipt.occurrence_key.failure_kind,
                "blocker_digest": receipt.occurrence_key.blocker_digest,
                "coordinator_fence_token": receipt.occurrence_key.coordinator_fence_token,
            },
            "run_authority_grant_id": receipt.run_authority_grant_id,
            "plan_revision": receipt.plan_revision,
            "phase": receipt.phase,
            "task_contract": receipt.task_contract,
            "subject_attempt": receipt.subject_attempt,
            "wbc_attempt_reference": receipt.wbc_attempt_reference,
            "tree_commit": receipt.tree_commit,
            "test_results": dict(receipt.test_results) if receipt.test_results else {},
            "blocker_hash": receipt.blocker_hash,
            "coordinator_fence_token": receipt.coordinator_fence_token,
            "custody_lease_id": receipt.custody_lease_id,
            "custody_epoch": receipt.custody_epoch,
            "causal_predecessor": receipt.causal_predecessor,
            "occurred_at": receipt.occurred_at,
            "recorded_by": dict(receipt.recorded_by) if receipt.recorded_by else {},
        }
        (plan_dir / filename).write_text(json.dumps(payload))

    def _make_minimal_state(self, project_dir: str) -> dict:
        return {
            "meta": {
                "run_authority_grant_id": "grant-abc",
                "coordinator_fence_token": 42,
                "custody_lease_id": "lease-001",
                "custody_epoch": 7,
            },
            "config": {
                "project_dir": project_dir,
            },
        }

    def _make_minimal_finalize(self) -> dict:
        return {
            "plan_revision": "rev-1",
            "task_contract": "contract-xyz",
        }

    def test_no_receipts_returns_unchanged_response(self):
        from arnold_pipelines.megaplan.handlers.execute import _adopt_repair_receipts

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = self._make_minimal_state(tmpdir)
            finalize = self._make_minimal_finalize()
            original_response = {"result": "success"}

            result = _adopt_repair_receipts(plan_dir, state, finalize, original_response)

            assert result is original_response
            assert "_repair_adoption" not in result

    def test_matching_receipt_is_adopted(self):
        from arnold_pipelines.megaplan.handlers.execute import _adopt_repair_receipts

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = self._make_minimal_state(tmpdir)

            receipt = _make_matching_receipt()
            assert receipt is not None
            self._write_receipt_artifact(plan_dir, receipt)

            # Include the receipt's payload_hash in finalize data so the
            # test_result_hash check passes.
            finalize = self._make_minimal_finalize()
            finalize["test_result_hash"] = receipt.payload_hash

            # Patch git HEAD to return the matching tree_commit.
            with patch(
                "arnold_pipelines.megaplan.handlers.execute._best_effort_git_head_for_circuit",
                return_value="abc123def",
            ):
                result = _adopt_repair_receipts(plan_dir, state, finalize, {"result": "ok"})

            assert result is not None
            adoption = result.get("_repair_adoption")
            assert adoption is not None
            assert adoption["total_receipts"] == 1
            assert adoption["adopted"] == 1
            assert adoption["quarantined"] == 0
            assert adoption["invalid"] == 0
            assert "adopted_reports" in adoption
            assert len(adoption["adopted_reports"]) == 1
            adopted_report = adoption["adopted_reports"][0]
            assert adopted_report["verdict"] == "adopt"

    def test_mismatched_receipt_is_quarantined(self):
        from arnold_pipelines.megaplan.handlers.execute import _adopt_repair_receipts

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = self._make_minimal_state(tmpdir)
            # State has grant-abc but we'll make the receipt have grant-different
            # but write a matching receipt file. The _derive_adoption_context
            # uses state meta for grant_id.
            finalize = self._make_minimal_finalize()

            receipt = _make_matching_receipt(grant_id="grant-different")
            assert receipt is not None
            self._write_receipt_artifact(plan_dir, receipt)

            with patch(
                "arnold_pipelines.megaplan.handlers.execute._best_effort_git_head_for_circuit",
                return_value="abc123def",
            ):
                result = _adopt_repair_receipts(plan_dir, state, finalize, {"result": "ok"})

            assert result is not None
            adoption = result.get("_repair_adoption")
            assert adoption is not None
            assert adoption["total_receipts"] == 1
            assert adoption["adopted"] == 0
            assert adoption["quarantined"] == 1
            assert adoption["invalid"] == 0
            assert "quarantined_reports" in adoption
            q_report = adoption["quarantined_reports"][0]
            assert q_report["verdict"] == "quarantine"

            # Normal execution continues — not blocked.
            assert result["result"] == "ok"
            assert isinstance(result.get("warnings"), list)

    def test_non_receipt_json_is_invalid(self):
        from arnold_pipelines.megaplan.handlers.execute import _adopt_repair_receipts

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = self._make_minimal_state(tmpdir)
            finalize = self._make_minimal_finalize()

            # Write a JSON file that is not a valid receipt.
            (plan_dir / "repair_receipts.json").write_text(
                json.dumps({"not": "a receipt", "receipt_id": ""})
            )

            with patch(
                "arnold_pipelines.megaplan.handlers.execute._best_effort_git_head_for_circuit",
                return_value="abc123def",
            ):
                result = _adopt_repair_receipts(plan_dir, state, finalize, {"result": "ok"})

            assert result is not None
            adoption = result.get("_repair_adoption")
            # The file contains a dict but normalize_repair_receipt returns None
            # because required fields are missing, so no receipts are collected.
            assert adoption is None or adoption["total_receipts"] == 0

    def test_multiple_receipts_mixed_outcomes(self):
        from arnold_pipelines.megaplan.handlers.execute import _adopt_repair_receipts

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = self._make_minimal_state(tmpdir)
            finalize = self._make_minimal_finalize()

            # Matching receipt.
            matching = _make_matching_receipt()
            assert matching is not None
            self._write_receipt_artifact(plan_dir, matching, "repair_receipts.json")

            # Also write a mismatched receipt in the directory.
            receipts_dir = plan_dir / "repair_receipts"
            receipts_dir.mkdir()
            mismatched = _make_matching_receipt(grant_id="grant-different")
            assert mismatched is not None
            self._write_receipt_artifact(receipts_dir, mismatched, "receipt_002.json")

            # Set test_result_hash to match the matching receipt's payload_hash.
            finalize["test_result_hash"] = matching.payload_hash

            with patch(
                "arnold_pipelines.megaplan.handlers.execute._best_effort_git_head_for_circuit",
                return_value="abc123def",
            ):
                result = _adopt_repair_receipts(plan_dir, state, finalize, {"result": "ok"})

            assert result is not None
            adoption = result.get("_repair_adoption")
            assert adoption is not None
            assert adoption["total_receipts"] == 2
            assert adoption["adopted"] == 1
            assert adoption["quarantined"] == 1
            assert adoption["invalid"] == 0
            # Normal execution continues.
            assert result["result"] == "ok"

    def test_none_response_creates_new_dict(self):
        from arnold_pipelines.megaplan.handlers.execute import _adopt_repair_receipts

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = self._make_minimal_state(tmpdir)
            finalize = self._make_minimal_finalize()

            receipt = _make_matching_receipt()
            assert receipt is not None
            self._write_receipt_artifact(plan_dir, receipt)
            finalize["test_result_hash"] = receipt.payload_hash

            with patch(
                "arnold_pipelines.megaplan.handlers.execute._best_effort_git_head_for_circuit",
                return_value="abc123def",
            ):
                result = _adopt_repair_receipts(plan_dir, state, finalize, None)

            assert result is not None
            assert isinstance(result, dict)
            assert "_repair_adoption" in result

    def test_receipt_labels_not_authority(self):
        """Receipt status labels (ATTEMPT, ACCEPTED, REJECTED, etc.) do NOT
        determine adoption. Only evidence field matching through the verifier
        matters."""
        receipt = _make_matching_receipt()
        assert receipt is not None

        # Give the receipt an ACCEPTED status — this should NOT cause it to be adopted.
        accepted_receipt = build_repair_receipt(
            target=_make_target(),
            occurrence_key=_make_occurrence(),
            run_authority_grant_id="grant-abc",
            plan_revision="rev-1",
            phase="execute",
            task_contract="contract-xyz",
            subject_attempt="attempt-1",
            tree_commit="abc123def",
            test_results={"passed": True},
            coordinator_fence_token=42,
            custody_lease_id="lease-001",
            custody_epoch=7,
            status=RepairReceiptStatus.ACCEPTED,
        )
        assert accepted_receipt is not None

        # Even with ACCEPTED status, if evidence mismatches → QUARANTINE.
        ctx = _current_state(grant_id="different-grant")
        report = verify_repair_adoption(accepted_receipt, **ctx)

        assert report.verdict == AdoptionVerdict.QUARANTINE
        # The receipt's ACCEPTED label did NOT override the evidence mismatch.

        # Conversely, a REJECTED receipt with matching evidence → ADOPT.
        rejected_receipt = build_repair_receipt(
            target=_make_target(),
            occurrence_key=_make_occurrence(),
            run_authority_grant_id="grant-abc",
            plan_revision="rev-1",
            phase="execute",
            task_contract="contract-xyz",
            subject_attempt="attempt-1",
            tree_commit="abc123def",
            test_results={"passed": True},
            coordinator_fence_token=42,
            custody_lease_id="lease-001",
            custody_epoch=7,
            status=RepairReceiptStatus.REJECTED,
        )
        assert rejected_receipt is not None

        ctx_match = _current_state(test_result_hash=rejected_receipt.payload_hash)
        report2 = verify_repair_adoption(rejected_receipt, **ctx_match)
        assert report2.verdict == AdoptionVerdict.ADOPT
        # The REJECTED label did not block adoption — only evidence matters.


# ---------------------------------------------------------------------------
# AdoptionDiagnostic
# ---------------------------------------------------------------------------


class TestAdoptionDiagnostic:
    def test_passed_diagnostic_has_empty_detail(self):
        diag = AdoptionDiagnostic(
            kind=AdoptionCheckKind.GRANT,
            passed=True,
            expected="grant-abc",
            actual="grant-abc",
        )
        assert diag.detail == ""
        assert diag.passed is True

    def test_failed_diagnostic_has_detail(self):
        diag = AdoptionDiagnostic(
            kind=AdoptionCheckKind.GRANT,
            passed=False,
            expected="grant-abc",
            actual="grant-xyz",
            detail="grant mismatch: receipt claims 'grant-xyz', current is 'grant-abc'",
        )
        assert diag.detail != ""
        assert diag.passed is False

    def test_to_dict_includes_all_fields(self):
        diag = AdoptionDiagnostic(
            kind=AdoptionCheckKind.LEASE,
            passed=False,
            expected="lease-001",
            actual="lease-002",
            detail="lease mismatch: receipt claims 'lease-002', current is 'lease-001'",
        )
        d = diag.to_dict()
        assert d["kind"] == "lease"
        assert d["passed"] is False
        assert d["expected"] == "lease-001"
        assert d["actual"] == "lease-002"
        assert "mismatch" in d["detail"]


# ---------------------------------------------------------------------------
# AdoptionReport
# ---------------------------------------------------------------------------


class TestAdoptionReport:
    def test_passed_property_true_for_adopt(self):
        report = AdoptionReport(
            verdict=AdoptionVerdict.ADOPT,
            receipt_id="rec-123",
            diagnostics=(),
        )
        assert report.passed is True

    def test_passed_property_false_for_quarantine(self):
        report = AdoptionReport(
            verdict=AdoptionVerdict.QUARANTINE,
            receipt_id="rec-123",
            diagnostics=(),
        )
        assert report.passed is False

    def test_passed_property_false_for_invalid(self):
        report = AdoptionReport(
            verdict=AdoptionVerdict.INVALID,
            receipt_id="",
            diagnostics=(),
        )
        assert report.passed is False

    def test_failed_checks_filters_passed(self):
        diag_pass = AdoptionDiagnostic(
            kind=AdoptionCheckKind.GRANT,
            passed=True,
            expected="g",
            actual="g",
        )
        diag_fail = AdoptionDiagnostic(
            kind=AdoptionCheckKind.LEASE,
            passed=False,
            expected="l1",
            actual="l2",
            detail="mismatch",
        )
        report = AdoptionReport(
            verdict=AdoptionVerdict.QUARANTINE,
            receipt_id="rec-1",
            diagnostics=(diag_pass, diag_fail),
        )
        assert len(report.failed_checks) == 1
        assert report.failed_checks[0].kind == AdoptionCheckKind.LEASE

    def test_to_dict_includes_digest(self):
        report = AdoptionReport(
            verdict=AdoptionVerdict.ADOPT,
            receipt_id="rec-1",
            diagnostics=(),
        )
        d = report.to_dict()
        assert d["verdict"] == "adopt"
        assert d["receipt_id"] == "rec-1"
        assert d["report_digest"].startswith("sha256:")
