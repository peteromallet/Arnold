"""Step IO contract decisions for typed artifact envelopes.

This module owns the neutral classification layer between raw repository JSON
and typed step artifacts. It intentionally validates the envelope payload
directly; it does not deserialize repository JSON as ``ContractResult``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.contract_validation import (
    ValidationDiagnostic,
    validate_payload_against_schema,
)
from arnold.pipeline.schema_registry import (
    ContractSchemaRegistry,
    SchemaRegistryError,
    create_contract_schema_registry,
    normalize_schema_version,
)


class StepIOOperation(str, Enum):
    READ = "read"
    WRITE = "write"


class StepIOClassification(str, Enum):
    TYPED_VALID = "typed_valid"
    TYPED_INVALID = "typed_invalid"
    LEGACY_UNKNOWN = "legacy_unknown"
    SCHEMA_UNAVAILABLE = "schema_unavailable"
    BINDING_UNAVAILABLE = "binding_unavailable"


@dataclass(frozen=True)
class StepIOContractContext:
    """Context needed to make a read/write contract decision."""

    operation: StepIOOperation | str
    registry: ContractSchemaRegistry | None = None
    registry_root: str | Path | None = None
    fail_closed_on_write: bool = True

    def resolve_registry(self) -> ContractSchemaRegistry | None:
        if self.registry is not None:
            return self.registry
        if self.registry_root is None:
            return create_contract_schema_registry()
        return create_contract_schema_registry(self.registry_root)


@dataclass(frozen=True)
class StepIOEnvelope:
    """A complete M1 typed artifact envelope."""

    logical_type: str
    schema_version: str
    payload: Any

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "StepIOEnvelope | None":
        logical_type = data.get("logical_type")
        schema_version = data.get("schema_version")
        if not (
            isinstance(logical_type, str)
            and logical_type
            and isinstance(schema_version, str)
            and schema_version
            and "payload" in data
        ):
            return None
        return cls(
            logical_type=logical_type,
            schema_version=schema_version,
            payload=data["payload"],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "logical_type": self.logical_type,
            "schema_version": self.schema_version,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class StepIODiagnostic:
    """Serializable diagnostic emitted by step IO decisions."""

    code: str
    message: str
    payload_pointer: str = ""
    schema_pointer: str = ""

    @classmethod
    def from_validation(cls, diagnostic: ValidationDiagnostic) -> "StepIODiagnostic":
        return cls(
            code=diagnostic.code,
            message=diagnostic.message,
            payload_pointer=diagnostic.payload_pointer,
            schema_pointer=diagnostic.schema_pointer,
        )

    def to_json(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "payload_pointer": self.payload_pointer,
            "schema_pointer": self.schema_pointer,
        }


@dataclass(frozen=True)
class StepIOContractDecision:
    """Read/write decision for one raw artifact JSON value."""

    classification: StepIOClassification
    allow_read: bool
    allow_write: bool
    value: Any
    envelope: StepIOEnvelope | None = None
    diagnostics: tuple[StepIODiagnostic, ...] = field(default_factory=tuple)
    block_reason: str = ""

    @property
    def typed(self) -> bool:
        return self.envelope is not None

    @property
    def ok(self) -> bool:
        return self.classification in (
            StepIOClassification.TYPED_VALID,
            StepIOClassification.LEGACY_UNKNOWN,
        )

    @property
    def blocks_write(self) -> bool:
        return not self.allow_write

    def to_json(self) -> dict[str, Any]:
        return {
            "classification": self.classification.value,
            "allow_read": self.allow_read,
            "allow_write": self.allow_write,
            "block_reason": self.block_reason,
            "diagnostics": [diagnostic.to_json() for diagnostic in self.diagnostics],
            "envelope": self.envelope.to_json() if self.envelope is not None else None,
        }


def is_step_io_envelope(value: Any) -> bool:
    """Return whether *value* is a complete typed artifact envelope."""

    return isinstance(value, Mapping) and StepIOEnvelope.from_json(value) is not None


def classify_step_io_contract(
    value: Any,
    context: StepIOContractContext | None = None,
) -> StepIOContractDecision:
    """Classify raw artifact JSON and return the repository IO decision."""

    envelope = StepIOEnvelope.from_json(value) if isinstance(value, Mapping) else None
    if envelope is None:
        return StepIOContractDecision(
            classification=StepIOClassification.LEGACY_UNKNOWN,
            allow_read=True,
            allow_write=True,
            value=value,
        )

    registry = context.resolve_registry() if context is not None else None
    if registry is None:
        return _schema_unavailable(envelope)

    try:
        schema_version = normalize_schema_version(envelope.schema_version)
        schema = registry.get_schema(schema_version)
    except SchemaRegistryError as exc:
        return _schema_unavailable(envelope, str(exc))

    result = validate_payload_against_schema(envelope.payload, schema)
    if result.ok:
        return StepIOContractDecision(
            classification=StepIOClassification.TYPED_VALID,
            allow_read=True,
            allow_write=True,
            value=envelope.payload,
            envelope=envelope,
        )

    diagnostics = tuple(StepIODiagnostic.from_validation(d) for d in result.diagnostics)
    return StepIOContractDecision(
        classification=StepIOClassification.TYPED_INVALID,
        allow_read=True,
        allow_write=False,
        value=envelope.payload,
        envelope=envelope,
        diagnostics=diagnostics,
        block_reason="typed artifact payload failed schema validation",
    )


def decide_step_io_read(
    value: Any,
    context: StepIOContractContext | None = None,
) -> StepIOContractDecision:
    """Return the read decision; valid typed artifacts expose payload as value."""

    return classify_step_io_contract(value, context)


def decide_step_io_write(
    value: Any,
    context: StepIOContractContext | None = None,
) -> StepIOContractDecision:
    """Return the write decision, failing closed for invalid typed envelopes."""

    decision = classify_step_io_contract(value, context)
    if (
        context is not None
        and not context.fail_closed_on_write
        and decision.classification
        in (StepIOClassification.TYPED_INVALID, StepIOClassification.SCHEMA_UNAVAILABLE)
    ):
        return StepIOContractDecision(
            classification=decision.classification,
            allow_read=decision.allow_read,
            allow_write=True,
            value=decision.value,
            envelope=decision.envelope,
            diagnostics=decision.diagnostics,
            block_reason="",
        )
    return decision


def _schema_unavailable(
    envelope: StepIOEnvelope,
    message: str = "typed artifact schema is unavailable",
) -> StepIOContractDecision:
    return StepIOContractDecision(
        classification=StepIOClassification.SCHEMA_UNAVAILABLE,
        allow_read=True,
        allow_write=False,
        value=envelope.payload,
        envelope=envelope,
        diagnostics=(StepIODiagnostic(code="schema_unavailable", message=message),),
        block_reason=message,
    )
