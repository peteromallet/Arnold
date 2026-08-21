"""Typed admission for editable engine-runtime source repairs.

The progress auditor is intentionally read-only.  A deep repair may only cross
the managed-agent launch boundary when an independent authority has issued a
durable, exact admission for the source surface.  This module contains the
small validation seam used by the repair trigger; it does not grant authority
and never writes state or starts a process.

The contract is deliberately narrower than the generic repair queue contract:
it binds one exact repair occurrence to one candidate revision, one set of
verification/provenance receipts, and one Run Authority/Custody/WBC fence.
It is an adapter around the existing ``blocker_recovery`` deterministic-phase
receipt, not a second writer or a replacement authority.  When that canonical
receipt is present it is checked for an engine-runtime scope and the same
candidate commit.  Missing or malformed fields fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.current_target_liveness import (
    MutationDenied,
    require_mutation_capability,
)


ENGINE_RUNTIME_REPAIR_SCHEMA = "arnold.engine-runtime-repair-admission.v1"
ENGINE_RUNTIME_EFFECT_CLASS = "engine_runtime"
SOURCE_REPAIR_SCOPE = "source_repair"
HORIZON_A_MODEL = "gpt-5.6-sol"

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _nested_or_top(mapping: Mapping[str, Any], nested: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = _text(nested.get(name))
        if value:
            return value
        value = _text(mapping.get(name))
        if value:
            return value
    return ""


@dataclass(frozen=True)
class EngineRuntimeRepairAdmission:
    """Validated, immutable view of an editable engine-runtime admission."""

    admission_id: str
    occurrence_fingerprint: str
    candidate_revision: str
    candidate_runtime_sha256: str
    verification_digest: str
    provenance_digest: str
    effect_barrier_digest: str
    fence_token: str
    authority_receipt: str
    custody_receipt: str
    wbc_receipt: str
    model: str = HORIZON_A_MODEL
    profile: str = "horizon-a"
    schema_version: str = ENGINE_RUNTIME_REPAIR_SCHEMA
    effect_class: str = ENGINE_RUNTIME_EFFECT_CLASS
    repair_scope: str = SOURCE_REPAIR_SCOPE
    canonical_phase_repair: Mapping[str, Any] | None = None
    engine_runtime_root: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "admission_id": self.admission_id,
            "effect_class": self.effect_class,
            "repair_scope": self.repair_scope,
            "occurrence_fingerprint": self.occurrence_fingerprint,
            "candidate": {
                "revision": self.candidate_revision,
                "runtime_sha256": self.candidate_runtime_sha256,
                "verification_digest": self.verification_digest,
                "provenance_digest": self.provenance_digest,
                "effect_barrier_digest": self.effect_barrier_digest,
            },
            "authority": {
                "decision": "approved",
                "model": self.model,
                "profile": self.profile,
            },
            "run_authority_receipt": self.authority_receipt,
            "custody_receipt": self.custody_receipt,
            "wbc_receipt": self.wbc_receipt,
            "fence_token": self.fence_token,
            "one_effect": True,
        }
        if self.canonical_phase_repair is not None:
            payload["canonical_phase_repair"] = dict(self.canonical_phase_repair)
        if self.engine_runtime_root:
            payload["engine_runtime_root"] = self.engine_runtime_root
        return payload


def parse_engine_runtime_repair_admission(
    value: Mapping[str, Any] | None,
    *,
    occurrence_fingerprint: str = "",
) -> EngineRuntimeRepairAdmission | None:
    """Return a validated admission object, or ``None`` on any mismatch."""

    if not isinstance(value, Mapping):
        return None
    schema_version = _text(value.get("schema_version") or value.get("schema"))
    if schema_version != ENGINE_RUNTIME_REPAIR_SCHEMA:
        return None
    admission_id = _text(value.get("admission_id") or value.get("id"))
    actual_occurrence = _text(value.get("occurrence_fingerprint"))
    if not admission_id or not actual_occurrence:
        return None
    if occurrence_fingerprint and actual_occurrence != _text(occurrence_fingerprint):
        return None

    candidate = _mapping(value.get("candidate"))
    authority = _mapping(value.get("authority"))
    candidate_revision = _nested_or_top(value, candidate, "revision", "candidate_revision", "source_commit")
    runtime_sha = _nested_or_top(value, candidate, "runtime_sha256", "candidate_runtime_sha256")
    verification_digest = _nested_or_top(value, candidate, "verification_digest", "tests_digest", "test_receipt_digest")
    provenance_digest = _nested_or_top(value, candidate, "provenance_digest", "provenance_receipt_digest")
    effect_barrier_digest = _nested_or_top(value, candidate, "effect_barrier_digest", "effect_barrier")
    if not _HEX40.fullmatch(candidate_revision.lower()):
        return None
    for digest in (runtime_sha, verification_digest, provenance_digest, effect_barrier_digest):
        if not _HEX64.fullmatch(digest.lower()):
            return None

    decision = _text(authority.get("decision") or authority.get("status") or value.get("approval"))
    approved = authority.get("approved") is True or decision.lower() == "approved"
    model = _text(authority.get("model") or value.get("model")).lower()
    profile = _text(authority.get("profile") or authority.get("route") or value.get("profile")).lower()
    if not approved or model != HORIZON_A_MODEL or profile not in {"horizon-a", "horizon_a"}:
        return None

    authority_receipt = _nested_or_top(value, authority, "run_authority_receipt", "authority_receipt", "run_authority_grant_id")
    custody_receipt = _text(value.get("custody_receipt") or _mapping(value.get("custody")).get("receipt"))
    wbc_receipt = _text(value.get("wbc_receipt") or _mapping(value.get("wbc")).get("receipt"))
    fence_token = _text(value.get("fence_token") or _mapping(value.get("fence")).get("token"))
    if not all((authority_receipt, custody_receipt, wbc_receipt, fence_token)):
        return None
    if value.get("one_effect") is not True:
        return None
    if _text(value.get("effect_class")) != ENGINE_RUNTIME_EFFECT_CLASS:
        return None
    if _text(value.get("repair_scope")) != SOURCE_REPAIR_SCOPE:
        return None

    canonical_phase_repair = _mapping(
        value.get("canonical_phase_repair") or value.get("deterministic_phase_repair")
    )
    if canonical_phase_repair:
        if _text(canonical_phase_repair.get("repair_scope")) != "engine_runtime":
            return None
    engine_runtime_root = _text(
        value.get("engine_runtime_root")
        or candidate.get("engine_runtime_root")
        or candidate.get("runtime_root")
    )
    if engine_runtime_root and not engine_runtime_root.startswith("/"):
        return None
    if canonical_phase_repair:
        if _text(canonical_phase_repair.get("repair_commit")).lower() != candidate_revision.lower():
            return None
        if not _text(canonical_phase_repair.get("failure_fingerprint")):
            return None
        if _text(canonical_phase_repair.get("authority")) not in {
            "explicit_repair_commit_bound_to_engine_runtime",
            "validated_deterministic_phase_repair",
        }:
            return None

    return EngineRuntimeRepairAdmission(
        admission_id=admission_id,
        occurrence_fingerprint=actual_occurrence,
        candidate_revision=candidate_revision.lower(),
        candidate_runtime_sha256=runtime_sha.lower(),
        verification_digest=verification_digest.lower(),
        provenance_digest=provenance_digest.lower(),
        effect_barrier_digest=effect_barrier_digest.lower(),
        fence_token=fence_token,
        authority_receipt=authority_receipt,
        custody_receipt=custody_receipt,
        wbc_receipt=wbc_receipt,
        model=HORIZON_A_MODEL,
        profile="horizon-a",
        canonical_phase_repair=dict(canonical_phase_repair) if canonical_phase_repair else None,
        engine_runtime_root=engine_runtime_root,
    )


def validate_engine_runtime_repair_admission(
    value: Mapping[str, Any] | None,
    *,
    occurrence_fingerprint: str = "",
) -> tuple[bool, str]:
    """Return ``(True, reason)`` only for a complete typed admission."""

    parsed = parse_engine_runtime_repair_admission(
        value, occurrence_fingerprint=occurrence_fingerprint
    )
    if parsed is None:
        return False, (
            "engine_runtime/source_repair requires an approved Horizon-A "
            "admission bound to the exact occurrence, candidate, receipts, "
            "and one-effect fence"
        )
    payload = value if isinstance(value, Mapping) else {}
    try:
        from arnold_pipelines.megaplan.cloud.current_target_liveness import (
            resolve_mutation_capability,
        )

        capability_payload = payload.get("mutation_capability") or payload.get("capability")
        if capability_payload is None:
            handle_id = (
                payload.get("mutation_capability_handle")
                or parsed.occurrence_fingerprint
            )
            capability_payload = resolve_mutation_capability(str(handle_id or ""))
        require_mutation_capability(
            capability_payload,
            action="engine_runtime",
            occurrence=parsed.occurrence_fingerprint,
            scope="engine_runtime",
        )
    except MutationDenied as exc:
        return False, f"engine_runtime mutation denied: {exc.reason}"
    return True, "typed Horizon-A engine-runtime source-repair admission"


def materialize_engine_runtime_repair_admission(
    *,
    occurrence_fingerprint: str,
    operator_charge: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Materialize a request-bound admission from an explicit operator charge.

    This is the handoff bridge used by the read-only auditor: it copies an
    already-issued Sol/Horizon-A charge into the immutable request target but
    does not invent receipts, candidate digests, or authority.  A missing
    charge (or any malformed field) returns ``None`` and the trigger remains
    action-off.
    """

    if not isinstance(operator_charge, Mapping):
        return None
    payload = dict(operator_charge)
    receipts = _mapping(payload.get("receipts"))
    for key, aliases in {
        "run_authority_receipt": ("run_authority_receipt", "authority_receipt"),
        "custody_receipt": ("custody_receipt",),
        "wbc_receipt": ("wbc_receipt",),
    }.items():
        if not _text(payload.get(key)):
            for alias in aliases:
                if _text(receipts.get(alias)):
                    payload[key] = receipts[alias]
                    break
    authority = _mapping(payload.get("authority"))
    if not authority:
        sol_review = _mapping(payload.get("sol_review"))
        authority = sol_review or payload
        payload["authority"] = dict(authority)
    payload.setdefault("schema_version", ENGINE_RUNTIME_REPAIR_SCHEMA)
    payload.setdefault("admission_id", _text(payload.get("charge_id")))
    payload.setdefault("effect_class", ENGINE_RUNTIME_EFFECT_CLASS)
    payload.setdefault("repair_scope", SOURCE_REPAIR_SCOPE)
    payload["occurrence_fingerprint"] = _text(occurrence_fingerprint)
    payload.setdefault("one_effect", True)
    parsed = parse_engine_runtime_repair_admission(
        payload, occurrence_fingerprint=occurrence_fingerprint
    )
    return parsed.to_dict() if parsed is not None else None


__all__ = [
    "ENGINE_RUNTIME_EFFECT_CLASS",
    "ENGINE_RUNTIME_REPAIR_SCHEMA",
    "EngineRuntimeRepairAdmission",
    "HORIZON_A_MODEL",
    "SOURCE_REPAIR_SCOPE",
    "parse_engine_runtime_repair_admission",
    "materialize_engine_runtime_repair_admission",
    "validate_engine_runtime_repair_admission",
]
