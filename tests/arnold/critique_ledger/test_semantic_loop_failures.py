"""Failure, retry, and no-side-effect contract tests for the semantic loop."""

from __future__ import annotations

from dataclasses import asdict

import pytest

import arnold.critique_ledger.semantic_loop as semantic_loop
from arnold.critique_ledger.schemas import (
    Authority,
    ContextMode,
    CritiqueOccurrenceEnvelope,
    DispositionFamily,
    EvidenceAvailability,
    FindingDispositionEvent,
    FindingReconciliationEvent,
    ParseStatus,
    Relationship,
    canonical_hash,
)
from arnold.critique_ledger.semantic_loop import (
    FailureMode,
    SemanticLoopError,
    replay_full,
    validate_occurrence_custody,
)


def _occ(
    occurrence_id: str = "occ-1",
    *,
    parse_status: str = ParseStatus.SELECTED.value,
    evidence_availability: str = EvidenceAvailability.RETAINED.value,
    producer_id: str = "critic",
    metadata: dict | None = None,
    unavailable_reason: str | None = None,
    reopen_condition: str | None = None,
    schema_version: str = "cl.schema.v1",
    receipts: tuple[str, ...] = ("wbc-1",),
) -> CritiqueOccurrenceEnvelope:
    return CritiqueOccurrenceEnvelope(
        schema_version=schema_version,
        occurrence_id=occurrence_id,
        attempt_id="attempt-1",
        round_label="v1",
        finding_id=f"finding-{occurrence_id}",
        producer_id=producer_id,
        model_id="model",
        context_mode=ContextMode.HISTORY_AWARE.value,
        parse_status=parse_status,
        evidence_availability=evidence_availability,
        unavailable_reason=unavailable_reason,
        reopen_condition=reopen_condition,
        custody_receipt_refs=receipts,
        metadata=metadata or {},
    )


def _rec(
    occurrence_ids: tuple[str, ...] = ("occ-1",),
    *,
    reconciliation_id: str = "rec-1",
    semantic_finding_id: str = "sf-1",
    authority: str = Authority.EVALUATOR.value,
) -> FindingReconciliationEvent:
    return FindingReconciliationEvent(
        reconciliation_id=reconciliation_id,
        canonical_finding_id="finding-1",
        semantic_finding_id=semantic_finding_id,
        occurrence_ids=occurrence_ids,
        relationship=Relationship.DUPLICATE.value,
        authority=authority,
        reason="Evaluator-authored semantic relationship",
    )


def _disp(
    semantic_finding_id: str = "sf-1",
    *,
    disposition_id: str = "disp-1",
    family: str = DispositionFamily.ACCEPTED_RISK.value,
    authority: str = Authority.EVALUATOR.value,
    reason_subcode: str = "",
    evidence_refs: tuple[str, ...] = (),
    reopen_predicate: str = "default reopen predicate",
) -> FindingDispositionEvent:
    # CL4 (Step 5): ACCEPTED_RISK (the default family) requires a
    # reopen_predicate under per-family field-presence validation, so the
    # helper supplies one by default. Tests that exercise a missing-field
    # failure pass reopen_predicate=None explicitly.
    return FindingDispositionEvent(
        disposition_id=disposition_id,
        semantic_finding_id=semantic_finding_id,
        family=family,
        authority=authority,
        reason_subcode=reason_subcode,
        evidence_refs=evidence_refs,
        reopen_predicate=reopen_predicate,
    )


def _replay(
    occurrences: list[CritiqueOccurrenceEnvelope] | None = None,
    reconciliations: list[FindingReconciliationEvent] | None = None,
    dispositions: list[FindingDispositionEvent] | None = None,
    **kwargs,
):
    return replay_full(
        occurrences if occurrences is not None else [_occ()],
        reconciliations if reconciliations is not None else [_rec()],
        dispositions if dispositions is not None else [_disp()],
        wbc_receipt_chain={"wbc-1": {"valid": True}},
        **kwargs,
    )


def _assert_mode(mode: FailureMode, **kwargs) -> SemanticLoopError:
    with pytest.raises(SemanticLoopError) as exc:
        _replay(**kwargs)
    assert exc.value.mode == mode
    return exc.value


def _occ_for_status(status: str) -> CritiqueOccurrenceEnvelope:
    """Build a custody-valid occurrence for a given parse status.

    TOMBSTONED occurrences require a tombstone_reason to pass replay_full's
    Phase 0 check; the other statuses need no extra metadata under the
    default evidence/producer setup.
    """
    if status == ParseStatus.TOMBSTONED.value:
        return _occ(
            parse_status=status, metadata={"tombstone_reason": "revoked"}
        )
    return _occ(parse_status=status)


# CL4 (Step 4): finding-eligible parse statuses REQUIRE exactly one
# reconciliation mapping; every other status is accounted without one.
_REQUIRES_RECONCILIATION_STATUSES = (
    ParseStatus.SELECTED.value,
    ParseStatus.COMPLETED.value,
)
_NO_RECONCILIATION_REQUIRED_STATUSES = (
    ParseStatus.FAILED.value,
    ParseStatus.DROPPED.value,
    ParseStatus.MALFORMED.value,
    ParseStatus.TOMBSTONED.value,
    ParseStatus.NO_ADDITIONAL_FINDINGS.value,
)


def test_duplicate_occurrence_identity_fails_before_projection() -> None:
    _assert_mode(
        FailureMode.OCCURRENCE_DUPLICATE_ID,
        occurrences=[_occ("same"), _occ("same")],
    )


def test_incompatible_schema_fails_closed() -> None:
    _assert_mode(
        FailureMode.SCHEMA_INCOMPATIBLE,
        occurrences=[_occ(schema_version="cl.schema.v999")],
    )


def test_missing_semantic_authority_fails_closed() -> None:
    _assert_mode(
        FailureMode.OWNERSHIP_MISSING,
        reconciliations=[_rec(authority="invalid-authority")])


@pytest.mark.parametrize(
    ("metadata", "mode"),
    [
        ({"start_persisted": False}, FailureMode.START_PERSISTENCE_FAILED),
        ({"terminal_persisted": False}, FailureMode.TERMINAL_PERSISTENCE_FAILED),
        ({"terminal_outcome_count": 0}, FailureMode.TERMINAL_OUTCOME_INVALID),
        ({"terminal_outcome_count": 2}, FailureMode.TERMINAL_OUTCOME_INVALID),
        ({"evidence_fresh": False}, FailureMode.EVIDENCE_STALE),
    ],
)
def test_attempt_and_freshness_failures_are_typed(
    metadata: dict, mode: FailureMode
) -> None:
    _assert_mode(mode, occurrences=[_occ(metadata=metadata)])


def test_dropped_attempt_is_not_treated_as_no_finding() -> None:
    # CL4 (Step 3): a DROPPED occurrence no longer halts replay. It flows
    # through reconciliation and receives an explicit excluded-from-finding-map
    # accounting entry with a reason, preserving the invariant — DROPPED is
    # surfaced (never silently ignored) and never confused with
    # NO_ADDITIONAL_FINDINGS.
    result = _replay(
        occurrences=[_occ(parse_status=ParseStatus.DROPPED.value)],
        reconciliations=[],
        dispositions=[],
    )
    accounting = result["reconciliation"]["occurrence_accounting"]
    assert len(accounting) == 1
    row = accounting[0]
    assert row["occurrence_id"] == "occ-1"
    assert row["parse_status"] == ParseStatus.DROPPED.value
    assert row["disposition"] == "excluded-from-finding-map"
    assert ParseStatus.DROPPED.value in row["reason"]
    assert row["semantic_finding_id_or_null"] is None
    # DROPPED is distinct from a no-additional-findings assertion.
    assert result["gate_projection"]["no_additional_findings"] is False
    assert result["gate_projection"]["no_known_findings"] is True


def test_unavailable_evidence_requires_reason_and_reopen_condition() -> None:
    occurrence = _occ(evidence_availability=EvidenceAvailability.UNAVAILABLE.value)
    result = validate_occurrence_custody(
        [occurrence], {"wbc-1": {"valid": True}}
    )
    assert result["valid"] is False
    assert result["failures"][0]["mode"] == FailureMode.CUSTODY_UNAVAILABLE_EVIDENCE


def test_required_briefing_input_cannot_be_unavailable() -> None:
    _assert_mode(
        FailureMode.BRIEFING_INPUT_UNAVAILABLE,
        occurrences=[
            _occ(
                evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
                unavailable_reason="governed source offline",
                reopen_condition="restore governed source",
                metadata={"required_for_briefing": True},
            )
        ],
    )


def test_tombstone_requires_explicit_reason() -> None:
    _assert_mode(
        FailureMode.TOMBSTONE_INVALID,
        occurrences=[_occ(parse_status=ParseStatus.TOMBSTONED.value)],
    )


@pytest.mark.parametrize(
    ("status", "requires_reconciliation"),
    [
        (status, True) for status in _REQUIRES_RECONCILIATION_STATUSES
    ] + [
        (status, False) for status in _NO_RECONCILIATION_REQUIRED_STATUSES
    ],
)
def test_every_parseable_occurrence_requires_one_reconciliation(
    status: str, requires_reconciliation: bool,
) -> None:
    # CL4 (Step 4): the accounting completeness proof is exercised across
    # every ParseStatus. Finding-eligible statuses (SELECTED, COMPLETED) with
    # no reconciliation raise OCCURRENCE_UNMAPPED; excluded and no-content
    # statuses are covered by exactly one accounting row and accepted.
    occurrence = _occ_for_status(status)
    if requires_reconciliation:
        _assert_mode(
            FailureMode.OCCURRENCE_UNMAPPED,
            occurrences=[occurrence],
            reconciliations=[],
            dispositions=[],
        )
    else:
        result = _replay(
            occurrences=[occurrence],
            reconciliations=[],
            dispositions=[],
        )
        accounting = result["reconciliation"]["occurrence_accounting"]
        assert len(accounting) == 1
        assert accounting[0]["parse_status"] == status
        assert accounting[0]["semantic_finding_id_or_null"] is None
        assert result["reconciliation"]["accepted"] is True


@pytest.mark.parametrize(
    ("status", "expect_multiply_mapped"),
    [
        (status, True) for status in _REQUIRES_RECONCILIATION_STATUSES
    ] + [
        (status, False) for status in _NO_RECONCILIATION_REQUIRED_STATUSES
    ],
)
def test_occurrence_cannot_map_to_two_semantic_findings(
    status: str, expect_multiply_mapped: bool,
) -> None:
    # CL4 (Step 4): an eligible occurrence mapped to two semantic findings is
    # an OCCURRENCE_MULTIPLY_MAPPED hard failure detected by the accounting
    # completeness proof. Non-eligible statuses are removed from the
    # finding_map by the eligibility filter, so two reconciliation events
    # targeting them cannot produce a multiply-mapped accounting row — they
    # are accounted as excluded/no-content instead.
    occurrence = _occ_for_status(status)
    recs = [
        _rec(reconciliation_id="rec-1", semantic_finding_id="sf-1"),
        _rec(reconciliation_id="rec-2", semantic_finding_id="sf-2"),
    ]
    if expect_multiply_mapped:
        _assert_mode(
            FailureMode.OCCURRENCE_MULTIPLY_MAPPED,
            occurrences=[occurrence],
            reconciliations=recs,
            dispositions=[_disp("sf-1"), _disp("sf-2", disposition_id="disp-2")],
        )
    else:
        result = _replay(
            occurrences=[occurrence],
            reconciliations=recs,
            dispositions=[],
        )
        accounting = result["reconciliation"]["occurrence_accounting"]
        assert len(accounting) == 1
        assert accounting[0]["disposition"] != "mapped-to-finding"
        assert accounting[0]["semantic_finding_id_or_null"] is None


def test_every_semantic_finding_requires_disposition() -> None:
    _assert_mode(FailureMode.DISPOSITION_INCOMPLETE, dispositions=[])


def test_resolved_closure_requires_reason_and_evidence() -> None:
    _assert_mode(
        FailureMode.CLOSURE_UNSUPPORTED,
        dispositions=[_disp(family=DispositionFamily.RESOLVED.value)],
    )


# ── CL4 (Plan Step 6): closure backstop covers both closure values ────
# apply_disposition_events is the PRIMARY enforcement for the new
# RESOLVED_VERIFIED value; replay_full's inline closure check is the
# redundant backstop, normalized so it covers BOTH the legacy RESOLVED
# value and the new RESOLVED_VERIFIED value equivalently.


def test_resolved_verified_lacking_evidence_rejected_through_replay() -> None:
    # Tracing a RESOLVED_VERIFIED disposition lacking verification evidence
    # through replay_full raises CLOSURE_UNSUPPORTED (equivalent to legacy
    # RESOLVED above), so the verified value cannot bypass closure.
    _assert_mode(
        FailureMode.CLOSURE_UNSUPPORTED,
        dispositions=[_disp(family=DispositionFamily.RESOLVED_VERIFIED.value)],
    )


def test_resolved_verified_with_evidence_passes_replay() -> None:
    # A RESOLVED_VERIFIED closure carrying verification evidence AND a
    # reason_subcode is permitted through the full replay (both the
    # primary enforcement and the normalized backstop accept it).
    result = _replay(
        dispositions=[
            _disp(
                family=DispositionFamily.RESOLVED_VERIFIED.value,
                evidence_refs=("verified-against-reproducer",),
                reason_subcode="verified",
            )
        ]
    )
    assert result["disposition"]["accepted"] is True


def test_resolved_verified_with_evidence_but_no_reason_rejected_by_backstop() -> None:
    # The primary enforcement only checks evidence; the redundant backstop
    # additionally requires reason_subcode and, via normalization, applies to
    # the new verified value too. A RESOLVED_VERIFIED with evidence but no
    # reason is therefore caught by the inline backstop.
    _assert_mode(
        FailureMode.CLOSURE_UNSUPPORTED,
        dispositions=[
            _disp(
                family=DispositionFamily.RESOLVED_VERIFIED.value,
                evidence_refs=("verified-against-reproducer",),
            )
        ],
    )


def test_prior_revision_hash_mismatch_fails_closed() -> None:
    prior = _replay()["manifest"]
    _assert_mode(
        FailureMode.PRIOR_REVISION_CHAIN_BROKEN,
        prior_manifest=prior,
        expected_prior_revision_hash="not-the-prior-hash",
    )


def test_projection_mismatch_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = semantic_loop.project_gate_input

    def mismatched(*args, **kwargs):
        projection = original(*args, **kwargs)
        # CL4 (Step 8): the enriched gate fields must round-trip through the
        # monkeypatched projection so the fake-return shape stays consistent
        # with the real project_gate_input contract before no_known_findings
        # is flipped to force the deterministic mismatch assertion.
        for _field in (
            "accepted_ledger_revision",
            "occurrence_coverage_proof",
            "disposition_state",
            "revision_actions",
            "independent_verification",
        ):
            assert _field in projection, f"enriched gate field missing: {_field}"
        projection["no_known_findings"] = not projection["no_known_findings"]
        return projection

    monkeypatch.setattr(semantic_loop, "project_gate_input", mismatched)
    _assert_mode(FailureMode.REPLAY_PROJECTION_MISMATCH)


def test_failure_does_not_mutate_inputs_or_emit_projection() -> None:
    occurrences = [_occ()]
    reconciliations = [_rec(occurrence_ids=("missing",))]
    dispositions = [_disp()]
    before = (
        [asdict(item) for item in occurrences],
        [asdict(item) for item in reconciliations],
        [asdict(item) for item in dispositions],
    )
    with pytest.raises(SemanticLoopError) as exc:
        _replay(occurrences, reconciliations, dispositions)
    assert exc.value.mode == FailureMode.RECONCILIATION_ORPHAN_OCCURRENCE
    after = (
        [asdict(item) for item in occurrences],
        [asdict(item) for item in reconciliations],
        [asdict(item) for item in dispositions],
    )
    assert after == before


def test_retry_replay_is_content_deterministic() -> None:
    first = _replay()
    second = _replay()
    assert canonical_hash(first["manifest"]) == canonical_hash(second["manifest"])
    assert canonical_hash(first["briefing"]) == canonical_hash(second["briefing"])
    assert first["reviser_projection"] == second["reviser_projection"]
    assert first["gate_projection"] == second["gate_projection"]


def test_malformed_unavailable_evidence_is_preserved_as_unknown() -> None:
    result = _replay(
        occurrences=[
            _occ(
                parse_status=ParseStatus.MALFORMED.value,
                evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
                unavailable_reason="producer output could not be parsed",
                reopen_condition="reparse retained completion",
            )
        ],
        reconciliations=[],
        dispositions=[],
    )
    assert result["gate_projection"]["occurrence_failed_dropped_malformed"] == 1
    assert "occ-1" in result["gate_projection"]["unavailable_evidence"]
    assert result["gate_projection"]["no_known_findings"] is True


def test_no_additional_findings_is_explicit_success() -> None:
    result = _replay(
        occurrences=[
            _occ(parse_status=ParseStatus.NO_ADDITIONAL_FINDINGS.value)
        ],
        reconciliations=[],
        dispositions=[],
    )
    # CL4 (Step 4): NO_ADDITIONAL_FINDINGS is covered by exactly one
    # accounting row that the completeness proof accepts — it is never an
    # OCCURRENCE_UNMAPPED failure despite carrying no semantic finding.
    accounting = result["reconciliation"]["occurrence_accounting"]
    assert len(accounting) == 1
    assert accounting[0]["disposition"] == "no-additional-findings"
    assert accounting[0]["semantic_finding_id_or_null"] is None
    assert result["reconciliation"]["accepted"] is True
    assert result["gate_projection"]["custody_valid"] is True
    assert result["gate_projection"]["no_additional_findings"] is True
    assert result["gate_projection"]["no_known_findings"] is True
