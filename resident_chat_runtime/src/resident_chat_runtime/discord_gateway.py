from __future__ import annotations

from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

GatewayCallback = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class GatewayCallbacks:
    on_ready: GatewayCallback | None = None
    on_message_create: GatewayCallback | None = None
    on_message_update: GatewayCallback | None = None
    on_message_delete: GatewayCallback | None = None
    on_reaction_add: GatewayCallback | None = None
    on_event: GatewayCallback | None = None


@dataclass
class DiscordGatewayLoop:
    callbacks: GatewayCallbacks = field(default_factory=GatewayCallbacks)
    event_names: dict[str, str] = field(
        default_factory=lambda: {
            "READY": "on_ready",
            "MESSAGE_CREATE": "on_message_create",
            "MESSAGE_UPDATE": "on_message_update",
            "MESSAGE_DELETE": "on_message_delete",
            "MESSAGE_REACTION_ADD": "on_reaction_add",
        }
    )

    async def dispatch_payload(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("t")
        data = payload.get("d")
        event_payload = data if isinstance(data, dict) else payload
        if self.callbacks.on_event is not None:
            await self.callbacks.on_event(payload)
        callback_name = self.event_names.get(str(event_type))
        if callback_name is None:
            return
        callback = getattr(self.callbacks, callback_name)
        if callback is not None:
            await callback(event_payload)

    async def run(self, payloads: AsyncIterable[dict[str, Any]]) -> None:
        async for payload in payloads:
            await self.dispatch_payload(payload)
