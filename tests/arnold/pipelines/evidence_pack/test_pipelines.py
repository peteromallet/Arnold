"""Construction tests for the migrated native-first evidence-pack pipeline.

Validates that :func:`build_pipeline` projects a graph with the legacy
five-stage topology and passes :func:`arnold.pipeline.validator.validate`.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from arnold.pipeline.declaration_lowering import lower_stage_declarations
from arnold.pipeline.types import (
    ParallelStage,
    Pipeline,
    Port,
    PortRef,
    Stage,
)
from arnold.pipeline.validator import validate, Diagnostics
from arnold.pipelines.evidence_pack.pipeline import build_pipeline
from arnold.pipelines.evidence_pack.steps import (
    ContentValidatorStep,
    EmitAttestationStep,
    HumanReviewStep,
    IngestStep,
    ReduceStep,
)


class TestPipelineConstruction:
    """Tests for the native-projected evidence-pack pipeline shape."""

    def test_builds_without_error(self) -> None:
        pipeline = build_pipeline()
        assert pipeline is not None
        assert pipeline.entry == "ingest"

    def test_all_stages_registered(self) -> None:
        pipeline = build_pipeline()
        stage_names = set(pipeline.stages.keys())
        expected = {"ingest", "content_validators", "reduce", "human_review", "emit_attestation"}
        assert stage_names == expected

    def test_entry_is_ingest(self) -> None:
        pipeline = build_pipeline()
        assert pipeline.entry == "ingest"

    def test_ingest_stage_has_typed_produce(self) -> None:
        pipeline = build_pipeline()
        ingest = pipeline.stages["ingest"]
        assert isinstance(ingest, Stage)
        assert all(isinstance(port, Port) for port in ingest.produces)
        assert ingest.produces[0].name == "evidence_pack"
        lowered = lower_stage_declarations(ingest)
        assert lowered.effective_produces == ingest.produces
        assert lowered.clean_binding is True

    def test_validators_is_parallel_stage(self) -> None:
        pipeline = build_pipeline()
        validators = pipeline.stages["content_validators"]
        assert isinstance(validators, ParallelStage)

    def test_validators_has_five_steps(self) -> None:
        pipeline = build_pipeline()
        validators = pipeline.stages["content_validators"]
        assert isinstance(validators, ParallelStage)
        assert len(validators.steps) == 5

    def test_validator_steps_have_distinct_kinds(self) -> None:
        pipeline = build_pipeline()
        validators = pipeline.stages["content_validators"]
        assert isinstance(validators, ParallelStage)
        kinds = {s.checkpoint_kind for s in validators.steps}  # type: ignore[union-attr]
        expected = {
            "structural_audit",
            "budget_enforcement",
            "suspension_propagation",
            "by_ref_validation",
            "human_review_gate",
        }
        assert kinds == expected

    def test_reduce_stage_consumes_typed_portrefs(self) -> None:
        pipeline = build_pipeline()
        reduce_stage = pipeline.stages["reduce"]
        assert isinstance(reduce_stage, Stage)
        assert all(isinstance(ref, PortRef) for ref in reduce_stage.consumes)
        port_names = {ref.port_name for ref in reduce_stage.consumes}
        assert "evidence_pack" in port_names
        assert "checkpoints" in port_names
        assert lower_stage_declarations(reduce_stage).clean_binding is True

    def test_internal_crossings_use_typed_consumes_produces(self) -> None:
        pipeline = build_pipeline()
        for name in ("content_validators", "reduce", "human_review", "emit_attestation"):
            stage = pipeline.stages[name]
            assert all(isinstance(ref, PortRef) for ref in stage.consumes)
            if name != "human_review":
                assert all(isinstance(port, Port) for port in stage.produces)
            assert lower_stage_declarations(stage).clean_binding is True

    def test_human_review_stage_present(self) -> None:
        pipeline = build_pipeline()
        assert "human_review" in pipeline.stages

    def test_emit_attestation_stage_present(self) -> None:
        pipeline = build_pipeline()
        assert "emit_attestation" in pipeline.stages

    def test_validator_validate_passes(self) -> None:
        pipeline = build_pipeline()
        diag = validate(pipeline)
        assert isinstance(diag, Diagnostics)
        assert diag.defects == [], f"Validator defects: {diag.defects}"

    def test_steps_are_concrete_classes(self) -> None:
        pipeline = build_pipeline()
        ingest_stage = pipeline.stages["ingest"]
        assert isinstance(ingest_stage, Stage)
        assert isinstance(ingest_stage.step, IngestStep)

        validators_stage = pipeline.stages["content_validators"]
        assert isinstance(validators_stage, ParallelStage)
        for step in validators_stage.steps:
            assert isinstance(step, ContentValidatorStep)

        reduce_stage = pipeline.stages["reduce"]
        assert isinstance(reduce_stage, Stage)
        assert isinstance(reduce_stage.step, ReduceStep)

        human_review_stage = pipeline.stages["human_review"]
        assert isinstance(human_review_stage, Stage)
        assert isinstance(human_review_stage.step, HumanReviewStep)

        emit_stage = pipeline.stages["emit_attestation"]
        assert isinstance(emit_stage, Stage)
        assert isinstance(emit_stage.step, EmitAttestationStep)

    def test_no_megaplan_imports_in_pipeline_module(self) -> None:
        from arnold.pipelines.evidence_pack import pipeline as pkg

        source = inspect.getsource(pkg)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if node.module and "megaplan" in node.module:
                    module_name = node.module
                    assert False, f"megaplan import found: {module_name}"

    def test_native_program_attached(self) -> None:
        pipeline = build_pipeline()
        assert pipeline.native_program is not None
        assert pipeline.native_program.name == "evidence_pack"
