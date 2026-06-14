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
from arnold.pipeline.declaration_lowering import lower_stage_declarations
from arnold.pipeline.step_invocation import StepInvocation, StepInvocationAdapterRegistry
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


class _NoopToolAdapter:
    def invoke(self, invocation: StepInvocation) -> object:  # pragma: no cover
        raise AssertionError("validation must resolve adapters without invoking them")


def _registry_with_tool_adapter() -> StepInvocationAdapterRegistry:
    registry = StepInvocationAdapterRegistry()
    registry.register("tool", _NoopToolAdapter())
    return registry


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

    def test_ingest_stage_has_typed_write_and_external_readref(self) -> None:
        """The ingest stage preserves external input while writing a typed port."""
        pipeline = build_initial_pipeline()
        ingest = pipeline.stages["ingest"]
        assert isinstance(ingest, Stage)
        assert isinstance(ingest.reads[0], ReadRef)
        assert ingest.reads[0].name == "evidence_pack"
        assert ingest.reads[0].external is True
        assert isinstance(ingest.writes[0], Port)
        assert ingest.writes[0].name == "evidence_pack"
        lowered = lower_stage_declarations(ingest)
        assert lowered.legacy_reads == ingest.reads
        assert lowered.effective_produces == ingest.produces
        assert lowered.clean_binding is True

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
        """The reduce stage authors internal inputs through typed reads."""
        pipeline = build_initial_pipeline()
        reduce_stage = pipeline.stages["reduce"]
        assert isinstance(reduce_stage, Stage)
        assert all(isinstance(ref, PortRef) for ref in reduce_stage.reads)
        port_names = {ref.port_name for ref in reduce_stage.reads}
        assert "evidence_pack" in port_names
        assert "checkpoints" in port_names
        assert lower_stage_declarations(reduce_stage).clean_binding is True

    def test_internal_crossings_use_typed_reads_writes(self) -> None:
        """Cleanly lowerable internal crossings are authored through reads/writes."""
        pipeline = build_initial_pipeline()
        for name in ("content_validators", "reduce", "human_review", "emit_attestation"):
            stage = pipeline.stages[name]
            assert all(isinstance(ref, PortRef) for ref in stage.reads)
            if name != "human_review":
                assert all(isinstance(port, Port) for port in stage.writes)
            assert lower_stage_declarations(stage).clean_binding is True

    def test_initial_pipeline_derives_binding_map(self) -> None:
        pipeline = build_initial_pipeline()
        assert pipeline.binding_map
        assert pipeline.binding_map[("content_validators", "evidence_pack")] == (
            "ingest",
            "evidence_pack",
        )
        assert pipeline.binding_map[("reduce", "checkpoints")] == (
            "content_validators",
            "checkpoints",
        )

    def test_human_review_stage_present(self) -> None:
        """The human_review stage exists in the initial pipeline."""
        pipeline = build_initial_pipeline()
        assert "human_review" in pipeline.stages

    def test_emit_attestation_stage_present(self) -> None:
        """The emit_attestation stage exists in the initial pipeline."""
        pipeline = build_initial_pipeline()
        assert "emit_attestation" in pipeline.stages

    def test_validator_validate_passes(self) -> None:
        """The initial pipeline validates when its tool adapter kind is registered."""
        pipeline = build_initial_pipeline()
        diag = validate(pipeline, adapter_registry=_registry_with_tool_adapter())
        assert isinstance(diag, Diagnostics)
        assert diag.defects == [], f"Validator defects: {diag.defects}"

    def test_invocation_examples_include_model_and_tool_shapes(self) -> None:
        """Evidence-pack metadata demonstrates model and future tool invocation shapes."""
        pipeline = build_initial_pipeline()
        validators = pipeline.stages["content_validators"]
        reduce_stage = pipeline.stages["reduce"]

        assert validators.invocation is not None
        assert validators.invocation.kind == "tool"
        assert validators.invocation.metadata["adapter_config"] == {
            "tool": "evidence-pack-checkpoint-validator",
            "mode": "local-deterministic",
        }
        assert reduce_stage.invocation is not None
        assert reduce_stage.invocation.kind == "model"
        assert reduce_stage.invocation.metadata["adapter_config"] == {
            "model": "evidence-pack-verdict-summarizer",
            "mode": "metadata-only",
        }
        assert isinstance(validators, ParallelStage)
        assert all(isinstance(step, ContentValidatorStep) for step in validators.steps)

    def test_unregistered_tool_invocation_fails_closed(self) -> None:
        """Default validation resolves invocation kinds and rejects unknown tool adapters."""
        pipeline = build_initial_pipeline()
        diag = validate(pipeline)
        assert any(
            issue.code == "invocation.unknown_adapter"
            and issue.stage == "content_validators"
            and issue.details["invocation_kind"] == "tool"
            for issue in diag.issues
        )


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
        assert lower_stage_declarations(review).effective_consumes == ()

    def test_emit_attestation_has_produces(self) -> None:
        """The emit_attestation stage declares typed Port writes."""
        pipeline = build_continuation_pipeline()
        emit = pipeline.stages["emit_attestation"]
        assert isinstance(emit, Stage)
        assert isinstance(emit.writes[0], Port)
        assert emit.writes[0].name == "attestation"

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
