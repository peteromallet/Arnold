from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from vibecomfy.workflow import VibeWorkflow

from .client import ComfyClient
from .server import comfy_server
from .session import (
    EmbeddedSession,
    RunResult,
    SessionConfig,
    _embedded_configuration,
    _prepare_prompt,
    _run_metadata,
)


async def run(workflow: VibeWorkflow, *, server_url: str | None = None, backend: str = "api") -> RunResult:
    api_dict = _prepare_prompt(workflow, backend=backend)

    run_id = f"run-{int(time.time())}"
    run_dir = Path("out/runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "comfy.log"
    async with comfy_server(server_url=server_url, log_path=log_path) as active_url:
        try:
            queued = await ComfyClient(active_url).queue_prompt(api_dict)
        except Exception as exc:
            raise RuntimeError(f"Workflow queue failed: {exc}") from exc
    metadata = _run_metadata(
        run_id=run_id,
        workflow=workflow,
        api_dict=api_dict,
        queued=queued,
        outputs=[],
        runtime="server",
    )
    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    return RunResult(
        run_id=run_id,
        prompt_id=queued.get("prompt_id") if isinstance(queued, dict) else None,
        outputs=[],
        metadata_path=str(metadata_path),
        log_path=str(log_path),
    )


def run_sync(workflow: VibeWorkflow, *, server_url: str | None = None, backend: str = "api") -> RunResult:
    return asyncio.run(run(workflow, server_url=server_url, backend=backend))


async def run_embedded(workflow: VibeWorkflow, *, backend: str = "api") -> RunResult:
    session = EmbeddedSession(SessionConfig.from_workflow_metadata(workflow))
    try:
        return await session.run(workflow, backend=backend)
    finally:
        await session.stop()


def run_embedded_sync(workflow: VibeWorkflow, *, backend: str = "api") -> RunResult:
    return asyncio.run(run_embedded(workflow, backend=backend))


async def smoke_runtime(*, server_url: str | None = None) -> dict[str, Any]:
    run_id = f"smoke-{int(time.time())}"
    run_dir = Path("out/runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "comfy.log"
    async with comfy_server(server_url=server_url, log_path=log_path) as active_url:
        client = ComfyClient(active_url)
        objects = await client.object_info()
    return {
        "run_id": run_id,
        "server_url": server_url or "managed",
        "node_count": len(objects),
        "log_path": str(log_path),
    }


def smoke_runtime_sync(*, server_url: str | None = None) -> dict[str, Any]:
    return asyncio.run(smoke_runtime(server_url=server_url))
