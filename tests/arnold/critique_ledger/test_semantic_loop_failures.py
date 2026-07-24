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
) -> FindingDispositionEvent:
    return FindingDispositionEvent(
        disposition_id=disposition_id,
        semantic_finding_id=semantic_finding_id,
        family=family,
        authority=authority,
        reason_subcode=reason_subcode,
        evidence_refs=evidence_refs,
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
    _assert_mode(
        FailureMode.ATTEMPT_DROPPED,
        occurrences=[_occ(parse_status=ParseStatus.DROPPED.value)],
    )


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


def test_every_parseable_occurrence_requires_one_reconciliation() -> None:
    _assert_mode(
        FailureMode.OCCURRENCE_UNMAPPED,
        reconciliations=[],
        dispositions=[],
    )


def test_occurrence_cannot_map_to_two_semantic_findings() -> None:
    _assert_mode(
        FailureMode.OCCURRENCE_MULTIPLY_MAPPED,
        reconciliations=[
            _rec(reconciliation_id="rec-1", semantic_finding_id="sf-1"),
            _rec(reconciliation_id="rec-2", semantic_finding_id="sf-2"),
        ],
        dispositions=[_disp("sf-1"), _disp("sf-2", disposition_id="disp-2")],
    )


def test_every_semantic_finding_requires_disposition() -> None:
    _assert_mode(FailureMode.DISPOSITION_INCOMPLETE, dispositions=[])


def test_resolved_closure_requires_reason_and_evidence() -> None:
    _assert_mode(
        FailureMode.CLOSURE_UNSUPPORTED,
        dispositions=[_disp(family=DispositionFamily.RESOLVED.value)],
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
    assert result["gate_projection"]["custody_valid"] is True
    assert result["gate_projection"]["no_additional_findings"] is True
    assert result["gate_projection"]["no_known_findings"] is True
