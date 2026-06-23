from __future__ import annotations

import ast
from pathlib import Path
from types import MappingProxyType

import pytest

from arnold.workflow import authoring
from tests.fixtures.workflow_authoring import components


def _provenance(name: str = "plan") -> authoring.ComponentProvenance:
    return authoring.ComponentProvenance(
        module="example.workflow.steps",
        qualname=name,
        export_name=name,
    )


def test_component_contracts_are_typed_compile_time_data() -> None:
    prompt = authoring.PromptComponent(
        id="planning_prompt",
        provenance=_provenance("planning_prompt"),
        template="Plan the work",
        parameters=("brief",),
    )
    policy = authoring.PolicyComponent(
        id="bounded_retry",
        provenance=_provenance("bounded_retry"),
        policy_type="retry",
        config={"max_attempts": 2, "labels": ["retryable"]},
    )
    schema = authoring.SchemaComponent(
        id="plan_output",
        provenance=_provenance("plan_output"),
        schema_type="json-schema",
        schema={"type": "object"},
    )
    subflow = authoring.SubflowComponent(
        id="review_subflow",
        provenance=_provenance("review_subflow"),
        workflow_id="review",
        version="1.0",
    )
    step = authoring.StepComponent(
        id="plan",
        provenance=_provenance(),
        prompt=prompt,
        policy=policy,
        output_schema=schema,
    )

    assert prompt.kind is authoring.ComponentKind.PROMPT
    assert policy.kind is authoring.ComponentKind.POLICY
    assert schema.kind is authoring.ComponentKind.SCHEMA
    assert subflow.kind is authoring.ComponentKind.SUBFLOW
    assert step.kind is authoring.ComponentKind.STEP
    assert policy.config["labels"] == ("retryable",)
    assert isinstance(policy.config, MappingProxyType)
    assert prompt.provenance.ref == "example.workflow.steps:planning_prompt"


def test_step_component_is_callable_shaped_without_executing_runtime() -> None:
    step = authoring.StepComponent(id="plan", provenance=_provenance())

    authored_step = step(id="plan_step", metadata={"source": ["fixture"]})

    assert authored_step == authoring.AuthoredStep(
        id="plan_step",
        component=step,
        metadata={"source": ("fixture",)},
    )
    assert authored_step.metadata["source"] == ("fixture",)
    assert isinstance(authored_step.metadata, MappingProxyType)


def test_workflow_authoring_fixture_components_are_typed_step_exports() -> None:
    assert components.plan.kind is authoring.ComponentKind.STEP
    assert components.execute.kind is authoring.ComponentKind.STEP
    assert components.review.kind is authoring.ComponentKind.STEP
    assert components.plan.provenance.ref == "tests.fixtures.workflow_authoring.components:plan"
    assert components.execute.provenance.ref == "tests.fixtures.workflow_authoring.components:execute"
    assert components.review.provenance.ref == "tests.fixtures.workflow_authoring.components:review"
    assert components.review.prompt is components.review_prompt
    assert components.plan.output_schema is components.plan_output


def test_reserved_intrinsics_are_declared_and_not_executable() -> None:
    assert authoring.GRAMMAR_VERSION == "arnold.workflow.authoring.v1"
    assert authoring.RESERVED_INTRINSIC_NAMES == (
        "workflow",
        "loop",
        "halt",
        "suspend",
        "transition",
    )

    for name in authoring.RESERVED_INTRINSIC_NAMES:
        intrinsic = getattr(authoring, name)
        assert intrinsic == authoring.IntrinsicDeclaration(name)
        with pytest.raises(RuntimeError, match="compile-time workflow intrinsic"):
            intrinsic()


def test_authoring_module_static_import_boundary() -> None:
    source_path = Path(authoring.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = {
        "arnold.execution",
        "arnold.pipeline.native",
        "arnold.pipeline",
        "arnold.runtime",
        "arnold_pipelines",
        "_pipeline",
        "stages",
    }

    assert imports.isdisjoint(forbidden)
