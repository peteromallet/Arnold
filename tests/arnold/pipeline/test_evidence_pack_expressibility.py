from __future__ import annotations

from arnold.pipeline.native import get_decision_meta
from arnold.pipeline.native.ir import NativeDecision, NativeInstruction, NativeProgram
from arnold.pipeline.types import ParallelStage, Pipeline, Port, PortRef
from arnold.pipelines.evidence_pack import native as native_module
from arnold.pipelines.evidence_pack.native import build_native_program
from arnold.pipelines.evidence_pack.pipeline import build_pipeline


def test_evidence_pack_pipeline_uses_core_pipeline_primitives() -> None:
    pipeline = build_pipeline()

    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)

    validators = pipeline.stages["content_validators"]
    assert isinstance(validators, ParallelStage)
    assert validators.name == "content_validators"
    assert tuple(step.name for step in validators.steps) == (
        "validator_structural_audit",
        "validator_budget_enforcement",
        "validator_suspension_propagation",
        "validator_by_ref_validation",
        "validator_human_review_gate",
    )

    for stage in pipeline.stages.values():
        assert all(isinstance(port, Port) for port in stage.produces)
        assert all(isinstance(ref, PortRef) for ref in stage.consumes)


def test_evidence_pack_native_program_exposes_decision_and_route_vocabulary() -> None:
    program = build_native_program()

    assert isinstance(program, NativeProgram)
    assert program.name == "evidence_pack"
    assert tuple(block.name for block in program.parallel_blocks) == (
        "content_validators",
    )

    decisions = {decision.name: decision for decision in program.decisions}
    assert set(decisions) == {"verdict_is_fail", "human_review_decision"}

    verdict = decisions["verdict_is_fail"]
    human_review = decisions["human_review_decision"]
    assert isinstance(verdict, NativeDecision)
    assert verdict.vocabulary == frozenset({"fail", "pass"})
    assert isinstance(human_review, NativeDecision)
    assert human_review.vocabulary == frozenset({"emit", "failed"})
    decision_meta = get_decision_meta(native_module.human_review_decision)
    assert decision_meta is not None
    assert decision_meta["human_gate"] is True
    assert decision_meta["artifact_stage"] == "human_review"
    assert decision_meta["choices"] == ("emit", "failed")
    assert decision_meta["override_routes"] == {
        "emit": "emit_attestation",
        "failed": None,
    }
    assert set(decision_meta["resume_input_schema"]["required"]) == {"choice"}

    instructions = {
        instruction.name: instruction
        for instruction in program.instructions
        if instruction.op == "decision"
    }
    assert isinstance(instructions["verdict_is_fail"], NativeInstruction)
    assert instructions["verdict_is_fail"].decision_vocabulary == frozenset(
        {"fail", "pass"}
    )
    assert set(instructions["verdict_is_fail"].branches) == {"fail", "pass"}
    assert instructions["human_review_decision"].decision_vocabulary == frozenset(
        {"emit", "failed"}
    )
    assert set(instructions["human_review_decision"].branches) == {
        "emit",
        "failed",
    }
