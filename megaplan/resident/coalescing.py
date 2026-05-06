"""Reusable burst coalescing for resident chat transports."""

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


@dataclass
class _CoalescingState(Generic[V]):
    items: list[V]
    idle_task: asyncio.Task[None] | None = None
    max_task: asyncio.Task[None] | None = None

    def cancel(self) -> None:
        current = asyncio.current_task()
        for task in (self.idle_task, self.max_task):
            if task is not None and task is not current and not task.done():
                task.cancel()


class AsyncBurstCoalescer(Generic[K, V]):
    """Coalesce messages by key until the idle or max delay elapses."""

    def __init__(
        self,
        handler: Callable[[BurstBatch[K, V]], Awaitable[None]],
        *,
        idle_delay_s: float,
        max_delay_s: float | None = None,
    ) -> None:
        if idle_delay_s < 0:
            raise ValueError("idle_delay_s must be non-negative")
        if max_delay_s is not None and max_delay_s <= 0:
            raise ValueError("max_delay_s must be positive")
        self._handler = handler
        self._idle_delay_s = idle_delay_s
        self._max_delay_s = max_delay_s
        self._states: dict[K, _CoalescingState[V]] = {}
        self._lock = asyncio.Lock()

    async def submit(self, key: K, item: V) -> None:
        async with self._lock:
            state = self._states.get(key)
            if state is None:
                state = _CoalescingState(items=[])
                self._states[key] = state
                if self._max_delay_s is not None:
                    state.max_task = asyncio.create_task(self._delayed_flush(key, self._max_delay_s))
            state.items.append(item)
            if state.idle_task is not None:
                state.idle_task.cancel()
            state.idle_task = asyncio.create_task(self._delayed_flush(key, self._idle_delay_s))

    async def flush(self, key: K) -> None:
        batch = await self._pop_batch(key)
        if batch is not None:
            await self._handler(batch)

    async def flush_all(self) -> None:
        async with self._lock:
            keys = tuple(self._states)
        for key in keys:
            await self.flush(key)

    async def close(self) -> None:
        async with self._lock:
            states = tuple(self._states.values())
            self._states.clear()
        for state in states:
            state.cancel()

    def snapshot(self) -> dict[K, tuple[V, ...]]:
        return {key: tuple(state.items) for key, state in self._states.items()}

    async def _delayed_flush(self, key: K, delay_s: float) -> None:
        await asyncio.sleep(delay_s)
        await self.flush(key)

    async def _pop_batch(self, key: K) -> BurstBatch[K, V] | None:
        async with self._lock:
            state = self._states.pop(key, None)
            if state is None or not state.items:
                return None
            state.cancel()
            return BurstBatch(key=key, items=tuple(state.items))
