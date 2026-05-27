from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from typing import Any

import pytest

import vibecomfy.runtime.execution as execution_module
from vibecomfy.runtime.execution import (
    collect_output_paths,
    embedded_outputs,
    normalize_prompt_id,
    queue_embedded_prompt,
    queue_server_prompt,
)


def _runtime_errors():
    return importlib.import_module("vibecomfy.errors")


class _EmbeddedQueueFailure:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def queue_prompt_api(self, api_dict: dict[str, Any]) -> Any:
        raise self.exc


class _ServerQueueFailure:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def queue_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
        raise self.exc


def test_normalize_prompt_id_accepts_dicts_and_objects() -> None:
    assert normalize_prompt_id({"prompt_id": "prompt-dict"}) == "prompt-dict"
    assert normalize_prompt_id(SimpleNamespace(prompt_id=123)) == "123"
    assert normalize_prompt_id({}) is None


def test_collect_output_paths_recurses_through_payloads() -> None:
    payload = {
        "images": [{"filename": "image.png"}, {"ignored": "value"}],
        "video": {"fullpath": "/tmp/video.mp4"},
        "audio": {"path": "audio.wav"},
    }

    assert collect_output_paths(payload) == ["image.png", "/tmp/video.mp4", "audio.wav"]


def test_embedded_outputs_accepts_result_objects_and_dict_payloads() -> None:
    result = SimpleNamespace(outputs={"1": {"filename": "object.png"}})

    assert embedded_outputs(result) == ["object.png"]
    assert embedded_outputs({"outputs": {"1": {"abs_path": "/tmp/dict.png"}}}) == ["/tmp/dict.png"]


def test_queue_embedded_prompt_wraps_failures_and_returns_outputs() -> None:
    class FakeEmbeddedQueue:
        async def queue_prompt_api(self, api_dict: dict[str, Any]) -> Any:
            assert api_dict == {"1": {"class_type": "SaveImage", "inputs": {}}}
            return SimpleNamespace(prompt_id="prompt-embedded", outputs={"1": {"filename": "out.png"}})

    result = asyncio.run(
        queue_embedded_prompt(
            FakeEmbeddedQueue(),
            {"1": {"class_type": "SaveImage", "inputs": {}}},
        )
    )

    assert result.prompt_id == "prompt-embedded"
    assert result.outputs == ["out.png"]


def test_queue_embedded_prompt_wraps_queue_failure() -> None:
    with pytest.raises(RuntimeError, match="Workflow queue failed: embedded rejected prompt"):
        asyncio.run(queue_embedded_prompt(_EmbeddedQueueFailure(ValueError("embedded rejected prompt")), {}))


def test_queue_embedded_prompt_wraps_non_timeout_failure_as_typed_queue_error() -> None:
    errors = _runtime_errors()

    with pytest.raises(errors.WorkflowQueueError) as exc_info:
        asyncio.run(queue_embedded_prompt(_EmbeddedQueueFailure(ValueError("embedded rejected prompt")), {}))

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert exc_info.value.next_action


def test_queue_embedded_prompt_preserves_asyncio_timeout() -> None:
    errors = _runtime_errors()

    with pytest.raises(asyncio.TimeoutError) as exc_info:
        asyncio.run(queue_embedded_prompt(_EmbeddedQueueFailure(asyncio.TimeoutError("embedded queue timed out")), {}))

    assert not isinstance(exc_info.value, errors.WorkflowQueueError)


def test_queue_server_prompt_uses_client_without_collecting_outputs() -> None:
    class FakeClient:
        async def queue_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
            assert prompt == {"1": {"class_type": "SaveImage", "inputs": {}}}
            return {"prompt_id": "prompt-server", "outputs": {"1": {"filename": "ignored.png"}}}

    result = asyncio.run(
        queue_server_prompt(
            {"1": {"class_type": "SaveImage", "inputs": {}}},
            client=FakeClient(),
        )
    )

    assert result.prompt_id == "prompt-server"
    assert result.outputs == []


def test_queue_server_prompt_builds_client_from_active_server_url(monkeypatch: pytest.MonkeyPatch) -> None:
    constructed_urls: list[str] = []

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            constructed_urls.append(server_url)

        async def queue_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
            return {"prompt_id": "prompt-from-url"}

    monkeypatch.setattr(execution_module, "ComfyClient", FakeClient)

    result = asyncio.run(queue_server_prompt({}, server_url="http://active.test"))

    assert constructed_urls == ["http://active.test"]
    assert result.prompt_id == "prompt-from-url"
    assert result.outputs == []


def test_queue_server_prompt_wraps_queue_failure() -> None:
    with pytest.raises(RuntimeError, match="Workflow queue failed: server rejected prompt"):
        asyncio.run(queue_server_prompt({}, client=_ServerQueueFailure(ValueError("server rejected prompt"))))


def test_queue_server_prompt_wraps_non_timeout_failure_as_typed_queue_error() -> None:
    errors = _runtime_errors()

    with pytest.raises(errors.WorkflowQueueError) as exc_info:
        asyncio.run(queue_server_prompt({}, client=_ServerQueueFailure(ValueError("server rejected prompt"))))

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert exc_info.value.next_action


def test_queue_server_prompt_preserves_asyncio_timeout() -> None:
    errors = _runtime_errors()

    with pytest.raises(asyncio.TimeoutError) as exc_info:
        asyncio.run(queue_server_prompt({}, client=_ServerQueueFailure(asyncio.TimeoutError("server queue timed out"))))

    assert not isinstance(exc_info.value, errors.WorkflowQueueError)
