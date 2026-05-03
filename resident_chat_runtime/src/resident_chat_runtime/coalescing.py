from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True)
class BurstBatch(Generic[K, V]):
    key: K
    items: tuple[V, ...]


class AsyncBurstCoalescer(Generic[K, V]):
    def __init__(
        self,
        handler: Callable[[BurstBatch[K, V]], Awaitable[None]],
        *,
        idle_delay: float,
        max_delay: float | None = None,
    ) -> None:
        if idle_delay < 0:
            raise ValueError("idle_delay must be non-negative")
        if max_delay is not None and max_delay <= 0:
            raise ValueError("max_delay must be positive")
        self._handler = handler
        self._idle_delay = idle_delay
        self._max_delay = max_delay
        self._states: dict[K, _State[V]] = {}
        self._lock = asyncio.Lock()

    async def submit(self, key: K, item: V) -> None:
        async with self._lock:
            state = self._states.get(key)
            if state is None:
                state = _State(items=[], first_at=asyncio.get_running_loop().time())
                self._states[key] = state
                if self._max_delay is not None:
                    state.max_task = asyncio.create_task(self._delayed_flush(key, self._max_delay))

            state.items.append(item)
            if state.idle_task is not None:
                state.idle_task.cancel()
            state.idle_task = asyncio.create_task(self._delayed_flush(key, self._idle_delay))

    async def flush(self, key: K) -> None:
        batch = await self._pop_batch(key)
        if batch is not None:
            await self._handler(batch)

    async def flush_all(self) -> None:
        async with self._lock:
            keys = list(self._states)
        for key in keys:
            await self.flush(key)

    async def close(self) -> None:
        async with self._lock:
            states = list(self._states.values())
            self._states.clear()
        for state in states:
            state.cancel()

    def snapshot(self) -> dict[K, tuple[V, ...]]:
        return {key: tuple(state.items) for key, state in self._states.items()}

    async def _delayed_flush(self, key: K, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            await self.flush(key)
        except asyncio.CancelledError:
            raise

    async def _pop_batch(self, key: K) -> BurstBatch[K, V] | None:
        async with self._lock:
            state = self._states.pop(key, None)
            if state is None or not state.items:
                return None
            state.cancel()
            return BurstBatch(key=key, items=tuple(state.items))


@dataclass
class _State(Generic[V]):
    items: list[V]
    first_at: float
    idle_task: asyncio.Task[None] | None = None
    max_task: asyncio.Task[None] | None = None

    def cancel(self) -> None:
        current = asyncio.current_task()
        for task in (self.idle_task, self.max_task):
            if task is not None and task is not current and not task.done():
                task.cancel()
