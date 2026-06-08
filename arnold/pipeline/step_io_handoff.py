"""Typed step-IO handoff helper.

This module is the small orchestration layer between M1's artifact contract
classifier, policy resolver, seam resolver, and telemetry writer. It adds only
the M2 port-pair checks that require resolved producer/consumer metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.schema_registry import AcceptedVersionRange, SchemaRegistryError
from arnold.pipeline.step_io_contract import (
    StepIOClassification,
    StepIOContractContext,
    StepIOContractDecision,
    StepIODiagnostic,
    StepIOEnvelope,
    StepIOOperation,
    decide_step_io_read,
    decide_step_io_write,
)
from arnold.pipeline.step_io_policy import (
    StepIOPolicy,
    decision_blocks_read,
    decision_blocks_write,
    resolve_step_io_policy,
)
from arnold.pipeline.runtime_contract_diagnostics import (
    RuntimeContractDiagnostic,
    diagnostic_from_step_io,
)
from arnold.pipeline.step_io_seams import SeamResolution, resolve_seam_from_binding_map
from arnold.pipeline.step_io_telemetry import StepIOViolationRecord, emit_decision_telemetry


@dataclass(frozen=True)
class StepIOHandoffResult:
    """Effective result for one read or write across a step-IO seam."""

    decision: StepIOContractDecision
    policy: StepIOPolicy
    seam: SeamResolution
    allow_read: bool
    allow_write: bool
    telemetry_record: StepIOViolationRecord | None = None
    author_diagnostic: RuntimeContractDiagnostic | None = None

    @property
    def blocks_read(self) -> bool:
        return not self.allow_read

    @property
    def blocks_write(self) -> bool:
        return not self.allow_write


def evaluate_step_io_handoff(
    value: Any,
    *,
    operation: StepIOOperation | str,
    context: StepIOContractContext | None = None,
    pipeline: Any = None,
    pipeline_id: str = "pipeline",
    consumer_step: str = "",
    consumer_port: str = "",
    seam: SeamResolution | None = None,
    producer_port: Any = None,
    consumer_port_decl: Any = None,
    configured_mode: Any = None,
    plan_dir: str | Path | None = None,
    state_config: Mapping[str, Any] | None = None,
    artifact: str = "step_io",
    telemetry_path: str | Path | None = None,
    producer_stage: str = "",
) -> StepIOHandoffResult:
    """Evaluate a typed artifact handoff without falling back to guessed ports.

    Validation and accepted-version checks run only when a binding resolves and
    both sides have typed declarations. Mixed, untyped, and unresolved seams
    pass through under the resolved M1 policy.
    """

    op = StepIOOperation(operation)
    seam = seam or _resolve_seam(
        pipeline=pipeline,
        pipeline_id=pipeline_id,
        consumer_step=consumer_step,
        consumer_port=consumer_port,
    )
    envelope = StepIOEnvelope.from_json(value) if isinstance(value, Mapping) else None
    policy = resolve_step_io_policy(
        configured_mode=configured_mode,
        plan_dir=plan_dir,
        state_config=state_config,
        binding=seam,
        producer_typed=seam.producer_typed,
        consumer_typed=seam.consumer_typed,
    )

    if envelope is not None and not seam.binding_found:
        decision = _binding_unavailable_decision(value=value, envelope=envelope, reason=seam.reason)
    elif not seam.both_sides_typed:
        decision = StepIOContractDecision(
            classification=StepIOClassification.LEGACY_UNKNOWN,
            allow_read=True,
            allow_write=True,
            value=value,
            envelope=envelope,
        )
    else:
        decision = _decide_typed_handoff(
            value=value,
            operation=op,
            context=context,
            producer_port=producer_port,
            consumer_port=consumer_port_decl,
        )

    allow_read = not decision_blocks_read(decision, policy)
    allow_write = not decision_blocks_write(decision, policy)
    record = None
    if telemetry_path is not None:
        record = emit_decision_telemetry(
            decision=decision,
            policy=policy,
            artifact=artifact,
            operation=op.value,
            telemetry_path=telemetry_path,
            seam=str(seam.seam_id) if seam.seam_id is not None else "step_io",
            envelope=envelope,
        )
    author_diagnostic = diagnostic_from_step_io(
        decision=decision,
        producer_stage=producer_stage,
        consumer_stage=consumer_step,
        seam_id=str(seam.seam_id) if seam.seam_id is not None else None,
        producer_port=producer_port,
        consumer_port=consumer_port_decl,
    )
    return StepIOHandoffResult(
        decision=decision,
        policy=policy,
        seam=seam,
        allow_read=allow_read,
        allow_write=allow_write,
        telemetry_record=record,
        author_diagnostic=author_diagnostic,
    )


def _resolve_seam(
    *,
    pipeline: Any,
    pipeline_id: str,
    consumer_step: str,
    consumer_port: str,
) -> SeamResolution:
    if pipeline is None or not consumer_step or not consumer_port:
        return SeamResolution(
            seam_id=None,
            producer_typed=False,
            consumer_typed=False,
            both_sides_typed=False,
            binding_found=False,
            reason="binding lookup unavailable",
        )
    return resolve_seam_from_binding_map(
        pipeline,
        pipeline_id=pipeline_id,
        consumer_step=consumer_step,
        consumer_port=consumer_port,
    )


def _decide_typed_handoff(
    *,
    value: Any,
    operation: StepIOOperation,
    context: StepIOContractContext | None,
    producer_port: Any,
    consumer_port: Any,
) -> StepIOContractDecision:
    reserved = _reserved_stream_decision(value, producer_port=producer_port, consumer_port=consumer_port)
    if reserved is not None:
        return reserved

    decision = (
        decide_step_io_read(value, context)
        if operation is StepIOOperation.READ
        else decide_step_io_write(value, context)
    )
    if decision.envelope is None or decision.classification is not StepIOClassification.TYPED_VALID:
        return decision
    return _check_accepted_range(decision, context=context, consumer_port=consumer_port)


def _check_accepted_range(
    decision: StepIOContractDecision,
    *,
    context: StepIOContractContext | None,
    consumer_port: Any,
) -> StepIOContractDecision:
    accepted_range = getattr(consumer_port, "accepted_version_range", None)
    if accepted_range is None:
        return decision
    if not isinstance(accepted_range, AcceptedVersionRange):
        return _invalid_metadata_decision(
            decision,
            code="invalid_accepted_version_range",
            message="consumer accepted_version_range must be an AcceptedVersionRange",
        )
    envelope = decision.envelope
    if envelope is None:
        return decision
    if accepted_range.logical_type != envelope.logical_type:
        return _invalid_metadata_decision(
            decision,
            code="logical_type_mismatch",
            message="consumer accepted_version_range logical_type does not match artifact logical_type",
        )

    registry = context.resolve_registry() if context is not None else None
    if registry is None:
        return _schema_unavailable_from_decision(decision, "typed artifact schema is unavailable")
    try:
        accepted = registry.accepts_version(envelope.logical_type, envelope.schema_version, accepted_range)
    except SchemaRegistryError as exc:
        return _schema_unavailable_from_decision(decision, str(exc))
    if accepted:
        return decision
    return _invalid_metadata_decision(
        decision,
        code="schema_version_not_accepted",
        message="typed artifact schema_version is outside the consumer accepted_version_range",
    )


def _reserved_stream_decision(
    value: Any,
    *,
    producer_port: Any,
    consumer_port: Any,
) -> StepIOContractDecision | None:
    for role, port in (("producer", producer_port), ("consumer", consumer_port)):
        if getattr(port, "cardinality", None) == "stream":
            envelope = StepIOEnvelope.from_json(value) if isinstance(value, Mapping) else None
            return StepIOContractDecision(
                classification=StepIOClassification.TYPED_INVALID,
                allow_read=False,
                allow_write=False,
                value=envelope.payload if envelope is not None else value,
                envelope=envelope,
                diagnostics=(
                    StepIODiagnostic(
                        code="reserved_stream_cardinality",
                        message=f"{role} port uses reserved stream cardinality",
                    ),
                ),
                block_reason="reserved stream cardinality is not supported at runtime",
            )
    return None


def _binding_unavailable_decision(
    *,
    value: Any,
    envelope: StepIOEnvelope,
    reason: str,
) -> StepIOContractDecision:
    return StepIOContractDecision(
        classification=StepIOClassification.BINDING_UNAVAILABLE,
        allow_read=True,
        allow_write=True,
        value=value,
        envelope=envelope,
        diagnostics=(
            StepIODiagnostic(
                code="binding_unavailable",
                message=reason or "binding lookup unavailable",
            ),
        ),
        block_reason=reason or "binding lookup unavailable",
    )


def _invalid_metadata_decision(
    decision: StepIOContractDecision,
    *,
    code: str,
    message: str,
) -> StepIOContractDecision:
    return StepIOContractDecision(
        classification=StepIOClassification.TYPED_INVALID,
        allow_read=decision.allow_read,
        allow_write=False,
        value=decision.value,
        envelope=decision.envelope,
        diagnostics=decision.diagnostics + (StepIODiagnostic(code=code, message=message),),
        block_reason=message,
    )


def _schema_unavailable_from_decision(
    decision: StepIOContractDecision,
    message: str,
) -> StepIOContractDecision:
    return StepIOContractDecision(
        classification=StepIOClassification.SCHEMA_UNAVAILABLE,
        allow_read=True,
        allow_write=False,
        value=decision.value,
        envelope=decision.envelope,
        diagnostics=decision.diagnostics
        + (StepIODiagnostic(code="schema_unavailable", message=message),),
        block_reason=message,
    )
