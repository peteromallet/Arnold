from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

DISCORD_API_BASE = "https://discord.com/api/v10"


class AsyncHTTPSession(Protocol):
    async def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class DiscordFilePayload:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


class DiscordRestClient:
    def __init__(
        self,
        *,
        token: str,
        session: AsyncHTTPSession,
        api_base: str = DISCORD_API_BASE,
        user_agent: str = "resident-chat-runtime",
    ) -> None:
        self._token = token
        self._session = session
        self._api_base = api_base.rstrip("/")
        self._user_agent = user_agent

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self._token}",
            "User-Agent": self._user_agent,
        }

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        return await self._session.request(method, f"{self._api_base}{path}", headers=headers, **kwargs)

    async def send_message(
        self,
        channel_id: int | str,
        *,
        content: str | None = None,
        embeds: list[Mapping[str, Any]] | None = None,
        files: list[DiscordFilePayload] | None = None,
    ) -> Any:
        payload: dict[str, Any] = {}
        if content is not None:
            payload["content"] = content
        if embeds is not None:
            payload["embeds"] = embeds
        if files:
            return await self.request(
                "POST",
                f"/channels/{channel_id}/messages",
                json=payload,
                files=[
                    {
                        "field": f"files[{idx}]",
                        "filename": item.filename,
                        "content": item.content,
                        "content_type": item.content_type,
                    }
                    for idx, item in enumerate(files)
                ],
            )
        return await self.request("POST", f"/channels/{channel_id}/messages", json=payload)

    async def send_typing(self, channel_id: int | str) -> Any:
        return await self.request("POST", f"/channels/{channel_id}/typing")

    async def edit_message(self, channel_id: int | str, message_id: int | str, **payload: Any) -> Any:
        return await self.request("PATCH", f"/channels/{channel_id}/messages/{message_id}", json=payload)

    async def fetch_channel_messages(
        self,
        channel_id: int | str,
        *,
        limit: int = 50,
        before: int | str | None = None,
        after: int | str | None = None,
    ) -> Any:
        params: dict[str, Any] = {"limit": limit}
        if before is not None:
            params["before"] = before
        if after is not None:
            params["after"] = after
        return await self.request("GET", f"/channels/{channel_id}/messages", params=params)
