from __future__ import annotations

import asyncio
import importlib
import json
import signal
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

import vibecomfy.runtime.session as session_module
import vibecomfy.node_packs_install as node_packs_install
from vibecomfy.memory_profile import MemoryProfile
from vibecomfy.node_packs import CustomNodePack
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.runtime.session import (
    EmbeddedSession,
    ServerSession,
    SessionConfig,
    _comfy_server_argv,
    _embedded_configuration_for_session,
    _prepare_prompt_async,
    _run_metadata,
    _warm_schema_provider,
    apply_memory_profile_override,
    model_fingerprint,
)
import vibecomfy.runtime.client as client_module
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

runtime_run_module = importlib.import_module("vibecomfy.runtime.run")


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


class WarmProvider:
    def __init__(self) -> None:
        self.cache_path = Path("unused-cache.json")
        self._object_info: dict[str, Any] | None = None
        self.object_info_calls = 0
        self._schemas = {
            "CheckpointLoaderSimple": NodeSchema(
                "CheckpointLoaderSimple",
                None,
                {"ckpt_name": InputSpec("STRING")},
                [],
            ),
            "KSampler": NodeSchema("KSampler", None, {"seed": InputSpec("INT")}, []),
        }

    async def object_info_async(self) -> dict[str, Any]:
        self.object_info_calls += 1
        return {"ready": True}

    def schemas(self) -> dict[str, NodeSchema]:
        if self._object_info is None:
            raise AssertionError("schemas read before object_info_async warmup")
        return self._schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schemas().get(class_type)


def test_async_warmup_populates_cache_then_validates() -> None:
    provider = WarmProvider()

    async def run_prepare() -> dict[str, Any]:
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


def test_one_shot_run_validates_against_active_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    built_for: list[str | None] = []
    queued_urls: list[str] = []

    @asynccontextmanager
    async def fake_server(*, server_url=None, log_path=None, config=None):
        assert config is None
        yield "http://active-runtime.test"

    def fake_build(server_url: str | None):
        built_for.append(server_url)
        return object()

    async def fake_prepare(workflow, *, backend, schema_provider, on_unavailable, cache_only=False):
        return workflow.compile(backend=backend)

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            queued_urls.append(server_url)

        async def queue_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
            return {"prompt_id": "prompt-1"}

    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", fake_build)
    monkeypatch.setattr(runtime_run_module, "_prepare_prompt_async", fake_prepare)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)

    asyncio.run(runtime_run_module.run(_workflow(), server_url="http://configured.test"))

    assert built_for == ["http://active-runtime.test"]
    assert queued_urls == ["http://active-runtime.test"]


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


def test_session_config_memory_profile_overlay_uses_normal_precedence() -> None:
    config = SessionConfig.from_dict(
        {
            "memory_profile": 5,
            "vram_policy": "normal",
            "reserve_vram_gb": 8.0,
            "cache_policy": "none",
        }
    )

    assert config.memory_profile is MemoryProfile.MINIMUM
    assert config.vram_policy == "normal"
    assert config.reserve_vram_gb == 8.0
    assert config.cache_policy == "none"
    assert config.disable_smart_memory is True


def test_session_config_memory_profile_overlay_respects_raw_hiddenswitch_precedence() -> None:
    config = SessionConfig.from_dict(
        {
            "memory_profile": 1,
            "lowvram": True,
            "reserve_vram": 3.0,
            "cache_none": True,
        }
    )

    assert config.memory_profile is MemoryProfile.LOW_RAM
    assert config.vram_policy == "low"
    assert config.reserve_vram_gb == 3.0
    assert config.cache_policy == "none"


@pytest.mark.parametrize("value", [0, 6, -1, "1", 1.0, True])
def test_session_config_memory_profile_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError, match="integer from 1 to 5"):
        SessionConfig.from_dict({"memory_profile": value})


def test_from_workflow_metadata_applies_memory_profile_before_explicit_fields() -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }

    config = SessionConfig.from_workflow_metadata(workflow)

    assert config.memory_profile is MemoryProfile.VERY_LOW_VRAM
    assert config.vram_policy == "low"
    assert config.cache_policy == "none"
    assert config.reserve_vram_gb == 7.0


def test_explicit_memory_profile_override_wins_after_workflow_metadata_resolution() -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }
    config = SessionConfig.from_workflow_metadata(workflow)

    resolved = apply_memory_profile_override(config, 5)

    assert config.memory_profile is MemoryProfile.VERY_LOW_VRAM
    assert config.cache_policy == "none"
    assert config.reserve_vram_gb == 7.0
    assert resolved.memory_profile is MemoryProfile.MINIMUM
    assert resolved.vram_policy == "low"
    assert resolved.cache_policy == "lru:1"
    assert resolved.reserve_vram_gb == 4.0
    assert resolved.disable_smart_memory is True
    assert workflow.metadata["comfy_configuration"] == {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }


def test_memory_profiles_round_trip_to_embedded_config_and_server_argv(fake_comfy) -> None:
    expected = {
        1: {"vram": "--highvram", "cache": None, "reserve": None, "disable": False},
        2: {"vram": "--highvram", "cache": ("--cache-lru", "32"), "reserve": None, "disable": False},
        3: {"vram": "--normalvram", "cache": None, "reserve": None, "disable": False},
        4: {"vram": "--lowvram", "cache": "--cache-classic", "reserve": "2.0", "disable": False},
        5: {"vram": "--lowvram", "cache": ("--cache-lru", "1"), "reserve": "4.0", "disable": True},
    }

    for value, profile_expected in expected.items():
        config = SessionConfig.from_dict({"memory_profile": value, "port": 8200})
        embedded = _embedded_configuration_for_session(config)
        argv = _comfy_server_argv(config)

        assert config.memory_profile == value
        assert embedded is not None
        assert getattr(embedded, profile_expected["vram"].removeprefix("--")) is True
        assert profile_expected["vram"] in argv
        assert argv[argv.index("--port") + 1] == "8200"

        cache = profile_expected["cache"]
        if cache is None:
            assert "--cache-lru" not in argv
            assert "--cache-classic" not in argv
            assert "--cache-none" not in argv
        elif isinstance(cache, tuple):
            flag, amount = cache
            assert argv[argv.index(flag) + 1] == amount
            assert getattr(embedded, flag.removeprefix("--").replace("-", "_")) == int(amount)
        else:
            assert cache in argv
            assert getattr(embedded, cache.removeprefix("--").replace("-", "_")) is True

        if profile_expected["reserve"] is None:
            assert "--reserve-vram" not in argv
            assert "reserve_vram" not in embedded
        else:
            assert argv[argv.index("--reserve-vram") + 1] == profile_expected["reserve"]
            assert embedded.reserve_vram == float(profile_expected["reserve"])

        if profile_expected["disable"]:
            assert "--disable-smart-memory" in argv
            assert embedded.disable_smart_memory is True
        else:
            assert "--disable-smart-memory" not in argv
            assert "disable_smart_memory" not in embedded


def test_run_metadata_includes_memory_profile_telemetry_when_configured() -> None:
    metadata = _run_metadata(
        run_id="run-test",
        workflow=_workflow(),
        api_dict={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        queued={"prompt_id": "prompt-test"},
        outputs=[],
        runtime="embedded",
        config=SessionConfig.from_dict({"memory_profile": 3}),
    )

    assert metadata["memory_profile"] == 3
    assert metadata["memory_profile_label"] == "Low VRAM"


def test_run_metadata_omits_memory_profile_telemetry_when_unset() -> None:
    metadata = _run_metadata(
        run_id="run-test",
        workflow=_workflow(),
        api_dict={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        queued={"prompt_id": "prompt-test"},
        outputs=[],
        runtime="embedded",
        config=SessionConfig(),
    )

    assert "memory_profile" not in metadata
    assert "memory_profile_label" not in metadata


def test_model_fingerprint_wan_snapshot() -> None:
    api = json.loads(Path("tests/snapshots/wan_t2v.api.json").read_text(encoding="utf-8"))

    # Post-conversion the snapshot uses canonical input names rather than
    # positional widget_X. Expectations updated to match the converted shape.
    assert model_fingerprint(api) == (
        ("CLIPLoader", "clip_name", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"),
        ("CLIPLoader", "device", "default"),
        ("CLIPLoader", "type", "wan"),
        ("UNETLoader", "unet_name", "wan2.1_t2v_1.3B_fp16.safetensors"),
        ("UNETLoader", "weight_dtype", "default"),
        ("VAELoader", "vae_name", "wan_2.1_vae.safetensors"),
    )


def test_model_fingerprint_ltx_snapshot_excludes_edge_references() -> None:
    api = json.loads(Path("tests/snapshots/ltx2_3_t2v.api.json").read_text(encoding="utf-8"))
    fingerprint = model_fingerprint(api)

    # Post-conversion: apply_ltx_lowvram swaps the ckpt to fp8; LoraLoaderModelOnly
    # widget_0 is now schema-resolved to lora_name; LTXAVTextEncoderLoader uses
    # canonical names from its source workflow JSON (text_encoder, not widget_0).
    assert ("LowVRAMCheckpointLoader", "ckpt_name", "ltx-2.3-22b-dev-fp8.safetensors") in fingerprint
    assert ("LowVRAMAudioVAELoader", "ckpt_name", "ltx-2.3-22b-dev-fp8.safetensors") in fingerprint
    assert (
        "LTXAVTextEncoderLoader",
        "text_encoder",
        "comfy_gemma_3_12B_it.safetensors",
    ) in fingerprint
    assert (
        "LoraLoaderModelOnly",
        "lora_name",
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


def _patch_fast_runtime_run(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_prepare(workflow, *, backend, schema_provider, on_unavailable, cache_only=False):
        return workflow.compile(backend=backend)

    async def fake_maybe_flush(_session, _fp):
        return None

    async def fake_start_watchdog(*, server_url, client_id, api_dict):
        return object()

    async def fake_finalize_watchdog(_watchdog, *, run_dir, reason):
        return None

    monkeypatch.setattr(session_module, "_prepare_prompt_async", fake_prepare)
    monkeypatch.setattr(session_module, "_maybe_flush_for_policy", fake_maybe_flush)
    monkeypatch.setattr(session_module, "_start_watchdog", fake_start_watchdog)
    monkeypatch.setattr(session_module, "_finalize_watchdog", fake_finalize_watchdog)
    monkeypatch.setattr(session_module, "_build_schema_provider", lambda _url: object())


def test_embedded_stop_refuses_inflight_when_not_waiting(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocking_queue(self, api_dict):
            started.set()
            await release.wait()
            return {"prompt_id": "prompt-blocked", "outputs": []}

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", blocking_queue)
        session = EmbeddedSession()
        task = asyncio.create_task(session.run(_workflow()))
        await started.wait()
        with pytest.raises(RuntimeError, match="session.stop\\(\\) called while a run is in flight"):
            await session.stop(wait_for_inflight=False)
        release.set()
        await task
        await session.stop()

    asyncio.run(run_case())


def test_embedded_stop_waits_for_inflight_run(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocking_queue(self, api_dict):
            started.set()
            await release.wait()
            return {"prompt_id": "prompt-blocked", "outputs": []}

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", blocking_queue)
        session = EmbeddedSession()
        task = asyncio.create_task(session.run(_workflow()))
        await started.wait()
        stop_task = asyncio.create_task(session.stop(wait_for_inflight=True))
        await asyncio.sleep(0)
        assert not stop_task.done()
        release.set()
        await stop_task
        assert task.done()

    asyncio.run(run_case())


def test_embedded_stop_reraises_inflight_run_exception_before_teardown(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def failing_queue(self, api_dict):
            started.set()
            await release.wait()
            raise ValueError("boom")

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", failing_queue)
        session = EmbeddedSession()
        task = asyncio.create_task(session.run(_workflow()))
        await started.wait()
        stop_task = asyncio.create_task(session.stop(wait_for_inflight=True))
        await asyncio.sleep(0)
        assert not stop_task.done()
        release.set()
        with pytest.raises(RuntimeError, match="Workflow queue failed: boom"):
            await stop_task
        assert task.done()
        assert fake_comfy.exit_count == 0
        await session.stop()

    asyncio.run(run_case())


def test_embedded_concurrent_run_is_rejected(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocking_queue(self, api_dict):
            started.set()
            await release.wait()
            return {"prompt_id": "prompt-blocked", "outputs": []}

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", blocking_queue)
        session = EmbeddedSession()
        task = asyncio.create_task(session.run(_workflow()))
        await started.wait()
        with pytest.raises(RuntimeError, match="session already has a run in flight"):
            await session.run(_workflow(seed=2))
        release.set()
        await task
        await session.stop()

    asyncio.run(run_case())


def test_embedded_reload_reopens_fresh_context_and_resets_cached_state(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    async def run_case() -> None:
        session = EmbeddedSession()
        await session.start()
        first_comfy = session._comfy
        session._schema_provider = object()
        session._schema_warning_emitted = True
        session.last_fingerprint = ("stale",)
        await session.reload_for_nodepack_change(reason="test")
        assert fake_comfy.exit_count == 1
        assert fake_comfy.enter_count == 2
        assert len(fake_comfy.instances) == 2
        assert session._comfy is not first_comfy
        assert session._schema_provider is None
        assert session._schema_warning_emitted is False
        assert session.last_fingerprint is None
        await session.stop()

    asyncio.run(run_case())


def test_embedded_reload_refuses_inflight_run(
    fake_comfy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)

    async def run_case() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocking_queue(self, api_dict):
            started.set()
            await release.wait()
            return {"prompt_id": "prompt-blocked", "outputs": []}

        monkeypatch.setattr(fake_comfy, "queue_prompt_api", blocking_queue)
        session = EmbeddedSession()
        task = asyncio.create_task(session.run(_workflow()))
        await started.wait()
        with pytest.raises(RuntimeError, match="reload_for_nodepack_change refused: run in flight"):
            await session.reload_for_nodepack_change(reason="test")
        release.set()
        await task
        await session.stop()

    asyncio.run(run_case())


def test_embedded_run_ensure_packs_invokes_install_then_reload_then_queue(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    pack = CustomNodePack(
        name="ExamplePack",
        repo="https://example.test/example.git",
        classes=frozenset({"ExampleNode"}),
    )
    calls: list[str] = []

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", lambda workflow: ([pack], []))

    def fake_install_pack(*, name):
        calls.append(f"install:{name}")
        return node_packs_install.InstallResult(name=name, status="installed", git_commit_sha="abc123", error=None)

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    monkeypatch.setattr(node_packs_install, "install_pack", fake_install_pack)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["install:ExamplePack", "reload:ensure_packs", "queue"]


def test_embedded_run_ensure_packs_prefers_lockfile_restore(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    pack = CustomNodePack(
        name="ExamplePack",
        repo="https://example.test/example.git",
        classes=frozenset({"ExampleNode"}),
    )
    calls: list[str] = []

    Path("custom_nodes.lock").write_text(
        "ExamplePack pinnedsha https://example.test/example.git\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", lambda workflow: ([pack], []))

    def fail_install_pack(**_kwargs):
        raise AssertionError("install_pack must not be called when a lockfile pin exists")

    def fake_restore_pack(entry):
        calls.append(f"restore:{entry.name}:{entry.git_commit_sha}")
        return node_packs_install.InstallResult(
            name=entry.name,
            status="refreshed",
            git_commit_sha=entry.git_commit_sha,
            error=None,
        )

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    monkeypatch.setattr(node_packs_install, "install_pack", fail_install_pack)
    monkeypatch.setattr(node_packs_install, "restore_pack", fake_restore_pack)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["restore:ExamplePack:pinnedsha", "reload:ensure_packs", "queue"]


def test_embedded_run_ensure_packs_skips_reload_when_nothing_missing(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[str] = []

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", lambda workflow: ([], []))

    def fail_install_pack(**_kwargs):
        raise AssertionError("install_pack must not be called when no packs are missing")

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    monkeypatch.setattr(node_packs_install, "install_pack", fail_install_pack)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["queue"]


def test_embedded_run_ensure_packs_continues_without_node_index_for_builtin_workflow(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[str] = []

    def missing_index(_workflow):
        raise FileNotFoundError("node_index.json not found at node_index.json; run `vibecomfy sources sync`")

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", missing_index)
    monkeypatch.setattr(session_module, "_node_packs_from_requirements", lambda workflow: [])

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-no-index", "outputs": []}

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())
    assert calls == ["queue"]


def test_embedded_run_ensure_packs_falls_back_to_declared_requirements(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    pack = CustomNodePack(
        name="ExamplePack",
        repo="https://example.test/example.git",
        classes=frozenset({"ExampleNode"}),
    )
    calls: list[str] = []

    def missing_index(_workflow):
        raise FileNotFoundError("node_index.json not found at node_index.json; run `vibecomfy sources sync`")

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", missing_index)
    monkeypatch.setattr(session_module, "_node_packs_from_requirements", lambda workflow: [pack])

    def fake_install_pack(*, name):
        calls.append(f"install:{name}")
        return node_packs_install.InstallResult(name=name, status="installed", git_commit_sha="abc123", error=None)

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    monkeypatch.setattr(node_packs_install, "install_pack", fake_install_pack)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["install:ExamplePack", "reload:ensure_packs", "queue"]


def test_embedded_run_ensure_packs_falls_back_to_workflow_class_types(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[str] = []

    def missing_index(_workflow):
        raise FileNotFoundError("node_index.json not found at node_index.json; run `vibecomfy sources sync`")

    def fake_install_pack(*, name):
        calls.append(f"install:{name}")
        return node_packs_install.InstallResult(name=name, status="installed", git_commit_sha="abc123", error=None)

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    workflow = _workflow()
    workflow.nodes["3"] = VibeNode("3", "WanVideoVAELoader")

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", missing_index)
    monkeypatch.setattr(node_packs_install, "install_pack", fake_install_pack)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(workflow, ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["install:ComfyUI-WanVideoWrapper", "reload:ensure_packs", "queue"]


def test_embedded_run_ensure_models_downloads_declared_assets(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = _workflow()
    workflow.metadata["model_assets"] = [
        {
            "name": "model-a.safetensors",
            "url": "https://example.test/model.safetensors",
            "directory": "checkpoints",
        }
    ]

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [
        [
            {
                "name": "model-a.safetensors",
                "url": "https://example.test/model.safetensors",
                "subdir": "checkpoints",
            }
        ],
        "queue",
    ]


def test_embedded_run_ensure_models_resolves_registry_assets_from_final_workflow(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = VibeWorkflow("asset-resolution", WorkflowSource("asset-resolution"))
    workflow.nodes["5011"] = VibeNode(
        "5011",
        "LTXICLoRALoaderModelOnly",
        inputs={"lora_name": "ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"},
    )

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-resolved-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [
        [
            {
                "name": "ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors",
                "url": "https://huggingface.co/qqceqqq/LTX-2.3-22b-IC-LoRA-Union-Control/resolve/main/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors",
                "subdir": "loras",
            }
        ],
        "queue",
    ]


def test_embedded_run_ensure_models_does_not_cross_resolve_same_basename_between_model_dirs(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = VibeWorkflow("asset-resolution", WorkflowSource("asset-resolution"))
    workflow.nodes["175"] = VibeNode(
        "175",
        "LTXVAudioVAELoader",
        inputs={"ckpt_name": "LTX23_audio_vae_bf16.safetensors"},
    )
    workflow.metadata["model_assets"] = [
        {
            "name": "LTX23_audio_vae_bf16.safetensors",
            "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors",
            "subdir": "checkpoints",
        }
    ]

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-resolved-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [workflow.metadata["model_assets"], "queue"]


def test_embedded_run_ensure_models_matches_declared_assets_with_normalized_paths(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = VibeWorkflow("asset-normalization", WorkflowSource("asset-normalization"))
    workflow.nodes["186"] = VibeNode(
        "186",
        "LoraLoaderModelOnly",
        inputs={"lora_name": r"LTX\v2\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors"},
    )
    workflow.metadata["model_assets"] = [
        {
            "name": "LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
            "url": "https://example.test/ltx-runexx.safetensors",
            "subdir": "loras",
        }
    ]

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-normalized-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [
        [
            {
                "name": "LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
                "url": "https://example.test/ltx-runexx.safetensors",
                "subdir": "loras",
            }
        ],
        "queue",
    ]


def test_embedded_run_ensure_models_resolves_cameraman_iclora_override(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = VibeWorkflow("asset-cameraman", WorkflowSource("asset-cameraman"))
    workflow.nodes["5011"] = VibeNode(
        "5011",
        "LTXICLoRALoaderModelOnly",
        inputs={"lora_name": "ltxv/ltx2/LTX2.3-22B_IC-LoRA-Cameraman_v1_10500.safetensors"},
    )

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-cameraman-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [
        [
            {
                "name": "ltxv/ltx2/LTX2.3-22B_IC-LoRA-Cameraman_v1_10500.safetensors",
                "url": "https://huggingface.co/Cseti/LTX2.3-22B_IC-LoRA-Cameraman_v1/resolve/main/LTX2.3-22B_IC-LoRA-Cameraman_v1_10500.safetensors",
                "subdir": "loras",
            }
        ],
        "queue",
    ]


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
