from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HealthResult:
    ok: bool
    detail: str = ""
    metadata: dict[str, Any] | None = None


class CachedHealthCheck:
    def __init__(
        self,
        check: Callable[[], Awaitable[HealthResult]],
        *,
        ttl_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")
        self._check = check
        self._ttl_seconds = ttl_seconds
        self._monotonic = monotonic
        self._cached: HealthResult | None = None
        self._cached_at: float | None = None

    async def get(self, *, force: bool = False) -> HealthResult:
        now = self._monotonic()
        if (
            not force
            and self._cached is not None
            and self._cached_at is not None
            and now - self._cached_at <= self._ttl_seconds
        ):
            return self._cached
        result = await self._check()
        self._cached = result
        self._cached_at = now
        return result

    def clear(self) -> None:
        self._cached = None
        self._cached_at = None

    def has_cached_result(self) -> bool:
        if self._cached is None or self._cached_at is None:
            return False
        return self._monotonic() - self._cached_at <= self._ttl_seconds
