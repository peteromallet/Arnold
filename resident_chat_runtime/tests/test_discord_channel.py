from typing import Any

import pytest

from resident_chat_runtime.discord_channel import (
    ChannelFile,
    channel_typing,
    edit_channel_message,
    fetch_channel,
    fetch_recent_messages,
    send_channel_message,
)


class FakeMessage:
    def __init__(self) -> None:
        self.edits: list[dict[str, Any]] = []

    async def edit(self, **kwargs: Any) -> "FakeMessage":
        self.edits.append(kwargs)
        return self


class FakeTyping:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> None:
        self.entered = True

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.exited = True


class FakeHistory:
    def __init__(self, items: list[str]) -> None:
        self._items = items

    def __aiter__(self) -> "FakeHistory":
        self._iter = iter(self._items)
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeChannel:
    def __init__(self) -> None:
        self.sent: list[tuple[Any, dict[str, Any]]] = []
        self.typing_manager = FakeTyping()

    async def send(self, content: Any = None, **kwargs: Any) -> dict[str, Any]:
        self.sent.append((content, kwargs))
        return {"content": content, **kwargs}

    def typing(self) -> FakeTyping:
        return self.typing_manager

    def history(self, *, limit: int) -> FakeHistory:
        return FakeHistory([f"message-{limit}"])


class FakeClient:
    def __init__(self) -> None:
        self.cached = FakeChannel()
        self.fetched = FakeChannel()

    def get_channel(self, channel_id: int) -> FakeChannel | None:
        return self.cached if channel_id == 1 else None

    async def fetch_channel(self, channel_id: int) -> FakeChannel:
        return self.fetched


@pytest.mark.asyncio
async def test_send_edit_typing_and_fetch_helpers() -> None:
    channel = FakeChannel()

    result = await send_channel_message(
        channel,
        "hello",
        files=[ChannelFile("a.txt", filename="renamed.txt")],
        file_factory=lambda path, *, filename=None: {"path": str(path), "filename": filename},
    )
    message = FakeMessage()
    edited = await edit_channel_message(message, "updated", suppress=True)
    async with channel_typing(channel):
        assert channel.typing_manager.entered is True

    client = FakeClient()
    cached = await fetch_channel(client, 1)
    fetched = await fetch_channel(client, 2)
    recent = await fetch_recent_messages(channel, limit=5)

    assert result["content"] == "hello"
    assert result["files"] == [{"path": "a.txt", "filename": "renamed.txt"}]
    assert edited is message
    assert message.edits == [{"content": "updated", "suppress": True}]
    assert channel.typing_manager.exited is True
    assert cached is client.cached
    assert fetched is client.fetched
    assert recent == ["message-5"]
