from __future__ import annotations

from pathlib import Path

import pytest

import arnold.workflow as workflow
from arnold.workflow import authoring
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.source_compiler import SourceCompileError


def _module_level_hook() -> None:
    return None


def test_dsl_and_authoring_components_share_ref_validation() -> None:
    with pytest.raises(ValueError, match="invalid ref format"):
        workflow.Step(id="bad/id", kind="agent")

    with pytest.raises(ValueError, match="invalid ref format"):
        authoring.StepComponent(
            id="bad/id",
            provenance=authoring.ComponentProvenance(
                module="tests.fixtures.workflow_authoring.components",
                qualname="plan",
            ),
        )


def test_source_compiler_reports_ref_validation_before_lowering() -> None:
    source = """
from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import plan

workflow(id="invalid-step-ref", steps=[plan(id="bad/id")])
"""

    result = workflow.check_workflow_source(source, source_path="invalid_step_ref.py")

    assert [diagnostic.message for diagnostic in result.diagnostics] == [
        "component call id must use the workflow ref alphabet"
    ]
    assert result.diagnostics[0].details == {"value": "bad/id"}
    with pytest.raises(SourceCompileError) as exc_info:
        workflow.lower_workflow_source(source, source_path="invalid_step_ref.py")
    assert tuple(exc_info.value.diagnostics) == result.diagnostics


def test_subflow_ref_diagnostics_match_manifest_validation_rules() -> None:
    source = """
from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import review_subflow

workflow(
    id="invalid-subflow-ref",
    steps=[
        review_subflow(
            id="review",
            manifest_hash="nested-review:1.0",
            alias="bad alias",
        )
    ],
)
"""

    result = workflow.check_workflow_source(source, source_path="invalid_subflow_ref.py")

    assert [diagnostic.message for diagnostic in result.diagnostics] == [
        "subflow manifest_hash must be a literal or resolver-provided identity",
        "subflow alias must use the workflow ref alphabet",
    ]


def test_hook_identity_reexports_are_the_same_ref_contract() -> None:
    manifest_ref = workflow.ImportRef.from_callable(_module_level_hook)
    hook_ref = workflow.HookRef.from_callable(_module_level_hook)

    assert hook_ref.spec == manifest_ref.spec
    assert hook_ref.key == f"hook:{manifest_ref.spec}"
    assert workflow.HookRef.parse(str(hook_ref)).resolve() is _module_level_hook


def test_source_compiler_manifest_output_matches_explicit_dsl_compiler() -> None:
    source_path = Path("tests/fixtures/workflow_authoring/valid_direct_linear.py")
    source = source_path.read_text(encoding="utf-8")

    pipeline = workflow.lower_workflow_source(source, source_path=source_path)
    from_source = workflow.compile_workflow_source(source, source_path=source_path)
    from_dsl = compile_pipeline(pipeline)

    assert from_source.to_json() == from_dsl.to_json()
