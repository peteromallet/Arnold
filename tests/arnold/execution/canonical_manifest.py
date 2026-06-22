"""Canonical Megaplan-shaped manifest builder for execution scenario tests.

The manifest contains every shape from ``tests/fixtures/workflow/canonical_megaplan_shapes.yaml``
wired into a single runnable DAG plus execution-specific policies (authority,
compensation, escalation, control transitions, topology overlays, and budgets).
"""

from __future__ import annotations

from arnold.manifest import (
    AuthorityRequirement,
    BudgetPolicy,
    CapabilityRequirement,
    CompensationPolicy,
    CompensationTarget,
    ControlTransitionSlot,
    EffectRef,
    EscalationPolicy,
    FanoutPolicy,
    IdempotencyPolicy,
    LoopPolicy,
    RetryPolicy,
    SubpipelineRef,
    SuspensionRoute,
    TopologyOverlaySlot,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
)

DECIDE_CONDITION = "tests.arnold.patterns._fixtures:decide_condition"
JUDGE_WINNER = "tests.arnold.patterns._fixtures:judge_winner"
REDUCER = "tests.arnold.patterns._fixtures:reducer"
HASH_A = "sha256:" + "a" * 64


def canonical_execution_manifest() -> WorkflowManifest:
    """Return a compiled, validated canonical manifest for runtime gate tests."""

    nodes = [
        WorkflowNode(id="start", kind="noop"),
        WorkflowNode(id="branch-decide", kind="branch"),
        WorkflowNode(id="branch-plan", kind="agent"),
        WorkflowNode(id="branch-fallback", kind="agent"),
        WorkflowNode(
            id="loop",
            kind="loop",
            policy=WorkflowPolicy(
                loop=LoopPolicy(max_iterations=3, until_ref=DECIDE_CONDITION),
                suspension_routes=(
                    SuspensionRoute(route_id="loop-reentry", reentry_id="retry"),
                ),
            ),
        ),
        WorkflowNode(id="loop-body", kind="agent"),
        WorkflowNode(
            id="revise",
            kind="revise",
            policy=WorkflowPolicy(
                loop=LoopPolicy(max_iterations=4, until_ref=DECIDE_CONDITION),
                suspension_routes=(
                    SuspensionRoute(route_id="revise-reentry", reentry_id="retry-revise"),
                ),
            ),
        ),
        WorkflowNode(id="draft", kind="agent"),
        WorkflowNode(
            id="fan",
            kind="fanout",
            policy=WorkflowPolicy(
                fanout=FanoutPolicy(mode="static", width=2, reducer_ref=REDUCER),
            ),
        ),
        WorkflowNode(id="fan-branch-a", kind="agent"),
        WorkflowNode(id="fan-branch-b", kind="agent"),
        WorkflowNode(id="fan-merged", kind="merge"),
        WorkflowNode(id="retry", kind="retry"),
        WorkflowNode(
            id="retry-fragile",
            kind="agent",
            policy=WorkflowPolicy(
                retry=RetryPolicy(max_attempts=3, backoff="none", retry_on=("error",)),
                escalation=EscalationPolicy(
                    targets=("escalate-supervisor",),
                    escalate_after_attempts=3,
                ),
            ),
        ),
        WorkflowNode(
            id="inner",
            kind="subpipeline",
            subpipeline=SubpipelineRef(manifest_hash=HASH_A, alias="nested"),
        ),
        WorkflowNode(
            id="gate",
            kind="suspension",
            capabilities=(
                CapabilityRequirement(
                    capability_id="human:operator",
                    route="default",
                    required=True,
                ),
            ),
            policy=WorkflowPolicy(
                suspension_routes=(
                    SuspensionRoute(
                        route_id="gate-gate",
                        capability_id="human:operator",
                        reentry_id="resume",
                    ),
                ),
                control_transitions=(
                    ControlTransitionSlot(
                        transition_id="ctrl.promote",
                        transition_type="supervisor_promotion",
                        target_ref="promote-supervisor",
                    ),
                ),
            ),
        ),
        WorkflowNode(id="override-decide", kind="branch"),
        WorkflowNode(id="override-primary", kind="agent"),
        WorkflowNode(id="override-fallback", kind="agent"),
        WorkflowNode(id="escalate-review", kind="review"),
        WorkflowNode(id="escalate-supervisor", kind="agent"),
        WorkflowNode(id="compensate-fragile", kind="agent"),
        WorkflowNode(id="compensate-target", kind="agent"),
        WorkflowNode(id="promote-gate", kind="suspension"),
        WorkflowNode(id="promote-supervisor", kind="agent"),
        WorkflowNode(id="feedback-review", kind="review"),
        WorkflowNode(id="feedback-plan", kind="agent"),
        WorkflowNode(
            id="robust-plan",
            kind="agent",
            policy=WorkflowPolicy(
                budget=BudgetPolicy(
                    max_cost=1.0,
                    max_seconds=30.0,
                    max_attempts=2,
                    token_budget=1000,
                ),
            ),
        ),
        WorkflowNode(
            id="overlay",
            kind="agent",
            policy=WorkflowPolicy(
                topology_overlays=(
                    TopologyOverlaySlot(
                        overlay_id="overlay.dynamic",
                        overlay_type="route",
                        source_ref="overlay",
                        target_refs=("overlay-extra",),
                    ),
                ),
                compensation=CompensationPolicy(
                    targets=(
                        CompensationTarget(
                            target_id="robust-plan",
                            effect=EffectRef(
                                effect_id="fx.compensate",
                                idempotency=IdempotencyPolicy(key_ref="comp-robust"),
                            ),
                        ),
                    )
                ),
            ),
            metadata={
                "dynamic_events": [
                    {"event": "on_branch", "slot": "branch"},
                    {"event": "on_suspend", "slot": "suspension"},
                ],
            },
        ),
        WorkflowNode(id="overlay-extra", kind="noop"),
        WorkflowNode(id="tourney-judge", kind="branch"),
        WorkflowNode(id="tourney-tiebreak-1", kind="branch"),
        WorkflowNode(id="tourney-tiebreak-2", kind="branch"),
        WorkflowNode(id="tourney-winner", kind="merge"),
        WorkflowNode(id="tourney-candidate-a", kind="agent"),
        WorkflowNode(id="tourney-candidate-b", kind="agent"),
    ]

    edges = [
        WorkflowEdge(id="start-branch-decide", source="start", target="branch-decide"),
        WorkflowEdge(
            id="branch-decide-branch-plan",
            source="branch-decide",
            target="branch-plan",
            label="then",
            condition_ref=DECIDE_CONDITION,
        ),
        WorkflowEdge(
            id="branch-decide-branch-fallback",
            source="branch-decide",
            target="branch-fallback",
            label="else",
            condition_ref=f"{DECIDE_CONDITION}:negated",
        ),
        WorkflowEdge(id="branch-plan-loop", source="branch-plan", target="loop"),
        WorkflowEdge(id="branch-fallback-loop", source="branch-fallback", target="loop"),
        WorkflowEdge(id="loop-loop-body", source="loop", target="loop-body", label="go"),
        WorkflowEdge(
            id="loop-body-loop",
            source="loop-body",
            target="loop",
            label="reentry",
            condition_ref="retry",
        ),
        WorkflowEdge(id="loop-fan", source="loop", target="fan"),
        WorkflowEdge(id="fan-fan-branch-a", source="fan", target="fan-branch-a", label="branch"),
        WorkflowEdge(id="fan-fan-branch-b", source="fan", target="fan-branch-b", label="branch"),
        WorkflowEdge(
            id="fan-branch-a-fan-merged",
            source="fan-branch-a",
            target="fan-merged",
            label="join",
        ),
        WorkflowEdge(
            id="fan-branch-b-fan-merged",
            source="fan-branch-b",
            target="fan-merged",
            label="join",
        ),
        WorkflowEdge(id="fan-merged-retry", source="fan-merged", target="retry"),
        WorkflowEdge(
            id="retry-retry-fragile",
            source="retry",
            target="retry-fragile",
            label="attempt",
        ),
        WorkflowEdge(id="retry-fragile-inner", source="retry-fragile", target="inner"),
        WorkflowEdge(id="inner-gate", source="inner", target="gate"),
        WorkflowEdge(id="gate-revise", source="gate", target="revise"),
        WorkflowEdge(id="revise-draft", source="revise", target="draft", label="go"),
        WorkflowEdge(
            id="draft-revise",
            source="draft",
            target="revise",
            label="revise",
            condition_ref="retry-revise",
        ),
        WorkflowEdge(id="revise-override-decide", source="revise", target="override-decide"),
        WorkflowEdge(
            id="override-decide-override-primary",
            source="override-decide",
            target="override-primary",
            label="default",
        ),
        WorkflowEdge(
            id="override-decide-override-fallback",
            source="override-decide",
            target="override-fallback",
            label="fallback",
        ),
        WorkflowEdge(id="override-primary-escalate-review", source="override-primary", target="escalate-review"),
        WorkflowEdge(id="override-fallback-escalate-review", source="override-fallback", target="escalate-review"),
        WorkflowEdge(
            id="escalate-review-escalate-supervisor",
            source="escalate-review",
            target="escalate-supervisor",
            label="escalate",
        ),
        WorkflowEdge(id="escalate-supervisor-compensate-fragile", source="escalate-supervisor", target="compensate-fragile"),
        WorkflowEdge(
            id="compensate-fragile-compensate-target",
            source="compensate-fragile",
            target="compensate-target",
            label="compensate",
        ),
        WorkflowEdge(id="compensate-target-feedback-review", source="compensate-target", target="feedback-review"),
        WorkflowEdge(
            id="feedback-review-feedback-plan",
            source="feedback-review",
            target="feedback-plan",
            label="feedback",
        ),
        WorkflowEdge(id="feedback-plan-robust-plan", source="feedback-plan", target="robust-plan"),
        WorkflowEdge(id="robust-plan-overlay", source="robust-plan", target="overlay"),
        WorkflowEdge(id="overlay-tourney-candidate-a", source="overlay", target="tourney-candidate-a"),
        WorkflowEdge(id="overlay-tourney-candidate-b", source="overlay", target="tourney-candidate-b"),
        WorkflowEdge(
            id="tourney-candidate-a-tourney-judge",
            source="tourney-candidate-a",
            target="tourney-judge",
            label="candidate",
        ),
        WorkflowEdge(
            id="tourney-candidate-b-tourney-judge",
            source="tourney-candidate-b",
            target="tourney-judge",
            label="candidate",
        ),
        WorkflowEdge(
            id="tourney-judge-tourney-tiebreak-1",
            source="tourney-judge",
            target="tourney-tiebreak-1",
            label="tie",
            condition_ref=DECIDE_CONDITION,
        ),
        WorkflowEdge(
            id="tourney-judge-tourney-winner",
            source="tourney-judge",
            target="tourney-winner",
            label="winner",
            condition_ref=JUDGE_WINNER,
        ),
        WorkflowEdge(
            id="tourney-tiebreak-1-tourney-tiebreak-2",
            source="tourney-tiebreak-1",
            target="tourney-tiebreak-2",
            label="tie",
            condition_ref=DECIDE_CONDITION,
        ),
        WorkflowEdge(
            id="tourney-tiebreak-1-tourney-winner",
            source="tourney-tiebreak-1",
            target="tourney-winner",
            label="winner",
            condition_ref=JUDGE_WINNER,
        ),
        WorkflowEdge(
            id="tourney-tiebreak-2-tourney-winner",
            source="tourney-tiebreak-2",
            target="tourney-winner",
            label="winner",
            condition_ref=JUDGE_WINNER,
        ),
    ]

    policy = WorkflowPolicy(
        budget=BudgetPolicy(
            max_cost=10.0,
            max_seconds=300.0,
            max_attempts=10,
            token_budget=10000,
        ),
        authority=(
            AuthorityRequirement(authority_id="resume-auth", action="resume"),
        ),
    )

    return WorkflowManifest(
        id="canonical-megaplan-execution",
        nodes=nodes,
        edges=edges,
        policy=policy,
    )
