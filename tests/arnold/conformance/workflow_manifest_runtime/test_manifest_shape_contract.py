"""M1 manifest shape contract: compiler output must use existing v1 fields only.

This is the T5 gate.  If the compiler or source compiler ever widens the
serialized manifest schema, this test must fail until the amendment is
documented in ``docs/arnold/workflow-manifest-amendments.md`` and paired with
an updated conformance fixture.
"""

from __future__ import annotations

from arnold.patterns import branch
from arnold.workflow import (
    Capability,
    Input,
    LoopPolicy,
    Output,
    Pipeline,
    Route,
    SourceSpan,
    Step,
    SuspensionRoute,
    WorkflowPolicy,
    compile_pipeline,
)


_MANIFEST_FIELDS = {
    "id",
    "nodes",
    "edges",
    "schema_version",
    "version",
    "capabilities",
    "policy",
    "source_span",
    "metadata",
    "topology_hash",
    "manifest_hash",
}

_NODE_FIELDS = {
    "id",
    "kind",
    "label",
    "inputs",
    "outputs",
    "capabilities",
    "policy",
    "source_span",
    "subpipeline",
    "metadata",
}

_EDGE_FIELDS = {
    "id",
    "source",
    "target",
    "label",
    "condition_ref",
    "metadata",
}


def _sample_manifest() -> dict:
    pattern = branch(
        "decide",
        condition_ref="tests.arnold.patterns._fixtures:decide_condition",
        then_id="plan",
        else_id="review",
    )
    pipeline = Pipeline(
        id="shape-check",
        version="v1",
        steps=[
            Step(
                id="plan",
                kind="agent",
                outputs=[Output("draft")],
                capabilities=[Capability("agent:planner")],
            ),
            Step(
                id="review",
                kind="agent",
                inputs=[Input("draft", value_ref="plan.draft")],
                policy=WorkflowPolicy(
                    loop=LoopPolicy(max_iterations=3),
                    suspension_routes=(SuspensionRoute("resume", reentry_id="retry"),),
                ),
            ),
        ],
        routes=[
            Route(id="plan-review", source="plan", target="review"),
        ],
        source_span=SourceSpan("pipeline.py", 1),
        metadata={"contract": "v1"},
    )
    return compile_pipeline(pipeline, patterns=(pattern,)).to_dict()


def test_manifest_top_level_uses_only_v1_fields() -> None:
    manifest = _sample_manifest()
    assert set(manifest.keys()) <= _MANIFEST_FIELDS


def test_manifest_nodes_use_only_v1_fields() -> None:
    manifest = _sample_manifest()
    assert manifest["nodes"]
    for node in manifest["nodes"]:
        assert set(node.keys()) <= _NODE_FIELDS


def test_manifest_edges_use_only_v1_fields() -> None:
    manifest = _sample_manifest()
    assert manifest["edges"]
    for edge in manifest["edges"]:
        assert set(edge.keys()) <= _EDGE_FIELDS
