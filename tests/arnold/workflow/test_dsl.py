from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

import arnold.workflow as workflow
from arnold.workflow import (
    Capability,
    Input,
    Output,
    Pipeline,
    Route,
    SourceSpan,
    Step,
    SuspensionRoute,
    WorkflowPolicy,
)


def test_explicit_node_pipeline_authoring_accepts_stable_ids() -> None:
    pipeline = workflow.Pipeline(
        id="planning",
        version="authoring-v1",
        steps=[
            workflow.Step(
                id="plan",
                kind="agent",
                outputs=[workflow.Output("draft")],
                capabilities=[workflow.Capability("agent:planner")],
                source_span=workflow.SourceSpan("pipeline.py", 10),
                metadata={"tags": ["seed"]},
            ),
            workflow.Step(
                id="review",
                kind="agent",
                inputs=[workflow.Input("draft", value_ref="plan.draft")],
                policy=WorkflowPolicy(
                    suspension_routes=(SuspensionRoute("operator", reentry_id="resume-review"),)
                ),
            ),
        ],
        routes=[workflow.Route(id="plan-review", source="plan", target="review", label="review")],
        source_span=workflow.SourceSpan("pipeline.py", 1),
    )

    assert pipeline.id == "planning"
    assert pipeline.version == "authoring-v1"
    assert [step.id for step in pipeline.steps] == ["plan", "review"]
    assert pipeline.routes == (Route(id="plan-review", source="plan", target="review", label="review"),)
    assert pipeline.steps[0].outputs == (Output("draft"),)
    assert pipeline.steps[0].capabilities == (Capability("agent:planner"),)
    assert pipeline.steps[1].inputs == (Input("draft", value_ref="plan.draft"),)
    assert isinstance(pipeline.source_span, SourceSpan)


def test_dsl_objects_are_frozen_and_normalize_mutable_inputs() -> None:
    metadata = {"nested": {"items": ["a"]}}
    step = Step(id="plan", kind="agent", metadata=metadata)
    pipeline = Pipeline(id="planning", version="v1", steps=[step], metadata=metadata)

    metadata["nested"]["items"].append("mutated")

    assert pipeline.steps == (step,)
    assert pipeline.metadata["nested"]["items"] == ("a",)
    with pytest.raises(TypeError):
        pipeline.metadata["extra"] = True  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        pipeline.version = "v2"  # type: ignore[misc]


def test_dsl_rejects_invalid_stable_ids() -> None:
    with pytest.raises(ValueError, match="step id"):
        Step(id="", kind="agent")
    with pytest.raises(ValueError, match="route source"):
        Route(id="bad-route", source="", target="plan")
    with pytest.raises(ValueError, match="workflow alias"):
        Pipeline(id="not valid", version="v1", steps=[])


def test_workflow_public_api_has_no_banned_authoring_surfaces() -> None:
    banned = {
        "PipelineBuilder",
        "Stage",
        "Edge",
        "stage",
        "step",
        "pipeline",
        "builder",
    }

    assert workflow.PUBLIC_EXPORTS == ("Pipeline", "Step", "Route", "Input", "Output", "Capability")
    assert banned.isdisjoint(set(workflow.__all__))
    for name in banned:
        assert not hasattr(workflow, name)

    assert not hasattr(Pipeline, "builder")
    assert not hasattr(Pipeline, "add_step")
    assert not hasattr(Pipeline, "then")
