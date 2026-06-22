from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan._core import read_json
from arnold.pipelines.megaplan.orchestration.evidence_contract import (
    EvidenceRef,
    EvidenceStatus,
    TransitionDecision,
    TrustClass,
)
from arnold.pipelines.megaplan.orchestration.transition_policy import (
    TRANSITION_DECISION_REVIEW_DONE_FILENAME,
    TransitionPolicy,
    TransitionWriter,
)
from arnold.pipelines.megaplan.planning.state import STATE_DONE


def _evidence(status: str, *, required: bool = False, trust_class: str = "evidence") -> dict:
    return {
        "kind": "green_suite",
        "status": status,
        "summary": status,
        "details": {"required": required},
        "trust_class": trust_class,
    }


def test_review_done_policy_allows_unknown_missing_non_required_and_provider_error_evidence() -> None:
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={"review_verdict": "approved", "review_completion_status": "complete"},
        review_evidence={
            "evidence": [
                _evidence(EvidenceStatus.unknown.value, required=True),
                _evidence(EvidenceStatus.unsatisfied.value, required=False),
            ],
            "provider_diagnostics": {"green_suite": {"ok": False, "error": "runner unavailable"}},
        },
    )

    assert decision.allowed is True
    assert decision.reasons == ()
    assert "provider-error evidence is advisory: green_suite" in decision.advisory

    missing = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={"review_verdict": "approved", "review_completion_status": "complete"},
        review_evidence=None,
    )
    assert missing.allowed is True
    assert "missing review evidence is advisory" in missing.advisory


def test_review_done_policy_allows_unknown_provider_and_non_required_unsatisfied_evidence() -> None:
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={"review_verdict": "approved", "review_completion_status": "complete"},
        review_evidence={
            "evidence": [
                _evidence("unknown-provider-status", required=True),
                _evidence(EvidenceStatus.unsatisfied.value, required=False),
            ],
        },
    )

    assert decision.allowed is True
    assert decision.reasons == ()


def test_review_done_policy_denies_fresh_required_canonical_unsatisfied_evidence() -> None:
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={"review_verdict": "approved", "review_completion_status": "complete"},
        review_evidence={"evidence": [_evidence(EvidenceStatus.unsatisfied.value, required=True)]},
    )

    assert decision.allowed is False
    assert decision.reasons == ("fresh required evidence unsatisfied: green_suite",)


def test_review_done_policy_denies_no_inspection_and_incomplete_approvals() -> None:
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "incomplete",
            "repository_inspected": False,
        },
        review_evidence={"evidence": []},
    )

    assert decision.allowed is False
    assert "review approval is incomplete" in decision.reasons
    assert "review approval did not inspect the repository" in decision.reasons


def test_review_done_policy_denies_blocking_and_routing_authority_contradictions() -> None:
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
            "blocking_rework_items": [{"issue": "still broken", "status": "blocking"}],
            "routing_authority_status": "unsatisfied",
        },
        review_evidence={"evidence": []},
    )

    assert decision.allowed is False
    assert "approved review still contains blocking rework" in decision.reasons
    assert "routing authority contradiction: routing_authority_status=unsatisfied" in decision.reasons


def test_review_done_policy_denies_unsupported_blockers() -> None:
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
            "unsupported_blockers": [{"issue": "provider cannot inspect required artifact"}],
        },
        review_evidence={"evidence": []},
    )

    assert decision.allowed is False
    assert "approved review still contains unsupported blockers" in decision.reasons


def test_review_done_policy_allows_fresh_evidence_over_stale_audit_finalize_contradictions() -> None:
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
            "execution_audit_status": "unsatisfied",
            "finalize_status": "blocked",
            "executor_notes": "old prose says not done",
        },
        review_evidence={"evidence": [_evidence(EvidenceStatus.satisfied.value, required=True)]},
    )

    assert decision.allowed is True
    assert decision.reasons == ()


def test_review_done_policy_treats_stale_and_prose_evidence_as_advisory(tmp_path: Path) -> None:
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={"review_verdict": "approved", "review_completion_status": "complete"},
        review_evidence={
            "head_sha": "old-sha",
            "evidence": [
                _evidence(
                    EvidenceStatus.unsatisfied.value,
                    required=True,
                    trust_class=TrustClass.judgment.value,
                )
            ],
        },
        project_dir=tmp_path,
    )

    assert decision.allowed is True
    assert decision.reasons == ()
    assert "could not prove review evidence freshness; treating evidence as advisory" in decision.advisory


def test_transition_writer_persists_review_done_decision_with_compact_provenance(tmp_path: Path) -> None:
    decision = TransitionDecision(
        decision_id="review-done-1",
        subject="plan:demo",
        from_state="review",
        to_state=STATE_DONE,
        action="allow_transition",
        status="allowed",
        evidence=(
            EvidenceRef(
                kind="green_suite",
                status=EvidenceStatus.satisfied,
                summary="suite passed",
                details={"required": True},
            ),
        ),
        would_block_reasons=("missing inspection",),
        invocation_id="inv-1",
        phase="review",
        iteration=4,
        base_sha="base",
        head_sha="head",
        code_hash="hash",
        routing_provider="transition_policy",
        routing_provenance={"source": "policy"},
    )

    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=False,
        next_action="mark_done",
        denial_kind="policy_denied",
        operator_summary="Fresh evidence passed; safe to proceed.",
        fresh_evidence_path="review_evidence.json",
    )

    assert output_path == tmp_path / TRANSITION_DECISION_REVIEW_DONE_FILENAME
    payload = read_json(output_path)
    assert payload["status"] == "allowed"
    assert payload["action"] == "allow_transition"
    assert payload["from_state"] == "review"
    assert payload["to_state"] == STATE_DONE
    assert payload["would_block_reasons"] == ["missing inspection"]
    assert payload["routing_provenance"]["retryable"] is False
    assert payload["routing_provenance"]["next_action"] == "mark_done"
    assert payload["routing_provenance"]["denial_kind"] == "policy_denied"
    assert payload["routing_provenance"]["operator_summary"] == "Fresh evidence passed; safe to proceed."
    assert payload["routing_provenance"]["fresh_evidence_path"] == "review_evidence.json"
    assert payload["routing_provenance"]["evidence_refs_compact"] == [
        {
            "kind": "green_suite",
            "status": "satisfied",
            "summary": "suite passed",
            "artifact_path": None,
        }
    ]

    restored = TransitionDecision.from_dict(payload)
    assert restored.routing_provenance["retryable"] is False
    assert restored.routing_provenance["next_action"] == "mark_done"
    assert restored.routing_provenance["denial_kind"] == "policy_denied"
    assert restored.routing_provenance["operator_summary"] == "Fresh evidence passed; safe to proceed."
    assert restored.routing_provenance["fresh_evidence_path"] == "review_evidence.json"
    assert restored.routing_provenance["evidence_refs_compact"] == [
        {
            "kind": "green_suite",
            "status": "satisfied",
            "summary": "suite passed",
            "artifact_path": None,
        }
    ]
