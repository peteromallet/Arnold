"""Native runtime entrypoints for ``arnold_pipelines.evidence_pack``."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline import Port, PortRef, StepContext, StepResult
from arnold.pipeline.native import compile_pipeline, decision, parallel, phase, pipeline
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.types import ContractStatus

from arnold_pipelines.evidence_pack.steps import (
    ContentValidatorStep,
    EmitAttestationStep,
    HumanReviewStep,
    IngestStep,
    ReduceStep,
)
from arnold_pipelines.evidence_pack.verifier import (
    CHECKPOINT_STATUS_FAILED,
    CHECKPOINT_STATUS_PASSED,
    VALIDATOR_KIND_BUDGET_ENFORCEMENT,
    VALIDATOR_KIND_BY_REF_VALIDATION,
    VALIDATOR_KIND_HUMAN_REVIEW_GATE,
    VALIDATOR_KIND_STRUCTURAL_AUDIT,
    VALIDATOR_KIND_SUSPENSION_PROPAGATION,
    VERDICT_FAIL,
    read_json_artifact,
)


def _ctx_from_native(raw_ctx: object) -> StepContext:
    if isinstance(raw_ctx, dict):
        raw_state = raw_ctx.get("state", {})
        state = dict(raw_state) if isinstance(raw_state, Mapping) else {}
        raw_inputs = raw_ctx.get("inputs", state)
        inputs = dict(raw_inputs) if isinstance(raw_inputs, Mapping) else {}
        return StepContext(
            artifact_root=str(raw_ctx.get("artifact_root", ".")),
            state=state,
            inputs=inputs,
            mode=str(raw_ctx.get("mode", state.get("mode", "default"))),
        )

    artifact_root = getattr(raw_ctx, "artifact_root", ".")
    raw_state = getattr(raw_ctx, "state", {}) or {}
    raw_inputs = getattr(raw_ctx, "inputs", raw_state) or {}
    return StepContext(
        artifact_root=str(artifact_root),
        state=dict(raw_state) if isinstance(raw_state, Mapping) else {},
        inputs=dict(raw_inputs) if isinstance(raw_inputs, Mapping) else {},
        mode=str(getattr(raw_ctx, "mode", "default")),
    )


def _json_safe_step_result(result: StepResult) -> StepResult:
    outputs = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in result.outputs.items()
    }
    contract_result = result.contract_result
    if contract_result is not None and contract_result.status is not ContractStatus.SUSPENDED:
        contract_result = None
    return replace(result, outputs=outputs, contract_result=contract_result)


def _run_validator(raw_ctx: object, *, phase_name: str, checkpoint_kind: str) -> StepResult:
    return _json_safe_step_result(
        ContentValidatorStep(name=phase_name, checkpoint_kind=checkpoint_kind).run(
            _ctx_from_native(raw_ctx)
        )
    )


def _native_human_review_resume_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "choice": {
                "type": "string",
                "enum": ["emit", "failed"],
            }
        },
        "required": ["choice"],
    }


def _human_review_checkpoint(raw_ctx: object) -> dict[str, Any] | None:
    state = _ctx_from_native(raw_ctx).inputs
    for value in state.values():
        if not isinstance(value, (str, Path)):
            continue
        path = Path(value)
        if not path.exists() or not path.name.startswith("checkpoint_"):
            continue
        try:
            payload = read_json_artifact(path)
        except ValueError:
            continue
        if payload.get("checkpoint_kind") == VALIDATOR_KIND_HUMAN_REVIEW_GATE:
            return payload
    return None


def _join_validators(
    results: list[StepResult | Mapping[str, Any] | Any],
    ctx: StepContext | None = None,
) -> StepResult:
    _ = ctx
    merged: dict[str, Any] = {}
    checkpoint_paths: list[str] = []

    for result in results:
        if isinstance(result, StepResult):
            merged.update(result.outputs)
            checkpoint_paths.extend(
                str(value)
                for value in result.outputs.values()
                if isinstance(value, (str, Path))
            )
        elif isinstance(result, Mapping):
            merged.update({str(key): value for key, value in result.items()})

    if checkpoint_paths:
        merged["checkpoints"] = tuple(checkpoint_paths)

    return StepResult(
        outputs=merged,
        next="reduce",
    )


@phase(
    name="ingest",
    produces=(Port("evidence_pack", "application/json"),),
)
def ingest(ctx: object) -> StepResult:
    return _json_safe_step_result(IngestStep().run(_ctx_from_native(ctx)))


@phase(
    name="validator_structural_audit",
    consumes=(PortRef("evidence_pack", "application/json"),),
    produces=(Port("checkpoints", "application/json", cardinality="collection"),),
)
def validator_structural_audit(ctx: object) -> StepResult:
    return _run_validator(
        ctx,
        phase_name="validator_structural_audit",
        checkpoint_kind=VALIDATOR_KIND_STRUCTURAL_AUDIT,
    )


@phase(
    name="validator_budget_enforcement",
    consumes=(PortRef("evidence_pack", "application/json"),),
    produces=(Port("checkpoints", "application/json", cardinality="collection"),),
)
def validator_budget_enforcement(ctx: object) -> StepResult:
    return _run_validator(
        ctx,
        phase_name="validator_budget_enforcement",
        checkpoint_kind=VALIDATOR_KIND_BUDGET_ENFORCEMENT,
    )


@phase(
    name="validator_suspension_propagation",
    consumes=(PortRef("evidence_pack", "application/json"),),
    produces=(Port("checkpoints", "application/json", cardinality="collection"),),
)
def validator_suspension_propagation(ctx: object) -> StepResult:
    return _run_validator(
        ctx,
        phase_name="validator_suspension_propagation",
        checkpoint_kind=VALIDATOR_KIND_SUSPENSION_PROPAGATION,
    )


@phase(
    name="validator_by_ref_validation",
    consumes=(PortRef("evidence_pack", "application/json"),),
    produces=(Port("checkpoints", "application/json", cardinality="collection"),),
)
def validator_by_ref_validation(ctx: object) -> StepResult:
    return _run_validator(
        ctx,
        phase_name="validator_by_ref_validation",
        checkpoint_kind=VALIDATOR_KIND_BY_REF_VALIDATION,
    )


@phase(
    name="validator_human_review_gate",
    consumes=(PortRef("evidence_pack", "application/json"),),
    produces=(Port("checkpoints", "application/json", cardinality="collection"),),
)
def validator_human_review_gate(ctx: object) -> StepResult:
    return _run_validator(
        ctx,
        phase_name="validator_human_review_gate",
        checkpoint_kind=VALIDATOR_KIND_HUMAN_REVIEW_GATE,
    )


@phase(
    name="reduce",
    consumes=(
        PortRef("evidence_pack", "application/json"),
        PortRef("checkpoints", "application/json", cardinality="collection"),
    ),
    produces=(Port("verdict", "application/json"),),
)
def reduce(ctx: object) -> StepResult:
    return _json_safe_step_result(ReduceStep().run(_ctx_from_native(ctx)))


@phase(
    name="human_review",
    consumes=(
        PortRef("evidence_pack", "application/json"),
        PortRef("verdict", "application/json"),
    ),
)
def human_review(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    inputs = dict(step_ctx.inputs)
    inputs.pop("human_input", None)
    result = HumanReviewStep().run(replace(step_ctx, inputs=inputs))
    if result.contract_result is not None and result.contract_result.status is ContractStatus.SUSPENDED:
        return replace(
            _json_safe_step_result(result),
            next="awaiting_decision",
            contract_result=None,
        )
    return _json_safe_step_result(result)


@phase(
    name="emit_attestation",
    consumes=(
        PortRef("evidence_pack", "application/json"),
        PortRef("verdict", "application/json"),
    ),
    produces=(Port("attestation", "application/json"),),
)
def emit_attestation(ctx: object) -> StepResult:
    return _json_safe_step_result(EmitAttestationStep().run(_ctx_from_native(ctx)))


@decision(
    name="verdict_is_fail",
    vocabulary=frozenset({"fail", "pass"}),
)
def verdict_is_fail(ctx: object) -> str:
    verdict_path = _ctx_from_native(ctx).inputs.get("verdict")
    if not isinstance(verdict_path, (str, Path)):
        return "fail"
    try:
        verdict_payload = read_json_artifact(verdict_path)
    except ValueError:
        return "fail"
    return "fail" if verdict_payload.get("verdict") == VERDICT_FAIL else "pass"


@decision(
    name="human_review_decision",
    vocabulary=frozenset({"emit", "failed"}),
    human_gate=True,
    artifact_stage="human_review",
    choices=("emit", "failed"),
    resume_input_schema=_native_human_review_resume_schema(),
    override_routes={"emit": "emit_attestation", "failed": None},
)
def human_review_decision(ctx: object) -> str:
    inputs = _ctx_from_native(ctx).inputs
    human_input = inputs.get("human_input")
    if isinstance(human_input, Mapping):
        choice = human_input.get("choice")
        if isinstance(choice, str) and choice in {"emit", "failed"}:
            return choice
        approved = human_input.get("approved")
        if isinstance(approved, bool):
            return "emit" if approved else "failed"

    checkpoint = _human_review_checkpoint(ctx)
    if checkpoint is not None:
        status = checkpoint.get("status")
        if status == CHECKPOINT_STATUS_PASSED:
            return "emit"
        if status == CHECKPOINT_STATUS_FAILED:
            return "failed"
    return "failed"


@pipeline(name="evidence_pack", description="Native evidence-pack verification pipeline")
def evidence_pack_native(ctx: object) -> Any:
    """Compile-time topology for native evidence-pack verification."""
    state = yield ingest(ctx)
    for validator in parallel(
        [
            validator_structural_audit,
            validator_budget_enforcement,
            validator_suspension_propagation,
            validator_by_ref_validation,
            validator_human_review_gate,
        ],
        reducer=_join_validators,
        name="content_validators",
    ):
        state = yield validator(ctx)

    state = yield reduce(ctx)
    if verdict_is_fail(ctx) == "fail":
        state = yield human_review(ctx)
        if human_review_decision(ctx) == "emit":
            state = yield emit_attestation(ctx)
        else:
            return state
    else:
        state = yield emit_attestation(ctx)
    return state


def build_native_program() -> NativeProgram:
    """Compile and return the native program for evidence-pack verification."""
    return compile_pipeline(evidence_pack_native)


__all__ = [
    "build_native_program",
    "emit_attestation",
    "evidence_pack_native",
    "human_review",
    "human_review_decision",
    "ingest",
    "reduce",
    "validator_budget_enforcement",
    "validator_by_ref_validation",
    "validator_human_review_gate",
    "validator_structural_audit",
    "validator_suspension_propagation",
    "verdict_is_fail",
]
