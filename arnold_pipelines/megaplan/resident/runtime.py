"""Reusable resident runtime seams for durable chat orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from arnold_pipelines.megaplan.schemas import Message, ProgressEvent, ResidentConversation, SystemLog
from arnold_pipelines.megaplan.store import ProgressEventInput, ResidentConversationInput, Store, deterministic_idempotency_key
from arnold_pipelines.megaplan.schemas.base import utc_now
from arnold_pipelines.megaplan.model_seam import render_step_message
from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
from arnold.execution.step_invocation import StepInvocation

from agentbox.redaction import redact_text

from .agent_loop import AgentRequest, AgentResponse, AgentRunner
from .auth import AuthorizationSubject, ResidentAuthorizer
from .cloud import CloudToolRequest
from .coalescing import AsyncBurstCoalescer, BurstBatch
from .config import ResidentConfig
from .escalations import EscalationAnswerDecision, authorize_escalation_answer, confirm_escalation_resolution
from .profile import MegaplanResidentProfile


@dataclass(frozen=True)
class InboundEvent:
    idempotency_key: str
    conversation_key: str
    subject: AuthorizationSubject
    content: str
    escalation_id: str | None = None
    resume_handler: str | None = None
    target_id: str | None = None
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
        if event.escalation_id:
            repair_data_dir = _repair_data_dir_from_config(self.config)
            if repair_data_dir is None:
                self.emitter.log_system_event(
                    level="warn",
                    category="system",
                    event_type="escalation_answer_unauthorized",
                    message="Escalation answer denied before resident mutation",
                    details={
                        "reason": "repair_data_dir_unavailable",
                        "escalation_id": event.escalation_id,
                        "user_id": event.subject.user_id,
                        "channel_id": event.subject.channel_id,
                    },
                    idempotency_key=deterministic_idempotency_key(
                        "resident-escalation-denial",
                        event.idempotency_key,
                        "repair_data_dir_unavailable",
                    ),
                )
                return
            escalation_decision = authorize_escalation_answer(
                authorizer=self.authorizer,
                subject=event.subject,
                action="escalation_reply",
                escalation_id=event.escalation_id,
                repair_data_dir=repair_data_dir,
                audit_sink=self.emitter,
                idempotency_key=event.idempotency_key,
            )
            if not escalation_decision.allowed:
                return
            if event.resume_handler or (escalation_decision.target and escalation_decision.target.resume_handler):
                handled = await self._handle_escalation_resolution(event, escalation_decision, repair_data_dir)
                if handled:
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
        burst = tuple({"role": "user", "content": item.event.content} for item in items)
        history = self._build_history(conversation.id, exclude_ids=message_ids)
        request_messages = (*history, *burst)
        model_seam_metadata = self._model_seam_metadata(
            conversation_id=conversation.id,
            messages=request_messages,
            system_prompt=system_prompt,
            hot_context=hot_context,
        )
        request = AgentRequest(
            conversation_id=conversation.id,
            messages=request_messages,
            system_prompt=system_prompt,
            hot_context=hot_context,
            model_seam_metadata=model_seam_metadata,
            subject=items[-1].event.subject,
            escalation_id=items[-1].event.escalation_id,
            resume_handler=items[-1].event.resume_handler,
            target_id=items[-1].event.target_id,
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
            safe_text = redact_text(response.final_text)
            outbound = self.store.create_message(
                epic_id=active_epic_id,
                conversation_id=conversation.id,
                direction="outbound",
                content=safe_text,
                bot_turn_id=turn.id,
                idempotency_key=deterministic_idempotency_key("resident-outbound", turn.id, "final"),
            )
            final_message_id = outbound.id
            await self.outbound.send(
                OutboundMessage(
                    conversation_key=conversation.conversation_key,
                    content=safe_text,
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

    async def _handle_escalation_resolution(
        self,
        event: InboundEvent,
        decision: EscalationAnswerDecision,
        repair_data_dir: str,
    ) -> bool:
        target = decision.target
        if target is None or event.escalation_id is None:
            return False
        resume_handler = (event.resume_handler or target.resume_handler or "").strip()
        if not resume_handler:
            return False

        confirmation = confirm_escalation_resolution(
            confirmation_manager=getattr(self.profile, "confirmation_manager", None),
            subject=event.subject,
            escalation_id=event.escalation_id,
            target=target,
            answer_text=event.content,
            resume_handler=resume_handler,
        )
        if not confirmation.allowed:
            if confirmation.confirmation_required and confirmation.exact_phrase:
                await self.outbound.send(
                    OutboundMessage(
                        conversation_key=event.conversation_key,
                        content=f"Confirmation required: {confirmation.exact_phrase}",
                        idempotency_key=deterministic_idempotency_key(
                            "resident-escalation-confirmation",
                            event.idempotency_key,
                            confirmation.request_id or event.escalation_id,
                        ),
                        metadata={
                            "escalation_id": event.escalation_id,
                            "confirmation_required": True,
                            "request_id": confirmation.request_id,
                        },
                    )
                )
            return True

        lock_dir = _repair_lock_dir_from_config(self.config, target.session, repair_data_dir)
        from arnold_pipelines.megaplan.cloud.human_blockers import EscalationLedgerWriter, clear_needs_human_marker
        from arnold_pipelines.megaplan.cloud.repair_lock import acquire_repair_lock, release_repair_lock

        lock = acquire_repair_lock(
            lock_dir,
            session=f"resident-escalation:{target.session}",
            target_id=target.target_id,
            extra={"escalation_id": event.escalation_id, "resume_handler": resume_handler},
            is_pid_live=_pid_is_live,
        )
        if not lock.acquired:
            self.emitter.log_system_event(
                level="warn",
                category="system",
                event_type="escalation_resume_deferred",
                message="Escalation answer confirmed but repair lock is busy",
                details={
                    "escalation_id": event.escalation_id,
                    "session": target.session,
                    "lock_status": lock.status,
                    "lock_dir": str(lock_dir),
                },
                idempotency_key=deterministic_idempotency_key(
                    "resident-escalation-lock-busy",
                    event.idempotency_key,
                    lock.status,
                ),
            )
            return True

        writer = EscalationLedgerWriter()
        writer.enable(repair_data_dir)
        resume_status = "unsupported_handler"
        try:
            writer.write_answered(
                target.session,
                escalation_id=event.escalation_id,
                responder_user_id=event.subject.user_id,
                channel_id=event.subject.channel_id or "",
                message_id=_optional_string(event.raw.get("discord_message_id")) or "",
                extra={"resume_handler": resume_handler},
            )
            marker_path = Path(repair_data_dir) / f"{target.session}.needs-human.json"
            if resume_handler == "cloud_resume":
                cloud_result = await self.profile.cloud_backend.run(
                    CloudToolRequest(
                        operation="cloud_resume",
                        target_id=target.current_plan or target.target_id,
                        arguments={
                            "plan": target.current_plan or target.target_id,
                            "cloud_yaml": str(self.config.cloud_yaml_path),
                        },
                        confirmed=True,
                    )
                )
                resume_status = cloud_result.classification
                clear_needs_human_marker(marker_path)
            writer.write_resume_attempted(
                target.session,
                escalation_id=event.escalation_id,
                action=resume_handler,
                resume_status=resume_status,
            )
        finally:
            release_repair_lock(lock_dir, owner=lock.owner)
        return True

    def _build_history(self, conversation_id: str, *, exclude_ids: Sequence[str]) -> tuple[dict[str, Any], ...]:
        """Reconstruct the last N prior messages as user/assistant turns for context.

        ``exclude_ids`` drops the current burst, which is already persisted before
        the turn runs, so it is not double-counted as history.
        """
        if self.config.history_window <= 0:
            return ()
        rows = self.store.list_conversation_messages(
            conversation_id,
            limit=self.config.history_window,
            exclude_ids=exclude_ids,
        )
        history: list[dict[str, Any]] = []
        for message in rows:
            content = message.content
            if not (content and content.strip()):
                continue
            role = "user" if message.direction == "inbound" else "assistant"
            history.append({"role": role, "content": content})
        return tuple(history)

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


def _repair_data_dir_from_config(config: ResidentConfig) -> str | None:
    value = getattr(config, "escalation_repair_data_dir", None)
    if value:
        return str(value)
    import os

    for key in ("MEGAPLAN_RESIDENT_REPAIR_DATA_DIR", "CLOUD_WATCHDOG_REPAIR_DATA_DIR"):
        candidate = os.environ.get(key, "").strip()
        if candidate:
            return candidate
    return None


def _repair_lock_dir_from_config(config: ResidentConfig, session: str, repair_data_dir: str) -> Path:
    value = getattr(config, "escalation_repair_lock_dir", None)
    if value:
        return Path(value)
    import os

    for key in ("MEGAPLAN_RESIDENT_REPAIR_LOCK_DIR", "CLOUD_WATCHDOG_REPAIR_LOCK_DIR"):
        candidate = os.environ.get(key, "").strip()
        if candidate:
            return Path(candidate)
    safe_session = "".join(ch if ch.isalnum() or ch in "_.-" else "-" for ch in session)
    return Path(repair_data_dir) / f"{safe_session}.repair-loop.lock"


def _pid_is_live(pid: int) -> bool:
    import os

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
