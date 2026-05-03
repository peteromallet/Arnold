import asyncio

from resident_chat_runtime.coalescing import AsyncBurstCoalescer, BurstBatch


def test_coalescer_groups_rapid_items_by_key() -> None:
    async def run() -> None:
        batches: list[BurstBatch[str, str]] = []

        async def handler(batch: BurstBatch[str, str]) -> None:
            batches.append(batch)

        coalescer = AsyncBurstCoalescer(handler, idle_delay=0.02, max_delay=0.2)
        await coalescer.submit("user-1", "a")
        await asyncio.sleep(0.01)
        await coalescer.submit("user-1", "b")
        await asyncio.sleep(0.05)
        await coalescer.close()

        assert batches == [BurstBatch(key="user-1", items=("a", "b"))]

    asyncio.run(run())


def test_coalescer_hard_cap_flushes_active_burst() -> None:
    async def run() -> None:
        batches: list[BurstBatch[str, str]] = []

        async def handler(batch: BurstBatch[str, str]) -> None:
            batches.append(batch)

        coalescer = AsyncBurstCoalescer(handler, idle_delay=0.2, max_delay=0.04)
        await coalescer.submit("user-1", "a")
        await asyncio.sleep(0.02)
        await coalescer.submit("user-1", "b")
        await asyncio.sleep(0.06)
        await coalescer.close()

        assert batches == [BurstBatch(key="user-1", items=("a", "b"))]

    asyncio.run(run())


def test_coalescer_manual_flush_drains_key() -> None:
    async def run() -> None:
        batches: list[BurstBatch[str, str]] = []

        async def handler(batch: BurstBatch[str, str]) -> None:
            batches.append(batch)

        coalescer = AsyncBurstCoalescer(handler, idle_delay=1.0)
        await coalescer.submit("user-1", "a")
        await coalescer.flush("user-1")
        await coalescer.flush("user-1")
        await coalescer.close()

        assert batches == [BurstBatch(key="user-1", items=("a",))]

    asyncio.run(run())


def test_coalescer_snapshot_reports_pending_items_without_flushing() -> None:
    async def run() -> None:
        batches: list[BurstBatch[str, str]] = []

        async def handler(batch: BurstBatch[str, str]) -> None:
            batches.append(batch)

        coalescer = AsyncBurstCoalescer(handler, idle_delay=1.0)
        await coalescer.submit("user-1", "a")
        await coalescer.submit("user-1", "b")

        assert coalescer.snapshot() == {"user-1": ("a", "b")}
        assert batches == []

        await coalescer.close()

    asyncio.run(run())
