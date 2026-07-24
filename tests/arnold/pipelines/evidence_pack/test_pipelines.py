"""Construction tests for the native-first evidence-pack pipeline."""

from __future__ import annotations

import ast
import inspect

from arnold.pipeline.declaration_lowering import lower_stage_declarations
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.types import (
    ParallelStage,
    Pipeline,
    Port,
    PortRef,
    Stage,
)
from arnold.workflow.validator import Diagnostics, validate
from arnold.pipelines.evidence_pack.pipeline import build_pipeline


EXPECTED_PROJECTED_STAGES = (
    "ingest",
    "content_validators",
    "reduce",
    "human_review",
    "emit_attestation",
)
EXPECTED_VALIDATOR_BRANCHES = (
    "validator_structural_audit",
    "validator_budget_enforcement",
    "validator_suspension_propagation",
    "validator_by_ref_validation",
    "validator_human_review_gate",
)
EXPECTED_UNIQUE_NATIVE_PHASES = (
    "ingest",
    *EXPECTED_VALIDATOR_BRANCHES,
    "reduce",
    "human_review",
    "emit_attestation",
)


def _port_names(ports: tuple[Port, ...]) -> tuple[str, ...]:
    return tuple(port.name for port in ports)


def _port_ref_names(refs: tuple[PortRef, ...]) -> tuple[str, ...]:
    return tuple(ref.port_name for ref in refs)


def _edge_map(stage: Stage | ParallelStage) -> dict[str, str]:
    return {edge.label: edge.target for edge in stage.edges}


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class TestPipelineConstruction:
    """Tests for the public shell and native declaration shape."""

    def test_builds_without_error(self) -> None:
        pipeline = build_pipeline()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.entry == "ingest"

    def test_projected_pipeline_shell_has_public_stage_shape(self) -> None:
        pipeline = build_pipeline()
        assert isinstance(pipeline, Pipeline)
        assert tuple(pipeline.stages) == EXPECTED_PROJECTED_STAGES
        assert pipeline.entry == "ingest"
        assert pipeline.resource_bundles == ()

    def test_projected_pipeline_declares_native_program(self) -> None:
        pipeline = build_pipeline()
        assert isinstance(pipeline.native_program, NativeProgram)
        assert pipeline.native_program.name == "evidence_pack"

    def test_native_program_has_nine_unique_phase_names(self) -> None:
        pipeline = build_pipeline()
        assert pipeline.native_program is not None
        unique_phase_names = sorted(
            {phase.name for phase in pipeline.native_program.phases}
        )
        assert len(unique_phase_names) == 9
        assert unique_phase_names == sorted(EXPECTED_UNIQUE_NATIVE_PHASES)

    def test_validator_fanout_is_declared_natively_and_projected(self) -> None:
        pipeline = build_pipeline()
        assert pipeline.native_program is not None

        assert len(pipeline.native_program.parallel_blocks) == 1
        fanout = pipeline.native_program.parallel_blocks[0]
        assert fanout.name == "content_validators"
        assert fanout.branches == EXPECTED_VALIDATOR_BRANCHES

        validators = pipeline.stages["content_validators"]
        assert isinstance(validators, ParallelStage)
        assert (
            tuple(step.name for step in validators.steps)
            == EXPECTED_VALIDATOR_BRANCHES
        )
        assert all(step.kind == "native_phase" for step in validators.steps)

    def test_projected_stages_declare_stable_ports(self) -> None:
        pipeline = build_pipeline()
        expected_ports = {
            "ingest": (("evidence_pack",), ()),
            "content_validators": (("checkpoints",), ("evidence_pack",)),
            "reduce": (("verdict",), ("evidence_pack", "checkpoints")),
            "human_review": ((), ("evidence_pack", "verdict")),
            "emit_attestation": (("attestation",), ("evidence_pack", "verdict")),
        }
        for name, (produces, consumes) in expected_ports.items():
            stage = pipeline.stages[name]
            assert all(isinstance(port, Port) for port in stage.produces)
            assert all(isinstance(ref, PortRef) for ref in stage.consumes)
            assert _port_names(stage.produces) == produces
            assert _port_ref_names(stage.consumes) == consumes
            lowered = lower_stage_declarations(stage)
            assert lowered.clean_binding is True
            assert lowered.effective_produces == stage.produces
            assert lowered.effective_consumes == stage.consumes

    def test_branch_metadata_is_stable_on_projection_and_native_program(self) -> None:
        pipeline = build_pipeline()
        assert pipeline.native_program is not None

        assert _edge_map(pipeline.stages["ingest"]) == {
            "content_validators": "content_validators"
        }
        assert _edge_map(pipeline.stages["content_validators"]) == {"reduce": "reduce"}
        assert _edge_map(pipeline.stages["reduce"]) == {
            "human_review": "human_review",
        }
        assert _edge_map(pipeline.stages["human_review"]) == {
            "emit_attestation": "emit_attestation",
        }
        assert _edge_map(pipeline.stages["emit_attestation"]) == {}

        # Verify the two expected decisions exist in the native program
        decision_names = {
            instruction.name
            for instruction in pipeline.native_program.instructions
            if instruction.op == "decision"
        }
        assert decision_names == {"verdict_is_fail", "human_review_decision"}

        # Verify decisions carry vocabulary metadata
        decision_vocabs = {
            d.name: d.vocabulary for d in pipeline.native_program.decisions
        }
        assert decision_vocabs == {
            "verdict_is_fail": frozenset({"fail", "pass"}),
            "human_review_decision": frozenset({"emit", "failed"}),
        }

    def test_validator_validate_passes(self) -> None:
        pipeline = build_pipeline()
        diag = validate(pipeline)
        assert isinstance(diag, Diagnostics)
        assert diag.defects == [], f"Validator defects: {diag.defects}"

    def test_projected_steps_are_native_phase_adapters(self) -> None:
        pipeline = build_pipeline()
        for name in ("ingest", "reduce", "human_review", "emit_attestation"):
            stage = pipeline.stages[name]
            assert isinstance(stage, Stage)
            assert stage.step.kind == "native_phase"
            assert stage.step.name == name

    def test_no_graph_era_imports_in_pipeline_module(self) -> None:
        from arnold.pipelines.evidence_pack import pipeline as pkg

        source = inspect.getsource(pkg)
        offenders = sorted(
            module for module in _imported_modules(source) if "megaplan" in module
        )
        assert offenders == []

    def test_no_graph_era_imports_in_native_module(self) -> None:
        # Re-import to get source after any reloads
        from arnold.pipelines.evidence_pack import native as nmod

        source = inspect.getsource(nmod)
        offenders = sorted(
            module for module in _imported_modules(source) if "megaplan" in module
        )
        assert offenders == []

    def test_import_scanner_covers_import_and_importfrom_nodes(self) -> None:
        source = """
import megaplan.direct
from arnold.pipeline import Pipeline
from megaplan.indirect import thing
"""
        assert _imported_modules(source) == {
            "megaplan.direct",
            "arnold.pipeline",
            "megaplan.indirect",
        }
