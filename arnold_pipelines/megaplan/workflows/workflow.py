"""Megaplan's canonical authored workflow source."""

from __future__ import annotations

from arnold.pipeline import parallel_map
from arnold.workflow.authoring import loop, workflow
from arnold_pipelines.megaplan.workflows.components import (
    DEFAULT_POLICY,
    REVISE_LOOP_POLICY,
    SOURCE_CRITIQUE,
    SOURCE_CRITIQUE_PANEL_WORKFLOW,
    SOURCE_EXECUTE,
    SOURCE_EXECUTE_BATCH_WORKFLOW,
    SOURCE_FINALIZE,
    SOURCE_GATE,
    SOURCE_HALT,
    SOURCE_OVERRIDE,
    SOURCE_PLAN,
    SOURCE_PREP,
    SOURCE_REVIEW,
    SOURCE_REVIEW_PANEL_WORKFLOW,
    SOURCE_REVISE,
    SOURCE_TIEBREAKER_WORKFLOW,
)

CRITIQUE_GATE_DIAGNOSTICS = {
    "bare_skip": {
        "owner": "critique-fanout",
        "surface": "SOURCE_CRITIQUE_PANEL_WORKFLOW",
        "effect": "skip_empty_or_bare_findings",
    },
    "evaluator_retry": {
        "owner": "critique-fanout",
        "surface": "SOURCE_CRITIQUE_PANEL_WORKFLOW",
        "effect": "retry_unverifiable_or_unavailable_evaluators",
    },
    "malformed_payload": {
        "owner": "gate",
        "surface": "SOURCE_GATE",
        "effect": "normalize_to_inferred_recommendation",
    },
    "empty_payload": {
        "owner": "gate",
        "surface": "SOURCE_GATE",
        "effect": "normalize_to_inferred_recommendation",
    },
    "worker_unavailable": {
        "owner": "gate",
        "surface": "SOURCE_GATE",
        "effect": "escalate_or_retry_via_preflight_policy",
    },
    "debt_recorded": {
        "owner": "gate",
        "surface": "SOURCE_GATE",
        "effect": "publish_debt_payload_on_proceed",
    },
}

CRITIQUE_FANOUT_CONTRACT = {
    "parallel_map_id": "critique-fanout",
    "fanout_ref": "megaplan.policy.critique_lenses",
    "step_ref": "SOURCE_CRITIQUE_PANEL_WORKFLOW",
    "reducer_ref": "SOURCE_CRITIQUE",
    "path_template": "critique/{item_id}",
    "route_signal": "critique_payload",
}

CRITIQUE_SKIP_AND_RETRY_POLICY = {
    "bare_robustness": {
        "route_signal": "skip_to_finalize",
        "effect": "workflow_handles_plan_to_finalize_without_handler_fanout",
    },
    "evaluator_retry": {
        "phase": "critique_evaluator",
        "max_attempts": 2,
        "on_exhausted": "blocked",
    },
    "payload_recovery": {
        "scratch_ref": "critique_output.json",
        "promote_to": "critique_v{iteration}.json",
    },
}

CRITIQUE_EXTERNAL_CALL_SURFACE = {
    "runtime_wrapper_ref": "arnold_pipelines.megaplan.orchestration.critique_runtime",
    "retained_handler_ref": "arnold_pipelines.megaplan.handlers.critique:handle_critique",
    "worker_phase": "critique",
    "evaluator_phase": "critique_evaluator",
}

TIEBREAKER_SUBWORKFLOW_SURFACE = {
    "run_step_ref": "SOURCE_TIEBREAKER_RUN",
    "decision_step_ref": "SOURCE_TIEBREAKER_DECIDE",
    "runtime_wrapper_ref": "arnold_pipelines.megaplan.orchestration.tiebreaker_runtime",
    "retained_handler_refs": (
        "arnold_pipelines.megaplan.handlers.tiebreaker:handle_tiebreaker_run",
        "arnold_pipelines.megaplan.handlers.tiebreaker:handle_tiebreaker_decide",
    ),
    "run_completion_route": {
        "route_signal": "default",
        "target_ref": "tiebreaker_decide",
        "failure_behavior": "complete_decision_cycle_with_recorded_artifacts",
    },
    "decision_routes": {
        "pick": {"route_signal": "proceed", "target_ref": "finalize"},
        "replan": {"route_signal": "iterate", "target_ref": "critique-fanout"},
        "escalate": {"route_signal": "escalate", "target_ref": "override"},
    },
    "fallback_route_signal": "escalate",
}

FINALIZE_FALLBACK_ROUTE_SURFACE = {
    "success_route": {"route_signal": "default", "target_ref": "execute"},
    "fallback_routes": {
        "plan_contract_revise_needed": {
            "route_signal": "revise",
            "target_ref": "revise",
            "policy_ref": "megaplan:finalize",
            "reason": "missing_scoped_baseline_test_contract",
        },
    },
}

EXECUTE_GATE_AND_FANOUT_SURFACE = {
    "approval_gates": {
        "destructive_confirmation": {
            "required_unless": "prose_mode",
            "signal_ref": "args.confirm_destructive",
            "failure_code": "missing_confirmation",
        },
        "operator_approval": {
            "required_unless": "state.config.auto_approve",
            "signal_ref": "state.meta.user_approved_gate",
            "grant_signal_ref": "args.user_approved",
            "failure_code": "missing_approval",
        },
        "mutating_preflight": {
            "policy_ref": "arnold_pipelines.megaplan.runtime.execution_environment:preflight_mutating_phase",
            "phase": "execute",
        },
    },
    "fanout_contract": {
        "parallel_map_id": "execute-batches",
        "fanout_ref": "megaplan.execute.batches",
        "step_ref": "SOURCE_EXECUTE_BATCH_WORKFLOW",
        "reducer_ref": "SOURCE_EXECUTE",
        "path_template": "execute/{index}",
        "route_signal": "execute_payload",
    },
    "retry_and_reentry": {
        "review_rework_reexecution": {
            "detect_ref": "last review history result needs_rework",
            "effect": "force_fresh_execute_session",
        },
        "blocked_retry": {
            "detect_ref": "last execute history result blocked",
            "effect": "force_fresh_execute_session",
        },
        "blocked_route": {
            "route_signal": "blocked",
            "target_ref": "override",
            "recoverable_state": "blocked",
            "resume_cursor": {
                "phase": "execute",
                "retry_strategy": "fresh_session",
            },
        },
    },
    "skip_review_routes": {
        "bare": {
            "route_signal": "no_review",
            "target_ref": "halt",
            "artifact": None,
        },
        "deferred_human": {
            "route_signal": "deferred_human",
            "target_ref": "halt",
            "artifact": "review.json",
        },
    },
}

REVIEW_ROUTE_SURFACE = {
    "fan_in_contract": {
        "parallel_map_id": "review-fan-in",
        "fan_in_ref": "review.checks",
        "step_ref": "SOURCE_REVIEW_PANEL_WORKFLOW",
        "reducer_ref": "SOURCE_REVIEW",
        "path_template": "review/{item_id}",
        "route_signal": "review_route_signal",
    },
    "route_groups": {
        "halt": ("pass", "force_proceeded", "deferred_human"),
        "rework": ("rework",),
        "recoverable_block": ("blocked",),
    },
    "rework_cycle": {
        "route_signal": "rework",
        "target_ref": "execute",
        "state_ref": "finalized",
        "fresh_execute_session": True,
    },
    "retry_and_cap": {
        "infrastructure_retry": {
            "route_signal": "blocked",
            "target_ref": "review",
            "state_ref": "executed",
            "retry_on": ("review_incomplete", "review_process_error", "missing_reviewer_evidence"),
        },
        "cap_exhausted_non_blocking": {
            "route_signal": "force_proceeded",
            "target_ref": "halt",
            "state_ref": "done",
        },
        "cap_exhausted_with_blockers": {
            "route_signal": "blocked",
            "target_ref": "override",
            "state_ref": "blocked",
            "resume_cursor": {
                "phase": "review",
                "retry_strategy": "manual_review",
            },
        },
    },
    "escalation": {
        "policy_ref": "megaplan:override",
        "route_signal": "blocked",
        "actions": ("recover-blocked", "force-proceed"),
    },
}

GATE_ROUTE_GROUPS = {
    "finalize": ("proceed", "force_proceed"),
    "revise": ("iterate", "retry_gate", "reprompt_downgrade"),
    "tiebreaker": ("tiebreaker",),
    "override": ("escalate", "blocked_preflight"),
    "halt": ("abort", "suspend"),
}

GATE_FALLBACK_ROUTE_SIGNALS = {
    "blocking_flag_reprompt": "retry_gate",
    "reprompt_downgrade": "iterate",
    "preflight_failed": "blocked_preflight",
    "unknown_recommendation": "escalate",
    "critique_cap": "force_proceed",
}


@workflow(id="megaplan", version="m4-phase3", policy=DEFAULT_POLICY)
def planning_workflow(brief: str) -> None:
    # The V1 source compiler lowers only the decorated workflow body, so this
    # route-compatible spine remains the compiled public-stage authority until
    # neutral subworkflow calls can be inlined without stage-name suffixing.
    prep_signal = SOURCE_PREP(id="prep", brief=brief)
    plan_payload = SOURCE_PLAN(id="plan", prep_payload=prep_signal)

    loop(policy=REVISE_LOOP_POLICY, reentry_id="critique")
    while True:
        critique_payload = parallel_map(
            id="critique-fanout",
            items="megaplan.policy.critique_lenses",
            step=SOURCE_CRITIQUE_PANEL_WORKFLOW,
            reducer=SOURCE_CRITIQUE,
            path_template="critique/{item_id}",
        )
        gate_route_signal = SOURCE_GATE(
            id="gate",
            critique_payload=critique_payload,
        )

        if gate_route_signal == "proceed":
            finalize_payload = SOURCE_FINALIZE(id="finalize", gate_payload=gate_route_signal)
            execute_payload = parallel_map(
                id="execute-batches",
                items="megaplan.execute.batches",
                step=SOURCE_EXECUTE_BATCH_WORKFLOW,
                reducer=SOURCE_EXECUTE,
                path_template="execute/{index}",
            )
            review_route_signal = parallel_map(
                id="review-fan-in",
                items=execute_payload,
                step=SOURCE_REVIEW_PANEL_WORKFLOW,
                reducer=SOURCE_REVIEW,
                path_template="review/{item_id}",
            )
            if review_route_signal == "pass":
                SOURCE_HALT(id="halt", review_payload=review_route_signal)
                return None
            elif review_route_signal == "rework":
                SOURCE_REVISE(id="review_revise", gate_payload=review_route_signal)
                return None
            else:
                SOURCE_HALT(id="review_halt", review_payload=review_route_signal)
                return None
        elif gate_route_signal == "iterate":
            SOURCE_REVISE(id="revise", gate_payload=gate_route_signal)
        elif gate_route_signal == "tiebreaker":
            # Internal pick/replan/escalate semantics stay on the declared child
            # workflow contract so topology can prove them from the authored call site.
            decision = SOURCE_TIEBREAKER_WORKFLOW(id="tiebreaker", gate_payload=gate_route_signal)
            if decision == "proceed":
                finalize_payload = SOURCE_FINALIZE(id="tiebreaker_finalize", gate_payload=decision)
                parallel_map(
                    id="tiebreaker-execute-batches",
                    items="megaplan.execute.batches",
                    step=SOURCE_EXECUTE_BATCH_WORKFLOW,
                    reducer=SOURCE_EXECUTE,
                    path_template="execute/{index}",
                )
                return None
            elif decision == "escalate":
                SOURCE_OVERRIDE(id="tiebreaker_override", gate_payload=decision)
                return None
        elif gate_route_signal == "escalate":
            override_result = SOURCE_OVERRIDE(id="override", gate_payload=gate_route_signal)
            if override_result == "abort":
                SOURCE_HALT(id="override_halt", override_result=override_result)
                return None
            elif override_result == "force_proceed":
                finalize_payload = SOURCE_FINALIZE(id="override_finalize", gate_payload=override_result)
                SOURCE_EXECUTE(id="override_execute", finalize_payload=finalize_payload)
                return None
            elif override_result == "replan":
                SOURCE_REVISE(id="override_revise", gate_payload=override_result)
                return None
            else:
                SOURCE_HALT(id="override_unknown", override_result=override_result)
                return None
        elif gate_route_signal == "abort":
            SOURCE_HALT(id="gate_abort", gate_payload=gate_route_signal)
            return None
        elif gate_route_signal == "suspend":
            SOURCE_HALT(id="gate_suspend", gate_payload=gate_route_signal)
            return None
        elif gate_route_signal == "blocked_preflight":
            SOURCE_OVERRIDE(id="blocked_override", gate_payload=gate_route_signal)
            return None
        elif gate_route_signal == "force_proceed":
            finalize_payload = SOURCE_FINALIZE(id="force_finalize", gate_payload=gate_route_signal)
            SOURCE_EXECUTE(id="force_execute", finalize_payload=finalize_payload)
            return None
        else:
            finalize_payload = SOURCE_FINALIZE(id="fallback_finalize", gate_payload=gate_route_signal)
            SOURCE_EXECUTE(id="fallback_execute", finalize_payload=finalize_payload)
            return None
