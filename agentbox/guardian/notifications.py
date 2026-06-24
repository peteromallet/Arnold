"""Guardian material-transition notifications through resident outbound."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol

from arnold.runtime.durable_ops import OperationNotFound

from agentbox.config import AgentBoxConfig
from agentbox.guardian.model import GuardianInspectionResult
from agentbox.guardian.state import GuardianStateStore
from agentbox.operations import open_operation_store


class OutboundSink(Protocol):
    """Async sink for outbound resident messages."""

    async def send(self, message: "OutboundMessage") -> None:
        ...


@dataclass(frozen=True)
class OutboundMessage:
    """Resident outbound message shape used by Guardian."""

    conversation_key: str
    content: str
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardianNotifier:
    """Emit idempotent material-transition notifications for operations."""

    store: Any | None = None
    outbound: OutboundSink | None = None
    operation_store: Any | None = None
    config: AgentBoxConfig | None = None
    state_store: GuardianStateStore | None = None

    async def notify_completed(
        self,
        operation_id: str,
        result: GuardianInspectionResult,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        return await self._notify(
            operation_id,
            transition="completed",
            result=result,
            now=now,
        )

    async def notify_failed(
        self,
        operation_id: str,
        result: GuardianInspectionResult,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        return await self._notify(
            operation_id,
            transition="failed",
            result=result,
            now=now,
        )

    async def notify_needs_attention(
        self,
        operation_id: str,
        result: GuardianInspectionResult,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        return await self._notify(
            operation_id,
            transition="needs_peter",
            result=result,
            now=now,
        )

    async def _notify(
        self,
        operation_id: str,
        transition: str,
        result: GuardianInspectionResult,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        timestamp = now or datetime.now(UTC)
        notification_key = f"{operation_id}:{transition}"

        state_store = self._state_store()
        if state_store.notification_was_sent(operation_id, notification_key):
            return None

        metadata = self._operation_metadata(operation_id)
        if metadata.get("guardian_notifications_disabled"):
            return None

        conversation_id = metadata.get("guardian_notification_conversation_id")
        if not conversation_id or self.store is None:
            return None

        conversation = self.store.load_resident_conversation(conversation_id)
        if conversation is None:
            return None

        conversation_key = conversation.conversation_key
        content = self._message_content(operation_id, transition, result)

        message = self.store.create_message(
            epic_id=None,
            conversation_id=conversation.id,
            direction="outbound",
            content=content,
            idempotency_key=notification_key,
        )

        self.store.update_resident_conversation(
            conversation.id,
            last_outbound_message_id=message.id,
            delivery_cursor=message.id,
            last_active_at=timestamp,
            idempotency_key=f"guardian:{notification_key}",
        )

        self._mark_operation_notification(
            operation_id,
            transition,
            message.id,
            timestamp,
        )

        state_store.mark_notification_sent(operation_id, notification_key, now=timestamp)

        if self.outbound is not None:
            await self.outbound.send(
                OutboundMessage(
                    conversation_key=conversation_key,
                    content=content,
                    idempotency_key=notification_key,
                    metadata={
                        "conversation_id": conversation.id,
                        "message_id": message.id,
                        "operation_id": operation_id,
                        "transition": transition,
                    },
                )
            )

        return {
            "operation_id": operation_id,
            "transition": transition,
            "message_id": message.id,
        }

    def _operation_metadata(self, operation_id: str) -> dict[str, Any]:
        if self.operation_store is not None:
            try:
                run = self.operation_store.load_operation_run(operation_id)
                return dict(run.metadata)
            except OperationNotFound:
                return {}
        if self.config is not None:
            try:
                run = open_operation_store(self.config).load_operation_run(operation_id)
                return dict(run.metadata)
            except OperationNotFound:
                return {}
        return {}

    def _mark_operation_notification(
        self,
        operation_id: str,
        transition: str,
        message_id: str,
        timestamp: datetime,
    ) -> None:
        metadata = {
            "guardian_notifications": {
                transition: {
                    "message_id": message_id,
                    "sent_at": timestamp.isoformat(),
                }
            }
        }
        state_store = self._state_store()
        try:
            state_store.merge_operation_metadata(operation_id, metadata)
        except OperationNotFound:
            pass
        except OperationLockConflict:
            for _ in range(3):
                try:
                    state_store.merge_operation_metadata(operation_id, metadata)
                    break
                except OperationLockConflict:
                    continue

    def _state_store(self) -> GuardianStateStore:
        if self.state_store is not None:
            return self.state_store
        if self.config is not None:
            return GuardianStateStore(self.config)
        raise RuntimeError("GuardianNotifier requires config or state_store")

    def _message_content(
        self,
        operation_id: str,
        transition: str,
        result: GuardianInspectionResult,
    ) -> str:
        summaries = {
            "completed": f"Operation {operation_id} completed.",
            "failed": f"Operation {operation_id} failed: {result.summary}",
            "needs_peter": f"Operation {operation_id} needs your input: {result.summary}",
        }
        return summaries.get(transition, f"Operation {operation_id}: {result.summary}")


__all__ = [
    "GuardianNotifier",
    "OutboundMessage",
    "OutboundSink",
]
