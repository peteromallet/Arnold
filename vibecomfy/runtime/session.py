from __future__ import annotations

import asyncio
import json
import logging
import os as _os
import signal
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

from vibecomfy.errors import (
    NodePackInstallError,
    SessionBusyError,
    SessionLifecycleError,
    WorkflowQueueError,
)
from vibecomfy.workflow import VibeWorkflow

from . import config as _config_module
from . import discovery as _discovery_module
from . import fingerprint as _fingerprint_module
from . import prompt as _prompt_module
from . import server_process as _server_process_module
from .client import ComfyClient
from .execution import queue_embedded_prompt, queue_server_prompt
from .metadata import _run_metadata
from .policy import _free_vram_gb
from .policy import _maybe_flush_for_policy as _policy_maybe_flush_for_policy
from .watchdog_runtime import _embedded_observation_url, _finalize_watchdog, _start_watchdog

logger = logging.getLogger(__name__)

os = _os
SessionConfig = _config_module.SessionConfig
OVERRIDES_EXCLUDE = _fingerprint_module.OVERRIDES_EXCLUDE
OVERRIDES_INCLUDE = _fingerprint_module.OVERRIDES_INCLUDE
apply_memory_profile_override = _config_module.apply_memory_profile_override
find_active_session = _discovery_module.find_active_session
model_fingerprint = _fingerprint_module.model_fingerprint
_build_schema_provider = _prompt_module._build_schema_provider
_cleanup_session_files = _discovery_module._cleanup_session_files
_comfy_server_argv = _config_module._comfy_server_argv
_comfyui_executable = _server_process_module._comfyui_executable
_embedded_configuration = _config_module._embedded_configuration
_embedded_configuration_for_session = _config_module._embedded_configuration_for_session
_partition_comfy_config = _config_module._partition_comfy_config
_prepare_prompt = _prompt_module._prepare_prompt
_prepare_prompt_async = _prompt_module._prepare_prompt_async
_spawn_comfy_server = _server_process_module._spawn_comfy_server
_validation_failed_message = _prompt_module._validation_failed_message
_warm_schema_provider = _prompt_module._warm_schema_provider

__all__ = [
    "EmbeddedSession",
    "RunResult",
    "ServerSession",
    "SessionConfig",
    "VibeSession",
    "OVERRIDES_EXCLUDE",
    "OVERRIDES_INCLUDE",
    "apply_memory_profile_override",
    "find_active_session",
    "model_fingerprint",
    "os",
    "queue_embedded_prompt",
    "queue_server_prompt",
    "_build_schema_provider",
    "_cleanup_session_files",
    "_comfy_server_argv",
    "_comfyui_executable",
    "_embedded_configuration",
    "_embedded_configuration_for_session",
    "_finalize_watchdog",
    "_free_vram_gb",
    "_maybe_flush_for_policy",
    "_partition_comfy_config",
    "_prepare_prompt",
    "_prepare_prompt_async",
    "_run_metadata",
    "_spawn_comfy_server",
    "_start_watchdog",
    "_validation_failed_message",
    "_warm_schema_provider",
]


VibeSession: TypeAlias = Any


@dataclass(slots=True)
class RunResult:
    run_id: str
    prompt_id: str | None
    outputs: list[str]
    metadata_path: str
    log_path: str


class _SchemaUnavailableMixin:
    def _on_schema_unavailable(self, msg: str) -> None:
        _prompt_module.emit_schema_unavailable_once(self, logger, msg)


class EmbeddedSession(_SchemaUnavailableMixin):
    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig()
        self.last_fingerprint: tuple[Any, ...] | None = None
        self._context: Any | None = None
        self._comfy: Any | None = None
        self._schema_provider: Any | None = None
        self._schema_warning_emitted = False
        self._inflight_run: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        if self._comfy is not None:
            return
        from comfy.client.embedded_comfy_client import Comfy

        self._context = Comfy(configuration=_embedded_configuration_for_session(self.config))
        self._comfy = await self._context.__aenter__()

    async def run(self, workflow: VibeWorkflow, *, backend: str = "api", ensure_packs: bool = False) -> RunResult:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise SessionBusyError(
                "session already has a run in flight; concurrent run() is not supported in P1",
                next_action="Wait for the current run to complete, or create a separate session for concurrent work.",
            )
        if ensure_packs:
            from vibecomfy.node_packs_install import install_pack, missing_packs_for_workflow

            # Dev convenience only; production should pre-stage nodepacks with `vibecomfy nodes ensure`.
            try:
                packs, _unresolved = missing_packs_for_workflow(workflow)
            except (FileNotFoundError, ValueError) as exc:
                raise NodePackInstallError(
                    "ensure_packs: " + str(exc),
                    next_action="Run `python -m vibecomfy.cli sources sync`, then retry or use `vibecomfy nodes ensure` explicitly.",
                ) from exc
            installed_or_refreshed = False
            for pack in packs:
                result = install_pack(name=pack.name)
                if result.status not in {"installed", "refreshed"}:
                    raise NodePackInstallError(
                        f"ensure_packs: install failed for {pack.name}: {result.error}",
                        next_action="Inspect the custom node install error, then run `vibecomfy nodes ensure` after fixing the pack.",
                    )
                installed_or_refreshed = True
            if installed_or_refreshed:
                await self.reload_for_nodepack_change(reason="ensure_packs")
        task = asyncio.current_task()
        self._inflight_run = task
        try:
            return await self._run_untracked(workflow, backend=backend)
        finally:
            if self._inflight_run is task:
                self._inflight_run = None

    async def _run_untracked(self, workflow: VibeWorkflow, *, backend: str = "api") -> RunResult:
        await self.start()
        assert self._comfy is not None
        if self._schema_provider is None:
            self._schema_provider = _build_schema_provider(None)
        api_dict = await _prepare_prompt_async(
            workflow,
            backend=backend,
            schema_provider=self._schema_provider,
            on_unavailable=self._on_schema_unavailable,
            cache_only=True,
        )
        fp = model_fingerprint(api_dict)

        await _maybe_flush_for_policy(self, fp)

        run_id = f"run-{int(time.time())}"
        run_dir = Path("out/runs") / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "embedded.log"

        # Embedded backend: comfy_kitchen does not necessarily expose a server
        # WebSocket. The watchdog will record connection_state=never_connected
        # in that case but VRAM-sampling and timeout-detection still work via
        # /system_stats if the embedded backend exposes one. We pass the local
        # loopback URL with whatever port the SessionConfig requests; if the
        # endpoint is unreachable the watchdog handles it gracefully.
        client_id = uuid.uuid4().hex
        ws_url = _embedded_observation_url(self.config)
        watchdog = await _start_watchdog(server_url=ws_url, client_id=client_id, api_dict=api_dict)
        stop_reason = "completed"
        try:
            try:
                execution = await queue_embedded_prompt(self._comfy, api_dict)
            except asyncio.TimeoutError:
                stop_reason = "timeout"
                raise
            except WorkflowQueueError:
                stop_reason = "exception"
                raise
            except Exception as exc:
                stop_reason = "exception"
                raise WorkflowQueueError(
                    f"Workflow queue failed: {exc}",
                    next_action="Check the embedded ComfyUI logs and verify the workflow can be queued by the active runtime.",
                ) from exc
        finally:
            await _finalize_watchdog(watchdog, run_dir=run_dir, reason=stop_reason)
        self.last_fingerprint = fp

        metadata = _run_metadata(
            run_id=run_id,
            workflow=workflow,
            api_dict=api_dict,
            queued=execution.queued,
            outputs=execution.outputs,
            runtime="embedded",
            config=self.config,
        )
        metadata_path = run_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        return RunResult(
            run_id=run_id,
            prompt_id=execution.prompt_id,
            outputs=execution.outputs,
            metadata_path=str(metadata_path),
            log_path=str(log_path),
        )

    async def flush(self) -> None:
        if self._comfy is None:
            return
        await self._comfy.clear_cache()

    async def reconfigure(self, config: SessionConfig) -> Any:
        self.config = config
        if self._comfy is None:
            return None
        return await self._comfy.reconfigure(_embedded_configuration_for_session(config))

    async def stop(self, wait_for_inflight: bool = True) -> None:
        await _resolve_inflight_before_stop(self, wait_for_inflight)
        if self._context is None:
            return
        try:
            await self._context.__aexit__(None, None, None)
        except AttributeError as exc:
            if "model_mmap_residency" not in str(exc):
                raise
        finally:
            self._context = None
            self._comfy = None

    async def reload_for_nodepack_change(self, *, reason: str) -> None:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise SessionLifecycleError(
                "reload_for_nodepack_change refused: run in flight",
                next_action="Wait for the in-flight run to finish before reloading custom node packs.",
            )
        logger.info("reload_for_nodepack_change: %s", reason)
        if self._context is not None:
            try:
                await self._context.__aexit__(None, None, None)
            except AttributeError as exc:
                if "model_mmap_residency" not in str(exc):
                    raise
        self._comfy = None
        self._context = None
        self._schema_provider = None
        self._schema_warning_emitted = False
        self.last_fingerprint = None
        await self.start()


class ServerSession(_SchemaUnavailableMixin):
    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig()
        self.last_fingerprint: tuple[Any, ...] | None = None
        self.process: asyncio.subprocess.Process | None = None
        self.url: str | None = None
        self.log_handle: Any | None = None
        self._argv = _comfy_server_argv(self.config)
        self._schema_provider: Any | None = None
        self._schema_warning_emitted = False
        self._inflight_run: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        if self.process is not None and self.process.returncode is None:
            return
        if self.process is not None:
            await self.stop()
        self.process, self.url, self.log_handle = await _spawn_comfy_server(self.config)
        self._argv = _comfy_server_argv(self.config)

    async def run(self, workflow: VibeWorkflow, *, backend: str = "api") -> RunResult:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise SessionBusyError(
                "session already has a run in flight; concurrent run() is not supported in P1",
                next_action="Wait for the current run to complete, or create a separate session for concurrent work.",
            )
        task = asyncio.current_task()
        self._inflight_run = task
        try:
            return await self._run_untracked(workflow, backend=backend)
        finally:
            if self._inflight_run is task:
                self._inflight_run = None

    async def _run_untracked(self, workflow: VibeWorkflow, *, backend: str = "api") -> RunResult:
        await self.start()
        assert self.url is not None
        if self._schema_provider is None:
            self._schema_provider = _build_schema_provider(self.url)
        api_dict = await _prepare_prompt_async(
            workflow,
            backend=backend,
            schema_provider=self._schema_provider,
            on_unavailable=self._on_schema_unavailable,
        )
        fp = model_fingerprint(api_dict)

        await _maybe_flush_for_policy(self, fp)

        run_id = f"run-{int(time.time())}"
        run_dir = Path("out/runs") / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "comfy.log"

        client_id = uuid.uuid4().hex
        watchdog = await _start_watchdog(server_url=self.url, client_id=client_id, api_dict=api_dict)
        stop_reason = "completed"
        try:
            try:
                execution = await queue_server_prompt(api_dict, client=ComfyClient(self.url))
            except asyncio.TimeoutError:
                stop_reason = "timeout"
                raise
            except WorkflowQueueError:
                stop_reason = "exception"
                raise
            except Exception as exc:
                stop_reason = "exception"
                raise WorkflowQueueError(
                    f"Workflow queue failed: {exc}",
                    next_action="Check server health, the ComfyUI logs, and whether the workflow payload is accepted by this runtime.",
                ) from exc
        finally:
            await _finalize_watchdog(watchdog, run_dir=run_dir, reason=stop_reason)
        self.last_fingerprint = fp
        metadata = _run_metadata(
            run_id=run_id,
            workflow=workflow,
            api_dict=api_dict,
            queued=execution.queued,
            outputs=execution.outputs,
            runtime="server",
            config=self.config,
        )
        metadata_path = run_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        return RunResult(
            run_id=run_id,
            prompt_id=execution.prompt_id,
            outputs=execution.outputs,
            metadata_path=str(metadata_path),
            log_path=str(log_path),
        )

    async def flush(self) -> None:
        await self.start()
        assert self.url is not None
        await ComfyClient(self.url).free(unload_models=True, free_memory=True)

    async def reconfigure(self, config: SessionConfig) -> bool:
        new_argv = _comfy_server_argv(config)
        if new_argv == self._argv:
            self.config = config
            return False
        await self.stop()
        self.config = config
        self._argv = new_argv
        await self.start()
        return True

    async def stop(self, wait_for_inflight: bool = True) -> None:
        await _resolve_inflight_before_stop(self, wait_for_inflight)
        process = self.process
        if process is not None and process.returncode is None:
            process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), timeout=15)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if self.log_handle:
            self.log_handle.close()
        self.process = None
        self.url = None
        self.log_handle = None

    async def reload_for_nodepack_change(self, *, reason: str) -> None:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise SessionLifecycleError(
                "reload_for_nodepack_change refused: run in flight",
                next_action="Wait for the in-flight run to finish before reloading custom node packs.",
            )
        # NOTE: ServerSession external-mode handling (attach to a server VibeComfy didn't spawn) is deferred to MP-5 alongside session-shared multi-stage orchestration. Current production paths route external server URLs through comfy_server(server_url=...) in vibecomfy/runtime/server.py, which already skips spawn/cleanup for external URLs.
        await self.stop()
        await self.start()
        logger.info("reload_for_nodepack_change: %s", reason)


async def _resolve_inflight_before_stop(session: Any, wait_for_inflight: bool) -> None:
    task = getattr(session, "_inflight_run", None)
    if task is None:
        return
    if task.done():
        session._inflight_run = None
        return
    if not wait_for_inflight:
        raise SessionLifecycleError(
            "session.stop() called while a run is in flight; pass wait_for_inflight=True or call after run completes",
            next_action="Wait for the run to complete, or call stop(wait_for_inflight=True) from another task.",
        )
    if task is asyncio.current_task():
        raise SessionLifecycleError(
            "session.stop() called from the in-flight run; call after run completes",
            next_action="Move stop() outside the running task or wait until run() returns.",
        )
    try:
        await task
    except BaseException:
        session._inflight_run = None
        raise
    session._inflight_run = None


async def _maybe_flush_for_policy(session: VibeSession, fp: tuple[Any, ...]) -> None:
    await _policy_maybe_flush_for_policy(session, fp, free_vram_gb=_free_vram_gb)
