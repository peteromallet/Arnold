"""Discord adapter boundary for resident Megaplan conversations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
from arnold_pipelines.megaplan.store import ScheduledJobInput, deterministic_idempotency_key

from .auth import AuthorizationSubject
from .runtime import InboundEvent, OutboundMessage, OutboundSink, ResidentRuntime
from .scheduler import ScheduledJobWorker
from .subagent import sweep_managed_agent_deliveries
from .transcription import AudioTranscriptionError, OpenAICompatibleAudioTranscriber

LOGGER = logging.getLogger(__name__)
DISCORD_MESSAGE_LIMIT = 2000
DISCORD_SAFE_MESSAGE_LIMIT = 1900
DISCORD_REPLY_REACTION = "☑️"
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
    ) -> None:
        self.client = client
        self.delivery_environment = str(delivery_environment).strip().lower()
        self.bot_role = str(bot_role).strip().lower()

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
        if reply_to_message_id:
            await _add_reply_reaction(channel, reply_to_message_id)
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


def _partial_message_reference(channel: Any, message_id: str) -> Any | None:
    get_partial_message = getattr(channel, "get_partial_message", None)
    if not callable(get_partial_message):
        return None
    try:
        return get_partial_message(int(message_id))
    except (TypeError, ValueError):
        return None


async def _add_reply_reaction(channel: Any, message_id: str) -> None:
    message = _partial_message_reference(channel, message_id)
    if message is None:
        fetch_message = getattr(channel, "fetch_message", None)
        if callable(fetch_message):
            try:
                message = await fetch_message(int(message_id))
            except Exception:
                LOGGER.exception("Failed to fetch Discord message for reply reaction message_id=%s", message_id)
                return
    add_reaction = getattr(message, "add_reaction", None)
    if not callable(add_reaction):
        return
    try:
        await add_reaction(DISCORD_REPLY_REACTION)
    except Exception:
        LOGGER.exception("Failed to add Discord reply reaction message_id=%s", message_id)


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
    ) -> None:
        if not token:
            raise ValueError("Discord token is required")
        self.runtime = runtime
        self.token = token
        self.scheduler = scheduler
        self.scheduler_interval_s = scheduler_interval_s
        self.transcriber = transcriber or OpenAICompatibleAudioTranscriber(runtime.config)
        self.attachment_downloader = attachment_downloader or DiscordAttachmentDownloader()
        self._scheduler_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError("discord.py is required for `megaplan resident discord`") from exc

        logging.basicConfig(level=os.environ.get("MEGAPLAN_LOG_LEVEL", "INFO").upper())
        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready() -> None:
            # Imported lazily to avoid making the low-level AgentBox outbox
            # depend on this package's eager public re-exports at import time.
            from agentbox.reset_notifications import sweep_reset_notifications

            outbound = getattr(self.runtime, "outbound", None)
            if isinstance(outbound, DiscordOutboundSink):
                outbound.bind_client(client)
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
                recovered = await self.runtime.recover_abandoned_turns()
            except Exception:
                recovered = 0
                LOGGER.exception(
                    "Resident abandoned-turn recovery failed; operational outboxes were swept independently"
                )
            self._log_transcription_readiness()
            self._ensure_scheduler_started(client)
            self._seed_special_requests_job()
            user = getattr(client, "user", None)
            guilds = getattr(client, "guilds", ())
            LOGGER.info(
                "Resident Discord service ready user_id=%s guild_count=%s recovered_turns=%s "
                "completion_delivery_scanned=%s completion_delivered=%s "
                "completion_retry_pending=%s completion_failed=%s "
                "reset_delivery_scanned=%s reset_delivered=%s reset_retry_pending=%s "
                "reset_waiting_for_target=%s reset_failed=%s",
                getattr(user, "id", None),
                len(guilds),
                recovered,
                completion_delivery.scanned if completion_delivery is not None else 0,
                completion_delivery.delivered if completion_delivery is not None else 0,
                completion_delivery.retry_pending if completion_delivery is not None else 0,
                completion_delivery.failed if completion_delivery is not None else 0,
                reset_delivery.scanned if reset_delivery is not None else 0,
                reset_delivery.delivered if reset_delivery is not None else 0,
                reset_delivery.retry_pending if reset_delivery is not None else 0,
                reset_delivery.waiting_for_target if reset_delivery is not None else 0,
                reset_delivery.failed if reset_delivery is not None else 0,
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
