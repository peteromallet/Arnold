"""S2/S3/S4/S5 boundary contract registry.

Defines immutable ``BoundaryContract`` instances for the S2 front-half
workflow boundaries (prep→plan, plan→critique, critique→gate,
gate→revise, revise→critique) and the S3 tiebreaker/replan boundaries
(researcher→challenger, challenger→synthesis, synthesis→decision,
decision→parent, replan authority, parent rejoin promotion), the S4
execute boundaries, and the S5 review/finalize evidence boundaries.
Each contract references a stable row ID from
``arnold.workflow.semantic_evidence`` and, where the shared enum already
covers the carrier, a ``BoundaryPhase`` value from
``arnold.workflow.boundary_evidence``.

This registry is intentionally declarative: it does not declare route
targets, compute routing predicates, or mutate state.  It is the single
source of truth for downstream checker, receipt-emission, and
semantic-health work.
"""

from __future__ import annotations

from arnold.workflow.boundary_evidence import BoundaryContract, BoundaryPhase
from arnold.workflow.semantic_evidence import (
    S2_CRITIQUE_ROW_ID,
    S2_GATE_ROW_ID,
    S2_PLAN_ROW_ID,
    S2_PREP_ROW_ID,
    S2_REVISE_ROW_ID,
    S3_PARENT_REJOIN_ROW_ID,
    S3_REPLAN_AUTHORITY_ROW_ID,
    S3_TIEBREAKER_CHALLENGER_ROW_ID,
    S3_TIEBREAKER_DECISION_ROW_ID,
    S3_TIEBREAKER_RESEARCHER_ROW_ID,
    S3_TIEBREAKER_SYNTHESIS_ROW_ID,
    S4_EXECUTE_ROW_ID,
)

# ── S5 review/finalize stable row ID namespace ─────────────────────────────
# These rows remain local to the registry until the downstream checker adds
# first-class S5 row matching. The IDs are still stable so receipts and
# diagnostics can reference them now.

S5_REVIEW_CHILD_OUTPUTS_ROW_ID = "s5.review_child_outputs.1"
S5_REVIEW_REDUCER_PROMOTION_ROW_ID = "s5.review_reducer_promotion.1"
S5_REVIEW_REWORK_EFFECTS_ROW_ID = "s5.review_rework_effects.1"
S5_REVIEW_CAP_AUTHORITY_ROW_ID = "s5.review_cap_authority.1"
S5_REVIEW_HUMAN_VERIFICATION_ROW_ID = "s5.review_human_verification.1"
S5_FINALIZE_ARTIFACTS_ROW_ID = "s5.finalize_artifacts.1"
S5_FINALIZE_FALLBACK_ROW_ID = "s5.finalize_fallback.1"
S5_FINAL_PROJECTION_ROW_ID = "s5.final_projection.1"

# ── S2 Front-half boundary contracts ───────────────────────────────────────

prep_to_plan = BoundaryContract(
    boundary_id="prep_to_plan",
    workflow_id="megaplan-review",
    row_id=S2_PREP_ROW_ID,
    phase=BoundaryPhase.PREP,
    required_artifacts=("research.md", "brief.md"),
    expected_state_delta={"current_phase": "prep"},
    expected_history_entry="prep_completed",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={"description": "Prep → Plan boundary: research and brief complete"},
)

plan_to_critique = BoundaryContract(
    boundary_id="plan_to_critique",
    workflow_id="megaplan-review",
    row_id=S2_PLAN_ROW_ID,
    phase=BoundaryPhase.PLAN,
    required_artifacts=("plan.md",),
    expected_state_delta={"current_phase": "plan"},
    expected_history_entry="plan_completed",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={"description": "Plan → Critique boundary: plan artifact produced"},
)

critique_to_gate = BoundaryContract(
    boundary_id="critique_to_gate",
    workflow_id="megaplan-review",
    row_id=S2_CRITIQUE_ROW_ID,
    phase=BoundaryPhase.CRITIQUE,
    required_artifacts=("critique.md", "scores.json"),
    expected_state_delta={"current_phase": "critique"},
    expected_history_entry="critique_completed",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={"description": "Critique → Gate boundary: critique and scores complete"},
)

gate_to_revise = BoundaryContract(
    boundary_id="gate_to_revise",
    workflow_id="megaplan-review",
    row_id=S2_GATE_ROW_ID,
    phase=BoundaryPhase.GATE,
    required_artifacts=("gate_decision.json", "phase_result.json"),
    expected_state_delta={"current_phase": "gate"},
    expected_history_entry="gate_iterate",
    phase_result_required=True,
    receipt_required=True,
    authority_required=True,
    details={
        "description": (
            "Gate → Revise boundary: gate decision requires revision; "
            "only emitted for iterate/retry/revise outcomes"
        ),
    },
)

revise_to_critique = BoundaryContract(
    boundary_id="revise_to_critique",
    workflow_id="megaplan-review",
    row_id=S2_REVISE_ROW_ID,
    phase=BoundaryPhase.REVISE,
    required_artifacts=("revised_plan.md", "revision_log.md"),
    expected_state_delta={"current_phase": "revise"},
    expected_history_entry="revise_completed",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={"description": "Revise → Critique boundary: revision complete, loop back"},
)

# ── S3 tiebreaker/replan boundary contracts ────────────────────────────────

researcher_to_challenger = BoundaryContract(
    boundary_id="tiebreaker_researcher_to_challenger",
    workflow_id="megaplan-review",
    row_id=S3_TIEBREAKER_RESEARCHER_ROW_ID,
    phase=BoundaryPhase.TIEBREAKER_RESEARCHER,
    required_artifacts=("research_findings.json",),
    expected_state_delta={"current_phase": "tiebreaker_researcher"},
    expected_history_entry="tiebreaker_researcher_completed",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "Tiebreaker Researcher → Challenger boundary: research findings produced",
        "child_trace_path": "tiebreaker/researcher",
    },
)

challenger_to_synthesis = BoundaryContract(
    boundary_id="tiebreaker_challenger_to_synthesis",
    workflow_id="megaplan-review",
    row_id=S3_TIEBREAKER_CHALLENGER_ROW_ID,
    phase=BoundaryPhase.TIEBREAKER_CHALLENGER,
    required_artifacts=("challenge_findings.json",),
    expected_state_delta={"current_phase": "tiebreaker_challenger"},
    expected_history_entry="tiebreaker_challenger_completed",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "Tiebreaker Challenger → Synthesis boundary: challenge findings produced",
        "child_trace_path": "tiebreaker/challenger",
    },
)

synthesis_to_decision = BoundaryContract(
    boundary_id="tiebreaker_synthesis_to_decision",
    workflow_id="megaplan-review",
    row_id=S3_TIEBREAKER_SYNTHESIS_ROW_ID,
    phase=BoundaryPhase.TIEBREAKER_SYNTHESIS,
    required_artifacts=("tiebreaker_payload.json",),
    expected_state_delta={"current_phase": "tiebreaker_synthesis"},
    expected_history_entry="tiebreaker_synthesis_completed",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "Tiebreaker Synthesis → Decision boundary: reducer payload produced",
        "child_trace_path": "tiebreaker/synthesis",
        "reducer_promotion": True,
    },
)

decision_to_parent = BoundaryContract(
    boundary_id="tiebreaker_decision_to_parent",
    workflow_id="megaplan-review",
    row_id=S3_TIEBREAKER_DECISION_ROW_ID,
    phase=BoundaryPhase.TIEBREAKER_DECISION,
    required_artifacts=("tiebreaker_decisions.json",),
    expected_state_delta={"current_phase": "tiebreaker_decision"},
    expected_history_entry="tiebreaker_decision_produced",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "Tiebreaker Decision → Parent Rejoin boundary: decision emitted, parent resumes",
        "child_trace_path": "tiebreaker/decision",
        "parent_rejoin_promotion": True,
        "decision_outcomes": ("proceed", "iterate", "escalate"),
    },
)

replan_authority = BoundaryContract(
    boundary_id="replan_authority",
    workflow_id="megaplan-review",
    row_id=S3_REPLAN_AUTHORITY_ROW_ID,
    phase=BoundaryPhase.REPLAN_AUTHORITY,
    required_artifacts=("replan_decision.json",),
    expected_state_delta={"replan_triggered": True},
    expected_history_entry="replan_authorized",
    phase_result_required=True,
    receipt_required=False,
    authority_required=True,
    details={
        "description": "Replan Authority boundary: replan decision authorized with evidence",
    },
)

parent_rejoin_promotion = BoundaryContract(
    boundary_id="parent_rejoin_promotion",
    workflow_id="megaplan-review",
    row_id=S3_PARENT_REJOIN_ROW_ID,
    phase=BoundaryPhase.PARENT_REJOIN,
    required_artifacts=(),
    expected_state_delta={"parent_rejoined": True},
    expected_history_entry="parent_rejoin_completed",
    phase_result_required=False,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "Parent Rejoin Promotion boundary: parent workflow resumes after tiebreaker decision",
    },
)

# ── S4 execute boundary contracts ──────────────────────────────────────────

execute_approval = BoundaryContract(
    boundary_id="execute_approval",
    workflow_id="megaplan-review",
    row_id=S4_EXECUTE_ROW_ID,
    phase=BoundaryPhase.EXECUTE,
    required_artifacts=("approval_record.json",),
    expected_state_delta={"current_phase": "execute", "approval_gate": "cleared"},
    expected_history_entry="execute_approval_cleared",
    phase_result_required=True,
    receipt_required=True,
    authority_required=True,
    details={
        "description": (
            "Execute approval gate: destructive confirmation and operator "
            "approval cleared — proceed to batch execution"
        ),
        "approval_scope": "execute:approval-approved",
        "branch_ref": "execute:approval-approved",
    },
)

execute_approval_denial = BoundaryContract(
    boundary_id="execute_approval_denial",
    workflow_id="megaplan-review",
    row_id=S4_EXECUTE_ROW_ID,
    phase=BoundaryPhase.EXECUTE,
    required_artifacts=(),
    expected_state_delta={"current_phase": "execute", "approval_gate": "denied"},
    expected_history_entry="execute_approval_denied",
    phase_result_required=False,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Execute approval denial: destructive confirmation or operator "
            "approval missing — halt before batch execution"
        ),
        "approval_scope": "denied",
        "branch_ref": "execute:approval-denied",
    },
)

execute_batch_checkpoint = BoundaryContract(
    boundary_id="execute_batch_checkpoint",
    workflow_id="megaplan-review",
    row_id=S4_EXECUTE_ROW_ID,
    phase=BoundaryPhase.EXECUTE,
    required_artifacts=("batch_checkpoint.json",),
    expected_state_delta={"current_phase": "execute", "batch_stage": "checkpoint"},
    expected_history_entry="execute_batch_checkpoint",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Execute batch checkpoint: one batch completed successfully; "
            "additional batches remain for continuation"
        ),
        "batch_index": 0,
        "task_ids": (),
        "branch_ref": "execute:batch-continuation",
    },
)

execute_partial_failure = BoundaryContract(
    boundary_id="execute_partial_failure",
    workflow_id="megaplan-review",
    row_id=S4_EXECUTE_ROW_ID,
    phase=BoundaryPhase.EXECUTE,
    required_artifacts=("blocked_batch_report.json",),
    expected_state_delta={"current_phase": "execute", "batch_stage": "partial_failure"},
    expected_history_entry="execute_partial_failure",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Execute partial failure: a batch was blocked by quality gates — "
            "route to override for recovery"
        ),
        "batch_index": 0,
        "task_ids": (),
        "branch_ref": "execute:blocked-recovery",
    },
)

execute_blocked_anchor = BoundaryContract(
    boundary_id="execute_blocked_anchor",
    workflow_id="megaplan-review",
    row_id=S4_EXECUTE_ROW_ID,
    phase=BoundaryPhase.EXECUTE,
    required_artifacts=("retry_decision.json",),
    expected_state_delta={"current_phase": "execute", "retry_stage": "blocked_anchor"},
    expected_history_entry="execute_blocked_anchor",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Execute blocked anchor: worker/transient timeout within retry "
            "budget — retry the batch or escalate to override"
        ),
        "retry_anchor": True,
        "branch_ref": "execute:timeout-retry",
    },
)

execute_resume_anchor = BoundaryContract(
    boundary_id="execute_resume_anchor",
    workflow_id="megaplan-review",
    row_id=S4_EXECUTE_ROW_ID,
    phase=BoundaryPhase.EXECUTE,
    required_artifacts=("fresh_session_request.json",),
    expected_state_delta={"current_phase": "execute", "retry_stage": "resume_anchor"},
    expected_history_entry="execute_resume_anchor",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Execute resume anchor: retry requires a fresh worker session — "
            "force new execute session"
        ),
        "retry_anchor": True,
        "fresh_session": True,
        "branch_ref": "execute:timeout-retry-fresh",
    },
)

execute_aggregate_promotion = BoundaryContract(
    boundary_id="execute_aggregate_promotion",
    workflow_id="megaplan-review",
    row_id=S4_EXECUTE_ROW_ID,
    phase=BoundaryPhase.EXECUTE,
    required_artifacts=("execute_payload.json",),
    expected_state_delta={"current_phase": "execute", "aggregation_stage": "promoted"},
    expected_history_entry="execute_aggregate_promotion",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Execute aggregate promotion: every batch payload aggregated into "
            "a single execute_payload — promoted to review fan-in as items source"
        ),
        "reducer_promotion": True,
        "child_trace_path": "execute/aggregate",
        "branch_ref": "execute:aggregate-promotion",
    },
)

execute_no_review_terminal = BoundaryContract(
    boundary_id="execute_no_review_terminal",
    workflow_id="megaplan-review",
    row_id=S4_EXECUTE_ROW_ID,
    phase=BoundaryPhase.EXECUTE,
    required_artifacts=(),
    expected_state_delta={"current_phase": "execute", "terminal_stage": "no_review"},
    expected_history_entry="execute_no_review_terminal",
    phase_result_required=False,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Execute no-review terminal: robustness skips review (bare or "
            "light without deferred must criteria) — terminate directly or "
            "await human verification"
        ),
        "terminal_outcomes": ("done", "awaiting_human_verify"),
        "branch_ref": "execute:no-review-terminal",
    },
)

# ── S5 review/finalize boundary contracts ──────────────────────────────────

review_child_outputs = BoundaryContract(
    boundary_id="review_child_outputs",
    workflow_id="megaplan-review",
    row_id=S5_REVIEW_CHILD_OUTPUTS_ROW_ID,
    required_artifacts=("review.json",),
    expected_state_delta={"current_phase": "review"},
    expected_history_entry="review_child_outputs_recorded",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Review child outputs boundary: review fanout children produced "
            "durable outputs for the visible review fan-in reducer."
        ),
        "child_trace_template": "review/{item_id}",
        "fan_in_ref": "review-fan-in",
        "evidence_surface_ref": "REVIEW_POLICY.metadata.route_surface.fan_in_contract",
    },
)

review_reducer_promotion = BoundaryContract(
    boundary_id="review_reducer_promotion",
    workflow_id="megaplan-review",
    row_id=S5_REVIEW_REDUCER_PROMOTION_ROW_ID,
    required_artifacts=("review.json",),
    expected_state_delta={"current_phase": "review"},
    expected_history_entry="review_reducer_promoted",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Review reducer promotion boundary: the authored review fan-in "
            "promoted child outputs into the canonical review payload."
        ),
        "reducer_promotion": True,
        "effect_id": "artifact.review.output",
        "artifact_policy_ref": "megaplan:artifact-contract",
        "reducer_ref": "SOURCE_REVIEW",
    },
)

review_rework_effects = BoundaryContract(
    boundary_id="review_rework_effects",
    workflow_id="megaplan-review",
    row_id=S5_REVIEW_REWORK_EFFECTS_ROW_ID,
    required_artifacts=("review.json",),
    expected_state_delta={"current_phase": "review"},
    expected_history_entry="review_rework_projected",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Review rework effects boundary: a review-directed rework cycle "
            "projects durable re-execute intent without privately routing it."
        ),
        "effect_kind": "review_rework_cycle",
        "fresh_execute_session": True,
        "evidence_surface_ref": "REVIEW_POLICY.metadata.route_surface.rework_cycle",
        "projection_state_ref": "finalized",
    },
)

review_cap_authority = BoundaryContract(
    boundary_id="review_cap_authority",
    workflow_id="megaplan-review",
    row_id=S5_REVIEW_CAP_AUTHORITY_ROW_ID,
    required_artifacts=("review.json",),
    expected_state_delta={"current_phase": "review"},
    expected_history_entry="review_cap_authorized",
    phase_result_required=True,
    receipt_required=True,
    authority_required=True,
    details={
        "description": (
            "Review cap authority boundary: cap exhaustion outcomes carry "
            "explicit authority records instead of handler-owned decisions."
        ),
        "authority_scope": "review.cap_exhausted",
        "authority_outcomes": ("blocked", "force_proceeded"),
        "policy_ref": "megaplan:review",
    },
)

review_human_verification = BoundaryContract(
    boundary_id="review_human_verification",
    workflow_id="megaplan-review",
    row_id=S5_REVIEW_HUMAN_VERIFICATION_ROW_ID,
    required_artifacts=("review.json",),
    expected_state_delta={"current_phase": "review"},
    expected_history_entry="review_human_verification_deferred",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Review human verification boundary: deferred-human review "
            "records suspension and resume evidence without becoming a route table."
        ),
        "suspension_route_id": "review:human",
        "resume_policy_ref": "megaplan:suspension",
        "resume_cursor_ref": "cursor:suspension",
        "terminal_state": "awaiting_human_verify",
    },
)

finalize_artifacts = BoundaryContract(
    boundary_id="finalize_artifacts",
    workflow_id="megaplan-review",
    row_id=S5_FINALIZE_ARTIFACTS_ROW_ID,
    required_artifacts=("contract.json", "final.md", "finalize.json"),
    expected_state_delta={"current_phase": "finalize"},
    expected_history_entry="finalize_artifacts_published",
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Finalize artifacts boundary: finalize published the canonical "
            "plan artifacts declared by the artifact contract."
        ),
        "effect_id": "artifact.finalize.plan",
        "artifact_policy_ref": "megaplan:artifact-contract",
        "artifact_refs": ("contract.json", "final.md", "finalize.json"),
    },
)

finalize_fallback = BoundaryContract(
    boundary_id="finalize_fallback",
    workflow_id="megaplan-review",
    row_id=S5_FINALIZE_FALLBACK_ROW_ID,
    required_artifacts=("finalize_revise_feedback.json",),
    expected_state_delta={"current_phase": "finalize"},
    expected_history_entry="finalize_revise_fallback",
    phase_result_required=False,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Finalize fallback boundary: revise fallback evidence is persisted "
            "as a declarative contract rather than a hidden finalize branch."
        ),
        "fallback_reason": "missing_scoped_baseline_test_contract",
        "evidence_surface_ref": (
            "FINALIZE_POLICY.metadata.route_surface.fallback_routes."
            "plan_contract_revise_needed"
        ),
        "projection_ref": "finalize:revise",
    },
)

final_projection = BoundaryContract(
    boundary_id="final_projection",
    workflow_id="megaplan-review",
    row_id=S5_FINAL_PROJECTION_ROW_ID,
    required_artifacts=("finalize.json",),
    expected_state_delta={},
    expected_history_entry="final_projection_recorded",
    phase_result_required=False,
    receipt_required=True,
    authority_required=False,
    details={
        "description": (
            "Final projection boundary: terminal or continuation projection is "
            "visible in finalize policy metadata and durable plan artifacts."
        ),
        "projection_cases": (
            "execute",
            "revise_fallback",
            "no_review_done",
            "no_review_deferred_human",
        ),
        "projected_status_ref": "status:terminal",
        "evidence_surface_ref": "FINALIZE_POLICY.metadata.route_surface.final_projection_routes",
    },
)

# ── Registry ───────────────────────────────────────────────────────────────

BOUNDARY_CONTRACTS: tuple[BoundaryContract, ...] = (
    prep_to_plan,
    plan_to_critique,
    critique_to_gate,
    gate_to_revise,
    revise_to_critique,
    researcher_to_challenger,
    challenger_to_synthesis,
    synthesis_to_decision,
    decision_to_parent,
    replan_authority,
    parent_rejoin_promotion,
    execute_approval,
    execute_approval_denial,
    execute_batch_checkpoint,
    execute_partial_failure,
    execute_blocked_anchor,
    execute_resume_anchor,
    execute_aggregate_promotion,
    execute_no_review_terminal,
    review_child_outputs,
    review_reducer_promotion,
    review_rework_effects,
    review_cap_authority,
    review_human_verification,
    finalize_artifacts,
    finalize_fallback,
    final_projection,
)

BOUNDARY_CONTRACTS_BY_ID: dict[str, BoundaryContract] = {
    c.boundary_id: c for c in BOUNDARY_CONTRACTS
}

# Ensure the registry has exactly twenty-seven entries with no duplicates.
assert len(BOUNDARY_CONTRACTS) == 27, (
    f"BOUNDARY_CONTRACTS must have exactly 27 entries, got {len(BOUNDARY_CONTRACTS)}"
)
assert len(BOUNDARY_CONTRACTS_BY_ID) == 27, (
    "BOUNDARY_CONTRACTS_BY_ID must have exactly 27 entries "
    "(duplicate boundary_id detected)"
)

__all__ = [
    "BOUNDARY_CONTRACTS",
    "BOUNDARY_CONTRACTS_BY_ID",
    "challenger_to_synthesis",
    "critique_to_gate",
    "decision_to_parent",
    "execute_aggregate_promotion",
    "execute_approval",
    "execute_approval_denial",
    "execute_batch_checkpoint",
    "execute_blocked_anchor",
    "execute_no_review_terminal",
    "execute_partial_failure",
    "execute_resume_anchor",
    "final_projection",
    "finalize_artifacts",
    "finalize_fallback",
    "gate_to_revise",
    "parent_rejoin_promotion",
    "plan_to_critique",
    "prep_to_plan",
    "replan_authority",
    "review_cap_authority",
    "review_child_outputs",
    "review_human_verification",
    "review_reducer_promotion",
    "review_rework_effects",
    "researcher_to_challenger",
    "revise_to_critique",
    "synthesis_to_decision",
]
