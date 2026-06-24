"""Notification test helper for AgentBox resident channels."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from datetime import UTC, datetime
from typing import Any

from agentbox.config import AgentBoxConfig
from agentbox.guardian.service import _resident_store_root


def notify_test(
    config: AgentBoxConfig,
    *,
    conversation_key: str | None = None,
    dm_user_id: str | None = None,
    outbound: Any | None = None,
) -> dict[str, Any]:
    """Send a test notification through the configured Discord resident channel.

    ``outbound`` is an optional DiscordOutboundSink-like sink, primarily for tests.
    """

    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        return {
            "ok": False,
            "error": "DISCORD_BOT_TOKEN is not set",
            "fix_command": "set DISCORD_BOT_TOKEN",
        }

    if importlib.util.find_spec("discord") is None:
        return {
            "ok": False,
            "error": "discord.py is not installed",
            "fix_command": "pip install discord.py",
        }

    target_conversation = conversation_key
    if target_conversation is None and dm_user_id is not None:
        target_conversation = f"discord:dm:{dm_user_id}"

    if target_conversation is None:
        store = _load_resident_store(config)
        if store is not None:
            conversations = store.list_resident_conversations(transport="discord", limit=10)
            for conversation in conversations:
                if conversation.conversation_key:
                    target_conversation = conversation.conversation_key
                    break

    if target_conversation is None:
        return {
            "ok": False,
            "error": "no target conversation provided and none found in store",
            "reason": "no target",
        }

    content = (
        f"AgentBox notify test at {datetime.now(UTC).isoformat()} "
        f"to {target_conversation}"
    )

    sink = outbound
    if sink is not None:
        return asyncio.run(_send_with_sink(sink, target_conversation, content))

    from arnold_pipelines.megaplan.resident.discord import DiscordOutboundSink

    sink = DiscordOutboundSink()
    return asyncio.run(_send_with_client(sink, token, target_conversation, content))


async def _send_with_sink(sink: Any, conversation_key: str, content: str) -> dict[str, Any]:
    await sink.send(_outbound_message(conversation_key, content))
    return {
        "ok": True,
        "conversation_key": conversation_key,
        "message_id": "sent",
    }


async def _send_with_client(
    sink: Any,
    token: str,
    conversation_key: str,
    content: str,
) -> dict[str, Any]:
    import discord

    client = discord.Client(
        intents=discord.Intents.default(),
    )
    if hasattr(sink, "bind_client"):
        sink.bind_client(client)

    message_id: str | None = None

    @client.event
    async def on_ready() -> None:
        nonlocal message_id
        try:
            await sink.send(
                _outbound_message(conversation_key, content),
            )
            message_id = "sent"
        finally:
            await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure as exc:
        return {
            "ok": False,
            "error": f"Discord login failed: {exc}",
            "fix_command": "check DISCORD_BOT_TOKEN",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Discord client error: {exc}",
        }
    return {
        "ok": message_id is not None,
        "conversation_key": conversation_key,
        "message_id": message_id,
    }


def _load_resident_store(config: AgentBoxConfig) -> Any | None:
    try:
        from arnold_pipelines.megaplan.store import FileStore

        return FileStore(_resident_store_root(config))
    except Exception:
        return None


def _outbound_message(conversation_key: str, content: str) -> Any:
    from arnold_pipelines.megaplan.resident.runtime import OutboundMessage

    return OutboundMessage(
        conversation_key=conversation_key,
        content=content,
        idempotency_key=f"agentbox-notify-test-{datetime.now(UTC).isoformat()}",
        metadata={},
    )


__all__ = [
    "notify_test",
]
