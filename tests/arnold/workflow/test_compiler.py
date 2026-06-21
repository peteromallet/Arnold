from __future__ import annotations

import pytest

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
    compile_pipeline,
    validate_manifest,
)

HASH_A = "sha256:" + "a" * 64


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


def test_compile_pipeline_is_exposed_from_workflow_namespace() -> None:
    assert hasattr(workflow, "compile_pipeline")
    assert hasattr(workflow, "CompileDiagnosticError")
