from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from vibecomfy.workflow import VibeWorkflow

from .client import ComfyClient
from .watchdog import Watchdog, write_report

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from comfy.cli_args_types import Configuration
else:
    Configuration = Any


OVERRIDES_INCLUDE: set[str] = set()
OVERRIDES_EXCLUDE: set[str] = set()


@dataclass(slots=True)
class RunResult:
    run_id: str
    prompt_id: str | None
    outputs: list[str]
    metadata_path: str
    log_path: str


@dataclass(slots=True)
class SessionConfig:
    vram_policy: str = "auto"
    reserve_vram_gb: float | None = None
    cache_policy: str = "smart"
    disable_smart_memory: bool = False
    warm_policy: str = "auto"
    auto_flush_vram_threshold_gb: float = 2.0
    port: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "SessionConfig":
        kwargs, extra = _partition_comfy_config(values)
        return cls(**kwargs, extra=extra)

    @classmethod
    def from_workflow_metadata(cls, workflow: VibeWorkflow) -> "SessionConfig":
        values = workflow.metadata.get("comfy_configuration", {})
        if not isinstance(values, dict):
            values = {}
        return cls.from_dict(values)


class VibeSession(Protocol):
    config: SessionConfig
    last_fingerprint: tuple[Any, ...] | None

    async def start(self) -> None:
        ...

    async def run(self, workflow: VibeWorkflow, *, backend: str = "api") -> RunResult:
        ...

    async def flush(self) -> None:
        ...

    async def reconfigure(self, config: SessionConfig) -> Any:
        ...

    async def stop(self, wait_for_inflight: bool = True) -> None:
        ...


class EmbeddedSession:
    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig()
        self.last_fingerprint: tuple[Any, ...] | None = None
        self._context: Any | None = None
        self._comfy: Any | None = None
        self._schema_provider: Any | None = None
        self._schema_warning_emitted = False
        self._inflight_run: asyncio.Task[Any] | None = None

    def _on_schema_unavailable(self, msg: str) -> None:
        if self._schema_warning_emitted:
            return
        logger.warning("vibecomfy schema gate: %s", msg)
        self._schema_warning_emitted = True

    async def start(self) -> None:
        if self._comfy is not None:
            return
        from comfy.client.embedded_comfy_client import Comfy

        self._context = Comfy(configuration=_embedded_configuration_for_session(self.config))
        self._comfy = await self._context.__aenter__()

    async def run(self, workflow: VibeWorkflow, *, backend: str = "api", ensure_packs: bool = False) -> RunResult:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("session already has a run in flight; concurrent run() is not supported in P1")
        if ensure_packs:
            from vibecomfy.node_packs_install import install_pack, missing_packs_for_workflow

            # Dev convenience only; production should pre-stage nodepacks with `vibecomfy nodes ensure`.
            try:
                packs, _unresolved = missing_packs_for_workflow(workflow)
            except (FileNotFoundError, ValueError) as exc:
                raise RuntimeError("ensure_packs: " + str(exc)) from exc
            installed_or_refreshed = False
            for pack in packs:
                result = install_pack(name=pack.name)
                if result.status not in {"installed", "refreshed"}:
                    raise RuntimeError(f"ensure_packs: install failed for {pack.name}: {result.error}")
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
                queued = await self._comfy.queue_prompt_api(api_dict)
            except asyncio.TimeoutError:
                stop_reason = "timeout"
                raise
            except Exception as exc:
                stop_reason = "exception"
                raise RuntimeError(f"Workflow queue failed: {exc}") from exc
        finally:
            await _finalize_watchdog(watchdog, run_dir=run_dir, reason=stop_reason)
        self.last_fingerprint = fp

        outputs = _collect_output_paths(getattr(queued, "outputs", queued))
        metadata = _run_metadata(
            run_id=run_id,
            workflow=workflow,
            api_dict=api_dict,
            queued=queued,
            outputs=outputs,
            runtime="embedded",
        )
        metadata_path = run_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        return RunResult(
            run_id=run_id,
            prompt_id=getattr(queued, "prompt_id", None),
            outputs=outputs,
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
            raise RuntimeError("reload_for_nodepack_change refused: run in flight")
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


class ServerSession:
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

    def _on_schema_unavailable(self, msg: str) -> None:
        if self._schema_warning_emitted:
            return
        logger.warning("vibecomfy schema gate: %s", msg)
        self._schema_warning_emitted = True

    async def start(self) -> None:
        if self.process is not None and self.process.returncode is None:
            return
        if self.process is not None:
            await self.stop()
        self.process, self.url, self.log_handle = await _spawn_comfy_server(self.config)
        self._argv = _comfy_server_argv(self.config)

    async def run(self, workflow: VibeWorkflow, *, backend: str = "api") -> RunResult:
        if self._inflight_run is not None and not self._inflight_run.done():
            raise RuntimeError("session already has a run in flight; concurrent run() is not supported in P1")
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
                queued = await ComfyClient(self.url).queue_prompt(api_dict)
            except asyncio.TimeoutError:
                stop_reason = "timeout"
                raise
            except Exception as exc:
                stop_reason = "exception"
                raise RuntimeError(f"Workflow queue failed: {exc}") from exc
        finally:
            await _finalize_watchdog(watchdog, run_dir=run_dir, reason=stop_reason)
        self.last_fingerprint = fp
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
            raise RuntimeError("reload_for_nodepack_change refused: run in flight")
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
        raise RuntimeError(
            "session.stop() called while a run is in flight; pass wait_for_inflight=True or call after run completes"
        )
    if task is asyncio.current_task():
        raise RuntimeError("session.stop() called from the in-flight run; call after run completes")
    try:
        await task
    except BaseException:
        session._inflight_run = None
        raise
    session._inflight_run = None


def find_active_session(id: str = "default") -> str | None:
    session_dir = Path("out/sessions") / id
    pid_path = session_dir / "pid"
    url_path = session_dir / "url"
    if not pid_path.exists() or not url_path.exists():
        _cleanup_session_files(session_dir)
        return None
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        url = url_path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        _cleanup_session_files(session_dir)
        return None
    if not url:
        _cleanup_session_files(session_dir)
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        _cleanup_session_files(session_dir)
        return None
    except PermissionError:
        return url
    except OSError:
        _cleanup_session_files(session_dir)
        return None
    return url


def _cleanup_session_files(session_dir: Path) -> None:
    for name in ("pid", "url", "config.json"):
        try:
            (session_dir / name).unlink()
        except FileNotFoundError:
            pass


def _partition_comfy_config(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split mixed config into SessionConfig kwargs and raw extra Comfy keys.

    HiddenSwitch keys are translated first, then typed SessionConfig field
    names overwrite translated values when both forms are present.
    """
    typed_fields = {
        "port",
        "vram_policy",
        "cache_policy",
        "warm_policy",
        "reserve_vram_gb",
        "disable_smart_memory",
        "auto_flush_vram_threshold_gb",
    }
    kwargs: dict[str, Any] = {}
    extra: dict[str, Any] = {}

    for key, value in values.items():
        if key in typed_fields:
            continue
        if key == "reserve_vram":
            kwargs["reserve_vram_gb"] = value
        elif key in {"highvram", "lowvram", "normalvram"}:
            if value:
                kwargs["vram_policy"] = key.removesuffix("vram")
        elif key == "cache_none":
            if value:
                kwargs["cache_policy"] = "none"
        elif key == "cache_classic":
            if value:
                kwargs["cache_policy"] = "classic"
        elif key == "cache_lru":
            if value:
                kwargs["cache_policy"] = f"lru:{value}"
        else:
            extra[key] = value

    for key, value in values.items():
        if key in typed_fields:
            kwargs[key] = value

    return kwargs, extra


def _schema_validate_disabled() -> bool:
    return os.environ.get("VIBECOMFY_SCHEMA_VALIDATE", "1").strip() in {"0", "false", "False", "no", "off"}


def _build_schema_provider(server_url: str | None) -> Any | None:
    if _schema_validate_disabled():
        return None
    from vibecomfy.schema import RuntimeSchemaProvider

    return RuntimeSchemaProvider(server_url=server_url)


async def _warm_schema_provider(
    provider: Any | None,
    *,
    on_unavailable,
    cache_only: bool = False,
) -> Any | None:
    if provider is None:
        return None
    try:
        if getattr(provider, "_object_info", None) is not None:
            return provider
        if cache_only:
            from vibecomfy.schema.cache import load_object_info_cache

            cached = load_object_info_cache(provider.cache_path)
            if cached is None:
                on_unavailable(f"object_info cache unavailable at {provider.cache_path}; using structural validation only")
                return None
            provider._object_info = cached
            return provider

        provider._object_info = await provider.object_info_async()
        return provider
    except (OSError, RuntimeError, TimeoutError) as exc:
        on_unavailable(f"{type(exc).__name__}: {exc}; using structural validation only")
        return None


def _prepare_prompt(
    workflow: VibeWorkflow,
    *,
    backend: str,
    schema_provider: Any | None = None,
) -> dict[str, Any]:
    # Schema validation: cache-hit on every submit after the first per-runtime; first-fetch latency acceptable.
    report = workflow.validate(schema_provider=schema_provider)
    if not report.ok:
        messages = "; ".join(issue.message for issue in report.issues)
        raise ValueError(f"Workflow validation failed: {messages}")

    try:
        return workflow.compile(backend=backend)
    except ValueError as exc:
        raise ValueError(f"Workflow build failed: {exc}") from exc
    except RuntimeError as exc:
        raise RuntimeError(f"Workflow build failed: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Workflow build failed: {exc}") from exc


async def _prepare_prompt_async(
    workflow: VibeWorkflow,
    *,
    backend: str,
    schema_provider: Any | None,
    on_unavailable,
    cache_only: bool = False,
) -> dict[str, Any]:
    effective = await _warm_schema_provider(
        schema_provider,
        on_unavailable=on_unavailable,
        cache_only=cache_only,
    )
    report = workflow.validate(schema_provider=effective)
    if not report.ok:
        raise ValueError(_validation_failed_message(report))

    try:
        return workflow.compile(backend=backend)
    except ValueError as exc:
        raise ValueError(f"Workflow build failed: {exc}") from exc
    except RuntimeError as exc:
        raise RuntimeError(f"Workflow build failed: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Workflow build failed: {exc}") from exc


def _validation_failed_message(report: Any) -> str:
    from vibecomfy.schema.format import format_issue

    return "Workflow validation failed:\n  - " + "\n  - ".join(
        format_issue(issue) for issue in report.issues if issue.severity == "error"
    )


def _run_metadata(
    *,
    run_id: str,
    workflow: VibeWorkflow,
    api_dict: dict[str, Any],
    queued: Any,
    outputs: list[str],
    runtime: str,
) -> dict[str, Any]:
    serialized = json.dumps(api_dict, sort_keys=True, default=str)
    return {
        "run_id": run_id,
        "workflow_id": workflow.id,
        "source": asdict(workflow.source),
        "workflow_hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "git_sha": _git_sha(),
        "inputs": {name: item.value for name, item in workflow.inputs.items()},
        "queued": queued,
        "outputs": outputs,
        "runtime": runtime,
    }


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _collect_output_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"abs_path", "path", "fullpath", "filename"} and isinstance(item, str):
                paths.append(item)
            else:
                paths.extend(_collect_output_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(_collect_output_paths(item))
    return paths


def _embedded_configuration_for_session(config: SessionConfig) -> Configuration | None:
    values: dict[str, Any] = {}
    if config.port is not None:
        values["port"] = config.port
    if config.vram_policy in {"high", "low", "normal"}:
        values[f"{config.vram_policy}vram"] = True
    if config.reserve_vram_gb is not None:
        values["reserve_vram"] = config.reserve_vram_gb
    if config.cache_policy == "classic":
        values["cache_classic"] = True
    elif config.cache_policy == "none":
        values["cache_none"] = True
    elif config.cache_policy.startswith("lru:"):
        values["cache_lru"] = int(config.cache_policy.split(":", 1)[1])
    if config.disable_smart_memory:
        values["disable_smart_memory"] = True

    values.update(config.extra)
    env_config = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if env_config:
        parsed = json.loads(env_config)
        if not isinstance(parsed, dict):
            raise ValueError("VIBECOMFY_COMFY_CONFIGURATION must be a JSON object")
        values.update(parsed)
    if not values:
        return None

    from comfy.client.embedded_comfy_client import default_configuration

    configuration = default_configuration()
    configuration.update(values)
    return configuration


def _embedded_configuration(workflow: VibeWorkflow) -> Configuration | None:
    return _embedded_configuration_for_session(SessionConfig.from_workflow_metadata(workflow))


def _comfy_server_argv(config: SessionConfig) -> tuple[str, ...]:
    argv = [_comfyui_executable(), "serve"]
    if config.vram_policy in {"high", "low", "normal"}:
        argv.append(f"--{config.vram_policy}vram")
    if config.reserve_vram_gb is not None:
        argv.extend(["--reserve-vram", str(config.reserve_vram_gb)])
    if config.disable_smart_memory:
        argv.append("--disable-smart-memory")
    if config.cache_policy == "classic":
        argv.append("--cache-classic")
    elif config.cache_policy == "none":
        argv.append("--cache-none")
    elif config.cache_policy.startswith("lru:"):
        argv.extend(["--cache-lru", config.cache_policy.split(":", 1)[1]])
    argv.extend(["--port", str(config.port or 8188)])
    return tuple(argv)


async def _spawn_comfy_server(
    config: SessionConfig, log_path: str | Path | None = None
) -> tuple[asyncio.subprocess.Process, str, Any | None]:
    log_handle = None
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        log_handle = Path(log_path).open("ab", buffering=0)
    argv = _comfy_server_argv(config)
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=log_handle or asyncio.subprocess.DEVNULL,
        stderr=log_handle or asyncio.subprocess.DEVNULL,
        env=os.environ.copy(),
    )
    managed_url = f"http://127.0.0.1:{config.port or 8188}"
    client = ComfyClient(managed_url)
    for _ in range(120):
        if await client.ready():
            break
        await asyncio.sleep(1)
    else:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if log_handle:
            log_handle.close()
        raise TimeoutError("Managed Comfy server did not become ready within 120 seconds")
    return process, managed_url, log_handle


def _comfyui_executable() -> str:
    executable = shutil.which("comfyui")
    if executable:
        return executable
    sibling = Path(sys.executable).with_name("comfyui")
    if sibling.exists():
        return str(sibling)
    return "comfyui"


async def _maybe_flush_for_policy(session: VibeSession, fp: tuple[Any, ...]) -> None:
    warm_policy = os.environ.get("VIBECOMFY_WARM", session.config.warm_policy).strip().lower()
    if warm_policy == "never":
        await session.flush()
    elif (
        warm_policy == "auto"
        and session.last_fingerprint is not None
        and fp != session.last_fingerprint
        and _free_vram_gb() < session.config.auto_flush_vram_threshold_gb
    ):
        await session.flush()


def _free_vram_gb() -> float:
    try:
        from comfy.model_management import get_free_memory
    except (ImportError, AttributeError):
        return float("inf")

    try:
        return float(get_free_memory()) / (1024**3)
    except (ImportError, AttributeError):
        return float("inf")


def _embedded_observation_url(config: SessionConfig) -> str:
    """Best-guess HTTP base for the embedded backend.

    The embedded backend may or may not expose a server. The watchdog tolerates
    either case: if the URL is unreachable we record connection_state=
    never_connected and continue with VRAM sampling (which will also fail
    silently and be reflected in the diagnosis).
    """
    port = config.port or 8188
    return f"http://127.0.0.1:{port}"


async def _start_watchdog(
    *,
    server_url: str | None,
    client_id: str,
    api_dict: dict[str, Any],
) -> Watchdog | None:
    """Build and start a Watchdog. Returns None if disabled or failed to start.

    The watchdog must NEVER raise into the run path. Any error here is logged
    and ignored. Must be called from inside a running event loop.
    """
    if os.environ.get("VIBECOMFY_WATCHDOG", "1").strip() in {"0", "false", "False", "no", "off"}:
        return None
    if not server_url:
        return None
    try:
        wd = Watchdog(server_url=server_url, client_id=client_id, api_dict=api_dict)
    except Exception:
        logger.exception("watchdog: construction failed; continuing without it")
        return None
    try:
        await wd.start()
    except Exception:
        logger.exception("watchdog: start scheduling failed; continuing without it")
        return None
    return wd


async def _finalize_watchdog(
    watchdog: Watchdog | None,
    *,
    run_dir: Path,
    reason: str,
) -> None:
    """Stop the watchdog and write its report. Errors are swallowed."""
    if watchdog is None:
        return
    try:
        await watchdog.stop(reason=reason)
        report = watchdog.dump()
        path = write_report(run_dir, report)
        # Greppable header on the orchestrator log so a single tail shows it.
        logger.info("%s path=%s", report.header_line(), path)
    except Exception:
        logger.exception("watchdog: finalize failed; ignoring")


def model_fingerprint(api_dict: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    triples: list[tuple[str, str, str]] = []
    for node in api_dict.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str):
            continue
        include = class_type in OVERRIDES_INCLUDE or (
            "Loader" in class_type and class_type not in OVERRIDES_EXCLUDE
        )
        if not include:
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for slot, value in inputs.items():
            if isinstance(slot, str) and isinstance(value, str):
                triples.append((class_type, slot, value))
    return tuple(sorted(triples))
