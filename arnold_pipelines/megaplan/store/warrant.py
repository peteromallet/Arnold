"""Warrant construction and verification over source projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from arnold_pipelines.megaplan._core.canonical import (
    canonical_projection_bytes,
    canonical_projection_sha256_uri,
    sha256_uri,
    sign_canonical_projection,
    verify_canonical_projection_signature,
)
from arnold_pipelines.megaplan._core.config_resolver import ConfigResolver
from arnold_pipelines.megaplan.schemas import Warrant, WarrantSignature, WarrantSourceProjection, utc_now


class WarrantError(ValueError):
    """Base class for machine-readable Warrant failures."""

    def __init__(self, error_kind: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.error_kind = error_kind
        self.details = {"error_kind": error_kind, **details}


@dataclass(frozen=True)
class WarrantBuildResult:
    warrant: Warrant
    signed_envelope_sha256: str


def _resolve_warrant_key(
    *,
    warrant_key: str | bytes | bytearray | memoryview | None = None,
    resolver: ConfigResolver | None = None,
) -> str | bytes | bytearray | memoryview:
    if warrant_key is not None:
        if isinstance(warrant_key, str) and not warrant_key:
            raise WarrantError("missing_warrant_key", "Warrant signing key is empty")
        if not isinstance(warrant_key, str) and not bytes(warrant_key):
            raise WarrantError("missing_warrant_key", "Warrant signing key is empty")
        return warrant_key
    resolved = (resolver or ConfigResolver()).effective("signing", "warrant_key")
    if not resolved:
        raise WarrantError("missing_warrant_key", "Warrant signing key is not configured")
    return resolved


def _required_source_errors(projection: WarrantSourceProjection) -> list[str]:
    completeness = projection.completeness
    required = set(completeness.required_fields)
    errors = sorted(required & (set(completeness.missing) | set(completeness.unsupported)))
    if not completeness.signable:
        errors.extend(
            name
            for name, value in (
                ("authority_envelope", projection.authority),
                ("verified_work_account", projection.account),
                ("rationale_anchor", projection.rationale_anchor),
                ("behavioral_or_manifest_hash", projection.behavioral_manifest_hash),
                ("verified_result_ref", projection.verified_result_ref),
            )
            if value is None and name not in errors
        )
    return sorted(set(errors))


def _incomplete_source_details(projection: WarrantSourceProjection) -> dict[str, Any]:
    completeness = projection.completeness
    required = set(completeness.required_fields)
    missing_required = sorted(required & set(completeness.missing))
    unsupported_required = sorted(required & set(completeness.unsupported))
    absent_required = _required_source_errors(projection)
    for name in absent_required:
        if name not in missing_required and name not in unsupported_required:
            missing_required.append(name)
    missing_required = sorted(set(missing_required))
    next_steps = [
        f"provide required Warrant source field: {name}" for name in missing_required
    ] + [
        f"add source adapter support for required Warrant field: {name}"
        for name in unsupported_required
    ]
    return {
        "projection_id": projection.projection_id,
        "missing_required": missing_required,
        "unsupported_required": unsupported_required,
        "present": sorted(set(completeness.present)),
        "legal_moves": next_steps,
        "next_steps": next_steps,
        # Backwards-compatible alias for older callers.
        "missing": sorted(set(missing_required) | set(unsupported_required)),
    }


def _warrant_envelope(
    *,
    projection: WarrantSourceProjection,
    warrant_id: str,
    issued_at: datetime | str | None,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        projection.authority is None
        or projection.account is None
        or projection.rationale_anchor is None
        or projection.behavioral_manifest_hash is None
        or projection.verified_result_ref is None
    ):
        raise WarrantError(
            "incomplete_warrant_source",
            "Warrant source projection is missing required signed fields",
            **_incomplete_source_details(projection),
        )
    envelope: dict[str, Any] = {
        "schema_version": 1,
        "warrant_id": warrant_id,
        "authority": projection.authority.model_dump(mode="json"),
        "account": projection.account.model_dump(mode="json"),
        "rationale_anchor": projection.rationale_anchor.model_dump(mode="json"),
        "behavioral_manifest_hash": projection.behavioral_manifest_hash,
        "verified_result_ref": dict(projection.verified_result_ref),
        "metadata": dict(metadata),
    }
    if issued_at is not None:
        envelope["issued_at"] = issued_at
    return envelope


def _stable_warrant_id(projection: WarrantSourceProjection, metadata: Mapping[str, Any]) -> str:
    payload = {
        "projection_id": projection.projection_id,
        "authority": projection.authority.model_dump(mode="json") if projection.authority else None,
        "account": projection.account.model_dump(mode="json") if projection.account else None,
        "rationale_anchor": projection.rationale_anchor.model_dump(mode="json")
        if projection.rationale_anchor
        else None,
        "behavioral_manifest_hash": projection.behavioral_manifest_hash,
        "verified_result_ref": projection.verified_result_ref,
        "metadata": dict(metadata),
    }
    return sha256_uri(canonical_projection_bytes(payload))


def build_warrant(
    projection: WarrantSourceProjection,
    *,
    warrant_key: str | bytes | bytearray | memoryview | None = None,
    resolver: ConfigResolver | None = None,
    key_id: str | None = None,
    issued_at: datetime | str | None = None,
    signed_at: datetime | str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> WarrantBuildResult:
    """Build and sign a Warrant from a complete source projection."""
    missing = _required_source_errors(projection)
    if missing:
        raise WarrantError(
            "incomplete_warrant_source",
            "Incomplete Warrant source projection cannot be signed",
            **_incomplete_source_details(projection),
        )
    key = _resolve_warrant_key(warrant_key=warrant_key, resolver=resolver)
    warrant_metadata = {
        "source_projection_id": projection.projection_id,
        "source_refs": projection.source_refs,
        **dict(metadata or {}),
    }
    issued_at = issued_at or utc_now()
    warrant_id = _stable_warrant_id(projection, warrant_metadata)
    envelope = _warrant_envelope(
        projection=projection,
        warrant_id=warrant_id,
        issued_at=issued_at,
        metadata=warrant_metadata,
    )
    signature_payload = sign_canonical_projection(
        envelope,
        warrant_key=key,
        key_id=key_id,
        signed_at=signed_at,
    )
    signature = WarrantSignature.model_validate(signature_payload)
    warrant_payload = {**envelope, "signature": signature.model_dump(mode="json")}
    warrant = Warrant.model_validate(warrant_payload)
    return WarrantBuildResult(
        warrant=warrant,
        signed_envelope_sha256=canonical_projection_sha256_uri(envelope),
    )


def warrant_signed_envelope(warrant: Warrant) -> dict[str, Any]:
    """Return the exact frozen Warrant envelope covered by the signature."""
    payload = warrant.model_dump(mode="json")
    payload.pop("signature", None)
    return payload


def verify_warrant(
    warrant: Warrant | Mapping[str, Any],
    *,
    warrant_key: str | bytes | bytearray | memoryview | None = None,
    resolver: ConfigResolver | None = None,
) -> bool:
    """Verify a Warrant signature against canonical frozen envelope bytes."""
    model = warrant if isinstance(warrant, Warrant) else Warrant.model_validate(warrant)
    key = _resolve_warrant_key(warrant_key=warrant_key, resolver=resolver)
    envelope = warrant_signed_envelope(model)
    return verify_canonical_projection_signature(
        envelope,
        model.signature.model_dump(mode="json"),
        warrant_key=key,
    )


__all__ = [
    "WarrantBuildResult",
    "WarrantError",
    "build_warrant",
    "verify_warrant",
    "warrant_signed_envelope",
]
