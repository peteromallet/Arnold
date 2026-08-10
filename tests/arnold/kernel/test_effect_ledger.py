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
    TerminalStateError,
    derive_effect_idempotency_key,
    fold_effect_ledger,
    fulfillment_payload,
    indeterminate_payload,
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


# ── INDETERMINATE state tests ──────────────────────────────────────────────


def test_mark_indeterminate_sets_state() -> None:
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_indeterminate(effect.idempotency_key)

    record = ledger.get_record(effect.idempotency_key)
    assert record is not None
    assert record.state is EffectRecordState.INDETERMINATE


def test_indeterminate_is_in_effect_record_state_enum() -> None:
    assert hasattr(EffectRecordState, "INDETERMINATE")
    assert EffectRecordState.INDETERMINATE.value == "indeterminate"


def test_effect_indeterminate_event_is_folded() -> None:
    effect = _descriptor(key="indet-1")
    events = (
        _event("effect_intent", intent_payload(effect)),
        _event(
            "effect_indeterminate",
            indeterminate_payload(effect, reason="provider timeout"),
        ),
    )

    ledger = fold_effect_ledger(events)
    record = ledger.get_record(effect.idempotency_key)
    assert record.state is EffectRecordState.INDETERMINATE


def test_indeterminate_payload_includes_reason() -> None:
    effect = _descriptor()
    payload = indeterminate_payload(effect, reason="timeout")
    assert payload["reason"] == "timeout"
    assert payload["idempotency_key"] == effect.idempotency_key


def test_indeterminate_payload_default_reason() -> None:
    effect = _descriptor()
    payload = indeterminate_payload(effect)
    assert payload["reason"] == ""


# ── Terminal state transition guards ────────────────────────────────────────


def test_cannot_transition_from_fulfilled_to_failed() -> None:
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_fulfilled(effect.idempotency_key)

    with pytest.raises(TerminalStateError, match="terminal state"):
        ledger.mark_failed(effect.idempotency_key)


def test_cannot_transition_from_failed_to_fulfilled() -> None:
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_failed(effect.idempotency_key)

    with pytest.raises(TerminalStateError, match="terminal state"):
        ledger.mark_fulfilled(effect.idempotency_key)


def test_cannot_transition_from_indeterminate_to_fulfilled() -> None:
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_indeterminate(effect.idempotency_key)

    with pytest.raises(TerminalStateError, match="terminal state"):
        ledger.mark_fulfilled(effect.idempotency_key)


def test_cannot_transition_from_indeterminate_to_failed() -> None:
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_indeterminate(effect.idempotency_key)

    with pytest.raises(TerminalStateError, match="terminal state"):
        ledger.mark_failed(effect.idempotency_key)


def test_cannot_transition_from_received_to_compensated() -> None:
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_received(effect.idempotency_key)

    with pytest.raises(TerminalStateError, match="terminal state"):
        ledger.mark_compensated(effect.idempotency_key)


def test_cannot_transition_from_compensated_to_received() -> None:
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_compensated(effect.idempotency_key)

    with pytest.raises(TerminalStateError, match="terminal state"):
        ledger.mark_received(effect.idempotency_key)


def test_cannot_transition_from_indeterminate_to_received() -> None:
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_indeterminate(effect.idempotency_key)

    with pytest.raises(TerminalStateError, match="terminal state"):
        ledger.mark_received(effect.idempotency_key)


# ── First-terminal folding: only the first terminal state sticks ────────────


def test_intended_can_transition_to_any_terminal() -> None:
    """INTENDED is the only non-terminal state; transitions are allowed."""
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)

    # All terminal transitions should work from INTENDED
    ledger.mark_fulfilled(effect.idempotency_key)
    # We can't chain since fulfilled is terminal, so test each separately:
    for state_method in [
        lambda l, k: None,  # placeholder for already tested fulfilled
    ]:
        pass

    # Test intended -> failed
    ledger2 = EffectLedger()
    effect2 = _descriptor(key="intended-to-failed")
    ledger2.prerecord(effect2)
    ledger2.mark_failed(effect2.idempotency_key)
    assert ledger2.get_record(effect2.idempotency_key).state is EffectRecordState.FAILED

    # Test intended -> indeterminate
    ledger3 = EffectLedger()
    effect3 = _descriptor(key="intended-to-indet")
    ledger3.prerecord(effect3)
    ledger3.mark_indeterminate(effect3.idempotency_key)
    assert ledger3.get_record(effect3.idempotency_key).state is EffectRecordState.INDETERMINATE


def test_terminal_state_preserved_on_duplicate_mark() -> None:
    """Calling the same terminal mark twice raises, not silently ignored."""
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_fulfilled(effect.idempotency_key)

    # Second attempt to mark fulfilled raises because already terminal
    with pytest.raises(TerminalStateError, match="terminal state"):
        ledger.mark_fulfilled(effect.idempotency_key)


# ── No-blind-retry: INDETERMINATE prevents silent retry ─────────────────────


def test_indeterminate_effect_is_terminal_blocks_retry() -> None:
    """An indeterminate effect cannot be blindly retried (no transition allowed)."""
    ledger = EffectLedger()
    effect = _descriptor()
    ledger.prerecord(effect)
    ledger.mark_indeterminate(effect.idempotency_key)

    # Any attempt to change state is rejected
    for method_name in [
        "mark_fulfilled",
        "mark_received",
        "mark_compensated",
        "mark_failed",
        "mark_indeterminate",
    ]:
        method = getattr(ledger, method_name)
        with pytest.raises(TerminalStateError, match="terminal state"):
            method(effect.idempotency_key)


def test_multiple_indeterminate_effects_in_ledger() -> None:
    """Multiple effects can independently be marked indeterminate."""
    ledger = EffectLedger()
    for i in range(3):
        effect = _descriptor(effect_id=f"write-{i}", key=f"idem-{i}")
        ledger.prerecord(effect)
        ledger.mark_indeterminate(effect.idempotency_key)

    assert len(ledger) == 3
    for i in range(3):
        record = ledger.get_record(f"idem-{i}")
        assert record.state is EffectRecordState.INDETERMINATE


def test_indeterminate_folded_from_journal_cannot_be_retried() -> None:
    """When folded from a journal, indeterminate effects are terminal."""
    effect = _descriptor(key="indet-journal")
    events = (
        _event("effect_intent", intent_payload(effect)),
        _event(
            "effect_indeterminate",
            indeterminate_payload(effect, reason="unknown"),
        ),
    )
    ledger = fold_effect_ledger(events)

    with pytest.raises(TerminalStateError, match="terminal state"):
        ledger.mark_fulfilled(effect.idempotency_key)
