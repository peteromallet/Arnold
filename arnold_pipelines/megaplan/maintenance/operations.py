"""Reference-only operational contracts for M3 occurrence-bound operations.

This module freezes the immutable, locator-only operational contracts that
the M3 lifecycle (request/effect/progress/checkpoint/terminal, recurrence,
and human escalation) is bound by.  It is the Step 2 contract surface
consumed by the incident schema (T3), the ledger (T4), projections (T5),
the coherent owner-source join (T6), the checkpoint scheduler (T7), the
independent verifier (T8), and the cloud adapter (T10-T13).

Design rules (locked decisions, do not re-litigate):

* Every owner coordinate is a *reference*, never a payload: the canonical
  M7 occurrence/lease, Run Authority grant/fence, M6A WBC attempt, policy
  version, action target, producer principal, and owner receipts are all
  carried as frozen :class:`~arnold_pipelines.megaplan.maintenance.identity.OwnerRef`
  locator/digest/cursor values (or plain identity strings for coordinates
  that are themselves identities).  Maintenance NEVER constructs an owner
  authority record: there is no lease store, action validator, WBC store,
  repair queue, completion engine, or lifecycle writer in this module.
* Recurrence is a fresh canonical occurrence linked to its predecessor;
  escalation is an immutable reference to the human escalation owner and
  never represents a waiver or a force-proceed.
* All models are frozen, forbid unknown fields, and round-trip through the
  single canonical codec (``canonical_dumps`` / ``strict_loads``).

The closed *action* vocabulary (repair request, source change, installation,
retrigger, progress observation, checkpoint verification, terminal
verification, recurrence, human escalation) and the occurrence-bound
:class:`~arnold_pipelines.megaplan.maintenance.events.OperationalEvent`
envelope live in :mod:`events` on top of these contracts.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
)

_SHA256_HEX = frozenset("0123456789abcdef")


def _require_sha256(value: str, *, what: str) -> str:
    if len(value) != 64 or any(char not in _SHA256_HEX for char in value):
        raise ValueError(f"{what} must be a 64-character lowercase sha256 hex digest")
    return value


def _validate_optional_sha256(value: str | None, *, what: str) -> str | None:
    if value is None:
        return None
    return _require_sha256(value, what=what)


def _validate_nonempty(value: str, *, what: str) -> str:
    if not value:
        raise ValueError(f"{what} must be a non-empty string")
    return value


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic (owner, locator, digest, cursor) reference order."""
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


# ---------------------------------------------------------------------------
# Producer principal
# ---------------------------------------------------------------------------


class ProducerRole(str, Enum):
    """Closed roles a Maintenance operational producer may declare.

    The repair producer is explicitly distinct from the independent
    verifier: a repair actor can never author terminal verification (the
    epic invariant), and the verifier must be a distinct durable principal.
    """

    REPAIR_PRODUCER = "repair_producer"
    VERIFIER = "verifier"
    OBSERVER = "observer"
    SCHEDULER = "scheduler"
    OPERATOR = "operator"


class ProducerPrincipal(BaseModel):
    """The principal that produced an operational action.

    ``principal`` is the exact durable principal identity; ``role`` is the
    closed role.  This is a reference-only contract: it carries no
    credential material and never constructs an owner authority record.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    principal: StrictStr
    role: ProducerRole

    @field_validator("principal")
    @classmethod
    def _validate_principal(cls, value: str) -> str:
        return _validate_nonempty(value, what="producer principal")


# ---------------------------------------------------------------------------
# M7 occurrence and lease coordinates
# ---------------------------------------------------------------------------


class OccurrenceCoordinates(BaseModel):
    """Immutable reference to the canonical M7 repair occurrence.

    ``occurrence_id`` is the exact M7 occurrence identity and
    ``canonical_digest`` its content digest; ``occurrence_ref`` is the
    locator-only reference into the canonical M7 occurrence record.
    Maintenance stores only this join/reference — it never creates a
    repair-custody store.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence_id: StrictStr
    canonical_digest: StrictStr
    occurrence_ref: OwnerRef | None = None

    @field_validator("occurrence_id")
    @classmethod
    def _validate_occurrence(cls, value: str) -> str:
        return _validate_nonempty(value, what="occurrence_id")

    @field_validator("canonical_digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return _require_sha256(value, what="occurrence canonical digest")


class LeaseCoordinates(BaseModel):
    """Immutable reference to the canonical M7 custody lease/epoch.

    ``custody_epoch`` is the exact current epoch of the lease;
    ``lease_digest`` is the lease record digest; ``lease_ref`` is the
    locator-only reference into the M7 lease store.  Maintenance never
    acquires, renews, transfers, or releases a lease.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    lease_id: StrictStr
    custody_epoch: int = Field(ge=1)
    lease_digest: StrictStr | None = None
    lease_ref: OwnerRef | None = None

    @field_validator("lease_id")
    @classmethod
    def _validate_lease(cls, value: str) -> str:
        return _validate_nonempty(value, what="lease_id")

    @field_validator("lease_digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        return _validate_optional_sha256(value, what="lease digest")


# ---------------------------------------------------------------------------
# Run Authority grant/fence coordinates
# ---------------------------------------------------------------------------


class RunAuthorityCoordinates(BaseModel):
    """Immutable reference to the Run Authority grant/fence for an action.

    ``satisfied`` mirrors the current ``evaluate_current_source`` outcome
    (a read, never a grant); ``grant_ref``/``fence_ref``/``decision_ref``
    are locator-only references to the matched authority records.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: StrictStr
    satisfied: bool = False
    grant_ref: OwnerRef | None = None
    fence_ref: OwnerRef | None = None
    decision_ref: OwnerRef | None = None

    @field_validator("run_id")
    @classmethod
    def _validate_run(cls, value: str) -> str:
        return _validate_nonempty(value, what="run_id")


# ---------------------------------------------------------------------------
# M6A WBC attempt coordinates
# ---------------------------------------------------------------------------


class WbcAttemptCoordinates(BaseModel):
    """Immutable reference to the canonical M6A WBC attempt.

    ``attempt_id`` is the exact WBC attempt identity; ``attempt_ref`` and
    ``ledger_ref`` are locator-only references into the WBC attempt ledger
    store.  Maintenance never appends to or writes the WBC store.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_id: StrictStr
    attempt_ref: OwnerRef | None = None
    ledger_ref: OwnerRef | None = None

    @field_validator("attempt_id")
    @classmethod
    def _validate_attempt(cls, value: str) -> str:
        return _validate_nonempty(value, what="attempt_id")


# ---------------------------------------------------------------------------
# Policy version and action target
# ---------------------------------------------------------------------------


class PolicyVersionCoordinates(BaseModel):
    """Immutable reference to the policy version governing an action.

    ``policy_version`` is the exact policy version identity;
    ``policy_digest`` is its content digest when known.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: StrictStr
    policy_digest: StrictStr | None = None

    @field_validator("policy_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        return _validate_nonempty(value, what="policy_version")

    @field_validator("policy_digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        return _validate_optional_sha256(value, what="policy digest")


class ActionTarget(BaseModel):
    """The exact target identity of an operational action.

    ``target`` is the exact target identity (path, service, occurrence
    subject, ...); ``target_type`` names the target kind when known.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: StrictStr
    target_type: StrictStr | None = None

    @field_validator("target")
    @classmethod
    def _validate_target(cls, value: str) -> str:
        return _validate_nonempty(value, what="action target")

    @field_validator("target_type")
    @classmethod
    def _validate_target_type(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("target_type must be a non-empty string when present")
        return value


# ---------------------------------------------------------------------------
# Owner receipts
# ---------------------------------------------------------------------------


class OwnerReceipts(BaseModel):
    """Immutable references to canonical owner receipts.

    Every receipt is a locator-only :class:`OwnerRef` into the canonical
    owner store (M7 repair receipt, M10 effect receipt, ...).  Receipts
    never authorize the next lifecycle edge by themselves and are always
    stored in deterministic order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt_refs: tuple[OwnerRef, ...] = ()

    @field_validator("receipt_refs")
    @classmethod
    def _sort_receipts(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)


# ---------------------------------------------------------------------------
# Recurrence and human escalation references
# ---------------------------------------------------------------------------


class RecurrenceReference(BaseModel):
    """Causal reference from a verified recurrence to its predecessor.

    A verified recurrence ALWAYS creates a fresh canonical occurrence: the
    predecessor occurrence/event identities must differ from the enclosing
    occurrence (enforced by the enclosing envelope).  ``root_cause_cluster``
    is analytical grouping only — it never participates in idempotency,
    lease, or budget scope.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    predecessor_occurrence_id: StrictStr
    predecessor_event_id: StrictStr
    root_cause_cluster: StrictStr | None = None

    @field_validator("predecessor_occurrence_id", "predecessor_event_id")
    @classmethod
    def _validate_predecessor(cls, value: str) -> str:
        return _validate_nonempty(value, what="recurrence predecessor identity")

    @field_validator("root_cause_cluster")
    @classmethod
    def _validate_cluster(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError(
                "root_cause_cluster must be a non-empty string when present"
            )
        return value


class EscalationReference(BaseModel):
    """Immutable reference to the human escalation owner for an unresolved gate.

    A true human gate or ambiguous blocker is represented by this reference
    while canonical custody stays OPEN: escalation never force-proceeds,
    never waives a gate, and never closes custody.  ``human_gate`` must be
    ``True`` — an escalation reference is always a human-gate reference.
    ``escalation_ref`` is a locator-only reference to the durable escalation
    record owned by the named escalation owner.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: StrictStr
    escalation_owner: StrictStr
    human_gate: bool = True
    escalation_ref: OwnerRef | None = None

    @field_validator("reason", "escalation_owner")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        return _validate_nonempty(value, what="escalation reason/owner")

    @model_validator(mode="after")
    def _require_human_gate(self) -> EscalationReference:
        if not self.human_gate:
            raise ValueError(
                "an escalation reference always represents a human gate; "
                "human_gate must be True"
            )
        return self


# ---------------------------------------------------------------------------
# Reference-only enforcement
# ---------------------------------------------------------------------------


def assert_reference_only_contract(model: BaseModel) -> None:
    """Prove *model* embeds no owner record payload.

    Every field whose annotation is an owner kind or carries owner data must
    be an :class:`OwnerRef` (locator/digest/cursor only) or ``None``/tuple of
    them.  Owner payloads (leases, grants, events, manifests, receipts as
    objects) are rejected: Maintenance constructs references, never owner
    authority records.
    """
    for name, field in type(model).model_fields.items():
        annotation = field.annotation
        if annotation is None:
            continue
        value = getattr(model, name)
        if value is None:
            continue
        if isinstance(value, tuple):
            for item in value:
                if not isinstance(item, OwnerRef):
                    raise TypeError(
                        f"{type(model).__name__}.{name} must contain only "
                        f"OwnerRef values, got {type(item).__name__}"
                    )
            continue
        if "OwnerRef" in str(annotation):
            if not isinstance(value, OwnerRef):
                raise TypeError(
                    f"{type(model).__name__}.{name} must be an OwnerRef, "
                    f"got {type(value).__name__}"
                )


__all__ = [
    "ActionTarget",
    "EscalationReference",
    "LeaseCoordinates",
    "OccurrenceCoordinates",
    "OwnerReceipts",
    "PolicyVersionCoordinates",
    "ProducerPrincipal",
    "ProducerRole",
    "RecurrenceReference",
    "RunAuthorityCoordinates",
    "WbcAttemptCoordinates",
    "assert_reference_only_contract",
]
