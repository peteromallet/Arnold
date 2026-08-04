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
    return FindingDispositionEvent(
        disposition_id=disposition_id,
        semantic_finding_id=semantic_finding_id,
        family=family,
        authority=Authority.EVALUATOR.value,
        **kwargs,
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
        # Only valid occurrence gets reconciled
        recs = [_make_reconciliation("rec-ok", occurrence_ids=("occ-ok",), semantic_finding_id="sf-ok")]
        rec_result = apply_reconciliation_events(occs, recs)
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
        occs = [_make_occurrence("occ-1", parse_status=ParseStatus.FAILED.value)]
        with pytest.raises(SemanticLoopError) as exc:
            replay_full(occs, [], [], wbc_receipt_chain={"wbc-001": {"valid": True}})
        assert exc.value.mode == FailureMode.OCCURRENCE_PARSE_FAILED

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
