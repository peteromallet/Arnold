import pytest

from resident_chat_runtime.health import CachedHealthCheck, HealthResult


@pytest.mark.asyncio
async def test_cached_health_check_reuses_result_until_ttl_or_force() -> None:
    now = 10.0
    calls = 0

    async def check() -> HealthResult:
        nonlocal calls
        calls += 1
        return HealthResult(ok=True, detail=f"call-{calls}")

    health = CachedHealthCheck(check, ttl_seconds=5.0, monotonic=lambda: now)

    first = await health.get()
    second = await health.get()
    now = 16.0
    third = await health.get()
    forced = await health.get(force=True)

    assert first is second
    assert first.detail == "call-1"
    assert third.detail == "call-2"
    assert forced.detail == "call-3"


@pytest.mark.asyncio
async def test_cached_health_check_reports_and_clears_cached_result() -> None:
    calls = 0

    async def check() -> HealthResult:
        nonlocal calls
        calls += 1
        return HealthResult(ok=True, detail=f"call-{calls}")

    health = CachedHealthCheck(check, ttl_seconds=60.0)

    assert health.has_cached_result() is False
    first = await health.get()
    assert health.has_cached_result() is True
    health.clear()
    assert health.has_cached_result() is False
    second = await health.get()

    assert first.detail == "call-1"
    assert second.detail == "call-2"
