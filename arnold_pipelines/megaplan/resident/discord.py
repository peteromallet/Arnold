"""Discord adapter boundary for resident Megaplan conversations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
from agentbox.redaction import redact_text
from arnold_pipelines.megaplan.store import ScheduledJobInput, deterministic_idempotency_key

from .auth import AuthorizationSubject
from .currently_running import (
    CURRENTLY_RUNNING_COMMAND,
    CURRENTLY_RUNNING_DESCRIPTION,
    collect_currently_running,
    render_currently_running,
)
from .discord_reactions import DiscordReactionEffectLedger, ReactionEffectSweepResult
from .runtime import InboundEvent, OutboundMessage, OutboundSink, ResidentRuntime
from .reply_chain import (
    REPLY_CAPTURE_MAX_ANCESTORS,
    bounded_reply_content,
)
from .restart_resident import (
    RESTART_RESIDENT_ACKNOWLEDGEMENT,
    RESTART_RESIDENT_COMMAND,
    RESTART_RESIDENT_DESCRIPTION,
    restart_discord_resident,
)
from .scheduler import ScheduledJobWorker
from .subagent import sweep_managed_agent_deliveries
from .transcription import AudioTranscriptionError, OpenAICompatibleAudioTranscriber
from .timezone import InvalidTimezone, TimezoneService

LOGGER = logging.getLogger(__name__)
DISCORD_MESSAGE_LIMIT = 2000
DISCORD_SAFE_MESSAGE_LIMIT = 1900
DISCORD_REPLY_REACTION = "☑️"
# Hourglass is a Unicode emoji supported by Discord and intentionally differs
# from the terminal checkbox.  Keep both transport UI conventions here.
DISCORD_WORKING_REACTION = "⏳"
ESCALATION_TAG_RE = re.compile(r"\[escalation:([A-Za-z0-9._:-]+)\]", re.IGNORECASE)
SUPPORTED_AUDIO_EXTENSIONS = frozenset(
    {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".opus"}
)
SUPPORTED_AUDIO_CONTENT_TYPES = frozenset(
    {
        "audio/mpeg",
        "audio/mp3",
        "audio/x-mpeg",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/wav",
        "audio/x-wav",
        "audio/vnd.wave",
        "audio/x-pn-wav",
        "audio/webm",
        "video/webm",
        "video/mp4",
        "video/mpeg",
        # Discord voice messages are normally Ogg/Opus attachments.
        "audio/ogg",
        "application/ogg",
        "audio/opus",
    }
)
DISCORD_ATTACHMENT_HOSTS = frozenset(
    {"cdn.discordapp.com", "cdn.discordapp.net", "media.discordapp.net"}
)
VOICE_FAILURE_UNSUPPORTED = (
    "I couldn't transcribe that attachment. Send one MP3, MP4, MPEG, MPGA, M4A, WAV, WebM, Ogg, or Opus audio file."
)
VOICE_FAILURE_TOO_LARGE = "I couldn't transcribe that audio because it is larger than the configured size limit."
VOICE_FAILURE_DOWNLOAD = "I couldn't download that Discord audio attachment. Please try sending it again."
VOICE_FAILURE_ENDPOINT = (
    "I couldn't transcribe that audio right now. Please try again later or send the message as text."
)
VOICE_FAILURE_DISABLED = (
    "Voice-message transcription is disabled for this resident. Please send the message as text."
)


@dataclass(frozen=True)
class DiscordApplicationCommand:
    name: str
    description: str
    handler_name: str


DISCORD_APPLICATION_COMMANDS = (
    DiscordApplicationCommand(
        name=CURRENTLY_RUNNING_COMMAND,
        description=CURRENTLY_RUNNING_DESCRIPTION,
        handler_name="handle_currently_running_interaction",
    ),
    DiscordApplicationCommand(
        name=RESTART_RESIDENT_COMMAND,
        description=RESTART_RESIDENT_DESCRIPTION,
        handler_name="handle_restart_resident_interaction",
    ),
)


def register_discord_application_commands(tree: Any, service: Any) -> tuple[str, ...]:
    """Register the resident's application-command inventory on one tree."""

    def callback_for(handler: Any, callback_name: str) -> Any:
        async def callback(interaction: Any) -> None:
            await handler(interaction)

        callback.__name__ = callback_name
        return callback

    registered: list[str] = []
    for command in DISCORD_APPLICATION_COMMANDS:
        handler = getattr(service, command.handler_name)
        callback = callback_for(handler, command.name.replace("-", "_"))
        tree.command(name=command.name, description=command.description)(callback)
        registered.append(command.name)
    return tuple(registered)


class AudioTranscriber(Protocol):
    async def transcribe(self, *, data: bytes, filename: str, content_type: str) -> str:
        ...


class AttachmentDownloader(Protocol):
    async def download(self, attachment: Any, *, max_bytes: int, timeout_s: float) -> bytes:
        ...


class VoiceMessageError(RuntimeError):
    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message


class DiscordAttachmentDownloader:
    """Stream a Discord CDN attachment into memory with a hard byte ceiling."""

    async def download(self, attachment: Any, *, max_bytes: int, timeout_s: float) -> bytes:
        declared_size = _attachment_size(attachment)
        if declared_size is not None and declared_size > max_bytes:
            raise VoiceMessageError("attachment_too_large", VOICE_FAILURE_TOO_LARGE)
        url = str(getattr(attachment, "url", "") or "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in DISCORD_ATTACHMENT_HOSTS:
            raise VoiceMessageError("unsafe_attachment_url", VOICE_FAILURE_DOWNLOAD)

        timeout = httpx.Timeout(timeout_s)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    content_length = _optional_int(response.headers.get("content-length"))
                    if content_length is not None and content_length > max_bytes:
                        raise VoiceMessageError("attachment_too_large", VOICE_FAILURE_TOO_LARGE)
                    chunks: list[bytes] = []
                    downloaded = 0
                    async for chunk in response.aiter_bytes(64 * 1024):
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            raise VoiceMessageError("attachment_too_large", VOICE_FAILURE_TOO_LARGE)
                        chunks.append(chunk)
        except VoiceMessageError:
            raise
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            raise VoiceMessageError("attachment_download_failed", VOICE_FAILURE_DOWNLOAD) from exc
        return b"".join(chunks)


@dataclass(frozen=True)
class DiscordDeliveryTarget:
    guild_id: str | None
    channel_id: str
    thread_id: str | None = None
    dm_user_id: str | None = None

    @property
    def conversation_key(self) -> str:
        if self.dm_user_id:
            return f"discord:dm:{self.dm_user_id}"
        thread_part = f":thread:{self.thread_id}" if self.thread_id else ""
        return f"discord:guild:{self.guild_id}:channel:{self.channel_id}{thread_part}"

    @classmethod
    def from_conversation_key(cls, conversation_key: str) -> "DiscordDeliveryTarget":
        parts = [part for part in conversation_key.split(":") if part]
        if parts[:2] == ["discord", "dm"] and len(parts) == 3:
            return cls(guild_id=None, channel_id=parts[2], dm_user_id=parts[2])
        if parts[:2] == ["discord", "guild"] and len(parts) >= 5 and parts[3] == "channel":
            thread_id = parts[6] if len(parts) >= 7 and parts[5] == "thread" else None
            return cls(guild_id=parts[2], channel_id=parts[4], thread_id=thread_id)
        raise ValueError(f"Unsupported Discord conversation key: {conversation_key}")


@dataclass(frozen=True)
class DiscordInboundMessage:
    message_id: str
    author_id: str
    target: DiscordDeliveryTarget
    content: str
    referenced_message_id: str | None = None
    referenced_message_author_id: str | None = None
    referenced_message_content: str | None = None
    reply_chain: dict[str, Any] | None = None
    escalation_id: str | None = None
    was_voice_message: bool = False
    transcription_metadata: dict[str, Any] | None = None

    @classmethod
    def from_discord_message(cls, message: Any) -> "DiscordInboundMessage":
        channel = message.channel
        guild = getattr(message, "guild", None)
        author = getattr(message, "author", None)
        guild_id = _optional_snowflake(getattr(guild, "id", None))
        author_id = _optional_snowflake(getattr(author, "id", None))
        channel_id = _optional_snowflake(getattr(channel, "id", None))
        thread_id = None
        dm_user_id = None
        parent = getattr(channel, "parent", None)
        if parent is not None and _optional_snowflake(getattr(parent, "id", None)):
            thread_id = channel_id
            channel_id = _optional_snowflake(getattr(parent, "id", None))
        if guild_id is None:
            dm_user_id = author_id
        if not author_id:
            raise ValueError("Discord message author has no stable id")
        if not channel_id:
            raise ValueError("Discord message channel has no stable id")
        content = str(getattr(message, "content", ""))
        referenced_message_id = _referenced_message_id(message)
        referenced_message = _referenced_message_snapshot(message)
        escalation_id = (
            _resolve_escalation_id_from_message_id(referenced_message_id)
            or _extract_escalation_id_tag(content)
        )
        return cls(
            message_id=str(message.id),
            author_id=author_id,
            target=DiscordDeliveryTarget(
                guild_id=guild_id,
                channel_id=channel_id,
                thread_id=thread_id,
                dm_user_id=dm_user_id,
            ),
            content=content,
            referenced_message_id=referenced_message_id,
            referenced_message_author_id=referenced_message.get("author_id"),
            referenced_message_content=referenced_message.get("content"),
            escalation_id=escalation_id,
        )

    def to_inbound_event(self) -> InboundEvent:
        return InboundEvent(
            idempotency_key=f"discord:message:{self.message_id}",
            conversation_key=self.target.conversation_key,
            subject=AuthorizationSubject(
                user_id=self.author_id,
                guild_id=self.target.guild_id,
                channel_id=self.target.channel_id,
            ),
            content=self.content,
            escalation_id=self.escalation_id,
            raw={
                "discord_message_id": self.message_id,
                "discord_reference_message_id": self.referenced_message_id,
                "discord_reference_author_id": self.referenced_message_author_id,
                "discord_reference_content": self.referenced_message_content,
                "discord_reply_chain": self.reply_chain,
                "escalation_id": self.escalation_id,
                "thread_id": self.target.thread_id,
                "dm_user_id": self.target.dm_user_id,
                "was_voice_message": self.was_voice_message,
                "transcription_metadata": self.transcription_metadata,
            },
        )

    def with_transcript(self, transcript: str, metadata: dict[str, Any]) -> "DiscordInboundMessage":
        return replace(
            self,
            content=transcript,
            was_voice_message=True,
            transcription_metadata=dict(metadata),
        )


class DiscordOutboundSink(OutboundSink):
    """Deliver resident outbound messages to Discord using durable targets."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        delivery_environment: str = "test",
        bot_role: str = "test",
        reaction_effect_root: Path | None = None,
    ) -> None:
        self.client = client
        self.delivery_environment = str(delivery_environment).strip().lower()
        self.bot_role = str(bot_role).strip().lower()
        self.reaction_effects = (
            DiscordReactionEffectLedger(reaction_effect_root)
            if reaction_effect_root is not None
            else None
        )
        self._reaction_sweep_lock = asyncio.Lock()

    def bind_client(self, client: Any) -> None:
        self.client = client

    async def send(self, message: OutboundMessage) -> None:
        if _is_operational_delivery(message) and not (
            self.delivery_environment == "production" and self.bot_role == "production"
        ):
            raise RuntimeError(
                "operational Discord delivery is disabled outside the production bot boundary"
            )
        if self.client is None:
            raise RuntimeError("Discord client is not bound")
        target = DiscordDeliveryTarget.from_conversation_key(message.conversation_key)
        channel = await self._resolve_channel(target)
        sent_messages = []
        reply_to_message_id = _optional_snowflake(
            message.metadata.get("discord_reply_to_message_id") if isinstance(message.metadata, dict) else None
        )
        nonce_base = (
            str(message.metadata.get("discord_nonce") or "").strip()
            if isinstance(message.metadata, dict)
            else ""
        )
        if not nonce_base and message.idempotency_key:
            nonce_base = hashlib.sha256(
                f"resident-discord-delivery:{message.idempotency_key}".encode()
            ).hexdigest()[:20]
        for index, chunk in enumerate(split_discord_message(message.content)):
            kwargs: dict[str, Any] = {}
            if nonce_base:
                # discord.py sends enforce_nonce=true whenever nonce is set.
                # Keep each chunk stable across retries while staying below the
                # Discord nonce length ceiling.
                kwargs["nonce"] = f"{nonce_base[:20]}-{index}"
            if index == 0 and reply_to_message_id:
                reference = _partial_message_reference(channel, reply_to_message_id)
                if reference is None:
                    raise RuntimeError(
                        f"Discord reply target {reply_to_message_id} is unavailable"
                    )
                kwargs["reference"] = reference
                kwargs["mention_author"] = False
            sent_messages.append(await channel.send(chunk, **kwargs))
        if isinstance(message.metadata, dict):
            ids = [str(getattr(sent, "id", "")) for sent in sent_messages]
            message.metadata["discord_message_ids"] = ids
            message.metadata["discord_message_id"] = ids[0] if ids else ""
        if reply_to_message_id and not bool(message.metadata.get("discord_processing_continues")):
            # Reply acceptance is the terminal delivery boundary. Reaction
            # intents are committed only after it, and reaction failures are
            # retried independently so an accepted reply is never re-sent just
            # because Discord's reaction endpoint was unavailable.
            try:
                await self._queue_terminal_reactions(message, reply_to_message_id)
            except Exception:
                # The reply is already accepted. Never turn a reaction-ledger
                # problem into a duplicate reply attempt.
                LOGGER.exception(
                    "Discord terminal reaction intent could not be committed message_id=%s",
                    reply_to_message_id,
                )

    async def _queue_terminal_reactions(
        self, message: OutboundMessage, reply_to_message_id: str
    ) -> None:
        working_ids = _reaction_message_ids(
            message.metadata.get("discord_processing_message_ids"),
            fallback=reply_to_message_id,
        )
        lifecycle_key = _reaction_lifecycle_key(message, fallback=reply_to_message_id)
        working_dependencies = self._supersede_pending_working(
            message.conversation_key, working_ids
        )
        terminal_effect_ids: set[str] = set()
        # The completion marker is the terminal handoff boundary: Discord must
        # accept it before any working marker can be removed.  Pending working
        # adds remain dependencies so a concurrent/replayed add cannot land
        # after terminal cleanup.
        completion = self._ensure_reaction_effect(
            conversation_key=message.conversation_key,
            message_id=reply_to_message_id,
            operation="add",
            emoji=DISCORD_REPLY_REACTION,
            phase="completion",
            lifecycle_key=lifecycle_key,
            turn_id=_optional_text(message.metadata.get("discord_processing_turn_id")),
            depends_on=[
                effect_id
                for dependencies in working_dependencies.values()
                for effect_id in dependencies
            ],
        )
        completion_id = str(completion["effect_id"])
        terminal_effect_ids.add(completion_id)
        for source_message_id in working_ids:
            effect = self._ensure_reaction_effect(
                conversation_key=message.conversation_key,
                message_id=source_message_id,
                operation="remove",
                emoji=DISCORD_WORKING_REACTION,
                phase="terminal_cleanup",
                lifecycle_key=lifecycle_key,
                turn_id=_optional_text(message.metadata.get("discord_processing_turn_id")),
                depends_on=[completion_id],
            )
            terminal_effect_ids.add(str(effect["effect_id"]))
        await self.reconcile_reactions(only=terminal_effect_ids)

    async def mark_processing(
        self,
        *,
        conversation_key: str,
        message_ids: list[str],
        turn_id: str | None = None,
    ) -> None:
        """Commit then apply working markers after durable turn creation."""

        effect_ids: set[str] = set()
        lifecycle_key = turn_id or "resident-processing"
        for message_id in _reaction_message_ids(message_ids):
            effect = self._ensure_reaction_effect(
                conversation_key=conversation_key,
                message_id=message_id,
                operation="add",
                emoji=DISCORD_WORKING_REACTION,
                phase="working",
                lifecycle_key=lifecycle_key,
                turn_id=turn_id,
            )
            effect_ids.add(str(effect["effect_id"]))
        await self.reconcile_reactions(only=effect_ids)

    async def mark_processing_interrupted(
        self,
        *,
        conversation_key: str,
        message_ids: list[str],
        turn_id: str | None = None,
    ) -> None:
        """Remove stale working markers without ever showing completion."""

        effect_ids: set[str] = set()
        lifecycle_key = turn_id or "resident-interrupted"
        normalized_ids = _reaction_message_ids(message_ids)
        working_dependencies = self._supersede_pending_working(
            conversation_key, normalized_ids
        )
        for message_id in normalized_ids:
            effect = self._ensure_reaction_effect(
                conversation_key=conversation_key,
                message_id=message_id,
                operation="remove",
                emoji=DISCORD_WORKING_REACTION,
                phase="interrupted_cleanup",
                lifecycle_key=lifecycle_key,
                turn_id=turn_id,
                depends_on=working_dependencies.get(message_id, []),
            )
            effect_ids.add(str(effect["effect_id"]))
        await self.reconcile_reactions(only=effect_ids)

    async def reconcile_reactions(
        self,
        *,
        only: set[str] | None = None,
    ) -> ReactionEffectSweepResult:
        """Replay pending reaction effects; safe under retries and concurrent sweeps."""

        if self.client is None:
            pending = self.reaction_effects.pending_count() if self.reaction_effects else 0
            return ReactionEffectSweepResult(retry_pending=pending)
        if self.reaction_effects is None:
            return await self._apply_ephemeral_reactions(only=only)

        scanned = applied = 0
        async with self._reaction_sweep_lock:
            while True:
                claimed = self.reaction_effects.claim_due(only=only)
                if not claimed:
                    break
                scanned += len(claimed)
                for effect in claimed:
                    try:
                        await self._apply_reaction_effect(effect)
                    except Exception as exc:
                        self.reaction_effects.finish(effect, error=exc)
                        LOGGER.warning(
                            "Discord reaction effect retry pending effect_id=%s operation=%s "
                            "message_id=%s error_class=%s",
                            effect.get("effect_id"),
                            effect.get("operation"),
                            effect.get("message_id"),
                            exc.__class__.__name__,
                        )
                    else:
                        self.reaction_effects.finish(effect)
                        applied += 1
                # Failures return to pending immediately; avoid a tight retry loop.
                if applied < scanned:
                    break
        pending = self.reaction_effects.pending_count()
        return ReactionEffectSweepResult(
            scanned=scanned,
            applied=applied,
            retry_pending=pending,
            skipped=max(0, pending - (scanned - applied)),
        )

    def _ensure_reaction_effect(self, **intent: Any) -> dict[str, Any]:
        if self.reaction_effects is not None:
            return self.reaction_effects.ensure(**intent)
        # Tests and non-resident notification callers may omit durable state.
        # Keep their behavior compatible while production injects a ledger.
        identity = json.dumps(intent, sort_keys=True, default=str)
        effect_id = "ephemeral-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
        effect = {"effect_id": effect_id, **intent, "status": "pending"}
        if not hasattr(self, "_ephemeral_reaction_effects"):
            self._ephemeral_reaction_effects: dict[str, dict[str, Any]] = {}
        return self._ephemeral_reaction_effects.setdefault(effect_id, effect)

    def _supersede_pending_working(
        self, conversation_key: str, message_ids: list[str]
    ) -> dict[str, list[str]]:
        if self.reaction_effects is not None:
            return self.reaction_effects.supersede_pending_working(
                conversation_key=conversation_key,
                message_ids=message_ids,
            )
        effects = getattr(self, "_ephemeral_reaction_effects", {})
        targets = set(message_ids)
        dependencies = {message_id: [] for message_id in targets}
        for effect in effects.values():
            if (
                effect.get("phase") == "working"
                and effect.get("conversation_key") == conversation_key
                and effect.get("message_id") in targets
            ):
                message_id = str(effect["message_id"])
                dependencies[message_id].append(str(effect["effect_id"]))
                if effect.get("status") == "pending":
                    effect["status"] = "applied"
                    effect["outcome"] = "superseded_before_apply"
        return dependencies

    async def _apply_ephemeral_reactions(
        self, *, only: set[str] | None
    ) -> ReactionEffectSweepResult:
        effects = getattr(self, "_ephemeral_reaction_effects", {})
        applied = scanned = 0
        for effect in list(effects.values()):
            if effect.get("status") == "applied":
                continue
            if only is not None and effect.get("effect_id") not in only:
                continue
            dependencies = [effects.get(value) for value in effect.get("depends_on", [])]
            if any(value is None or value.get("status") != "applied" for value in dependencies):
                continue
            scanned += 1
            try:
                await self._apply_reaction_effect(effect)
            except Exception as exc:
                effect["last_error"] = redact_text(str(exc))[:500]
                effect["last_error_class"] = exc.__class__.__name__
                LOGGER.warning(
                    "Discord reaction effect retry pending effect_id=%s error_class=%s",
                    effect.get("effect_id"),
                    exc.__class__.__name__,
                )
            else:
                effect["status"] = "applied"
                applied += 1
        # Terminal cleanup may become eligible after completion in this pass.
        if applied and any(
            effect.get("status") != "applied"
            and (only is None or effect.get("effect_id") in only)
            for effect in effects.values()
        ):
            followup = await self._apply_ephemeral_reactions(only=only)
            scanned += followup.scanned
            applied += followup.applied
        pending = sum(1 for effect in effects.values() if effect.get("status") != "applied")
        return ReactionEffectSweepResult(scanned=scanned, applied=applied, retry_pending=pending)

    async def _apply_reaction_effect(self, effect: Any) -> None:
        channel = await self._resolve_channel(
            DiscordDeliveryTarget.from_conversation_key(str(effect["conversation_key"]))
        )
        operation = str(effect["operation"])
        if operation == "add":
            applied = await _add_reaction(channel, str(effect["message_id"]), str(effect["emoji"]))
        elif operation == "remove":
            applied = await _remove_reaction(
                channel,
                str(effect["message_id"]),
                str(effect["emoji"]),
                actor=getattr(self.client, "user", None),
            )
        else:
            raise RuntimeError(f"unsupported Discord reaction operation: {operation}")
        if not applied:
            raise RuntimeError("Discord reaction target does not support the requested operation")

    async def _resolve_channel(self, target: DiscordDeliveryTarget) -> Any:
        if target.dm_user_id:
            user = self.client.get_user(int(target.dm_user_id)) or await self.client.fetch_user(int(target.dm_user_id))
            return user.dm_channel or await user.create_dm()
        channel_id = int(target.thread_id or target.channel_id)
        channel = self.client.get_channel(channel_id)
        if channel is None:
            channel = await self.client.fetch_channel(channel_id)
        return channel


def _is_operational_delivery(message: OutboundMessage) -> bool:
    """Identify outbox traffic that only the production bot may deliver."""

    metadata = message.metadata if isinstance(message.metadata, dict) else {}
    return bool(
        metadata.get("resident_reset_notification")
        or metadata.get("completion_delivery")
        or metadata.get("operational_delivery")
    )


def split_discord_message(content: str) -> list[str]:
    """Split outbound Discord text into messages below Discord's hard limit."""

    text = str(content or "")
    if len(text) <= DISCORD_MESSAGE_LIMIT:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        chunk, remaining = _split_once(remaining, DISCORD_SAFE_MESSAGE_LIMIT)
        chunks.append(chunk)
    return chunks


def _split_once(text: str, limit: int) -> tuple[str, str]:
    if len(text) <= limit:
        return text, ""
    split_at = max(
        text.rfind("\n\n", 0, limit + 1),
        text.rfind("\n", 0, limit + 1),
        text.rfind(" ", 0, limit + 1),
    )
    if split_at <= 0:
        split_at = limit
    chunk = text[:split_at].rstrip()
    rest = text[split_at:].lstrip()
    if not chunk:
        chunk = text[:limit]
        rest = text[limit:]
    return chunk, rest


def _extract_escalation_id_tag(content: str) -> str | None:
    match = ESCALATION_TAG_RE.search(content or "")
    if not match:
        return None
    escalation_id = match.group(1).strip()
    return escalation_id or None


def _referenced_message_id(message: Any) -> str | None:
    reference = getattr(message, "reference", None)
    if reference is None:
        return None
    message_id = _optional_snowflake(getattr(reference, "message_id", None))
    if message_id:
        return message_id
    resolved = getattr(reference, "resolved", None)
    if resolved is None:
        return None
    return _optional_snowflake(getattr(resolved, "id", None))


def _referenced_message_snapshot(message: Any) -> dict[str, str]:
    reference = getattr(message, "reference", None)
    if reference is None:
        return {}
    resolved = getattr(reference, "resolved", None)
    if resolved is None:
        return {}
    content = str(getattr(resolved, "content", "") or "").strip()
    if not content:
        return {}
    author = getattr(resolved, "author", None)
    author_id = _optional_snowflake(getattr(author, "id", None))
    snapshot = {"content": content}
    if author_id:
        snapshot["author_id"] = author_id
    return snapshot


async def _capture_discord_reply_chain(message: Any) -> dict[str, Any]:
    """Capture exact reply pointers through Discord once, before store persistence."""

    source_id = _optional_snowflake(getattr(message, "id", None))
    channel = getattr(message, "channel", None)
    channel_id = _optional_snowflake(getattr(channel, "id", None))
    ancestors: list[dict[str, Any]] = []
    seen = {source_id} if source_id else set()
    child = message
    termination_reason = "root"
    chain_complete = True
    capture_truncated = False

    for depth in range(1, REPLY_CAPTURE_MAX_ANCESTORS + 1):
        reference = getattr(child, "reference", None)
        parent_id = _referenced_message_id(child)
        if not parent_id:
            termination_reason = "root"
            break
        reference_channel_id = _optional_snowflake(getattr(reference, "channel_id", None))
        if reference_channel_id and channel_id and reference_channel_id != channel_id:
            ancestors.append(
                {
                    "depth": depth,
                    "message_id": parent_id,
                    "status": "scope_rejected",
                    "unavailable_reason": "reference_outside_source_channel_or_thread",
                }
            )
            termination_reason = "scope_rejected"
            chain_complete = False
            break
        if parent_id in seen:
            ancestors.append(
                {
                    "depth": depth,
                    "message_id": parent_id,
                    "status": "cycle_detected",
                    "unavailable_reason": "reply_pointer_cycle",
                }
            )
            termination_reason = "cycle_detected"
            chain_complete = False
            break
        seen.add(parent_id)

        parent = _resolved_reference_message(reference, parent_id)
        if parent is None:
            fetch_message = getattr(channel, "fetch_message", None)
            if callable(fetch_message):
                try:
                    parent = await fetch_message(int(parent_id))
                except Exception:
                    parent = None
        if parent is None or not hasattr(parent, "content"):
            ancestors.append(
                {
                    "depth": depth,
                    "message_id": parent_id,
                    "status": "unavailable",
                    "unavailable_reason": "missing_deleted_or_inaccessible",
                }
            )
            termination_reason = "ancestor_unavailable"
            chain_complete = False
            break
        parent_channel_id = _optional_snowflake(
            getattr(getattr(parent, "channel", None), "id", None)
        )
        if parent_channel_id and channel_id and parent_channel_id != channel_id:
            ancestors.append(
                {
                    "depth": depth,
                    "message_id": parent_id,
                    "status": "scope_rejected",
                    "unavailable_reason": "resolved_parent_outside_source_channel_or_thread",
                }
            )
            termination_reason = "scope_rejected"
            chain_complete = False
            break

        content, content_truncated = bounded_reply_content(getattr(parent, "content", ""))
        author = getattr(parent, "author", None)
        ancestors.append(
            {
                "depth": depth,
                "message_id": parent_id,
                "author_id": _optional_snowflake(getattr(author, "id", None)),
                "content": content,
                "content_truncated": content_truncated,
                "status": "available",
                "parent_message_id": _referenced_message_id(parent),
            }
        )
        child = parent
    else:
        if _referenced_message_id(child):
            termination_reason = "capture_depth_limit"
            chain_complete = False
            capture_truncated = True

    return {
        "ancestors": ancestors,
        "chain_complete": chain_complete,
        "capture_truncated": capture_truncated,
        "termination_reason": termination_reason,
        "capture_limit": REPLY_CAPTURE_MAX_ANCESTORS,
    }


def _resolved_reference_message(reference: Any, expected_id: str) -> Any | None:
    if reference is None:
        return None
    resolved = getattr(reference, "resolved", None)
    if resolved is None:
        return None
    resolved_id = _optional_snowflake(getattr(resolved, "id", None))
    return resolved if resolved_id == expected_id else None


def _partial_message_reference(channel: Any, message_id: str) -> Any | None:
    get_partial_message = getattr(channel, "get_partial_message", None)
    if not callable(get_partial_message):
        return None
    try:
        return get_partial_message(int(message_id))
    except (TypeError, ValueError):
        return None


def _reaction_message_ids(value: Any, *, fallback: str | None = None) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    result = [str(item).strip() for item in values if item is not None and str(item).strip()]
    if not result and fallback:
        result = [fallback]
    return list(dict.fromkeys(result))


def _reaction_lifecycle_key(message: OutboundMessage, *, fallback: str) -> str:
    metadata = message.metadata if isinstance(message.metadata, dict) else {}
    return str(
        metadata.get("managed_agent_run_id")
        or metadata.get("discord_processing_turn_id")
        or message.idempotency_key
        or fallback
    )


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


async def _reaction_message(channel: Any, message_id: str) -> Any:
    message = _partial_message_reference(channel, message_id)
    if message is None:
        fetch_message = getattr(channel, "fetch_message", None)
        if callable(fetch_message):
            try:
                message = await fetch_message(int(message_id))
            except Exception as exc:
                raise RuntimeError(f"Discord reaction target unavailable: {message_id}") from exc
    if message is None:
        raise RuntimeError(f"Discord reaction target unavailable: {message_id}")
    return message


async def _add_reaction(channel: Any, message_id: str, emoji: str) -> bool:
    message = await _reaction_message(channel, message_id)
    add_reaction = getattr(message, "add_reaction", None)
    if not callable(add_reaction):
        return False
    await add_reaction(emoji)
    return True


async def _remove_reaction(channel: Any, message_id: str, emoji: str, *, actor: Any) -> bool:
    message = await _reaction_message(channel, message_id)
    remove_reaction = getattr(message, "remove_reaction", None)
    if not callable(remove_reaction):
        return False
    try:
        await remove_reaction(emoji, actor)
    except TypeError:
        # discord.py accepts emoji and the reacting member; partial-message
        # test seams commonly expose the simpler one-argument form.
        await remove_reaction(emoji)
    return True


def _resolve_escalation_id_from_message_id(message_id: str | None) -> str | None:
    if not message_id:
        return None
    ledger_path = _escalations_ledger_path()
    if ledger_path is None or not ledger_path.exists():
        return None
    try:
        for raw_line in ledger_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                continue
            if str(record.get("event") or "") != "delivered":
                continue
            message_ids = record.get("message_ids")
            if not isinstance(message_ids, list):
                continue
            if message_id not in {str(item) for item in message_ids if str(item).strip()}:
                continue
            escalation_id = str(record.get("escalation_id") or "").strip()
            if escalation_id:
                return escalation_id
    except Exception:
        LOGGER.exception("Failed to resolve escalation id from Discord message reference")
    return None


def _escalations_ledger_path() -> Path | None:
    for key in ("MEGAPLAN_RESIDENT_REPAIR_DATA_DIR", "CLOUD_WATCHDOG_REPAIR_DATA_DIR"):
        value = os.environ.get(key, "").strip()
        if value:
            return Path(value) / "escalations" / "escalations.jsonl"
    return None


def _voice_attachment(message: Any) -> tuple[Any | None, str]:
    attachments = tuple(getattr(message, "attachments", ()) or ())
    supported: list[tuple[Any, str]] = []
    unsupported_audio = False
    for attachment in attachments:
        discord_voice = _is_discord_voice_attachment(attachment)
        extension = Path(str(getattr(attachment, "filename", "") or "")).suffix.lower()
        content_type = _attachment_content_type(attachment)
        looks_like_audio = (
            discord_voice
            or content_type.startswith("audio/")
            or content_type in {"application/ogg", "video/mp4", "video/webm"}
            or extension in SUPPORTED_AUDIO_EXTENSIONS
            or extension in {".aac", ".flac"}
        )
        if not looks_like_audio:
            continue
        if not _is_supported_audio_attachment(extension=extension, content_type=content_type):
            unsupported_audio = True
            continue
        supported.append((attachment, "discord_voice_message" if discord_voice else "discord_audio_attachment"))

    message_flags = getattr(message, "flags", None)
    message_is_voice = bool(getattr(message_flags, "voice", False))
    if unsupported_audio or (message_is_voice and not supported):
        raise VoiceMessageError("unsupported_audio_type", VOICE_FAILURE_UNSUPPORTED)
    if len(supported) > 1:
        raise VoiceMessageError("multiple_audio_attachments", VOICE_FAILURE_UNSUPPORTED)
    return supported[0] if supported else (None, "")


def _is_discord_voice_attachment(attachment: Any) -> bool:
    checker = getattr(attachment, "is_voice_message", None)
    if not callable(checker):
        return False
    try:
        return bool(checker())
    except Exception:
        return False


def _is_supported_audio_attachment(*, extension: str, content_type: str) -> bool:
    if extension and extension not in SUPPORTED_AUDIO_EXTENSIONS:
        return False
    if (
        content_type
        and content_type not in SUPPORTED_AUDIO_CONTENT_TYPES
        and content_type != "application/octet-stream"
    ):
        return False
    return extension in SUPPORTED_AUDIO_EXTENSIONS or content_type in SUPPORTED_AUDIO_CONTENT_TYPES


def _attachment_content_type(attachment: Any) -> str:
    value = str(getattr(attachment, "content_type", "") or "").strip().lower()
    return value.split(";", 1)[0].strip() or "application/octet-stream"


def _safe_attachment_filename(attachment: Any) -> str:
    original = Path(str(getattr(attachment, "filename", "") or "audio")).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", original).strip(".-")
    if not sanitized:
        sanitized = "audio"
    extension = Path(original).suffix.lower()
    if extension in SUPPORTED_AUDIO_EXTENSIONS and not sanitized.lower().endswith(extension):
        sanitized += extension
    return sanitized[-160:]


def _attachment_size(attachment: Any) -> int | None:
    return _optional_int(getattr(attachment, "size", None))


def _first_attachment(message: Any) -> Any | None:
    attachments = tuple(getattr(message, "attachments", ()) or ())
    return attachments[0] if attachments else None


async def _send_voice_failure(message: Any, user_message: str) -> None:
    channel = getattr(message, "channel", None)
    send = getattr(channel, "send", None)
    if not callable(send):
        LOGGER.error("Unable to deliver Discord voice failure: channel has no send method")
        return
    kwargs: dict[str, Any] = {}
    message_id = _optional_snowflake(getattr(message, "id", None))
    if message_id:
        reference = _partial_message_reference(channel, message_id)
        if reference is not None:
            kwargs["reference"] = reference
            kwargs["mention_author"] = False
    await send(user_message, **kwargs)


async def _send_timezone_reply(message: Any, user_message: str) -> None:
    """Reply to an authorized preference command without invoking the model."""

    await _send_voice_failure(message, user_message)


def _optional_int(value: object) -> int | None:
    try:
        result = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return result if result is not None and result >= 0 else None


class ResidentDiscordService:
    """Thin discord.py service that feeds Discord events into ResidentRuntime."""

    def __init__(
        self,
        *,
        runtime: ResidentRuntime,
        token: str,
        scheduler: ScheduledJobWorker | None = None,
        scheduler_interval_s: float = 10.0,
        transcriber: AudioTranscriber | None = None,
        attachment_downloader: AttachmentDownloader | None = None,
        restart_operation: Callable[[], Mapping[str, Any]] | None = None,
    ) -> None:
        if not token:
            raise ValueError("Discord token is required")
        self.runtime = runtime
        self.token = token
        self.scheduler = scheduler
        self.scheduler_interval_s = scheduler_interval_s
        self.transcriber = transcriber or OpenAICompatibleAudioTranscriber(runtime.config)
        self.attachment_downloader = attachment_downloader or DiscordAttachmentDownloader()
        self.restart_operation = restart_operation or restart_discord_resident
        self._scheduler_task: asyncio.Task[None] | None = None
        self._command_tree: Any | None = None
        self._commands_synced = False

    async def start(self) -> None:
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError("discord.py is required for `megaplan resident discord`") from exc

        logging.basicConfig(level=os.environ.get("MEGAPLAN_LOG_LEVEL", "INFO").upper())
        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        app_commands = getattr(discord, "app_commands", None)
        command_tree_type = getattr(app_commands, "CommandTree", None)
        if command_tree_type is not None:
            self._command_tree = command_tree_type(client)
            register_discord_application_commands(self._command_tree, self)
        else:  # pragma: no cover - supported discord.py always exposes this
            LOGGER.warning("discord.py application-command support is unavailable")

        @client.event
        async def on_ready() -> None:
            # Imported lazily to avoid making the low-level AgentBox outbox
            # depend on this package's eager public re-exports at import time.
            from agentbox.reset_notifications import (
                reconcile_prepared_reset_notifications,
                sweep_reset_notifications,
            )
            from agentbox.services import resident_process_identity

            outbound = getattr(self.runtime, "outbound", None)
            if isinstance(outbound, DiscordOutboundSink):
                outbound.bind_client(client)
            if self._command_tree is not None and not self._commands_synced:
                try:
                    synced = await self._command_tree.sync()
                except Exception:
                    LOGGER.exception("Resident Discord application-command sync failed")
                else:
                    self._commands_synced = True
                    LOGGER.info(
                        "Resident Discord application commands synced count=%s commands=%s",
                        len(synced),
                        ",".join(command.name for command in DISCORD_APPLICATION_COMMANDS),
                    )
            try:
                process_identity = await asyncio.wait_for(
                    asyncio.to_thread(resident_process_identity), timeout=3.0
                )
                restart_reconciliation = reconcile_prepared_reset_notifications(
                    current_identity=process_identity
                )
            except Exception:
                process_identity = None
                restart_reconciliation = {
                    "scanned": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "in_progress": 0,
                }
                LOGGER.exception("Resident restart transaction reconciliation failed")
            if self.runtime.config.allows_operational_discord_delivery:
                completion_delivery = await sweep_managed_agent_deliveries(
                    outbound=self.runtime.outbound,
                    project_root=Path.cwd(),
                    completion_turn_handler=getattr(
                        self.runtime, "run_managed_completion_turn", None
                    ),
                )
                reset_delivery = await sweep_reset_notifications(
                    outbound=self.runtime.outbound,
                    store=self.runtime.store,
                )
            else:
                completion_delivery = None
                reset_delivery = None
            try:
                restart_replayed = (
                    await self.runtime.recover_restart_interrupted_turns(process_identity)
                    if process_identity is not None
                    else 0
                )
                recovered = await self.runtime.recover_abandoned_turns()
            except Exception:
                restart_replayed = 0
                recovered = 0
                LOGGER.exception(
                    "Resident abandoned-turn recovery failed; operational outboxes were swept independently"
                )
            if isinstance(outbound, DiscordOutboundSink):
                reaction_delivery = await outbound.reconcile_reactions()
            else:
                reaction_delivery = None
            self._log_transcription_readiness()
            self._ensure_scheduler_started(client)
            self._seed_special_requests_job()
            user = getattr(client, "user", None)
            guilds = getattr(client, "guilds", ())
            LOGGER.info(
                "Resident Discord service ready user_id=%s guild_count=%s recovered_turns=%s "
                "restart_replayed_turns=%s restart_reconciled_succeeded=%s "
                "restart_reconciled_failed=%s restart_reconcile_in_progress=%s "
                "completion_delivery_scanned=%s completion_delivered=%s "
                "completion_retry_pending=%s completion_failed=%s "
                "reset_delivery_scanned=%s reset_delivered=%s reset_retry_pending=%s "
                "reset_waiting_for_target=%s reset_failed=%s "
                "reaction_effects_scanned=%s reaction_effects_applied=%s "
                "reaction_effects_retry_pending=%s",
                getattr(user, "id", None),
                len(guilds),
                recovered,
                restart_replayed,
                restart_reconciliation["succeeded"],
                restart_reconciliation["failed"],
                restart_reconciliation["in_progress"],
                completion_delivery.scanned if completion_delivery is not None else 0,
                completion_delivery.delivered if completion_delivery is not None else 0,
                completion_delivery.retry_pending if completion_delivery is not None else 0,
                completion_delivery.failed if completion_delivery is not None else 0,
                reset_delivery.scanned if reset_delivery is not None else 0,
                reset_delivery.delivered if reset_delivery is not None else 0,
                reset_delivery.retry_pending if reset_delivery is not None else 0,
                reset_delivery.waiting_for_target if reset_delivery is not None else 0,
                reset_delivery.failed if reset_delivery is not None else 0,
                reaction_delivery.scanned if reaction_delivery is not None else 0,
                reaction_delivery.applied if reaction_delivery is not None else 0,
                reaction_delivery.retry_pending if reaction_delivery is not None else 0,
            )

        @client.event
        async def on_message(message: Any) -> None:
            if getattr(getattr(message, "author", None), "bot", False):
                return
            try:
                await self.handle_message(message)
            except Exception:
                LOGGER.exception("Resident Discord message handling failed")

        @client.event
        async def on_error(event_method: str, *args: Any, **kwargs: Any) -> None:
            LOGGER.exception("Resident Discord client event failed: %s", event_method)

        await client.start(self.token)

    async def handle_currently_running_interaction(self, interaction: Any) -> None:
        """Serve ``/currently-running`` without invoking the resident model."""

        user_id = _optional_snowflake(
            getattr(getattr(interaction, "user", None), "id", None)
        )
        guild_id = _optional_snowflake(getattr(interaction, "guild_id", None))
        channel = getattr(interaction, "channel", None)
        parent = getattr(channel, "parent", None)
        channel_id = _optional_snowflake(
            getattr(parent, "id", None)
            if parent is not None
            else getattr(interaction, "channel_id", None)
        )
        subject = AuthorizationSubject(
            user_id=user_id or "",
            guild_id=guild_id,
            channel_id=channel_id,
        )
        authorizer = getattr(self.runtime, "authorizer", None)
        decision = authorizer.authorize_inbound(subject) if authorizer is not None else None
        if not user_id or decision is None or not decision.allowed:
            await interaction.response.send_message(
                "This command is not authorized in this Discord context.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        try:
            report = await collect_currently_running(self.runtime)
            rendered = render_currently_running(report)
        except Exception:
            LOGGER.exception("Resident currently-running command failed")
            rendered = (
                "**Currently running**\n"
                "⚠️ Canonical status is temporarily unavailable; no running-state claims were made."
            )
        for chunk in split_discord_message(rendered):
            await interaction.followup.send(chunk)

    async def handle_restart_resident_interaction(self, interaction: Any) -> None:
        """Authorize and hand ``/restart-resident`` to the guarded lifecycle API."""

        user_id = _optional_snowflake(
            getattr(getattr(interaction, "user", None), "id", None)
        )
        guild_id = _optional_snowflake(getattr(interaction, "guild_id", None))
        channel = getattr(interaction, "channel", None)
        parent = getattr(channel, "parent", None)
        channel_id = _optional_snowflake(
            getattr(parent, "id", None)
            if parent is not None
            else getattr(interaction, "channel_id", None)
        )
        subject = AuthorizationSubject(
            user_id=user_id or "",
            guild_id=guild_id,
            channel_id=channel_id,
        )
        authorizer = getattr(self.runtime, "authorizer", None)
        decision = (
            authorizer.authorize_action(subject, "admin")
            if authorizer is not None and user_id
            else None
        )
        if decision is None or not decision.allowed:
            await interaction.response.send_message(
                "This command requires resident administrator authorization.",
                ephemeral=True,
            )
            return

        # Discord confirms this response before the external supervisor is
        # allowed to replace the resident process.
        await interaction.response.send_message(
            RESTART_RESIDENT_ACKNOWLEDGEMENT,
            ephemeral=True,
        )
        operation = getattr(self, "restart_operation", restart_discord_resident)
        try:
            result = await asyncio.to_thread(operation)
        except Exception:
            LOGGER.exception("Guarded Discord resident restart invocation failed")
            await interaction.followup.send(
                "The resident restart did not return a confirmed acceptance. "
                "No restart outcome is being claimed; check the durable lifecycle status.",
                ephemeral=True,
            )
            return

        if not isinstance(result, Mapping):
            await interaction.followup.send(
                "The resident restart returned no valid lifecycle result. "
                "No restart outcome is being claimed; check the durable lifecycle status.",
                ephemeral=True,
            )
            return

        if not result.get("ok"):
            error = redact_text(
                str(result.get("error") or "restart safety preflight failed")
            )
            await interaction.followup.send(
                f"The resident restart was refused safely: {error}. "
                "No restart was performed.",
                ephemeral=True,
            )
            return

        if result.get("duplicate"):
            message = (
                "This restart request was already processed; no second resident "
                "restart was started."
            )
        else:
            message = (
                "The guarded resident restart was accepted. Only the Discord resident "
                "is targeted; replacement health is verified by the durable lifecycle "
                "supervisor after reconnect."
            )
        # Best effort: the awaited warning above is the delivery guarantee, as
        # the resident may be replaced before this follow-up reaches Discord.
        await interaction.followup.send(message, ephemeral=True)

    async def handle_message(self, message: Any) -> None:
        """Convert one Discord message into a resident event, transcribing audio first."""

        inbound = DiscordInboundMessage.from_discord_message(message)
        authorizer = getattr(self.runtime, "authorizer", None)
        authorization_decision = (
            authorizer.authorize_inbound(inbound.to_inbound_event().subject)
            if authorizer is not None
            else None
        )
        if authorization_decision is not None and not authorization_decision.allowed:
            # Let the runtime perform its canonical denial audit, but do not
            # download or transcribe content from an unauthorized sender.
            await self.runtime.receive(
                inbound.to_inbound_event(),
                authorization_decision=authorization_decision,
            )
            return
        if await self._handle_timezone_command(message, inbound):
            return
        inbound = replace(inbound, reply_chain=await _capture_discord_reply_chain(message))
        try:
            attachment, input_kind = _voice_attachment(message)
            if attachment is not None:
                inbound = await self._transcribe_attachment(inbound, attachment, input_kind=input_kind)
        except VoiceMessageError as exc:
            safe_config = self._safe_transcription_configuration()
            LOGGER.warning(
                "Resident Discord voice input rejected message_id=%s attachment_id=%s code=%s "
                "provider=%s model=%s endpoint_host=%s credential_env=%s credential_present=%s",
                inbound.message_id,
                _optional_snowflake(getattr(_first_attachment(message), "id", None)),
                exc.code,
                safe_config.get("provider", "unknown"),
                safe_config.get("model", "unknown"),
                safe_config.get("endpoint_host", "unknown"),
                safe_config.get("credential_env", "unknown"),
                safe_config.get("credential_present", "unknown"),
            )
            await _send_voice_failure(message, exc.user_message)
            return
        LOGGER.info(
            "Resident Discord inbound message_id=%s author_id=%s conversation_key=%s content_length=%s voice=%s",
            inbound.message_id,
            inbound.author_id,
            inbound.target.conversation_key,
            len(inbound.content),
            inbound.was_voice_message,
        )
        if authorization_decision is None:
            await self.runtime.receive(inbound.to_inbound_event())
        else:
            await self.runtime.receive(
                inbound.to_inbound_event(),
                authorization_decision=authorization_decision,
            )

    async def _handle_timezone_command(
        self, message: Any, inbound: DiscordInboundMessage
    ) -> bool:
        content = inbound.content.strip()
        if content != "/timezone" and not content.startswith("/timezone "):
            return False
        service = TimezoneService(self.runtime.store, self.runtime.config)
        conversation = self.runtime.store.get_resident_conversation_by_key(
            transport="discord",
            conversation_key=inbound.target.conversation_key,
        )
        argument = content[len("/timezone") :].strip()
        if argument.lower().startswith("set "):
            argument = argument[4:].strip()
        if argument:
            try:
                preference = service.set_user_timezone(
                    inbound.author_id,
                    argument,
                    idempotency_key=deterministic_idempotency_key(
                        "resident-user-timezone-command", inbound.message_id
                    ),
                )
            except InvalidTimezone as exc:
                await _send_timezone_reply(
                    message,
                    f"I couldn't update your timezone: {exc}. Use an IANA name such as `America/New_York`.",
                )
                return True
            await _send_timezone_reply(
                message,
                f"Timezone set to `{preference.timezone_name}`. It will apply to your next message and delegated result.",
            )
            return True
        preference = service.get_user_preference(inbound.author_id)
        resolved = service.resolve(
            user_id=inbound.author_id,
            conversation=conversation,
            guild_id=inbound.target.guild_id,
        )
        configured = preference.timezone_name if preference is not None else None
        if configured:
            text = f"Your timezone is `{configured}` (effective source: {resolved.source})."
        else:
            text = (
                f"No user timezone is set; effective timezone is `{resolved.name}` "
                f"from {resolved.source}. Set one with `/timezone America/New_York`."
            )
        await _send_timezone_reply(message, text)
        return True

    async def _transcribe_attachment(
        self,
        inbound: DiscordInboundMessage,
        attachment: Any,
        *,
        input_kind: str,
    ) -> DiscordInboundMessage:
        config = self.runtime.config
        if not config.voice_transcription_enabled:
            raise VoiceMessageError("transcription_disabled", VOICE_FAILURE_DISABLED)
        declared_size = _attachment_size(attachment)
        if declared_size is not None and declared_size > config.voice_max_attachment_bytes:
            raise VoiceMessageError("attachment_too_large", VOICE_FAILURE_TOO_LARGE)
        filename = _safe_attachment_filename(attachment)
        content_type = _attachment_content_type(attachment)
        data = await self.attachment_downloader.download(
            attachment,
            max_bytes=config.voice_max_attachment_bytes,
            timeout_s=config.voice_download_timeout_s,
        )
        if not data:
            raise VoiceMessageError("empty_attachment", VOICE_FAILURE_DOWNLOAD)
        try:
            transcript = await self.transcriber.transcribe(
                data=data,
                filename=filename,
                content_type=content_type,
            )
        except asyncio.CancelledError:
            raise
        except AudioTranscriptionError as exc:
            raise VoiceMessageError(f"transcription_{exc.code}", VOICE_FAILURE_ENDPOINT) from exc
        except Exception as exc:
            raise VoiceMessageError("transcription_failed", VOICE_FAILURE_ENDPOINT) from exc
        if not transcript.strip():
            raise VoiceMessageError("empty_transcript", VOICE_FAILURE_ENDPOINT)
        metadata = {
            "source": input_kind,
            "status": "completed",
            "discord_message_id": inbound.message_id,
            "discord_attachment_id": _optional_snowflake(getattr(attachment, "id", None)),
            "filename": filename,
            "content_type": content_type,
            "declared_size_bytes": declared_size,
            "downloaded_size_bytes": len(data),
            "model": config.voice_transcription_model,
            "provider": config.voice_transcription_provider,
            "normalization": (
                "ogg_opus_to_webm"
                if Path(filename).suffix.lower() in {".ogg", ".opus"}
                or content_type.partition(";")[0].strip().lower()
                in {"audio/ogg", "application/ogg", "audio/opus"}
                else "none"
            ),
        }
        return inbound.with_transcript(transcript.strip(), metadata)

    def _safe_transcription_configuration(self) -> dict[str, Any]:
        diagnostics = getattr(self.transcriber, "safe_configuration", None)
        if not callable(diagnostics):
            return {}
        try:
            result = diagnostics()
        except Exception:
            LOGGER.exception("Failed to inspect resident voice transcription configuration")
            return {}
        return result if isinstance(result, dict) else {}

    def _log_transcription_readiness(self) -> None:
        if not self.runtime.config.voice_transcription_enabled:
            LOGGER.info("Resident voice transcription disabled")
            return
        safe_config = self._safe_transcription_configuration()
        if not safe_config:
            return
        log = LOGGER.info if safe_config.get("credential_present") else LOGGER.warning
        log(
            "Resident voice transcription configuration provider=%s model=%s endpoint_host=%s "
            "credential_env=%s credential_present=%s",
            safe_config.get("provider", "unknown"),
            safe_config.get("model", "unknown"),
            safe_config.get("endpoint_host", "unknown"),
            safe_config.get("credential_env", "unknown"),
            safe_config.get("credential_present", False),
        )

    def run(self) -> None:
        asyncio.run(self.start())

    def _ensure_scheduler_started(self, client: Any) -> None:
        if self._scheduler_task is not None and not self._scheduler_task.done():
            return
        self._scheduler_task = client.loop.create_task(self._scheduler_loop(client))

    def _seed_special_requests_job(self) -> None:
        config = self.runtime.config
        if not config.special_requests_enabled:
            return
        subject_user_id = (
            config.special_requests_subject_user_id
            or (config.allowed_user_ids[0] if config.allowed_user_ids else None)
            or (config.admin_user_ids[0] if config.admin_user_ids else None)
        )
        if not subject_user_id:
            LOGGER.warning(
                "VP to-do sweep enabled but no user id configured "
                "(allowed_user_ids or admin_user_ids); skipping seed"
            )
            return
        # Default target is a DM to the admin user; a conversation_key override
        # (e.g. a guild channel) may be set for non-DM delivery.
        conversation_key = (
            config.special_requests_conversation_key
            or f"discord:dm:{subject_user_id}"
        )
        store = self.runtime.store
        if store.list_scheduled_jobs(job_type="vp_todo_sweep", status="pending", limit=1):
            return
        target = DiscordDeliveryTarget.from_conversation_key(conversation_key)
        interval_s = int(config.special_requests_interval_s)
        payload = {
            "conversation_key": conversation_key,
            "subject_user_id": subject_user_id,
            "guild_id": target.guild_id,
            # A DM has no channel id; leave it unset so the inbound channel
            # allowlist (if any) doesn't block the system-generated turn.
            "channel_id": None if target.dm_user_id else target.channel_id,
            "dm_user_id": target.dm_user_id,
            "interval_s": interval_s,
        }
        store.create_scheduled_job(
            ScheduledJobInput(
                job_type="vp_todo_sweep",
                payload=payload,
                scheduled_for=datetime.now(UTC),
                max_attempts=3,
            ),
            idempotency_key=deterministic_idempotency_key(
                "resident-vp-todo-sweep-seed", conversation_key
            ),
        )
        LOGGER.info(
            "VP to-do sweep job seeded target=%s interval_s=%s",
            conversation_key,
            interval_s,
        )

    async def _scheduler_loop(self, client: Any) -> None:
        LOGGER.info("Resident scheduler loop started interval_s=%s", self.scheduler_interval_s)
        while not client.is_closed():
            try:
                from agentbox.reset_notifications import sweep_reset_notifications

                if self.runtime.config.allows_operational_discord_delivery:
                    delivery = await sweep_managed_agent_deliveries(
                        outbound=self.runtime.outbound,
                        project_root=Path.cwd(),
                        completion_turn_handler=getattr(
                            self.runtime, "run_managed_completion_turn", None
                        ),
                    )
                    if delivery.delivered or delivery.retry_pending or delivery.failed:
                        LOGGER.info(
                            "Resident managed-agent delivery sweep scanned=%s delivered=%s retry_pending=%s failed=%s",
                            delivery.scanned,
                            delivery.delivered,
                            delivery.retry_pending,
                            delivery.failed,
                        )
                    reset_delivery = await sweep_reset_notifications(
                        outbound=self.runtime.outbound,
                        store=self.runtime.store,
                    )
                    if (
                        reset_delivery.delivered
                        or reset_delivery.retry_pending
                        or reset_delivery.failed
                        or reset_delivery.waiting_for_target
                    ):
                        LOGGER.info(
                            "Resident reset-notification sweep scanned=%s delivered=%s "
                            "retry_pending=%s waiting_for_target=%s failed=%s",
                            reset_delivery.scanned,
                            reset_delivery.delivered,
                            reset_delivery.retry_pending,
                            reset_delivery.waiting_for_target,
                            reset_delivery.failed,
                        )
                if self.scheduler is not None:
                    result = await self.scheduler.run_due_once()
                    if result.claimed:
                        LOGGER.info(
                            "Resident scheduler processed claimed=%s fired=%s retried=%s cancelled=%s",
                            result.claimed,
                            result.fired,
                            result.retried,
                            result.cancelled,
                        )
            except Exception:
                LOGGER.exception("Resident scheduler loop failed")
            await asyncio.sleep(max(1.0, self.scheduler_interval_s))


def discord_token_from_env(env_name: str) -> str | None:
    token = os.environ.get(env_name)
    return token.strip() if token and token.strip() else None


def _optional_snowflake(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
