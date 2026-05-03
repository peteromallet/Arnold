import pytest

from resident_chat_runtime.discord_gateway import DiscordGatewayLoop, GatewayCallbacks


@pytest.mark.asyncio
async def test_gateway_dispatches_known_events_and_raw_callback() -> None:
    seen: list[tuple[str, dict[str, object]]] = []

    async def on_event(payload: dict[str, object]) -> None:
        seen.append(("event", payload))

    async def on_message(payload: dict[str, object]) -> None:
        seen.append(("message", payload))

    loop = DiscordGatewayLoop(
        GatewayCallbacks(on_event=on_event, on_message_create=on_message)
    )

    await loop.dispatch_payload({"t": "MESSAGE_CREATE", "d": {"id": "m1"}})
    await loop.dispatch_payload({"t": "UNKNOWN", "d": {"id": "m2"}})

    assert seen == [
        ("event", {"t": "MESSAGE_CREATE", "d": {"id": "m1"}}),
        ("message", {"id": "m1"}),
        ("event", {"t": "UNKNOWN", "d": {"id": "m2"}}),
    ]


@pytest.mark.asyncio
async def test_gateway_run_consumes_payload_stream() -> None:
    seen: list[dict[str, object]] = []

    async def stream():
        yield {"t": "READY", "d": {"session_id": "s1"}}

    async def on_ready(payload: dict[str, object]) -> None:
        seen.append(payload)

    loop = DiscordGatewayLoop(GatewayCallbacks(on_ready=on_ready))

    await loop.run(stream())

    assert seen == [{"session_id": "s1"}]
