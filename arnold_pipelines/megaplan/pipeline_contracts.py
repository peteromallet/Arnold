"""Production typed-port contract catalog for the Megaplan planning pipeline."""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.contract_validation import ValidationDiagnostic, validate_payload_against_schema
from arnold.pipeline.schema_registry import (
    AcceptedVersionRange,
    ContractSchemaRegistry,
    schema_version_for,
)
from arnold.pipeline.step_io_contract import StepIOEnvelope
from arnold.pipeline.types import ContractResult, Port, PortRef


CONTENT_TYPE_JSON = "application/json"

LOGICAL_PREP_PAYLOAD = "megaplan.planning.prep_payload"
LOGICAL_PLAN_PAYLOAD = "megaplan.planning.plan_payload"
LOGICAL_CRITIQUE_PAYLOAD = "megaplan.planning.critique_payload"
LOGICAL_GATE_PAYLOAD = "megaplan.planning.gate_payload"
LOGICAL_REVISE_PAYLOAD = "megaplan.planning.revise_payload"
LOGICAL_FINALIZE_PAYLOAD = "megaplan.planning.finalize_payload"
LOGICAL_EXECUTE_PAYLOAD = "megaplan.planning.execute_payload"
LOGICAL_REVIEW_PAYLOAD = "megaplan.planning.review_payload"
LOGICAL_TIEBREAKER_PAYLOAD = "megaplan.planning.tiebreaker_payload"

PRODUCTION_PLANNING_LOGICAL_TYPES: tuple[str, ...] = (
    LOGICAL_PREP_PAYLOAD,
    LOGICAL_PLAN_PAYLOAD,
    LOGICAL_CRITIQUE_PAYLOAD,
    LOGICAL_GATE_PAYLOAD,
    LOGICAL_REVISE_PAYLOAD,
    LOGICAL_FINALIZE_PAYLOAD,
    LOGICAL_EXECUTE_PAYLOAD,
    LOGICAL_REVIEW_PAYLOAD,
    LOGICAL_TIEBREAKER_PAYLOAD,
)

_ARTIFACT_REF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["uri", "content_type"],
    "properties": {
        "uri": {"type": "string"},
        "content_type": {"type": "string"},
        "digest": {"type": ["string", "null"]},
        "size_bytes": {"type": ["integer", "null"]},
        "name": {"type": ["string", "null"]},
    },
    "additionalProperties": False,
}


def _by_reference_schema(logical_type: str) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["logical_type", "artifact_refs"],
        "properties": {
            "logical_type": {"const": logical_type},
            "artifact_refs": {
                "type": "array",
                "items": _ARTIFACT_REF_SCHEMA,
            },
            "summary": {"type": "string"},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


PRODUCTION_PLANNING_SCHEMAS: dict[str, dict[str, Any]] = {
    logical_type: _by_reference_schema(logical_type)
    for logical_type in PRODUCTION_PLANNING_LOGICAL_TYPES
}


@dataclass(frozen=True)
class PlanningPayloadContract:
    """Registered schema and helper metadata for one planning payload."""

    logical_type: str
    schema_version: str
    accepted_range: AcceptedVersionRange
    schema: Mapping[str, Any]

    def producer_port(self, name: str = "result") -> Port:
        return produce_port(name, self)

    def consumer_port(self, name: str = "result") -> PortRef:
        return consume_port(name, self)


class PlanningPayloadBuildError(ValueError):
    """Raised when a declared producer port cannot emit a typed payload."""


def production_planning_contracts() -> dict[str, PlanningPayloadContract]:
    """Return the pure contract metadata for production planning payloads.

    Unlike :func:`register_production_planning_contracts`, this helper is side
    effect free and does not persist anything to disk. It is appropriate for
    stage declaration wiring, where we need stable logical metadata without a
    runtime registry write.
    """

    contracts: dict[str, PlanningPayloadContract] = {}
    for logical_type in PRODUCTION_PLANNING_LOGICAL_TYPES:
        schema = PRODUCTION_PLANNING_SCHEMAS[logical_type]
        version = schema_version_for(schema)
        accepted_range = AcceptedVersionRange(
            logical_type=logical_type,
            min_version=version,
            max_version=version,
        )
        contracts[logical_type] = PlanningPayloadContract(
            logical_type=logical_type,
            schema_version=version,
            accepted_range=accepted_range,
            schema=schema,
        )
    return contracts


def register_production_planning_contracts(
    registry: ContractSchemaRegistry,
) -> dict[str, PlanningPayloadContract]:
    """Register all production planning payload schemas and return their contracts."""

    contracts: dict[str, PlanningPayloadContract] = {}
    for logical_type in PRODUCTION_PLANNING_LOGICAL_TYPES:
        schema = PRODUCTION_PLANNING_SCHEMAS[logical_type]
        version = registry.register(logical_type, schema)
        accepted_range = AcceptedVersionRange(
            logical_type=logical_type,
            min_version=version,
            max_version=version,
        )
        contracts[logical_type] = PlanningPayloadContract(
            logical_type=logical_type,
            schema_version=version,
            accepted_range=accepted_range,
            schema=schema,
        )
    return contracts


def produce_port(name: str, contract: PlanningPayloadContract) -> Port:
    """Return a producer port declaration for a registered planning payload."""

    return Port(
        name,
        CONTENT_TYPE_JSON,
        logical_type=contract.logical_type,
        accepted_version_range=contract.accepted_range,
    )


def consume_port(name: str, contract: PlanningPayloadContract) -> PortRef:
    """Return a consumer port declaration for a registered planning payload."""

    return PortRef(
        name,
        CONTENT_TYPE_JSON,
        logical_type=contract.logical_type,
        accepted_version_range=contract.accepted_range,
    )


def _content_type_for_path(path: Path) -> str:
    if path.suffix == ".json":
        return "application/json"
    if path.suffix in {".md", ".markdown"}:
        return "text/markdown"
    if path.suffix in {".txt", ".log"}:
        return "text/plain"
    return "application/octet-stream"


def _artifact_uri(path: Path) -> str:
    try:
        return path.resolve().as_uri()
    except ValueError:
        return str(path)


def artifact_refs_from_outputs(
    outputs: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Return stable by-reference artifact refs for legacy stage outputs.

    The helper reads only path-like output values. Non-path output values are
    intentionally ignored so legacy outputs can remain broader than the typed
    by-reference subset.
    """

    refs: list[dict[str, Any]] = []
    for label, value in outputs.items():
        if not isinstance(value, (str, Path)):
            continue
        path = Path(value)
        ref: dict[str, Any] = {
            "uri": _artifact_uri(path),
            "content_type": _content_type_for_path(path),
            "digest": None,
            "size_bytes": None,
            "name": str(label),
        }
        if path.exists() and path.is_file():
            data = path.read_bytes()
            ref["digest"] = f"sha256:{hashlib.sha256(data).hexdigest()}"
            ref["size_bytes"] = len(data)
        refs.append(ref)
    return tuple(refs)


def _accepted_range_json(accepted_range: AcceptedVersionRange | None) -> dict[str, Any] | None:
    if accepted_range is None:
        return None
    return {
        "logical_type": accepted_range.logical_type,
        "min_version": accepted_range.min_version,
        "max_version": accepted_range.max_version,
    }


def _producer_port_json(producer_port: Port) -> dict[str, Any]:
    return {
        "name": producer_port.name,
        "content_type": producer_port.content_type,
        "cardinality": producer_port.cardinality,
        "logical_type": producer_port.logical_type,
        "accepted_version_range": _accepted_range_json(
            producer_port.accepted_version_range
        ),
    }


def _verdict_json(verdict: Any) -> dict[str, Any] | None:
    if verdict is None:
        return None
    if isinstance(verdict, Mapping):
        return dict(verdict)
    if dataclasses.is_dataclass(verdict):
        return dataclasses.asdict(verdict)
    return {
        "score": getattr(verdict, "score", None),
        "flags": list(getattr(verdict, "flags", ()) or ()),
        "notes": getattr(verdict, "notes", ""),
        "payload": dict(getattr(verdict, "payload", {}) or {}),
        "recommendation": getattr(verdict, "recommendation", None),
        "override": getattr(verdict, "override", None),
    }


def _diagnostics_json(diagnostics: Any) -> tuple[dict[str, Any], ...]:
    values = diagnostics or ()
    normalized: list[dict[str, Any]] = []
    for diagnostic in values:
        if isinstance(diagnostic, Mapping):
            normalized.append(dict(diagnostic))
        elif dataclasses.is_dataclass(diagnostic):
            normalized.append(dataclasses.asdict(diagnostic))
        else:
            normalized.append(
                {
                    "code": getattr(diagnostic, "code", str(diagnostic)),
                    "message": getattr(diagnostic, "message", str(diagnostic)),
                    "payload_pointer": getattr(diagnostic, "payload_pointer", None),
                }
            )
    return tuple(normalized)


def _contract_for_producer_port(
    producer_port: Port,
    contract: PlanningPayloadContract | None,
) -> PlanningPayloadContract:
    if not producer_port.logical_type:
        raise PlanningPayloadBuildError("producer port must declare logical_type")
    if contract is None:
        try:
            contract = production_planning_contracts()[producer_port.logical_type]
        except KeyError as exc:
            raise PlanningPayloadBuildError(
                f"unknown production planning logical_type {producer_port.logical_type!r}"
            ) from exc
    if producer_port.logical_type != contract.logical_type:
        raise PlanningPayloadBuildError(
            "producer port logical_type does not match payload contract"
        )
    accepted_range = producer_port.accepted_version_range
    if accepted_range is None:
        raise PlanningPayloadBuildError("producer port must declare accepted_version_range")
    if accepted_range.logical_type != contract.logical_type:
        raise PlanningPayloadBuildError(
            "producer port accepted range logical_type does not match payload contract"
        )
    if accepted_range.min_version != contract.schema_version:
        raise PlanningPayloadBuildError(
            "producer port accepted range min_version does not match payload schema hash"
        )
    if accepted_range.max_version != contract.schema_version:
        raise PlanningPayloadBuildError(
            "producer port accepted range max_version does not match payload schema hash"
        )
    return contract


def build_stage_payload(
    *,
    producer_port: Port,
    outputs: Mapping[str, Any],
    state_patch: Mapping[str, Any],
    contract: PlanningPayloadContract | None = None,
    verdict: Any = None,
    outcome: Mapping[str, Any] | None = None,
    diagnostics: Any = (),
    summary: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> tuple[PlanningPayloadContract, dict[str, Any]]:
    """Build a by-reference typed payload from legacy stage result data.

    The payload intentionally carries artifact references and state patch
    *keys* only. Existing output mappings and state patch values remain owned
    by the legacy ``StepResult`` surface.
    """

    resolved_contract = _contract_for_producer_port(producer_port, contract)
    payload_metadata: dict[str, Any] = {
        "producer_port": _producer_port_json(producer_port),
        "output_keys": list(outputs.keys()),
        "state_patch_keys": list(state_patch.keys()),
    }
    verdict_payload = _verdict_json(verdict)
    if verdict_payload is not None:
        payload_metadata["verdict"] = verdict_payload
    if outcome is not None:
        payload_metadata["outcome"] = dict(outcome)
    diagnostic_payload = _diagnostics_json(diagnostics)
    if diagnostic_payload:
        payload_metadata["diagnostics"] = list(diagnostic_payload)
    if metadata:
        payload_metadata.update(dict(metadata))

    return resolved_contract, {
        "logical_type": resolved_contract.logical_type,
        "artifact_refs": list(artifact_refs_from_outputs(outputs)),
        "summary": summary,
        "metadata": payload_metadata,
    }


def produce_stage_payload_result(
    *,
    producer_port: Port,
    outputs: Mapping[str, Any],
    state_patch: Mapping[str, Any],
    contract: PlanningPayloadContract | None = None,
    verdict: Any = None,
    outcome: Mapping[str, Any] | None = None,
    diagnostics: Any = (),
    summary: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> ContractResult:
    """Build and wrap a stage by-reference payload in ``ContractResult``."""

    resolved_contract, payload = build_stage_payload(
        producer_port=producer_port,
        outputs=outputs,
        state_patch=state_patch,
        contract=contract,
        verdict=verdict,
        outcome=outcome,
        diagnostics=diagnostics,
        summary=summary,
        metadata=metadata,
    )
    return produce_payload_result(resolved_contract, payload)


def with_stage_payload_result(
    step_result: Any,
    *,
    producer_port: Port,
    contract: PlanningPayloadContract | None = None,
    outcome: Mapping[str, Any] | None = None,
    diagnostics: Any = (),
    summary: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> Any:
    """Return ``step_result`` with ``contract_result`` added.

    ``dataclasses.replace`` preserves every legacy field value, including
    ``outputs`` and ``state_patch`` mappings, while adding the typed seam
    result for executors that opt into it.
    """

    contract_result = produce_stage_payload_result(
        producer_port=producer_port,
        outputs=getattr(step_result, "outputs", {}),
        state_patch=getattr(step_result, "state_patch", {}),
        contract=contract,
        verdict=getattr(step_result, "verdict", None),
        outcome=outcome,
        diagnostics=diagnostics,
        summary=summary,
        metadata=metadata,
    )
    return dataclasses.replace(step_result, contract_result=contract_result)


def produce_payload_result(
    contract: PlanningPayloadContract,
    payload: Mapping[str, Any],
) -> ContractResult:
    """Wrap a by-reference planning payload in the Step-IO envelope subset."""

    envelope = StepIOEnvelope(
        logical_type=contract.logical_type,
        schema_version=contract.schema_version,
        payload=dict(payload),
    )
    return ContractResult(payload=envelope.to_json())


def consume_payload_result(
    registry: ContractSchemaRegistry,
    contract: PlanningPayloadContract,
    result: ContractResult,
) -> tuple[Mapping[str, Any] | None, tuple[ValidationDiagnostic, ...]]:
    """Validate and unwrap a planning payload result.

    The returned diagnostics are empty on success.  Schema acceptance is checked
    against the contract's declared logical history range before payload shape
    validation runs.
    """

    envelope = StepIOEnvelope.from_json(result.payload)
    if envelope is None:
        return None, (
            ValidationDiagnostic(
                code="invalid_step_io_envelope",
                message="ContractResult payload is not a StepIOEnvelope",
            ),
        )
    if envelope.logical_type != contract.logical_type:
        return None, (
            ValidationDiagnostic(
                code="logical_type_mismatch",
                message="payload logical_type does not match contract logical_type",
                payload_pointer="/logical_type",
            ),
        )
    if not registry.accepts_version(
        contract.logical_type,
        envelope.schema_version,
        contract.accepted_range,
    ):
        return None, (
            ValidationDiagnostic(
                code="schema_version_not_accepted",
                message="payload schema_version is outside the accepted range",
                payload_pointer="/schema_version",
            ),
        )
    validation = validate_payload_against_schema(
        envelope.payload,
        registry.get_schema(envelope.schema_version),
    )
    if not validation.ok:
        return None, validation.diagnostics
    return envelope.payload, ()


__all__ = [
    "CONTENT_TYPE_JSON",
    "LOGICAL_PREP_PAYLOAD",
    "LOGICAL_PLAN_PAYLOAD",
    "LOGICAL_CRITIQUE_PAYLOAD",
    "LOGICAL_GATE_PAYLOAD",
    "LOGICAL_REVISE_PAYLOAD",
    "LOGICAL_FINALIZE_PAYLOAD",
    "LOGICAL_EXECUTE_PAYLOAD",
    "LOGICAL_REVIEW_PAYLOAD",
    "LOGICAL_TIEBREAKER_PAYLOAD",
    "PRODUCTION_PLANNING_LOGICAL_TYPES",
    "PRODUCTION_PLANNING_SCHEMAS",
    "PlanningPayloadContract",
    "PlanningPayloadBuildError",
    "production_planning_contracts",
    "register_production_planning_contracts",
    "produce_port",
    "consume_port",
    "artifact_refs_from_outputs",
    "build_stage_payload",
    "produce_stage_payload_result",
    "with_stage_payload_result",
    "produce_payload_result",
    "consume_payload_result",
]
