# Runtime Surface

Observed runtime: HiddenSwitch ComfyUI `0.18.2` installed from `hiddenswitch/ComfyUI` commit `c5ed940244b1373daf855c0adbf2f7fd6dec327a`.

For the running compatibility ledger, see `docs/runtime/incompatibilities.md`.

## CLI Surface

Validated commands:

```bash
comfyui --help
comfyui serve --help
comfyui run-workflow --help
comfyui env check
comfyui nodes --help
```

`comfyui serve` starts the HTTP server. Useful flags include `--listen`, `--port`, `--guess-settings`, `--novram`, `--base-directory`, `--input-directory`, `--output-directory`, `--extra-model-paths-config`, `--disable-all-custom-nodes`, `--whitelist-custom-nodes`, `--blacklist-custom-nodes`, `--prompt`, `--steps`, `--seed`, and `--set`.

`comfyui run-workflow` executes workflow files and exits. It accepts local paths, URIs, literal JSON, and stdin. It supports `--all` for installing missing custom nodes and downloading known models, plus the same common override flags: `--prompt`, `--steps`, `--seed`, `--set`, `--output-directory`, `--cwd`, `--base-directory`, and device/VRAM flags.

`comfyui env check` prints the active runtime profile. On this local Mac it reported Python `3.11.11`, ComfyUI `0.18.2`, Torch `2.11.0`, no NVIDIA/AMD GPU, `mps`, 16 GB RAM, and missing local model directories.

## HTTP Surface

VibeComfy currently uses:

```text
GET  /system_stats
GET  /object_info
POST /prompt {"prompt": <api workflow dict>}
POST /api/free {"unload_models": true, "free_memory": true}
```

`/system_stats` is the readiness probe. `/object_info` is the node-definition source of truth and returned 1,202 node definitions in the local managed smoke. `/prompt` queues work but does not by itself prove the workflow finished, so it is a queue-submission path rather than the strongest end-to-end execution path.

`/api/free` is used for explicit server-session flushes. HiddenSwitch treats it as queue-async: it sets queue flags and applies at the next prompt boundary, not synchronously before the HTTP response returns.

## Embedded Surface

HiddenSwitch exposes `comfy.client.embedded_comfy_client.Comfy`.

Validated APIs:

```python
from comfy.client.embedded_comfy_client import Comfy

async with Comfy() as comfy:
    result = await comfy.queue_prompt_api(api_workflow)
```

This waits for workflow completion and returns output metadata. VibeComfy uses this as the local one-shot fallback when no warm managed session is active because it proves execution and output creation without managing an HTTP server.

Progress is available through:

```python
task = comfy.queue_with_progress(api_workflow)
async for notification in task.progress():
    ...
result = await task.get()
```

## VibeSession API

VibeComfy exposes a shared session shape for both warm backends:

```python
from vibecomfy.runtime.session import EmbeddedSession, ServerSession, SessionConfig

config = SessionConfig(warm_policy="auto", cache_policy="smart")

session = EmbeddedSession(config)
# or:
session = ServerSession(config)

await session.start()
try:
    result = await session.run(workflow)
    await session.flush()
    await session.reconfigure(config)
finally:
    await session.stop()
```

Session methods:

- `start()` opens the long-lived backend if it is not already running.
- `run(workflow, backend="api")` compiles and queues a workflow, applying the warm-policy flush gate before queueing.
- `flush()` explicitly releases cached/resident model state at the session boundary. Server flushes call `/api/free`, which is queue-async and applies at the next prompt boundary.
- `reconfigure(config)` applies a new `SessionConfig`; embedded sessions pass it through to `Comfy.reconfigure()`, and server sessions restart only when the resulting Comfy CLI arguments change.
- `stop()` closes the embedded context or terminates the managed server process.

Run metadata keeps the legacy `outputs` list as resolved artifact paths. It also exposes `comfy_outputs` for the raw Comfy return payload and `artifact_paths` as an explicit alias for resolved files, using `comfy_configuration.output_directory` when Comfy returns filename-only records.

`SessionConfig` fields:

- `vram_policy`: `auto`, `high`, `low`, or `normal`
- `reserve_vram_gb`
- `cache_policy`: `smart`, `classic`, `lru:N`, or `none`
- `disable_smart_memory`
- `warm_policy`: `auto`, `always`, or `never`
- `auto_flush_vram_threshold_gb`
- `port`
- `extra`: raw HiddenSwitch configuration keys not represented by typed fields

`EmbeddedSession` holds one `Comfy()` context across multiple `run()` calls. `ServerSession` holds one `comfyui serve` subprocess and uses HTTP for readiness, prompt queueing, and explicit flush.

## GraphBuilder

GraphBuilder is available at `comfy_execution.graph_utils.GraphBuilder`. Its own docstring describes it as a utility that outputs graphs in the form expected by the ComfyUI backend.

VibeComfy's optional `workflow.compile("graphbuilder")` backend now uses this class and has parity tests against the direct API-dict backend.

## Decisions

- Use `VibeWorkflow -> API dict` as the primary compiler path.
- Use `GraphBuilder` as an optional backend, not the only representation.
- Keep HTTP managed server mode for compatibility, `/object_info` discovery, and reusable warm sessions.
- Use embedded mode when the caller needs to wait for completed outputs or owns an in-process warm session.
- Treat `comfyui run-workflow` as an important parity check and operational fallback, not the core VibeComfy scratchpad API.
