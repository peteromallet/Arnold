"""Tests for transition_policy.py — review-to-done boundary, evidence refs, and authority visibility."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.workflow.boundary_evidence import (
    AuthorityState,
    classify_authority_state,
    compile_authority_view,
)
from arnold.pipeline.types import EvidenceStatus, TrustClass
from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    EvidenceRef,
    TransitionDecision,
)
from arnold_pipelines.megaplan.orchestration.transition_policy import (
    TRANSITION_DECISION_REVIEW_DONE_FILENAME,
    TransitionPolicy,
    TransitionPolicyDecision,
    TransitionWriter,
)
from arnold_pipelines.megaplan.planning.state import STATE_DONE


# ── helpers ─────────────────────────────────────────────────────────────


def _evidence(
    status: str,
    *,
    required: bool = False,
    trust_class: str = "evidence",
    kind: str = "green_suite",
) -> dict:
    return {
        "kind": kind,
        "status": status,
        "summary": status,
        "details": {"required": required},
        "trust_class": trust_class,
    }


def _make_decision(**overrides: object) -> TransitionDecision:
    kwargs: dict[str, object] = {
        "decision_id": "review-done-1",
        "subject": "plan:demo",
        "from_state": "review",
        "to_state": STATE_DONE,
        "action": "allow_transition",
        "status": "allowed",
        "evidence": (
            EvidenceRef(
                kind="green_suite",
                status=EvidenceStatus.satisfied,
                summary="suite passed",
                details={"required": True},
            ),
        ),
        "would_block_reasons": (),
        "invocation_id": "inv-1",
        "phase": "review",
        "iteration": 4,
        "base_sha": "base",
        "head_sha": "head",
        "code_hash": "hash",
        "routing_provider": "transition_policy",
        "routing_provenance": {"source": "policy"},
    }
    kwargs.update(overrides)
    return TransitionDecision(**kwargs)


# ── boundary id and evidence ref persistence ─────────────────────────────


def test_review_done_decision_persists_boundary_id(tmp_path: Path) -> None:
    """A persisted review-to-done decision includes boundary_id in routing_provenance."""
    decision = _make_decision(boundary_id="megaplan.review_done")
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=False,
        next_action="mark_done",
    )
    assert output_path == tmp_path / TRANSITION_DECISION_REVIEW_DONE_FILENAME
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["routing_provenance"]["boundary_id"] == "megaplan.review_done"


def test_review_done_decision_persists_checked_evidence_refs(tmp_path: Path) -> None:
    """A persisted decision includes checked_evidence_refs in routing_provenance."""
    decision = _make_decision(
        boundary_id="megaplan.review_done",
        checked_evidence_refs=("evidence:green_suite", "evidence:unit_tests"),
    )
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=False,
        next_action="mark_done",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["routing_provenance"]["checked_evidence_refs"] == [
        "evidence:green_suite",
        "evidence:unit_tests",
    ]


def test_review_done_decision_persists_authority_record_refs(tmp_path: Path) -> None:
    """A persisted decision includes authority_record_refs in routing_provenance."""
    decision = _make_decision(
        boundary_id="megaplan.review_done",
        authority_record_refs=("authority:execute:T1", "authority:execute:T2"),
    )
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=False,
        next_action="mark_done",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["routing_provenance"]["authority_record_refs"] == [
        "authority:execute:T1",
        "authority:execute:T2",
    ]


def test_review_done_decision_roundtrip_with_all_boundary_fields(tmp_path: Path) -> None:
    """Round-trip a TransitionDecision with all S2 boundary fields through write + read."""
    decision = _make_decision(
        boundary_id="megaplan.review_done",
        checked_evidence_refs=("evidence:green_suite",),
        authority_record_refs=("authority:execute:T1",),
    )
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=False,
        next_action="mark_done",
        authority_state=AuthorityState.IRREVERSIBLE,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    restored = TransitionDecision.from_dict(payload)

    assert restored.boundary_id == "megaplan.review_done"
    assert restored.checked_evidence_refs == ("evidence:green_suite",)
    assert restored.authority_record_refs == ("authority:execute:T1",)
    assert restored.routing_provenance["boundary_id"] == "megaplan.review_done"
    assert restored.routing_provenance["authority_state"] == "irreversible"
    assert "authority_view" in restored.routing_provenance


def test_review_done_legacy_decision_deserializes_without_boundary_fields() -> None:
    """A legacy decision without boundary_id/checked_evidence_refs/authority_record_refs
    deserializes with empty defaults."""
    legacy_payload = {
        "schema": "megaplan.transition_decision",
        "schema_version": 1,
        "evidence_contract_version": 1,
        "decision_id": "old-decision",
        "subject": "plan:legacy",
        "from_state": "review",
        "to_state": STATE_DONE,
        "action": "allow_transition",
        "status": "allowed",
        "evidence": [],
        "would_block_reasons": [],
        "invocation_id": "inv-legacy",
        "phase": "review",
        "iteration": 1,
        "base_sha": None,
        "head_sha": None,
        "code_hash": None,
        "routing_provider": "transition_policy",
        "routing_provenance": {},
    }
    decision = TransitionDecision.from_dict(legacy_payload)
    assert decision.boundary_id is None
    assert decision.checked_evidence_refs == ()
    assert decision.authority_record_refs == ()


def test_review_done_decision_omits_empty_boundary_fields_from_payload() -> None:
    """When boundary fields are empty/None, they are omitted from the serialized payload."""
    decision = _make_decision()  # no boundary fields set
    payload = decision.to_dict()
    assert "boundary_id" not in payload
    assert "checked_evidence_refs" not in payload
    assert "authority_record_refs" not in payload


# ── stale evidence policy ────────────────────────────────────────────────


def test_stale_evidence_is_advisory_not_denial(tmp_path: Path) -> None:
    """Stale evidence (head_sha mismatch) is advisory, never a hard denial."""
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
        },
        review_evidence={
            "head_sha": "old-sha",
            "evidence": [
                _evidence(
                    EvidenceStatus.unsatisfied.value,
                    required=True,
                )
            ],
        },
        project_dir=tmp_path,
    )

    # Stale evidence makes the unsatisfied evidence advisory, not denial
    assert decision.allowed is True
    assert decision.reasons == ()
    assert "could not prove review evidence freshness; treating evidence as advisory" in decision.advisory


def test_fresh_required_unsatisfied_evidence_is_denial() -> None:
    """Fresh, required, non-advisory-trust-class evidence that is unsatisfied causes denial."""
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
        },
        review_evidence={
            "evidence": [
                _evidence(
                    EvidenceStatus.unsatisfied.value,
                    required=True,
                    trust_class=TrustClass.evidence.value,
                )
            ],
        },
    )

    assert decision.allowed is False
    assert any(
        "fresh required evidence unsatisfied" in reason
        for reason in decision.reasons
    )


def test_stale_required_unsatisfied_evidence_with_judgment_trust_is_advisory(
    tmp_path: Path,
) -> None:
    """When evidence is stale AND has judgment trust class, it's advisory (double-protection)."""
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
        },
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


def test_provider_error_evidence_is_advisory() -> None:
    """Provider-error evidence is always advisory, never a denial."""
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
        },
        review_evidence={
            "evidence": [],
            "provider_diagnostics": {
                "green_suite": {"ok": False, "error": "runner unavailable"},
            },
        },
    )

    assert decision.allowed is True
    assert "provider-error evidence is advisory: green_suite" in decision.advisory


def test_missing_evidence_is_advisory() -> None:
    """Completely missing review evidence is advisory, not denial."""
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
        },
        review_evidence=None,
    )

    assert decision.allowed is True
    assert "missing review evidence is advisory" in decision.advisory


# ── authority state classification ──────────────────────────────────────


def test_classify_authority_state_missing_when_no_refs() -> None:
    """When no authority or evidence refs exist, state is MISSING."""
    state = classify_authority_state(
        allowed=True,
        authority_record_refs=(),
        checked_evidence_refs=(),
    )
    assert state is AuthorityState.MISSING


def test_classify_authority_state_denied_when_not_allowed() -> None:
    """When the transition is denied, state is DENIED regardless of refs."""
    state = classify_authority_state(
        allowed=False,
        authority_record_refs=("authority:execute:T1",),
        checked_evidence_refs=("evidence:suite",),
    )
    assert state is AuthorityState.DENIED


def test_classify_authority_state_waived_when_waiver() -> None:
    """When a waiver is present, state is WAIVED."""
    state = classify_authority_state(
        allowed=True,
        authority_record_refs=("authority:execute:T1",),
        checked_evidence_refs=(),
        has_waiver=True,
    )
    assert state is AuthorityState.WAIVED


def test_classify_authority_state_stale_when_advisory_mentions_stale() -> None:
    """When advisory contains 'stale', state is STALE."""
    state = classify_authority_state(
        allowed=True,
        authority_record_refs=("authority:execute:T1",),
        checked_evidence_refs=("evidence:suite",),
        advisory=("stale review evidence is advisory",),
    )
    assert state is AuthorityState.STALE


def test_classify_authority_state_degraded_when_provider_errors() -> None:
    """When provider errors exist, state is DEGRADED."""
    state = classify_authority_state(
        allowed=True,
        authority_record_refs=("authority:execute:T1",),
        checked_evidence_refs=("evidence:suite",),
        provider_errors=True,
    )
    assert state is AuthorityState.DEGRADED


def test_classify_authority_state_partial_when_authority_without_evidence() -> None:
    """Authority refs without checked evidence refs → PARTIAL."""
    state = classify_authority_state(
        allowed=True,
        authority_record_refs=("authority:execute:T1",),
        checked_evidence_refs=(),
    )
    assert state is AuthorityState.PARTIAL


def test_classify_authority_state_irreversible_when_complete() -> None:
    """Complete fresh evidence with authority refs → IRREVERSIBLE."""
    state = classify_authority_state(
        allowed=True,
        authority_record_refs=("authority:execute:T1",),
        checked_evidence_refs=("evidence:suite",),
    )
    assert state is AuthorityState.IRREVERSIBLE


def test_classify_authority_state_denied_has_highest_priority() -> None:
    """DENIED takes priority over all other signals."""
    state = classify_authority_state(
        allowed=False,
        authority_record_refs=("authority:execute:T1",),
        checked_evidence_refs=("evidence:suite",),
        has_waiver=True,
        provider_errors=True,
        advisory=("stale review evidence is advisory",),
    )
    assert state is AuthorityState.DENIED


def test_classify_authority_state_missing_priority_over_waived() -> None:
    """MISSING (no refs at all) takes priority over WAIVED even when waiver flag set."""
    state = classify_authority_state(
        allowed=True,
        authority_record_refs=(),
        checked_evidence_refs=(),
        has_waiver=True,
    )
    assert state is AuthorityState.MISSING


# ── authority view compilation ───────────────────────────────────────────


def test_compile_authority_view_missing_state(tmp_path: Path) -> None:
    """Authority view for missing state includes correct metadata."""
    view = compile_authority_view(
        boundary_id="megaplan.review_done",
        authority_state=AuthorityState.MISSING,
        authority_record_refs=(),
        checked_evidence_refs=(),
        status="allowed",
    )
    assert view["authority_state"] == "missing"
    assert view["boundary_id"] == "megaplan.review_done"
    assert view["status"] == "allowed"
    # Empty refs omitted from compact view
    assert "authority_record_refs" not in view
    assert "checked_evidence_refs" not in view


def test_compile_authority_view_irreversible_state() -> None:
    """Authority view for irreversible includes full counts."""
    view = compile_authority_view(
        boundary_id="megaplan.review_done",
        authority_state=AuthorityState.IRREVERSIBLE,
        authority_record_refs=("authority:execute:T1", "authority:execute:T2"),
        checked_evidence_refs=("evidence:suite",),
        status="allowed",
        would_block_reasons=(),
        operator_summary="Safe to proceed.",
    )
    assert view["authority_state"] == "irreversible"
    assert view["authority_record_refs"] == ["authority:execute:T1", "authority:execute:T2"]
    assert view["checked_evidence_refs"] == ["evidence:suite"]
    assert view["status"] == "allowed"
    assert view["operator_summary"] == "Safe to proceed."


def test_compile_authority_view_denied_state() -> None:
    """Authority view for denied includes denial reasons."""
    view = compile_authority_view(
        boundary_id="megaplan.review_done",
        authority_state=AuthorityState.DENIED,
        authority_record_refs=(),
        checked_evidence_refs=(),
        status="denied",
        would_block_reasons=("fresh required evidence unsatisfied: green_suite",),
        operator_summary="Transition denied by policy.",
    )
    assert view["authority_state"] == "denied"
    assert view["status"] == "denied"
    assert len(view["would_block_reasons"]) == 1


def test_authority_view_persisted_in_routing_provenance(tmp_path: Path) -> None:
    """The authority_view is embedded in routing_provenance when writing a decision."""
    decision = _make_decision(
        boundary_id="megaplan.review_done",
        checked_evidence_refs=("evidence:green_suite",),
        authority_record_refs=("authority:execute:T1",),
    )
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=False,
        next_action="mark_done",
        authority_state=AuthorityState.IRREVERSIBLE,
        operator_summary="All evidence fresh.",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    view = payload["routing_provenance"]["authority_view"]
    assert view["authority_state"] == "irreversible"
    assert view["authority_record_refs"] == ["authority:execute:T1"]
    assert view["checked_evidence_refs"] == ["evidence:green_suite"]
    assert view["boundary_id"] == "megaplan.review_done"


def test_authority_view_for_denied_decision(tmp_path: Path) -> None:
    """A denied decision still includes authority_view in provenance."""
    decision = _make_decision(
        status="denied",
        action="deny_transition",
        would_block_reasons=("missing inspection",),
        boundary_id="megaplan.review_done",
        checked_evidence_refs=(),
        authority_record_refs=(),
    )
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=True,
        next_action="review",
        denial_kind="policy_denied",
        operator_summary="Review-to-done transition denied by policy.",
        authority_state=AuthorityState.DENIED,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    view = payload["routing_provenance"]["authority_view"]
    assert view["authority_state"] == "denied"
    assert view["status"] == "denied"
    assert view["boundary_id"] == "megaplan.review_done"


# ── transition policy decision merge ─────────────────────────────────────


def test_merge_denial_reasons_appends_and_denies() -> None:
    """merge_denial_reasons forces allowed=False and appends reasons."""
    original = TransitionPolicyDecision(
        allowed=True,
        reasons=(),
        advisory=("note",),
    )
    merged = original.merge_denial_reasons(["north_star_blocker_1"])
    assert merged.allowed is False
    assert merged.reasons == ("north_star_blocker_1",)
    assert merged.advisory == ("note",)


def test_merge_denial_reasons_with_empty_returns_unchanged() -> None:
    """merge_denial_reasons with empty/no reasons returns unchanged decision."""
    original = TransitionPolicyDecision(allowed=True, reasons=(), advisory=())
    merged = original.merge_denial_reasons([])
    assert merged is original  # same object when no new reasons


def test_merge_denial_reasons_appends_to_existing() -> None:
    """merge_denial_reasons appends to existing denial reasons."""
    original = TransitionPolicyDecision(
        allowed=False,
        reasons=("existing_reason",),
        advisory=(),
    )
    merged = original.merge_denial_reasons(["new_reason"])
    assert merged.allowed is False
    assert merged.reasons == ("existing_reason", "new_reason")


def test_merge_denial_reasons_strips_whitespace() -> None:
    """Whitespace-only reasons are filtered out."""
    original = TransitionPolicyDecision(allowed=True, reasons=(), advisory=())
    merged = original.merge_denial_reasons(["  ", "\t", "valid_reason"])
    assert merged.allowed is False
    assert merged.reasons == ("valid_reason",)


# ── transition writer with authority_state ───────────────────────────────


def test_writer_injects_authority_state_string(tmp_path: Path) -> None:
    """TransitionWriter accepts a plain string for authority_state."""
    decision = _make_decision(boundary_id="megaplan.review_done")
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=False,
        next_action="mark_done",
        authority_state="waived",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["routing_provenance"]["authority_state"] == "waived"


def test_writer_defaults_authority_state_to_missing(tmp_path: Path) -> None:
    """When no authority_state supplied, authority_view defaults to MISSING."""
    decision = _make_decision()
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=False,
        next_action="mark_done",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    view = payload["routing_provenance"]["authority_view"]
    assert view["authority_state"] == "missing"


def test_writer_persists_denial_kind(tmp_path: Path) -> None:
    """When denied, denial_kind is persisted in routing_provenance."""
    decision = _make_decision(status="denied", action="deny_transition")
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=True,
        next_action="review",
        denial_kind="policy_denied",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["routing_provenance"]["denial_kind"] == "policy_denied"
    assert payload["routing_provenance"]["retryable"] is True


def test_writer_compact_evidence_refs(tmp_path: Path) -> None:
    """Compact evidence refs are persisted correctly."""
    decision = _make_decision(
        evidence=(
            EvidenceRef(
                kind="green_suite",
                status=EvidenceStatus.satisfied,
                summary="suite passed",
                details={"required": True},
            ),
            EvidenceRef(
                kind="unit_tests",
                status=EvidenceStatus.unsatisfied,
                summary="tests failed",
                details={},
            ),
        ),
    )
    output_path = TransitionWriter.write_review_done(
        tmp_path,
        decision,
        retryable=False,
        next_action="mark_done",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    compact = payload["routing_provenance"]["evidence_refs_compact"]
    assert len(compact) == 2
    assert compact[0]["kind"] == "green_suite"
    assert compact[0]["status"] == "satisfied"
    assert compact[1]["kind"] == "unit_tests"
    assert compact[1]["status"] == "unsatisfied"


# ── transition policy edge cases ─────────────────────────────────────────


def test_not_review_to_done_route_is_allowed_with_advisory() -> None:
    """Transitions that aren't success→done are allowed with advisory note."""
    decision = TransitionPolicy.evaluate_review_done(
        result="failure",
        next_state=STATE_DONE,
    )
    assert decision.allowed is True
    assert "not a normal success-to-done review route" in decision.advisory


def test_review_with_non_approved_verdict_is_denied() -> None:
    """A review verdict that isn't 'approved' causes denial."""
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "rejected",
            "review_completion_status": "complete",
        },
        review_evidence={"evidence": []},
    )
    assert decision.allowed is False
    assert any("review verdict is not approved" in r for r in decision.reasons)


def test_blocking_rework_with_deterministic_check_is_denied() -> None:
    """Blocking rework items with deterministic_check flag cause denial."""
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
            "blocking_rework_items": [
                {"issue": "broken", "deterministic_check": True}
            ],
        },
        review_evidence={"evidence": []},
    )
    assert decision.allowed is False
    assert "approved review still contains blocking rework" in decision.reasons


def test_routing_authority_status_unsatisfied_is_denied() -> None:
    """routing_authority_status=unsatisfied causes denial."""
    decision = TransitionPolicy.evaluate_review_done(
        result="success",
        next_state=STATE_DONE,
        review_payload={
            "review_verdict": "approved",
            "review_completion_status": "complete",
            "routing_authority_status": "unsatisfied",
        },
        review_evidence={"evidence": []},
    )
    assert decision.allowed is False
    assert any(
        "routing authority contradiction: routing_authority_status=unsatisfied" in r
        for r in decision.reasons
    )
