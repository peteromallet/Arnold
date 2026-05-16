from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import (
    ServerSession,
    SessionConfig,
    _prepare_prompt_async,
    _warm_schema_provider,
)

from tests._runtime_session_helpers import (
    WarmProvider,
    _workflow,
    fake_server,  # noqa: F401 -- pytest fixture imported for use in tests
)


def test_async_warmup_populates_cache_then_validates() -> None:
    provider = WarmProvider()

    async def run_prepare() -> dict:
        return await _prepare_prompt_async(
            _workflow(),
            backend="api",
            schema_provider=provider,
            on_unavailable=lambda msg: (_ for _ in ()).throw(AssertionError(msg)),
        )

    api = asyncio.run(run_prepare())

    assert provider.object_info_calls == 1
    assert provider._object_info == {"ready": True}
    assert api["1"]["inputs"]["ckpt_name"] == "model-a.safetensors"


def test_session_caches_schema_provider_across_runs(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    provider = WarmProvider()
    built_for: list[str | None] = []

    def fake_build(server_url: str | None):
        built_for.append(server_url)
        return provider

    monkeypatch.setattr(session_module, "_build_schema_provider", fake_build)

    async def run_twice() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
            await session.run(_workflow(seed=2))
        finally:
            await session.stop()

    asyncio.run(run_twice())

    assert built_for == ["http://127.0.0.1:8200"]
    assert provider.object_info_calls == 1
    assert len(fake_server) == 1


def test_provider_unavailable_falls_back_to_structural_with_warning(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)

    class UnavailableProvider:
        _object_info = None

        async def object_info_async(self):
            raise OSError("offline")

    monkeypatch.setattr(session_module, "_build_schema_provider", lambda server_url: UnavailableProvider())

    async def run_twice() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
            await session.run(_workflow(seed=2))
        finally:
            await session.stop()

    with caplog.at_level("WARNING", logger=session_module.__name__):
        asyncio.run(run_twice())

    assert [record.message for record in caplog.records].count(
        "vibecomfy schema gate: OSError: offline; using structural validation only"
    ) == 1


def test_server_session_validates_against_started_url(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    built_for: list[str | None] = []
    prepared_with: list[object | None] = []

    def fake_build(server_url: str | None):
        provider = object()
        built_for.append(server_url)
        return provider

    async def fake_prepare(workflow, *, backend, schema_provider, on_unavailable, cache_only=False):
        prepared_with.append(schema_provider)
        return workflow.compile(backend=backend)

    monkeypatch.setattr(session_module, "_build_schema_provider", fake_build)
    monkeypatch.setattr(session_module, "_prepare_prompt_async", fake_prepare)

    async def run_once() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
            assert session.url == "http://127.0.0.1:8200"
        finally:
            await session.stop()

    asyncio.run(run_once())

    assert built_for == ["http://127.0.0.1:8200"]
    assert len(prepared_with) == 1


def test_env_var_disables_gate(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    async def run_once() -> ServerSession:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
            return session
        finally:
            await session.stop()

    session = asyncio.run(run_once())

    assert session._schema_provider is None


def test_embedded_path_does_not_spawn_extra_comfy_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    entered = False

    class Provider:
        cache_path = tmp_path / "missing-object-info.json"
        _object_info = None

    @asynccontextmanager
    async def fail_if_entered(*args, **kwargs):
        nonlocal entered
        entered = True
        yield "http://should-not-start.test"

    unavailable: list[str] = []
    monkeypatch.setattr("vibecomfy.runtime.server.comfy_server", fail_if_entered)

    effective = asyncio.run(
        _warm_schema_provider(
            Provider(),
            on_unavailable=unavailable.append,
            cache_only=True,
        )
    )

    assert effective is None
    assert entered is False
    assert len(unavailable) == 1
    assert "using structural validation only" in unavailable[0]
