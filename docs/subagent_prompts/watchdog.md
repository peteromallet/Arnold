# Subagent prompt: execution watchdog

You are working in `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`. This is a self-contained task — implement, then verify. Do not modify the materializer, the validator, or the model-staging logic; those are separate workstreams.

## Problem

Long-running LTX community workflows fail opaquely after roughly 280–350 seconds. The doc entry is `Long-running LTX community graphs do not fail cleanly` in `docs/hiddenswitch_incompatibilities.md` (Root cause: `runtime_observability`). Today, when a workflow stalls, all we know is "the run did not produce output before the timeout." We can't distinguish:

- **Slow node** — execution is progressing, just slowly.
- **Stalled runtime** — Comfy stopped emitting events but the process is alive.
- **OOM-ish behavior** — VRAM saturated and the runtime is thrashing or has fallen over.
- **Missing event stream** — we never connected to events in the first place.

ComfyUI emits events on a WebSocket at `/ws?clientId=<uuid>`. The current `vibecomfy/runtime/client.py` is HTTP-only. There is no event subscription anywhere in the runtime path. That gap is the whole problem.

## Scope

Add an execution watchdog that subscribes to Comfy's WebSocket event stream during a run and, on timeout (or any abnormal termination), dumps a structured summary of what was happening when the run stopped progressing.

Not in scope: changing how runs are submitted, retried, or scheduled. The watchdog observes; it does not intervene.

## Files to read before writing code

- `vibecomfy/runtime/client.py` — current HTTP client (httpx). The watchdog will add a WebSocket capability here or in a sibling module.
- `vibecomfy/runtime/session.py` — where `queue_prompt` is called for both embedded and spawned-server backends. The watchdog needs to wrap or sit alongside these call sites. Lines 111 and 189 are the two submit points.
- `vibecomfy/runtime/run.py` — single-shot runs.
- `docs/hiddenswitch_incompatibilities.md` — the failure class this work targets.

## ComfyUI WebSocket protocol (you can rely on this)

Connect to `ws://<server>/ws?clientId=<your_uuid>`. The server emits JSON messages:

- `{"type": "status", "data": {"status": {"exec_info": {"queue_remaining": N}}, "sid": "..."}}` — initial handshake; remember the `sid` if your client_id matches.
- `{"type": "execution_start", "data": {"prompt_id": "..."}}` — a prompt began executing.
- `{"type": "execution_cached", "data": {"nodes": [...], "prompt_id": "..."}}` — these nodes were cached and skipped.
- `{"type": "executing", "data": {"node": "<node_id>", "prompt_id": "...", "display_node": "..."}}` — node started; `node: null` means the prompt finished.
- `{"type": "progress", "data": {"value": N, "max": M, "prompt_id": "...", "node": "<node_id>"}}` — progress within a node (sampler steps, etc.).
- `{"type": "executed", "data": {"node": "<node_id>", "output": {...}, "prompt_id": "..."}}` — node produced output.
- `{"type": "execution_error", "data": {"prompt_id": "...", "node_id": "...", "node_type": "...", "exception_message": "...", ...}}` — node raised. Capture this and surface it.

Use the `websockets` Python package (already a transitive dep via `aio-pika`/`huggingface_hub` indirectly; if not, add it explicitly to `pyproject.toml`). Keep the connection alive for the duration of the run.

## What to build

1. **`vibecomfy/runtime/watchdog.py`** — new module. Public surface:
   - `WatchdogState` dataclass: `prompt_id`, `client_id`, `started_at`, `last_event_at`, `current_node_id`, `current_node_class_type`, `current_node_progress` (`{value, max}` or `None`), `executed_node_ids` (ordered list), `cached_node_ids`, `last_error` (None or the `execution_error` payload), `connection_state` (`connected | reconnecting | disconnected | never_connected`).
   - `Watchdog` class: takes server URL, client_id, the submitted API graph (so it can resolve `node_id → class_type` for messages), a poll interval for VRAM sampling (default 5s), and an optional timeout. Provides `async start()`, `async stop()`, and `dump() -> WatchdogReport`.
   - On a `progress`, `executing`, `executed`, or `execution_cached` message, update state. On `execution_error`, capture and stop. On any message, update `last_event_at`.
   - VRAM sampling: every poll interval, GET `/system_stats` and append `(timestamp, vram_free_bytes, vram_total_bytes)` to a ring buffer (capped at the most recent ~120 samples).
   - On `dump()`: produce a structured report (dict) that includes the full `WatchdogState`, the VRAM samples, and a one-line **diagnosis** chosen from:
     - `slow_node`: events still arriving in the last 30s, current node has been active >120s.
     - `stalled_runtime`: no events in the last 60s, but `/system_stats` still responsive.
     - `oom_ish`: VRAM free < 500MB for >3 consecutive samples, and current_node has been active >60s.
     - `missing_event_stream`: `connection_state == "never_connected"` or `"disconnected"` and we never received `execution_start`.
     - `crashed`: `/system_stats` not responsive.
     - `completed`: prompt finished cleanly (final `executing: null`).
     - `errored`: an `execution_error` was captured.
   - All diagnoses are heuristics, not contracts. Document the heuristic alongside each branch in the code.

2. **Wire into `vibecomfy/runtime/session.py`** at both submit sites (line 111 embedded, line 189 spawned). After `queue_prompt`, generate a UUID `client_id`, start a `Watchdog`, and arrange for `dump()` to be called when:
   - the run completes successfully (call `dump()` and write the report alongside the run's existing logs)
   - the run hits a timeout (the existing timeout path)
   - any exception bubbles out of the run path (finally block)
   The dump should land in `out/runpod_artifacts/<run>/watchdog.json` (or whatever the existing per-run artifact dir is — match the convention; check `_run_metadata` and adjacent code).

3. **Failure-mode dump format**: human-readable header line summarizing the diagnosis, then JSON body. The header should be greppable so a failed run's diagnosis is visible from a single `tail` of the orchestrator log. Example:
   ```
   WATCHDOG diagnosis=slow_node prompt_id=abc123 last_node=42 (KSamplerAdvanced) elapsed_in_node=183s vram_free=1.2GB
   {full json body...}
   ```

4. **One CLI escape hatch**: `vibecomfy watchdog tail <run_id>` reads the dumped JSON and pretty-prints it. Useful when triaging a failed run after the fact.

## Constraints

- **Reversibility**: the watchdog must be opt-out via env var (`VIBECOMFY_WATCHDOG=0`). On error inside the watchdog itself, log and continue — never let the watchdog crash a run.
- **No new heavyweight deps**. `websockets` is the only acceptable addition; it's small and pure-Python.
- **Embedded backend**: the embedded `comfy_kitchen` execution path may not expose a server-side WebSocket. If `/ws` is unreachable on the embedded backend, the watchdog should record `connection_state: never_connected` and continue without crashing — the VRAM-sampling and timeout-detection halves still work via `/system_stats`. Do not block the embedded path on WebSocket availability.
- **No CPU-heavy hot path**. The watchdog runs in an asyncio task; it should not poll faster than the configured interval (default 5s for VRAM, message-driven for state).

## Acceptance

- Reproduce a previously-failing LTX community workflow run (use one of the entries in `docs/hiddenswitch_incompatibilities.md` under `Long-running LTX community graphs do not fail cleanly`). The watchdog dump must produce a non-`completed` diagnosis with at least: which node was active, how long it had been active, the last 30s of progress events, and recent VRAM samples.
- Reproduce a clean run of one of the 14 runtime-green workflows. The watchdog dump must produce `completed` with the executed node sequence.
- Add unit tests under `tests/test_watchdog.py` that simulate WebSocket message sequences (use a mocked websocket or pytest-aiohttp) for each diagnosis branch.
- The watchdog must not regress any existing test or runtime path. If `VIBECOMFY_WATCHDOG=0` is set, behavior must be identical to today.

## Out of scope (do not do these)

- Auto-killing or restarting stalled runs. Diagnose only.
- Submitting telemetry to any external service.
- Persisting watchdog state across runs.
- Modifying any node, materializer, or validation logic.
- Adding a dashboard, web UI, or notification system.

## When done

Report the final dump JSON shape, the diagnosis branches and their thresholds, and any assumptions you made about Comfy's event payload structure (so they can be verified against the live runtime later).
