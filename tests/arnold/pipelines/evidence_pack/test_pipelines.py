"""Construction tests for evidence-pack pipeline shapes (T9).

Validates that both the initial and continuation pipeline shapes are
well-formed and pass :func:`arnold.pipeline.validator.validate`.
"""

from __future__ import annotations

import pytest

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Port,
    PortRef,
    ReadRef,
    Stage,
    StepContext,
    StepResult,
    WriteRef,
)
from arnold.pipelines.evidence_pack.pipelines import (
    build_continuation_pipeline,
    build_initial_pipeline,
)
from arnold.pipelines.evidence_pack.steps import (
    ContentValidatorStep,
    EmitAttestationStep,
    HumanReviewStep,
    IngestStep,
    ReduceStep,
)
from arnold.pipeline.validator import validate, Diagnostics


# ---------------------------------------------------------------------------
# Construction tests — initial pipeline
# ---------------------------------------------------------------------------


class TestInitialPipelineConstruction:
    """Tests for the initial evidence-pack pipeline shape."""

    def test_builds_without_error(self) -> None:
        """PipelineBuilder.build() succeeds for the initial pipeline."""
        pipeline = build_initial_pipeline()
        assert pipeline is not None
        assert pipeline.entry == "ingest"

    def test_all_stages_registered(self) -> None:
        """All 5 stages are present in the initial pipeline."""
        pipeline = build_initial_pipeline()
        stage_names = set(pipeline.stages.keys())
        expected = {"ingest", "content_validators", "reduce", "human_review", "emit_attestation"}
        assert stage_names == expected

    def test_entry_is_ingest(self) -> None:
        """The entry point for the initial pipeline is 'ingest'."""
        pipeline = build_initial_pipeline()
        assert pipeline.entry == "ingest"

    def test_ingest_stage_has_typed_ports(self) -> None:
        """The ingest stage declares typed Port in produces."""
        pipeline = build_initial_pipeline()
        ingest = pipeline.stages["ingest"]
        assert isinstance(ingest, Stage)
        assert len(ingest.produces) >= 1
        assert ingest.produces[0].name == "evidence_pack"

    def test_ingest_stage_has_readref(self) -> None:
        """The ingest stage uses direct ReadRef imports."""
        pipeline = build_initial_pipeline()
        ingest = pipeline.stages["ingest"]
        assert isinstance(ingest, Stage)
        assert len(ingest.reads) >= 1
        assert isinstance(ingest.reads[0], ReadRef)
        assert ingest.reads[0].name == "evidence_pack"

    def test_ingest_stage_has_writeref(self) -> None:
        """The ingest stage uses direct WriteRef imports."""
        pipeline = build_initial_pipeline()
        ingest = pipeline.stages["ingest"]
        assert isinstance(ingest, Stage)
        assert len(ingest.writes) >= 1
        assert isinstance(ingest.writes[0], WriteRef)
        assert ingest.writes[0].name == "evidence_pack"

    def test_validators_is_parallel_stage(self) -> None:
        """The content_validators stage is a ParallelStage (fan-out)."""
        pipeline = build_initial_pipeline()
        validators = pipeline.stages["content_validators"]
        assert isinstance(validators, ParallelStage)

    def test_validators_has_five_steps(self) -> None:
        """The parallel validators stage contains 5 validator steps."""
        pipeline = build_initial_pipeline()
        validators = pipeline.stages["content_validators"]
        assert isinstance(validators, ParallelStage)
        assert len(validators.steps) == 5

    def test_validator_steps_have_distinct_kinds(self) -> None:
        """Each parallel validator has a distinct checkpoint_kind."""
        pipeline = build_initial_pipeline()
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
        """The reduce stage consumes typed PortRef bindings."""
        pipeline = build_initial_pipeline()
        reduce_stage = pipeline.stages["reduce"]
        assert isinstance(reduce_stage, Stage)
        port_names = {ref.port_name for ref in reduce_stage.consumes}
        assert "evidence_pack" in port_names
        assert "checkpoints" in port_names

    def test_human_review_stage_present(self) -> None:
        """The human_review stage exists in the initial pipeline."""
        pipeline = build_initial_pipeline()
        assert "human_review" in pipeline.stages

    def test_emit_attestation_stage_present(self) -> None:
        """The emit_attestation stage exists in the initial pipeline."""
        pipeline = build_initial_pipeline()
        assert "emit_attestation" in pipeline.stages

    def test_validator_validate_passes(self) -> None:
        """The initial pipeline passes validator.validate without defects."""
        pipeline = build_initial_pipeline()
        diag = validate(pipeline)
        assert isinstance(diag, Diagnostics)
        assert diag.defects == [], f"Validator defects: {diag.defects}"


# ---------------------------------------------------------------------------
# Construction tests — continuation pipeline
# ---------------------------------------------------------------------------


class TestContinuationPipelineConstruction:
    """Tests for the continuation evidence-pack pipeline shape."""

    def test_builds_without_error(self) -> None:
        """PipelineBuilder.build() succeeds for the continuation pipeline."""
        pipeline = build_continuation_pipeline()
        assert pipeline is not None

    def test_entry_is_human_review(self) -> None:
        """The continuation pipeline entry is 'human_review'."""
        pipeline = build_continuation_pipeline()
        assert pipeline.entry == "human_review"

    def test_two_stages_registered(self) -> None:
        """The continuation has exactly human_review + emit_attestation."""
        pipeline = build_continuation_pipeline()
        stage_names = set(pipeline.stages.keys())
        expected = {"human_review", "emit_attestation"}
        assert stage_names == expected

    def test_human_review_has_external_readrefs(self) -> None:
        """The human_review stage in continuation uses external ReadRef for inputs."""
        pipeline = build_continuation_pipeline()
        review = pipeline.stages["human_review"]
        assert isinstance(review, Stage)
        read_names = {ref.name for ref in review.reads}
        assert "evidence_pack" in read_names
        assert "verdict" in read_names
        # Both reads are marked external (no upstream producer)
        for ref in review.reads:
            if ref.name in ("evidence_pack", "verdict"):
                assert ref.external, f"ReadRef {ref.name} should be external"
                assert ref.optional, f"ReadRef {ref.name} should be optional"

    def test_human_review_no_typed_consumes(self) -> None:
        """The human_review stage in continuation has no typed PortRef consumes
        (external inputs arrive via ReadRef only)."""
        pipeline = build_continuation_pipeline()
        review = pipeline.stages["human_review"]
        assert isinstance(review, Stage)
        assert len(review.consumes) == 0

    def test_emit_attestation_has_produces(self) -> None:
        """The emit_attestation stage declares typed Port produces."""
        pipeline = build_continuation_pipeline()
        emit = pipeline.stages["emit_attestation"]
        assert isinstance(emit, Stage)
        assert len(emit.produces) >= 1
        assert emit.produces[0].name == "attestation"

    def test_validator_validate_passes(self) -> None:
        """The continuation pipeline passes validator.validate without defects."""
        pipeline = build_continuation_pipeline()
        diag = validate(pipeline)
        assert isinstance(diag, Diagnostics)
        assert diag.defects == [], f"Validator defects: {diag.defects}"


# ---------------------------------------------------------------------------
# Construction tests — shape invariants across both pipelines
# ---------------------------------------------------------------------------


class TestPipelineShapeInvariants:
    """Shape invariants that must hold for both pipeline shapes."""

    def test_both_pipelines_use_pipeline_builder(self) -> None:
        """Both pipelines are built via PipelineBuilder."""
        init = build_initial_pipeline()
        cont = build_continuation_pipeline()
        assert isinstance(init, Pipeline)
        assert isinstance(cont, Pipeline)

    def test_both_pipelines_have_emit_attestation(self) -> None:
        """Both pipelines include emit_attestation as a terminal stage."""
        init = build_initial_pipeline()
        cont = build_continuation_pipeline()
        assert "emit_attestation" in init.stages
        assert "emit_attestation" in cont.stages

    def test_steps_are_concrete_classes(self) -> None:
        """All steps are concrete Step classes from arnold.pipelines.evidence_pack.steps."""
        init = build_initial_pipeline()
        ingest_stage = init.stages["ingest"]
        assert isinstance(ingest_stage, Stage)
        assert isinstance(ingest_stage.step, IngestStep)

        validators_stage = init.stages["content_validators"]
        assert isinstance(validators_stage, ParallelStage)
        for step in validators_stage.steps:
            assert isinstance(step, ContentValidatorStep)

    def test_no_megaplan_imports_in_pipeline_module(self) -> None:
        """The pipelines module does not import from megaplan (model-less design)."""
        import ast
        import inspect
        from arnold.pipelines.evidence_pack import pipelines as pkg

        source = inspect.getsource(pkg)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if node.module and "megaplan" in node.module:
                    module_name = node.module
                    assert False, f"megaplan import found: {module_name}"
