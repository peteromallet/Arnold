from __future__ import annotations

import asyncio
import json
import signal
from pathlib import Path

import pytest

import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import ServerSession, SessionConfig

from tests._runtime_session_helpers import (
    FakeAsyncClient,
    FakeProcess,
    _workflow,
    fake_server,  # noqa: F401 -- pytest fixture imported for use in tests
)


def test_server_session_start_translates_config_to_cli_args(fake_server) -> None:
    async def run_start() -> None:
        session = ServerSession(
            SessionConfig(
                vram_policy="high",
                reserve_vram_gb=2.0,
                cache_policy="lru:3",
                disable_smart_memory=True,
                port=8200,
            )
        )
        await session.start()
        await session.stop()

    asyncio.run(run_start())

    argv = fake_server[0][0]
    assert "--highvram" in argv
    assert argv[argv.index("--reserve-vram") + 1] == "2.0"
    assert argv[argv.index("--cache-lru") + 1] == "3"
    assert "--disable-smart-memory" in argv
    assert argv[argv.index("--port") + 1] == "8200"


def test_server_session_two_runs_share_one_subprocess(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_twice() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
            await session.run(_workflow())
        finally:
            await session.stop()

    asyncio.run(run_twice())

    assert len(fake_server) == 1
    assert [post[0] for post in FakeAsyncClient.posts].count("http://127.0.0.1:8200/prompt") == 2


def test_server_session_queue_failure_includes_id_map(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    from tests._runtime_session_helpers import FakeResponse

    async def post(self, url: str, json: dict | None = None):
        if url.endswith("/prompt"):
            raise RuntimeError("queue refused prompt")
        return FakeResponse(200, {})

    monkeypatch.setattr(FakeAsyncClient, "post", post)

    workflow = _workflow()
    workflow.metadata["id_map"] = {"sampler": "2"}
    workflow.nodes["2"].metadata["source_id"] = "7"

    async def run_case() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            with pytest.raises(RuntimeError, match="Workflow queue failed: queue refused prompt") as exc_info:
                await session.run(workflow)
            message = str(exc_info.value)
            assert "id_map=" in message
            assert "'sampler': '2'" in message
            assert "'7': '2'" in message
        finally:
            await session.stop()

    asyncio.run(run_case())


def test_server_session_waits_for_history_and_records_outputs(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "server-output.png").write_bytes(b"png")

    async def run_case():
        session = ServerSession(SessionConfig(port=8200, extra={"output_directory": str(output_dir)}))
        try:
            return await session.run(_workflow())
        finally:
            await session.stop()

    result = asyncio.run(run_case())
    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))

    assert result.outputs == [str(output_dir / "server-output.png")]
    assert metadata["outputs"] == result.outputs
    assert any(url.endswith("/history/prompt-1") for url in FakeAsyncClient.gets)


def test_server_session_flush_posts_api_free_payload(fake_server) -> None:
    async def run_flush() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.start()
            await session.flush()
        finally:
            await session.stop()

    asyncio.run(run_flush())

    assert (
        "http://127.0.0.1:8200/api/free",
        {"unload_models": True, "free_memory": True},
    ) in FakeAsyncClient.posts


def test_server_session_reconfigure_noop_or_restart(fake_server) -> None:
    async def run_reconfigure() -> tuple[bool, bool]:
        config = SessionConfig(port=8200, cache_policy="smart")
        session = ServerSession(config)
        try:
            await session.start()
            same = await session.reconfigure(SessionConfig(port=8200, cache_policy="smart"))
            changed = await session.reconfigure(SessionConfig(port=8201, cache_policy="none"))
            return same, changed
        finally:
            await session.stop()

    same, changed = asyncio.run(run_reconfigure())

    assert same is False
    assert changed is True
    assert len(fake_server) == 2
    assert signal.SIGTERM in fake_server[0][1].signals


def test_server_session_stop_sigterms_then_falls_back_to_kill(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess()
    process.wait_blocks = True
    session = ServerSession()
    session.process = process

    async def fake_wait_for(awaitable, *, timeout):
        if hasattr(awaitable, "close"):
            awaitable.close()
        assert timeout == 15
        raise asyncio.TimeoutError

    async def fake_wait_after_kill() -> int:
        process.returncode = -9
        return -9

    monkeypatch.setattr(session_module.asyncio, "wait_for", fake_wait_for)
    process.wait = fake_wait_after_kill  # type: ignore[method-assign]

    asyncio.run(session.stop())

    assert process.signals == [signal.SIGTERM]
    assert process.killed is True


def test_server_reload_calls_stop_then_start() -> None:
    async def run_case() -> None:
        session = ServerSession()
        calls: list[str] = []

        async def fake_stop(wait_for_inflight: bool = True) -> None:
            calls.append("stop")

        async def fake_start() -> None:
            calls.append("start")

        session.stop = fake_stop  # type: ignore[method-assign]
        session.start = fake_start  # type: ignore[method-assign]
        await session.reload_for_nodepack_change(reason="test")
        assert calls == ["stop", "start"]

    asyncio.run(run_case())


def test_server_reload_refuses_inflight_and_has_no_external_mode_api() -> None:
    async def run_case() -> None:
        session = ServerSession()
        task = asyncio.create_task(asyncio.sleep(3600))
        session._inflight_run = task
        try:
            with pytest.raises(RuntimeError, match="reload_for_nodepack_change refused: run in flight"):
                await session.reload_for_nodepack_change(reason="test")
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run_case())
    assert not hasattr(ServerSession, "attach")
    assert not hasattr(session_module, "ExternalServerRestartRequired")
