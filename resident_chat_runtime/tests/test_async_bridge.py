import asyncio
import threading

import pytest

from resident_chat_runtime.async_bridge import SameLoopBridgeError, run_coroutine_sync


async def _value(value: int) -> int:
    return value


def test_run_coroutine_sync_without_loop() -> None:
    assert run_coroutine_sync(_value(3)) == 3


def test_run_coroutine_sync_rejects_same_running_loop() -> None:
    async def run() -> None:
        with pytest.raises(SameLoopBridgeError):
            run_coroutine_sync(_value(3))

    asyncio.run(run())


def test_run_coroutine_sync_can_target_other_thread_loop() -> None:
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def runner() -> None:
        asyncio.set_event_loop(loop)
        ready.set()
        loop.run_forever()

    thread = threading.Thread(target=runner)
    thread.start()
    ready.wait(timeout=2)
    try:
        assert run_coroutine_sync(_value(4), loop=loop) == 4
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
        loop.close()
