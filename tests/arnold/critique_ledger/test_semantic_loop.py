"""Tests for arnold.critique_ledger.semantic_loop — pure replay engine.

Covers:
- Custody validation (no receipt, broken chain, unknown producer)
- Occurrence envelope validation (missing ID, duplicates, parse failures)
- Reconciliation (orphan occurrences, duplicates, inferred sameness, reopen)
- Disposition (orphan findings, duplicates, unknown families)
- Manifest construction (empty input, domain incomplete)
- Briefing (budget exceeded, domain floor unmet, silent truncation)
- Reviser projection (four no-X fields, no verdict)
- Gate projection (four no-X fields, custody/reconciliation/disposition signals)
- Complete replay (integration)
"""

from __future__ import annotations

import pytest

from arnold.critique_ledger.schemas import (
    Authority,
    ContextMode,
    DispositionFamily,
    EvidenceAvailability,
    ParseStatus,
    Relationship,
    CritiqueOccurrenceEnvelope,
    FindingDispositionEvent,
    FindingReconciliationEvent,
)
from arnold.critique_ledger.semantic_loop import (
    FailureMode,
    SemanticLoopError,
    apply_disposition_events,
    apply_reconciliation_events,
    build_briefing,
    construct_manifest,
    project_gate_input,
    project_reviser_input,
    replay_full,
    validate_occurrence_custody,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_occurrence(
    occurrence_id: str = "occ-1",
    parse_status: str = ParseStatus.SELECTED.value,
    evidence_availability: str = EvidenceAvailability.RETAINED.value,
    custody_receipt_refs: tuple[str, ...] = ("wbc-001",),
    producer_id: str = "test-producer",
    **kwargs,
) -> CritiqueOccurrenceEnvelope:
    return CritiqueOccurrenceEnvelope(
        occurrence_id=occurrence_id,
        attempt_id="attempt-1",
        round_label="v1",
        finding_id="F01",
        producer_id=producer_id,
        model_id="test-model",
        context_mode=ContextMode.BLIND.value,
        parse_status=parse_status,
        evidence_availability=evidence_availability,
        custody_receipt_refs=custody_receipt_refs,
        **kwargs,
    )


def _make_reconciliation(
    reconciliation_id: str = "rec-1",
    occurrence_ids: tuple[str, ...] = ("occ-1",),
    semantic_finding_id: str = "sf-1",
    relationship: str = Relationship.DUPLICATE.value,
    reason: str = "Same concern across rounds",
    **kwargs,
) -> FindingReconciliationEvent:
    return FindingReconciliationEvent(
        reconciliation_id=reconciliation_id,
        canonical_finding_id="F01",
        semantic_finding_id=semantic_finding_id,
        occurrence_ids=occurrence_ids,
        relationship=relationship,
        authority=Authority.EVALUATOR.value,
        reason=reason,
        **kwargs,
    )


def _make_disposition(
    disposition_id: str = "disp-1",
    semantic_finding_id: str = "sf-1",
    family: str = DispositionFamily.ACCEPTED_RISK.value,
    **kwargs,
) -> FindingDispositionEvent:
    # CL4 (Step 5): provide all per-family required fields by default so the
    # helper yields a disposition valid under field-presence validation for
    # every non-closure family. Tests exercising a specific missing-field
    # failure override the relevant kwarg (e.g. reopen_predicate=None).
    defaults = {
        "reopen_predicate": "default reopen predicate",
        "reason_subcode": "default-reason",
        "action_taken": True,
        "action_description": "default action taken",
        "metadata": {"canonical_finding_id": "sf-canonical-ref"},
    }
    defaults.update(kwargs)
    return FindingDispositionEvent(
        disposition_id=disposition_id,
        semantic_finding_id=semantic_finding_id,
        family=family,
        authority=Authority.EVALUATOR.value,
        **defaults,
    )


# ── Custody validation ───────────────────────────────────────────────


class TestCustodyValidation:
    def test_valid_custody_passes(self) -> None:
        occ = _make_occurrence(custody_receipt_refs=("wbc-001",))
        result = validate_occurrence_custody(
            [occ], {"wbc-001": {"valid": True}}
        )
        assert result["valid"] is True
        assert len(result["failures"]) == 0

    def test_no_receipt_refs_fails(self) -> None:
        occ = _make_occurrence(custody_receipt_refs=())
        result = validate_occurrence_custody([occ])
        assert result["valid"] is False
        assert result["failures"][0]["mode"] == FailureMode.CUSTODY_NO_RECEIPT.value

    def test_broken_receipt_chain_fails(self) -> None:
        occ = _make_occurrence(custody_receipt_refs=("wbc-999",))
        result = validate_occurrence_custody(
            [occ], {"wbc-001": {"valid": True}}
        )
        assert result["valid"] is False
        assert any(
            f["mode"] == FailureMode.CUSTODY_RECEIPT_CHAIN_BROKEN.value
            for f in result["failures"]
        )

    def test_unknown_producer_fails(self) -> None:
        occ = _make_occurrence(
            producer_id="UNKNOWN_test",
            custody_receipt_refs=("wbc-001",),
        )
        result = validate_occurrence_custody(
            [occ], {"wbc-001": {"valid": True}}
        )
        assert result["valid"] is False
        assert any(
            f["mode"] == FailureMode.CUSTODY_PRODUCER_UNKNOWN.value
            for f in result["failures"]
        )

    def test_multiple_occurrences_track_receipt_coverage(self) -> None:
        occs = [
            _make_occurrence("occ-1", custody_receipt_refs=("wbc-001",)),
            _make_occurrence("occ-2", custody_receipt_refs=("wbc-001", "wbc-002")),
            _make_occurrence("occ-3", custody_receipt_refs=("wbc-002",)),
        ]
        result = validate_occurrence_custody(
            occs, {"wbc-001": {"valid": True}, "wbc-002": {"valid": True}}
        )
        assert result["valid"] is True
        assert result["receipt_coverage"]["unique_receipts_referenced"] == 2


# ── Reconciliation ───────────────────────────────────────────────────


class TestReconciliation:
    def test_basic_reconciliation_maps_occurrences_to_finding(self) -> None:
        occs = [
            _make_occurrence("occ-1"),
            _make_occurrence("occ-2"),
        ]
        recs = [
            _make_reconciliation(
                "rec-1",
                occurrence_ids=("occ-1", "occ-2"),
                semantic_finding_id="sf-1",
            ),
        ]
        result = apply_reconciliation_events(occs, recs)
        assert result["accepted"] is True
        assert result["finding_map"]["sf-1"] == ["occ-1", "occ-2"]
        assert result["total_semantic_findings"] == 1

    def test_orphan_occurrence_fails(self) -> None:
        occs = [_make_occurrence("occ-1")]
        recs = [
            _make_reconciliation(
                occurrence_ids=("occ-1", "nonexistent"),
            ),
        ]
        result = apply_reconciliation_events(occs, recs)
        assert result["accepted"] is False
        assert any(
            f["mode"] == FailureMode.RECONCILIATION_ORPHAN_OCCURRENCE.value
            for f in result["failures"]
        )

    def test_duplicate_reconciliation_id_fails(self) -> None:
        occs = [_make_occurrence("occ-1")]
        recs = [
            _make_reconciliation("rec-1", occurrence_ids=("occ-1",)),
            _make_reconciliation("rec-1", occurrence_ids=("occ-1",)),
        ]
        result = apply_reconciliation_events(occs, recs)
        assert result["accepted"] is False
        assert any(
            f["mode"] == FailureMode.RECONCILIATION_DUPLICATE_EVENT.value
            for f in result["failures"]
        )

    def test_missing_reconciliation_id_fails(self) -> None:
        occs = [_make_occurrence("occ-1")]
        recs = [
            FindingReconciliationEvent(
                reconciliation_id="",
                occurrence_ids=("occ-1",),
            ),
        ]
        result = apply_reconciliation_events(occs, recs)
        assert any(
            f["mode"] == FailureMode.RECONCILIATION_MISSING_ID.value
            for f in result["failures"]
        )

    def test_inferred_sameness_without_reason_fails(self) -> None:
        occs = [_make_occurrence("occ-1")]
        recs = [
            _make_reconciliation(
                relationship=Relationship.REFINEMENT.value,
                reason="",  # no reason
            ),
        ]
        result = apply_reconciliation_events(occs, recs)
        assert any(
            f["mode"] == FailureMode.RECONCILIATION_INFERRED_SAMENESS.value
            for f in result["failures"]
        )
        # Still accepted since it's a warning, not a hard failure for the finding_map
        assert result["total_semantic_findings"] == 1

    def test_reopen_event_recorded(self) -> None:
        occs = [_make_occurrence("occ-1")]
        recs = [
            _make_reconciliation(
                relationship=Relationship.REOPEN.value,
                reason="New evidence requires re-evaluation",
                reopen_condition="When preserved repo restored",
            ),
        ]
        result = apply_reconciliation_events(occs, recs, allow_reopen=True)
        assert len(result["reopen_events"]) == 1
        assert result["reopen_events"][0]["reopen_condition"] == "When preserved repo restored"

    def test_reopen_blocked_when_not_allowed(self) -> None:
        occs = [_make_occurrence("occ-1")]
        recs = [
            _make_reconciliation(
                relationship=Relationship.REOPEN.value,
                reason="Reopen needed",
            ),
        ]
        result = apply_reconciliation_events(occs, recs, allow_reopen=False)
        assert any(
            f["mode"] == FailureMode.RECONCILIATION_OUT_OF_ORDER.value
            for f in result["failures"]
        )

    def test_five_occurrences_one_finding(self) -> None:
        """Oracle fact 4: five occurrences → one semantic finding."""
        occs = [
            _make_occurrence(f"occ-v{i}-CF-CD1C") for i in range(1, 6)
        ]
        recs = [
            _make_reconciliation(
                "rec-scope-1",
                occurrence_ids=tuple(f"occ-v{i}-CF-CD1C" for i in range(1, 6)),
                semantic_finding_id="sem-finding-scope-god-task",
                reason="Same scope/work-sizing concern across five rounds",
            ),
        ]
        result = apply_reconciliation_events(occs, recs)
        assert result["accepted"] is True
        assert result["total_semantic_findings"] == 1
        assert len(result["finding_map"]["sem-finding-scope-god-task"]) == 5

    # ── CL4 new relationship members (T1) ──────────────────────────────

    def test_cl4_new_relationships_accepted_and_mapped_to_finding(self) -> None:
        """MERGE, NEW, UNRELATED, and UNCERTAIN all validate and map
        their occurrences to the finding_map exactly once."""
        for rel in (
            Relationship.MERGE.value,
            Relationship.NEW.value,
            Relationship.UNRELATED.value,
            Relationship.UNCERTAIN.value,
        ):
            occs = [_make_occurrence("occ-a"), _make_occurrence("occ-b")]
            recs = [_make_reconciliation(
                "rec-x", occurrence_ids=("occ-a", "occ-b"),
                semantic_finding_id="sf-x", relationship=rel,
                reason="explicit evaluator judgment",
            )]
            result = apply_reconciliation_events(occs, recs)
            assert result["accepted"] is True, f"relationship {rel} not accepted"
            assert result["finding_map"]["sf-x"] == ["occ-a", "occ-b"]
            assert result["total_semantic_findings"] == 1

    def test_cl4_unknown_relationship_rejected(self) -> None:
        """An unrecognized serialized relationship is rejected with a typed
        failure and does not contribute a finding."""
        occs = [_make_occurrence("occ-1")]
        recs = [_make_reconciliation(
            "rec-bad", relationship="NONSENSE",
            reason="should be rejected",
        )]
        result = apply_reconciliation_events(occs, recs)
        assert any(
            f["mode"] == FailureMode.RECONCILIATION_UNKNOWN_RELATIONSHIP.value
            for f in result["failures"]
        )
        # Rejected event must not contribute a finding.
        assert result["total_semantic_findings"] == 0

    def test_cl4_disputed_merge_with_evaluator_disagreement_retained(self) -> None:
        """A MERGE event is retained in finding_map even when a second
        evaluator disputes the sameness with UNRELATED. Both mappings are
        recorded exactly-once; neither is silently dropped."""
        occs = [_make_occurrence("occ-1"), _make_occurrence("occ-2")]
        recs = [
            _make_reconciliation(
                "rec-merge",
                occurrence_ids=("occ-1", "occ-2"),
                semantic_finding_id="sf-merge",
                relationship=Relationship.MERGE.value,
                reason="same root cause",
            ),
            _make_reconciliation(
                "rec-disagree",
                occurrence_ids=("occ-2",),
                semantic_finding_id="sf-distinct",
                relationship=Relationship.UNRELATED.value,
                reason="evaluator B disagrees — different scope",
            ),
        ]
        result = apply_reconciliation_events(occs, recs)
        assert result["accepted"] is True
        # The disputed MERGE is retained.
        assert result["finding_map"]["sf-merge"] == ["occ-1", "occ-2"]
        # The disagreeing UNRELATED mapping coexists.
        assert result["finding_map"]["sf-distinct"] == ["occ-2"]
        assert result["total_semantic_findings"] == 2

    def test_cl4_uncertain_is_non_blocking(self) -> None:
        """UNCERTAIN does not force accepted=False or add a hard failure."""
        occs = [_make_occurrence("occ-1")]
        recs = [_make_reconciliation(
            "rec-uncertain", occurrence_ids=("occ-1",),
            semantic_finding_id="sf-u",
            relationship=Relationship.UNCERTAIN.value,
            reason="cannot determine sameness from available evidence",
        )]
        result = apply_reconciliation_events(occs, recs)
        assert result["accepted"] is True
        assert result["total_semantic_findings"] == 1
        # No hard (non-warning) failure for UNCERTAIN.
        assert not any(
            f["mode"] != FailureMode.RECONCILIATION_INFERRED_SAMENESS.value
            for f in result["failures"]
        )


# ── Disposition ──────────────────────────────────────────────────────


class TestDisposition:
    def test_basic_disposition(self) -> None:
        finding_map = {"sf-1": {"occ-1"}}
        disps = [_make_disposition("disp-1", "sf-1")]
        result = apply_disposition_events(finding_map, disps)
        assert result["accepted"] is True
        assert result["family_counts"]["accepted-risk"] == 1

    def test_orphan_finding_fails(self) -> None:
        finding_map = {"sf-1": {"occ-1"}}
        disps = [_make_disposition("disp-1", "sf-nonexistent")]
        result = apply_disposition_events(finding_map, disps)
        assert result["accepted"] is False
        assert any(
            f["mode"] == FailureMode.DISPOSITION_ORPHAN_FINDING.value
            for f in result["failures"]
        )

    def test_duplicate_disposition_fails(self) -> None:
        finding_map = {"sf-1": {"occ-1"}}
        disps = [
            _make_disposition("disp-1", "sf-1"),
            _make_disposition("disp-1", "sf-1"),
        ]
        result = apply_disposition_events(finding_map, disps)
        assert result["accepted"] is False
        assert any(
            f["mode"] == FailureMode.DISPOSITION_DUPLICATE_EVENT.value
            for f in result["failures"]
        )

    def test_unknown_family_fails(self) -> None:
        finding_map = {"sf-1": {"occ-1"}}
        disps = [_make_disposition("disp-1", "sf-1", family="nonexistent-family")]
        result = apply_disposition_events(finding_map, disps)
        assert result["accepted"] is False
        assert any(
            f["mode"] == FailureMode.DISPOSITION_UNKNOWN_FAMILY.value
            for f in result["failures"]
        )

    def test_missing_disposition_id_fails(self) -> None:
        finding_map = {"sf-1": {"occ-1"}}
        disps = [FindingDispositionEvent(
            disposition_id="", semantic_finding_id="sf-1",
        )]
        result = apply_disposition_events(finding_map, disps)
        assert any(
            f["mode"] == FailureMode.DISPOSITION_MISSING_ID.value
            for f in result["failures"]
        )

    def test_all_eight_families_classified(self) -> None:
        finding_map = {f"sf-{i}": {f"occ-{i}"} for i in range(8)}
        families = [
            DispositionFamily.ACTED_ON.value,
            DispositionFamily.IGNORED.value,
            DispositionFamily.DEFERRED.value,
            DispositionFamily.REJECTED.value,
            DispositionFamily.DUPLICATE.value,
            DispositionFamily.ACCEPTED_RISK.value,
            DispositionFamily.UNKNOWN.value,
            DispositionFamily.RESOLVED.value,
        ]
        disps = [
            _make_disposition(f"disp-{i}", f"sf-{i}", family=families[i])
            for i in range(8)
        ]
        result = apply_disposition_events(finding_map, disps)
        assert result["accepted"] is True
        assert len(result["family_counts"]) == 8


# ── Manifest construction ────────────────────────────────────────────


class TestManifestConstruction:
    def test_basic_manifest(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        assert manifest.revision_number == 1
        assert manifest.input_set_hash != ""
        assert len(manifest.event_ids) > 0
        assert "occ-1" in manifest.event_ids

    def test_empty_input_raises(self) -> None:
        with pytest.raises(SemanticLoopError) as exc:
            construct_manifest([], {"finding_map": {}}, {"disposition_map": {}})
        assert exc.value.mode == FailureMode.MANIFEST_EMPTY_INPUT_SET

    def test_domain_incomplete_raises(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        with pytest.raises(SemanticLoopError) as exc:
            construct_manifest(
                occs, rec_result, disp_result,
                domain_completeness={"domain-a": True, "domain-b": False},
            )
        assert exc.value.mode == FailureMode.MANIFEST_DOMAIN_INCOMPLETE

    def test_manifest_includes_failed_events_in_excluded(self) -> None:
        occs = [_make_occurrence("occ-1", parse_status=ParseStatus.FAILED.value)]
        rec_result = apply_reconciliation_events(occs, [])
        disp_result = apply_disposition_events(
            rec_result["finding_map"], []
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        assert "occ-1" in manifest.excluded_reasons
        assert "parse_status=FAILED" in manifest.excluded_reasons["occ-1"]


# ── Briefing ─────────────────────────────────────────────────────────


class TestBriefing:
    def test_standard_budget(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
            budget_level="standard",
        )
        assert briefing.budget_level == "standard"
        assert briefing.domains == ("critique_ledger",)

    def test_high_budget(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
            budget_level="high",
        )
        assert briefing.budget_level == "high"

    def test_exhaustive_budget_unbounded(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
            budget_level="exhaustive",
        )
        assert briefing.budget_level == "exhaustive"

    def test_finding_spillover_not_silent_truncation(self) -> None:
        """Standard budget max 10 findings. 11 findings → spillover, not silent."""
        occs = []
        recs = []
        disps = []
        for i in range(11):
            oid = f"occ-{i}"
            sf_id = f"sf-{i}"
            occs.append(_make_occurrence(oid))
            recs.append(_make_reconciliation(
                f"rec-{i}", occurrence_ids=(oid,), semantic_finding_id=sf_id,
            ))
            disps.append(_make_disposition(f"disp-{i}", sf_id))
        rec_result = apply_reconciliation_events(occs, recs)
        disp_result = apply_disposition_events(rec_result["finding_map"], disps)
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
            budget_level="standard",
            domain_assignments={f"sf-{i}": "critique_ledger" for i in range(11)},
        )
        assert briefing.is_truncated is True
        assert len(briefing.spillover_findings) == 1
        assert len(briefing.findings) == 10

    def test_unknown_budget_raises(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        with pytest.raises(SemanticLoopError) as exc:
            build_briefing(
                manifest, disp_result, rec_result["finding_map"],
                budget_level="imaginary",
            )
        assert exc.value.mode == FailureMode.BRIEFING_BUDGET_EXCEEDED

    def test_domain_floor_unmet_raises(self) -> None:
        """Multiple domains with empty ones should raise."""
        occs = []
        recs = []
        disps = []
        for i in range(3):
            oid = f"occ-{i}"
            sf_id = f"sf-{i}"
            occs.append(_make_occurrence(oid))
            recs.append(_make_reconciliation(
                f"rec-{i}", occurrence_ids=(oid,), semantic_finding_id=sf_id,
            ))
            disps.append(_make_disposition(f"disp-{i}", sf_id))
        rec_result = apply_reconciliation_events(occs, recs)
        disp_result = apply_disposition_events(rec_result["finding_map"], disps)
        manifest = construct_manifest(occs, rec_result, disp_result)
        # 3 domains → standard max is 2
        with pytest.raises(SemanticLoopError) as exc:
            build_briefing(
                manifest, disp_result, rec_result["finding_map"],
                budget_level="standard",
                domain_assignments={
                    "sf-0": "domain-a", "sf-1": "domain-b", "sf-2": "domain-c",
                },
            )
        assert exc.value.mode == FailureMode.BRIEFING_DOMAIN_FLOOR_UNMET

    def test_open_blocking_accepted_risk_unknown_classification(self) -> None:
        """Verify findings are correctly classified in briefing."""
        occs = [
            _make_occurrence(f"occ-{i}") for i in range(4)
        ]
        recs = [
            _make_reconciliation(f"rec-{i}", occurrence_ids=(f"occ-{i}",),
                                 semantic_finding_id=f"sf-{i}")
            for i in range(4)
        ]
        disps = [
            _make_disposition("disp-0", "sf-0", family=DispositionFamily.IGNORED.value),   # open
            _make_disposition("disp-1", "sf-1", family=DispositionFamily.REJECTED.value),   # blocked
            _make_disposition("disp-2", "sf-2", family=DispositionFamily.ACCEPTED_RISK.value),
            _make_disposition("disp-3", "sf-3", family=DispositionFamily.UNKNOWN.value),    # unknown
        ]
        rec_result = apply_reconciliation_events(occs, recs)
        disp_result = apply_disposition_events(rec_result["finding_map"], disps)
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        assert "sf-0" in briefing.open_findings
        assert "sf-1" in briefing.blocked_findings
        assert "sf-2" in briefing.accepted_risk_findings
        assert "sf-3" in briefing.unknown_findings

    def test_cl4_three_disposition_forms_classify_into_correct_buckets(self) -> None:
        """CL4 Step 2.3: RESOLVED_VERIFIED and legacy RESOLVED both route to
        resolved_findings; ADDRESSED_PENDING_VERIFICATION routes to
        acted_on_findings (still open, pending verification). Every finding
        lands in exactly one bucket, preserving the partition invariant."""
        occs = [_make_occurrence(f"occ-{i}") for i in range(3)]
        recs = [
            _make_reconciliation(f"rec-{i}", occurrence_ids=(f"occ-{i}",),
                                 semantic_finding_id=f"sf-{i}")
            for i in range(3)
        ]
        disps = [
            _make_disposition(
                "disp-0", "sf-0",
                family=DispositionFamily.RESOLVED_VERIFIED.value,
                # CL4 Step 6: RESOLVED_VERIFIED closure requires a
                # verification artifact in evidence_refs plus a reason
                # subcode; without them the disposition is rejected as
                # CLOSURE_UNSUPPORTED and never reaches the resolved bucket.
                evidence_refs=["verification-artifact-occ-0"],
                reason_subcode="verified-by-evidence",
            ),
            _make_disposition("disp-1", "sf-1",
                              family=DispositionFamily.RESOLVED.value),  # legacy
            _make_disposition("disp-2", "sf-2",
                              family=DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value),
        ]
        rec_result = apply_reconciliation_events(occs, recs)
        disp_result = apply_disposition_events(rec_result["finding_map"], disps)
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
            budget_level="exhaustive",
        )
        # RESOLVED_VERIFIED → resolved bucket.
        assert "sf-0" in briefing.resolved_findings
        # Legacy RESOLVED normalizes → resolved bucket, stored value intact.
        assert "sf-1" in briefing.resolved_findings
        assert disps[1].family == "resolved"
        # ADDRESSED_PENDING_VERIFICATION → acted-on bucket (open follow-up).
        assert "sf-2" in briefing.acted_on_findings
        # Partition: every finding in exactly one bucket.
        union = set()
        for bucket in (
            "acted_on_findings", "ignored_findings", "deferred_findings",
            "blocked_findings", "accepted_risk_findings",
            "unknown_findings", "resolved_findings", "duplicate_findings",
        ):
            union |= set(getattr(briefing, bucket))
        assert union == {"sf-0", "sf-1", "sf-2"}


# ── CL3 briefing invariants (T19) ────────────────────────────────────
#
# Deterministic, builder-only fixtures proving the eight family buckets
# partition the full pre-truncation input, open_findings is derived exactly
# from acted-on/ignored/deferred (and retains IGNORED), no_open_blocking
# semantics, the NO_ADDITIONAL vs no_known distinction, cross-domain
# agreement between manifest and briefing, surfaced unavailable evidence,
# blind-mode history stripping, and post-truncation reachability.


def _cl3_build(
    families: list[str],
    *,
    budget_level: str = "exhaustive",
    domain_assignments: dict[str, str] | None = None,
    mode: str = ContextMode.HISTORY_AWARE.value,
    extra_disposition_kwargs: dict[str, dict] | None = None,
):
    """Build manifest + briefing from one finding per disposition family.

    Returns ``(briefing, all_sf_ids)`` so callers can assert invariants
    against the same deterministic builder path used in production.
    """
    occs = []
    recs = []
    disps = []
    extra_disposition_kwargs = extra_disposition_kwargs or {}
    for i, family in enumerate(families):
        oid = f"occ-{i}"
        sf_id = f"sf-{i}"
        occs.append(_make_occurrence(oid))
        recs.append(_make_reconciliation(
            f"rec-{i}", occurrence_ids=(oid,), semantic_finding_id=sf_id,
        ))
        disps.append(_make_disposition(
            f"disp-{i}", sf_id, family=family,
            **extra_disposition_kwargs.get(sf_id, {}),
        ))
    rec_result = apply_reconciliation_events(occs, recs)
    disp_result = apply_disposition_events(rec_result["finding_map"], disps)
    manifest = construct_manifest(occs, rec_result, disp_result)
    briefing = build_briefing(
        manifest, disp_result, rec_result["finding_map"],
        budget_level=budget_level,
        domain_assignments=domain_assignments,
        rec_result=rec_result,
        occurrences=occs,
        mode=mode,
    )
    return briefing, manifest, rec_result, [f"sf-{i}" for i in range(len(families))]


class TestCl3BriefingInvariants:
    _ALL_FAMILIES = [
        DispositionFamily.ACTED_ON.value,
        DispositionFamily.IGNORED.value,
        DispositionFamily.DEFERRED.value,
        DispositionFamily.REJECTED.value,
        DispositionFamily.DUPLICATE.value,
        DispositionFamily.ACCEPTED_RISK.value,
        DispositionFamily.UNKNOWN.value,
        DispositionFamily.RESOLVED.value,
    ]

    def test_eight_buckets_partition_full_pre_truncation_input(self) -> None:
        briefing, _, _, sf_ids = _cl3_build(self._ALL_FAMILIES)
        union = set(briefing.acted_on_findings) | set(briefing.ignored_findings) \
            | set(briefing.deferred_findings) | set(briefing.blocked_findings) \
            | set(briefing.accepted_risk_findings) | set(briefing.unknown_findings) \
            | set(briefing.resolved_findings) | set(briefing.duplicate_findings)
        assert union == set(sf_ids)
        # No finding appears in two family buckets.
        bucket_counts = {}
        for fid in sf_ids:
            bucket_counts[fid] = sum(
                fid in getattr(briefing, b) for b in (
                    "acted_on_findings", "ignored_findings", "deferred_findings",
                    "blocked_findings", "accepted_risk_findings",
                    "unknown_findings", "resolved_findings", "duplicate_findings",
                )
            )
        assert all(c == 1 for c in bucket_counts.values())

    def test_open_findings_equals_acted_ignored_deferred_and_retains_ignored(self) -> None:
        briefing, _, _, _ = _cl3_build([
            DispositionFamily.ACTED_ON.value,
            DispositionFamily.IGNORED.value,
            DispositionFamily.DEFERRED.value,
            DispositionFamily.RESOLVED.value,
        ])
        assert set(briefing.open_findings) == set(
            briefing.acted_on_findings
            + briefing.ignored_findings
            + briefing.deferred_findings
        )
        # IGNORED findings are retained in open_findings, not dropped.
        assert briefing.ignored_findings == ("sf-1",)
        assert "sf-1" in briefing.open_findings

    def test_no_open_blocking_findings_semantics_unchanged(self) -> None:
        # No open and no blocked -> True.
        closed, _, _, _ = _cl3_build([
            DispositionFamily.RESOLVED.value,
            DispositionFamily.DUPLICATE.value,
            DispositionFamily.ACCEPTED_RISK.value,
        ])
        assert closed.no_open_blocking_findings is True
        # A blocked finding -> False.
        with_block, _, _, _ = _cl3_build([
            DispositionFamily.RESOLVED.value,
            DispositionFamily.REJECTED.value,
        ])
        assert with_block.no_open_blocking_findings is False
        # An open finding -> False.
        with_open, _, _, _ = _cl3_build([
            DispositionFamily.RESOLVED.value,
            DispositionFamily.DEFERRED.value,
        ])
        assert with_open.no_open_blocking_findings is False

    def test_no_additional_findings_differs_from_no_known_findings(self) -> None:
        # A NO_ADDITIONAL_FINDINGS occurrence WITH a prior finding:
        # no_additional_findings True but no_known_findings False.
        occ_naf = _make_occurrence(
            "occ-naf", parse_status=ParseStatus.NO_ADDITIONAL_FINDINGS.value,
        )
        rec_result = apply_reconciliation_events([occ_naf], [])
        disp_result = apply_disposition_events(rec_result["finding_map"], [])
        manifest = construct_manifest([occ_naf], rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
            occurrences=[occ_naf],
        )
        assert briefing.no_additional_findings is True
        assert briefing.no_known_findings is True  # no findings at all here

        # Now add a real finding alongside the NO_ADDITIONAL occurrence:
        # no_additional_findings still True (admitted status), but
        # no_known_findings is False because the ledger holds a finding.
        occ_sel = _make_occurrence("occ-sel")
        rec_sel = _make_reconciliation("rec-sel", occurrence_ids=("occ-sel",), semantic_finding_id="sf-sel")
        disp_sel = _make_disposition("disp-sel", "sf-sel")
        rec_result2 = apply_reconciliation_events([occ_naf, occ_sel], [rec_sel])
        disp_result2 = apply_disposition_events(rec_result2["finding_map"], [disp_sel])
        manifest2 = construct_manifest([occ_naf, occ_sel], rec_result2, disp_result2)
        briefing2 = build_briefing(
            manifest2, disp_result2, rec_result2["finding_map"],
            occurrences=[occ_naf, occ_sel],
        )
        assert briefing2.no_additional_findings is True
        assert briefing2.no_known_findings is False

    def test_cross_domain_refs_agree_between_manifest_and_briefing(self) -> None:
        briefing, manifest, rec_result, _ = _cl3_build([DispositionFamily.ACTED_ON.value])
        # Inject a reconciliation-derived cross-domain ref into the shared
        # rec_result and rebuild manifest + briefing so both derive from the
        # same source set.
        rec_result["cross_domain_refs"] = ["domain-alpha", "domain-alpha", "domain-beta"]
        manifest = construct_manifest(
            [_make_occurrence("occ-0")], rec_result,
            apply_disposition_events(rec_result["finding_map"], [_make_disposition()]),
        )
        briefing = build_briefing(
            manifest,
            apply_disposition_events(rec_result["finding_map"], [_make_disposition()]),
            rec_result["finding_map"],
            rec_result=rec_result,
        )
        assert manifest.cross_domain_refs == briefing.cross_domain_refs
        assert manifest.cross_domain_refs == ("domain-alpha", "domain-beta")

    def test_unavailable_evidence_is_surfaced(self) -> None:
        occ = _make_occurrence(
            "occ-unavail",
            evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
            unavailable_reason="governed source offline",
        )
        rec = _make_reconciliation("rec-u", occurrence_ids=("occ-unavail",), semantic_finding_id="sf-u")
        rec_result = apply_reconciliation_events([occ], [rec])
        disp_result = apply_disposition_events(rec_result["finding_map"], [_make_disposition("disp-u", "sf-u")])
        manifest = construct_manifest([occ], rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
            rec_result=rec_result, occurrences=[occ],
        )
        assert briefing.evidence_unavailable
        assert "governed source offline" in briefing.evidence_unavailable

    def test_blind_mode_strips_history_but_retains_identity(self) -> None:
        from types import SimpleNamespace
        occ = _make_occurrence(
            "occ-blind",
            metadata={"prior_instructions": "do not regress X"},
        )
        rec = _make_reconciliation("rec-b", occurrence_ids=("occ-blind",), semantic_finding_id="sf-b")
        rec_result = apply_reconciliation_events([occ], [rec])
        rec_result["cross_domain_refs"] = ["other-domain"]
        disp = _make_disposition("disp-b", "sf-b", family=DispositionFamily.IGNORED.value)
        disp_result = apply_disposition_events(rec_result["finding_map"], [disp])
        manifest = construct_manifest([occ], rec_result, disp_result)
        fresh = [SimpleNamespace(is_stale=True, staleness_reason="source rotated")]
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
            rec_result=rec_result, occurrences=[occ],
            freshness_vectors=fresh,
            mode=ContextMode.BLIND.value,
        )
        # History / disposition fields are blanked.
        assert briefing.acted_on_findings == ()
        assert briefing.ignored_findings == ()
        assert briefing.open_findings == ()
        assert briefing.blocked_findings == ()
        assert briefing.cross_domain_refs == ()
        assert briefing.prior_instructions == ()
        assert briefing.stale_flag is False
        assert briefing.rebuild_trigger is None
        assert briefing.evidence_unavailable == ()
        # Identity / accounting fields are retained.
        assert briefing.revision_manifest_hash == manifest.input_set_hash or briefing.revision_manifest_hash
        assert briefing.input_set_hash == manifest.input_set_hash
        assert briefing.findings == ("sf-b",)
        assert briefing.domains == ("critique_ledger",)

    def test_retained_buckets_plus_split_refs_cover_every_finding(self) -> None:
        # Standard budget caps at 10 findings; build 11.
        families = [DispositionFamily.ACTED_ON.value] * 11
        briefing, manifest, rec_result, sf_ids = _cl3_build(
            families, budget_level="standard",
            domain_assignments={f"sf-{i}": "critique_ledger" for i in range(11)},
        )
        retained = set(briefing.findings)
        split_parents = {p for p, _r in briefing.split_parent_refs}
        assert (retained | split_parents) == set(sf_ids)
        assert briefing.spillover_findings
        assert all(r for _p, r in briefing.split_parent_refs)
        assert briefing.is_truncated is True


# ── Reviser projection ───────────────────────────────────────────────


class TestReviserProjection:
    def test_four_no_x_fields_present(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        projection = project_reviser_input(
            manifest, briefing, occs, disp_result,
        )
        # Four no-X fields
        assert "no_open_blocking_findings" in projection
        assert "no_additional_findings" in projection
        assert "no_known_findings" in projection
        assert "no_adjacent_text_match" in projection
        # No verdict field
        assert "verdict" not in projection
        assert "proceed" not in projection
        assert "block" not in projection

    def test_reviser_exposes_cumulative_truth(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        projection = project_reviser_input(
            manifest, briefing, occs, disp_result,
        )
        assert projection["manifest_id"] == manifest.manifest_id
        assert projection["input_set_hash"] == manifest.input_set_hash
        assert len(projection["finding_summaries"]) == 1

    def test_reviser_carries_actionable_disposed_unchanged_history(self) -> None:
        # CL4 (Step 7): the reviser projection must carry actionable_findings,
        # disposed_history, unchanged_findings, and revision_actions_required.
        # Every known finding appears in disposed_history regardless of family.
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        # ACCEPTED_RISK is an UNCHANGED family — remains visible, no action.
        disp_result = apply_disposition_events(
            rec_result["finding_map"],
            [_make_disposition(family=DispositionFamily.ACCEPTED_RISK.value)],
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        projection = project_reviser_input(
            manifest, briefing, occs, disp_result,
        )
        # All four enriched fields are present.
        assert "actionable_findings" in projection
        assert "disposed_history" in projection
        assert "unchanged_findings" in projection
        assert "revision_actions_required" in projection
        # ACCEPTED_RISK finding is unchanged (settled, visible) and not
        # actionable, so no revision action is required.
        assert projection["unchanged_findings"] == ["sf-1"]
        assert projection["actionable_findings"] == []
        assert projection["revision_actions_required"] is False
        # disposed_history retains the complete prior-disposition record.
        assert len(projection["disposed_history"]) == 1
        history = projection["disposed_history"][0]
        assert history["semantic_finding_id"] == "sf-1"
        assert history["family"] == DispositionFamily.ACCEPTED_RISK.value
        assert history["normalized_family"] == "accepted-risk"
        assert history["reopen_predicate"] == "default reopen predicate"

    def test_missing_action_coverage_sets_revision_actions_required(self) -> None:
        # CL4 (Step 7): an actionable finding (ADDRESSED_PENDING_VERIFICATION)
        # whose action has not been taken signals missing action coverage and
        # sets revision_actions_required=True. The finding still appears in
        # disposed_history so no known finding disappears.
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"],
            [
                _make_disposition(
                    family=DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value,
                    action_taken=False,
                    action_description=None,
                ),
            ],
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        projection = project_reviser_input(
            manifest, briefing, occs, disp_result,
        )
        # Actionable but action coverage missing -> flag True.
        assert projection["revision_actions_required"] is True
        assert len(projection["actionable_findings"]) == 1
        assert projection["actionable_findings"][0]["semantic_finding_id"] == "sf-1"
        assert projection["actionable_findings"][0]["action_taken"] is False
        # The finding is still surfaced in disposed_history (no disappearance).
        assert len(projection["disposed_history"]) == 1
        assert projection["disposed_history"][0]["semantic_finding_id"] == "sf-1"

    def test_acted_on_actionable_finding_does_not_require_flag(self) -> None:
        # CL4 (Step 7): an ACTED_ON finding carries a completed action, so it
        # is actionable but does NOT trip revision_actions_required.
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"],
            [
                _make_disposition(
                    family=DispositionFamily.ACTED_ON.value,
                    action_taken=True,
                    action_description="patched the offending module",
                ),
            ],
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        projection = project_reviser_input(
            manifest, briefing, occs, disp_result,
        )
        assert projection["revision_actions_required"] is False
        assert len(projection["actionable_findings"]) == 1
        assert projection["actionable_findings"][0]["action_taken"] is True

    def test_open_minor_ignored_finding_retains_reopen_predicate(self) -> None:
        # CL4 (Step 7): an open minor IGNORED finding carries a reopen
        # predicate. The reviser sees it in disposed_history with its reopen
        # predicate and evidence retained, so it remains visible (not dropped)
        # while flagged as ignored.
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"],
            [
                _make_disposition(
                    family=DispositionFamily.IGNORED.value,
                    reopen_predicate="monitor for regression over next cycle",
                    evidence_refs=("evidence-ignored-001",),
                ),
            ],
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        projection = project_reviser_input(
            manifest, briefing, occs, disp_result,
        )
        # IGNORED is an open (not actionable, not unchanged) minor finding.
        assert projection["revision_actions_required"] is False
        assert projection["actionable_findings"] == []
        assert projection["unchanged_findings"] == []
        # The open minor IGNORED finding is fully retained in history.
        ignored_entries = [
            h for h in projection["disposed_history"]
            if h["family"] == DispositionFamily.IGNORED.value
        ]
        assert len(ignored_entries) == 1
        entry = ignored_entries[0]
        assert entry["semantic_finding_id"] == "sf-1"
        assert entry["reopen_predicate"] == "monitor for regression over next cycle"
        assert entry["staleness_check_deferred"] is True
        assert entry["evidence_refs"] == ["evidence-ignored-001"]
        # It survives as a known finding in the briefing open set.
        assert "sf-1" in briefing.ignored_findings


# ── Gate projection ──────────────────────────────────────────────────


class TestGateProjection:
    def test_four_no_x_fields_present(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        custody_result = validate_occurrence_custody(
            occs, {"wbc-001": {"valid": True}},
        )
        projection = project_gate_input(
            manifest, briefing, occs, rec_result, disp_result, custody_result,
        )
        # Four no-X fields
        assert "no_open_blocking_findings" in projection
        assert "no_additional_findings" in projection
        assert "no_known_findings" in projection
        assert "no_adjacent_text_match" in projection
        # No verdict
        assert "verdict" not in projection
        assert "proceed" not in projection
        assert "block" not in projection

    def test_gate_exposes_custody_and_reconciliation_signals(self) -> None:
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        custody_result = validate_occurrence_custody(
            occs, {"wbc-001": {"valid": True}},
        )
        projection = project_gate_input(
            manifest, briefing, occs, rec_result, disp_result, custody_result,
        )
        assert projection["custody_valid"] is True
        assert projection["custody_failure_count"] == 0
        assert projection["reconciliation_accepted"] is True
        assert projection["disposition_accepted"] is True

    def test_gate_counts_failed_dropped_malformed(self) -> None:
        occs = [
            _make_occurrence("occ-ok", parse_status=ParseStatus.SELECTED.value),
            _make_occurrence("occ-fail", parse_status=ParseStatus.FAILED.value),
            _make_occurrence("occ-drop", parse_status=ParseStatus.DROPPED.value),
            _make_occurrence("occ-malf", parse_status=ParseStatus.MALFORMED.value),
        ]
        # Only the eligible occurrence is reconciled; FAILED/DROPPED/MALFORMED
        # are accounted as excluded-from-finding-map rather than halting.
        recs = [_make_reconciliation("rec-ok", occurrence_ids=("occ-ok",), semantic_finding_id="sf-ok")]
        rec_result = apply_reconciliation_events(occs, recs)
        # CL4 (Step 3): every input occurrence has exactly one accounting row.
        accounting = rec_result["occurrence_accounting"]
        assert len(accounting) == 4
        by_occ = {row["occurrence_id"]: row for row in accounting}
        # The eligible SELECTED occurrence is mapped to its finding.
        assert by_occ["occ-ok"]["disposition"] == "mapped-to-finding"
        assert by_occ["occ-ok"]["semantic_finding_id_or_null"] == "sf-ok"
        # FAILED/DROPPED/MALFORMED are surfaced as excluded-from-finding-map
        # with explicit reasons — never confused with NO_ADDITIONAL_FINDINGS.
        for oid, status in (
            ("occ-fail", ParseStatus.FAILED.value),
            ("occ-drop", ParseStatus.DROPPED.value),
            ("occ-malf", ParseStatus.MALFORMED.value),
        ):
            assert by_occ[oid]["disposition"] == "excluded-from-finding-map", oid
            assert by_occ[oid]["parse_status"] == status, oid
            assert by_occ[oid]["semantic_finding_id_or_null"] is None, oid
            assert status in by_occ[oid]["reason"], oid
        # Excluded occurrences never enter the finding_map.
        all_mapped: set[str] = set()
        for _oids in rec_result["finding_map"].values():
            all_mapped.update(_oids)
        assert all_mapped == {"occ-ok"}
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition("disp-ok", "sf-ok")],
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        custody_result = validate_occurrence_custody(
            occs, {"wbc-001": {"valid": True}},
        )
        projection = project_gate_input(
            manifest, briefing, occs, rec_result, disp_result, custody_result,
        )
        # No halt: the gate observes the three terminal-failure occurrences.
        assert projection["occurrence_failed_dropped_malformed"] == 3

    def test_unavailable_evidence_tracked(self) -> None:
        occs = [
            _make_occurrence("occ-1", evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
                           unavailable_reason="Repo not restored", reopen_condition="Restore repo"),
        ]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation(occurrence_ids=("occ-1",))]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"], [_make_disposition()]
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        reviser = project_reviser_input(
            manifest, briefing, occs, disp_result,
        )
        assert "occ-1" in reviser["unavailable_evidence"]

    def test_gate_carries_enriched_truthful_claim_fields(self) -> None:
        # CL4 (Step 8): the gate projection carries the enriched fields that
        # ground any acceptance claim: accepted_ledger_revision,
        # occurrence_coverage_proof, disposition_state, revision_actions,
        # and independent_verification — while preserving no_adjacent_text_match.
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"],
            [_make_disposition(family=DispositionFamily.ACCEPTED_RISK.value)],
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        custody_result = validate_occurrence_custody(
            occs, {"wbc-001": {"valid": True}},
        )
        projection = project_gate_input(
            manifest, briefing, occs, rec_result, disp_result, custody_result,
        )
        # All five enriched fields are present.
        assert "accepted_ledger_revision" in projection
        assert "occurrence_coverage_proof" in projection
        assert "disposition_state" in projection
        assert "revision_actions" in projection
        assert "independent_verification" in projection
        # accepted_ledger_revision matches the manifest identity.
        assert projection["accepted_ledger_revision"]["manifest_id"] == manifest.manifest_id
        assert projection["accepted_ledger_revision"]["revision_number"] == manifest.revision_number
        assert projection["accepted_ledger_revision"]["input_set_hash"] == manifest.input_set_hash
        # occurrence_coverage_proof is exact and complete.
        proof = projection["occurrence_coverage_proof"]
        assert proof["total_input_occurrences"] == 1
        assert proof["accounting_row_count"] == 1
        assert proof["complete"] is True
        assert proof["reconciliation_accepted"] is True
        # disposition_state carries the normalized family and family counts.
        assert projection["disposition_state"]["family_counts"] == {"accepted-risk": 1}
        assert "sf-1" in projection["disposition_state"]["findings"]
        assert (
            projection["disposition_state"]["findings"]["sf-1"]["normalized_family"]
            == "accepted-risk"
        )
        # revision_actions has no actionable findings here.
        assert projection["revision_actions"]["actionable_findings"] == []
        assert projection["revision_actions"]["revision_actions_required"] is False
        # No verified/pending findings -> independent_verification reflects it.
        assert projection["independent_verification"]["verified_findings"] == []
        assert projection["independent_verification"]["pending_verification_findings"] == []
        assert projection["independent_verification"]["has_verification_evidence"] is False
        # The adjacency no-X field is preserved.
        assert "no_adjacent_text_match" in projection

    def test_gate_surfaces_open_minor_disposition(self) -> None:
        # CL4 (Step 8): an open-minor IGNORED disposition (gate-acceptable,
        # non-blocking) survives to the gate projection with its reopen
        # predicate and staleness flag intact.
        occs = [_make_occurrence("occ-1")]
        rec_result = apply_reconciliation_events(
            occs, [_make_reconciliation()]
        )
        disp_result = apply_disposition_events(
            rec_result["finding_map"],
            [
                _make_disposition(
                    family=DispositionFamily.IGNORED.value,
                    reopen_predicate="monitor for regression",
                ),
            ],
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        custody_result = validate_occurrence_custody(
            occs, {"wbc-001": {"valid": True}},
        )
        projection = project_gate_input(
            manifest, briefing, occs, rec_result, disp_result, custody_result,
        )
        # IGNORED is open but not blocking: the gate accepts it as known.
        state = projection["disposition_state"]["findings"]["sf-1"]
        assert state["family"] == DispositionFamily.IGNORED.value
        assert state["reopen_predicate"] == "monitor for regression"
        assert state["staleness_check_deferred"] is True
        # IGNORED is not actionable nor verified.
        assert projection["revision_actions"]["actionable_findings"] == []
        assert projection["revision_actions"]["revision_actions_required"] is False
        assert projection["independent_verification"]["verified_findings"] == []
        # It still counts as an open finding at the gate.
        assert projection["open_finding_count"] == 1

    def test_gate_surfaces_merge_relationship_coverage(self) -> None:
        # CL4 (Step 8): a MERGE reconciliation relationship surfaces in the
        # gate projection's occurrence coverage proof and disposition state.
        occs = [
            _make_occurrence("occ-a"),
            _make_occurrence("occ-b"),
        ]
        recs = [
            _make_reconciliation(
                reconciliation_id="rec-merge",
                occurrence_ids=("occ-a", "occ-b"),
                semantic_finding_id="sf-merge",
                relationship=Relationship.MERGE.value,
                reason="two occurrences describe the same merged concern",
            ),
        ]
        rec_result = apply_reconciliation_events(occs, recs)
        assert rec_result["accepted"] is True
        disp_result = apply_disposition_events(
            rec_result["finding_map"],
            [_make_disposition("disp-merge", "sf-merge", family=DispositionFamily.ACCEPTED_RISK.value)],
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        custody_result = validate_occurrence_custody(
            occs, {"wbc-001": {"valid": True}},
        )
        projection = project_gate_input(
            manifest, briefing, occs, rec_result, disp_result, custody_result,
        )
        # Both merged occurrences are accounted exactly once.
        proof = projection["occurrence_coverage_proof"]
        assert proof["total_input_occurrences"] == 2
        assert proof["accounting_row_count"] == 2
        assert proof["complete"] is True
        accounted = {row["occurrence_id"] for row in proof["occurrence_accounting"]}
        assert accounted == {"occ-a", "occ-b"}
        # The merged finding is present in disposition_state.
        assert "sf-merge" in projection["disposition_state"]["findings"]

    def test_gate_propagates_reopen_as_actionable(self) -> None:
        # CL4 (Step 8): a REOPEN reconciliation event propagates an actionable
        # finding to the gate projection — the reopen is counted and the
        # reopened finding's disposition (ACTED_ON with a completed action)
        # is surfaced as actionable.
        occs = [_make_occurrence("occ-1")]
        recs = [
            _make_reconciliation(
                reconciliation_id="rec-reopen",
                occurrence_ids=("occ-1",),
                semantic_finding_id="sf-1",
                relationship=Relationship.REOPEN.value,
                reason="concern regressed; reopened for re-action",
                is_reopen=True,
                reopen_condition="regression observed in production",
            ),
        ]
        rec_result = apply_reconciliation_events(occs, recs)
        assert rec_result["accepted"] is True
        assert len(rec_result["reopen_events"]) == 1
        disp_result = apply_disposition_events(
            rec_result["finding_map"],
            [
                _make_disposition(
                    family=DispositionFamily.ACTED_ON.value,
                    action_taken=True,
                    action_description="hotfix applied and redeployed",
                ),
            ],
        )
        manifest = construct_manifest(occs, rec_result, disp_result)
        briefing = build_briefing(
            manifest, disp_result, rec_result["finding_map"],
        )
        custody_result = validate_occurrence_custody(
            occs, {"wbc-001": {"valid": True}},
        )
        projection = project_gate_input(
            manifest, briefing, occs, rec_result, disp_result, custody_result,
        )
        # The reopen event is counted at the gate.
        assert projection["reopen_event_count"] == 1
        # The reopened finding is propagated as actionable.
        assert projection["revision_actions"]["actionable_findings"] == ["sf-1"]
        # ACTED_ON carries a completed action -> no missing coverage.
        assert projection["revision_actions"]["revision_actions_required"] is False
        state = projection["disposition_state"]["findings"]["sf-1"]
        assert state["family"] == DispositionFamily.ACTED_ON.value
        assert state["action_taken"] is True


# ── Complete replay ──────────────────────────────────────────────────


class TestReplayFull:
    def test_full_replay_produces_all_phases(self) -> None:
        occs = [_make_occurrence("occ-1")]
        recs = [_make_reconciliation()]
        disps = [_make_disposition()]
        result = replay_full(
            occs, recs, disps,
            wbc_receipt_chain={"wbc-001": {"valid": True}},
        )
        assert "custody" in result
        assert "reconciliation" in result
        assert "disposition" in result
        assert "manifest" in result
        assert "briefing" in result
        assert "reviser_projection" in result
        assert "gate_projection" in result

    def test_replay_fails_on_invalid_occurrence(self) -> None:
        # CL4 (Step 3): a FAILED occurrence no longer halts replay with
        # OCCURRENCE_PARSE_FAILED before reconciliation. It now flows through
        # reconciliation and receives an explicit excluded-from-finding-map
        # accounting entry with a reason, surfaced at the gate instead of
        # raised before reconciliation runs.
        occs = [_make_occurrence("occ-1", parse_status=ParseStatus.FAILED.value)]
        result = replay_full(
            occs, [], [], wbc_receipt_chain={"wbc-001": {"valid": True}},
        )
        accounting = result["reconciliation"]["occurrence_accounting"]
        assert len(accounting) == 1
        row = accounting[0]
        assert row["occurrence_id"] == "occ-1"
        assert row["parse_status"] == ParseStatus.FAILED.value
        assert row["disposition"] == "excluded-from-finding-map"
        assert ParseStatus.FAILED.value in row["reason"]
        assert row["semantic_finding_id_or_null"] is None
        # No finding was produced; the gate observes the failed occurrence.
        assert result["gate_projection"]["occurrence_failed_dropped_malformed"] == 1
        assert result["gate_projection"]["no_known_findings"] is True

    def test_replay_fails_on_custody_broken(self) -> None:
        occs = [_make_occurrence("occ-1", custody_receipt_refs=("wbc-999",))]
        with pytest.raises(SemanticLoopError):
            replay_full(
                occs,
                [_make_reconciliation()],
                [_make_disposition()],
                wbc_receipt_chain={"wbc-001": {"valid": True}},
            )

    def test_replay_fails_on_reconciliation_orphan(self) -> None:
        occs = [_make_occurrence("occ-1")]
        recs = [_make_reconciliation(occurrence_ids=("nonexistent",))]
        with pytest.raises(SemanticLoopError) as exc:
            replay_full(occs, recs, [], wbc_receipt_chain={"wbc-001": {"valid": True}})

    def test_replay_fails_on_disposition_orphan(self) -> None:
        occs = [_make_occurrence("occ-1")]
        recs = [_make_reconciliation()]
        disps = [_make_disposition(semantic_finding_id="nonexistent")]
        with pytest.raises(SemanticLoopError) as exc:
            replay_full(occs, recs, disps, wbc_receipt_chain={"wbc-001": {"valid": True}})

    def test_accepted_replay_limitation_preserved(self) -> None:
        """Oracle fact 5: accepted replay limitation with reopen condition."""
        occs = [_make_occurrence("occ-1",
            evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
            unavailable_reason="Preserved repo not available",
            reopen_condition="Restore preserved repo at ea2be1fe",
        )]
        recs = [_make_reconciliation()]
        disps = [_make_disposition(
            is_reopen=True,
            reopen_predicate="Restore preserved repo at ea2be1fe",
        )]
        result = replay_full(
            occs, recs, disps,
            wbc_receipt_chain={"wbc-001": {"valid": True}},
        )
        # Reopen events tracked
        assert result["gate_projection"]["reopen_event_count"] == 0
        # But unavailable evidence tracked
        assert "occ-1" in result["reviser_projection"]["unavailable_evidence"]

    def test_m6_five_occurrences_one_semantic_finding(self) -> None:
        """Oracle fact 4: five occurrences → one semantic finding via
        evaluator-authored reconciliation event, never inferred."""
        occs = [
            CritiqueOccurrenceEnvelope(
                occurrence_id=f"occ-v{i}-CF-CD1C",
                attempt_id="attempt-v1",
                round_label=f"v{i}",
                finding_id="CF-CD1C58FBC288E3BBA77C",
                producer_id="test-producer",
                model_id="test-model",
                context_mode=ContextMode.HISTORY_AWARE.value,
                parse_status=ParseStatus.SELECTED.value,
                evidence_availability=EvidenceAvailability.RETAINED.value,
                custody_receipt_refs=("wbc-001",),
            )
            for i in range(1, 6)
        ]
        recs = [
            _make_reconciliation(
                "rec-scope-god-task",
                occurrence_ids=tuple(f"occ-v{i}-CF-CD1C" for i in range(1, 6)),
                semantic_finding_id="sem-finding-scope-god-task",
                reason="Same scope/work-sizing concern (god-tasks) across five rounds",
            ),
        ]
        disps = [
            _make_disposition(
                "disp-scope-god-task",
                "sem-finding-scope-god-task",
                family=DispositionFamily.ACCEPTED_RISK.value,
                is_reopen=True,
                reopen_predicate="Re-run generate_cl1_m6_corpus.py when preserved repo restored",
            ),
        ]
        result = replay_full(
            occs, recs, disps,
            wbc_receipt_chain={"wbc-001": {"valid": True}},
            budget_level="standard",
            domain_assignments={"sem-finding-scope-god-task": "critique_ledger"},
        )
        # Five occurrences mapped to one semantic finding
        fm = result["reconciliation"]["finding_map"]
        assert len(fm) == 1
        assert len(fm["sem-finding-scope-god-task"]) == 5
        # Disposition is accepted-risk
        assert result["disposition"]["family_counts"]["accepted-risk"] == 1
        # Gate projection has no blocking findings
        assert result["gate_projection"]["blocking_finding_count"] == 0
        assert result["gate_projection"]["open_finding_count"] == 0
