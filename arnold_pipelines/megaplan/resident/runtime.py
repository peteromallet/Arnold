"""Reusable resident runtime seams for durable chat orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from arnold_pipelines.megaplan.schemas import Message, ProgressEvent, ResidentConversation, SystemLog
from arnold_pipelines.megaplan.store import ProgressEventInput, ResidentConversationInput, Store, deterministic_idempotency_key
from arnold_pipelines.megaplan.schemas.base import utc_now
from arnold_pipelines.megaplan.model_seam import render_step_message
from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
from arnold.pipeline import StepInvocation

from .agent_loop import AgentRequest, AgentResponse, AgentRunner
from .auth import AuthorizationSubject, ResidentAuthorizer
from .coalescing import AsyncBurstCoalescer, BurstBatch
from .config import ResidentConfig
from .profile import MegaplanResidentProfile


@dataclass(frozen=True)
class InboundEvent:
    idempotency_key: str
    conversation_key: str
    subject: AuthorizationSubject
    content: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundMessage:
    conversation_key: str
    content: str
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class OutboundSink(Protocol):
    async def send(self, message: OutboundMessage) -> None:
        """Deliver a resident response."""


class EmitProtocol(Protocol):
    """Resident event-write surface exposed by the shared Store emit path."""

    def log_system_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        turn_id: str | None = None,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> SystemLog:
        ...

    def append_progress_event(
        self,
        event: ProgressEventInput,
        *,
        idempotency_key: str | None = None,
    ) -> ProgressEvent:
        ...


@dataclass(frozen=True)
class PersistedInboundEvent:
    event: InboundEvent
    conversation: ResidentConversation
    message: Message


class ResidentRuntime:
    """Shared resident flow: authorize, coalesce, run profile, and emit output."""

    def __init__(
        self,
        *,
        config: ResidentConfig,
        authorizer: ResidentAuthorizer,
        store: Store,
        profile: MegaplanResidentProfile,
        runner: AgentRunner,
        outbound: OutboundSink,
    ) -> None:
        self.config = config
        self.authorizer = authorizer
        self.store = store
        self.emitter: EmitProtocol = store
        self.profile = profile
        self.runner = runner
        self.outbound = outbound
        self.coalescer: AsyncBurstCoalescer[str, PersistedInboundEvent] = AsyncBurstCoalescer(
            self._handle_batch,
            idle_delay_s=config.burst_idle_delay_s,
            max_delay_s=config.burst_max_delay_s,
        )

    async def receive(self, event: InboundEvent) -> None:
        decision = self.authorizer.authorize_inbound(event.subject)
        if not decision.allowed:
            if decision.audit is not None:
                self.emitter.log_system_event(
                    level="warn",
                    category="system",
                    event_type="resident_inbound_denied",
                    message="Resident inbound event denied before execution",
                    details={"reason": decision.reason, "audit": decision.audit},
                    idempotency_key=deterministic_idempotency_key("resident-denial", event.idempotency_key),
                )
            return
        persisted = self._persist_inbound_event(event)
        if persisted.message.bot_turn_id is not None:
            return
        await self.coalescer.submit(persisted.conversation.id, persisted)

    async def recover_abandoned_turns(self) -> int:
        recovered = 0
        for turn in self.store.find_abandoned_turns(int(self.config.stale_turn_timeout_s)):
            self.store.update_turn(
                turn.id,
                status="abandoned",
                warnings_issued=list(turn.warnings_issued or []) + ["recovered as abandoned on resident startup"],
                idempotency_key=deterministic_idempotency_key("resident-turn-abandoned", turn.id),
            )
            recovered += 1
        return recovered

    def _persist_inbound_event(self, event: InboundEvent) -> PersistedInboundEvent:
        raw = dict(event.raw)
        conversation = self.store.upsert_resident_conversation(
            ResidentConversationInput(
                transport="discord",
                conversation_key=event.conversation_key,
                active_epic_id=_optional_string(raw.get("active_epic_id")),
                guild_id=event.subject.guild_id,
                channel_id=event.subject.channel_id,
                thread_id=_optional_string(raw.get("thread_id")),
                dm_user_id=_optional_string(raw.get("dm_user_id")),
                metadata={"last_subject_user_id": event.subject.user_id, **dict(raw.get("conversation_metadata") or {})},
            ),
            idempotency_key=deterministic_idempotency_key("resident-conversation", event.conversation_key),
        )
        message = self.store.create_message(
            epic_id=conversation.active_epic_id,
            conversation_id=conversation.id,
            direction="inbound",
            content=event.content,
            discord_message_id=_optional_string(raw.get("discord_message_id")),
            idempotency_key=event.idempotency_key,
            has_code_attachment=bool(raw.get("has_code_attachment", False)),
            has_image_attachment=bool(raw.get("has_image_attachment", False)),
            was_voice_message=bool(raw.get("was_voice_message", False)),
            audio_storage_url=_optional_string(raw.get("audio_storage_url")),
            transcription_metadata=_optional_dict(raw.get("transcription_metadata")),
        )
        self.store.update_resident_conversation(
            conversation.id,
            last_inbound_message_id=message.id,
            delivery_cursor=message.id,
            last_active_at=utc_now(),
            idempotency_key=deterministic_idempotency_key("resident-conversation-inbound", conversation.id, message.id),
        )
        conversation = self.store.load_resident_conversation(conversation.id) or conversation
        return PersistedInboundEvent(event=event, conversation=conversation, message=message)

    async def _handle_batch(self, batch: BurstBatch[str, PersistedInboundEvent]) -> None:
        items = _dedupe_persisted_events(batch.items)
        if not items:
            return
        conversation = self.store.load_resident_conversation(batch.key) or items[-1].conversation
        active_epic_id = conversation.active_epic_id
        system_prompt = self.profile.system_prompt()
        hot_context = await self.profile.load_hot_context(conversation.id)
        message_ids = [item.message.id for item in items]
        turn = self.store.create_turn(
            epic_id=active_epic_id,
            triggered_by_message_ids=message_ids,
            prompt_snapshot={
                "system_prompt": system_prompt,
                "message_count": len(items),
                "tool_catalog": self.profile.tools().as_schema_catalog(),
            },
            prompt_version=hot_context.get("prompt_version") if isinstance(hot_context, dict) else None,
            state_at_turn=hot_context,
            model_version=self.config.model_name,
            idempotency_key=deterministic_idempotency_key("resident-turn", conversation.id, *message_ids),
        )
        for item in items:
            self.store.update_message(
                item.message.id,
                bot_turn_id=turn.id,
                in_burst_with=[msg_id for msg_id in message_ids if msg_id != item.message.id] or None,
                idempotency_key=deterministic_idempotency_key("resident-message-turn", item.message.id, turn.id),
            )
        model_seam_metadata = self._model_seam_metadata(
            conversation_id=conversation.id,
            messages=tuple({"role": "user", "content": item.event.content} for item in items),
            system_prompt=system_prompt,
            hot_context=hot_context,
        )
        request = AgentRequest(
            conversation_id=conversation.id,
            messages=tuple({"role": "user", "content": item.event.content} for item in items),
            system_prompt=system_prompt,
            hot_context=hot_context,
            model_seam_metadata=model_seam_metadata,
            subject=items[-1].event.subject,
        )
        try:
            response = await self.runner.run(request, self.profile.tools())
        except Exception as exc:
            self.store.update_turn(
                turn.id,
                status="failed",
                warnings_issued=[f"{exc.__class__.__name__}: {exc}"],
                idempotency_key=deterministic_idempotency_key("resident-turn-failed", turn.id),
            )
            raise
        self._record_tool_calls(turn.id, response)
        final_message_id = None
        if response.final_text:
            outbound = self.store.create_message(
                epic_id=active_epic_id,
                conversation_id=conversation.id,
                direction="outbound",
                content=response.final_text,
                bot_turn_id=turn.id,
                idempotency_key=deterministic_idempotency_key("resident-outbound", turn.id, "final"),
            )
            final_message_id = outbound.id
            await self.outbound.send(
                OutboundMessage(
                    conversation_key=conversation.conversation_key,
                    content=response.final_text,
                    idempotency_key=outbound.idempotency_key,
                    metadata={"conversation_id": conversation.id, "message_id": outbound.id, "turn_id": turn.id},
                )
            )
            self.store.update_resident_conversation(
                conversation.id,
                last_outbound_message_id=outbound.id,
                delivery_cursor=outbound.id,
                last_active_at=utc_now(),
                idempotency_key=deterministic_idempotency_key("resident-conversation-outbound", conversation.id, outbound.id),
            )
        self.store.update_turn(
            turn.id,
            status="completed",
            final_output_message_id=final_message_id,
            message_sent=bool(final_message_id),
            idempotency_key=deterministic_idempotency_key("resident-turn-completed", turn.id),
        )

    def _record_tool_calls(self, turn_id: str, response: AgentResponse) -> None:
        for record in response.tool_calls:
            self.store.record_tool_call(
                turn_id=turn_id,
                tool_name=record.tool_name,
                operation_kind=record.operation_kind,
                arguments=record.arguments,
                result=record.result,
                duration_ms=record.duration_ms,
                idempotency_key=deterministic_idempotency_key("resident-tool-call", turn_id, record.id),
            )

    def _model_seam_metadata(
        self,
        *,
        conversation_id: str,
        messages: tuple[dict[str, Any], ...],
        system_prompt: str,
        hot_context: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            normalized_model, agent_kwargs = resolve_model(self.config.model_name)
        except Exception:
            if ":" in self.config.model_name:
                raise
            normalized_model, agent_kwargs = self.config.model_name, {}
        rendered = render_step_message(
            StepInvocation(
                kind="model",
                metadata={
                    "tier": "non_enforced",
                    "worker": "resident",
                    "model": normalized_model,
                    "normalized_model": normalized_model,
                    "system": system_prompt,
                    "messages": messages,
                    "history": messages,
                    "hot_context": hot_context,
                    "prompt": "\n".join(str(message.get("content", "")) for message in messages),
                },
            )
        )
        return {
            "conversation_id": conversation_id,
            "validation_step": "resident",
            "tier": "non_enforced",
            "model": normalized_model,
            "normalized_model": normalized_model,
            "agent_kwargs": agent_kwargs,
            "rendered": rendered.to_json(),
        }


def _dedupe_persisted_events(items: Sequence[PersistedInboundEvent]) -> tuple[PersistedInboundEvent, ...]:
    seen: set[str] = set()
    deduped: list[PersistedInboundEvent] = []
    for item in items:
        if item.message.id in seen:
            continue
        seen.add(item.message.id)
        deduped.append(item)
    return tuple(deduped)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_dict(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None
