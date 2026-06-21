from __future__ import annotations

from arnold.kernel import (
    ControlTarget,
    ControlTransition,
    ControlTransitionType,
    EffectDescriptor,
    EffectKind,
    EffectLedger,
    derive_idempotency_key,
)


def test_control_transition_carries_overlay_fields() -> None:
    key = derive_idempotency_key("run-1", "control", "override")
    transition = ControlTransition(
        transition_type=ControlTransitionType.OVERRIDE,
        source=ControlTarget("node:gate"),
        target=ControlTarget("node:revise"),
        trigger="operator",
        payload_schema_hash="sha256:" + "1" * 64,
        policy_ref="policy:override",
        idempotency_key=key,
    )

    assert transition.idempotency_key == key
    assert transition.target.node_ref == "node:revise"


def test_effect_ledger_deduplicates_prerecorded_effects() -> None:
    key = derive_idempotency_key("run-1", "effect", "write")
    effect = EffectDescriptor(
        effect_id="write-1",
        kind=EffectKind.INTENT,
        target="artifact:report",
        idempotency_key=key,
        payload_schema_hash="sha256:" + "2" * 64,
    )
    ledger = EffectLedger()

    assert ledger.prerecord(effect) is True
    assert ledger.prerecord(effect) is False
    assert ledger.get(key) == effect
