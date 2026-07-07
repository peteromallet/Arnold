"""S2/S3 boundary contract registry.

Defines immutable ``BoundaryContract`` instances for the S2 front-half
workflow boundaries (prep→plan, plan→critique, critique→gate,
gate→revise, revise→critique) and the S3 tiebreaker/replan boundaries
(researcher→challenger, challenger→synthesis, synthesis→decision,
decision→parent, replan authority, parent rejoin promotion).
Each contract references a stable row ID from
``arnold.workflow.semantic_evidence`` and a ``BoundaryPhase`` value
from ``arnold.workflow.boundary_evidence``.

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
)

BOUNDARY_CONTRACTS_BY_ID: dict[str, BoundaryContract] = {
    c.boundary_id: c for c in BOUNDARY_CONTRACTS
}

# Ensure the registry has exactly nineteen entries with no duplicates.
assert len(BOUNDARY_CONTRACTS) == 19, (
    f"BOUNDARY_CONTRACTS must have exactly 19 entries, got {len(BOUNDARY_CONTRACTS)}"
)
assert len(BOUNDARY_CONTRACTS_BY_ID) == 19, (
    "BOUNDARY_CONTRACTS_BY_ID must have exactly 19 entries "
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
    "gate_to_revise",
    "parent_rejoin_promotion",
    "plan_to_critique",
    "prep_to_plan",
    "replan_authority",
    "researcher_to_challenger",
    "revise_to_critique",
    "synthesis_to_decision",
]
