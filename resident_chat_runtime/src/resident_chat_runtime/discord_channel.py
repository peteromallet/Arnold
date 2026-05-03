from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class DiscordFileFactory(Protocol):
    def __call__(self, path: str | Path, *, filename: str | None = None) -> Any: ...


@dataclass(frozen=True)
class ChannelFile:
    path: str | Path
    filename: str | None = None


def default_discord_file_factory(path: str | Path, *, filename: str | None = None) -> Any:
    import discord  # type: ignore[import-not-found]

    return discord.File(str(path), filename=filename)


async def send_channel_message(
    channel: Any,
    content: str | None = None,
    *,
    files: list[ChannelFile] | None = None,
    file_factory: DiscordFileFactory | None = None,
    **kwargs: Any,
) -> Any:
    if files:
        factory = file_factory or default_discord_file_factory
        kwargs["files"] = [factory(item.path, filename=item.filename) for item in files]
    return await channel.send(content, **kwargs)


async def edit_channel_message(message: Any, content: str | None = None, **kwargs: Any) -> Any:
    return await message.edit(content=content, **kwargs)


async def fetch_channel(client: Any, channel_id: int | str) -> Any:
    getter = getattr(client, "get_channel", None)
    if getter is not None:
        channel = getter(int(channel_id))
        if channel is not None:
            return channel
    return await client.fetch_channel(int(channel_id))


async def fetch_recent_messages(channel: Any, *, limit: int = 50) -> list[Any]:
    history = channel.history(limit=limit)
    if hasattr(history, "__aiter__"):
        return [message async for message in history]
    return await history.flatten()


@asynccontextmanager
async def channel_typing(channel: Any) -> AsyncIterator[None]:
    manager = channel.typing()
    async with manager:
        yield
