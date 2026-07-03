"""Discord adapter boundary for resident Megaplan conversations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import re
from typing import Any

from arnold_pipelines.megaplan.store import ScheduledJobInput, deterministic_idempotency_key

from .auth import AuthorizationSubject
from .runtime import InboundEvent, OutboundMessage, OutboundSink, ResidentRuntime
from .scheduler import ScheduledJobWorker

LOGGER = logging.getLogger(__name__)
DISCORD_MESSAGE_LIMIT = 2000
DISCORD_SAFE_MESSAGE_LIMIT = 1900
ESCALATION_TAG_RE = re.compile(r"\[escalation:([A-Za-z0-9._:-]+)\]", re.IGNORECASE)


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
    escalation_id: str | None = None

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
                "escalation_id": self.escalation_id,
                "thread_id": self.target.thread_id,
                "dm_user_id": self.target.dm_user_id,
            },
        )


class DiscordOutboundSink(OutboundSink):
    """Deliver resident outbound messages to Discord using durable targets."""

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def bind_client(self, client: Any) -> None:
        self.client = client

    async def send(self, message: OutboundMessage) -> None:
        if self.client is None:
            raise RuntimeError("Discord client is not bound")
        target = DiscordDeliveryTarget.from_conversation_key(message.conversation_key)
        channel = await self._resolve_channel(target)
        sent_messages = []
        for chunk in split_discord_message(message.content):
            sent_messages.append(await channel.send(chunk))
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


class ResidentDiscordService:
    """Thin discord.py service that feeds Discord events into ResidentRuntime."""

    def __init__(
        self,
        *,
        runtime: ResidentRuntime,
        token: str,
        scheduler: ScheduledJobWorker | None = None,
        scheduler_interval_s: float = 10.0,
    ) -> None:
        if not token:
            raise ValueError("Discord token is required")
        self.runtime = runtime
        self.token = token
        self.scheduler = scheduler
        self.scheduler_interval_s = scheduler_interval_s
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
            outbound = getattr(self.runtime, "outbound", None)
            if isinstance(outbound, DiscordOutboundSink):
                outbound.bind_client(client)
            recovered = await self.runtime.recover_abandoned_turns()
            self._ensure_scheduler_started(client)
            self._seed_special_requests_job()
            user = getattr(client, "user", None)
            guilds = getattr(client, "guilds", ())
            LOGGER.info(
                "Resident Discord service ready user_id=%s guild_count=%s recovered_turns=%s",
                getattr(user, "id", None),
                len(guilds),
                recovered,
            )

        @client.event
        async def on_message(message: Any) -> None:
            if getattr(getattr(message, "author", None), "bot", False):
                return
            try:
                inbound = DiscordInboundMessage.from_discord_message(message)
                LOGGER.info(
                    "Resident Discord inbound message_id=%s author_id=%s conversation_key=%s content_length=%s",
                    inbound.message_id,
                    inbound.author_id,
                    inbound.target.conversation_key,
                    len(inbound.content),
                )
                await self.runtime.receive(inbound.to_inbound_event())
            except Exception:
                LOGGER.exception("Resident Discord message handling failed")

        @client.event
        async def on_error(event_method: str, *args: Any, **kwargs: Any) -> None:
            LOGGER.exception("Resident Discord client event failed: %s", event_method)

        await client.start(self.token)

    def run(self) -> None:
        asyncio.run(self.start())

    def _ensure_scheduler_started(self, client: Any) -> None:
        if self.scheduler is None:
            return
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
