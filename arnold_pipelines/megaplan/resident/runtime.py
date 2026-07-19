"""Reusable resident runtime seams for durable chat orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Protocol

from arnold_pipelines.megaplan.schemas import Message, ProgressEvent, ResidentConversation, SystemLog
from arnold_pipelines.megaplan.store import ProgressEventInput, ResidentConversationInput, Store, deterministic_idempotency_key
from arnold_pipelines.megaplan.schemas.base import utc_now
from arnold_pipelines.megaplan.model_seam import render_step_message
from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
from arnold.execution.step_invocation import StepInvocation

from agentbox.redaction import redact_text

from .agent_loop import (
    AgentRequest,
    AgentResponse,
    AgentRunner,
    AgentTimeoutError,
    durable_launch_run_ids,
    ToolRuntimeContext,
    durable_launch_run_ids,
    execute_registered_tool,
)
from .auth import AuthorizationDecision, AuthorizationSubject, ResidentAuthorizer
from .cloud import CloudToolRequest
from .coalescing import AsyncBurstCoalescer, BurstBatch
from .config import ResidentConfig
from .context_tree import classify_intent_packs
from .escalations import EscalationAnswerDecision, authorize_escalation_answer, confirm_escalation_resolution
from .fix_the_fixer import FIX_THE_FIXER_TOOL
from .profile import MegaplanResidentProfile
from .query_relationship import (
    classify_query_relationship,
    load_query_relationship,
    relationship_store_root,
)
from .reply_chain import build_reply_provenance, render_reply_context
from .timezone import TimezoneService, localize_text_timestamps, timezone_prompt_instruction


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
        project_root: str | Path | None = None,
    ) -> None:
        self.config = config
        self.authorizer = authorizer
        self.store = store
        self.emitter: EmitProtocol = store
        self.profile = profile
        self.runner = runner
        self.outbound = outbound
        self.project_root = Path(
            project_root or getattr(runner, "cwd", None) or Path.cwd()
        ).resolve()
        self.coalescer: AsyncBurstCoalescer[str, PersistedInboundEvent] = AsyncBurstCoalescer(
            self._handle_batch,
            idle_delay_s=config.burst_idle_delay_s,
            max_delay_s=config.burst_max_delay_s,
        )

    async def receive(
        self,
        event: InboundEvent,
        *,
        authorization_decision: AuthorizationDecision | None = None,
    ) -> None:
        decision = authorization_decision or self.authorizer.authorize_inbound(event.subject)
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
        classify_query_relationship(
            store=self.store,
            conversation=persisted.conversation,
            current=persisted.message,
            project_root=self.project_root,
        )
        if await self._route_resident_command(persisted):
            return
        if await self._route_discord_managed_followup(persisted):
            return
        await self.coalescer.submit(persisted.conversation.id, persisted)

    async def _route_resident_command(self, persisted: PersistedInboundEvent) -> bool:
        command = persisted.event.raw.get("resident_command")
        if not isinstance(command, Mapping) or command.get("name") != FIX_THE_FIXER_TOOL:
            return False
        conversation = self.store.load_resident_conversation(persisted.conversation.id)
        conversation = conversation or persisted.conversation
        hot_context = await self.profile.load_hot_context(conversation.id)
        turn = self.store.create_turn(
            epic_id=conversation.active_epic_id,
            triggered_by_message_ids=[persisted.message.id],
            prompt_snapshot={
                "resident_command": FIX_THE_FIXER_TOOL,
                "tool_catalog": self.profile.tools().as_compact_catalog(),
            },
            prompt_version=hot_context.get("prompt_version") if isinstance(hot_context, dict) else None,
            state_at_turn=hot_context,
            model_version="resident-direct-command",
            idempotency_key=deterministic_idempotency_key(
                "resident-command-turn", persisted.message.id, FIX_THE_FIXER_TOOL
            ),
        )
        self.store.update_message(
            persisted.message.id,
            bot_turn_id=turn.id,
            idempotency_key=deterministic_idempotency_key(
                "resident-command-message-turn", persisted.message.id, turn.id
            ),
        )
        discord_message_id = _optional_string(persisted.event.raw.get("discord_message_id"))
        processing_message_ids = [discord_message_id] if discord_message_id else []
        await self._invoke_transport_lifecycle(
            "mark_processing",
            conversation_key=conversation.conversation_key,
            message_ids=processing_message_ids,
            turn_id=turn.id,
        )
        error = _optional_string(command.get("error"))
        processing_continues = False
        if error:
            safe_text = f"I couldn't launch fix-the-fixer: {error}"
            turn_status = "completed"
        else:
            arguments = command.get("arguments")
            arguments = dict(arguments) if isinstance(arguments, Mapping) else {}
            audit_id = f"resident_command_{turn.id}"
            launch_origin = self._managed_subagent_launch_origin(
                [persisted],
                turn_id=turn.id,
                timezone_name=_timezone_name_from_hot_context(hot_context),
            )
            audit = await execute_registered_tool(
                tools=self.profile.tools(),
                tool_name=FIX_THE_FIXER_TOOL,
                arguments=arguments,
                audit_id=audit_id,
                timeout_s=self.config.model_timeout_s,
                runtime_context=ToolRuntimeContext(
                    conversation_id=conversation.id,
                    subject=persisted.event.subject,
                    launch_origin={**launch_origin, "delegation_id": audit_id},
                    tool_call_id=audit_id,
                ),
            )
            result = audit.result if isinstance(audit.result, dict) else {}
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            run_id = _optional_string(data.get("run_id"))
            run_status = _optional_string(data.get("status"))
            if result.get("ok") is True and run_id and run_status:
                target = str(data.get("target") or arguments.get("target") or "")
                safe_text = (
                    f"Launched one durable fix-the-fixer meta-fixer `{run_id}` for target "
                    f"{json.dumps(target, ensure_ascii=False)}. It has D10/high recovery "
                    "custody and will deliver its evidence-backed result to this request."
                )
                processing_continues = run_status in {"launching", "queued", "running"}
                turn_status = "completed"
            else:
                safe_text = "I couldn't launch fix-the-fixer: " + str(
                    result.get("message") or "the durable launch returned no run receipt"
                )
                turn_status = "failed"
            self._record_tool_calls(
                turn.id,
                AgentResponse(final_text=safe_text, tool_calls=(audit,)),
            )
        safe_text = redact_text(safe_text)
        outbound = self.store.create_message(
            epic_id=conversation.active_epic_id,
            conversation_id=conversation.id,
            direction="outbound",
            content=safe_text,
            bot_turn_id=turn.id,
            idempotency_key=deterministic_idempotency_key(
                "resident-command-outbound", turn.id, FIX_THE_FIXER_TOOL
            ),
        )
        await self.outbound.send(
            OutboundMessage(
                conversation_key=conversation.conversation_key,
                content=safe_text,
                idempotency_key=outbound.idempotency_key,
                metadata={
                    "conversation_id": conversation.id,
                    "message_id": outbound.id,
                    "turn_id": turn.id,
                    "discord_reply_to_message_id": discord_message_id,
                    "discord_processing_message_ids": processing_message_ids,
                    "discord_processing_turn_id": turn.id,
                    "discord_processing_continues": processing_continues,
                },
            )
        )
        self.store.update_resident_conversation(
            conversation.id,
            last_outbound_message_id=outbound.id,
            delivery_cursor=outbound.id,
            last_active_at=utc_now(),
            idempotency_key=deterministic_idempotency_key(
                "resident-command-conversation-outbound", conversation.id, outbound.id
            ),
        )
        self.store.update_turn(
            turn.id,
            status=turn_status,
            final_output_message_id=outbound.id,
            message_sent=True,
            idempotency_key=deterministic_idempotency_key(
                "resident-command-turn-finished", turn.id, turn_status
            ),
        )
        return True

    async def _route_discord_managed_followup(
        self, persisted: PersistedInboundEvent
    ) -> bool:
        """Continue an exact recent managed session or leave normal routing intact."""

        provenance = persisted.message.discord_reply_provenance
        if not isinstance(provenance, Mapping):
            return False
        source_author_id = _optional_string(provenance.get("source_author_id"))
        if source_author_id != persisted.event.subject.user_id:
            return False
        ancestors = provenance.get("ancestors")
        if not isinstance(ancestors, list) or not ancestors:
            return False
        immediate = ancestors[0]
        if not isinstance(immediate, Mapping) or immediate.get("status") != "available":
            return False
        parent_discord_id = _optional_string(immediate.get("message_id"))
        reference_discord_id = _optional_string(
            persisted.event.raw.get("discord_reference_message_id")
        )
        if not parent_discord_id or parent_discord_id != reference_discord_id:
            return False
        # "Reply to their own message" is proven twice: from the immutable
        # adapter-captured ancestor and from the exact stored parent source.
        if _optional_string(immediate.get("author_id")) != source_author_id:
            return False
        parent = self.store.find_conversation_message_by_discord_id(
            persisted.conversation.id, parent_discord_id
        )
        parent_provenance = getattr(parent, "discord_reply_provenance", None)
        if (
            parent is None
            or parent.direction != "inbound"
            or parent.conversation_id != persisted.conversation.id
            or not isinstance(parent_provenance, Mapping)
            or _optional_string(parent_provenance.get("source_author_id"))
            != source_author_id
        ):
            return False

        from .provenance import normalize_delegation_provenance
        from .subagent import (
            SubagentFollowupError,
            find_discord_followup_target,
            follow_up_managed_subagent,
        )

        target = find_discord_followup_target(
            source_record_id=parent.id,
            discord_message_id=parent_discord_id,
            resident_conversation_id=persisted.conversation.id,
            conversation_key=persisted.conversation.conversation_key,
            reply_received_at=persisted.message.sent_at,
            project_root=self.project_root,
        )
        if target is None:
            return False
        timezone_name = TimezoneService(self.store, self.config).resolve(
            user_id=source_author_id,
            conversation=persisted.conversation,
            guild_id=persisted.event.subject.guild_id,
        ).name
        caller_provenance = normalize_delegation_provenance(
            {
                "transport": "discord",
                "applicability": "applicable",
                "resident_conversation_id": persisted.conversation.id,
                "source_record_id": persisted.message.id,
                "conversation_key": persisted.conversation.conversation_key,
                "discord_message_id": persisted.message.discord_message_id,
                "reply_to_message_id": persisted.message.discord_message_id,
                "guild_id": persisted.event.subject.guild_id,
                "channel_id": persisted.event.subject.channel_id,
                "thread_id": _optional_string(
                    persisted.event.raw.get("thread_id")
                ),
                "dm_user_id": _optional_string(
                    persisted.event.raw.get("dm_user_id")
                ),
                "source_kind": "discord_inbound_message",
                "timezone_name": timezone_name,
            }
        )
        try:
            query_relationship = load_query_relationship(
                persisted.message.id,
                store_root=relationship_store_root(self.store, self.project_root),
            )
            result = follow_up_managed_subagent(
                run_id=target.run_id,
                message=persisted.message.content,
                project_dir=self.project_root,
                idempotency_key=persisted.event.idempotency_key,
                caller_provenance=caller_provenance,
                expected_target_source_record_id=parent.id,
                expected_target_discord_message_id=parent_discord_id,
                query_relationship=query_relationship,
            )
        except (SubagentFollowupError, ValueError, OSError) as exc:
            self.emitter.log_system_event(
                level="warn",
                category="system",
                event_type="resident_subagent_followup_fallback",
                message="Managed-session continuation was unsafe; normal resident routing retained",
                details={
                    "source_record_id": persisted.message.id,
                    "parent_source_record_id": parent.id,
                    "target_run_id": target.run_id,
                    "error_class": exc.__class__.__name__,
                    "rejection_reason": " ".join(redact_text(str(exc)).split())[:240],
                },
                idempotency_key=deterministic_idempotency_key(
                    "resident-subagent-followup-fallback", persisted.message.id
                ),
            )
            return False
        await self._invoke_transport_lifecycle(
            "mark_processing",
            conversation_key=persisted.conversation.conversation_key,
            message_ids=[str(persisted.message.discord_message_id)],
            turn_id=f"followup:{result.followup_id}",
        )
        self.emitter.log_system_event(
            level="info",
            category="system",
            event_type="resident_subagent_followup_routed",
            message="Discord reply durably routed to its canonical managed owner",
            details={
                "source_record_id": persisted.message.id,
                "parent_source_record_id": parent.id,
                "target_run_id": target.run_id,
                "lineage_root_run_id": target.lineage_root_run_id,
                "continuation_run_id": result.continuation_run_id,
                "route": result.route,
                "delivery_owner_run_id": result.delivery_owner_run_id,
                "launch_anchor": target.launch_anchor,
                "launch_anchor_field": target.launch_anchor_field,
                "window_seconds": 900,
                "idempotent_replay": result.idempotent_replay,
            },
            idempotency_key=deterministic_idempotency_key(
                "resident-subagent-followup-routed", persisted.message.id
            ),
        )
        return True

    async def recover_abandoned_turns(self) -> int:
        recovered = 0
        for turn in self.store.find_abandoned_turns(int(self.config.stale_turn_timeout_s)):
            self.store.update_turn(
                turn.id,
                status="abandoned",
                warnings_issued=list(turn.warnings_issued or []) + ["recovered as abandoned on resident startup"],
                idempotency_key=deterministic_idempotency_key("resident-turn-abandoned", turn.id),
            )
            await self._notify_abandoned_turn(turn.id, turn.triggered_by_message_ids)
            recovered += 1
        return recovered

    async def recover_restart_interrupted_turns(
        self,
        process_identity: Mapping[str, Any],
    ) -> int:
        """Promptly replay the exact inbound source owned by a completed restart."""

        from agentbox.reset_notifications import (
            claim_restart_interrupted_turns,
            finish_restart_interrupted_turn,
        )

        recovered = 0
        claims = claim_restart_interrupted_turns(process_identity=process_identity)
        turns = {turn.id: turn for turn in self.store.list_recent_turns(n=1000)}
        for claim in claims:
            turn = turns.get(claim.turn_id)
            messages = self.store.load_messages(claim.source_record_ids)
            if (
                turn is None
                or turn.status != "in_progress"
                or not messages
                or any(message.direction != "inbound" for message in messages)
            ):
                finish_restart_interrupted_turn(
                    claim.notification_id, status="skipped"
                )
                continue
            persisted: list[PersistedInboundEvent] = []
            for message in messages:
                if not message.conversation_id or not message.discord_message_id:
                    continue
                conversation = self.store.load_resident_conversation(
                    message.conversation_id
                )
                if conversation is None:
                    continue
                provenance = (
                    message.discord_reply_provenance
                    if isinstance(message.discord_reply_provenance, Mapping)
                    else {}
                )
                author_id = str(
                    provenance.get("source_author_id")
                    or conversation.metadata.get("last_subject_user_id")
                    or ""
                )
                if not author_id:
                    continue
                raw = {
                    "discord_message_id": message.discord_message_id,
                    "thread_id": conversation.thread_id,
                    "dm_user_id": conversation.dm_user_id,
                    "restart_replay_of_turn_id": turn.id,
                    "restart_transaction_id": claim.notification_id,
                }
                event = InboundEvent(
                    idempotency_key=message.idempotency_key
                    or deterministic_idempotency_key(
                        "resident-restart-replay-source", message.id
                    ),
                    conversation_key=conversation.conversation_key,
                    subject=AuthorizationSubject(
                        user_id=author_id,
                        guild_id=conversation.guild_id,
                        channel_id=conversation.channel_id,
                    ),
                    content=message.content,
                    raw=raw,
                )
                persisted.append(
                    PersistedInboundEvent(
                        event=event,
                        conversation=conversation,
                        message=message,
                    )
                )
            if not persisted:
                finish_restart_interrupted_turn(
                    claim.notification_id, status="skipped"
                )
                continue
            conversation = persisted[-1].conversation
            existing_outbound = next(
                (
                    row
                    for row in reversed(
                        self.store.list_conversation_messages(
                            conversation.id, limit=1000
                        )
                    )
                    if row.direction == "outbound" and row.bot_turn_id == turn.id
                ),
                None,
            )
            if existing_outbound is not None:
                source_discord_ids = [
                    str(item.message.discord_message_id)
                    for item in persisted
                    if item.message.discord_message_id
                ]
                try:
                    await self.outbound.send(
                        OutboundMessage(
                            conversation_key=conversation.conversation_key,
                            content=existing_outbound.content,
                            idempotency_key=existing_outbound.idempotency_key,
                            metadata={
                                "conversation_id": conversation.id,
                                "message_id": existing_outbound.id,
                                "turn_id": turn.id,
                                "discord_reply_to_message_id": (
                                    source_discord_ids[-1]
                                    if source_discord_ids
                                    else None
                                ),
                                "discord_processing_message_ids": source_discord_ids,
                                "discord_processing_turn_id": turn.id,
                                "restart_delivery_replay": True,
                            },
                        )
                    )
                except Exception as exc:
                    finish_restart_interrupted_turn(
                        claim.notification_id,
                        status="pending",
                        error_class=exc.__class__.__name__,
                    )
                    continue
                self.store.update_turn(
                    turn.id,
                    status="completed",
                    final_output_message_id=existing_outbound.id,
                    message_sent=True,
                    warnings_issued=list(turn.warnings_issued or [])
                    + ["restart replay reused persisted outbound without model execution"],
                    idempotency_key=deterministic_idempotency_key(
                        "resident-restart-existing-outbound-delivered",
                        turn.id,
                        existing_outbound.id,
                    ),
                )
                finish_restart_interrupted_turn(
                    claim.notification_id,
                    status="complete",
                    replacement_turn_id=turn.id,
                    user_delivery_owned=True,
                )
                recovered += 1
                continue
            # The claimed source is the command that initiated this restart.
            # Re-running it would repeat the same side effect and can create an
            # unbounded restart loop.  The durable terminal restart receipt is
            # the response; keep the inbound message consumed and never invoke
            # the model again for this turn.
            self.store.update_turn(
                turn.id,
                status="abandoned",
                warnings_issued=list(turn.warnings_issued or [])
                + [
                    f"restart transaction {claim.notification_id} consumed this "
                    "side-effectful turn; automatic model replay suppressed"
                ],
                idempotency_key=deterministic_idempotency_key(
                    "resident-turn-restart-consumed", turn.id, claim.notification_id
                ),
            )
            finish_restart_interrupted_turn(
                claim.notification_id,
                status="complete",
                replacement_turn_id=turn.id,
            )
            recovered += 1
        return recovered

    async def run_managed_completion_turn(
        self,
        manifest_path: Path,
        manifest: Mapping[str, Any],
    ) -> Any:
        """Run a delegated terminal result through the normal resident turn lifecycle.

        The delegated final response is explicitly untrusted evidence.  This
        turn has its own prompt snapshot, model invocation, canonical turn and
        outbound message records.  Discord transport remains the responsibility
        of the manifest's existing durable completion outbox.
        """

        from .subagent import ManagedCompletionTurnResult, record_completion_turn_id

        provenance = manifest.get("launch_provenance")
        if not isinstance(provenance, Mapping):
            raise RuntimeError("managed completion has no immutable launch provenance")
        source_record_id = str(provenance.get("source_record_id") or "")
        conversation_id = str(provenance.get("resident_conversation_id") or "")
        source_message = self.store.load_message(source_record_id)
        conversation = self.store.load_resident_conversation(conversation_id)
        if source_message is None or conversation is None:
            raise RuntimeError("managed completion source message or conversation is unavailable")
        if source_message.conversation_id != conversation.id:
            raise RuntimeError("managed completion provenance does not match the source conversation")
        expected_reply = str(provenance.get("reply_to_message_id") or "")
        if not expected_reply or source_message.discord_message_id != expected_reply:
            raise RuntimeError("managed completion provenance does not match the inbound reply target")

        hot_context = await self.profile.load_hot_context(conversation.id)
        hot_context["current_request"] = {
            "authority": "persisted inbound record triggering the delegated run",
            "source_record_ids": [source_message.id],
            "query_relationship": (
                dict(manifest["query_relationship"])
                if isinstance(manifest.get("query_relationship"), Mapping)
                else None
            ),
        }
        if isinstance(hot_context.get("context_root"), dict):
            hot_context["context_root"]["intent_packs"] = ["delegation", "conversation"]
        prompt_for = getattr(self.profile, "system_prompt_for", None)
        profile_prompt = (
            prompt_for(source_message.content)
            if callable(prompt_for)
            else self.profile.system_prompt()
        )
        system_prompt = (
            profile_prompt
            + "\n\n"
            + _authoritative_current_request_records_prompt(
                [
                    {
                        "source_record_id": source_message.id,
                        "content": source_message.content,
                    }
                ]
            )
            + "\n\n"
            + _timezone_instruction_from_hot_context(hot_context)
            + "\n\n"
            + _COMPLETION_VERIFIER_SYSTEM_PROMPT
        )
        run_id = str(manifest.get("run_id") or manifest_path.parent.name)
        completion_state = manifest.get("resident_completion_turn")
        existing_turn_id = (
            str(completion_state.get("resident_turn_id") or "")
            if isinstance(completion_state, Mapping)
            else ""
        )
        if existing_turn_id:
            turn_id = existing_turn_id
            self.store.update_turn(
                turn_id,
                current_activity="verifying delegated terminal result",
                idempotency_key=deterministic_idempotency_key(
                    "resident-completion-turn-resume", run_id, turn_id
                ),
            )
        else:
            turn = self.store.create_turn(
                epic_id=conversation.active_epic_id,
                triggered_by_message_ids=[source_message.id],
                prompt_snapshot={
                    "system_prompt": system_prompt,
                    "message_count": 1,
                    "turn_kind": "managed_delegation_completion_verification",
                    "managed_agent_run_id": run_id,
                    "tool_catalog": self.profile.tools().as_compact_catalog(),
                },
                prompt_version=(hot_context.get("prompt_version") if isinstance(hot_context, dict) else None),
                state_at_turn=hot_context,
                model_version=self.config.model_name,
                idempotency_key=deterministic_idempotency_key(
                    "resident-completion-turn", run_id
                ),
            )
            turn_id = turn.id
            record_completion_turn_id(manifest_path, turn_id)

        verification_prompt = _managed_completion_verification_prompt(
            manifest_path=manifest_path,
            manifest=manifest,
            source_message=source_message.content,
        )
        # Completion verification is correlated to one immutable delegation.
        # Conversation history may contain newer user commands (for example a
        # resident restart) and must not be allowed to change the incident this
        # turn verifies.  The verifier prompt already carries the exact source
        # message and terminal manifest evidence it is authorized to assess.
        messages = ({"role": "user", "content": verification_prompt},)
        request = AgentRequest(
            conversation_id=conversation.id,
            messages=messages,
            system_prompt=system_prompt,
            turn_id=turn_id,
            hot_context=hot_context,
            model_seam_metadata=self._model_seam_metadata(
                conversation_id=conversation.id,
                messages=messages,
                system_prompt=system_prompt,
                hot_context=hot_context,
            ),
            subject=None,
            launch_origin=dict(provenance),
        )
        try:
            response = await self.runner.run(request, self.profile.tools())
            self._record_tool_calls(turn_id, response)
            safe_text = _localize_user_text(
                redact_text(response.final_text).strip(), hot_context
            )
            classified_outcome = _classified_verification_outcome(safe_text)
            blocked_semantics = _completion_verification_is_semantically_blocked(
                manifest, safe_text
            )
            if blocked_semantics:
                outcome = "blocked"
                safe_text = _blocked_completion_verification_text(safe_text)
            else:
                outcome = classified_outcome or "unknown"
            if not safe_text:
                safe_text = (
                    "The verification outcome is unknown because the resident verification turn "
                    "returned no summary; the delegated result is not being treated as proof."
                )
                outcome = "unknown"
            elif classified_outcome is None and not blocked_semantics:
                safe_text = (
                    safe_text
                    + "\n\nThe verification outcome is unknown because the resident did not "
                    "provide a clear evidence classification."
                )
            turn_status = "completed"
            warnings = None
        except Exception as exc:
            outcome = "unknown"
            safe_text = (
                f"The delegated run reached terminal status {str(manifest.get('status') or 'unknown')!r}, "
                "but the resident verification turn failed before it could independently validate the "
                "claimed work. The verification outcome is unknown, so the delegated final result is not "
                "being reported as proof; operator inspection is still required."
            )
            turn_status = "failed"
            warnings = [f"completion verifier {exc.__class__.__name__}"]

        outbound = self.store.create_message(
            epic_id=conversation.active_epic_id,
            conversation_id=conversation.id,
            direction="outbound",
            content=safe_text,
            bot_turn_id=turn_id,
            idempotency_key=deterministic_idempotency_key(
                "resident-completion-outbound", run_id
            ),
        )
        self.store.update_turn(
            turn_id,
            status=turn_status,
            final_output_message_id=outbound.id,
            message_sent=False,
            warnings_issued=warnings,
            current_activity=None,
            idempotency_key=deterministic_idempotency_key(
                "resident-completion-turn-finished", run_id, turn_status
            ),
        )
        return ManagedCompletionTurnResult(
            final_text=safe_text,
            verification_outcome=outcome,
            turn_id=turn_id,
            outbound_message_id=outbound.id,
        )

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
        discord_message_id = _optional_string(raw.get("discord_message_id"))
        reference_message_id = _optional_string(raw.get("discord_reference_message_id"))
        stored_parent = (
            self.store.find_conversation_message_by_discord_id(
                conversation.id, reference_message_id
            )
            if reference_message_id
            else None
        )
        reply_provenance = (
            build_reply_provenance(
                source_message_id=discord_message_id,
                source_author_id=event.subject.user_id,
                conversation_key=event.conversation_key,
                scope={
                    "guild_id": event.subject.guild_id,
                    "channel_id": event.subject.channel_id,
                    "thread_id": _optional_string(raw.get("thread_id")),
                    "dm_user_id": _optional_string(raw.get("dm_user_id")),
                },
                raw_chain=raw.get("discord_reply_chain"),
                reference_message_id=reference_message_id,
                reference_author_id=_optional_string(raw.get("discord_reference_author_id")),
                reference_content=_optional_string(raw.get("discord_reference_content")),
                stored_parent=stored_parent,
            )
            if discord_message_id
            else None
        )
        message = self.store.create_message(
            epic_id=conversation.active_epic_id,
            conversation_id=conversation.id,
            direction="inbound",
            content=event.content,
            discord_message_id=discord_message_id,
            discord_reply_provenance=reply_provenance,
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
        request_text = "\n".join(item.message.content for item in items if item.message.content)
        hot_context = await self.profile.load_hot_context(conversation.id)
        relationship_root = relationship_store_root(self.store, self.project_root)
        query_relationships = [
            relationship
            for item in items
            if (
                relationship := load_query_relationship(
                    item.message.id, store_root=relationship_root
                )
            )
            is not None
        ]
        hot_context["current_request"] = {
            "authority": "persisted inbound records triggering this turn",
            "source_record_ids": [item.message.id for item in items],
            "query_relationships": query_relationships,
        }
        if query_relationships:
            hot_context["current_query_relationships"] = query_relationships
        if isinstance(hot_context.get("context_root"), dict):
            hot_context["context_root"]["intent_packs"] = list(
                classify_intent_packs(request_text)
            )
        prompt_for = getattr(self.profile, "system_prompt_for", None)
        profile_prompt = (
            prompt_for(request_text) if callable(prompt_for) else self.profile.system_prompt()
        )
        system_prompt = (
            profile_prompt
            + "\n\n"
            + _authoritative_current_request_prompt(items)
            + "\n\n"
            + _timezone_instruction_from_hot_context(hot_context)
        )
        message_ids = [item.message.id for item in items]
        turn = self.store.create_turn(
            epic_id=active_epic_id,
            triggered_by_message_ids=message_ids,
            prompt_snapshot={
                "system_prompt": system_prompt,
                "message_count": len(items),
                "tool_catalog": self.profile.tools().as_compact_catalog(),
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
        # Turn and message custody are durable before showing the transient
        # Discord marker.  Optional so non-Discord/test sinks retain the core
        # resident contract; transport failure cannot strand accepted work.
        processing_message_ids = [
            message_id
            for item in items
            if (message_id := _optional_string(item.event.raw.get("discord_message_id")))
        ]
        await self._invoke_transport_lifecycle(
            "mark_processing",
            conversation_key=conversation.conversation_key,
            message_ids=processing_message_ids,
            turn_id=turn.id,
        )
        burst = tuple(
            {"role": "user", "content": self._message_content_with_discord_reply_context(item)}
            for item in items
        )
        history = self._build_history(
            conversation.id,
            exclude_ids=message_ids,
            discord_only=bool(processing_message_ids),
        )
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
            turn_id=turn.id,
            hot_context=hot_context,
            model_seam_metadata=model_seam_metadata,
            subject=items[-1].event.subject,
            escalation_id=items[-1].event.escalation_id,
            resume_handler=items[-1].event.resume_handler,
            target_id=items[-1].event.target_id,
            launch_origin=self._managed_subagent_launch_origin(
                items,
                turn_id=turn.id,
                timezone_name=_timezone_name_from_hot_context(hot_context),
            ),
            report_only=bool(items) and all(
                item.event.raw.get("report_only") is True for item in items
            ),
        )
        try:
            response = await self.runner.run(request, self.profile.tools())
        except Exception as exc:
            warning = _bounded_failure_warning(exc)
            safe_text = _resident_turn_failure_reply(exc)
            outbound = self.store.create_message(
                epic_id=active_epic_id,
                conversation_id=conversation.id,
                direction="outbound",
                content=safe_text,
                bot_turn_id=turn.id,
                idempotency_key=deterministic_idempotency_key(
                    "resident-outbound", turn.id, "model-failure"
                ),
            )
            self.store.update_turn(
                turn.id,
                status="failed",
                final_output_message_id=outbound.id,
                message_sent=False,
                warnings_issued=[warning],
                idempotency_key=deterministic_idempotency_key("resident-turn-failed", turn.id),
            )
            await self.outbound.send(
                OutboundMessage(
                    conversation_key=conversation.conversation_key,
                    content=safe_text,
                    idempotency_key=outbound.idempotency_key,
                    metadata={
                        "conversation_id": conversation.id,
                        "message_id": outbound.id,
                        "turn_id": turn.id,
                        "discord_reply_to_message_id": _optional_string(
                            items[-1].event.raw.get("discord_message_id")
                        ),
                        "discord_processing_message_ids": processing_message_ids,
                        "discord_processing_turn_id": turn.id,
                        "discord_processing_continues": False,
                    },
                )
            )
            self.store.update_resident_conversation(
                conversation.id,
                last_outbound_message_id=outbound.id,
                delivery_cursor=outbound.id,
                last_active_at=utc_now(),
                idempotency_key=deterministic_idempotency_key(
                    "resident-conversation-outbound", conversation.id, outbound.id
                ),
            )
            self.store.update_turn(
                turn.id,
                status="failed",
                final_output_message_id=outbound.id,
                message_sent=True,
                warnings_issued=[warning],
                idempotency_key=deterministic_idempotency_key(
                    "resident-turn-failure-delivered", turn.id
                ),
            )
            return
        self._record_tool_calls(turn.id, response)
        processing_continues = _response_has_detached_subagent(response)
        final_message_id = None
        if response.final_text:
            safe_text = _localize_user_text(redact_text(response.final_text), hot_context)
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
                    metadata={
                        "conversation_id": conversation.id,
                        "message_id": outbound.id,
                        "turn_id": turn.id,
                        "discord_reply_to_message_id": _optional_string(items[-1].event.raw.get("discord_message_id")),
                        "discord_processing_message_ids": processing_message_ids,
                        "discord_processing_turn_id": turn.id,
                        "discord_processing_continues": processing_continues,
                    },
                )
            )
            self.store.update_resident_conversation(
                conversation.id,
                last_outbound_message_id=outbound.id,
                delivery_cursor=outbound.id,
                last_active_at=utc_now(),
                idempotency_key=deterministic_idempotency_key("resident-conversation-outbound", conversation.id, outbound.id),
            )
        elif not processing_continues:
            # No terminal user-visible reply exists, so remove the transient
            # marker without inventing a completion reaction.
            await self._invoke_transport_lifecycle(
                "mark_processing_interrupted",
                conversation_key=conversation.conversation_key,
                message_ids=processing_message_ids,
                turn_id=turn.id,
            )
        self.store.update_turn(
            turn.id,
            status="completed",
            final_output_message_id=final_message_id,
            message_sent=bool(final_message_id),
            warnings_issued=_response_diagnostic_warnings(response),
            idempotency_key=deterministic_idempotency_key("resident-turn-completed", turn.id),
        )

    async def _notify_abandoned_turn(
        self,
        turn_id: str,
        triggered_by_message_ids: Sequence[str],
    ) -> None:
        grouped: dict[str, list[str]] = {}
        for message in self.store.load_messages(triggered_by_message_ids):
            if not message.conversation_id or not message.discord_message_id:
                continue
            conversation = self.store.load_resident_conversation(message.conversation_id)
            if conversation is None or not conversation.conversation_key.startswith("discord:"):
                continue
            grouped.setdefault(conversation.conversation_key, []).append(message.discord_message_id)
        for conversation_key, message_ids in grouped.items():
            await self._invoke_transport_lifecycle(
                "mark_processing_interrupted",
                conversation_key=conversation_key,
                message_ids=message_ids,
                turn_id=turn_id,
            )

    async def _invoke_transport_lifecycle(
        self,
        method_name: str,
        *,
        conversation_key: str,
        message_ids: list[str],
        turn_id: str,
    ) -> None:
        if not message_ids:
            return
        callback = getattr(self.outbound, method_name, None)
        if not callable(callback):
            return
        try:
            await callback(
                conversation_key=conversation_key,
                message_ids=message_ids,
                turn_id=turn_id,
            )
        except Exception as exc:
            # Reaction state is a transport effect, never custody for the turn
            # itself. Adapter implementations persist their own retry intent.
            self.emitter.log_system_event(
                level="warn",
                category="external_api",
                event_type="resident_transport_lifecycle_retry_pending",
                message="Resident transport lifecycle effect could not be applied",
                details={
                    "method": method_name,
                    "turn_id": turn_id,
                    "error_class": exc.__class__.__name__,
                },
                turn_id=turn_id,
                idempotency_key=deterministic_idempotency_key(
                    "resident-transport-lifecycle-error", method_name, turn_id
                ),
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

    def _message_content_with_discord_reply_context(self, item: PersistedInboundEvent) -> str:
        if not item.message.discord_message_id:
            return item.event.content
        # Render only immutable provenance on the source record.  History is a
        # separate bounded excerpt and is never an ancestry oracle.
        persisted = self.store.load_message(item.message.id) or item.message
        return render_reply_context(persisted)

    def _managed_subagent_launch_origin(
        self,
        items: Sequence[PersistedInboundEvent],
        *,
        turn_id: str,
        timezone_name: str,
    ) -> dict[str, Any]:
        """Return durable, non-secret Discord provenance for delegated work."""

        discord_items = [
            item
            for item in items
            if _optional_string(item.event.raw.get("discord_message_id"))
            and item.conversation.conversation_key.startswith("discord:")
        ]
        if discord_items and len(discord_items) != len(items):
            # A scheduler event coalesced with a Discord inbound must never
            # borrow the coincident user's immutable reply envelope.
            return {
                "transport": "discord",
                "applicability": "ambiguous",
                "source_kind": "mixed_scheduler_discord_burst",
                "resident_turn_id": turn_id,
            }
        if len(discord_items) > 1:
            # A burst can contain independent user requests.  The resident may
            # answer the burst conversationally, but delegated side effects
            # must not guess which message owns the reply.
            return {
                "transport": "discord",
                "applicability": "ambiguous",
                "source_kind": "discord_burst",
                "resident_turn_id": turn_id,
            }
        if not discord_items:
            scheduled_turn = any(
                item.event.raw.get("source_kind") == "scheduled_turn"
                for item in items
            )
            report_only = bool(items) and all(
                item.event.raw.get("report_only") is True for item in items
            )
            return {
                "transport": "non_discord",
                "applicability": "not_applicable",
                "source_kind": (
                    "scheduled_turn" if scheduled_turn else "scheduler_or_internal_turn"
                ),
                "report_only": report_only,
            }
        item = discord_items[0]
        message_id = _optional_string(item.event.raw.get("discord_message_id"))
        conversation_key = item.conversation.conversation_key
        assert message_id is not None
        return {
            "transport": "discord",
            "applicability": "applicable",
            "conversation_id": item.conversation.id,
            "resident_conversation_id": item.conversation.id,
            "resident_turn_id": turn_id,
            "source_record_id": item.message.id,
            "reply_target_source_record_id": item.message.id,
            "conversation_key": conversation_key,
            "message_id": message_id,
            "discord_message_id": message_id,
            "reply_to_message_id": message_id,
            "guild_id": item.event.subject.guild_id,
            "channel_id": item.event.subject.channel_id,
            "thread_id": _optional_string(item.event.raw.get("thread_id")),
            "dm_user_id": _optional_string(item.event.raw.get("dm_user_id")),
            "source_kind": "discord_inbound_message",
            "timezone_name": timezone_name,
        }

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
                            "discord_reply_to_message_id": _optional_string(event.raw.get("discord_message_id")),
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

    def _build_history(
        self,
        conversation_id: str,
        *,
        exclude_ids: Sequence[str],
        discord_only: bool = False,
    ) -> tuple[dict[str, Any], ...]:
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
        has_discord_inbound = any(
            message.direction == "inbound"
            and getattr(message, "discord_message_id", None)
            for message in rows
        )
        history: list[dict[str, Any]] = []
        for message in rows:
            if (
                discord_only
                and has_discord_inbound
                and message.direction == "inbound"
                and not getattr(message, "discord_message_id", None)
            ):
                # Scheduler and maintenance inputs are not Discord-user speech.
                # Including them in later human turns bloats context and changes
                # the apparent conversation history.
                continue
            content = message.content
            if not (content and content.strip()):
                continue
            content = content.strip()
            if len(content) > 4_000:
                content = content[:3_999] + "…"
            role = "user" if message.direction == "inbound" else "assistant"
            history.append({"role": role, "content": content})
        selected: list[dict[str, Any]] = []
        used = 0
        for item in reversed(history):
            size = len(item["content"])
            if selected and used + size > 16_000:
                break
            selected.append(item)
            used += size
        return tuple(reversed(selected))

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


def _response_has_detached_subagent(response: AgentResponse) -> bool:
    """Keep working state across the resident's non-terminal launch acknowledgement."""

    return bool(durable_launch_run_ids(response.tool_calls))


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_dict(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _timezone_name_from_hot_context(hot_context: Mapping[str, Any]) -> str:
    value = hot_context.get("user_timezone")
    if isinstance(value, Mapping):
        name = str(value.get("timezone_name") or "").strip()
        if name:
            return name
    return "UTC"


def _bounded_failure_warning(exc: Exception) -> str:
    warning = redact_text(f"{exc.__class__.__name__}: {exc}").strip()
    return warning if len(warning) <= 1200 else f"{warning[:1199]}…"


def _resident_turn_failure_reply(exc: Exception) -> str:
    if isinstance(exc, AgentTimeoutError):
        return (
            "I couldn't complete this resident turn because the model exceeded its execution "
            "limit and did not finish during the single bounded same-process recovery window. "
            "The process group was stopped, no second invocation was started, and specific "
            "diagnostic evidence was recorded."
        )
    detail = str(exc).lower()
    if "prompt exceeds" in detail or "input_too_large" in detail or "maximum length" in detail:
        return (
            "I couldn't process this message because the resident's internal context exceeded "
            "the model input limit. The failure was recorded and no requested action was taken."
        )
    return (
        "I couldn't complete this resident turn because the model invocation failed. "
        "The failure was recorded and no requested action was taken."
    )


def _response_diagnostic_warnings(response: AgentResponse) -> list[str] | None:
    recovery = response.metadata.get("timeout_recovery")
    if not isinstance(recovery, Mapping):
        return None
    return [
        "AgentTimeoutRecovery: same invocation completed during bounded grace; "
        f"continuations={recovery.get('continuations', 1)}, "
        f"invocation_replays={recovery.get('invocation_replays', 0)}, "
        f"initial_timeout_s={recovery.get('initial_timeout_s')}, "
        f"recovery_grace_s={recovery.get('recovery_grace_s')}, "
        f"elapsed_s={recovery.get('elapsed_s')}, "
        f"process_pid={recovery.get('process_pid')}, "
        f"stdout_bytes={recovery.get('stdout_bytes')}, "
        f"stderr_bytes={recovery.get('stderr_bytes')}",
    ]


def _timezone_instruction_from_hot_context(hot_context: Mapping[str, Any]) -> str:
    from .timezone import ResolvedTimezone

    return timezone_prompt_instruction(
        ResolvedTimezone(
            name=_timezone_name_from_hot_context(hot_context),
            source="hot_context",
        )
    )


def _localize_user_text(text: str, hot_context: Mapping[str, Any]) -> str:
    return localize_text_timestamps(
        text,
        _timezone_name_from_hot_context(hot_context),
    )


def _authoritative_current_request_prompt(
    items: Sequence[PersistedInboundEvent],
) -> str:
    """Render the exact turn-triggering records as prompt authority, without summarizing."""

    return _authoritative_current_request_records_prompt(
        [
            {
                "source_record_id": item.message.id,
                "content": item.message.content,
            }
            for item in items
        ]
    )


def _authoritative_current_request_records_prompt(
    records: Sequence[Mapping[str, str]],
) -> str:
    """Render exact persisted inbound records as the system-prompt request authority."""

    has_content = any(record.get("content") for record in records)
    absence = (
        "Every authoritative content value is empty. There is no substantive current request "
        "to infer; represent that absence honestly and do not fabricate one."
        if not has_content
        else "Answer the authoritative message or messages below as the current request."
    )
    return (
        "Authoritative current inbound request for this turn:\n"
        "The persisted inbound record(s) in the JSON block below are the sole current request. "
        "Bounded conversation history, reply ancestry, hot context, and retrieved context are "
        "context only: do not infer or substitute a different current request from them. "
        f"{absence} Respond naturally without adding a synthetic request header.\n"
        "<authoritative_current_request_json>\n"
        + json.dumps(records, ensure_ascii=False, sort_keys=True)
        + "\n</authoritative_current_request_json>"
    )


_COMPLETION_VERIFIER_SYSTEM_PROMPT = """
You are handling a resident-managed delegated-run completion as a fresh normal
resident turn. Independently verify the original task and the delegated run's
claims. A terminal manifest, exit code zero, result.md, or delegated final prose
is evidence to inspect, never proof of completion. Inspect the actual project
state and run log; run proportionate read-only or test verification when safe.
Classify truthfully as success, partial, failed, unknown, or blocked. Do not
repair or continue the delegated task in this turn. Write a concise,
user-facing response in natural prose: begin with what happened rather than a
template label, and state the classification clearly in prose (for example,
"The verification outcome is partial."). Explain what is actually complete,
concrete verification evidence, and remaining caveats/actions. Never expose
secrets or internal handoff notes.
""".strip()


def _managed_completion_verification_prompt(
    *,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    source_message: str,
) -> str:
    def resolved_path(field: str, fallback: str) -> str:
        path = Path(str(manifest.get(field) or fallback))
        if not path.is_absolute():
            path = manifest_path.parent / path
        return str(path.resolve())

    relationship = manifest.get("query_relationship")
    relationship_context = (
        "Query relationship and aggregation ownership:\n"
        + json.dumps(relationship, sort_keys=True, default=str)
        + "\n\n"
        if isinstance(relationship, Mapping)
        else ""
    )
    completion_verification = manifest.get("completion_verification")
    verification_context = (
        "Resident completion-verification contract outcome:\n"
        + json.dumps(completion_verification, sort_keys=True, default=str)
        + "\nTreat applicable_non_mutating_success as an explicit applicable success; do not "
        "request git commit/diff/clean-worktree evidence for that classification. Git-backed "
        "mutation still requires git_backed_mutation_custody_verified.\n\n"
        if isinstance(completion_verification, Mapping)
        else ""
    )
    queue = manifest.get("queue")
    dependency_context = ""
    if isinstance(queue, Mapping) and queue.get("state") == "dependency_failed":
        dependency_context = (
            "Terminal dependency evidence from the synthesis/delivery owner's durable queue:\n"
            + json.dumps(
                {
                    key: queue.get(key)
                    for key in (
                        "state",
                        "attention",
                        "failed_predecessor_run_id",
                        "predecessor_status",
                        "predecessor_states",
                    )
                    if queue.get(key) is not None
                },
                sort_keys=True,
                default=str,
            )
            + "\nThe synthesis/delivery child did not execute. Inspect predecessor manifests and "
            "artifacts for partial work, label it as partial/unverified as appropriate, clearly "
            "name the blocked or abandoned dependency, and never claim downstream synthesis ran.\n\n"
        )
    return (
        "A resident-managed delegated execution has reached a terminal state and now requires "
        "independent completion verification. Do not accept its final response as proof.\n\n"
        f"Managed run id: {manifest.get('run_id') or manifest_path.parent.name}\n"
        f"Claimed terminal status: {manifest.get('status') or 'unknown'}\n"
        f"Return code: {manifest.get('returncode', 'unknown')}\n"
        f"Project directory: {manifest.get('project_dir') or 'unknown'}\n"
        f"Manifest: {manifest_path.resolve()}\n"
        f"Original delegated prompt: {resolved_path('prompt_path', 'prompt.md')}\n"
        f"Delegated final claim: {resolved_path('result_path', 'result.md')}\n"
        f"Full delegated log: {resolved_path('full_log_path', str(manifest.get('log_path') or 'run.log'))}\n\n"
        f"{relationship_context}"
        f"{verification_context}"
        f"{dependency_context}"
        "Authoritative original user request (preserve its requirements):\n"
        f"{source_message[:12000]}"
    )


def _classified_verification_outcome(text: str) -> str | None:
    """Return an explicit verifier classification, distinct from no classification."""

    normalized = text.lower()
    for outcome in ("success", "partial", "failed", "unknown", "blocked"):
        if re.search(
            rf"\b(?:the )?verification outcome\s*(?::|is|was|as)\s*{outcome}\b",
            normalized,
        ):
            return outcome
    return None


def _completion_verification_is_semantically_blocked(
    manifest: Mapping[str, Any], text: str
) -> bool:
    """Fail closed when lifecycle completion is not semantic recovery success.

    Resident delivery and finite worker exit are transport/lifecycle facts.  A
    linked repair goal or the verifier's own evidence can independently prove
    that the underlying recovery is still blocked.  In that case the outbound
    classification must remain blocked even if the verifier also used
    success-led handoff wording.
    """

    semantic_completion = manifest.get("semantic_completion")
    if isinstance(semantic_completion, Mapping):
        authority = str(semantic_completion.get("authority") or "").strip()
        status = str(semantic_completion.get("status") or "").strip().lower()
        complete = semantic_completion.get("complete")
        if authority == "repair_goal" and (
            complete is False
            or status
            in {
                "active",
                "blocked",
                "continuing",
                "approval_required",
                "retry_pending",
                "unknown",
            }
        ):
            return True

    links = manifest.get("links")
    goal_path = ""
    if isinstance(links, Mapping):
        goal_path = str(links.get("repair_goal_path") or "").strip()
    if goal_path:
        try:
            goal = json.loads(Path(goal_path).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            # Missing semantic authority cannot be converted into success.
            return True
        if isinstance(goal, Mapping):
            goal_status = str(goal.get("status") or "unknown").strip().lower()
            if goal_status != "progressed":
                return True

    normalized = " ".join(text.lower().split())
    blocked_subjects = (
        "underlying recovery",
        "original recovery",
        "original blocker",
        "forward motion",
        "target recovery",
    )
    blocked_states = (
        "remains blocked",
        "remain blocked",
        "is blocked",
        "remains unresolved",
        "remain unresolved",
        "has not resumed",
        "stopped",
    )
    return any(subject in normalized for subject in blocked_subjects) and any(
        state in normalized for state in blocked_states
    )


def _blocked_completion_verification_text(text: str) -> str:
    """Lead blocked verification plainly and remove known success-led claims."""

    cleaned = re.sub(
        r"(?im)^.*(?:handoff|message delivery|message was durably sent).*(?:success(?:ful(?:ly)?)?|completed).*$",
        "",
        text,
    ).strip()
    prefix = (
        "Forward motion remains blocked; completion or delivery of the finite delegated task "
        "is not semantic recovery success. The verification outcome is blocked."
    )
    return prefix if not cleaned else f"{prefix}\n\n{cleaned}"


def _verification_outcome(text: str) -> str:
    return _classified_verification_outcome(text) or "unknown"


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
