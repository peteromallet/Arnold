from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from vibecomfy.errors import WorkflowQueueError

from .client import ComfyClient


class EmbeddedQueue(Protocol):
    async def queue_prompt_api(self, api_dict: dict[str, Any]) -> Any:
        ...


@dataclass(frozen=True, slots=True)
class QueuedExecution:
    queued: Any
    prompt_id: str | None
    outputs: list[str]


def normalize_prompt_id(queued: Any) -> str | None:
    if isinstance(queued, dict):
        prompt_id = queued.get("prompt_id")
    else:
        prompt_id = getattr(queued, "prompt_id", None)
    if prompt_id is None:
        return None
    return str(prompt_id)


def collect_output_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"abs_path", "path", "fullpath", "filename"} and isinstance(item, str):
                paths.append(item)
            else:
                paths.extend(collect_output_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(collect_output_paths(item))
    return paths


def embedded_outputs(queued: Any) -> list[str]:
    payload = getattr(queued, "outputs", None)
    if payload is None and isinstance(queued, dict):
        payload = queued.get("outputs", queued)
    return collect_output_paths(payload)


async def queue_embedded_prompt(queue: EmbeddedQueue, api_dict: dict[str, Any]) -> QueuedExecution:
    try:
        queued = await queue.queue_prompt_api(api_dict)
    except asyncio.TimeoutError:
        raise
    except Exception as exc:
        raise WorkflowQueueError(
            f"Workflow queue failed: {exc}",
            next_action="Check the embedded ComfyUI logs and verify the workflow can be queued by the active runtime.",
        ) from exc
    return QueuedExecution(
        queued=queued,
        prompt_id=normalize_prompt_id(queued),
        outputs=embedded_outputs(queued),
    )


async def queue_server_prompt(
    api_dict: dict[str, Any],
    *,
    server_url: str | None = None,
    client: ComfyClient | None = None,
) -> QueuedExecution:
    if client is None:
        if server_url is None:
            raise ValueError("server_url is required when client is not provided")
        client = ComfyClient(server_url)
    try:
        queued = await client.queue_prompt(api_dict)
    except asyncio.TimeoutError:
        raise
    except Exception as exc:
        raise WorkflowQueueError(
            f"Workflow queue failed: {exc}",
            next_action="Check server health, the ComfyUI logs, and whether the workflow payload is accepted by this runtime.",
        ) from exc
    return QueuedExecution(
        queued=queued,
        prompt_id=normalize_prompt_id(queued),
        outputs=[],
    )
