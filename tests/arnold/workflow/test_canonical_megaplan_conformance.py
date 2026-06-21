from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

import arnold.patterns as patterns
from arnold.workflow import (
    BudgetPolicy,
    Capability,
    Input,
    LoopPolicy,
    Output,
    Pipeline,
    Route,
    SourceSpan,
    Step,
    SubpipelineRef,
    SuspensionRoute,
    WorkflowPolicy,
    compile_pipeline,
)
from tests.arnold.patterns import _fixtures

HASH_A = "sha256:" + "a" * 64
FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "workflow" / "canonical_megaplan_shapes.yaml"


def _load_shapes() -> dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["shapes"]


def _build_pipeline() -> Pipeline:
    branch_block = patterns.branch(
        "branch-decide",
        condition_ref="tests.arnold.patterns._fixtures:decide_condition",
        then_id="branch-plan",
        else_id="branch-fallback",
    )
    loop_block = patterns.loop(
        "loop",
        "loop-body",
        until_ref="tests.arnold.patterns._fixtures:decide_condition",
        max_iterations=3,
        reentry_id="retry",
    )
    revise_block = patterns.revise(
        "revise",
        "draft",
        revise_ref="tests.arnold.patterns._fixtures:agent_prompt",
        until_ref="tests.arnold.patterns._fixtures:decide_condition",
        max_iterations=4,
        reentry_id="retry-revise",
    )
    panel_block = patterns.panel(
        "fan",
        branch_ids=("fan-branch-a", "fan-branch-b"),
        merge_id="fan-merged",
        reducer_ref="tests.arnold.patterns._fixtures:reducer",
    )
    retry_block = patterns.retry(
        "retry",
        target_id="retry-fragile",
        max_attempts=3,
        retry_on=("error",),
    )
    sub_step = patterns.subpipeline("inner", manifest_hash=HASH_A, alias="nested")
    gate_step = patterns.human_gate("gate", capability_id="human:operator", reentry_id="resume")

    override_decide = Step(
        id="override-decide",
        kind="branch",
        metadata={"condition_ref": "tests.arnold.patterns._fixtures:decide_condition"},
    )
    override_routes = (
        Route(id="override-decide-override-primary", source="override-decide", target="override-primary", label="default"),
        Route(id="override-decide-override-fallback", source="override-decide", target="override-fallback", label="fallback"),
    )

    escalate_review = Step(id="escalate-review", kind="review")
    escalate_route = Route(
        id="escalate-review-escalate-supervisor",
        source="escalate-review",
        target="escalate-supervisor",
        label="escalate",
    )

    compensate_fragile = Step(id="compensate-fragile", kind="agent")
    compensate_target = Step(id="compensate-target", kind="agent")
    compensate_route = Route(
        id="compensate-fragile-compensate-target",
        source="compensate-fragile",
        target="compensate-target",
        label="compensate",
    )

    promote_gate = Step(id="promote-gate", kind="suspension")
    promote_route = Route(
        id="promote-gate-promote-supervisor",
        source="promote-gate",
        target="promote-supervisor",
        label="promote",
    )

    feedback_review = Step(id="feedback-review", kind="review")
    feedback_plan = Step(id="feedback-plan", kind="agent")
    feedback_route = Route(
        id="feedback-review-feedback-plan",
        source="feedback-review",
        target="feedback-plan",
        label="feedback",
    )

    robust_plan = patterns.agent(
        "robust-plan",
        task="robust",
        prompt_ref="tests.arnold.patterns._fixtures:agent_prompt",
        policy=WorkflowPolicy(
            budget=BudgetPolicy(max_cost=1.0, max_seconds=30.0, max_attempts=2, token_budget=1000),
        ),
    )
    overlay = patterns.agent(
        "overlay",
        task="overlay",
        prompt_ref="tests.arnold.patterns._fixtures:agent_prompt",
        metadata={
            "dynamic_events": [
                {"event": "on_branch", "slot": "branch"},
                {"event": "on_suspend", "slot": "suspension"},
            ],
        },
    )
    tournament_block = patterns.tournament(
        "tourney",
        candidate_ids=("tourney-candidate-a", "tourney-candidate-b"),
        merge_id="tourney-winner",
        winner_ref="tests.arnold.patterns._fixtures:judge_winner",
        tie_ref="tests.arnold.patterns._fixtures:decide_condition",
    )

    all_steps = [
        Step(id="branch-plan", kind="agent"),
        Step(id="branch-fallback", kind="agent"),
        *branch_block.steps,
        Step(id="loop-body", kind="agent"),
        *loop_block.steps,
        Step(id="draft", kind="agent"),
        *revise_block.steps,
        Step(id="fan-branch-a", kind="agent"),
        Step(id="fan-branch-b", kind="agent"),
        *panel_block.steps,
        Step(id="retry-fragile", kind="agent"),
        *retry_block.steps,
        sub_step,
        gate_step,
        override_decide,
        Step(id="override-primary", kind="agent"),
        Step(id="override-fallback", kind="agent"),
        escalate_review,
        Step(id="escalate-supervisor", kind="agent"),
        compensate_fragile,
        compensate_target,
        promote_gate,
        Step(id="promote-supervisor", kind="agent"),
        feedback_review,
        feedback_plan,
        robust_plan,
        overlay,
        *tournament_block.steps,
        Step(id="tourney-candidate-a", kind="agent"),
        Step(id="tourney-candidate-b", kind="agent"),
    ]
    all_routes = [
        *branch_block.routes,
        Route(id="loop-loop-body", source="loop", target="loop-body", label="go"),
        *loop_block.routes,
        *revise_block.routes,
        *panel_block.routes,
        *retry_block.routes,
        *override_routes,
        escalate_route,
        compensate_route,
        promote_route,
        feedback_route,
        *tournament_block.routes,
    ]
    return Pipeline(
        id="canonical-megaplan",
        version="conformance-v1",
        steps=all_steps,
        routes=all_routes,
        source_span=SourceSpan("pipeline.py", 1),
    )


def _normalize_capabilities(capabilities: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {"capability_id": cap.get("capability_id"), "route": cap.get("route", "default"), "required": cap.get("required", True)}
        for cap in capabilities
    )


def _assert_shape_matches(manifest, shape: dict[str, Any]) -> None:
    nodes_by_id = {node.id: node for node in manifest.nodes}
    edges_by_id = {edge.id: edge for edge in manifest.edges}

    for expected_node in shape["nodes"]:
        node = nodes_by_id.get(expected_node["id"])
        assert node is not None, f"missing node {expected_node['id']}"
        assert node.kind == expected_node["kind"], f"node {node.id} kind mismatch"
        if "capabilities" in expected_node:
            assert _normalize_capabilities(expected_node["capabilities"]) == tuple(
                {"capability_id": cap.capability_id, "route": cap.route, "required": cap.required}
                for cap in node.capabilities
            )
        if expected_node["id"] in shape.get("subpipelines", {}):
            expected = shape["subpipelines"][expected_node["id"]]
            assert node.subpipeline is not None
            assert node.subpipeline.manifest_hash == expected["manifest_hash"]
            assert node.subpipeline.alias == expected["alias"]

    for expected_edge in shape.get("edges", ()):
        edge = edges_by_id.get(expected_edge["id"])
        assert edge is not None, f"missing edge {expected_edge['id']}"
        assert edge.source == expected_edge["source"]
        assert edge.target == expected_edge["target"]
        assert edge.label == expected_edge["label"]
        assert edge.condition_ref == expected_edge.get("condition_ref")

    for node_id, expected_policy in shape.get("policies", {}).items():
        node = nodes_by_id[node_id]
        assert node.policy is not None, f"node {node_id} missing expected policy"
        if "loop" in expected_policy:
            assert node.policy.loop is not None
            assert node.policy.loop.max_iterations == expected_policy["loop"]["max_iterations"]
            assert node.policy.loop.until_ref == expected_policy["loop"].get("until_ref")
        if "retry" in expected_policy:
            assert node.policy.retry is not None
            assert node.policy.retry.max_attempts == expected_policy["retry"]["max_attempts"]
            assert node.policy.retry.backoff == expected_policy["retry"]["backoff"]
            assert node.policy.retry.retry_on == tuple(expected_policy["retry"]["retry_on"])
        if "fanout" in expected_policy:
            assert node.policy.fanout is not None
            assert node.policy.fanout.mode == expected_policy["fanout"]["mode"]
            assert node.policy.fanout.reducer_ref == expected_policy["fanout"].get("reducer_ref")
        if "budget" in expected_policy:
            assert node.policy.budget is not None
            assert node.policy.budget.max_cost == expected_policy["budget"]["max_cost"]
        if "suspension_routes" in expected_policy:
            expected_routes = expected_policy["suspension_routes"]
            actual = [
                {
                    "route_id": route.route_id,
                    "capability_id": route.capability_id,
                    "reentry_id": route.reentry_id,
                }
                for route in node.policy.suspension_routes
            ]
            assert actual == expected_routes, f"suspension routes mismatch for {node_id}"

    for node_id, expected_metadata in shape.get("metadata", {}).items():
        node = nodes_by_id[node_id]
        for key, value in expected_metadata.items():
            assert node.metadata.get(key) == value, f"metadata mismatch for {node_id}.{key}"


@pytest.mark.parametrize("shape_name", list(_load_shapes().keys()))
def test_canonical_shape(shape_name: str) -> None:
    shapes = _load_shapes()
    pipeline = _build_pipeline()
    manifest = compile_pipeline(pipeline)
    _assert_shape_matches(manifest, shapes[shape_name])


def test_compiled_manifest_validates_and_hashes_stably() -> None:
    pipeline = _build_pipeline()
    first = compile_pipeline(pipeline)
    second = compile_pipeline(pipeline)

    assert first.manifest_hash == second.manifest_hash
    assert first.topology_hash == second.topology_hash
    validate_manifest = __import__("arnold.workflow", fromlist=["validate_manifest"]).validate_manifest
    validate_manifest(first)


def test_tournament_has_two_full_tiebreaker_rounds() -> None:
    shapes = _load_shapes()
    pipeline = _build_pipeline()
    manifest = compile_pipeline(pipeline)
    _assert_shape_matches(manifest, shapes["tournament"])

    tie_routes = [
        edge for edge in manifest.edges
        if edge.label == "tie"
    ]
    assert len(tie_routes) == 2
    assert tie_routes[0].source == "tourney-judge"
    assert tie_routes[0].target == "tourney-tiebreak-1"
    assert tie_routes[1].source == "tourney-tiebreak-1"
    assert tie_routes[1].target == "tourney-tiebreak-2"


def test_loop_revise_is_explicit_bounded_reentry() -> None:
    shapes = _load_shapes()
    pipeline = _build_pipeline()
    manifest = compile_pipeline(pipeline)
    _assert_shape_matches(manifest, shapes["loop_revise"])

    assert any(edge.condition_ref == "retry" for edge in manifest.edges)
    assert any(edge.condition_ref == "retry-revise" for edge in manifest.edges)
