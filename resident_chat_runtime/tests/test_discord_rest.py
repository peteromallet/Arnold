from typing import Any

import pytest

from resident_chat_runtime.discord_rest import DiscordFilePayload, DiscordRestClient


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((method, url, kwargs))
        return {"ok": True}


@pytest.mark.asyncio
async def test_discord_rest_shapes_headers_and_json_message() -> None:
    session = FakeSession()
    client = DiscordRestClient(token="token", session=session, api_base="https://discord.test")

    result = await client.send_message(123, content="hello")

    assert result == {"ok": True}
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://discord.test/channels/123/messages"
    assert kwargs["headers"]["Authorization"] == "Bot token"
    assert kwargs["json"] == {"content": "hello"}


@pytest.mark.asyncio
async def test_discord_rest_typing_edit_fetch_and_files() -> None:
    session = FakeSession()
    client = DiscordRestClient(token="token", session=session, api_base="https://discord.test")

    await client.send_typing("c1")
    await client.edit_message("c1", "m1", content="updated")
    await client.fetch_channel_messages("c1", limit=10, before="m0")
    await client.send_message(
        "c1",
        content="with file",
        files=[DiscordFilePayload(filename="a.txt", content=b"hello", content_type="text/plain")],
    )

    assert [call[0] for call in session.calls] == ["POST", "PATCH", "GET", "POST"]
    assert session.calls[0][1].endswith("/channels/c1/typing")
    assert session.calls[1][2]["json"] == {"content": "updated"}
    assert session.calls[2][2]["params"] == {"limit": 10, "before": "m0"}
    assert session.calls[3][2]["files"] == [
        {
            "field": "files[0]",
            "filename": "a.txt",
            "content": b"hello",
            "content_type": "text/plain",
        }
    ]
