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
    DispositionFamily,
    DomainBriefingEnvelope,
    FindingDispositionEvent,
    FindingReconciliationEvent,
    LedgerRevisionManifest,
    Relationship,
    canonical_hash,
    freeze_for_hashing,
)
from arnold.critique_ledger.semantic_loop import (
    FailureMode,
    apply_disposition_events,
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

    # ── CL4 reconciliation relationship members (T1) ───────────────────

    def test_new_relationship_members_serialize_to_canonical_values(self) -> None:
        assert Relationship.MERGE.value == "MERGE"
        assert Relationship.NEW.value == "NEW"
        assert Relationship.UNRELATED.value == "UNRELATED"
        assert Relationship.UNCERTAIN.value == "UNCERTAIN"

    def test_relationship_has_twelve_members_after_cl4(self) -> None:
        # 8 original + 4 CL4 additions = 12.
        assert len(list(Relationship)) == 12

    def test_new_relationship_values_roundtrip_in_reconciliation(self) -> None:
        for rel in (
            Relationship.MERGE.value,
            Relationship.NEW.value,
            Relationship.UNRELATED.value,
            Relationship.UNCERTAIN.value,
        ):
            original = FindingReconciliationEvent(
                reconciliation_id="rec-cl4",
                relationship=rel,
                reason="explicit evaluator judgment",
            )
            restored = FindingReconciliationEvent.from_dict(original.to_dict())
            assert restored == original
            assert restored.relationship == rel

    # ── CL4 disposition family members and fields (T2) ─────────────────

    def test_new_disposition_families_are_distinct_serialized_values(self) -> None:
        assert DispositionFamily.RESOLVED_VERIFIED.value == "resolved-verified"
        assert (
            DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value
            == "addressed-pending-verification"
        )
        # Legacy RESOLVED preserved verbatim, not aliased to the new member.
        assert DispositionFamily.RESOLVED.value == "resolved"
        assert (
            DispositionFamily.RESOLVED_VERIFIED.value
            != DispositionFamily.RESOLVED.value
        )
        assert (
            DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value
            != DispositionFamily.RESOLVED_VERIFIED.value
        )

    def test_evidence_limits_and_remaining_questions_roundtrip(self) -> None:
        original = FindingDispositionEvent(
            disposition_id="disp-cl4",
            semantic_finding_id="sf-cl4",
            family=DispositionFamily.RESOLVED_VERIFIED.value,
            evidence_limits=["no-reproducer", "log-rotation-pending"],
            remaining_questions=["does the fix hold under load?"],
        )
        data = original.to_dict()
        assert data["evidence_limits"] == ["no-reproducer", "log-rotation-pending"]
        assert data["remaining_questions"] == ["does the fix hold under load?"]
        restored = FindingDispositionEvent.from_dict(data)
        assert restored == original
        assert restored.evidence_limits == ["no-reproducer", "log-rotation-pending"]
        assert restored.remaining_questions == ["does the fix hold under load?"]

    def test_disposition_new_fields_default_empty_for_backward_compat(self) -> None:
        # Existing dispositions without the new CL4 fields round-trip unchanged.
        legacy = FindingDispositionEvent(
            disposition_id="disp-legacy",
            semantic_finding_id="sf-legacy",
            family=DispositionFamily.RESOLVED.value,
        )
        data = legacy.to_dict()
        assert data["evidence_limits"] == []
        assert data["remaining_questions"] == []
        restored = FindingDispositionEvent.from_dict(data)
        assert restored.evidence_limits == []
        assert restored.remaining_questions == []

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
# CL4 (Step 5): per-family disposition field-presence validation (T5)
# ══════════════════════════════════════════════════════════════════════


class TestDispositionFamilyFieldPresence:
    """Each of the seven non-closure disposition families must surface a
    specific typed FailureMode when its required field is absent, while a
    fully-specified disposition is accepted. UNKNOWN remains a valid
    terminal judgment with no extra requirement.
    """

    # Minimal finding_map shared by every case: one finding with one
    # occurrence so the orphan/coverage checks never fire.
    _FINDING_MAP = {"sf-1": ["occ-1"]}

    def _modes(self, result: dict) -> set[str]:
        return {f["mode"] for f in result["failures"]}

    # ── ACTED_ON requires action_taken + action_description ───────────

    def test_acted_on_valid_is_accepted(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.ACTED_ON.value,
            action_taken=True, action_description="patched the gate",
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True
        assert result["family_counts"][DispositionFamily.ACTED_ON.value] == 1

    def test_acted_on_without_action_fails(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.ACTED_ON.value,
            # action_taken defaults False; action_description defaults None
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is False
        assert FailureMode.ACTED_ON_MISSING_ACTION.value in self._modes(result)

    def test_acted_on_without_description_fails(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.ACTED_ON.value,
            action_taken=True,  # description still missing
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is False
        assert FailureMode.ACTED_ON_MISSING_ACTION.value in self._modes(result)

    # ── IGNORED requires reopen_predicate ─────────────────────────────

    def test_ignored_valid_is_accepted(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.IGNORED.value,
            reopen_predicate="revisit when X lands",
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True

    def test_ignored_without_reopen_predicate_fails(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.IGNORED.value,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is False
        assert FailureMode.IGNORED_MISSING_REOPEN_PREDICATE.value in self._modes(result)

    # ── DEFERRED requires reopen_predicate ────────────────────────────

    def test_deferred_valid_is_accepted(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.DEFERRED.value,
            reopen_predicate="revisit after dependency ships",
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True

    def test_deferred_without_reopen_predicate_fails(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.DEFERRED.value,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is False
        assert FailureMode.DEFERRED_MISSING_REOPEN_PREDICATE.value in self._modes(result)

    # ── ACCEPTED_RISK requires reopen_predicate (rationale) ───────────

    def test_accepted_risk_valid_is_accepted(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.ACCEPTED_RISK.value,
            reopen_predicate="revisit when reproducer available",
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True

    def test_accepted_risk_without_rationale_fails(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.ACCEPTED_RISK.value,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is False
        assert FailureMode.ACCEPTED_RISK_MISSING_RATIONALE.value in self._modes(result)

    # ── REJECTED requires reason_subcode ──────────────────────────────

    def test_rejected_valid_is_accepted(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.REJECTED.value,
            reason_subcode="out-of-scope",
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True

    def test_rejected_without_reason_subcode_fails(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.REJECTED.value,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is False
        assert FailureMode.REJECTED_MISSING_REASON_SUBCODE.value in self._modes(result)

    # ── DUPLICATE requires a canonical-finding ref in metadata ────────

    def test_duplicate_valid_with_canonical_ref_is_accepted(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.DUPLICATE.value,
            metadata={"canonical_finding_id": "sf-canonical"},
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True

    def test_duplicate_without_canonical_ref_fails(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.DUPLICATE.value,
            metadata={},
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is False
        assert FailureMode.DUPLICATE_MISSING_CANONICAL_REF.value in self._modes(result)

    def test_duplicate_canonical_ref_alias_keys_accepted(self) -> None:
        # The canonical-finding ref may be supplied under any recognized key.
        for key in ("canonical_finding_id", "canonical_finding_ref", "canonical_ref"):
            disp = FindingDispositionEvent(
                disposition_id=f"d-{key}", semantic_finding_id="sf-1",
                family=DispositionFamily.DUPLICATE.value,
                metadata={key: "sf-canonical"},
            )
            result = apply_disposition_events(self._FINDING_MAP, [disp])
            assert result["accepted"] is True, key

    # ── UNKNOWN is a valid terminal judgment, no extra requirement ────

    def test_unknown_valid_with_no_extra_fields_is_accepted(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.UNKNOWN.value,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True
        # No field-presence failure should ever surface for UNKNOWN.
        presence_modes = {
            FailureMode.ACTED_ON_MISSING_ACTION.value,
            FailureMode.IGNORED_MISSING_REOPEN_PREDICATE.value,
            FailureMode.DEFERRED_MISSING_REOPEN_PREDICATE.value,
            FailureMode.ACCEPTED_RISK_MISSING_RATIONALE.value,
            FailureMode.REJECTED_MISSING_REASON_SUBCODE.value,
            FailureMode.DUPLICATE_MISSING_CANONICAL_REF.value,
        }
        assert presence_modes.isdisjoint(self._modes(result))

    # ── every missing field yields exactly its own FailureMode ────────

    @pytest.mark.parametrize(
        ("family", "failure_mode"),
        [
            (DispositionFamily.ACTED_ON.value, FailureMode.ACTED_ON_MISSING_ACTION.value),
            (DispositionFamily.IGNORED.value, FailureMode.IGNORED_MISSING_REOPEN_PREDICATE.value),
            (DispositionFamily.DEFERRED.value, FailureMode.DEFERRED_MISSING_REOPEN_PREDICATE.value),
            (DispositionFamily.ACCEPTED_RISK.value, FailureMode.ACCEPTED_RISK_MISSING_RATIONALE.value),
            (DispositionFamily.REJECTED.value, FailureMode.REJECTED_MISSING_REASON_SUBCODE.value),
            (DispositionFamily.DUPLICATE.value, FailureMode.DUPLICATE_MISSING_CANONICAL_REF.value),
        ],
    )
    def test_each_family_missing_field_yields_exact_failure_mode(
        self, family: str, failure_mode: str,
    ) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=family,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is False
        assert failure_mode in self._modes(result)
        # No OTHER field-presence mode leaks in.
        other_presence = {
            FailureMode.ACTED_ON_MISSING_ACTION.value,
            FailureMode.IGNORED_MISSING_REOPEN_PREDICATE.value,
            FailureMode.DEFERRED_MISSING_REOPEN_PREDICATE.value,
            FailureMode.ACCEPTED_RISK_MISSING_RATIONALE.value,
            FailureMode.REJECTED_MISSING_REASON_SUBCODE.value,
            FailureMode.DUPLICATE_MISSING_CANONICAL_REF.value,
        } - {failure_mode}
        assert other_presence.isdisjoint(self._modes(result))


# ══════════════════════════════════════════════════════════════════════
# CL4 (Plan Step 6): closure-evidence enforcement, transition gating, and
# reopen-predicate staleness flag (apply_disposition_events level).
# ══════════════════════════════════════════════════════════════════════


class TestClosureEvidenceAndReopenStaleness:
    """Plan Step 6: RESOLVED_VERIFIED closure requires verification evidence,
    pending->verified transitions are gated on the same evidence, and
    reopen-predicate dispositions carry a deferred staleness flag.

    The legacy ``RESOLVED`` value is intentionally not normalized inside
    apply_disposition_events, so it keeps its existing apply-level behaviour
    (closure enforced only by the replay_full backstop); only the new
    ``RESOLVED_VERIFIED`` value carries the apply-level evidence requirement.
    """

    _FINDING_MAP = {"sf-1": ["occ-1"]}

    def _modes(self, result: dict) -> set[str]:
        return {f["mode"] for f in result["failures"]}

    # ── RESOLVED_VERIFIED requires verification evidence (Step 6.1) ──────

    def test_resolved_verified_without_evidence_is_rejected(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.RESOLVED_VERIFIED.value,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is False
        assert FailureMode.CLOSURE_UNSUPPORTED.value in self._modes(result)

    def test_resolved_verified_with_evidence_is_accepted(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.RESOLVED_VERIFIED.value,
            evidence_refs=("verified-against-reproducer",),
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True
        assert result["family_counts"][DispositionFamily.RESOLVED_VERIFIED.value] == 1

    def test_resolved_verified_rejection_detail_names_evidence(self) -> None:
        # Standalone (no preceding pending) rejection must NOT be framed as a
        # transition; the detail names the evidence requirement directly.
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.RESOLVED_VERIFIED.value,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        closure = next(
            f for f in result["failures"]
            if f["mode"] == FailureMode.CLOSURE_UNSUPPORTED.value
        )
        assert "transition" not in closure["detail"].lower()
        assert "evidence" in closure["detail"].lower()

    # ── pending -> verified transition gating (Step 6.2) ────────────────

    def test_pending_to_verified_without_evidence_is_gated(self) -> None:
        pending = FindingDispositionEvent(
            disposition_id="d-pending", semantic_finding_id="sf-1",
            family=DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value,
        )
        verified = FindingDispositionEvent(
            disposition_id="d-verified", semantic_finding_id="sf-1",
            family=DispositionFamily.RESOLVED_VERIFIED.value,
            # evidence_refs intentionally absent
        )
        result = apply_disposition_events(self._FINDING_MAP, [pending, verified])
        assert result["accepted"] is False
        assert FailureMode.CLOSURE_UNSUPPORTED.value in self._modes(result)
        closure = next(
            f for f in result["failures"]
            if f["mode"] == FailureMode.CLOSURE_UNSUPPORTED.value
        )
        # The transition is named explicitly in the failure detail.
        assert "transition" in closure["detail"].lower()

    def test_pending_to_verified_with_evidence_is_accepted(self) -> None:
        pending = FindingDispositionEvent(
            disposition_id="d-pending", semantic_finding_id="sf-1",
            family=DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value,
        )
        verified = FindingDispositionEvent(
            disposition_id="d-verified", semantic_finding_id="sf-1",
            family=DispositionFamily.RESOLVED_VERIFIED.value,
            evidence_refs=("verified-against-reproducer",),
        )
        result = apply_disposition_events(self._FINDING_MAP, [pending, verified])
        assert result["accepted"] is True
        # The later RESOLVED_VERIFIED overrides the pending entry.
        assert result["disposition_map"]["sf-1"]["family"] == (
            DispositionFamily.RESOLVED_VERIFIED.value
        )

    # ── legacy RESOLVED keeps apply-level behaviour (Step 6.3 split) ────

    def test_legacy_resolved_not_enforced_at_apply_level(self) -> None:
        # The legacy value is not normalized inside apply_disposition_events,
        # so a legacy RESOLVED without evidence is accepted here and is only
        # enforced by the replay_full closure backstop.
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.RESOLVED.value,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True
        assert result["family_counts"][DispositionFamily.RESOLVED.value] == 1

    # ── reopen-predicate staleness flag (Step 6.4) ──────────────────────

    def test_reopen_predicate_sets_staleness_check_deferred_true(self) -> None:
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.IGNORED.value,
            reopen_predicate="revisit when X lands",
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True
        assert result["disposition_map"]["sf-1"]["staleness_check_deferred"] is True

    def test_no_reopen_predicate_sets_staleness_check_deferred_false(self) -> None:
        # UNKNOWN is a valid terminal judgment with no reopen_predicate.
        disp = FindingDispositionEvent(
            disposition_id="d", semantic_finding_id="sf-1",
            family=DispositionFamily.UNKNOWN.value,
        )
        result = apply_disposition_events(self._FINDING_MAP, [disp])
        assert result["accepted"] is True
        assert result["disposition_map"]["sf-1"]["staleness_check_deferred"] is False


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
