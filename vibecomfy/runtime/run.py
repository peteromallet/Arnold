from __future__ import annotations

import asyncio
import json
import logging
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
    _build_schema_provider,
    _collect_output_paths,
    _configured_output_directory,
    _embedded_configuration,
    _outputs_from_server_history,
    _prepare_prompt_async,
    _run_metadata,
    _wait_for_server_history,
    _workflow_queue_failure_message,
)

logger = logging.getLogger(__name__)


async def run(
    workflow: VibeWorkflow,
    *,
    server_url: str | None = None,
    backend: str = "api",
    config: SessionConfig | None = None,
) -> RunResult:
    run_id = f"run-{int(time.time())}"
    run_dir = Path("out/runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "comfy.log"
    resolved_config = config or SessionConfig.from_workflow_metadata(workflow)
    managed_config = resolved_config if server_url is None else None
    async with comfy_server(server_url=server_url, log_path=log_path, config=managed_config) as active_url:
        provider = _build_schema_provider(active_url)
        warned = {"emitted": False}

        def on_unavailable(msg: str) -> None:
            if warned["emitted"]:
                return
            logger.warning("vibecomfy schema gate: %s", msg)
            warned["emitted"] = True

        api_dict = await _prepare_prompt_async(
            workflow,
            backend=backend,
            schema_provider=provider,
            on_unavailable=on_unavailable,
        )
        try:
            queued = await ComfyClient(active_url).queue_prompt(api_dict)
        except Exception as exc:
            raise RuntimeError(_workflow_queue_failure_message(workflow, exc)) from exc
        prompt_id = queued.get("prompt_id") if isinstance(queued, dict) else None
        history = await _wait_for_server_history(active_url, prompt_id, config=resolved_config)
        comfy_outputs = _outputs_from_server_history(history, prompt_id)
        outputs = _collect_output_paths(
            comfy_outputs,
            output_directory=_configured_output_directory(resolved_config),
        )
    metadata = _run_metadata(
        run_id=run_id,
        workflow=workflow,
        api_dict=api_dict,
        queued=queued,
        comfy_outputs=comfy_outputs,
        outputs=outputs,
        runtime="server",
        config=managed_config,
    )
    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    return RunResult(
        run_id=run_id,
        prompt_id=prompt_id,
        outputs=outputs,
        metadata_path=str(metadata_path),
        log_path=str(log_path),
    )


def run_sync(
    workflow: VibeWorkflow,
    *,
    server_url: str | None = None,
    backend: str = "api",
    config: SessionConfig | None = None,
) -> RunResult:
    return asyncio.run(run(workflow, server_url=server_url, backend=backend, config=config))


async def run_embedded(
    workflow: VibeWorkflow,
    *,
    backend: str = "api",
    config: SessionConfig | None = None,
    ensure_packs: bool = False,
    ensure_models: bool = False,
) -> RunResult:
    session = EmbeddedSession(config or SessionConfig.from_workflow_metadata(workflow))
    try:
        return await session.run(workflow, backend=backend, ensure_packs=ensure_packs, ensure_models=ensure_models)
    finally:
        await session.stop()


def run_embedded_sync(
    workflow: VibeWorkflow,
    *,
    backend: str = "api",
    config: SessionConfig | None = None,
    ensure_packs: bool = False,
    ensure_models: bool = False,
) -> RunResult:
    return asyncio.run(run_embedded(workflow, backend=backend, config=config, ensure_packs=ensure_packs, ensure_models=ensure_models))


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
