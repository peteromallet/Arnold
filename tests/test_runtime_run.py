from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
import types
from contextlib import asynccontextmanager

import pytest

from vibecomfy.commands.run import _cmd_run
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

runtime_run_module = importlib.import_module("vibecomfy.runtime.run")


def _workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("runtime-test", WorkflowSource("runtime-test"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "test"})
    return workflow


def test_run_starts_server_before_building(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    entered_server = False

    @asynccontextmanager
    async def fail_if_entered(*args, **kwargs):
        nonlocal entered_server
        entered_server = True
        yield "http://127.0.0.1:8188"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fail_if_entered)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    with pytest.raises(ValueError, match="Workflow build failed: Unknown compile backend"):
        asyncio.run(runtime_run_module.run(_workflow(), backend="missing"))

    assert entered_server is True
    assert (tmp_path / "out").exists()


def test_run_embedded_starts_before_building(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeComfy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = lambda configuration=None: FakeComfy()
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="Workflow build failed: Unknown compile backend"):
        asyncio.run(runtime_run_module.run_embedded(_workflow(), backend="missing"))

    assert not (tmp_path / "out/runs").exists()


def test_run_validates_before_queueing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    entered_server = False

    @asynccontextmanager
    async def fail_if_entered(*args, **kwargs):
        nonlocal entered_server
        entered_server = True
        yield "http://127.0.0.1:8188"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fail_if_entered)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    with pytest.raises(ValueError, match=r"Workflow validation failed:\n  - \[empty_workflow\]"):
        asyncio.run(runtime_run_module.run(VibeWorkflow("empty", WorkflowSource("empty"))))

    assert entered_server is True
    assert (tmp_path / "out").exists()


def test_run_surfaces_queue_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    queued_prompts: list[dict] = []

    @asynccontextmanager
    async def fake_server(*args, **kwargs):
        yield "http://runtime.test"

    class FailingClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def queue_prompt(self, prompt: dict) -> dict:
            queued_prompts.append(prompt)
            raise RuntimeError("runtime rejected prompt")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FailingClient)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", lambda active_url: None)

    with pytest.raises(RuntimeError, match="Workflow queue failed: runtime rejected prompt"):
        asyncio.run(runtime_run_module.run(_workflow(), server_url="http://runtime.test"))

    assert queued_prompts == [
        {"1": {"class_type": "SaveImage", "inputs": {"filename_prefix": "test"}}}
    ]


def test_embedded_configuration_uses_hiddenswitch_configuration_object(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeConfiguration(dict):
        def __getattr__(self, name: str):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

    def default_configuration() -> FakeConfiguration:
        return FakeConfiguration({"cwd": None, "reserve_vram": 0.0, "cache_none": False})

    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.default_configuration = default_configuration
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)
    monkeypatch.setenv("VIBECOMFY_COMFY_CONFIGURATION", '{"reserve_vram":12,"cache_none":true}')

    config = runtime_run_module._embedded_configuration(_workflow())

    assert isinstance(config, FakeConfiguration)
    assert config.cwd is None
    assert config.reserve_vram == 12
    assert config.cache_none is True


def test_run_embedded_ignores_hiddenswitch_cleanup_bug_after_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FakeComfy:
        def __init__(self, configuration=None) -> None:
            self.configuration = configuration

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            raise AttributeError("'NoneType' object has no attribute 'model_mmap_residency'")

        async def queue_prompt_api(self, api_dict):
            return {"outputs": {"1": {"filename": "output.mp4"}}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.client", types.ModuleType("comfy.client"))
    embedded = types.ModuleType("comfy.client.embedded_comfy_client")
    embedded.Comfy = FakeComfy
    monkeypatch.setitem(sys.modules, "comfy.client.embedded_comfy_client", embedded)

    result = runtime_run_module.run_embedded_sync(_workflow())

    assert result.outputs == ["output.mp4"]


def test_cmd_run_prints_clear_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="embedded",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )

    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: _workflow())
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda workflow, *, backend: (_ for _ in ()).throw(ValueError("Workflow build failed: bad backend")),
    )

    assert _cmd_run(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "run failed: Workflow build failed: bad backend\n"


def test_cmd_run_auto_uses_active_session_for_schema_and_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="auto",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    schema_calls: list[tuple[str, str | None]] = []
    loaded_schema_providers: list[object] = []
    run_calls: list[tuple[VibeWorkflow, str | None, str]] = []
    provider = object()

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: "http://warm.test")

    def fake_schema_provider(prefer: str, *, server_url: str | None = None):
        schema_calls.append((prefer, server_url))
        return provider

    def fake_load_workflow_reference(*args, **kwargs):
        loaded_schema_providers.append(kwargs["schema_provider"])
        return _workflow()

    def fake_run_sync(workflow: VibeWorkflow, *, server_url: str | None, backend: str):
        run_calls.append((workflow, server_url, backend))
        return types.SimpleNamespace(
            run_id="run-1",
            prompt_id="prompt-1",
            outputs=[],
            metadata_path="metadata.json",
            log_path="comfy.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", fake_schema_provider)
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", fake_load_workflow_reference)
    monkeypatch.setattr("vibecomfy.commands.run.run_sync", fake_run_sync)
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("embedded should not run")),
    )

    assert _cmd_run(args) == 0

    assert schema_calls == [("auto", "http://warm.test")]
    assert loaded_schema_providers == [provider]
    assert run_calls[0][1:] == ("http://warm.test", "api")
    assert "run_id: run-1" in capsys.readouterr().out


def test_cmd_run_auto_without_active_session_falls_back_to_embedded(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        path="edit/qwen_image_edit",
        ready=True,
        runtime="auto",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    schema_calls: list[tuple[str, str | None]] = []
    embedded_calls: list[tuple[VibeWorkflow, str]] = []

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.get_schema_provider",
        lambda prefer, *, server_url=None: schema_calls.append((prefer, server_url)) or object(),
    )
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: _workflow())
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_sync",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("server should not run")),
    )

    def fake_run_embedded_sync(workflow: VibeWorkflow, *, backend: str):
        embedded_calls.append((workflow, backend))
        return types.SimpleNamespace(
            run_id="run-embedded",
            prompt_id="prompt-embedded",
            outputs=[],
            metadata_path="metadata.json",
            log_path="embedded.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_embedded_sync", fake_run_embedded_sync)

    assert _cmd_run(args) == 0

    assert schema_calls == [("auto", None)]
    assert embedded_calls[0][1] == "api"
    assert "run_id: run-embedded" in capsys.readouterr().out
