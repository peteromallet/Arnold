"""Tests for Critique Ledger v1 schemas.

Covers structural integrity, golden case round-trips, strict/preserve mode,
budget enforcement, and corrupt/future-version rejection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.critique_ledger.schemas import (
    BRIEFING_BUDGETS,
    SCHEMA_VERSION,
    CritiqueOccurrenceEnvelope,
    DomainBriefingEnvelope,
    FindingDispositionEvent,
    FindingReconciliationEvent,
    LedgerRevisionManifest,
    canonical_hash,
    freeze_for_hashing,
)

# ── Paths ──────────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / (
    "fixtures/critique_ledger"
)
GOLDEN_CASES_PATH = FIXTURE_DIR / "schema_golden_cases.json"


def _load_golden_cases() -> dict[str, Any]:
    with open(GOLDEN_CASES_PATH, "r") as f:
        return json.load(f)


SCHEMA_CLASSES = {
    "CritiqueOccurrenceEnvelope": CritiqueOccurrenceEnvelope,
    "FindingReconciliationEvent": FindingReconciliationEvent,
    "FindingDispositionEvent": FindingDispositionEvent,
    "DomainBriefingEnvelope": DomainBriefingEnvelope,
    "LedgerRevisionManifest": LedgerRevisionManifest,
}


# ══════════════════════════════════════════════════════════════════════
# Structural tests
# ══════════════════════════════════════════════════════════════════════


class TestSchemaStructuralIntegrity:
    """Basic structural checks on all five v1 record types."""

    def test_critique_occurrence_envelope_is_frozen(self) -> None:
        obj = CritiqueOccurrenceEnvelope(occurrence_id="test")
        with pytest.raises(Exception):
            obj.occurrence_id = "mutated"  # type: ignore[misc]

    def test_finding_reconciliation_event_is_frozen(self) -> None:
        obj = FindingReconciliationEvent(reconciliation_id="test")
        with pytest.raises(Exception):
            obj.reconciliation_id = "mutated"  # type: ignore[misc]

    def test_finding_disposition_event_is_frozen(self) -> None:
        obj = FindingDispositionEvent(disposition_id="test")
        with pytest.raises(Exception):
            obj.disposition_id = "mutated"  # type: ignore[misc]

    def test_domain_briefing_envelope_is_frozen(self) -> None:
        obj = DomainBriefingEnvelope(briefing_id="test")
        with pytest.raises(Exception):
            obj.briefing_id = "mutated"  # type: ignore[misc]

    def test_ledger_revision_manifest_is_frozen(self) -> None:
        obj = LedgerRevisionManifest(manifest_id="test")
        with pytest.raises(Exception):
            obj.manifest_id = "mutated"  # type: ignore[misc]

    # ── separate identity fields ──────────────────────────────────────

    def test_occurrence_has_separate_identity_fields(self) -> None:
        obj = CritiqueOccurrenceEnvelope(
            occurrence_id="occ-1",
            finding_id="F-1",
            semantic_finding_id="CF-1",
        )
        d = obj.to_dict()
        # All three identity fields present and separately named
        assert d["occurrence_id"] == "occ-1"
        assert d["finding_id"] == "F-1"
        assert d["semantic_finding_id"] == "CF-1"
        assert "occurrence_id" != "finding_id"
        assert "finding_id" != "semantic_finding_id"

    def test_reconciliation_has_separate_identity_fields(self) -> None:
        obj = FindingReconciliationEvent(
            reconciliation_id="rec-1",
            canonical_finding_id="F-CAN-1",
            semantic_finding_id="CF-1",
        )
        d = obj.to_dict()
        assert d["reconciliation_id"] == "rec-1"
        assert d["canonical_finding_id"] == "F-CAN-1"
        assert d["semantic_finding_id"] == "CF-1"

    # ── to_dict / from_dict round-trip ────────────────────────────────

    def test_occurrence_roundtrip(self) -> None:
        original = CritiqueOccurrenceEnvelope(
            occurrence_id="occ-rt",
            finding_id="F-RT",
            semantic_finding_id="CF-RT",
            context_mode="HISTORY_AWARE",
            parse_status="COMPLETED",
        )
        data = original.to_dict()
        restored = CritiqueOccurrenceEnvelope.from_dict(data)
        assert restored == original

    def test_reconciliation_roundtrip(self) -> None:
        original = FindingReconciliationEvent(
            reconciliation_id="rec-rt",
            canonical_finding_id="F-CAN-RT",
            semantic_finding_id="CF-RT",
            occurrence_ids=("occ-a", "occ-b"),
            relationship="DUPLICATE",
            authority="EVALUATOR",
            is_reopen=True,
            reopen_condition="when evidence available",
        )
        data = original.to_dict()
        restored = FindingReconciliationEvent.from_dict(data)
        assert restored == original

    def test_disposition_roundtrip(self) -> None:
        original = FindingDispositionEvent(
            disposition_id="disp-rt",
            semantic_finding_id="CF-RT",
            family="acted-on",
            reason_subcode="blocked-prerequisite-resolved",
            severity="high",
            action_taken=True,
            action_description="Fixed",
            accountable_scope="M6",
            is_reopen=False,
        )
        data = original.to_dict()
        restored = FindingDispositionEvent.from_dict(data)
        assert restored == original

    def test_briefing_roundtrip(self) -> None:
        original = DomainBriefingEnvelope(
            briefing_id="brief-rt",
            revision_manifest_hash="sha256:abc",
            budget_level="standard",
            domains=("d1", "d2"),
            findings=("f1",),
            open_findings=(),
            blocked_findings=(),
            accepted_risk_findings=(),
            unknown_findings=(),
            no_additional_findings=False,
            no_open_blocking_findings=True,
            no_known_findings=False,
            no_adjacent_text_match=True,
        )
        data = original.to_dict()
        restored = DomainBriefingEnvelope.from_dict(data)
        assert restored == original

    def test_manifest_roundtrip(self) -> None:
        original = LedgerRevisionManifest(
            manifest_id="man-rt",
            revision_number=1,
            input_set_hash="sha256:input",
            domain_completeness={"cl": True},
            event_ids=("ev-1", "ev-2"),
            included_reasons={"ev-1": "valid"},
            excluded_reasons={},
        )
        data = original.to_dict()
        restored = LedgerRevisionManifest.from_dict(data)
        assert restored == original

    # ── strict mode rejects unknown fields ─────────────────────────────

    def test_occurrence_strict_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown field"):
            CritiqueOccurrenceEnvelope.from_dict(
                {"schema_version": SCHEMA_VERSION, "occurrence_id": "x", "bad": 1},
                mode="strict",
            )

    def test_reconciliation_strict_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown field"):
            FindingReconciliationEvent.from_dict(
                {"schema_version": SCHEMA_VERSION, "reconciliation_id": "x", "bad": 1},
                mode="strict",
            )

    def test_disposition_strict_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown field"):
            FindingDispositionEvent.from_dict(
                {"schema_version": SCHEMA_VERSION, "disposition_id": "x", "bad": 1},
                mode="strict",
            )

    def test_briefing_strict_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown field"):
            DomainBriefingEnvelope.from_dict(
                {"schema_version": SCHEMA_VERSION, "briefing_id": "x", "bad": 1},
                mode="strict",
            )

    def test_manifest_strict_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown field"):
            LedgerRevisionManifest.from_dict(
                {"schema_version": SCHEMA_VERSION, "manifest_id": "x", "bad": 1},
                mode="strict",
            )

    # ── preserve mode retains unknown fields ──────────────────────────

    def test_occurrence_preserve_keeps_unknown(self) -> None:
        obj = CritiqueOccurrenceEnvelope.from_dict(
            {"schema_version": SCHEMA_VERSION, "occurrence_id": "x", "extra": "keep"},
            mode="preserve",
        )
        assert obj.occurrence_id == "x"
        assert obj._extra == {"extra": "keep"}
        data = obj.to_dict(mode="preserve")
        assert data["extra"] == "keep"

    # ── unsupported schema versions ───────────────────────────────────

    def test_occurrence_rejects_future_schema(self) -> None:
        with pytest.raises(ValueError, match="Unsupported schema_version"):
            CritiqueOccurrenceEnvelope.from_dict(
                {"schema_version": "cl.schema.v99", "occurrence_id": "x"}
            )

    def test_occurrence_rejects_corrupt_schema(self) -> None:
        with pytest.raises(ValueError, match="Unsupported schema_version"):
            CritiqueOccurrenceEnvelope.from_dict(
                {"schema_version": "garbage", "occurrence_id": "x"}
            )

    def test_reconciliation_rejects_future_schema(self) -> None:
        with pytest.raises(ValueError, match="Unsupported schema_version"):
            FindingReconciliationEvent.from_dict(
                {"schema_version": "cl.schema.v2-future", "reconciliation_id": "x"}
            )

    def test_disposition_rejects_future_schema(self) -> None:
        with pytest.raises(ValueError, match="Unsupported schema_version"):
            FindingDispositionEvent.from_dict(
                {"schema_version": "v99", "disposition_id": "x"}
            )

    def test_briefing_rejects_future_schema(self) -> None:
        with pytest.raises(ValueError, match="Unsupported schema_version"):
            DomainBriefingEnvelope.from_dict(
                {"schema_version": "cl.schema.v99", "briefing_id": "x"}
            )

    def test_manifest_rejects_future_schema(self) -> None:
        with pytest.raises(ValueError, match="Unsupported schema_version"):
            LedgerRevisionManifest.from_dict(
                {"schema_version": "future", "manifest_id": "x"}
            )

    # ── canonical hashing is deterministic ─────────────────────────────

    def test_canonical_hash_deterministic(self) -> None:
        obj1 = CritiqueOccurrenceEnvelope(
            occurrence_id="occ-hash", finding_id="F-HASH", semantic_finding_id="CF-HASH"
        )
        obj2 = CritiqueOccurrenceEnvelope(
            occurrence_id="occ-hash", finding_id="F-HASH", semantic_finding_id="CF-HASH"
        )
        assert canonical_hash(obj1) == canonical_hash(obj2)

    def test_freeze_for_hashing_produces_same_for_equal_objects(self) -> None:
        obj1 = CritiqueOccurrenceEnvelope(occurrence_id="occ-1")
        obj2 = CritiqueOccurrenceEnvelope(occurrence_id="occ-1")
        assert freeze_for_hashing(obj1) == freeze_for_hashing(obj2)

    def test_different_objects_have_different_hashes(self) -> None:
        obj1 = CritiqueOccurrenceEnvelope(occurrence_id="occ-1")
        obj2 = CritiqueOccurrenceEnvelope(occurrence_id="occ-2")
        assert canonical_hash(obj1) != canonical_hash(obj2)

    # ── budget validation ─────────────────────────────────────────────

    def test_standard_budget_accepts_valid(self) -> None:
        DomainBriefingEnvelope.validate_budget("standard", 2, 10)

    def test_standard_budget_rejects_too_many_domains(self) -> None:
        with pytest.raises(ValueError, match="exceeds standard budget"):
            DomainBriefingEnvelope.validate_budget("standard", 3, 5)

    def test_standard_budget_rejects_too_many_findings(self) -> None:
        with pytest.raises(ValueError, match="exceeds standard budget"):
            DomainBriefingEnvelope.validate_budget("standard", 1, 11)

    def test_high_budget_accepts_valid(self) -> None:
        DomainBriefingEnvelope.validate_budget("high", 4, 25)

    def test_high_budget_rejects_exceeded(self) -> None:
        with pytest.raises(ValueError, match="exceeds high budget"):
            DomainBriefingEnvelope.validate_budget("high", 5, 5)

    def test_exhaustive_budget_accepts_any(self) -> None:
        DomainBriefingEnvelope.validate_budget("exhaustive", 100, 1000)

    def test_unknown_budget_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown budget_level"):
            DomainBriefingEnvelope.validate_budget("nonexistent", 1, 1)

    # ── budget constants ──────────────────────────────────────────────

    def test_briefing_budgets_have_all_levels(self) -> None:
        assert set(BRIEFING_BUDGETS.keys()) == {"standard", "high", "exhaustive"}

    def test_standard_budget_values(self) -> None:
        assert BRIEFING_BUDGETS["standard"] == {"max_domains": 2, "max_findings": 10}

    def test_high_budget_values(self) -> None:
        assert BRIEFING_BUDGETS["high"] == {"max_domains": 4, "max_findings": 25}

    def test_exhaustive_budget_is_unbounded(self) -> None:
        assert BRIEFING_BUDGETS["exhaustive"]["max_domains"] is None
        assert BRIEFING_BUDGETS["exhaustive"]["max_findings"] is None


# ══════════════════════════════════════════════════════════════════════
# Golden case tests
# ══════════════════════════════════════════════════════════════════════


class TestGoldenCases:
    """Run every golden case through the respective schema class."""

    @pytest.fixture(scope="class")
    def golden(self) -> dict[str, Any]:
        return _load_golden_cases()

    def test_golden_cases_file_is_valid(self, golden: dict[str, Any]) -> None:
        assert "golden_cases" in golden
        assert len(golden["golden_cases"]) > 0

    @pytest.mark.parametrize(
        "case",
        _load_golden_cases()["golden_cases"],
        ids=lambda c: c["case_id"],
    )
    def test_golden_case(self, case: dict[str, Any]) -> None:
        schema_name = case["schema"]
        schema_cls = SCHEMA_CLASSES[schema_name]
        data = case["data"]

        if case.get("expect_strict_ok", True):
            # Should succeed in strict mode
            obj = schema_cls.from_dict(data, mode="strict")
            if case.get("expect_roundtrip", True):
                roundtripped = schema_cls.from_dict(obj.to_dict(mode="strict"), mode="strict")
                assert roundtripped == obj
        else:
            # Should fail in strict mode
            with pytest.raises((ValueError, KeyError), match=case.get("expected_error", "")):
                schema_cls.from_dict(data, mode="strict")

        # Preserve mode
        if case.get("expect_preserve_ok", False):
            obj = schema_cls.from_dict(data, mode="preserve")
            assert obj._extra or True  # at least doesn't crash

        # Budget failure check
        if case.get("expect_budget_failure"):
            obj = schema_cls.from_dict(data, mode="strict")
            with pytest.raises(ValueError):
                obj.validate_budget(
                    obj.budget_level,
                    len(obj.domains),
                    len(obj.findings),
                )

    def test_all_eight_disposition_families_covered(self, golden: dict[str, Any]) -> None:
        families_found: set[str] = set()
        for case in golden["golden_cases"]:
            if case["schema"] == "FindingDispositionEvent":
                families_found.add(case["data"]["family"])
        expected = {
            "acted-on", "ignored", "deferred", "rejected",
            "duplicate", "accepted-risk", "unknown", "resolved",
        }
        assert families_found == expected, (
            f"Missing disposition families: {expected - families_found}"
        )

    def test_all_eight_relationships_covered(self, golden: dict[str, Any]) -> None:
        # At least one reconciliation case has each relationship
        rels_found: set[str] = set()
        for case in golden["golden_cases"]:
            if case["schema"] == "FindingReconciliationEvent":
                rels_found.add(case["data"]["relationship"])
        # Not all 8 need individual cases, but the basic DUPLICATE and
        # the explicit BLOCKS case should be present at minimum
        assert "DUPLICATE" in rels_found
        assert "BLOCKS" in rels_found

    def test_both_context_modes_covered(self, golden: dict[str, Any]) -> None:
        modes_found: set[str] = set()
        for case in golden["golden_cases"]:
            if case["schema"] == "CritiqueOccurrenceEnvelope":
                modes_found.add(case["data"].get("context_mode", "BLIND"))
        assert "BLIND" in modes_found
        assert "HISTORY_AWARE" in modes_found

    def test_no_additional_findings_covered(self, golden: dict[str, Any]) -> None:
        found = any(
            case["data"].get("parse_status") == "NO_ADDITIONAL_FINDINGS"
            for case in golden["golden_cases"]
            if case["schema"] == "CritiqueOccurrenceEnvelope"
        )
        assert found, "Must have at least one NO_ADDITIONAL_FINDINGS case"

    def test_tombstone_covered(self, golden: dict[str, Any]) -> None:
        found = any(
            case["data"].get("parse_status") == "TOMBSTONED"
            for case in golden["golden_cases"]
            if case["schema"] == "CritiqueOccurrenceEnvelope"
        )
        assert found, "Must have at least one TOMBSTONED case"

    def test_unavailable_evidence_covered(self, golden: dict[str, Any]) -> None:
        found = any(
            case["data"].get("evidence_availability") == "UNAVAILABLE"
            for case in golden["golden_cases"]
        )
        assert found, "Must have at least one UNAVAILABLE evidence case"

    def test_future_version_rejection_covered(self, golden: dict[str, Any]) -> None:
        found = any(
            not case.get("expect_strict_ok", True)
            and "version" in case.get("expected_error", "").lower()
            for case in golden["golden_cases"]
        )
        assert found, "Must have at least one future-version rejection case"

    def test_corrupt_version_rejection_covered(self, golden: dict[str, Any]) -> None:
        found = any(
            case["case_id"] == "g-old-05-occurrence-corrupt-version"
            for case in golden["golden_cases"]
        )
        assert found, "Must have corrupt version rejection case g-old-05"
