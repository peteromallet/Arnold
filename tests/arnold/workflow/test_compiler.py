from __future__ import annotations

from dataclasses import dataclass

import pytest

import arnold.patterns as patterns
from arnold.patterns import PatternBlock, branch
import arnold.workflow as workflow
from arnold.workflow import (
    Capability,
    CompileDiagnosticError,
    Input,
    LoopPolicy,
    Output,
    Pipeline,
    Route,
    SourceSpan,
    Step,
    SubpipelineRef,
    SuspensionRoute,
    WorkflowManifest,
    WorkflowPolicy,
    compile_pattern_block,
    compile_pipeline,
    validate_manifest,
)

HASH_A = "sha256:" + "a" * 64


@dataclass
class MutableLiveInstance:
    value: str = "live"


class CallableInstance:
    def __call__(self) -> str:
        return "live"


def _sample_pipeline() -> Pipeline:
    return Pipeline(
        id="planning",
        version="authoring-v1",
        steps=[
            Step(
                id="plan",
                kind="agent",
                outputs=[Output("draft")],
                capabilities=[Capability("agent:planner")],
                source_span=SourceSpan("pipeline.py", 10),
                metadata={"tags": ["seed"]},
            ),
            Step(
                id="review",
                kind="agent",
                inputs=[Input("draft", value_ref="plan.draft")],
                policy=WorkflowPolicy(
                    suspension_routes=(SuspensionRoute("operator", reentry_id="resume-review"),)
                ),
            ),
        ],
        routes=[Route(id="plan-review", source="plan", target="review", label="review")],
        source_span=SourceSpan("pipeline.py", 1),
    )


def test_compiler_preserves_authored_ids_and_lowers_nodes() -> None:
    pipeline = _sample_pipeline()
    manifest = compile_pipeline(pipeline)

    assert isinstance(manifest, WorkflowManifest)
    assert manifest.id == "planning"
    assert manifest.version == "authoring-v1"
    node_ids = [node.id for node in manifest.nodes]
    assert node_ids == ["plan", "review"]

    plan_node = manifest.nodes[0]
    assert plan_node.kind == "agent"
    assert plan_node.outputs == ("draft",)
    assert plan_node.capabilities[0].capability_id == "agent:planner"
    assert plan_node.source_span == SourceSpan("pipeline.py", 10)
    assert plan_node.metadata["tags"] == ["seed"]

    review_node = manifest.nodes[1]
    assert review_node.inputs == ("draft",)
    assert review_node.policy is not None
    assert review_node.policy.suspension_routes[0].reentry_id == "resume-review"


def test_compiler_lowers_routes_to_deterministic_edges() -> None:
    pipeline = _sample_pipeline()
    manifest = compile_pipeline(pipeline)

    assert len(manifest.edges) == 1
    edge = manifest.edges[0]
    assert edge.id == "plan-review"
    assert edge.source == "plan"
    assert edge.target == "review"
    assert edge.label == "review"


def test_compiler_hashes_are_stable_across_repeated_compilation() -> None:
    first = compile_pipeline(_sample_pipeline())
    second = compile_pipeline(_sample_pipeline())

    assert first.topology_hash == second.topology_hash
    assert first.manifest_hash == second.manifest_hash
    assert first.to_json() == second.to_json()


def test_compiler_rejects_duplicate_step_ids() -> None:
    pipeline = Pipeline(
        id="bad",
        version="v1",
        steps=[
            Step(id="plan", kind="agent"),
            Step(id="plan", kind="agent"),
        ],
    )

    with pytest.raises(CompileDiagnosticError, match="duplicate step ids") as exc_info:
        compile_pipeline(pipeline)

    assert exc_info.value.node_id is None
    assert exc_info.value.field == "steps"


def test_compiler_rejects_dangling_route_target() -> None:
    pipeline = Pipeline(
        id="bad",
        version="v1",
        steps=[Step(id="plan", kind="agent")],
        routes=[Route(id="missing", source="plan", target="absent")],
    )

    with pytest.raises(CompileDiagnosticError, match="route target 'absent' is not a declared step"):
        compile_pipeline(pipeline)


def test_compiler_validates_manifest_before_return() -> None:
    pipeline = Pipeline(
        id="bad",
        version="v1",
        steps=[
            Step(id="plan", kind="agent"),
            Step(id="plan", kind="agent"),
        ],
    )

    with pytest.raises(Exception):  # duplicate IDs are rejected before validation
        compile_pipeline(pipeline)


def test_compiler_preserves_subpipeline_and_policies() -> None:
    pipeline = Pipeline(
        id="nested",
        version="v1",
        steps=[
            Step(
                id="sub",
                kind="subpipeline",
                subpipeline=SubpipelineRef(manifest_hash=HASH_A, alias="inner"),
                policy=WorkflowPolicy(loop=LoopPolicy(max_iterations=5)),
            ),
        ],
    )

    manifest = compile_pipeline(pipeline)
    node = manifest.nodes[0]

    assert node.subpipeline is not None
    assert node.subpipeline.manifest_hash == HASH_A
    assert node.subpipeline.alias == "inner"
    assert node.policy is not None
    assert node.policy.loop is not None
    assert node.policy.loop.max_iterations == 5
    validate_manifest(manifest)


def test_compiler_lowers_capabilities_at_manifest_level() -> None:
    pipeline = Pipeline(
        id="cap",
        version="v1",
        steps=[Step(id="plan", kind="agent")],
        capabilities=[Capability("agent:planner", route="fast", required=False)],
    )

    manifest = compile_pipeline(pipeline)
    assert manifest.capabilities[0].capability_id == "agent:planner"
    assert manifest.capabilities[0].route == "fast"
    assert manifest.capabilities[0].required is False


def test_compiler_normalizes_pattern_blocks_via_explicit_parameter() -> None:
    pattern = branch(
        "decide",
        condition_ref="tests.arnold.patterns._fixtures:decide_condition",
        then_id="approve",
        else_id="fallback",
    )
    pipeline = Pipeline(
        id="patterned",
        version="v1",
        steps=[
            Step(id="approve", kind="agent"),
            Step(id="fallback", kind="agent"),
        ],
    )

    manifest = compile_pipeline(pipeline, patterns=(pattern,))

    assert {node.id for node in manifest.nodes} == {"approve", "fallback", "decide"}
    assert {edge.label for edge in manifest.edges} == {"then", "else"}


def test_compiler_rejects_pattern_blocks_inside_pipeline_steps() -> None:
    pattern = PatternBlock(steps=(Step(id="inner", kind="agent"),))
    pipeline = Pipeline(
        id="bad",
        version="v1",
        steps=[pattern],  # type: ignore[list-item]
    )

    with pytest.raises(CompileDiagnosticError, match="PatternBlock values are not allowed"):
        compile_pipeline(pipeline)


def test_compiler_rejects_live_mutable_instances_in_metadata() -> None:
    pipeline = Pipeline(
        id="bad",
        version="v1",
        steps=[Step(id="plan", kind="agent", metadata={"live": MutableLiveInstance()})],
    )

    with pytest.raises(CompileDiagnosticError, match="MutableLiveInstance"):
        compile_pipeline(pipeline)


def test_compiler_rejects_callable_instances_in_metadata() -> None:
    pipeline = Pipeline(
        id="bad",
        version="v1",
        steps=[Step(id="plan", kind="agent", metadata={"callable": CallableInstance()})],
    )

    with pytest.raises(CompileDiagnosticError, match="CallableInstance"):
        compile_pipeline(pipeline)


def test_compiler_rejects_live_object_references_in_nested_metadata() -> None:
    pipeline = Pipeline(
        id="bad",
        version="v1",
        steps=[Step(id="plan", kind="agent", metadata={"nested": {"ref": object()}})],
    )

    with pytest.raises(CompileDiagnosticError, match="object"):
        compile_pipeline(pipeline)


def test_compiler_rejects_non_primitive_pattern_metadata() -> None:
    pattern = PatternBlock(
        steps=(Step(id="pattern-step", kind="agent", metadata={"live": object()}),)
    )
    pipeline = Pipeline(id="bad", version="v1", steps=[])

    with pytest.raises(CompileDiagnosticError, match="JSON primitives"):
        compile_pipeline(pipeline, patterns=(pattern,))


def test_compile_pattern_block_compiles_self_contained_block_to_manifest() -> None:
    pattern = PatternBlock(
        steps=(
            Step(id="a", kind="agent"),
            Step(id="b", kind="agent"),
        ),
        routes=(Route(id="a-b", source="a", target="b"),),
    )

    manifest = compile_pattern_block(pattern, id="self-contained", version="v1")

    assert manifest.id == "self-contained"
    assert {node.id for node in manifest.nodes} == {"a", "b"}
    assert len(manifest.edges) == 1
    validate_manifest(manifest)


def test_compile_pattern_block_validates_route_targets_after_expansion() -> None:
    pattern = PatternBlock(
        steps=(Step(id="a", kind="agent"),),
        routes=(Route(id="a-missing", source="a", target="missing"),),
    )

    with pytest.raises(CompileDiagnosticError, match="route target .* is not a declared step"):
        compile_pattern_block(pattern)


def test_compile_pipeline_patterns_reject_duplicate_step_ids() -> None:
    pattern_a = PatternBlock(steps=(Step(id="dup", kind="agent"),))
    pattern_b = PatternBlock(steps=(Step(id="dup", kind="agent"),))
    pipeline = Pipeline(id="bad", version="v1", steps=[])

    with pytest.raises(CompileDiagnosticError, match="duplicate step ids"):
        compile_pipeline(pipeline, patterns=(pattern_a, pattern_b))


def test_compile_pattern_block_is_exposed_from_workflow_namespace() -> None:
    assert hasattr(workflow, "compile_pattern_block")


def test_compile_pipeline_is_exposed_from_workflow_namespace() -> None:
    assert hasattr(workflow, "compile_pipeline")
    assert hasattr(workflow, "CompileDiagnosticError")


def test_compiler_accepts_base_pattern_steps() -> None:
    plan = patterns.agent(
        "plan",
        task="draft",
        prompt_ref="tests.arnold.patterns._fixtures:agent_prompt",
    )
    call = patterns.external_call(
        "call",
        endpoint_ref="tests.arnold.patterns._fixtures:decide_condition",
    )
    merged = patterns.merge("merged", reducer_ref="tests.arnold.patterns._fixtures:reducer")
    inner = patterns.subpipeline("inner", manifest_hash=HASH_A)

    pipeline = Pipeline(
        id="base",
        version="v1",
        steps=[plan, call, merged, inner],
        routes=[Route(id="plan-call", source="plan", target="call")],
    )
    manifest = compile_pipeline(pipeline)

    assert {node.id for node in manifest.nodes} == {"plan", "call", "merged", "inner"}
    validate_manifest(manifest)


def test_compiler_accepts_control_pattern_blocks() -> None:
    pipeline = Pipeline(
        id="control",
        version="v1",
        steps=[
            Step(id="fragile", kind="agent"),
            Step(id="then", kind="agent"),
            Step(id="else", kind="agent"),
            Step(id="body", kind="agent"),
        ],
    )
    blocks = (
        patterns.branch(
            "decide",
            condition_ref="tests.arnold.patterns._fixtures:decide_condition",
            then_id="then",
            else_id="else",
        ),
        patterns.loop(
            "loop",
            "body",
            until_ref="tests.arnold.patterns._fixtures:decide_condition",
            max_iterations=3,
            reentry_id="retry",
        ),
        patterns.retry("retry", target_id="fragile", max_attempts=3),
    )

    manifest = compile_pipeline(pipeline, patterns=blocks)

    validate_manifest(manifest)
    assert any(edge.condition_ref == "retry" for edge in manifest.edges)
    assert any(edge.condition_ref == "retry:retry" for edge in manifest.edges)


def test_compiler_accepts_human_gate_as_generic_suspension() -> None:
    gate = patterns.human_gate("gate", capability_id="human:operator", reentry_id="resume")
    pipeline = Pipeline(id="gate", version="v1", steps=[gate])

    manifest = compile_pipeline(pipeline)

    node = next(node for node in manifest.nodes if node.id == "gate")
    assert node.kind == "suspension"
    assert node.capabilities[0].capability_id == "human:operator"
    assert node.policy is not None
    assert node.policy.suspension_routes[0].reentry_id == "resume"
    validate_manifest(manifest)


def test_compiler_accepts_review_pattern_blocks() -> None:
    pipeline = Pipeline(
        id="review",
        version="v1",
        steps=[Step(id="draft", kind="agent")],
    )
    blocks = (
        patterns.critique(
            "critique",
            "draft",
            critique_ref="tests.arnold.patterns._fixtures:agent_prompt",
        ),
        patterns.review(
            "review",
            "draft",
            review_ref="tests.arnold.patterns._fixtures:agent_prompt",
            approve_ref="tests.arnold.patterns._fixtures:decide_condition",
        ),
        patterns.revise(
            "revise",
            "draft",
            revise_ref="tests.arnold.patterns._fixtures:agent_prompt",
            until_ref="tests.arnold.patterns._fixtures:decide_condition",
            max_iterations=4,
            reentry_id="retry-revise",
        ),
    )

    manifest = compile_pipeline(pipeline, patterns=blocks)

    validate_manifest(manifest)
    assert any(node.kind == "critique" for node in manifest.nodes)
    assert any(node.kind == "review" for node in manifest.nodes)
    assert any(node.kind == "revise" for node in manifest.nodes)


def test_compiler_accepts_tournament_with_bounded_tiebreaker_loopback() -> None:
    pipeline = Pipeline(
        id="tournament",
        version="v1",
        steps=[
            Step(id="candidate-a", kind="agent"),
            Step(id="candidate-b", kind="agent"),
        ],
    )
    block = patterns.tournament(
        "tourney",
        candidate_ids=("candidate-a", "candidate-b"),
        merge_id="winner",
        winner_ref="tests.arnold.patterns._fixtures:judge_winner",
        tie_ref="tests.arnold.patterns._fixtures:decide_condition",
        max_tiebreaker_rounds=3,
    )

    manifest = compile_pipeline(pipeline, patterns=(block,))

    validate_manifest(manifest)
    retry_edge = next(edge for edge in manifest.edges if edge.label == "retry")
    assert retry_edge.source == "tourney-tiebreak-2"
    assert retry_edge.target == "tourney-judge"
    assert retry_edge.condition_ref == "tourney:tiebreak"
    judge = next(node for node in manifest.nodes if node.id == "tourney-judge")
    assert judge.policy is not None
    assert judge.policy.loop is not None
    assert judge.policy.loop.max_iterations == 3
