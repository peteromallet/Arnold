from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from arnold.runtime.durable_ops import OperationState
from agentbox.config import AgentBoxConfig
from agentbox.guardian.model import (
    GuardianInspectionResult,
    GuardianMaterialTransition,
    GuardianOutcome,
)
from agentbox.guardian.notifications import GuardianNotifier, OutboundMessage
from agentbox.guardian.state import GuardianStateStore
from agentbox.operations import create_agentbox_operation, load_agentbox_operation, update_agentbox_operation
from arnold_pipelines.megaplan.store import FileStore, ResidentConversationInput


@dataclass
class FakeOutboundSink:
    sent: list[OutboundMessage] = field(default_factory=list)

    async def send(self, message: OutboundMessage) -> None:
        self.sent.append(message)


def _result(
    operation_id: str,
    transition: GuardianMaterialTransition,
    summary: str = "summary",
) -> GuardianInspectionResult:
    outcome = {
        GuardianMaterialTransition.COMPLETED: GuardianOutcome.OK,
        GuardianMaterialTransition.FAILED: GuardianOutcome.FAILED,
        GuardianMaterialTransition.STALLED: GuardianOutcome.ESCALATED,
    }.get(transition, GuardianOutcome.OK)
    return GuardianInspectionResult(
        operation_id=operation_id,
        outcome=outcome,
        material_transition=transition,
        summary=summary,
    )


def test_completion_notification_emitted_once(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        ),
        idempotency_key="conversation-1",
    )
    create_agentbox_operation(
        config,
        "chain-complete",
        operation_type="megaplan_chain",
        command=("fake",),
        metadata={
            "guardian_notification_conversation_id": conversation.id,
            "guardian_notifications_disabled": False,
        },
    )
    update_agentbox_operation(config, "chain-complete", state=OperationState.RUNNING)
    outbound = FakeOutboundSink()
    notifier = GuardianNotifier(
        store=store,
        outbound=outbound,
        config=config,
    )

    asyncio.run(notifier.notify_completed(
        "chain-complete",
        _result("chain-complete", GuardianMaterialTransition.COMPLETED),
    ))

    assert len(outbound.sent) == 1
    assert outbound.sent[0].conversation_key == "discord:guild:g1:channel:c1"
    assert "completed" in outbound.sent[0].content

    asyncio.run(notifier.notify_completed(
        "chain-complete",
        _result("chain-complete", GuardianMaterialTransition.COMPLETED),
    ))

    assert len(outbound.sent) == 1


def test_needs_peter_notification_uses_conversation_key(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        ),
        idempotency_key="conversation-1",
    )
    create_agentbox_operation(
        config,
        "chain-blocked",
        operation_type="megaplan_chain",
        command=("fake",),
        metadata={
            "guardian_notification_conversation_id": conversation.id,
            "guardian_notifications_disabled": False,
        },
    )
    update_agentbox_operation(config, "chain-blocked", state=OperationState.RUNNING)
    outbound = FakeOutboundSink()
    notifier = GuardianNotifier(
        store=store,
        outbound=outbound,
        config=config,
    )

    asyncio.run(notifier.notify_needs_attention(
        "chain-blocked",
        _result("chain-blocked", GuardianMaterialTransition.STALLED, "needs input"),
    ))

    assert len(outbound.sent) == 1
    assert outbound.sent[0].conversation_key == "discord:guild:g1:channel:c1"
    assert "needs your input" in outbound.sent[0].content


def test_final_failure_notification_after_retry_cap(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        ),
        idempotency_key="conversation-1",
    )
    create_agentbox_operation(
        config,
        "chain-failed",
        operation_type="megaplan_chain",
        command=("fake",),
        metadata={
            "guardian_notification_conversation_id": conversation.id,
            "guardian_notifications_disabled": False,
        },
    )
    update_agentbox_operation(config, "chain-failed", state=OperationState.FAILED)
    outbound = FakeOutboundSink()
    notifier = GuardianNotifier(
        store=store,
        outbound=outbound,
        config=config,
    )

    asyncio.run(notifier.notify_failed(
        "chain-failed",
        _result("chain-failed", GuardianMaterialTransition.FAILED, "gave up"),
    ))

    assert len(outbound.sent) == 1
    assert "failed" in outbound.sent[0].content
    assert "gave up" in outbound.sent[0].content


def test_idempotent_replay_produces_no_duplicate_message(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        ),
        idempotency_key="conversation-1",
    )
    create_agentbox_operation(
        config,
        "chain-idem",
        operation_type="megaplan_chain",
        command=("fake",),
        metadata={
            "guardian_notification_conversation_id": conversation.id,
            "guardian_notifications_disabled": False,
        },
    )
    update_agentbox_operation(config, "chain-idem", state=OperationState.RUNNING)
    outbound = FakeOutboundSink()
    notifier = GuardianNotifier(
        store=store,
        outbound=outbound,
        config=config,
    )

    result = _result("chain-idem", GuardianMaterialTransition.COMPLETED)
    asyncio.run(notifier.notify_completed("chain-idem", result))
    asyncio.run(notifier.notify_completed("chain-idem", result))
    asyncio.run(notifier.notify_completed("chain-idem", result))

    assert len(outbound.sent) == 1


def test_no_notification_when_disabled(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        ),
        idempotency_key="conversation-1",
    )
    create_agentbox_operation(
        config,
        "chain-disabled",
        operation_type="megaplan_chain",
        command=("fake",),
        metadata={
            "guardian_notification_conversation_id": conversation.id,
            "guardian_notifications_disabled": True,
        },
    )
    update_agentbox_operation(config, "chain-disabled", state=OperationState.RUNNING)
    outbound = FakeOutboundSink()
    notifier = GuardianNotifier(
        store=store,
        outbound=outbound,
        config=config,
    )

    asyncio.run(notifier.notify_completed(
        "chain-disabled",
        _result("chain-disabled", GuardianMaterialTransition.COMPLETED),
    ))

    assert outbound.sent == []


def test_no_notification_when_conversation_missing(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileStore(tmp_path / "store")
    create_agentbox_operation(
        config,
        "chain-missing-conversation",
        operation_type="megaplan_chain",
        command=("fake",),
        metadata={
            "guardian_notification_conversation_id": "missing",
            "guardian_notifications_disabled": False,
        },
    )
    update_agentbox_operation(config, "chain-missing-conversation", state=OperationState.RUNNING)
    outbound = FakeOutboundSink()
    notifier = GuardianNotifier(
        store=store,
        outbound=outbound,
        config=config,
    )

    asyncio.run(notifier.notify_completed(
        "chain-missing-conversation",
        _result("chain-missing-conversation", GuardianMaterialTransition.COMPLETED),
    ))

    assert outbound.sent == []


def test_notification_does_not_require_active_operator_turn(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        ),
        idempotency_key="conversation-1",
    )
    create_agentbox_operation(
        config,
        "chain-no-turn",
        operation_type="megaplan_chain",
        command=("fake",),
        metadata={
            "guardian_notification_conversation_id": conversation.id,
            "guardian_notifications_disabled": False,
        },
    )
    update_agentbox_operation(config, "chain-no-turn", state=OperationState.RUNNING)
    outbound = FakeOutboundSink()
    notifier = GuardianNotifier(
        store=store,
        outbound=outbound,
        config=config,
    )

    asyncio.run(notifier.notify_completed(
        "chain-no-turn",
        _result("chain-no-turn", GuardianMaterialTransition.COMPLETED),
    ))

    assert len(outbound.sent) == 1
    assert store.latest_outbound_message() is not None
    assert store.latest_outbound_message().conversation_id == conversation.id
