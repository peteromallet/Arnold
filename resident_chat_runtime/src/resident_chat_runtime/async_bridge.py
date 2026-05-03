from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


class SameLoopBridgeError(RuntimeError):
    """Raised when synchronous code tries to block the event loop it is running on."""


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def run_coroutine_sync(
    coro: Coroutine[object, object, T],
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    same_loop_message: str = "cannot synchronously wait on the currently running event loop",
) -> T:
    running = _running_loop()
    if running is not None and (loop is None or loop is running):
        coro.close()
        raise SameLoopBridgeError(same_loop_message)

    if loop is None:
        return asyncio.run(coro)

    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    return loop.run_until_complete(coro)
