from __future__ import annotations

import subprocess
import sys
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
    # Importing a compatibility submodule such as ``arnold.workflow.builder``
    # makes Python attach that module to its parent package.  Validate the
    # public root-import surface in a fresh interpreter so this contract is
    # independent of test collection/import order.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import arnold.workflow as workflow; "
                f"banned = {sorted(banned)!r}; "
                "raise SystemExit(1 if any(hasattr(workflow, name) for name in banned) else 0)"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr

    assert not hasattr(Pipeline, "builder")
    assert not hasattr(Pipeline, "add_step")
    assert not hasattr(Pipeline, "then")
