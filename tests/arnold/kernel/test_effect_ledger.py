from __future__ import annotations

import pytest

from arnold.kernel import (
    EffectDescriptor,
    EffectKind,
    EffectLedger,
    EffectRecordState,
    EventEnvelope,
    EventFamily,
    ManifestReference,
    MissingIdempotencyPolicyError,
    derive_effect_idempotency_key,
    fold_effect_ledger,
    fulfillment_payload,
    intent_payload,
    receipt_payload,
    require_idempotency_policy,
)


def _event(kind: str, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        event_id=f"evt:{kind}",
        family=EventFamily.EFFECT,
        kind=kind,
        manifest=ManifestReference(alias="demo", manifest_hash="sha256:" + "a" * 64),
        run_id="run-1",
        payload_schema_hash="sha256:" + "b" * 64,
        payload=payload,
    )


def _descriptor(effect_id: str = "write-1", key: str = "idem-1") -> EffectDescriptor:
    return EffectDescriptor(
        effect_id=effect_id,
        kind=EffectKind.INTENT,
        target="artifact:report",
        idempotency_key=key,
        payload_schema_hash="sha256:" + "c" * 64,
    )


def test_prerecord_creates_intended_record() -> None:
    ledger = EffectLedger()
    effect = _descriptor()

    assert ledger.prerecord(effect) is True
    record = ledger.get_record(effect.idempotency_key)
    assert record is not None
    assert record.state is EffectRecordState.INTENDED
    assert ledger.get(effect.idempotency_key) == effect


def test_prerecord_returns_false_for_duplicate_key() -> None:
    ledger = EffectLedger()
    effect = _descriptor()

    assert ledger.prerecord(effect) is True
    assert ledger.prerecord(effect) is False


def test_effect_intent_event_is_folded_into_ledger() -> None:
    effect = _descriptor()
    event = _event("effect_intent", intent_payload(effect))

    ledger = fold_effect_ledger((event,))
    assert ledger.is_duplicate(effect.idempotency_key)
    assert ledger.get_record(effect.idempotency_key).state is EffectRecordState.INTENDED


def test_effect_fulfillment_event_marks_fulfilled() -> None:
    effect = _descriptor()
    events = (
        _event("effect_intent", intent_payload(effect)),
        _event("effect_fulfillment", fulfillment_payload(effect, {"ok": True})),
    )

    ledger = fold_effect_ledger(events)
    record = ledger.get_record(effect.idempotency_key)
    assert record.state is EffectRecordState.FULFILLED


def test_effect_receipt_event_marks_received() -> None:
    effect = _descriptor()
    events = (
        _event("effect_intent", intent_payload(effect)),
        _event("effect_receipt", receipt_payload(effect, {"received_at": "now"})),
    )

    ledger = fold_effect_ledger(events)
    record = ledger.get_record(effect.idempotency_key)
    assert record.state is EffectRecordState.RECEIVED


def test_effect_compensation_event_marks_compensated() -> None:
    effect = _descriptor(key="comp-1")
    events = (
        _event("effect_intent", intent_payload(effect)),
        _event("effect_compensation", intent_payload(effect)),
    )

    ledger = fold_effect_ledger(events)
    record = ledger.get_record(effect.idempotency_key)
    assert record.state is EffectRecordState.COMPENSATED


def test_required_idempotency_policy_is_enforced() -> None:
    with pytest.raises(MissingIdempotencyPolicyError, match="idempotency policy"):
        require_idempotency_policy(key_ref=None, key_template=None, required=True)


def test_optional_idempotency_policy_is_skipped() -> None:
    require_idempotency_policy(key_ref=None, key_template=None, required=False)


def test_idempotency_policy_satisfied_by_key_ref() -> None:
    require_idempotency_policy(key_ref="stable-ref", key_template=None)


def test_idempotency_policy_satisfied_by_key_template() -> None:
    require_idempotency_policy(key_ref=None, key_template="{run_id}:{node_ref}")


def test_derive_effect_idempotency_key_is_deterministic() -> None:
    key1 = derive_effect_idempotency_key(
        run_id="run-1",
        node_ref="n1",
        effect_id="write",
        key_template="{run_id}:{node_ref}",
    )
    key2 = derive_effect_idempotency_key(
        run_id="run-1",
        node_ref="n1",
        effect_id="write",
        key_template="{run_id}:{node_ref}",
    )
    assert key1 == key2
    assert key1.startswith("sha256:")


def test_deduped_effect_is_not_re_executed() -> None:
    ledger = EffectLedger()
    effect = _descriptor()

    assert ledger.prerecord(effect) is True
    assert ledger.prerecord(effect) is False
    assert len(ledger) == 1
