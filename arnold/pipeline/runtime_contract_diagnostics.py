"""Author-facing runtime diagnostics for typed contract failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


_BIND_FAILURE_CODES = {
    "no_match": "contract.no_match",
    "typo_name": "contract.no_match",
    "content_type_mismatch": "contract.content_type_mismatch",
    "cardinality_mismatch": "contract.cardinality_mismatch",
    "schema_mismatch": "contract.schema_mismatch",
}


@dataclass(frozen=True)
class RuntimeContractDiagnostic:
    producer_stage: str
    consumer_stage: str
    seam_id: str | None
    logical_type: str
    schema_version: str
    failure_code: str
    suggested_author_action: str
    detail: str

    @property
    def message(self) -> str:
        parts = ["Typed contract violation"]
        if self.producer_stage:
            parts.append(f"producer_stage={self.producer_stage!r}")
        if self.consumer_stage:
            parts.append(f"consumer_stage={self.consumer_stage!r}")
        if self.seam_id:
            parts.append(f"seam_id={self.seam_id!r}")
        parts.append(f"logical_type={self.logical_type!r}")
        parts.append(f"schema_version={self.schema_version!r}")
        parts.append(f"failure_code={self.failure_code!r}")
        parts.append(f"detail={self.detail}")
        parts.append(f"Suggested author action: {self.suggested_author_action}")
        return "; ".join(parts)


def diagnostic_from_step_io(
    *,
    decision: Any,
    producer_stage: str = "",
    consumer_stage: str = "",
    seam_id: str | None = None,
    producer_port: Any = None,
    consumer_port: Any = None,
) -> RuntimeContractDiagnostic | None:
    classification = getattr(decision, "classification", None)
    if getattr(classification, "value", classification) in ("typed_valid", "legacy_unknown"):
        return None

    envelope = getattr(decision, "envelope", None)
    logical_type = str(
        getattr(envelope, "logical_type", None)
        or getattr(producer_port, "logical_type", None)
        or getattr(consumer_port, "logical_type", None)
        or "unknown"
    )
    schema_version = str(getattr(envelope, "schema_version", None) or "unknown")
    diagnostics = tuple(getattr(decision, "diagnostics", ()) or ())
    first = diagnostics[0] if diagnostics else None
    failure_code = str(getattr(first, "code", None) or getattr(classification, "value", classification) or "unknown")
    detail = str(getattr(first, "message", None) or getattr(decision, "block_reason", None) or failure_code)
    return RuntimeContractDiagnostic(
        producer_stage=producer_stage,
        consumer_stage=consumer_stage,
        seam_id=seam_id,
        logical_type=logical_type,
        schema_version=schema_version,
        failure_code=failure_code,
        suggested_author_action=_suggested_action(failure_code, detail=detail),
        detail=detail,
    )


def diagnostic_from_binding_failure(
    *,
    diagnostics: Mapping[str, Any],
    producer_stage: str = "",
    consumer_stage: str = "",
    logical_type: str = "unknown",
    schema_version: str = "unknown",
    seam_id: str | None = None,
) -> RuntimeContractDiagnostic:
    raw_code = str(diagnostics.get("error_kind") or "binding_unavailable")
    failure_code = _BIND_FAILURE_CODES.get(raw_code, raw_code)
    detail = str(diagnostics.get("detail") or raw_code)
    suggested_moves = diagnostics.get("suggested_moves")
    if isinstance(suggested_moves, (list, tuple)) and suggested_moves:
        detail = f"{detail}; suggested_moves={list(suggested_moves)!r}"
    return RuntimeContractDiagnostic(
        producer_stage=producer_stage,
        consumer_stage=consumer_stage,
        seam_id=seam_id,
        logical_type=logical_type,
        schema_version=schema_version,
        failure_code=failure_code,
        suggested_author_action=_suggested_action(failure_code, detail=detail),
        detail=detail,
    )


def diagnostic_from_agent_capture(
    *,
    stage_name: str,
    logical_type: str = "unknown",
    schema_version: str = "unknown",
    failure_code: str,
    detail: str,
) -> RuntimeContractDiagnostic:
    return RuntimeContractDiagnostic(
        producer_stage=stage_name,
        consumer_stage="model_capture",
        seam_id=None,
        logical_type=logical_type,
        schema_version=schema_version,
        failure_code=failure_code,
        suggested_author_action=_suggested_action(failure_code, detail=detail),
        detail=detail,
    )


def _suggested_action(failure_code: str, *, detail: str) -> str:
    if failure_code in {"binding_unavailable", "contract.no_match"}:
        return "Align the producer writes and consumer reads so the port name, type, and wiring can bind cleanly."
    if failure_code == "contract.content_type_mismatch":
        return "Make the producer and consumer content_type declarations compatible."
    if failure_code == "contract.cardinality_mismatch":
        return "Make the producer and consumer cardinality declarations match."
    if failure_code in {"contract.schema_mismatch", "logical_type_mismatch", "schema_version_not_accepted"}:
        return "Align the logical_type and schema compatibility declarations across the producer and consumer."
    if failure_code == "schema_unavailable":
        return "Register the emitted schema version or update the stage to emit a schema version that already exists in the registry."
    if failure_code == "reserved_stream_cardinality":
        return "Use a supported runtime cardinality instead of the reserved 'stream' cardinality."
    if failure_code == "worker_structural_audit_failed":
        return "Update the step output so it matches the declared capture schema before it reaches the typed contract seam."
    if failure_code == "invalid_accepted_version_range":
        return "Fix the consumer accepted_version_range metadata so runtime compatibility checks can run."
    if "schema" in detail.lower():
        return "Align the emitted payload with the declared schema and logical type."
    return "Update the authored stage contract so the runtime payload matches the declared producer and consumer seam."
