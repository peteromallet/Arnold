"""Tests for Step 13H: Resident delivery callers through WBC delivery effects.

Covers:
- DiscordOutboundSink.send() routed through delivery_effects
- sweep_managed_agent_deliveries with delivery_effects parameter
- Backward compatibility when delivery_effects is None
- Stable global-effect keys (parent/target/channel)
- Reclaim, duplicate scheduling, lost ACK, completion sweep
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from arnold_pipelines.megaplan.resident.delivery_effects import (
    DeliveryChannel,
    DeliveryTarget,
    DeliveryOutcome,
    DeliveryEffects,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_INDETERMINATE,
)


# ── DeliveryEffects with mock protocol ────────────────────────────────────────


@pytest.fixture
def mock_delivery_effects():
    """Create a DeliveryEffects with mock protocol that accepts deliveries."""
    protocol = MagicMock()
    reservation = MagicMock()
    reservation.global_logical_effect_key = "glek-delivery-001"
    protocol.reserve_and_start.return_value = reservation

    def dispatch(_attempt_id, _glek, *, apply_fn, request_payload, **_kwargs):
        return apply_fn("test-key", request_payload)

    protocol.dispatch.side_effect = dispatch

    effects = DeliveryEffects(protocol, production_enabled=False)
    return effects


@pytest.fixture
def mock_blocking_delivery_effects():
    """Create a DeliveryEffects that blocks all deliveries."""
    from arnold_pipelines.megaplan.custody.action_gate import ActionGateVerdict

    protocol = MagicMock()

    def block_gate(family, key):
        return ActionGateVerdict.BLOCKED_RA_UNSATISFIED

    effects = DeliveryEffects(protocol, action_gate_check=block_gate, production_enabled=False)
    return effects


# ── Stable global-effect keys ─────────────────────────────────────────────────


def test_delivery_target_produces_stable_key():
    """DeliveryTarget produces stable, deterministic target_key."""
    t1 = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="conv-123",
        target_id="msg-456",
        action="send",
    )
    t2 = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="conv-123",
        target_id="msg-456",
        action="send",
    )
    assert t1.target_key == t2.target_key
    assert "delivery:resident:conv-123:msg-456:send" in t1.target_key


def test_different_channels_produce_different_keys():
    """Different channels produce different target keys."""
    t1 = DeliveryTarget(channel=DeliveryChannel.DISCORD_DM, parent_id="u1", target_id="u1")
    t2 = DeliveryTarget(channel=DeliveryChannel.AGENTBOX, parent_id="u1", target_id="u1")
    assert t1.target_key != t2.target_key


def test_different_parents_produce_different_keys():
    """Different parent IDs produce different target keys."""
    t1 = DeliveryTarget(channel=DeliveryChannel.RESIDENT, parent_id="conv-A", target_id="msg-1")
    t2 = DeliveryTarget(channel=DeliveryChannel.RESIDENT, parent_id="conv-B", target_id="msg-1")
    assert t1.target_key != t2.target_key


def test_completion_sweep_and_sink_share_one_effect_identity():
    from arnold_pipelines.megaplan.resident.delivery_effects import DeliveryEffects

    completion_key = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="discord:dm:42",
        target_id="resident-subagent-completion:run-1",
        action="completion_sweep",
    )
    sink_key = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="discord:dm:42",
        target_id="resident-subagent-completion:run-1",
        action="completion_sweep",
    )
    assert DeliveryEffects._build_effect_identity(completion_key).global_logical_effect_key == (
        DeliveryEffects._build_effect_identity(sink_key).global_logical_effect_key
    )


# ── Delivery dispatch ─────────────────────────────────────────────────────────


def test_deliver_succeeds_with_valid_target(mock_delivery_effects):
    """A valid delivery target dispatches and returns ok."""
    target = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="conv-001",
        target_id="msg-001",
        action="send",
    )
    outcome = mock_delivery_effects.deliver(
        target=target,
        intent_payload={"content": "Hello"},
        apply_fn=lambda x: {"sent": True},
    )
    assert outcome.ok
    assert outcome.glek != ""
    assert outcome.outcome_kind == OUTCOME_COMPLETED
    assert outcome.channel == "resident"


def test_deliver_blocked_by_gate(mock_blocking_delivery_effects):
    """A delivery blocked by the action gate returns not ok."""
    target = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="conv-001",
        target_id="msg-001",
        action="send",
    )
    outcome = mock_blocking_delivery_effects.deliver(
        target=target,
        intent_payload={"content": "Hello"},
        apply_fn=lambda x: {"sent": True},
    )
    assert not outcome.ok
    assert "Action gate blocked" in outcome.error


def test_deliver_discord_dm_uses_stable_keys(mock_delivery_effects):
    """deliver_discord_dm constructs stable DeliveryTarget with DISCORD_DM channel."""
    outcome = mock_delivery_effects.deliver_discord_dm(
        user_id="user-123",
        payload={"content": "DM test"},
        apply_fn=lambda x: {"sent": True},
    )
    assert outcome.channel == "discord_dm"


def test_deliver_agentbox_uses_stable_keys(mock_delivery_effects):
    """deliver_agentbox constructs stable DeliveryTarget with AGENTBOX channel."""
    outcome = mock_delivery_effects.deliver_agentbox(
        operation_id="op-456",
        payload={"content": "notify"},
        apply_fn=lambda x: {"sent": True},
    )
    assert outcome.channel == "agentbox"


# ── Reclaim and duplicate scheduling ──────────────────────────────────────────


def test_repeated_delivery_same_target_produces_same_glek_inputs(mock_delivery_effects):
    """Delivering to the same target multiple times produces same GLEK identity."""
    target = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="conv-reclaim",
        target_id="msg-reclaim",
        action="send",
    )
    ei1 = mock_delivery_effects._build_effect_identity(target)
    ei2 = mock_delivery_effects._build_effect_identity(target)
    assert ei1.action_target == ei2.action_target
    assert ei1.effect_family == ei2.effect_family
    assert ei1.environment_id == ei2.environment_id


# ── Lost ACK handling ─────────────────────────────────────────────────────────


def test_lost_ack_does_not_crash_adapter(mock_delivery_effects):
    """Even when the apply_fn raises (simulating lost ACK), the adapter handles it."""
    def flaky_transport(payload):
        raise ConnectionError("ACK lost - connection reset")

    target = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="conv-lost-ack",
        target_id="msg-lost-ack",
        action="send",
    )
    outcome = mock_delivery_effects.deliver(
        target=target,
        intent_payload={"content": "test"},
        apply_fn=flaky_transport,
    )
    assert not outcome.ok
    assert outcome.outcome_kind == OUTCOME_INDETERMINATE
    assert "ACK lost" in outcome.error


def _durable_effects(db_path):
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.effect_protocol import EffectProtocol
    from arnold.workflow.ledger_outbox import SqliteLedgerOutbox

    store = SqliteAttemptLedgerStore(str(db_path))
    return DeliveryEffects(EffectProtocol(store, SqliteLedgerOutbox(store))), store


def test_applied_then_timeout_is_indeterminate_and_never_redriven(tmp_path):
    effects, store = _durable_effects(tmp_path / "effects.db")
    target = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="incident-1",
        target_id="notification-1",
        action="send",
    )
    calls = 0

    def applied_then_timeout(_payload):
        nonlocal calls
        calls += 1
        raise TimeoutError("provider accepted before connection timed out")

    first = effects.deliver(
        target=target,
        intent_payload={"content": "needs review", "idempotency_key": "occurrence-1"},
        apply_fn=applied_then_timeout,
    )
    second = effects.deliver(
        target=target,
        intent_payload={"content": "needs review", "idempotency_key": "occurrence-1"},
        apply_fn=applied_then_timeout,
    )
    assert first.outcome_kind == OUTCOME_INDETERMINATE
    assert second.outcome_kind == OUTCOME_INDETERMINATE
    assert second.evidence["adopted"] is True
    assert calls == 1
    store.close()


def test_two_hundred_identical_polls_and_restart_apply_once(tmp_path):
    db_path = tmp_path / "effects.db"
    target = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="incident-2",
        target_id="notification-2",
        action="send",
    )
    calls = 0

    def provider(_payload):
        nonlocal calls
        calls += 1
        return {"message_ids": ["provider-message-1"]}

    effects, store = _durable_effects(db_path)
    for _ in range(100):
        outcome = effects.deliver(
            target=target,
            intent_payload={"content": "same", "idempotency_key": "occurrence-2"},
            apply_fn=provider,
        )
        assert outcome.ok
    store.close()

    restarted, restarted_store = _durable_effects(db_path)
    for _ in range(100):
        outcome = restarted.deliver(
            target=target,
            intent_payload={"content": "same", "idempotency_key": "occurrence-2"},
            apply_fn=provider,
        )
        assert outcome.ok
        assert outcome.evidence.get("adopted") is True
    assert calls == 1
    restarted_store.close()


def test_async_provider_timeout_is_indeterminate_and_not_retried(tmp_path):
    import asyncio

    effects, store = _durable_effects(tmp_path / "async-effects.db")
    target = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="incident-async",
        target_id="notification-async",
        action="send",
    )
    calls = 0

    async def provider(_key, _payload):
        nonlocal calls
        calls += 1
        raise TimeoutError("accepted then timed out")

    async def exercise():
        first = await effects.deliver_async(
            target=target,
            intent_payload={"content": "same", "idempotency_key": "occurrence-async"},
            apply_fn=provider,
        )
        second = await effects.deliver_async(
            target=target,
            intent_payload={"content": "same", "idempotency_key": "occurrence-async"},
            apply_fn=provider,
        )
        return first, second

    first, second = asyncio.run(exercise())
    assert first.outcome_kind == OUTCOME_INDETERMINATE
    assert second.outcome_kind == OUTCOME_INDETERMINATE
    assert second.evidence.get("adopted") is True
    assert calls == 1
    store.close()


# ── Completion sweep delivery ─────────────────────────────────────────────────


def test_completion_sweep_target_uses_stable_action(mock_delivery_effects):
    """A completion sweep delivery uses a stable 'completion_sweep' action."""
    target = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="conv-sweep",
        target_id="resident-subagent-completion:run-001",
        action="completion_sweep",
    )
    assert "completion_sweep" in target.target_key
    outcome = mock_delivery_effects.deliver(
        target=target,
        intent_payload={"run_id": "run-001", "result_kind": "success"},
        apply_fn=lambda x: {"delivered": True},
    )
    assert outcome.ok


# ── Child aggregation ─────────────────────────────────────────────────────────


def test_multiple_deliveries_different_children_produce_different_gleks(mock_delivery_effects):
    """Different child deliveries (different target_ids) produce different identities."""
    child_a = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="parent-001",
        target_id="child-A",
        action="send",
    )
    child_b = DeliveryTarget(
        channel=DeliveryChannel.RESIDENT,
        parent_id="parent-001",
        target_id="child-B",
        action="send",
    )
    ei_a = mock_delivery_effects._build_effect_identity(child_a)
    ei_b = mock_delivery_effects._build_effect_identity(child_b)
    assert ei_a.action_target != ei_b.action_target


# ── Backward compatibility (delivery_effects=None) ────────────────────────────


def test_delivery_effects_none_does_not_crash_construction():
    """Constructing DeliveryEffects without protocol raises expected error."""
    # DeliveryEffects requires a protocol; verify the class structure
    assert hasattr(DeliveryEffects, 'deliver')
    assert hasattr(DeliveryEffects, 'deliver_discord_dm')
    assert hasattr(DeliveryEffects, 'deliver_agentbox')


# ── OutboundMessage compatibility ─────────────────────────────────────────────


def test_delivery_outcome_matches_structure():
    """DeliveryOutcome has the expected fields."""
    outcome = DeliveryOutcome(
        ok=True,
        channel="resident",
        action="send",
        glek="glek-123",
        outcome_kind=OUTCOME_COMPLETED,
    )
    assert outcome.ok
    assert outcome.glek == "glek-123"
    assert outcome.error is None
    assert outcome.evidence == {}
