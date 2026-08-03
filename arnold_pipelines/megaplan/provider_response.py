"""Provider response-enforcement selection and evidence.

The persisted megaplan schema is the semantic contract.  Provider structured-
output schemas are only a transport optimization: they must never silently
rewrite that contract.  This module therefore compiles a conservative OpenAI/
Codex dialect when it can do so without changing semantics and otherwise
selects exact local JSON parsing plus canonical schema validation.
"""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


RESPONSE_CONTRACT_COMPILER_VERSION = "codex-response-contract-v1"


class ResponseEnforcement(str, Enum):
    """How a model response is constrained, independent of tool access."""

    PROVIDER_STRICT = "provider_strict"
    LOCAL_STRICT_JSON = "local_strict_json"


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def schema_sha256(schema: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(schema)).hexdigest()


@dataclass(frozen=True)
class ResponseEnforcementAttestation:
    canonical_schema_hash: str
    response_enforcement: str
    enforcement_reason: str
    provider: str
    model: str | None
    phase: str
    transport_schema_hash: str | None
    compiler_version: str = RESPONSE_CONTRACT_COMPILER_VERSION

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CompiledResponseContract:
    attestation: ResponseEnforcementAttestation
    transport_schema: dict[str, Any] | None


class ProviderResponseContractError(RuntimeError):
    """Impossible compiler invariant with stable machine-readable routing data."""

    error_kind = "provider_contract"
    error_layer = "schema_error"
    deterministic = True
    nonretryable = True

    def __init__(self, message: str, *, schema: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        material = {
            "compiler_version": RESPONSE_CONTRACT_COMPILER_VERSION,
            "message": message,
            "schema_hash": schema_sha256(schema) if schema is not None else None,
        }
        self.failure_fingerprint = hashlib.sha256(_canonical_json(material)).hexdigest()

    def external_error(self) -> dict[str, Any]:
        return {
            "error_kind": self.error_kind,
            "error_layer": self.error_layer,
            "deterministic": self.deterministic,
            "nonretryable": self.nonretryable,
            "failure_fingerprint": self.failure_fingerprint,
        }


# Conservative subset accepted by Codex/OpenAI strict structured output.  A
# schema outside this subset remains fully supported through local validation.
_SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "anyOf",
        "description",
        "$defs",
        "$ref",
    }
)


def _dynamic_object_rejection(schema: Any, path: tuple[str, ...] = ()) -> str | None:
    """Find semantic open maps before reporting less fundamental keywords."""

    if isinstance(schema, list):
        for index, item in enumerate(schema):
            reason = _dynamic_object_rejection(item, path + (str(index),))
            if reason:
                return reason
        return None
    if not isinstance(schema, dict):
        return None
    schema_type = schema.get("type")
    if schema_type == "object" or (
        isinstance(schema_type, list) and "object" in schema_type
    ):
        additional = schema.get("additionalProperties")
        if additional is not False:
            return f"dynamic_or_open_object@{'/'.join(path) or '$'}"
    for key in ("properties", "$defs"):
        children = schema.get(key)
        if isinstance(children, dict):
            for name, child in children.items():
                reason = _dynamic_object_rejection(child, path + (key, str(name)))
                if reason:
                    return reason
    if "items" in schema:
        reason = _dynamic_object_rejection(schema["items"], path + ("items",))
        if reason:
            return reason
    if "anyOf" in schema:
        return _dynamic_object_rejection(schema["anyOf"], path + ("anyOf",))
    return None


def _provider_strict_rejection(schema: Any, path: tuple[str, ...] = ()) -> str | None:
    if isinstance(schema, list):
        for index, item in enumerate(schema):
            reason = _provider_strict_rejection(item, path + (str(index),))
            if reason:
                return reason
        return None
    if not isinstance(schema, dict):
        return None

    for key in schema:
        if key not in _SUPPORTED_SCHEMA_KEYWORDS:
            location = "/".join(path) or "$"
            return f"unsupported_keyword:{key}@{location}"

    schema_type = schema.get("type")
    if schema_type == "object" or (
        isinstance(schema_type, list) and "object" in schema_type
    ):
        properties = schema.get("properties")
        additional = schema.get("additionalProperties")
        if additional is not False:
            location = "/".join(path) or "$"
            return f"dynamic_or_open_object@{location}"
        if not isinstance(properties, dict):
            location = "/".join(path) or "$"
            return f"object_without_closed_properties@{location}"
        required = schema.get("required")
        if not isinstance(required, list) or set(required) != set(properties):
            location = "/".join(path) or "$"
            return f"optional_object_properties@{location}"
        for name, child in properties.items():
            reason = _provider_strict_rejection(
                child, path + ("properties", str(name))
            )
            if reason:
                return reason

    if "items" in schema:
        reason = _provider_strict_rejection(schema["items"], path + ("items",))
        if reason:
            return reason
    if "anyOf" in schema:
        reason = _provider_strict_rejection(schema["anyOf"], path + ("anyOf",))
        if reason:
            return reason
    if "$defs" in schema:
        definitions = schema["$defs"]
        if not isinstance(definitions, dict):
            return f"invalid_defs@{'/'.join(path) or '$'}"
        for name, child in definitions.items():
            reason = _provider_strict_rejection(child, path + ("$defs", str(name)))
            if reason:
                return reason
    return None


def compile_response_contract(
    canonical_schema: Mapping[str, Any],
    *,
    provider: str,
    model: str | None,
    phase: str,
    provider_schema_available: bool = True,
) -> CompiledResponseContract:
    """Select provider- or local-strict enforcement without semantic drift."""

    if not isinstance(canonical_schema, Mapping) or not canonical_schema:
        raise ProviderResponseContractError(
            "canonical response schema must be a non-empty mapping",
            schema=canonical_schema if isinstance(canonical_schema, Mapping) else None,
        )
    canonical = deepcopy(dict(canonical_schema))
    canonical_hash = schema_sha256(canonical)
    normalized_provider = provider.strip().lower()
    reason: str | None = None
    if not provider_schema_available:
        reason = "transport_does_not_support_provider_schema"
    elif normalized_provider not in {"openai", "codex"}:
        reason = f"provider_dialect_not_compiled:{normalized_provider or 'unknown'}"
    else:
        reason = _dynamic_object_rejection(canonical)
        if reason is None:
            reason = _provider_strict_rejection(canonical)

    if reason is not None:
        attestation = ResponseEnforcementAttestation(
            canonical_schema_hash=canonical_hash,
            response_enforcement=ResponseEnforcement.LOCAL_STRICT_JSON.value,
            enforcement_reason=reason,
            provider=normalized_provider or provider,
            model=model,
            phase=phase,
            transport_schema_hash=None,
        )
        return CompiledResponseContract(attestation, None)

    transport_schema = canonical
    transport_hash = schema_sha256(transport_schema)
    attestation = ResponseEnforcementAttestation(
        canonical_schema_hash=canonical_hash,
        response_enforcement=ResponseEnforcement.PROVIDER_STRICT.value,
        enforcement_reason="closed_schema_accepted_by_codex_dialect",
        provider=normalized_provider,
        model=model,
        phase=phase,
        transport_schema_hash=transport_hash,
    )
    return CompiledResponseContract(attestation, transport_schema)


def persist_response_enforcement_attestation(
    plan_dir: Path,
    attestation: ResponseEnforcementAttestation,
) -> Path:
    """Durably append one response-enforcement decision to the plan ledger."""

    path = plan_dir / "response_enforcement.ndjson"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical_json(attestation.to_json()) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    return path


__all__ = [
    "CompiledResponseContract",
    "ProviderResponseContractError",
    "RESPONSE_CONTRACT_COMPILER_VERSION",
    "ResponseEnforcement",
    "ResponseEnforcementAttestation",
    "compile_response_contract",
    "persist_response_enforcement_attestation",
    "schema_sha256",
]
