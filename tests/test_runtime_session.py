from __future__ import annotations

import asyncio
import json
import signal
import sys
import types
from pathlib import Path
from typing import Any

import pytest

import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import (
    EmbeddedSession,
    ServerSession,
    SessionConfig,
    _embedded_configuration_for_session,
    model_fingerprint,
)
import vibecomfy.runtime.client as client_module
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class FakeConfiguration(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _default_configuration() -> FakeConfiguration:
    return FakeConfiguration({"cwd": None})


@pytest.fixture
def fake_comfy(monkeypatch: pytest.MonkeyPatch):
    class FakeComfy:
        instances: list["FakeComfy"] = []
        enter_count = 0
        exit_count = 0

        def __init__(self, configuration=None) -> None:
            self.configuration = configuration
            self.queue_calls: list[dict[str, Any]] = []
            self.clear_cache_calls = 0
            self.reconfigure_calls: list[Any] = []
            FakeComfy.instances.append(self)

        async def __aenter__(self):
            FakeComfy.enter_count += 1
            return self

        async def __aexit__(self, exc_type, exc, tb):
            FakeComfy.exit_count += 1

        async def queue_prompt_api(self, api_dict):
            self.queue_calls.append(api_dict)
            return {"prompt_id": f"prompt-{len(self.queue_calls)}", "outputs": []}

        async def clear_cache(self):
            self.clear_cache_calls += 1

        async def reconfigure(self, configuration):
            self.reconfigure_calls.append(configuration)
            return configuration

    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = FakeComfy
    embedded.default_configuration = _default_configuration
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)
    monkeypatch.delenv("VIBECOMFY_WARM", raising=False)
    return FakeComfy


def _workflow(ckpt: str = "model-a.safetensors", *, seed: int = 1) -> VibeWorkflow:
    workflow = VibeWorkflow("session-test", WorkflowSource("session-test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "CheckpointLoaderSimple",
        inputs={"ckpt_name": ckpt},
    )
    workflow.nodes["2"] = VibeNode("2", "KSampler", inputs={"seed": seed})
    return workflow


def test_embedded_session_reuses_single_comfy_context(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_twice() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow())
            await session.run(_workflow())
        finally:
            await session.stop()

    asyncio.run(run_twice())

    assert fake_comfy.enter_count == 1
    assert fake_comfy.exit_count == 1
    assert len(fake_comfy.instances) == 1
    assert len(fake_comfy.instances[0].queue_calls) == 2


def test_embedded_session_flush_invokes_clear_cache(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_flush() -> None:
        session = EmbeddedSession()
        try:
            await session.start()
            await session.flush()
        finally:
            await session.stop()

    asyncio.run(run_flush())

    assert fake_comfy.instances[0].clear_cache_calls == 1


def test_embedded_session_reconfigure_passes_typed_configuration(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_reconfigure() -> None:
        session = EmbeddedSession()
        try:
            await session.start()
            await session.reconfigure(
                SessionConfig(
                    port=8200,
                    vram_policy="high",
                    reserve_vram_gb=2.0,
                    cache_policy="lru:3",
                    disable_smart_memory=True,
                )
            )
        finally:
            await session.stop()

    asyncio.run(run_reconfigure())

    config = fake_comfy.instances[0].reconfigure_calls[0]
    assert isinstance(config, FakeConfiguration)
    assert config.port == 8200
    assert config.highvram is True
    assert config.reserve_vram == 2.0
    assert config.cache_lru == 3
    assert config.disable_smart_memory is True


def test_from_workflow_metadata_raw_hiddenswitch_carries_through(
    fake_comfy, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "reserve_vram": 12,
        "cache_none": True,
        "fp8_e4m3fn_text_enc": True,
    }

    config = SessionConfig.from_workflow_metadata(workflow)

    assert config.reserve_vram_gb == 12
    assert config.cache_policy == "none"
    assert config.extra == {"fp8_e4m3fn_text_enc": True}
    embedded_config = _embedded_configuration_for_session(config)
    assert embedded_config.reserve_vram == 12
    assert embedded_config.cache_none is True
    assert embedded_config.fp8_e4m3fn_text_enc is True


def test_session_config_from_dict_raw_hiddenswitch_mirror() -> None:
    config = SessionConfig.from_dict(
        {"reserve_vram": 12, "cache_none": True, "fp8_e4m3fn_text_enc": True}
    )

    assert config.reserve_vram_gb == 12
    assert config.cache_policy == "none"
    assert config.extra == {"fp8_e4m3fn_text_enc": True}


def test_session_config_from_dict_typed_names() -> None:
    config = SessionConfig.from_dict(
        {
            "port": 8200,
            "vram_policy": "high",
            "reserve_vram_gb": 2.0,
            "cache_policy": "lru:3",
            "warm_policy": "always",
        }
    )

    assert config == SessionConfig(
        port=8200,
        vram_policy="high",
        reserve_vram_gb=2.0,
        cache_policy="lru:3",
        warm_policy="always",
        extra={},
    )


def test_session_config_from_dict_mixed_typed_and_raw_hiddenswitch() -> None:
    config = SessionConfig.from_dict(
        {"port": 8200, "reserve_vram": 12, "fp8_e4m3fn_text_enc": True}
    )

    assert config.port == 8200
    assert config.reserve_vram_gb == 12
    assert config.extra == {"fp8_e4m3fn_text_enc": True}


def test_session_config_typed_values_override_raw_hiddenswitch_conflicts() -> None:
    config = SessionConfig.from_dict({"reserve_vram_gb": 2.0, "reserve_vram": 12})

    assert config.reserve_vram_gb == 2.0


def test_session_config_empty_dict_uses_defaults() -> None:
    assert SessionConfig.from_dict({}) == SessionConfig(extra={})


def test_model_fingerprint_wan_snapshot() -> None:
    api = json.loads(Path("tests/snapshots/wan_t2v.api.json").read_text(encoding="utf-8"))

    assert model_fingerprint(api) == (
        ("CLIPLoader", "widget_0", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"),
        ("CLIPLoader", "widget_1", "wan"),
        ("CLIPLoader", "widget_2", "default"),
        ("UNETLoader", "widget_0", "wan2.1_t2v_1.3B_fp16.safetensors"),
        ("UNETLoader", "widget_1", "default"),
        ("VAELoader", "widget_0", "wan_2.1_vae.safetensors"),
    )


def test_model_fingerprint_ltx_snapshot_excludes_edge_references() -> None:
    api = json.loads(Path("tests/snapshots/ltx2_3_t2v.api.json").read_text(encoding="utf-8"))
    fingerprint = model_fingerprint(api)

    assert ("LowVRAMCheckpointLoader", "ckpt_name", "ltx-2.3-22b-dev.safetensors") in fingerprint
    assert ("LowVRAMAudioVAELoader", "ckpt_name", "ltx-2.3-22b-dev.safetensors") in fingerprint
    assert (
        "LTXAVTextEncoderLoader",
        "widget_0",
        "comfy_gemma_3_12B_it.safetensors",
    ) in fingerprint
    assert (
        "LoraLoaderModelOnly",
        "widget_0",
        "ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors",
    ) in fingerprint
    assert not any(slot in {"dependencies", "model"} for _, slot, _ in fingerprint)


def test_model_fingerprint_synthetic_gguf_loaders_excludes_edge_references() -> None:
    api = {
        "1": {
            "class_type": "DualCLIPLoaderGGUF",
            "inputs": {"clip_name1": "a.gguf", "clip_name2": "b.gguf", "clip": ["9", 0]},
        },
        "2": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": "wan.gguf", "model": ["1", 0]},
        },
    }

    assert model_fingerprint(api) == (
        ("DualCLIPLoaderGGUF", "clip_name1", "a.gguf"),
        ("DualCLIPLoaderGGUF", "clip_name2", "b.gguf"),
        ("UnetLoaderGGUF", "unet_name", "wan.gguf"),
    )


def test_auto_flush_truth_table(fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    free_vram = 0.5
    monkeypatch.setattr(session_module, "_free_vram_gb", lambda: free_vram)

    async def run_cases() -> None:
        nonlocal free_vram
        session = EmbeddedSession(SessionConfig(auto_flush_vram_threshold_gb=2.0))
        try:
            await session.run(_workflow("model-a.safetensors", seed=1))
            await session.run(_workflow("model-a.safetensors", seed=2))
            assert fake_comfy.instances[0].clear_cache_calls == 0
            await session.run(_workflow("model-b.safetensors", seed=2))
            assert fake_comfy.instances[0].clear_cache_calls == 1
            free_vram = 10.0
            await session.run(_workflow("model-c.safetensors", seed=2))
            assert fake_comfy.instances[0].clear_cache_calls == 1
        finally:
            await session.stop()

    asyncio.run(run_cases())


def test_warm_policy_never_flushes_before_every_run(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_WARM", "never")

    async def run_cases() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow("model-a.safetensors"))
            await session.run(_workflow("model-a.safetensors"))
        finally:
            await session.stop()

    asyncio.run(run_cases())

    assert fake_comfy.instances[0].clear_cache_calls == 2


def test_warm_policy_always_never_auto_flushes(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_WARM", "always")
    monkeypatch.setattr(session_module, "_free_vram_gb", lambda: 0.5)

    async def run_cases() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow("model-a.safetensors"))
            await session.run(_workflow("model-b.safetensors"))
        finally:
            await session.stop()

    asyncio.run(run_cases())

    assert fake_comfy.instances[0].clear_cache_calls == 0


class FakeResponse:
    def __init__(self, status_code: int = 200, data: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._data = data or {}
        self.content = json.dumps(self._data).encode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._data


class FakeAsyncClient:
    posts: list[tuple[str, dict[str, Any] | None]] = []
    gets: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url: str) -> FakeResponse:
        self.gets.append(url)
        return FakeResponse(200, {"ready": True})

    async def post(self, url: str, json: dict[str, Any] | None = None) -> FakeResponse:
        self.posts.append((url, json))
        if url.endswith("/prompt"):
            return FakeResponse(200, {"prompt_id": f"prompt-{len(self.posts)}"})
        return FakeResponse(200, {})


class FakeProcess:
    def __init__(self, *, wait_blocks: bool = False) -> None:
        self.returncode: int | None = None
        self.signals: list[int] = []
        self.killed = False
        self.wait_blocks = wait_blocks

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)

    async def wait(self) -> int:
        if self.wait_blocks:
            await asyncio.sleep(3600)
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch):
    FakeAsyncClient.posts = []
    FakeAsyncClient.gets = []
    spawned: list[tuple[tuple[str, ...], FakeProcess]] = []

    async def fake_create_subprocess_exec(*argv, **kwargs):
        process = FakeProcess()
        spawned.append((tuple(argv), process))
        return process

    monkeypatch.setattr(session_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(client_module.httpx, "AsyncClient", FakeAsyncClient)
    return spawned


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
