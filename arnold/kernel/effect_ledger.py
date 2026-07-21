"""Effect ledger with journal folding, idempotency policy enforcement, and dedupe.

Every external effect is pre-recorded as an intent event before execution.
Fulfillment, receipt, and compensation events update the ledger. Effects
without an idempotency policy are rejected, and duplicate idempotency keys are
executed at most once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol

from arnold.kernel.effect import EffectDescriptor, EffectKind
from arnold.kernel.events import EventEnvelope
from arnold.kernel.ids import derive_idempotency_key


class EffectRecordState(StrEnum):
    """Lifecycle state of an effect in the ledger."""

    INTENDED = "intended"
    FULFILLED = "fulfilled"
    RECEIVED = "received"
    COMPENSATED = "compensated"
    FAILED = "failed"


@dataclass(frozen=True)
class EffectRecord:
    """A single effect entry in the folded ledger."""

    descriptor: EffectDescriptor
    state: EffectRecordState


class EffectEvidenceRecorder(Protocol):
    """Optional recorder used to emit WBC evidence for effect boundaries."""

    def effect_intent(self, name: str, payload: Mapping[str, Any] | None = None) -> None: ...

    def effect_outcome(
        self,
        name: str,
        *,
        status: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None: ...

    def reconciliation(
        self,
        name: str,
        *,
        outcome: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None: ...


@dataclass
class EffectLedger:
    """Folded ledger of external effects derived from the journal.

    The in-memory contract model supports both direct use in tests and
    reconstruction by folding ``effect_*`` events from a journal.
    """

    _records: dict[str, EffectRecord] = field(default_factory=dict)
    _evidence: EffectEvidenceRecorder | None = field(default=None, repr=False, compare=False)
    _boundary_name: str = field(default="kernel.effect_ledger", repr=False, compare=False)

    def prerecord(self, effect: EffectDescriptor) -> bool:
        """Record an effect intent before execution.

        Returns ``True`` for a new key and ``False`` when a duplicate key was
        already recorded.
        """

        payload = _effect_payload(effect)
        if effect.idempotency_key in self._records:
            if self._evidence is not None:
                self._evidence.reconciliation(
                    f"{self._boundary_name}.duplicate",
                    outcome="already_intended",
                    payload=payload,
                )
            return False
        if self._evidence is not None:
            self._evidence.effect_intent(
                f"{self._boundary_name}.{effect.effect_id}",
                payload=payload,
            )
        self._records[effect.idempotency_key] = EffectRecord(
            descriptor=effect,
            state=EffectRecordState.INTENDED,
        )
        return True

    def mark_fulfilled(self, idempotency_key: str) -> None:
        record = self._records.get(idempotency_key)
        if record is not None:
            self._records[idempotency_key] = EffectRecord(
                descriptor=record.descriptor,
                state=EffectRecordState.FULFILLED,
            )
            self._record_outcome(record.descriptor, EffectRecordState.FULFILLED)

    def mark_received(self, idempotency_key: str) -> None:
        record = self._records.get(idempotency_key)
        if record is not None:
            self._records[idempotency_key] = EffectRecord(
                descriptor=record.descriptor,
                state=EffectRecordState.RECEIVED,
            )
            self._record_outcome(record.descriptor, EffectRecordState.RECEIVED)

    def mark_compensated(self, idempotency_key: str) -> None:
        record = self._records.get(idempotency_key)
        if record is not None:
            self._records[idempotency_key] = EffectRecord(
                descriptor=record.descriptor,
                state=EffectRecordState.COMPENSATED,
            )
            self._record_outcome(record.descriptor, EffectRecordState.COMPENSATED)

    def mark_failed(self, idempotency_key: str) -> None:
        record = self._records.get(idempotency_key)
        if record is not None:
            self._records[idempotency_key] = EffectRecord(
                descriptor=record.descriptor,
                state=EffectRecordState.FAILED,
            )
            self._record_outcome(record.descriptor, EffectRecordState.FAILED)

    def get(self, idempotency_key: str) -> EffectDescriptor | None:
        record = self._records.get(idempotency_key)
        return record.descriptor if record is not None else None

    def get_record(self, idempotency_key: str) -> EffectRecord | None:
        return self._records.get(idempotency_key)

    def is_duplicate(self, idempotency_key: str) -> bool:
        """Return True if an effect with this key has already been intended."""

        return idempotency_key in self._records

    def __iter__(self):
        return iter(self._records.values())

    def __len__(self) -> int:
        return len(self._records)

    def _record_outcome(
        self,
        descriptor: EffectDescriptor,
        state: EffectRecordState,
    ) -> None:
        if self._evidence is None:
            return
        payload = _effect_payload(descriptor)
        payload["lifecycle_state"] = state.value
        self._evidence.effect_outcome(
            f"{self._boundary_name}.{descriptor.effect_id}",
            status=state.value,
            payload=payload,
        )


EFFECT_EVENT_KINDS = frozenset({
    "effect_intent",
    "effect_fulfillment",
    "effect_receipt",
    "effect_compensation",
    "effect_failure",
})


def intent_payload(descriptor: EffectDescriptor) -> Mapping[str, Any]:
    """Build an event payload for an effect intent."""

    return {
        "effect_id": descriptor.effect_id,
        "kind": descriptor.kind.value,
        "target": descriptor.target,
        "idempotency_key": descriptor.idempotency_key,
        "payload_schema_hash": descriptor.payload_schema_hash,
    }


def _effect_payload(descriptor: EffectDescriptor) -> dict[str, Any]:
    return dict(intent_payload(descriptor))


def fulfillment_payload(
    descriptor: EffectDescriptor,
    result: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Build an event payload for an effect fulfillment."""

    payload = intent_payload(descriptor)
    payload["result"] = dict(result) if result is not None else {}
    return payload


def receipt_payload(
    descriptor: EffectDescriptor,
    receipt: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Build an event payload for an effect receipt."""

    payload = intent_payload(descriptor)
    payload["receipt"] = dict(receipt) if receipt is not None else {}
    return payload


class MissingIdempotencyPolicyError(Exception):
    """Raised when an effect lacks a required idempotency policy."""


def require_idempotency_policy(
    *,
    key_ref: str | None,
    key_template: str | None,
    required: bool = True,
) -> None:
    """Require that an effect carries an idempotency policy before execution.

    A policy is satisfied when ``key_ref`` or ``key_template`` is non-empty.
    When ``required`` is False, the check is a no-op.
    """

    if not required:
        return
    if not key_ref and not key_template:
        raise MissingIdempotencyPolicyError(
            "external effect requires an idempotency policy (key_ref or key_template)"
        )


def derive_effect_idempotency_key(
    *,
    run_id: str,
    node_ref: str,
    effect_id: str,
    key_template: str | None = None,
    key_ref: str | None = None,
) -> str:
    """Derive a deterministic idempotency key for an effect.

    The manifest fields are used only as opaque string inputs; they are never
    treated as dynamic import paths.
    """

    if key_template:
        return derive_idempotency_key(run_id, node_ref, effect_id, key_template)
    if key_ref:
        return derive_idempotency_key(run_id, node_ref, effect_id, key_ref)
    return derive_idempotency_key(run_id, node_ref, effect_id)


def fold_effect_ledger(events: tuple[EventEnvelope, ...]) -> EffectLedger:
    """Reconstruct an effect ledger by folding effect events from a journal."""

    ledger = EffectLedger()
    for event in events:
        if event.kind not in EFFECT_EVENT_KINDS:
            continue
        payload = event.payload
        idempotency_key = payload.get("idempotency_key")
        if not idempotency_key:
            continue
        descriptor = EffectDescriptor(
            effect_id=payload.get("effect_id", ""),
            kind=EffectKind(payload.get("kind", EffectKind.INTENT.value)),
            target=payload.get("target", ""),
            idempotency_key=idempotency_key,
            payload_schema_hash=payload.get("payload_schema_hash", ""),
        )
        if event.kind == "effect_intent":
            ledger.prerecord(descriptor)
        elif event.kind == "effect_fulfillment":
            ledger.prerecord(descriptor)
            ledger.mark_fulfilled(idempotency_key)
        elif event.kind == "effect_receipt":
            ledger.prerecord(descriptor)
            ledger.mark_received(idempotency_key)
        elif event.kind == "effect_compensation":
            ledger.prerecord(descriptor)
            ledger.mark_compensated(idempotency_key)
        elif event.kind == "effect_failure":
            ledger.prerecord(descriptor)
            ledger.mark_failed(idempotency_key)
    return ledger


__all__ = [
    "EffectLedger",
    "EffectRecord",
    "EffectRecordState",
    "MissingIdempotencyPolicyError",
    "derive_effect_idempotency_key",
    "fold_effect_ledger",
    "fulfillment_payload",
    "intent_payload",
    "receipt_payload",
    "require_idempotency_policy",
]
